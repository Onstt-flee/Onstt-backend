import json
from pathlib import Path
from typing import Any, Dict, List, Tuple


BASE_DIR = Path(__file__).resolve().parent.parent
WORD_DB_PATH = BASE_DIR / "rag_data" / "vocab" / "word_db.json"


def load_word_db() -> Dict[str, Dict[str, Any]]:
    """
    word_db.json 파일을 로드한다.

    이 함수는 단어 정보를 읽기만 한다.
    교정, 오류 판정, 단어 선택 오류 확정은 하지 않는다.
    """
    try:
        with open(WORD_DB_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)

        if not isinstance(data, dict):
            return {}

        return data

    except FileNotFoundError:
        return {}
    except json.JSONDecodeError:
        return {}


def has_overlap(start: int, end: int, spans: List[Tuple[int, int]]) -> bool:
    """
    이미 매칭된 단어 범위와 겹치는지 확인한다.
    """
    for span_start, span_end in spans:
        if start < span_end and end > span_start:
            return True

    return False


def retrieve_vocab(text: str, top_k: int = 20) -> Dict[str, Any]:
    """
    입력 문장에서 word_db.json에 있는 단어를 검색한다.

    역할:
    - 입력 문장에 포함된 단어 찾기
    - 읽기, 뜻, JLPT 레벨을 참고 자료로 제공

    하지 않는 것:
    - 문장 교정
    - 오류 확정
    - 단어 선택 오류 확정
    """
    word_db = load_word_db()
    matched_words: List[Dict[str, Any]] = []
    consumed_spans: List[Tuple[int, int]] = []

    # 긴 단어를 먼저 매칭한다.
    # 예: 日本語가 日本보다 먼저 잡히도록 처리한다.
    sorted_items = sorted(
        word_db.items(),
        key=lambda item: len(item[0]),
        reverse=True,
    )

    for word, info in sorted_items:
        forms = info.get("forms") or [word]

        for form in forms:
            if not form:
                continue

            start = text.find(form)
            if start == -1:
                continue

            end = start + len(form)

            if has_overlap(start, end, consumed_spans):
                continue

            matched_words.append(
                {
                    "word": info.get("word", word),
                    "matched_form": form,
                    "reading": info.get("reading", ""),
                    "meaning": info.get("meaning", ""),
                    "level": info.get("level", ""),
                    "start": start,
                    "end": end,
                }
            )
            consumed_spans.append((start, end))
            break

        if len(matched_words) >= top_k:
            break

    matched_words.sort(key=lambda item: item["start"])

    return {
        "matched_words": matched_words,
        "vocab_context": build_vocab_context(matched_words),
    }


def build_vocab_context(matched_words: List[Dict[str, Any]]) -> str:
    """
    pipeline과 나중의 LLM 프롬프트에서 사용할 단어 참고 context를 만든다.

    이 context는 교정 지시가 아니라 단어 의미 참고 자료다.
    """
    if not matched_words:
        return ""

    lines = []

    lines.append("다음은 입력 문장에서 검색된 단어 참고 자료이다.")
    lines.append("이 자료는 단어 의미와 읽기 확인용이며, 오류 확정이나 교정 지시가 아니다.")
    lines.append("")

    for item in matched_words:
        lines.append(f"[{item['word']}]")
        lines.append(f"- matched_form: {item.get('matched_form')}")
        lines.append(f"- reading: {item.get('reading')}")
        lines.append(f"- meaning: {item.get('meaning')}")
        lines.append(f"- level: {item.get('level')}")
        lines.append("")

    return "\n".join(lines).strip()
