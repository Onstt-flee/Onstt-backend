"""Isolated runner for the rejected judgment-v0.2.1 prompt experiment.

The frozen holdout protocols pin runner.py by SHA-256. This module registers the
experimental prompt only for its own process so the historical runner remains
byte-for-byte unchanged.
"""

from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator

from evaluation.judgment import runner


PROMPT_VERSION_V21 = "judgment-v0.2.1"
SYSTEM_PROMPT_V21 = """당신은 일본어 학습자 발화의 문법 교정 필요성을 판단하는 시스템입니다.
학습자 점수를 매기거나 더 세련된 표현으로 바꾸지 말고, 주어진 텍스트와 문맥만 판단하세요.

반드시 JSON 객체 하나만 출력하고 다음 네 필드만 사용하세요.
{
  "decision": "acceptable | needs_correction | insufficient_evidence",
  "corrected_text": "원문 또는 최소 교정문",
  "error_types": ["허용 오류 유형"],
  "reason_ko": "짧은 한국어 판단 근거"
}

허용 오류 유형은 particle_misuse, verb_conjugation, adjective_conjugation,
copula_conjugation, modifier_connection, tense_mismatch뿐입니다.

판단 규칙:
1. acceptable 또는 insufficient_evidence이면 corrected_text에 사용자 입력 JSON의 text 값을 문자 단위로 정확히 복사하세요.
2. 위 두 판단에서는 원문의 공백·구두점·표기·불완전한 부분을 삭제, 추가, 완성, 정규화하거나 번역하지 말고 error_types는 반드시 빈 배열로 출력하세요.
3. needs_correction일 때만 의미와 문체를 보존하는 최소 문법 교정을 하고 해당 오류 유형을 중복 없이 기록하세요.
4. 수정 위치는 출력하지 마세요. 위치와 변경 구간은 백엔드가 원문과 corrected_text의 차이로 계산합니다.
5. 문체 취향, 더 자연스러운 대안, 표기 조언, 발음 추정, 질문 관련성을 문법 교정과 섞지 마세요.
6. 원음이 없으면 학습자 발음 오류와 STT 전사 오류 중 하나로 단정하지 마세요.
7. 빈 입력, 잡음뿐인 입력, 누락 구간, 범위 밖 언어는 insufficient_evidence로 처리하되 원문 text를 그대로 복사하세요.
8. 출력 직전에 decision이 needs_correction이 아니라면 corrected_text가 입력 text와 완전히 같은지 다시 확인하세요.
9. JSON 밖의 설명, Markdown 코드 펜스, 추가 필드는 출력하지 마세요."""


@contextmanager
def activated_prompt() -> Iterator[None]:
    """Temporarily reuse the v0.2 parser for the position-free v0.2.1 contract."""
    original_version = runner.PROMPT_VERSION_V2
    runner.PROMPTS[PROMPT_VERSION_V21] = SYSTEM_PROMPT_V21
    runner.PROMPT_VERSION_V2 = PROMPT_VERSION_V21
    try:
        yield
    finally:
        runner.PROMPT_VERSION_V2 = original_version
        runner.PROMPTS.pop(PROMPT_VERSION_V21, None)


def main(argv: list[str] | None = None) -> int:
    with activated_prompt():
        return runner.main(argv)


if __name__ == "__main__":
    raise SystemExit(main())
