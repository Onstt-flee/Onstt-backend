import unittest

from analyzer.feedback_particle_risk_gate import assess_candidate, detect_particle_risks
from evaluation.feedback.evaluate_particle_risk_gate import evaluate


def judgment(decision="acceptable", text="", errors=None):
    return {"decision": decision, "corrected_text": text, "error_types": errors or [], "reason_ko": "근거"}


class FeedbackParticleRiskGateTests(unittest.TestCase):
    def test_repeated_failure_patterns_emit_review_only_signals(self):
        existence = detect_particle_risks("夕刻は配電室で変圧器があります。")
        animate = detect_particle_risks("昼前は配電室で電気係がいます。")
        destination = detect_particle_risks("今度は動物保護所を行きます。")
        self.assertEqual([item.code for item in existence], ["existence_location_de_risk"])
        self.assertEqual([item.code for item in animate], ["existence_location_de_risk"])
        self.assertEqual([item.code for item in destination], ["destination_wo_iku_risk"])
        self.assertTrue(all(item.action == "secondary_review_only" for item in existence + animate + destination))

    def test_ambiguous_occurrence_and_route_patterns_fail_open(self):
        for text in (
            "会場でイベントがあります。", "講堂で説明会があります。",
            "この道を行きます。", "長い廊下を行きました。", "人生を行く。",
        ):
            self.assertEqual(detect_particle_risks(text), (), text)

    def test_safe_controls_do_not_signal(self):
        for text in (
            "配電室に変圧器があります。", "配電室に電気係がいます。",
            "配電室で変圧器を点検します。", "動物保護所に行きます。",
        ):
            self.assertEqual(detect_particle_risks(text), (), text)

    def test_assessment_never_mutates_candidate(self):
        text = "夕刻は配電室で変圧器があります。"
        candidate = judgment(text=text)
        before = dict(candidate)
        assessed = assess_candidate(text, candidate)
        self.assertEqual(candidate, before)
        self.assertEqual(assessed["status"], "review_required")
        self.assertFalse(assessed["mutates_judgment"])
        corrected = judgment("needs_correction", "夕刻は配電室に変圧器があります。", ["particle_misuse"])
        self.assertEqual(assess_candidate(text, corrected)["status"], "acknowledged")

    def test_retrospective_summary_contains_counts_not_content(self):
        gold = [{
            "id": "x", "text": "倉庫で台車があります。",
            "expected": {"verdict": "disagree", "recommended_judgment": {
                "decision": "needs_correction", "corrected_text": "倉庫に台車があります。",
                "error_types": ["particle_misuse"], "reason_ko": "근거",
            }},
        }]
        result = [{"id": "x", "parsed": {"verdict": "agree", "recommended_judgment": None}}]
        summary = evaluate(gold, result)
        self.assertEqual(summary["risk_coverage"], 1)
        self.assertEqual(summary["non_risk_signals"], 0)
        self.assertEqual(summary["covered_model_target_failures"], 1)
        self.assertNotIn("text", summary)


if __name__ == "__main__":
    unittest.main()
