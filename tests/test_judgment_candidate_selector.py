"""Test the label-free primary-decision correction candidate gate."""

import unittest

from evaluation.judgment.candidate_selector import (
    _latency_ms, candidate_score, choose_candidate,
)


def judgment(decision: str, corrected: str) -> dict:
    return {
        "decision": decision,
        "corrected_text": corrected,
        "error_types": [] if decision != "needs_correction" else ["verb_conjugation"],
        "reason_ko": "테스트 근거",
    }


class JudgmentCandidateSelectorTests(unittest.TestCase):
    def test_primary_non_correction_decision_is_locked(self):
        source = "今日は駅まで歩いて帰る。"
        primary = judgment("acceptable", source)
        secondary = judgment("needs_correction", "今日は駅まで歩いて帰ります。")
        selected, reason, _ = choose_candidate(source, primary, secondary)
        self.assertIs(selected, primary)
        self.assertEqual(reason, "primary_decision_locked")

    def test_polite_register_beats_plain_candidate(self):
        source = "弟は漢字を読めるます。"
        primary = judgment("needs_correction", "弟は漢字を読める。")
        secondary = judgment("needs_correction", "弟は漢字を読めます。")
        selected, _, _ = choose_candidate(source, primary, secondary)
        self.assertIs(selected, secondary)

    def test_request_intent_is_preserved(self):
        source = "明日は駅で友達に会いてください。"
        primary = judgment("needs_correction", "明日は駅で友達に会ってください。")
        secondary = judgment("needs_correction", "明日は駅で友達に会いましょう。")
        selected, _, _ = choose_candidate(source, primary, secondary)
        self.assertIs(selected, primary)

    def test_remaining_malformed_form_loses(self):
        source = "小さいな犬が庭でいます。"
        primary = judgment("needs_correction", "小さいな犬が庭にいます。")
        secondary = judgment("needs_correction", "小さい犬が庭にいます。")
        self.assertGreater(candidate_score(source, secondary["corrected_text"]),
                           candidate_score(source, primary["corrected_text"]))
        selected, _, _ = choose_candidate(source, primary, secondary)
        self.assertIs(selected, secondary)

    def test_primary_wins_exact_score_tie(self):
        source = "本を読むました。"
        primary = judgment("needs_correction", "本を読みました。")
        secondary = judgment("needs_correction", "本を読みました。")
        selected, reason, _ = choose_candidate(source, primary, secondary)
        self.assertIs(selected, primary)
        self.assertEqual(reason, "primary_tie_or_higher")


    def test_latency_requires_non_negative_number(self):
        row = {"response": {"latency_ms": 12.5}}
        self.assertEqual(_latency_ms(row, label="primary"), 12.5)
        for value in (None, True, -1, "12"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                _latency_ms({"response": {"latency_ms": value}}, label="primary")


if __name__ == "__main__":
    unittest.main()

