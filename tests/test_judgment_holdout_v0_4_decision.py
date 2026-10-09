"""Tests for the frozen holdout v0.4 candidate decision."""

import copy
import json
from pathlib import Path
import unittest

from evaluation.judgment.decide_holdout_v0_4 import decide

ROOT = Path(__file__).resolve().parents[1]
PROTOCOL = json.loads((ROOT / "evaluation/judgment/holdout_v0.4.protocol.json").read_text())
REPORT = json.loads((ROOT / "evaluation/judgment/results/qwen3-4b-v02d-vs-v02f-holdout-v04.json").read_text())


class HoldoutV04DecisionTests(unittest.TestCase):
    def test_observed_result_selects_none(self):
        result = decide(PROTOCOL, REPORT)
        self.assertFalse(result["candidates"]["d"]["eligible"])
        self.assertFalse(result["candidates"]["f"]["eligible"])
        self.assertFalse(result["candidates"]["d"]["eligibility_checks"]["accepted_correction_rate"])
        self.assertFalse(result["candidates"]["f"]["eligibility_checks"]["accepted_correction_rate"])
        self.assertIsNone(result["selected_candidate"])
        self.assertEqual(result["selection_decision"], "neither_candidate_eligible")

    def test_only_f_eligible_selects_f(self):
        report = copy.deepcopy(REPORT)
        d, f = report["runs"]
        d["metrics"]["accepted_correction_rate_end_to_end"]["value"] = 0.79
        f["metrics"]["accepted_correction_rate_end_to_end"]["value"] = 0.80
        result = decide(PROTOCOL, report)
        self.assertFalse(result["candidates"]["d"]["eligible"])
        self.assertTrue(result["candidates"]["f"]["eligible"])
        self.assertEqual(result["selected_candidate"], "judgment-v02f")

    def test_both_eligible_but_f_regression_keeps_d(self):
        report = copy.deepcopy(REPORT)
        for run in report["runs"]:
            run["metrics"]["accepted_correction_rate_end_to_end"]["value"] = 0.80
            run["metrics"]["accepted_correction_rate_end_to_end"]["numerator"] = 40
        result = decide(PROTOCOL, report)
        self.assertTrue(result["candidates"]["d"]["eligible"])
        self.assertTrue(result["candidates"]["f"]["eligible"])
        self.assertEqual(result["selected_candidate"], "judgment-v02d")


if __name__ == "__main__":
    unittest.main()
