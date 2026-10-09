"""Deterministic boundary routing for the judgment pipeline.

This module is intentionally independent from the operating API. It can bypass
the model only when the text itself provides enough evidence that no Japanese
grammar judgment is possible. STT orthography is emitted as an advisory and
never attributed to either the learner or the recognizer.
"""

from __future__ import annotations

from copy import deepcopy
import re
import unicodedata
from typing import Any


POLICY_VERSION = "judgment-boundary-v0.1"
STT_CONTEXT_MARKERS = (
    "stt", "전사", "원음", "음성 인식", "음성인식", "文字起こし", "音声認識",
)
NOISE_ONLY_RE = re.compile(
    r"^[\s\[\]［］【】()（）]*(?:雑音|ノイズ|聞き取れない|聴取不能|"
    r"noise|inaudible)[\s\[\]［］【】()（）.!！?？…・-]*$",
    re.IGNORECASE,
)
PERSONAL_TOPIC_RE = re.compile(r"わたしわ")
OBJECT_O_RE = re.compile(
    r"(?P<noun>[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff々〆ヵヶ]{1,8})"
    r"お(?P<stem>読み|書き|買い|食べ|見|聞き|使い|持ち|取り|飲み)ます"
)


def _is_japanese_evidence(char: str) -> bool:
    code = ord(char)
    return (
        0x3040 <= code <= 0x30FF
        or 0xFF66 <= code <= 0xFF9D
        or 0x3400 <= code <= 0x4DBF
        or 0x4E00 <= code <= 0x9FFF
        or 0xF900 <= code <= 0xFAFF
    )


def _is_hangul(char: str) -> bool:
    code = ord(char)
    return (
        0x1100 <= code <= 0x11FF
        or 0x3130 <= code <= 0x318F
        or 0xAC00 <= code <= 0xD7AF
    )


def _is_latin(char: str) -> bool:
    return "LATIN" in unicodedata.name(char, "")


def _punctuation_or_symbol_only(text: str) -> bool:
    visible = [char for char in text if not char.isspace()]
    return bool(visible) and all(
        unicodedata.category(char)[0] in {"P", "S"} for char in visible
    )


def _insufficient(text: str, reason: str, boundary_type: str) -> dict[str, Any]:
    return {
        "route": "deterministic",
        "boundary_type": boundary_type,
        "model_call_required": False,
        "judgment": {
            "decision": "insufficient_evidence",
            "corrected_text": text,
            "error_types": [],
            "edits": [],
            "reason_ko": reason,
            "classification_review_required": False,
        },
        "advisories": [],
        "policy_version": POLICY_VERSION,
    }


def detect_orthography_advisories(
    text: str,
    context: str | None,
) -> list[dict[str, Any]]:
    """Return conservative STT spelling candidates without changing grammar."""
    if not isinstance(text, str):
        raise TypeError("text must be a string")
    if context is not None and not isinstance(context, str):
        raise TypeError("context must be null or a string")
    normalized_context = (context or "").casefold()
    if not any(marker in normalized_context for marker in STT_CONTEXT_MARKERS):
        return []

    candidates: list[dict[str, Any]] = []
    for match in PERSONAL_TOPIC_RE.finditer(text):
        start = match.start() + len("わたし")
        candidate = text[:start] + "は" + text[start + 1 :]
        candidates.append({
            "kind": "orthography_candidate",
            "start": start,
            "end": start + 1,
            "source": "わ",
            "replacement": "は",
            "candidate_text": candidate,
            "attribution": "unknown",
            "action": "advisory_only",
        })
    for match in OBJECT_O_RE.finditer(text):
        start = match.start("stem") - 1
        candidate = text[:start] + "を" + text[start + 1 :]
        candidates.append({
            "kind": "orthography_candidate",
            "start": start,
            "end": start + 1,
            "source": "お",
            "replacement": "を",
            "candidate_text": candidate,
            "attribution": "unknown",
            "action": "advisory_only",
        })
    return sorted(candidates, key=lambda value: (value["start"], value["end"]))


def assess_boundary(text: str, context: str | None) -> dict[str, Any]:
    """Choose a deterministic bypass only for high-precision boundary cases."""
    if not isinstance(text, str):
        raise TypeError("text must be a string")
    if context is not None and not isinstance(context, str):
        raise TypeError("context must be null or a string")
    if not text.strip():
        return _insufficient(text, "판단할 발화 내용이 없습니다.", "empty_input")
    stripped = text.strip()
    if NOISE_ONLY_RE.fullmatch(stripped) or _punctuation_or_symbol_only(stripped):
        return _insufficient(
            text,
            "식별 가능한 발화 내용이 없어 문법을 판단할 수 없습니다.",
            "no_proposition",
        )

    has_japanese = any(_is_japanese_evidence(char) for char in text)
    has_foreign_letters = any(_is_hangul(char) or _is_latin(char) for char in text)
    if has_foreign_letters and not has_japanese:
        return _insufficient(
            text,
            "일본어 문법 판단 범위 밖의 입력이므로 번역하거나 교정하지 않습니다.",
            "out_of_scope_language",
        )

    return {
        "route": "model",
        "boundary_type": None,
        "model_call_required": True,
        "judgment": None,
        "advisories": detect_orthography_advisories(text, context),
        "policy_version": POLICY_VERSION,
    }


def _is_exact_orthography_correction(
    judgment: dict[str, Any],
    advisories: list[dict[str, Any]],
) -> bool:
    return (
        judgment.get("decision") == "needs_correction"
        and judgment.get("error_types") == ["particle_misuse"]
        and any(
            judgment.get("corrected_text") == advisory["candidate_text"]
            for advisory in advisories
        )
    )


def apply_boundary_policy(
    text: str,
    context: str | None,
    model_judgment: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Apply pre-routing and isolate exact STT spelling changes from grammar."""
    assessment = assess_boundary(text, context)
    if assessment["route"] == "deterministic":
        return {
            **assessment,
            "model_output_overridden": model_judgment is not None,
        }
    if model_judgment is None:
        return {**assessment, "model_output_overridden": False}

    judgment = deepcopy(model_judgment)
    if _is_exact_orthography_correction(judgment, assessment["advisories"]):
        judgment = {
            "decision": "acceptable",
            "corrected_text": text,
            "error_types": [],
            "edits": [],
            "reason_ko": (
                "STT 표기 후보는 문법 교정과 분리하며 원음 없이 "
                "학습자와 음성 인식 중 오류 주체를 단정하지 않습니다."
            ),
            "classification_review_required": False,
        }
        overridden = True
    else:
        overridden = False
    return {
        **assessment,
        "judgment": judgment,
        "model_output_overridden": overridden,
    }
