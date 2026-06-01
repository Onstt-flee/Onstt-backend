# analyzer/prompt_builder.py

import json


def build_prompt(
    original_text: str,
    primary_type: str,
    candidate_types,
    vocab_context: str,
    grammar_context: str,
    example_context: str,
    error_context: str,
) -> str:
    """
    RAG 검색 결과를 LLM 판단용 고정 프롬프트로 합성한다.
    이 함수는 LLM을 호출하지 않고, 프롬프트 문자열만 생성한다.
    """

    if not isinstance(candidate_types, str):
        candidate_types_text = json.dumps(candidate_types, ensure_ascii=False)
    else:
        candidate_types_text = candidate_types

    prompt = f"""
너는 일본어 학습자의 STT 인식 문장을 분석하는 일본어 교정 보조 시스템이다.

목표:
- 입력 문장이 자연스러운 일본어인지 판단한다.
- 오류가 있으면 의미를 바꾸지 않는 범위에서 최소한으로 교정한다.
- 오류 유형은 제공된 오류 코드 목록 안에서만 선택한다.
- 정상 문장, 인사 표현, 단편 발화를 불필요하게 고치지 않는다.
- STT 오류 가능성이 있어도 단정하지 말고, 문장 근거에 기반해 판단한다.

[입력 문장]
{original_text}

[문장 타입 분류 결과]
primary_type: {primary_type}
candidate_types: {candidate_types_text}

[단어 참고 자료]
{vocab_context}

[문법 참고 자료]
{grammar_context}

[예문 참고 자료]
{example_context}

[오류 패턴 참고 자료]
{error_context}

판단 규칙:
1. 참고 자료는 판단 근거일 뿐이며, 무조건 오류로 확정하지 않는다.
2. 의미가 통하는 자연스러운 회화 표현은 과교정하지 않는다.
3. 조사, 시제, 동사 활용, 단어 선택 오류가 명확할 때만 오류로 판단한다.
4. corrected_text는 입력 의미를 최대한 유지해야 한다.
5. error_types는 반드시 오류 패턴 참고 자료에 있는 코드만 사용한다.
6. 출력은 반드시 JSON 하나만 반환한다. 설명 문장을 JSON 밖에 쓰지 않는다.

출력 JSON 형식:
{{
  "is_correct": true 또는 false,
  "corrected_text": "교정 문장 또는 원문",
  "error_types": ["오류코드"],
  "feedback_ko": "한국어 피드백",
  "feedback_ja": "日本語フィードバック",
  "confidence": 0.0부터 1.0 사이 숫자
}}
""".strip()

    return prompt
