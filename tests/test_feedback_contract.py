"""Strict feedback-v0.1 contract tests."""

import json
import unittest

from analyzer.feedback_contract import build_request, parse_output


TEXT = "学校を行きます。"
JUDGMENT = {
    "decision": "needs_correction",
    "corrected_text": "学校に行きます。",
    "error_types": ["particle_misuse"],
    "reason_ko": "목적지 조사가 잘못되었습니다.",
}


class FeedbackContractTests(unittest.TestCase):
    def test_request_is_source_blind_and_fixed_generation(self):
        body = build_request({
            "text": TEXT,
            "context": None,
            "learner_level": "N5",
            "judgment": JUDGMENT,
        }, "feedback-qwen3-8b-v01")
        user = json.loads(body["messages"][1]["content"])
        self.assertEqual(set(user), {"text", "context", "learner_level", "judgment"})
        self.assertNotIn("runtime", body["messages"][1]["content"])
        self.assertEqual(body["temperature"], 0.0)

    def test_agree_and_unreviewable_require_empty_details(self):
        for verdict in ("agree", "unreviewable"):
            parsed, error = parse_output(json.dumps({
                "verdict": verdict,
                "issue_codes": [],
                "recommended_judgment": None,
                "review_reason_ko": "검수 결과입니다.",
            }), TEXT)
            self.assertIsNone(error)
            self.assertEqual(parsed["verdict"], verdict)
        _, error = parse_output(json.dumps({
            "verdict": "agree",
            "issue_codes": ["wrong_correction"],
            "recommended_judgment": None,
            "review_reason_ko": "모순입니다.",
        }), TEXT)
        self.assertIn("must not contain", error)

    def test_disagree_normalizes_backend_edits(self):
        parsed, error = parse_output(json.dumps({
            "verdict": "disagree",
            "issue_codes": ["wrong_correction"],
            "recommended_judgment": {
                "decision": "needs_correction",
                "corrected_text": "学校に行きます。",
                "error_types": ["particle_misuse"],
                "reason_ko": "목적지에는 に를 씁니다.",
            },
            "review_reason_ko": "기존 교정안을 바꿔야 합니다.",
        }, ensure_ascii=False), TEXT)
        self.assertIsNone(error)
        self.assertEqual(parsed["recommended_judgment"]["edits"][0]["source"], "を")
        self.assertEqual(parsed["recommended_judgment"]["edits"][0]["replacement"], "に")

    def test_rejects_extra_duplicate_and_confidence_fields(self):
        base = {
            "verdict": "agree", "issue_codes": [],
            "recommended_judgment": None, "review_reason_ko": "동의합니다.",
            "confidence": 0.9,
        }
        self.assertIn("exactly four", parse_output(json.dumps(base), TEXT)[1])
        raw = '{"verdict":"agree","verdict":"disagree","issue_codes":[],' \
              '"recommended_judgment":null,"review_reason_ko":"x"}'
        self.assertIn("Duplicate JSON key", parse_output(raw, TEXT)[1])

    def test_recommended_non_correction_preserves_original(self):
        _, error = parse_output(json.dumps({
            "verdict": "disagree",
            "issue_codes": ["false_positive"],
            "recommended_judgment": {
                "decision": "acceptable",
                "corrected_text": "学校に行きます。",
                "error_types": [],
                "reason_ko": "정상입니다.",
            },
            "review_reason_ko": "과교정입니다.",
        }, ensure_ascii=False), TEXT)
        self.assertIn("preserve input", error)

    def test_issue_codes_require_semantically_consistent_recommendations(self):
        cases = [
            ("false_negative", "acceptable", TEXT, [], "false_negative requires"),
            ("false_positive", "needs_correction", "学校に行きます。", ["particle_misuse"], "false_positive requires"),
            ("should_abstain", "acceptable", TEXT, [], "should_abstain requires"),
            ("unnecessary_abstention", "insufficient_evidence", TEXT, [], "unnecessary_abstention requires"),
        ]
        for issue, decision, corrected, error_types, expected_error in cases:
            with self.subTest(issue=issue):
                _, error = parse_output(json.dumps({
                    "verdict": "disagree",
                    "issue_codes": [issue],
                    "recommended_judgment": {
                        "decision": decision,
                        "corrected_text": corrected,
                        "error_types": error_types,
                        "reason_ko": "권장 판단입니다.",
                    },
                    "review_reason_ko": "기존 판단과 다릅니다.",
                }, ensure_ascii=False), TEXT)
                self.assertIn(expected_error, error)


if __name__ == "__main__":
    unittest.main()
