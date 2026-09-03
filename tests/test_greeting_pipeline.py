"""Greeting-path regressions without loading RAG data or calling an LLM."""

import json
import unittest
from unittest.mock import patch

from analyzer import pipeline


class GreetingPipelineTests(unittest.TestCase):
    def setUp(self):
        self.retrievers = {}
        for function_name, context_key in (
            ("retrieve_vocab", "vocab_context"),
            ("retrieve_grammar_rules", "grammar_context"),
            ("retrieve_examples", "example_context"),
            ("retrieve_error_patterns", "error_context"),
        ):
            patcher = patch.object(
                pipeline,
                function_name,
                return_value={context_key: f"mock {context_key}"},
            )
            self.retrievers[function_name] = patcher.start()
            self.addCleanup(patcher.stop)

        llm_patcher = patch.object(pipeline, "call_llm")
        self.call_llm = llm_patcher.start()
        self.addCleanup(llm_patcher.stop)

    def assert_retrieved_entire_text(self, text, primary_type):
        self.retrievers["retrieve_vocab"].assert_called_once_with(text, top_k=20)
        self.retrievers["retrieve_grammar_rules"].assert_called_once_with(
            text, sentence_type=primary_type, top_k=5
        )
        self.retrievers["retrieve_examples"].assert_called_once_with(text, top_k=5)
        self.retrievers["retrieve_error_patterns"].assert_called_once_with(
            text, primary_type=primary_type, top_k=5
        )
        self.call_llm.assert_called_once()
        prompt = self.call_llm.call_args.args[0]
        self.assertIn(f"[입력 문장]\n{text}\n\n[문장 타입 분류 결과]", prompt)

    def mock_llm_response(self, corrected_text, error_types):
        self.call_llm.return_value = {
            "success": True,
            "raw_text": json.dumps(
                {
                    "is_correct": not error_types,
                    "corrected_text": corrected_text,
                    "error_types": error_types,
                    "feedback_ko": "문장 전체를 검토한 결과입니다.",
                    "feedback_ja": "文全体を確認した結果です。",
                    "confidence": 0.87,
                },
                ensure_ascii=False,
            ),
            "model_name": "mock-llm",
            "adapter_name": "mock-adapter",
        }

    def reset_calls(self):
        for retriever in self.retrievers.values():
            retriever.reset_mock()
        self.call_llm.reset_mock()

    def test_standalone_greetings_do_not_call_retrievers_or_llm(self):
        for greeting in (
            "こんにちは",
            "こんばんは",
            "おはよう",
            "はじめまして",
            "ありがとう",
            "すみません",
            "おはようございます",
            "ありがとうございます",
            "ありがとうございました",
            "すみませんでした",
            "どうもありがとう",
            "どうもありがとうございます",
            "どうもありがとうございました",
            "おはよう ございます",
            "ありがとう ございました",
            "すみません でした",
            "どうも ありがとう ございます",
        ):
            for ending in ("", "。", "！", "!", "？", "?"):
                with self.subTest(greeting=greeting, ending=ending):
                    self.reset_calls()
                    text = f"{greeting}{ending}"

                    result = pipeline.analyze(f" \t\u3000{text}\u3000\n ")

                    self.assertEqual(result["primary_type"], "greeting")
                    self.assertFalse(result["needs_deep_analysis"])
                    self.assertTrue(result["is_correct"])
                    self.assertEqual(result["corrected_text"], text)
                    self.assertEqual(result["error_types"], [])
                    self.assertEqual(result["model_name"], "rule_based_pipeline")
                    for retriever in self.retrievers.values():
                        retriever.assert_not_called()
                    self.call_llm.assert_not_called()

    def test_mixed_greetings_are_fully_analyzed_and_return_llm_corrections(self):
        for original, corrected, errors in (
            (
                "すみません、学校を行きます。",
                "すみません、学校に行きます。",
                ["particle_misuse"],
            ),
            (
                "こんにちは。昨日水を食べます。",
                "こんにちは。昨日水を飲みました。",
                ["word_choice_error", "tense_error"],
            ),
            (
                "学校を行きます。ありがとう",
                "学校に行きます。ありがとう",
                ["particle_misuse"],
            ),
            (
                "すみません学校を行きます。",
                "すみません学校に行きます。",
                ["particle_misuse"],
            ),
        ):
            with self.subTest(original=original):
                self.reset_calls()
                self.mock_llm_response(corrected, errors)

                result = pipeline.analyze(original)

                self.assert_retrieved_entire_text(original, "statement")
                self.assertEqual(result["primary_type"], "statement")
                self.assertTrue(result["needs_deep_analysis"])
                self.assertFalse(result["is_correct"])
                self.assertEqual(result["corrected_text"], corrected)
                self.assertCountEqual(result["error_types"], errors)
                self.assertEqual(result["model_name"], "mock-llm")
                self.assertEqual(result["adapter_name"], "mock-adapter")
                self.assertEqual(result["confidence"], 0.87)
                for key in (
                    "vocab_context", "grammar_context", "example_context", "error_context"
                ):
                    self.assertEqual(result[key], f"mock {key}")

    def test_quoted_greeting_requires_llm_analysis_even_when_correct(self):
        text = "彼は「こんにちは」と言いました。"
        self.mock_llm_response(text, [])

        result = pipeline.analyze(text)

        self.assert_retrieved_entire_text(text, "statement")
        self.assertTrue(result["needs_deep_analysis"])
        self.assertTrue(result["is_correct"])
        self.assertEqual(result["corrected_text"], text)
        self.assertEqual(result["model_name"], "mock-llm")

    def test_mixed_questions_and_requests_reach_llm_with_original_type(self):
        for text, primary_type in (
            ("すみません、学校へ行きますか", "question"),
            ("こんにちは。どこへ行きますか？", "question"),
            ("すみません、学校へ行ってください。", "request"),
            ("ありがとうございます。確認をお願いします。", "request"),
        ):
            with self.subTest(text=text):
                self.reset_calls()
                self.mock_llm_response(text, [])

                result = pipeline.analyze(text)

                self.assert_retrieved_entire_text(text, primary_type)
                self.assertEqual(result["primary_type"], primary_type)
                self.assertTrue(result["needs_deep_analysis"])
                self.assertEqual(result["corrected_text"], text)
                self.assertEqual(result["model_name"], "mock-llm")


if __name__ == "__main__":
    unittest.main()
