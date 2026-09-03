"""Regression checks for the bundled example-search index.

Run from the repository root with:
    venv/bin/python -m unittest discover -s tests -v

These tests use the repository's existing index without rebuilding it or
contacting the database or an LLM service.
"""

import unittest
from unittest.mock import patch

from analyzer import example_retriever


SAMPLE_QUERY = "きみにちょっとしたものをもってきたよ。"


class ExampleRetrieverTests(unittest.TestCase):
    def test_saved_index_matches_example_texts(self):
        texts = example_retriever.load_examples()
        vectorizer, tfidf_matrix = example_retriever.load_tfidf()

        self.assertTrue(texts)
        self.assertTrue(all(isinstance(text, str) and text.strip() for text in texts))
        self.assertEqual(tfidf_matrix.shape[0], len(texts))
        self.assertEqual(
            tfidf_matrix.shape[1], len(vectorizer.get_feature_names_out())
        )

    def test_self_query_returns_matching_example_and_context(self):
        self.assertIn(SAMPLE_QUERY, example_retriever.load_examples())

        result = example_retriever.retrieve_examples(SAMPLE_QUERY, top_k=5)
        examples = result["examples"]

        self.assertTrue(examples)
        self.assertEqual(examples[0]["text"], SAMPLE_QUERY)
        self.assertAlmostEqual(examples[0]["score"], 1.0, places=4)
        self.assertTrue(all(item["score"] > 0 for item in examples))
        self.assertEqual(
            [item["score"] for item in examples],
            sorted((item["score"] for item in examples), reverse=True),
        )
        self.assertEqual(
            result["example_context"],
            "\n".join(
                f"[예문 {number}] {item['text']} (similarity={item['score']})"
                for number, item in enumerate(examples, start=1)
            ),
        )

    def test_top_k_limits_results(self):
        for top_k in (0, 1, 3):
            with self.subTest(top_k=top_k):
                result = example_retriever.retrieve_examples(SAMPLE_QUERY, top_k=top_k)

                self.assertLessEqual(len(result["examples"]), top_k)
                if top_k:
                    self.assertTrue(result["examples"])
                    self.assertEqual(result["examples"][0]["text"], SAMPLE_QUERY)
                else:
                    self.assertEqual(result, {"examples": [], "example_context": ""})

    def test_empty_input_skips_index_loading(self):
        for text in (None, "", " \n\t", "\u3000"):
            with self.subTest(text=text):
                with (
                    patch.object(example_retriever, "load_examples") as load_examples,
                    patch.object(example_retriever, "load_tfidf") as load_tfidf,
                ):
                    result = example_retriever.retrieve_examples(text)

                self.assertEqual(result, {"examples": [], "example_context": ""})
                load_examples.assert_not_called()
                load_tfidf.assert_not_called()


if __name__ == "__main__":
    unittest.main()
