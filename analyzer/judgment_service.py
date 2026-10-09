"""Feature-flagged D-only judgment model client for the operating API."""

from __future__ import annotations

import os
from typing import Any, Callable

from evaluation.judgment.runner import (
    DEFAULT_ENDPOINT,
    PROMPT_VERSION_V2,
    build_request,
    call_endpoint,
    parse_model_output,
)


DEFAULT_MODEL = "judgment-v02d"
DEFAULT_ADAPTER = "judgment-qwen3-4b-failure-focus-v0.2-d"
CONTRACT_VERSION = "judgment-v0.2"
STRATEGY = "d_only"
SELECTION_REASON = "primary_selected_by_holdout_v0.3"
PRESERVATION_CONTRACT_ERROR = "Non-correction decisions must preserve input text"
RETRY_INSTRUCTION = (
    "\n\n이전 응답이 비교정 판단의 원문 보존 계약을 위반했습니다. "
    "acceptable 또는 insufficient_evidence를 선택하면 corrected_text를 입력 text와 "
    "Unicode 코드 포인트까지 완전히 동일하게 복사하고 error_types를 빈 배열로 출력하세요. "
    "needs_correction인 경우에만 최소 교정문을 출력하세요. JSON 객체 하나만 반환하세요."
)
Transport = Callable[..., dict[str, Any]]


class JudgmentServiceError(RuntimeError):
    """Model transport or output-contract failure safe to expose as HTTP 503."""

    def __init__(
        self,
        message: str,
        *,
        raw_text: str | None = None,
        attempt_count: int = 1,
        retry_used: bool = False,
        first_contract_error: str | None = None,
    ):
        super().__init__(message)
        self.raw_text = raw_text
        self.attempt_count = attempt_count
        self.retry_used = retry_used
        self.first_contract_error = first_contract_error


def judgment_enabled() -> bool:
    return os.getenv("JUDGMENT_ENABLED", "false").strip().lower() in {
        "1", "true", "yes", "on"
    }


def _call_model(
    *,
    endpoint: str,
    request_body: dict[str, Any],
    timeout: float,
    transport: Transport,
) -> dict[str, Any]:
    try:
        response = transport(
            endpoint=endpoint,
            request_body=request_body,
            timeout=timeout,
            api_key=None,
        )
    except Exception as exc:
        raise JudgmentServiceError(f"Judgment model call failed: {exc}") from exc
    if not isinstance(response, dict):
        raise JudgmentServiceError("Judgment model call returned an invalid result")
    if not response.get("transport_success"):
        raise JudgmentServiceError(response.get("error") or "Judgment model call failed")
    return response


def _retry_request(request_body: dict[str, Any]) -> dict[str, Any]:
    retry = {
        **request_body,
        "messages": [dict(message) for message in request_body["messages"]],
    }
    retry["messages"][0]["content"] += RETRY_INSTRUCTION
    return retry


def run_judgment(
    text: str,
    *,
    context: str | None,
    learner_level: str,
    endpoint: str | None = None,
    model_name: str | None = None,
    timeout: float | None = None,
    transport: Transport = call_endpoint,
) -> dict[str, Any]:
    """Call D once and retry only a non-correction text-preservation violation."""
    if not isinstance(text, str) or not text.strip():
        raise ValueError("text must be nonblank")
    if context is not None and not isinstance(context, str):
        raise ValueError("context must be null or a string")
    if learner_level not in {"N5", "N4"}:
        raise ValueError("learner_level must be N5 or N4")

    endpoint = endpoint or os.getenv("JUDGMENT_ENDPOINT", DEFAULT_ENDPOINT)
    model_name = model_name or os.getenv("JUDGMENT_MODEL", DEFAULT_MODEL)
    if timeout is None:
        try:
            timeout = float(os.getenv("JUDGMENT_TIMEOUT_SECONDS", "120"))
        except ValueError as exc:
            raise JudgmentServiceError("Invalid judgment timeout configuration") from exc
    if timeout <= 0:
        raise JudgmentServiceError("Invalid judgment timeout configuration")

    try:
        request_body = build_request(
            {"text": text, "context": context, "learner_level": learner_level},
            model_name,
            temperature=0.0,
            top_p=1.0,
            max_tokens=512,
            prompt_version=PROMPT_VERSION_V2,
        )
    except Exception as exc:
        raise JudgmentServiceError(f"Judgment model call failed: {exc}") from exc

    response = _call_model(
        endpoint=endpoint,
        request_body=request_body,
        timeout=timeout,
        transport=transport,
    )
    parsed, contract_error = parse_model_output(
        response.get("raw_text", ""), text, PROMPT_VERSION_V2
    )
    attempt_count = 1
    retry_used = False
    first_contract_error = None
    latency_ms = response.get("latency_ms")

    if parsed is None and contract_error == PRESERVATION_CONTRACT_ERROR:
        retry_used = True
        attempt_count = 2
        first_contract_error = contract_error
        try:
            retry_response = _call_model(
                endpoint=endpoint,
                request_body=_retry_request(request_body),
                timeout=timeout,
                transport=transport,
            )
        except JudgmentServiceError as exc:
            exc.attempt_count = 2
            exc.retry_used = True
            exc.first_contract_error = first_contract_error
            raise
        retry_latency = retry_response.get("latency_ms")
        if isinstance(latency_ms, (int, float)) and isinstance(
            retry_latency, (int, float)
        ):
            latency_ms = float(latency_ms) + float(retry_latency)
        else:
            latency_ms = None
        parsed, contract_error = parse_model_output(
            retry_response.get("raw_text", ""), text, PROMPT_VERSION_V2
        )
        response = retry_response

    if parsed is None:
        raise JudgmentServiceError(
            f"Judgment model contract violation: {contract_error}",
            raw_text=response.get("raw_text", ""),
            attempt_count=attempt_count,
            retry_used=retry_used,
            first_contract_error=first_contract_error,
        )

    return {
        "decision": parsed["decision"],
        "corrected_text": parsed["corrected_text"],
        "edits": parsed["edits"],
        "error_types": parsed["error_types"],
        "reason_ko": parsed["reason_ko"],
        "classification_review_required": parsed["classification_review_required"],
        "strategy": STRATEGY,
        "model_name": model_name,
        "adapter_name": os.getenv("JUDGMENT_ADAPTER", DEFAULT_ADAPTER),
        "selection_reason": SELECTION_REASON,
        "contract_version": CONTRACT_VERSION,
        "latency_ms": latency_ms,
        "context": context,
        "learner_level": learner_level,
        "attempt_count": attempt_count,
        "retry_used": retry_used,
        "first_contract_error": first_contract_error,
    }
