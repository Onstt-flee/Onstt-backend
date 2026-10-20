import unittest

from evaluation.feedback.two_stage_scorer import evaluate_thresholds, score


def gold(item_id, verdict, stage2=None):
    return {"id": item_id, "expected_stage1": {"verdict": verdict}, "expected_stage2": stage2}


def result(item_id, verdict, *, called=False, stage2=None, latency=100):
    return {
        "id": item_id,
        "stage1_contract_success": True,
        "stage1_parsed": {"verdict": verdict},
        "stage2_called": called,
        "stage2_contract_success": stage2 is not None if called else None,
        "stage2_parsed": stage2,
        "total_latency_ms": latency,
    }


class FeedbackTwoStageScorerTests(unittest.TestCase):
    def test_perfect_two_stage_run_scores_one(self):
        recommendation = {"decision": "needs_correction", "corrected_text": "正しい。"}
        metrics = score(
            [gold("a", "agree"), gold("b", "disagree", recommendation), gold("c", "unreviewable")],
            [result("a", "agree"), result("b", "disagree", called=True, stage2=recommendation, latency=200), result("c", "unreviewable")],
        )
        for name in (
            "stage1_contract_success_rate", "disagreement_precision", "disagreement_recall",
            "unreviewable_accuracy", "stage2_call_discipline_rate", "stage2_contract_success_rate",
            "recommended_decision_accuracy", "accepted_correction_rate",
        ):
            self.assertEqual(metrics[name], 1.0, name)
        self.assertEqual(metrics["false_disagreement_rate"], 0.0)

    def test_missed_disagreement_reduces_recall_and_recommendation(self):
        recommendation = {"decision": "needs_correction", "corrected_text": "正しい。"}
        metrics = score([gold("a", "disagree", recommendation)], [result("a", "agree")])
        self.assertEqual(metrics["disagreement_recall"], 0.0)
        self.assertEqual(metrics["recommended_decision_accuracy"], 0.0)
        self.assertEqual(metrics["accepted_correction_rate"], 0.0)
        self.assertEqual(metrics["stage2_call_discipline_rate"], 1.0)

    def test_call_discipline_and_id_sets_fail_closed(self):
        metrics = score([gold("a", "agree")], [result("a", "agree", called=True)])
        self.assertEqual(metrics["stage2_call_discipline_rate"], 0.0)
        with self.assertRaisesRegex(ValueError, "ids differ"):
            score([gold("a", "agree")], [result("b", "agree")])

    def test_threshold_evaluation_reports_failures(self):
        metrics = {
            "stage1_contract_success_rate": 1.0, "false_disagreement_rate": 0.0,
            "disagreement_precision": 1.0, "disagreement_recall": 0.5,
            "unreviewable_accuracy": 1.0, "stage2_call_discipline_rate": 1.0,
            "stage2_contract_success_rate": 1.0, "recommended_decision_accuracy": 0.5,
            "accepted_correction_rate": 1.0, "conditional_total_p95_seconds": 1.0,
        }
        thresholds = {
            "stage1_contract_success_rate_min": .99, "false_disagreement_rate_max": .02,
            "disagreement_precision_min": .95, "disagreement_recall_min": .8,
            "unreviewable_accuracy_min": .9, "stage2_call_discipline_rate_min": 1.0,
            "stage2_contract_success_rate_min": .99, "recommended_decision_accuracy_min": .9,
            "accepted_correction_rate_min": .8, "conditional_total_p95_seconds_max": 10.0,
        }
        decision = evaluate_thresholds(metrics, thresholds)
        self.assertFalse(decision["passed"])
        self.assertEqual(decision["failed_thresholds"], ["disagreement_recall", "recommended_decision_accuracy"])


if __name__ == "__main__":
    unittest.main()
