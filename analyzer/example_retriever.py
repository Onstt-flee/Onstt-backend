import json
import pickle
from pathlib import Path
from typing import Any, Dict, List


BASE_DIR = Path(__file__).resolve().parent.parent

TEXTS_PATH = BASE_DIR / "rag_data" / "examples" / "texts.json"
TFIDF_PATH = BASE_DIR / "rag_data" / "examples" / "tfidf.pkl"


def load_examples() -> List[str]:
    with open(TEXTS_PATH, "r", encoding="utf-8") as f:
        texts = json.load(f)

    if not isinstance(texts, list):
        raise ValueError("texts.json must be a list")

    return texts


def load_tfidf():
    with open(TFIDF_PATH, "rb") as f:
        data = pickle.load(f)

    if not isinstance(data, tuple) or len(data) != 2:
        raise ValueError("tfidf.pkl must contain (vectorizer, tfidf_matrix)")

    vectorizer, tfidf_matrix = data
    return vectorizer, tfidf_matrix


def retrieve_examples(text: str, top_k: int = 5) -> Dict[str, Any]:
    """
    입력 문장과 유사한 예문을 TF-IDF cosine similarity 기준으로 검색한다.
    현재 단계에서는 LLM 판단용 참고 예문 context만 생성한다.
    """

    if text is None or not text.strip():
        return {
            "examples": [],
            "example_context": ""
        }

    texts = load_examples()
    vectorizer, tfidf_matrix = load_tfidf()

    query_vec = vectorizer.transform([text])
    scores = (tfidf_matrix @ query_vec.T).toarray().ravel()

    top_indices = scores.argsort()[::-1][:top_k]

    examples = []

    for idx in top_indices:
        score = float(scores[idx])

        if score <= 0:
            continue

        examples.append({
            "text": texts[idx],
            "score": round(score, 4)
        })

    context_lines = []

    for i, item in enumerate(examples, start=1):
        context_lines.append(
            f"[예문 {i}] {item['text']} (similarity={item['score']})"
        )

    example_context = "\n".join(context_lines)

    return {
        "examples": examples,
        "example_context": example_context
    }


if __name__ == "__main__":
    result = retrieve_examples("今日は学校に行きました", top_k=5)

    print("examples:")
    for item in result["examples"]:
        print(item)

    print("\nexample_context:")
    print(result["example_context"])