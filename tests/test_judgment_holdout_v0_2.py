"""The second holdout is sealed before any v0.2-D model run."""

import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from evaluation.judgment.build_holdout_v0_2 import DATA, MANIFEST, build
from evaluation.judgment.dataset import load_records, validate_records


ROOT = Path(__file__).resolve().parents[1]


class JudgmentHoldoutV02Tests(unittest.TestCase):
    def test_distribution_hash_and_review_status(self):
        rows = load_records(DATA)
        validate_records(rows)
        manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        self.assertEqual(len(rows), 120)
        self.assertEqual(len({row["id"] for row in rows}), 120)
        self.assertEqual({row["split"] for row in rows}, {"holdout_eval"})
        self.assertEqual({row["review"]["status"] for row in rows}, {"generated_validated"})
        self.assertEqual({row["review"]["reviewed_at"] for row in rows}, {None})
        self.assertEqual(manifest["decisions"], {
            "acceptable": 50, "insufficient_evidence": 20, "needs_correction": 50,
        })
        self.assertEqual(manifest["compound_error_cases"], 10)
        self.assertFalse(manifest["human_reviewed"])
        self.assertFalse(manifest["expert_reviewed"])
        self.assertEqual(manifest["contamination_audit"]["exact_normalized_matches"], 0)
        self.assertEqual(manifest["contamination_audit"]["near_dataset_matches_at_or_above_0_85"], 0)
        self.assertLess(manifest["contamination_audit"]["max_dataset_character_3gram_jaccard"], 0.85)
        self.assertEqual(hashlib.sha256(DATA.read_bytes()).hexdigest(), manifest["sha256"])
        old_ids = {row["id"] for row in load_records(ROOT / "evaluation/judgment/holdout_v0.1.jsonl")}
        self.assertFalse(old_ids.intersection(row["id"] for row in rows))

    def test_reproducible_without_model_predictions(self):
        with tempfile.TemporaryDirectory() as directory:
            data, manifest = Path(directory) / "holdout.jsonl", Path(directory) / "manifest.json"
            build(data, manifest)
            self.assertEqual(data.read_bytes(), DATA.read_bytes())
            self.assertEqual(manifest.read_bytes(), MANIFEST.read_bytes())


if __name__ == "__main__":
    unittest.main()
