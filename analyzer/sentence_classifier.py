import re
from typing import Dict, Any, List


QUESTION_PATTERNS = [
    r"か$",
    r"ですか$",
    r"ますか$",
    r"何",
    r"どこ",
    r"いつ",
    r"だれ",
    r"誰",
]

REQUEST_PATTERNS = [
    r"ください",
    r"お願いします",
    r"てください",
]

GREETING_PATTERNS = [
    r"こんにちは",
    r"こんばんは",
    r"おはよう(?:\s*ございます)?",
    r"はじめまして",
    r"(?:どうも\s*)?ありがとう(?:\s*ござい(?:ます|ました))?",
    r"すみません(?:\s*でした)?",
]

EMOTION_PATTERNS = [
    r"好き",
    r"嫌い",
    r"疲れた",
    r"楽しい",
    r"嬉しい",
    r"悲しい",
    r"眠い",
    r"お腹",
]


TYPE_PRIORITY = [
    "invalid",
    "question",
    "request",
    "greeting",
    "emotion",
    "statement",
    "fragment",
]


def _match_patterns(text: str, patterns: List[str]) -> List[str]:
    matched = []

    for pattern in patterns:
        if re.search(pattern, text):
            matched.append(pattern)

    return matched


def classify_sentence(text: str, is_valid: bool = True) -> Dict[str, Any]:
    """
    Layer 2 문장 타입 분류 함수.

    역할:
    - invalid / greeting / question / request / emotion / statement / fragment 분류
    - 하나의 타입으로 강제하지 않고 candidate_types에 후보를 모두 저장
    - primary_type은 우선순위와 점수를 기준으로 하나만 선택
    - needs_deep_analysis 여부 반환
    """
    candidate_types = []

    if not is_valid:
        return {
            "primary_type": "invalid",
            "candidate_types": [
                {
                    "type": "invalid",
                    "score": 1.0,
                    "matched_rules": ["input_validation_failed"],
                }
            ],
            "classification_reason": "입력 검증 단계에서 분석 불가로 판단됨",
            "needs_deep_analysis": False,
        }

    normalized_text = text.strip()

    if len(normalized_text) <= 2:
        candidate_types.append(
            {
                "type": "fragment",
                "score": 0.8,
                "matched_rules": ["short_text"],
            }
        )

    # 인사가 포함된 일반 문장을 조기 정답 처리하지 않도록 단독 인사만 허용한다.
    greeting_matches = [
        pattern
        for pattern in GREETING_PATTERNS
        if re.fullmatch(rf"(?:{pattern})[\s。．.!！?？]*", normalized_text)
    ]
    if greeting_matches:
        candidate_types.append(
            {
                "type": "greeting",
                "score": 0.95,
                "matched_rules": greeting_matches,
            }
        )

    question_matches = _match_patterns(normalized_text, QUESTION_PATTERNS)
    if question_matches:
        candidate_types.append(
            {
                "type": "question",
                "score": 0.9,
                "matched_rules": question_matches,
            }
        )

    request_matches = _match_patterns(normalized_text, REQUEST_PATTERNS)
    if request_matches:
        candidate_types.append(
            {
                "type": "request",
                "score": 0.9,
                "matched_rules": request_matches,
            }
        )

    emotion_matches = _match_patterns(normalized_text, EMOTION_PATTERNS)
    if emotion_matches:
        candidate_types.append(
            {
                "type": "emotion",
                "score": 0.85,
                "matched_rules": emotion_matches,
            }
        )

    if not candidate_types:
        candidate_types.append(
            {
                "type": "statement",
                "score": 0.7,
                "matched_rules": ["default_statement"],
            }
        )

    primary_type = _select_primary_type(candidate_types)

    needs_deep_analysis = primary_type not in ["invalid", "greeting", "fragment"]

    return {
        "primary_type": primary_type,
        "candidate_types": candidate_types,
        "classification_reason": _build_reason(primary_type, candidate_types),
        "needs_deep_analysis": needs_deep_analysis,
    }


def _select_primary_type(candidate_types: List[Dict[str, Any]]) -> str:
    """
    점수가 같거나 비슷할 때 TYPE_PRIORITY 기준으로 대표 타입 선택.
    """
    sorted_candidates = sorted(
        candidate_types,
        key=lambda item: (
            -item["score"],
            TYPE_PRIORITY.index(item["type"])
            if item["type"] in TYPE_PRIORITY
            else 999,
        ),
    )

    return sorted_candidates[0]["type"]


def _build_reason(primary_type: str, candidate_types: List[Dict[str, Any]]) -> str:
    type_names = [item["type"] for item in candidate_types]

    return (
        "후보 타입 "
        + ", ".join(type_names)
        + " 중 대표 타입을 "
        + primary_type
        + "으로 선택함"
    )
