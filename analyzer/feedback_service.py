"""OpenAI-compatible client for the strict feedback-v0.1 verifier."""

from __future__ import annotations

import json
import os
from typing import Any, Callable

from analyzer.feedback_contract import build_request, parse_output
from evaluation.judgment.runner import call_endpoint


DEFAULT_ENDPOINT = "http://127.0.0.1:1235/v1/chat/completions"
Transport = Callable[..., dict[str, Any]]


class FeedbackServiceError(RuntimeError):
    def __init__(self, category: str):
        super().__init__(category)
        self.category = category


def run_feedback(
    text: str,
    *,
    context: str | None,
    learner_level: str,
    judgment: dict[str, Any],
    endpoint: str | None = None,
    model_name: str | None = None,
    timeout: float | None = None,
    transport: Transport = call_endpoint,
) -> dict[str, Any]:
    endpoint = endpoint or os.getenv("FEEDBACK_ENDPOINT", DEFAULT_ENDPOINT)
    model_name = model_name or os.getenv("FEEDBACK_MODEL", "feedback-qwen3-8b-v01")
    if timeout is None:
        try:
            timeout = float(os.getenv("FEEDBACK_TIMEOUT_SECONDS", "120"))
        except ValueError as exc:
            raise FeedbackServiceError("configuration") from exc
    if timeout <= 0:
        raise FeedbackServiceError("configuration")
    try:
        request = build_request({
            "text": text, "context": context, "learner_level": learner_level,
            "judgment": judgment,
        }, model_name)
        response = transport(endpoint=endpoint, request_body=request, timeout=timeout, api_key=None)
    except FeedbackServiceError:
        raise
    except Exception as exc:
        raise FeedbackServiceError("transport") from exc
    if not isinstance(response, dict) or not response.get("transport_success"):
        raise FeedbackServiceError("transport")
    parsed, error = parse_output(response.get("raw_text", ""), text)
    if parsed is None:
        raise FeedbackServiceError("contract")
    parsed["latency_ms"] = response.get("latency_ms")
    return parsed


def judgment_input(row: Any) -> dict[str, Any]:
    return {
        "decision": row.decision,
        "corrected_text": row.corrected_text,
        "error_types": json.loads(row.error_types),
        "reason_ko": row.reason_ko,
    }
