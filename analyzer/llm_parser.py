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


def _normalize_for_compare(text: str) -> str:
    """
    원문과 교정문 비교용 정규화.
    공백과 일부 구두점을 제거해서 의미 있는 차이만 비교한다.
    """
    if text is None:
        return ""

    return (
        str(text)
        .replace(" ", "")
        .replace("　", "")
        .replace("\n", "")
        .replace("\t", "")
    )


def _contains_any(text: str, patterns: List[str]) -> bool:
    return any(pattern in text for pattern in patterns)


def _postprocess_error_types(
    original_text: str,
    corrected_text: str,
    error_types: List[str],
) -> List[str]:
    """
    LLM이 반환한 error_types를 원문 -> 교정문 변화 기준으로 보정한다.
    목적:
    - 교정 내용과 error_types의 모순 제거
    - 명확한 단어 선택 오류/조사 오류/시제 오류 보정
    """
    allowed_error_types = {
        "particle_omission",
        "particle_misuse",
        "verb_conjugation_error",
        "tense_error",
        "word_choice_error",
        "unnatural_expression",
        "overcorrection_risk",
        "non_japanese_input",
        "fragment",
    }

    cleaned = []
    for error_type in error_types:
        if error_type in allowed_error_types and error_type not in cleaned:
            cleaned.append(error_type)

    original = _normalize_for_compare(original_text)
    corrected = _normalize_for_compare(corrected_text)

    # 교정문이 원문과 같으면 오류 유형을 비운다.
    if original == corrected:
        return []

    # 1. 단어 선택 오류: 물 + 먹다 -> 마시다
    water_eat_patterns = [
        "水を食べる",
        "水を食べます",
        "水を食べました",
        "水食べる",
        "水食べます",
        "水食べました",
    ]
    water_drink_patterns = [
        "水を飲む",
        "水を飲みます",
        "水を飲みました",
        "水飲む",
        "水飲みます",
        "水飲みました",
    ]

    if _contains_any(original, water_eat_patterns) and _contains_any(corrected, water_drink_patterns):
        cleaned = [e for e in cleaned if e not in ["particle_omission", "particle_misuse"]]
        if "word_choice_error" not in cleaned:
            cleaned.append("word_choice_error")

    # 2. 단어 선택 오류: 라멘 + 마시다 -> 먹다
    ramen_drink_patterns = [
        "ラーメンを飲む",
        "ラーメンを飲みます",
        "ラーメンを飲みました",
        "ラーメン飲む",
        "ラーメン飲みます",
        "ラーメン飲みました",
    ]
    ramen_eat_patterns = [
        "ラーメンを食べる",
        "ラーメンを食べます",
        "ラーメンを食べました",
        "ラーメン食べる",
        "ラーメン食べます",
        "ラーメン食べました",
    ]

    if _contains_any(original, ramen_drink_patterns) and _contains_any(corrected, ramen_eat_patterns):
        cleaned = [e for e in cleaned if e not in ["particle_omission", "particle_misuse"]]
        if "word_choice_error" not in cleaned:
            cleaned.append("word_choice_error")

    # 3. 조사 오용: 水が飲む/飲みます/飲みました -> 水を飲む/飲みます/飲みました
    water_ga_patterns = [
        "水が飲む",
        "水が飲みます",
        "水が飲みました",
    ]
    water_wo_patterns = [
        "水を飲む",
        "水を飲みます",
        "水を飲みました",
    ]

    if _contains_any(original, water_ga_patterns) and _contains_any(corrected, water_wo_patterns):
        if "particle_misuse" not in cleaned:
            cleaned.append("particle_misuse")

    # 4. 조사 오용: 学校を行く/行きます/行きました -> 学校に行く/行きます/行きました
    school_wo_patterns = [
        "学校を行く",
        "学校を行きます",
        "学校を行きました",
    ]
    school_ni_patterns = [
        "学校に行く",
        "学校に行きます",
        "学校に行きました",
    ]

    if _contains_any(original, school_wo_patterns) and _contains_any(corrected, school_ni_patterns):
        if "particle_misuse" not in cleaned:
            cleaned.append("particle_misuse")

    # 5. 조사 누락: 대표 패턴
    omission_pairs = [
        ("友達一緒に", "友達と一緒に"),
        ("図書館日本語", "図書館で日本語"),
        ("レストラン昼ご飯", "レストランで昼ご飯"),
        ("学校行き", "学校に行き"),
    ]

    for before, after in omission_pairs:
        if before in original and after in corrected:
            if "particle_omission" not in cleaned:
                cleaned.append("particle_omission")

    # 6. 시제 오류: 昨日 포함 + ます 계열이 ました 계열로 바뀐 경우
    tense_pairs = [
        ("食べます", "食べました"),
        ("勉強します", "勉強しました"),
        ("行きます", "行きました"),
        ("飲みます", "飲みました"),
    ]

    if "昨日" in original:
        for before, after in tense_pairs:
            if before in original and after in corrected:
                if "tense_error" not in cleaned:
                    cleaned.append("tense_error")

    # 7. 동사 활용 오류: 비정상 활용 대표 패턴
    conjugation_error_patterns = [
        "ましたない",
        "ますない",
        "食べましたない",
        "飲みましたない",
        "行きましたない",
    ]

    if _contains_any(original, conjugation_error_patterns):
        # 이 경우 핵심은 조사 누락이 아니라 동사 활용 오류다.
        cleaned = [e for e in cleaned if e not in ["particle_omission", "particle_misuse"]]

        if "verb_conjugation_error" not in cleaned:
            cleaned.append("verb_conjugation_error")

    return cleaned


def _feedback_looks_positive(feedback: str) -> bool:
    """
    LLM 피드백이 '오류 없음/자연스러움' 계열인지 대략 판정한다.
    """
    if not feedback:
        return True

    positive_markers = [
        "오류가 없습니다",
        "문제가 없습니다",
        "자연스러운 일본어",
        "문법과 의미가 올바",
        "문법적으로 올바",
        "수정할 필요가 없습니다",
        "교정이 필요하지 않습니다",
        "自然な日本語",
        "誤りはありません",
        "修正する必要はありません",
        "問題ありません",
    ]

    return any(marker in feedback for marker in positive_markers)


def _build_feedback_from_error_types(
    original_text: str,
    corrected_text: str,
    error_types: List[str],
    feedback_ko: str,
    feedback_ja: str,
) -> Dict[str, str]:
    """
    후처리된 error_types와 기존 feedback이 모순될 때 피드백을 보정한다.
    단, 기존 피드백이 이미 오류를 설명하고 있으면 최대한 유지한다.
    """
    if not error_types:
        return {
            "feedback_ko": feedback_ko,
            "feedback_ja": feedback_ja,
        }

    # 기존 피드백이 이미 오류 설명을 하고 있으면 유지한다.
    # 단, '오류 없음' 계열이면 교체한다.
    should_replace = _feedback_looks_positive(feedback_ko) or _feedback_looks_positive(feedback_ja)

    if not should_replace:
        return {
            "feedback_ko": feedback_ko,
            "feedback_ja": feedback_ja,
        }

    ko_parts = []
    ja_parts = []

    if "particle_omission" in error_types:
        ko_parts.append("문장에서 필요한 조사가 생략된 부분이 있어 문장 구조가 부자연스러웠습니다.")
        ja_parts.append("文の中で必要な助詞が省略されている部分があり、文の構造が不自然でした。")

    if "particle_misuse" in error_types:
        ko_parts.append("문맥상 사용된 조사가 적절하지 않아 더 자연스러운 조사로 수정했습니다.")
        ja_parts.append("文脈上、使われている助詞が適切ではなかったため、より自然な助詞に修正しました。")

    if "tense_error" in error_types:
        ko_parts.append("과거 시간 표현과 동사 시제가 맞지 않아 과거형으로 수정했습니다.")
        ja_parts.append("過去の時間表現と動詞の時制が一致していなかったため、過去形に修正しました。")

    if "word_choice_error" in error_types:
        ko_parts.append("명사와 동사의 의미 조합이 어색하여 더 적절한 동사로 수정했습니다.")
        ja_parts.append("名詞と動詞の意味の組み合わせが不自然だったため、より適切な動詞に修正しました。")

    if "verb_conjugation_error" in error_types:
        ko_parts.append("동사 활용 형태가 부자연스러워 올바른 활용 형태로 수정했습니다.")
        ja_parts.append("動詞の活用形が不自然だったため、正しい活用形に修正しました。")

    if "unnatural_expression" in error_types:
        ko_parts.append("문법적으로 완전히 틀렸다고 보기는 어렵지만, 더 자연스러운 표현으로 수정했습니다.")
        ja_parts.append("文法的に完全な誤りとは言い切れませんが、より自然な表現に修正しました。")

    if not ko_parts:
        ko_parts.append("입력 문장을 더 자연스러운 일본어 표현으로 수정했습니다.")

    if not ja_parts:
        ja_parts.append("入力文をより自然な日本語表現に修正しました。")

    return {
        "feedback_ko": " ".join(ko_parts),
        "feedback_ja": " ".join(ja_parts),
    }


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

    error_types = _postprocess_error_types(
        original_text=original_text,
        corrected_text=corrected_text,
        error_types=error_types,
    )

    original_for_compare = _normalize_for_compare(original_text)
    corrected_for_compare = _normalize_for_compare(corrected_text)

    if original_for_compare != corrected_for_compare:
        is_correct = False

    if original_for_compare == corrected_for_compare and not error_types:
        is_correct = True

    feedback_ko = _safe_text(parsed.get("feedback_ko"), default="")
    feedback_ja = _safe_text(parsed.get("feedback_ja"), default="")

    feedback_result = _build_feedback_from_error_types(
        original_text=original_text,
        corrected_text=corrected_text,
        error_types=error_types,
        feedback_ko=feedback_ko,
        feedback_ja=feedback_ja,
    )

    feedback_ko = feedback_result["feedback_ko"]
    feedback_ja = feedback_result["feedback_ja"]

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
