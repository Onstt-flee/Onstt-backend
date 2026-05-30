import json
from pathlib import Path
from typing import Any, Dict, List, Optional


BASE_DIR = Path(__file__).resolve().parent.parent
ERROR_PATTERNS_PATH = BASE_DIR / "rag_data" / "errors" / "error_patterns.json"


def load_error_patterns() -> List[Dict[str, Any]]:
    """
    error_patterns.json 파일을 로드한다.

    이 함수는 오류 패턴 참고 자료를 읽기만 한다.
    오류 확정, 교정, error_types 확정은 하지 않는다.
    """
    try:
        with open(ERROR_PATTERNS_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)

        if not isinstance(data, list):
            return []

        return data

    except FileNotFoundError:
        return []
    except json.JSONDecodeError:
        return []


def score_error_pattern(
    text: str,
    primary_type: Optional[str],
    pattern: Dict[str, Any],
) -> Dict[str, int]:
    """
    입력 문장과 오류 패턴의 관련도 점수를 계산한다.

    중요:
    - 이 점수는 오류 확정 점수가 아니다.
    - 이 점수는 교정 필요성 점수가 아니다.
    - 단순히 현재 문장과 오류 패턴 참고 자료가 얼마나 관련 있어 보이는지 나타낸다.
    """
    keyword_match_count = 0

    keywords = pattern.get("keywords", [])
    for keyword in keywords:
        if keyword and keyword in text:
            keyword_match_count += 1

    # 기본적으로 키워드 기반 관련도만 사용한다.
    # invalid는 pipeline에서 이미 조기 반환하므로 여기서는 일반 문장만 대상으로 한다.
    type_match_score = 0
    if primary_type in ["statement", "question", "request", "emotion"]:
        type_match_score = 1

    total_score = keyword_match_count + type_match_score

    return {
        "total_score": total_score,
        "keyword_match_count": keyword_match_count,
        "type_match_score": type_match_score,
    }


def retrieve_error_patterns(
    text: str,
    primary_type: Optional[str] = None,
    top_k: int = 5,
) -> Dict[str, Any]:
    """
    입력 문장에 관련 있을 수 있는 오류 패턴 참고 자료를 검색한다.

    이 함수는 다음을 하지 않는다:
    - 오류 확정
    - 문장 교정
    - is_correct 판정
    - error_types 확정

    이 함수의 역할은 possible error 참고 자료를 error_context로 제공하는 것뿐이다.
    """
    patterns = load_error_patterns()
    scored_patterns = []

    for pattern in patterns:
        score_info = score_error_pattern(text, primary_type, pattern)

        # 과교정 방지:
        # 키워드가 하나도 맞지 않는 오류 패턴은 제외한다.
        if score_info["keyword_match_count"] == 0:
            continue

        if score_info["total_score"] > 0:
            scored_patterns.append(
                {
                    "score_info": score_info,
                    "pattern": pattern,
                }
            )

    scored_patterns.sort(
        key=lambda item: item["score_info"]["total_score"],
        reverse=True,
    )

    matched_patterns = [
        {
            "id": item["pattern"].get("id"),
            "error_code": item["pattern"].get("error_code"),
            "title": item["pattern"].get("title"),
            "description_ko": item["pattern"].get("description_ko"),
            "reference_examples": item["pattern"].get("reference_examples", []),
            "related_focus": item["pattern"].get("related_focus", []),
            "overcorrection_note": item["pattern"].get("overcorrection_note"),
            "score": item["score_info"]["total_score"],
            "keyword_match_count": item["score_info"]["keyword_match_count"],
            "type_match_score": item["score_info"]["type_match_score"],
        }
        for item in scored_patterns[:top_k]
    ]

    return {
        "matched_error_patterns": matched_patterns,
        "error_context": build_error_context(matched_patterns),
    }


def build_error_context(matched_patterns: List[Dict[str, Any]]) -> str:
    """
    pipeline과 나중의 LLM 프롬프트에서 사용할 오류 패턴 참고 context를 만든다.

    중요:
    - 이 context는 오류 확정 결과가 아니다.
    - 이 context는 교정 지시가 아니다.
    - 이 context는 가능한 오류 유형 참고 자료다.
    """
    if not matched_patterns:
        return ""

    lines = []

    lines.append("다음은 입력 문장과 관련 있을 수 있는 오류 유형 참고 자료이다.")
    lines.append("이 자료는 오류 확정이나 교정 지시가 아니라, 가능한 오류 유형을 판단하기 위한 참고 근거이다.")
    lines.append("회화체 생략, 인사 표현, 단편 발화는 과교정하지 않도록 주의한다.")
    lines.append("")

    for pattern in matched_patterns:
        lines.append(f"[{pattern['error_code']}] {pattern['title']}")
        lines.append(f"- description_ko: {pattern.get('description_ko')}")

        related_focus = pattern.get("related_focus", [])
        if related_focus:
            lines.append(f"- related_focus: {', '.join(related_focus)}")

        reference_examples = pattern.get("reference_examples", [])
        if reference_examples:
            lines.append("- reference_examples:")
            for example in reference_examples:
                observed = example.get("observed", "")
                reference = example.get("reference", "")
                lines.append(f"  - observed: {observed}")
                lines.append(f"    reference: {reference}")

        overcorrection_note = pattern.get("overcorrection_note")
        if overcorrection_note:
            lines.append(f"- overcorrection_note: {overcorrection_note}")

        lines.append(
            f"- retrieval_score: {pattern.get('score')} "
            f"(keyword_match_count={pattern.get('keyword_match_count')}, "
            f"type_match_score={pattern.get('type_match_score')})"
        )

        lines.append("")

    return "\n".join(lines).strip()
