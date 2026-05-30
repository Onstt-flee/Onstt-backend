import json
from pathlib import Path
from typing import Any, Dict, List, Optional


BASE_DIR = Path(__file__).resolve().parent.parent
GRAMMAR_RULES_PATH = BASE_DIR / "rag_data" / "grammar" / "grammar_rules.json"


def load_grammar_rules() -> List[Dict[str, Any]]:
    """
    grammar_rules.json 파일을 로드한다.

    이 함수는 규칙을 해석하거나 교정하지 않는다.
    단순히 RAG 검색에 사용할 문법 참고 데이터를 읽는다.
    """
    try:
        with open(GRAMMAR_RULES_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)

        if not isinstance(data, list):
            return []

        return data

    except FileNotFoundError:
        return []
    except json.JSONDecodeError:
        return []


def score_rule(text: str, sentence_type: Optional[str], rule: Dict[str, Any]) -> Dict[str, int]:
    """
    입력 문장과 문법 규칙의 관련도 점수를 계산한다.

    중요:
    - 이 점수는 '오류 점수'가 아니다.
    - 이 점수는 '교정 필요성 점수'도 아니다.
    - 단순히 현재 문장과 해당 문법 참고 규칙이 얼마나 관련 있는지 나타내는 관련도 점수다.

    점수 기준:
    - keyword가 입력 문장에 포함될 때마다 +1
    - sentence_type이 규칙의 sentence_types에 포함되면 +2
    - 단, keyword_match_count가 0이면 문장 타입만 맞아도 검색 결과에서 제외할 수 있도록 한다.
    """
    keyword_match_count = 0
    type_match_score = 0

    keywords = rule.get("keywords", [])
    for keyword in keywords:
        if keyword and keyword in text:
            keyword_match_count += 1

    rule_sentence_types = rule.get("sentence_types", [])
    if sentence_type and sentence_type in rule_sentence_types:
        type_match_score = 2

    total_score = keyword_match_count + type_match_score

    return {
        "total_score": total_score,
        "keyword_match_count": keyword_match_count,
        "type_match_score": type_match_score
    }


def retrieve_grammar_rules(
    text: str,
    sentence_type: Optional[str] = None,
    top_k: int = 5
) -> Dict[str, Any]:
    """
    입력 문장과 문장 타입에 맞는 문법 참고 규칙을 검색한다.

    이 함수는 다음을 하지 않는다:
    - 문장 교정
    - 오류 확정
    - is_correct 판정
    - error_types 확정

    이 함수의 역할은 관련 문법 참고 자료를 찾아 grammar_context로 제공하는 것뿐이다.
    """
    rules = load_grammar_rules()
    scored_rules = []

    for rule in rules:
        score_info = score_rule(text, sentence_type, rule)

        # 과교정 방지:
        # sentence_type만 맞고 실제 키워드가 하나도 맞지 않는 규칙은 제외한다.
        if score_info["keyword_match_count"] == 0:
            continue

        if score_info["total_score"] > 0:
            scored_rules.append(
                {
                    "score_info": score_info,
                    "rule": rule
                }
            )

    scored_rules.sort(
        key=lambda item: item["score_info"]["total_score"],
        reverse=True
    )

    matched_rules = [
        {
            "id": item["rule"].get("id"),
            "title": item["rule"].get("title"),
            "level": item["rule"].get("level"),
            "rule_type": item["rule"].get("rule_type"),
            "pattern": item["rule"].get("pattern"),
            "description_ko": item["rule"].get("description_ko"),
            "reference_examples": item["rule"].get("reference_examples", []),
            "possible_focus": item["rule"].get("possible_focus", []),
            "possible_error_types": item["rule"].get("possible_error_types", []),
            "overcorrection_note": item["rule"].get("overcorrection_note"),
            "score": item["score_info"]["total_score"],
            "keyword_match_count": item["score_info"]["keyword_match_count"],
            "type_match_score": item["score_info"]["type_match_score"],
        }
        for item in scored_rules[:top_k]
    ]

    grammar_context = build_grammar_context(matched_rules)

    return {
        "matched_rules": matched_rules,
        "grammar_context": grammar_context
    }


def build_grammar_context(matched_rules: List[Dict[str, Any]]) -> str:
    """
    LLM 또는 pipeline에서 사용할 수 있는 문법 참고 context를 만든다.

    중요:
    - 이 context는 교정 지시문이 아니다.
    - 이 context는 오류 확정 결과가 아니다.
    - 이 context는 관련 문법 참고 자료다.
    """
    if not matched_rules:
        return ""

    lines = []

    lines.append("다음은 입력 문장과 관련 있을 수 있는 문법 참고 자료이다.")
    lines.append("이 자료는 오류 확정이나 교정 지시가 아니라, 판단을 위한 참고 근거이다.")
    lines.append("soft_reference 또는 style_reference 규칙은 과교정하지 않도록 주의한다.")
    lines.append("")

    for rule in matched_rules:
        lines.append(f"[{rule['id']}] {rule['title']}")
        lines.append(f"- rule_type: {rule.get('rule_type')}")
        lines.append(f"- level: {rule.get('level')}")
        lines.append(f"- pattern: {rule.get('pattern')}")
        lines.append(f"- description_ko: {rule.get('description_ko')}")

        reference_examples = rule.get("reference_examples", [])
        if reference_examples:
            lines.append(f"- reference_examples: {', '.join(reference_examples)}")

        possible_focus = rule.get("possible_focus", [])
        if possible_focus:
            lines.append(f"- possible_focus: {', '.join(possible_focus)}")

        possible_error_types = rule.get("possible_error_types", [])
        if possible_error_types:
            lines.append(f"- possible_error_types: {', '.join(possible_error_types)}")

        overcorrection_note = rule.get("overcorrection_note")
        if overcorrection_note:
            lines.append(f"- overcorrection_note: {overcorrection_note}")

        lines.append(
            f"- retrieval_score: {rule.get('score')} "
            f"(keyword_match_count={rule.get('keyword_match_count')}, "
            f"type_match_score={rule.get('type_match_score')})"
        )

        lines.append("")

    return "\n".join(lines).strip()