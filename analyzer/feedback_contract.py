"""Strict, source-blind contract for the GPU feedback verifier."""

from __future__ import annotations

from difflib import SequenceMatcher
import json
from typing import Any

from evaluation.judgment.dataset import ERROR_TYPES


CONTRACT_VERSION = "feedback-v0.1"
VERDICTS = frozenset({"agree", "disagree", "unreviewable"})
ISSUE_CODES = frozenset({
    "false_positive",
    "false_negative",
    "wrong_decision",
    "wrong_correction",
    "nonminimal_correction",
    "meaning_changed",
    "wrong_error_type",
    "reason_mismatch",
    "context_misread",
    "should_abstain",
    "unnecessary_abstention",
})

SYSTEM_PROMPT = """당신은 일본어 문법 판단모델의 결과를 독립적으로 검수하는 시스템입니다.
학습자에게 직접 답하지 말고 주어진 원문, 문맥, 학습자 수준과 판단 결과만 검토하세요.
판단 결과의 실행 위치, 모델 이름, 양자화 형식은 알 수 없으며 추측하지 마세요.

반드시 JSON 객체 하나만 출력하고 다음 네 필드만 사용하세요.
{
  "verdict": "agree | disagree | unreviewable",
  "issue_codes": ["허용 문제 유형"],
  "recommended_judgment": null,
  "review_reason_ko": "짧은 한국어 검수 근거"
}

disagree일 때 recommended_judgment는 다음 네 필드를 모두 포함해야 합니다.
{
  "decision": "acceptable | needs_correction | insufficient_evidence",
  "corrected_text": "원문 또는 의미·문체를 보존한 최소 교정문",
  "error_types": ["허용 문법 오류 유형"],
  "reason_ko": "권장 판단 근거"
}

허용 문제 유형은 false_positive, false_negative, wrong_decision,
wrong_correction, nonminimal_correction, meaning_changed, wrong_error_type,
reason_mismatch, context_misread, should_abstain, unnecessary_abstention입니다.
허용 문법 오류 유형은 particle_misuse, verb_conjugation,
adjective_conjugation, copula_conjugation, modifier_connection,
tense_mismatch입니다.

규칙:
1. 원 판단과 교정·근거가 모두 타당하면 agree, issue_codes=[], recommended_judgment=null입니다.
2. 오류가 있으면 disagree와 하나 이상의 issue_codes, 완전한 권장 판단을 출력하세요.
3. 제공된 정보만으로 검수할 수 없으면 unreviewable이며 issue_codes=[]와 null을 출력하세요.
4. acceptable/insufficient_evidence 권장은 원문을 그대로 보존하고 error_types를 비우세요.
5. needs_correction 권장은 실제로 달라지는 최소 교정과 하나 이상의 오류 유형이 필요합니다.
6. 수정 위치는 출력하지 마세요. 백엔드가 결정론적으로 계산합니다.
7. 숫자 confidence, Markdown, 코드 펜스, 추가 필드, JSON 밖 설명을 출력하지 마세요."""


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _strict_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"Duplicate JSON key: {key}")
        result[key] = value
    return result


def _reject_constant(value: str) -> None:
    raise ValueError(f"Non-standard JSON constant: {value}")


def validate_input(value: dict[str, Any]) -> None:
    if set(value) != {"text", "context", "learner_level", "judgment"}:
        raise ValueError("feedback input contains unsupported fields")
    if not isinstance(value["text"], str) or not value["text"].strip():
        raise ValueError("text must be nonblank")
    if value["context"] is not None and not isinstance(value["context"], str):
        raise ValueError("context must be null or a string")
    if value["learner_level"] not in {"N5", "N4"}:
        raise ValueError("learner_level must be N5 or N4")
    judgment = value["judgment"]
    if not isinstance(judgment, dict) or set(judgment) != {
        "decision", "corrected_text", "error_types", "reason_ko"
    }:
        raise ValueError("judgment must contain the four public judgment fields")
    _normalize_judgment(judgment, value["text"])


def build_request(model_input: dict[str, Any], model: str) -> dict[str, Any]:
    validate_input(model_input)
    if not isinstance(model, str) or not model.strip():
        raise ValueError("model must be nonblank")
    return {
        "model": model,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": canonical_json(model_input)},
        ],
        "temperature": 0.0,
        "top_p": 1.0,
        "max_tokens": 512,
        "stream": False,
    }


def _normalize_judgment(value: dict[str, Any], original_text: str) -> dict[str, Any]:
    if set(value) != {"decision", "corrected_text", "error_types", "reason_ko"}:
        raise ValueError("recommended_judgment must contain exactly four fields")
    decision = value["decision"]
    corrected = value["corrected_text"]
    error_types = value["error_types"]
    reason = value["reason_ko"]
    if decision not in {"acceptable", "needs_correction", "insufficient_evidence"}:
        raise ValueError("recommended decision is invalid")
    if not isinstance(corrected, str):
        raise ValueError("recommended corrected_text must be a string")
    if not isinstance(reason, str) or not reason.strip():
        raise ValueError("recommended reason_ko must be nonblank")
    if (
        not isinstance(error_types, list)
        or any(item not in ERROR_TYPES for item in error_types)
        or len(error_types) != len(set(error_types))
    ):
        raise ValueError("recommended error_types must be unique allowed values")
    if decision != "needs_correction":
        if corrected != original_text or error_types:
            raise ValueError("recommended non-correction must preserve input text")
        return {**value, "edits": [], "classification_review_required": False}
    if corrected == original_text or not corrected.strip() or not error_types:
        raise ValueError("recommended correction must change text and classify the error")
    opcodes = [
        item for item in SequenceMatcher(
            None, original_text, corrected, autojunk=False
        ).get_opcodes() if item[0] != "equal"
    ]
    if len(error_types) == len(opcodes):
        assigned = list(error_types)
        review_required = False
    elif len(error_types) == 1:
        assigned = error_types * len(opcodes)
        review_required = False
    else:
        assigned = [
            error_types[index] if index < len(error_types) else None
            for index in range(len(opcodes))
        ]
        review_required = True
    edits = [
        {
            "start": start,
            "end": end,
            "source": original_text[start:end],
            "replacement": corrected[target_start:target_end],
            "error_type": error_type,
        }
        for (_, start, end, target_start, target_end), error_type
        in zip(opcodes, assigned)
    ]
    return {
        **value,
        "edits": edits,
        "classification_review_required": review_required,
    }


def parse_output(raw_text: str, original_text: str) -> tuple[dict[str, Any] | None, str | None]:
    try:
        if not isinstance(raw_text, str) or not raw_text.strip():
            raise ValueError("feedback content is empty")
        value = json.loads(
            raw_text,
            object_pairs_hook=_strict_object,
            parse_constant=_reject_constant,
        )
        if not isinstance(value, dict) or set(value) != {
            "verdict", "issue_codes", "recommended_judgment", "review_reason_ko"
        }:
            raise ValueError("feedback output must contain exactly four fields")
        verdict = value["verdict"]
        issue_codes = value["issue_codes"]
        recommended = value["recommended_judgment"]
        reason = value["review_reason_ko"]
        if verdict not in VERDICTS:
            raise ValueError("feedback verdict is invalid")
        if (
            not isinstance(issue_codes, list)
            or any(item not in ISSUE_CODES for item in issue_codes)
            or len(issue_codes) != len(set(issue_codes))
        ):
            raise ValueError("issue_codes must be unique allowed values")
        if not isinstance(reason, str) or not reason.strip():
            raise ValueError("review_reason_ko must be nonblank")
        if verdict in {"agree", "unreviewable"}:
            if issue_codes or recommended is not None:
                raise ValueError(f"{verdict} must not contain issues or recommendation")
            normalized = None
        else:
            if not issue_codes or not isinstance(recommended, dict):
                raise ValueError("disagree requires issues and recommended_judgment")
            normalized = _normalize_judgment(recommended, original_text)
        return {**value, "recommended_judgment": normalized}, None
    except (json.JSONDecodeError, TypeError, ValueError) as exc:
        return None, str(exc)
