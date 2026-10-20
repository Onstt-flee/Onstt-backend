"""OpenAI-compatible client for the strict feedback-v0.1 verifier."""

from __future__ import annotations

import json
import os
from typing import Any, Callable

from analyzer.feedback_contract import (
    CONTRACT_VERSION as LEGACY_CONTRACT_VERSION,
    build_request,
    parse_output,
)
from analyzer.feedback_two_stage_contract import (
    CONTRACT_VERSION as TWO_STAGE_CONTRACT_VERSION,
    build_stage1_request,
    build_stage2_request,
    combine_outputs,
    parse_stage1_output,
    parse_stage2_output,
    should_call_stage2,
)
from evaluation.judgment.runner import call_endpoint


DEFAULT_ENDPOINT = "http://127.0.0.1:1235/v1/chat/completions"
Transport = Callable[..., dict[str, Any]]


class FeedbackServiceError(RuntimeError):
    def __init__(self, category: str):
        super().__init__(category)
        self.category = category


def _call_model(
    *, endpoint: str, request: dict[str, Any], timeout: float, transport: Transport,
) -> dict[str, Any]:
    try:
        response = transport(endpoint=endpoint, request_body=request, timeout=timeout, api_key=None)
    except FeedbackServiceError:
        raise
    except Exception as exc:
        raise FeedbackServiceError("transport") from exc
    if not isinstance(response, dict) or not response.get("transport_success"):
        raise FeedbackServiceError("transport")
    return response


def _latency_ms(response: dict[str, Any]) -> float:
    value = response.get("latency_ms")
    return float(value) if isinstance(value, (int, float)) else 0.0


def run_feedback(
    text: str,
    *,
    context: str | None,
    learner_level: str,
    judgment: dict[str, Any],
    endpoint: str | None = None,
    model_name: str | None = None,
    timeout: float | None = None,
    contract_version: str | None = None,
    transport: Transport = call_endpoint,
) -> dict[str, Any]:
    endpoint = endpoint or os.getenv("FEEDBACK_ENDPOINT", DEFAULT_ENDPOINT)
    model_name = model_name or os.getenv("FEEDBACK_MODEL", "feedback-qwen3-8b-v01")
    contract_version = contract_version or os.getenv(
        "FEEDBACK_CONTRACT_VERSION", LEGACY_CONTRACT_VERSION
    ).strip()
    if timeout is None:
        try:
            timeout = float(os.getenv("FEEDBACK_TIMEOUT_SECONDS", "120"))
        except ValueError as exc:
            raise FeedbackServiceError("configuration") from exc
    if timeout <= 0:
        raise FeedbackServiceError("configuration")
    model_input = {
        "text": text, "context": context, "learner_level": learner_level,
        "judgment": judgment,
    }
    try:
        if contract_version == LEGACY_CONTRACT_VERSION:
            request = build_request(model_input, model_name)
            response = _call_model(
                endpoint=endpoint, request=request, timeout=timeout, transport=transport
            )
            parsed, error = parse_output(response.get("raw_text", ""), text)
            if parsed is None:
                raise FeedbackServiceError("contract")
            parsed["latency_ms"] = response.get("latency_ms")
            return parsed
        if contract_version != TWO_STAGE_CONTRACT_VERSION:
            raise FeedbackServiceError("configuration")
        stage1_response = _call_model(
            endpoint=endpoint,
            request=build_stage1_request(model_input, model_name),
            timeout=timeout, transport=transport,
        )
        stage1, error = parse_stage1_output(stage1_response.get("raw_text", ""))
        if stage1 is None:
            raise FeedbackServiceError("contract_stage1")
        stage2 = None
        latency_ms = _latency_ms(stage1_response)
        if should_call_stage2(stage1):
            stage2_response = _call_model(
                endpoint=endpoint,
                request=build_stage2_request(model_input, stage1, model_name),
                timeout=timeout, transport=transport,
            )
            stage2, error = parse_stage2_output(
                stage2_response.get("raw_text", ""), text, stage1["issue_codes"]
            )
            if stage2 is None:
                raise FeedbackServiceError("contract_stage2")
            latency_ms += _latency_ms(stage2_response)
        result = combine_outputs(stage1, stage2)
        result["latency_ms"] = latency_ms
        return result
    except FeedbackServiceError:
        raise
    except (TypeError, ValueError) as exc:
        raise FeedbackServiceError("contract") from exc


def judgment_input(row: Any) -> dict[str, Any]:
    return {
        "decision": row.decision,
        "corrected_text": row.corrected_text,
        "error_types": json.loads(row.error_types),
        "reason_ko": row.reason_ko,
    }
