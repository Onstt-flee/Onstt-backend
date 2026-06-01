# analyzer/llm_parser.py

import json
import re
from typing import Any, Dict, List, Optional


REQUIRED_FIELDS = {
    "is_correct",
    "corrected_text",
    "error_types",
    "feedback_ko",
    "feedback_ja",
    "confidence",
}


def _strip_code_block(raw_text: str) -> str:
    """
    ```json
    {...}
    ```
    형태의 코드블록을 제거한다.
    """
    text = raw_text.strip()

    # ```json ... ``` 또는 ``` ... ``` 제거
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?", "", text.strip(), flags=re.IGNORECASE).strip()
        text = re.sub(r"```$", "", text.strip()).strip()

    return text


def _extract_json_object(raw_text: str) -> Optional[str]:
    """
    LLM 응답에서 첫 번째 JSON 객체 후보를 추출한다.

    처리 예:
    - 순수 JSON: {"is_correct": false, ...}
    - 코드블록 포함: ```json {...} ```
    - 앞뒤 설명 포함: "결과는 다음과 같습니다. {...}"
    """
    if not raw_text:
        return None

    text = _strip_code_block(raw_text)

    # 1차: 전체가 JSON인지 확인
    if text.startswith("{") and text.endswith("}"):
        return text

    # 2차: 앞뒤 설명문이 섞인 경우 첫 { ~ 마지막 } 추출
    start = text.find("{")
    end = text.rfind("}")

    if start == -1 or end == -1 or start >= end:
        return None

    return text[start:end + 1]


def _safe_bool(value: Any) -> Optional[bool]:
    """
    is_correct 값을 bool 또는 None으로 보정한다.
    """
    if isinstance(value, bool):
        return value

    if value is None:
        return None

    if isinstance(value, str):
        lowered = value.strip().lower()

        if lowered in ["true", "yes", "correct", "정답", "맞음"]:
            return True

        if lowered in ["false", "no", "incorrect", "오답", "틀림"]:
            return False

    return None


def _safe_float(value: Any, default: float = 0.0) -> float:
    """
    confidence 값을 0.0 ~ 1.0 범위로 보정한다.
    """
    try:
        confidence = float(value)
    except (TypeError, ValueError):
        return default

    if confidence < 0.0:
        return 0.0

    if confidence > 1.0:
        return 1.0

    return confidence


def _safe_error_types(value: Any) -> List[str]:
    """
    error_types를 항상 list[str] 형태로 보정한다.
    """
    if value is None:
        return []

    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]

    if isinstance(value, str):
        value = value.strip()

        if not value:
            return []

        # 문자열인데 JSON 배열처럼 온 경우
        # 예: '["tense_error", "particle_omission"]'
        if value.startswith("[") and value.endswith("]"):
            try:
                parsed = json.loads(value)
                if isinstance(parsed, list):
                    return [str(item).strip() for item in parsed if str(item).strip()]
            except json.JSONDecodeError:
                pass

        # 콤마 구분 문자열 처리
        # 예: "tense_error, particle_omission"
        if "," in value:
            return [item.strip() for item in value.split(",") if item.strip()]

        return [value]

    return [str(value).strip()] if str(value).strip() else []


def _safe_text(value: Any, default: str = "") -> str:
    """
    None이나 비문자열 값을 안전한 문자열로 변환한다.
    """
    if value is None:
        return default

    return str(value)


def _build_fallback(
    original_text: str,
    raw_text: str,
    error_message: str,
    model_name: Optional[str] = None,
    adapter_name: Optional[str] = None,
) -> Dict[str, Any]:
    """
    LLM 응답 파싱 실패 시 pipeline이 죽지 않도록 fallback 결과를 만든다.
    """
    return {
        "is_correct": None,
        "corrected_text": original_text,
        "error_types": [],
        "feedback_ko": f"LLM 응답 파싱에 실패했습니다. 원문을 그대로 반환합니다. 원인: {error_message}",
        "feedback_ja": "",
        "confidence": 0.0,
        "model_name": model_name,
        "adapter_name": adapter_name,
        "parse_success": False,
        "parse_error": error_message,
        "raw_text": raw_text,
    }


def normalize_llm_result(
    parsed: Dict[str, Any],
    original_text: str,
    raw_text: str,
    model_name: Optional[str] = None,
    adapter_name: Optional[str] = None,
) -> Dict[str, Any]:
    """
    JSON 파싱은 성공했지만 필드 타입이 불안정할 수 있으므로 최종 결과를 보정한다.
    """
    is_correct = _safe_bool(parsed.get("is_correct"))

    corrected_text = _safe_text(
        parsed.get("corrected_text"),
        default=original_text,
    )

    # corrected_text가 빈 문자열이면 원문 유지
    if not corrected_text.strip():
        corrected_text = original_text

    error_types = _safe_error_types(parsed.get("error_types"))

    feedback_ko = _safe_text(parsed.get("feedback_ko"), default="")
    feedback_ja = _safe_text(parsed.get("feedback_ja"), default="")
    confidence = _safe_float(parsed.get("confidence"), default=0.0)

    return {
        "is_correct": is_correct,
        "corrected_text": corrected_text,
        "error_types": error_types,
        "feedback_ko": feedback_ko,
        "feedback_ja": feedback_ja,
        "confidence": confidence,
        "model_name": model_name,
        "adapter_name": adapter_name,
        "parse_success": True,
        "parse_error": None,
        "raw_text": raw_text,
    }


def parse_llm_response(
    raw_text: str,
    original_text: str,
    model_name: Optional[str] = None,
    adapter_name: Optional[str] = None,
) -> Dict[str, Any]:
    """
    LLM raw_text를 분석 결과 dict로 변환한다.

    이 함수는 다음 상황을 처리한다.
    1. 정상 JSON 문자열
    2. ```json 코드블록 포함 응답
    3. 앞뒤 설명문이 섞인 응답
    4. JSON 파싱 실패
    5. 필수 필드 누락 또는 타입 불안정
    """
    if raw_text is None:
        return _build_fallback(
            original_text=original_text,
            raw_text="",
            error_message="raw_text is None",
            model_name=model_name,
            adapter_name=adapter_name,
        )

    json_text = _extract_json_object(raw_text)

    if json_text is None:
        return _build_fallback(
            original_text=original_text,
            raw_text=raw_text,
            error_message="No JSON object found in LLM response",
            model_name=model_name,
            adapter_name=adapter_name,
        )

    try:
        parsed = json.loads(json_text)
    except json.JSONDecodeError as exc:
        return _build_fallback(
            original_text=original_text,
            raw_text=raw_text,
            error_message=f"JSONDecodeError: {str(exc)}",
            model_name=model_name,
            adapter_name=adapter_name,
        )

    if not isinstance(parsed, dict):
        return _build_fallback(
            original_text=original_text,
            raw_text=raw_text,
            error_message="Parsed JSON is not an object",
            model_name=model_name,
            adapter_name=adapter_name,
        )

    return normalize_llm_result(
        parsed=parsed,
        original_text=original_text,
        raw_text=raw_text,
        model_name=model_name,
        adapter_name=adapter_name,
    )
