import json
from pathlib import Path
import tempfile
import unittest

from evaluation.feedback.build_synthetic_shadow_v0_1 import build
from scripts.run_feedback_synthetic_shadow import load_inputs, percentile


class FeedbackSyntheticShadowTests(unittest.TestCase):
    def test_generator_creates_200_label_free_unique_inputs(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "inputs.jsonl"
            manifest_path = Path(directory) / "manifest.json"
            manifest = build(output, manifest_path)
            rows = load_inputs(output)
        self.assertEqual(len(rows), 200)
        self.assertEqual(len({row["id"] for row in rows}), 200)
        self.assertEqual(manifest["stratum_counts"], {
            "acceptable_like": 80,
            "correction_like": 80,
            "insufficient_like": 20,
            "boundary_like": 20,
        })
        self.assertFalse(manifest["quality_claim_allowed"])
        for row in rows:
            self.assertEqual(set(row["input"]), {"text", "context", "learner_level"})
            self.assertNotIn("expected", json.dumps(row, ensure_ascii=False))

    def test_percentile_uses_nearest_rank(self):
        self.assertEqual(percentile([1.0, 2.0, 3.0, 4.0], 0.95), 4.0)
        self.assertIsNone(percentile([], 0.95))


if __name__ == "__main__":
    unittest.main()
