import re
from typing import Dict, Any


HIRAGANA_RE = re.compile(r"[\u3040-\u309F]")
KATAKANA_RE = re.compile(r"[\u30A0-\u30FF]")
KANJI_RE = re.compile(r"[\u4E00-\u9FFF]")
KOREAN_RE = re.compile(r"[\uAC00-\uD7A3]")
ENGLISH_RE = re.compile(r"[A-Za-z]")


def normalize_text(text: str) -> str:
    """
    STT 원문에서 앞뒤 공백과 과도한 내부 공백을 정리한다.
    """
    if text is None:
        return ""

    normalized = text.strip()
    normalized = re.sub(r"\s+", " ", normalized)
    return normalized


def contains_japanese(text: str) -> bool:
    """
    히라가나, 가타카나, 한자 중 하나라도 포함하면 일본어 가능성이 있다고 본다.
    """
    return bool(
        HIRAGANA_RE.search(text)
        or KATAKANA_RE.search(text)
        or KANJI_RE.search(text)
    )


def contains_korean(text: str) -> bool:
    return bool(KOREAN_RE.search(text))


def contains_english(text: str) -> bool:
    return bool(ENGLISH_RE.search(text))


def validate_input(text: str) -> Dict[str, Any]:
    """
    Layer 1 입력 검증 함수.

    역할:
    - 빈 문자열 차단
    - 일본어 문자가 없는 입력 차단
    - 한국어/영어만 있는 입력 차단
    - 너무 짧은 STT 실패성 입력 차단
    - 정규화된 텍스트 반환
    """
    normalized_text = normalize_text(text)

    if not normalized_text:
        return {
            "is_valid": False,
            "reason": "empty_input",
            "normalized_text": normalized_text,
        }

    has_japanese = contains_japanese(normalized_text)
    has_korean = contains_korean(normalized_text)
    has_english = contains_english(normalized_text)

    if not has_japanese:
        if has_korean or has_english:
            return {
                "is_valid": False,
                "reason": "non_japanese_or_stt_language_mismatch",
                "normalized_text": normalized_text,
            }

        return {
            "is_valid": False,
            "reason": "no_japanese_characters",
            "normalized_text": normalized_text,
        }

    # 일본어 문자가 있더라도 너무 짧으면 STT 실패 가능성으로 본다.
    # 예: "あ", "ん", "え" 같은 단일 음절
    if len(normalized_text) <= 1:
        return {
            "is_valid": False,
            "reason": "too_short_for_analysis",
            "normalized_text": normalized_text,
        }

    return {
        "is_valid": True,
        "reason": "valid_japanese_input",
        "normalized_text": normalized_text,
    }
