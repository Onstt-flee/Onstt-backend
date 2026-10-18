import json
from pathlib import Path
import subprocess
import tempfile
import unittest

from evaluation.feedback.compare_runs import compare


ROOT = Path(__file__).resolve().parents[1]


class FeedbackBaselineLoraComparisonTests(unittest.TestCase):
    def test_compare_tracks_improvements_and_regressions(self):
        gold = [
            {"id": "a", "expected": {"verdict": "agree", "recommended_judgment": None}},
            {"id": "b", "expected": {"verdict": "agree", "recommended_judgment": None}},
        ]
        valid = {"contract_success": True, "parsed": {"verdict": "agree", "recommended_judgment": None}, "latency_ms": 10}
        invalid = {"contract_success": False, "parsed": None, "latency_ms": 20}
        result = compare(gold, [{"id": "a", **valid}, {"id": "b", **invalid}],
                         [{"id": "a", **invalid}, {"id": "b", **valid}])
        self.assertEqual(result["core_match"]["improved_count"], 1)
        self.assertEqual(result["core_match"]["regressed_ids"], ["a"])

    def test_recorded_v04_comparison_is_internal_and_lora_improves_baseline(self):
        result = json.loads((ROOT / "evaluation/feedback/holdout_v0.4.baseline-lora.result.json").read_text(encoding="utf-8"))
        self.assertEqual(result["comparison_scope"], "retrospective_internal_generated_validation")
        self.assertEqual(result["dataset_sha256"], "c22c5ddb0153c60d7087ef1e26580e669ea974e2bdafb0e65142f9eaeed60802")
        self.assertEqual(result["base_metrics"]["records"], 120)
        self.assertEqual(result["lora_metrics"]["records"], 120)
        self.assertGreater(result["lora_metrics"]["contract_success_rate"], result["base_metrics"]["contract_success_rate"])
        self.assertGreater(result["lora_metrics"]["disagreement_recall"], result["base_metrics"]["disagreement_recall"])
        self.assertLess(result["lora_metrics"]["p95_latency_seconds"], result["base_metrics"]["p95_latency_seconds"])
        self.assertEqual(result["core_match"]["baseline"], 34)
        self.assertEqual(result["core_match"]["lora"], 112)
        self.assertEqual(result["core_match"]["regressed_ids"], ["FVH-04-069"])

    def test_cli_can_mark_a_preplanned_comparison_as_prospective(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            gold = root / "gold.jsonl"
            baseline = root / "baseline.jsonl"
            lora = root / "lora.jsonl"
            output = root / "result.json"
            gold.write_text('{"id":"a","expected":{"verdict":"agree","recommended_judgment":null}}\n', encoding="utf-8")
            row = '{"id":"a","contract_success":true,"parsed":{"verdict":"agree","recommended_judgment":null},"latency_ms":1}\n'
            baseline.write_text(row, encoding="utf-8")
            lora.write_text(row, encoding="utf-8")
            subprocess.run(
                [
                    str(ROOT / "venv/bin/python"), "-m", "evaluation.feedback.compare_runs",
                    "--gold", str(gold), "--baseline", str(baseline), "--lora", str(lora),
                    "--output", str(output), "--prospective",
                ],
                cwd=ROOT,
                check=True,
            )
            result = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(result["comparison_scope"], "prospective_internal_generated_validation")
            self.assertIn("사전 계획", result["limitations"][1])


if __name__ == "__main__":
    unittest.main()
