import unittest

from evaluation.feedback.scorer import score


def gold(item_id, verdict, recommended=None, source=None):
    row = {
        "id": item_id,
        "expected": {"verdict": verdict, "recommended_judgment": recommended},
    }
    if source:
        row["source_stratum"] = source
    return row


def result(item_id, verdict, recommended=None):
    return {
        "id": item_id,
        "contract_success": True,
        "parsed": {"verdict": verdict, "recommended_judgment": recommended},
        "latency_ms": 100,
    }


class FeedbackScorerTests(unittest.TestCase):
    def test_internal_holdout_does_not_require_source_stratum(self):
        metrics = score(
            [gold("a", "agree"), gold("b", "unreviewable")],
            [result("a", "agree"), result("b", "unreviewable")],
        )
        self.assertIsNone(metrics["source_metric_gap_pp"])
        self.assertEqual(metrics["false_disagreement_rate"], 0.0)

    def test_unreviewable_is_not_a_recommendation_denominator(self):
        expected = {"decision": "acceptable", "corrected_text": "正しい。"}
        metrics = score(
            [gold("a", "disagree", expected), gold("b", "unreviewable")],
            [result("a", "disagree", expected), result("b", "unreviewable")],
        )
        self.assertEqual(metrics["recommended_decision_accuracy"], 1.0)

    def test_false_disagreement_includes_all_non_disagree_gold(self):
        metrics = score(
            [gold("a", "agree"), gold("b", "unreviewable")],
            [result("a", "agree"), result("b", "disagree", {})],
        )
        self.assertEqual(metrics["false_disagreement_rate"], 0.5)

    def test_source_gap_is_reported_when_two_strata_exist(self):
        metrics = score(
            [gold("a", "agree", source="gpu_bf16"),
             gold("b", "agree", source="pi_gguf")],
            [result("a", "agree"), result("b", "disagree", {})],
        )
        self.assertEqual(metrics["source_metric_gap_pp"], 100.0)


if __name__ == "__main__":
    unittest.main()
