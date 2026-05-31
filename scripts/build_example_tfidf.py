import json
import pickle
import re
from pathlib import Path

from sklearn.feature_extraction.text import TfidfVectorizer


BASE_DIR = Path(__file__).resolve().parent.parent

TEXTS_PATH = BASE_DIR / "rag_data" / "examples" / "texts.json"
TFIDF_PATH = BASE_DIR / "rag_data" / "examples" / "tfidf.pkl"


def contains_japanese(text: str) -> bool:
    return bool(re.search(r"[\u3040-\u30ff\u3400-\u9fff]", text))


def main():
    with open(TEXTS_PATH, "r", encoding="utf-8") as f:
        raw_texts = json.load(f)

    if not isinstance(raw_texts, list):
        raise ValueError("texts.json must be a list")

    texts = [
        text.strip()
        for text in raw_texts
        if isinstance(text, str)
        and text.strip()
        and contains_japanese(text)
    ]

    vectorizer = TfidfVectorizer(
        analyzer="char",
        ngram_range=(2, 4),
        lowercase=False
    )

    tfidf_matrix = vectorizer.fit_transform(texts)

    with open(TEXTS_PATH, "w", encoding="utf-8") as f:
        json.dump(texts, f, ensure_ascii=False, indent=2)

    with open(TFIDF_PATH, "wb") as f:
        pickle.dump((vectorizer, tfidf_matrix), f)

    print("saved texts:", len(texts))
    print("saved tfidf:", TFIDF_PATH)
    print("tfidf shape:", tfidf_matrix.shape)
    print("vocab size:", len(vectorizer.get_feature_names_out()))


if __name__ == "__main__":
    main()