import csv
import json
from pathlib import Path
from typing import List, Dict


BASE_DIR = Path(__file__).resolve().parent.parent
CSV_PATH = BASE_DIR / "rag_data" / "vocab" / "n5_raw.csv"
OUTPUT_PATH = BASE_DIR / "rag_data" / "vocab" / "word_db.json"


def detect_level(tags: str) -> str:
    tags = tags or ""

    if "N5" in tags or "JLPT_5" in tags:
        return "N5"
    if "N4" in tags or "JLPT_4" in tags:
        return "N4"
    if "N3" in tags or "JLPT_3" in tags:
        return "N3"
    if "N2" in tags or "JLPT_2" in tags:
        return "N2"
    if "N1" in tags or "JLPT_1" in tags:
        return "N1"

    return "unknown"


def split_expressions(expression: str) -> List[str]:
    """
    '足; 脚' 같은 항목을 각각 매칭 가능하게 분리한다.
    """
    if not expression:
        return []

    parts = []
    for item in expression.split(";"):
        item = item.strip()
        if item:
            parts.append(item)

    return parts


def build_word_db() -> Dict[str, dict]:
    word_db = {}

    with open(CSV_PATH, "r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)

        for row in reader:
            expression = (row.get("expression") or "").strip()
            reading = (row.get("reading") or "").strip()
            meaning = (row.get("meaning") or "").strip()
            tags = (row.get("tags") or "").strip()

            if not expression:
                continue

            forms = split_expressions(expression)
            if not forms:
                forms = [expression]

            representative = forms[0]

            word_db[representative] = {
                "word": representative,
                "reading": reading,
                "meaning": meaning,
                "level": detect_level(tags),
                "forms": forms,
            }

    return word_db


def main():
    if not CSV_PATH.exists():
        raise FileNotFoundError(f"CSV file not found: {CSV_PATH}")

    word_db = build_word_db()

    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(word_db, f, ensure_ascii=False, indent=2)

    print(f"created: {OUTPUT_PATH}")
    print(f"word count: {len(word_db)}")


if __name__ == "__main__":
    main()
