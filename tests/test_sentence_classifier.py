"""Regression checks for the standalone-greeting analysis shortcut."""

import unittest

from analyzer.sentence_classifier import classify_sentence


STANDALONE_GREETINGS = (
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
    "ありがとう\u3000ございました",
    "すみません\tでした",
    "どうも\u3000ありがとう ございます",
)


class SentenceClassifierTests(unittest.TestCase):
    def assert_deep_analysis(self, text, expected_type=None):
        result = classify_sentence(text)

        self.assertNotEqual(result["primary_type"], "greeting")
        self.assertNotIn(
            "greeting", [item["type"] for item in result["candidate_types"]]
        )
        self.assertTrue(result["needs_deep_analysis"])
        if expected_type is not None:
            self.assertEqual(result["primary_type"], expected_type)

    def test_standalone_greetings_skip_deep_analysis(self):
        for greeting in STANDALONE_GREETINGS:
            with self.subTest(greeting=greeting):
                result = classify_sentence(greeting)

                self.assertEqual(result["primary_type"], "greeting")
                self.assertFalse(result["needs_deep_analysis"])

    def test_terminal_punctuation_and_surrounding_whitespace_are_allowed(self):
        for greeting in STANDALONE_GREETINGS:
            for ending in ("。", ".", "．", "！", "!", "？", "?", "！！", " 。 "):
                with self.subTest(greeting=greeting, ending=ending):
                    result = classify_sentence(f" \t\u3000{greeting}{ending}\u3000\n ")

                    self.assertEqual(result["primary_type"], "greeting")
                    self.assertFalse(result["needs_deep_analysis"])

    def test_greetings_with_additional_statements_require_deep_analysis(self):
        for text in (
            "すみません、学校を行きます。",
            "こんにちは。昨日水を食べます。",
            "学校を行きます。ありがとう",
            "彼は「こんにちは」と言いました。",
            "すみません学校を行きます。",
            "学校を行きますありがとう",
            "学校を行きますありがとう明日も行きます。",
            "こんにちは 学校を行きます。",
            "ありがとうございます。学校を行きます。",
            "こんにちは\n学校を行きます。",
            "どうもありがとうございます。学校を行きます。",
            "すみません でした。学校を行きます。",
        ):
            with self.subTest(text=text):
                self.assert_deep_analysis(text, expected_type="statement")

    def test_incorrect_greeting_suffixes_require_deep_analysis(self):
        for text in (
            "こんにちはです。",
            "こんばんはます。",
            "おはようございまし。",
            "はじめましてました。",
            "ありがとうございまし。",
            "ありがとうございますた。",
            "ありがとうございましたない。",
            "すみませんでしたない。",
            "どうもありがとうございますた。",
        ):
            with self.subTest(text=text):
                self.assert_deep_analysis(text, expected_type="statement")

    def test_mixed_questions_and_requests_keep_their_classification(self):
        # These sentences match existing question/request patterns without
        # relying on a separate punctuation-normalization change.
        for text, expected_type in (
            ("すみません、学校へ行きますか", "question"),
            ("こんにちは。どこへ行きますか？", "question"),
            ("すみません、学校へ行ってください。", "request"),
            ("ありがとうございます。確認をお願いします。", "request"),
        ):
            with self.subTest(text=text):
                self.assert_deep_analysis(text, expected_type=expected_type)

    def test_other_shortcut_classifications_are_preserved(self):
        invalid = classify_sentence("こんにちは", is_valid=False)
        fragment = classify_sentence("猫")

        self.assertEqual(invalid["primary_type"], "invalid")
        self.assertFalse(invalid["needs_deep_analysis"])
        self.assertEqual(fragment["primary_type"], "fragment")
        self.assertFalse(fragment["needs_deep_analysis"])


if __name__ == "__main__":
    unittest.main()
