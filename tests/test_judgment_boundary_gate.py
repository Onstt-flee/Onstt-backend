"""Tests for the offline deterministic judgment boundary policy."""

import unittest

from evaluation.judgment.boundary_gate import (
    POLICY_VERSION,
    apply_boundary_policy,
    assess_boundary,
    detect_orthography_advisories,
)


class JudgmentBoundaryGateTests(unittest.TestCase):
    def test_empty_noise_and_punctuation_bypass_without_model(self):
        for text in ("", "   ", "……", "［雑音］", "[noise]", "！？"):
            with self.subTest(text=text):
                result = assess_boundary(text, None)
                self.assertEqual(result["route"], "deterministic")
                self.assertFalse(result["model_call_required"])
                self.assertEqual(
                    result["judgment"]["decision"], "insufficient_evidence"
                )
                self.assertEqual(result["judgment"]["corrected_text"], text)
                self.assertEqual(result["policy_version"], POLICY_VERSION)

        self.assertEqual(assess_boundary("あの、ええと……", None)["route"], "model")

    def test_clear_foreign_language_bypasses_but_ambiguous_text_does_not(self):
        for text in (
            "I went to the station yesterday.",
            "내일 학교에 갑니다.",
            "Bonjour tout le monde.",
        ):
            with self.subTest(text=text):
                result = assess_boundary(text, None)
                self.assertEqual(result["boundary_type"], "out_of_scope_language")
                self.assertEqual(
                    result["judgment"]["decision"], "insufficient_evidence"
                )
                self.assertEqual(result["judgment"]["corrected_text"], text)

        for text in ("AIを勉強します。", "京都", "寿司 is delicious"):
            with self.subTest(text=text):
                self.assertEqual(assess_boundary(text, None)["route"], "model")

    def test_stt_orthography_is_advisory_only(self):
        context = "STT가 생성한 전사 텍스트이며 원음은 없습니다."
        first = detect_orthography_advisories("わたしわ大学生です。", context)
        self.assertEqual(len(first), 1)
        self.assertEqual(first[0]["candidate_text"], "わたしは大学生です。")
        self.assertEqual(first[0]["attribution"], "unknown")
        self.assertEqual(first[0]["action"], "advisory_only")

        second = detect_orthography_advisories("本お読みます。", context)
        self.assertEqual(len(second), 1)
        self.assertEqual(second[0]["candidate_text"], "本を読みます。")

        self.assertEqual(
            detect_orthography_advisories("本お読みます。", None), []
        )
        self.assertEqual(
            detect_orthography_advisories(
                "本をお読みになります。", context
            ),
            [],
        )

    def test_exact_orthography_change_is_separated_from_grammar(self):
        context = "음성 인식 전사이며 원음은 제공되지 않았습니다."
        model = {
            "decision": "needs_correction",
            "corrected_text": "本を読みます。",
            "error_types": ["particle_misuse"],
            "edits": [{
                "start": 1,
                "end": 2,
                "source": "お",
                "replacement": "を",
                "error_type": "particle_misuse",
            }],
            "reason_ko": "조사를 고칩니다.",
            "classification_review_required": False,
        }
        result = apply_boundary_policy("本お読みます。", context, model)
        self.assertTrue(result["model_output_overridden"])
        self.assertEqual(result["judgment"]["decision"], "acceptable")
        self.assertEqual(result["judgment"]["corrected_text"], "本お読みます。")
        self.assertEqual(result["judgment"]["edits"], [])
        self.assertEqual(result["advisories"][0]["candidate_text"], "本を読みます。")

    def test_unrelated_model_correction_is_not_overridden(self):
        context = "STT 전사 텍스트입니다."
        model = {
            "decision": "needs_correction",
            "corrected_text": "本お読みました。",
            "error_types": ["tense_mismatch"],
            "edits": [],
            "reason_ko": "시제를 고칩니다.",
            "classification_review_required": False,
        }
        result = apply_boundary_policy("本お読みます。", context, model)
        self.assertFalse(result["model_output_overridden"])
        self.assertEqual(result["judgment"], model)

    def test_deterministic_route_ignores_model_output_and_preserves_literal(self):
        model = {
            "decision": "acceptable",
            "corrected_text": "내일 학교에 갑니다.",
            "error_types": [],
            "edits": [],
            "reason_ko": "허용",
            "classification_review_required": False,
        }
        result = apply_boundary_policy(
            "내일 학교에 갑니다.", None, model
        )
        self.assertTrue(result["model_output_overridden"])
        self.assertEqual(result["judgment"]["decision"], "insufficient_evidence")
        self.assertEqual(result["judgment"]["corrected_text"], "내일 학교에 갑니다.")


if __name__ == "__main__":
    unittest.main()
