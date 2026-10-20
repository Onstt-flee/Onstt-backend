"""Strict two-stage contract for feedback verdict and recommendation generation.

Stage 1 decides whether the submitted judgment is acceptable.  Stage 2 is
legal only after a valid ``disagree`` and produces the replacement judgment.
This module performs no transport, persistence, or automatic activation.
"""

from __future__ import annotations

import json
from typing import Any

from analyzer.feedback_contract import (
    ISSUE_CODES,
    ISSUE_DECISION_RULES,
    VERDICTS,
    _normalize_judgment,
    _reject_constant,
    _strict_object,
    canonical_json,
    validate_input,
)


CONTRACT_VERSION = "feedback-two-stage-v0.1"

STAGE1_SYSTEM_PROMPT = """당신은 일본어 문법 판단 결과의 독립 검수기입니다.
원문, 문맥, 학습자 수준과 제출된 판단만 검토하고 실행 위치나 모델 출처는 추측하지 마세요.

JSON 객체 하나만 출력하세요.
{
  "verdict": "agree | disagree | unreviewable",
  "issue_codes": ["허용 문제 유형"],
  "review_reason_ko": "짧은 한국어 검수 근거"
}

agree는 판단·교정·근거가 모두 타당할 때만 사용하고 issue_codes는 비웁니다.
disagree는 한 개 이상의 issue_codes를 포함해야 합니다.
unreviewable은 제공 정보로 검수할 수 없을 때만 사용하고 issue_codes는 비웁니다.
권장 판단, 교정문, confidence, 수정 위치, Markdown, 추가 필드는 출력하지 마세요."""

STAGE2_SYSTEM_PROMPT = """당신은 1단계 검수에서 불일치가 확정된 일본어 판단의 권장안을 만듭니다.
원문의 의미·문체를 보존하고 필요한 부분만 최소 교정하세요.

JSON 객체 하나만 출력하고 다음 네 필드만 사용하세요.
{
  "decision": "acceptable | needs_correction | insufficient_evidence",
  "corrected_text": "원문 또는 최소 교정문",
  "error_types": ["허용 문법 오류 유형"],
  "reason_ko": "권장 판단 근거"
}

acceptable과 insufficient_evidence는 원문을 그대로 보존하고 error_types를 비웁니다.
needs_correction은 원문과 다른 최소 교정문과 오류 유형을 포함합니다.
confidence, 수정 위치, Markdown, 추가 필드는 출력하지 마세요."""


def _decode_object(raw_text: str) -> dict[str, Any]:
    if not isinstance(raw_text, str) or not raw_text.strip():
        raise ValueError("feedback content is empty")
    value = json.loads(
        raw_text,
        object_pairs_hook=_strict_object,
        parse_constant=_reject_constant,
    )
    if not isinstance(value, dict):
        raise ValueError("feedback output must be a JSON object")
    return value


def build_stage1_request(model_input: dict[str, Any], model: str) -> dict[str, Any]:
    validate_input(model_input)
    if not isinstance(model, str) or not model.strip():
        raise ValueError("model must be nonblank")
    return {
        "model": model,
        "messages": [
            {"role": "system", "content": STAGE1_SYSTEM_PROMPT},
            {"role": "user", "content": canonical_json(model_input)},
        ],
        "temperature": 0.0,
        "top_p": 1.0,
        "max_tokens": 192,
        "stream": False,
    }


def parse_stage1_output(raw_text: str) -> tuple[dict[str, Any] | None, str | None]:
    try:
        value = _decode_object(raw_text)
        if set(value) != {"verdict", "issue_codes", "review_reason_ko"}:
            raise ValueError("stage-1 output must contain exactly three fields")
        verdict = value["verdict"]
        issues = value["issue_codes"]
        reason = value["review_reason_ko"]
        if verdict not in VERDICTS:
            raise ValueError("stage-1 verdict is invalid")
        if (
            not isinstance(issues, list)
            or any(issue not in ISSUE_CODES for issue in issues)
            or len(issues) != len(set(issues))
        ):
            raise ValueError("stage-1 issue_codes must be unique allowed values")
        if not isinstance(reason, str) or not reason.strip():
            raise ValueError("stage-1 review_reason_ko must be nonblank")
        if verdict == "disagree" and not issues:
            raise ValueError("stage-1 disagree requires issue_codes")
        if verdict != "disagree" and issues:
            raise ValueError("stage-1 non-disagree must not contain issue_codes")
        return value, None
    except (json.JSONDecodeError, TypeError, ValueError) as exc:
        return None, str(exc)


def should_call_stage2(stage1: dict[str, Any]) -> bool:
    parsed, error = parse_stage1_output(canonical_json(stage1))
    if parsed is None:
        raise ValueError(f"invalid stage-1 result: {error}")
    return parsed["verdict"] == "disagree"


def build_stage2_request(
    model_input: dict[str, Any],
    stage1: dict[str, Any],
    model: str,
) -> dict[str, Any]:
    validate_input(model_input)
    parsed, error = parse_stage1_output(canonical_json(stage1))
    if parsed is None:
        raise ValueError(f"invalid stage-1 result: {error}")
    if parsed["verdict"] != "disagree":
        raise ValueError("stage 2 is allowed only after disagree")
    if not isinstance(model, str) or not model.strip():
        raise ValueError("model must be nonblank")
    visible = {"input": model_input, "stage1_audit": parsed}
    return {
        "model": model,
        "messages": [
            {"role": "system", "content": STAGE2_SYSTEM_PROMPT},
            {"role": "user", "content": canonical_json(visible)},
        ],
        "temperature": 0.0,
        "top_p": 1.0,
        "max_tokens": 384,
        "stream": False,
    }


def parse_stage2_output(
    raw_text: str,
    original_text: str,
    issue_codes: list[str],
) -> tuple[dict[str, Any] | None, str | None]:
    try:
        if not issue_codes or any(issue not in ISSUE_CODES for issue in issue_codes):
            raise ValueError("valid nonempty stage-1 issue_codes are required")
        value = _decode_object(raw_text)
        normalized = _normalize_judgment(value, original_text)
        decision = normalized["decision"]
        for issue_code, allowed_decisions in ISSUE_DECISION_RULES.items():
            if issue_code in issue_codes and decision not in allowed_decisions:
                allowed = ", ".join(sorted(allowed_decisions))
                raise ValueError(f"{issue_code} requires recommended decision in: {allowed}")
        return normalized, None
    except (json.JSONDecodeError, TypeError, ValueError) as exc:
        return None, str(exc)


def combine_outputs(
    stage1: dict[str, Any],
    stage2: dict[str, Any] | None,
) -> dict[str, Any]:
    parsed, error = parse_stage1_output(canonical_json(stage1))
    if parsed is None:
        raise ValueError(f"invalid stage-1 result: {error}")
    if parsed["verdict"] == "disagree":
        if stage2 is None:
            raise ValueError("disagree requires a valid stage-2 recommendation")
        recommendation = stage2
    else:
        if stage2 is not None:
            raise ValueError("non-disagree must not include a stage-2 recommendation")
        recommendation = None
    return {
        "verdict": parsed["verdict"],
        "issue_codes": parsed["issue_codes"],
        "recommended_judgment": recommendation,
        "review_reason_ko": parsed["review_reason_ko"],
    }
