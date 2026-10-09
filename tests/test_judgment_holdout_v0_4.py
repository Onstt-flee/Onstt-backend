"""Protect the sealed v0.4 holdout before v0.2-H experimentation."""

from collections import Counter
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from evaluation.judgment.build_holdout_v0_4 import DATA, MANIFEST, build, build_records


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class JudgmentHoldoutV04Tests(unittest.TestCase):
    def test_distribution_boundaries_and_unique_ids(self):
        rows = build_records()
        self.assertEqual(len(rows), 120)
        self.assertEqual(len({row["id"] for row in rows}), 120)
        decisions = Counter(row["expected"]["decision"] for row in rows)
        self.assertEqual(decisions, {
            "acceptable": 50, "needs_correction": 50, "insufficient_evidence": 20,
        })
        self.assertEqual(sum(len(row["expected"]["edits"]) > 1 for row in rows), 10)
        for row in rows:
            if row["expected"]["decision"] != "needs_correction":
                self.assertEqual(row["input"]["text"], row["expected"]["corrected_text"])
                self.assertEqual(row["expected"]["edits"], [])

    def test_checked_in_artifacts_are_deterministic_and_unconsumed(self):
        manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        self.assertEqual(sha256(DATA), manifest["sha256"])
        self.assertEqual(manifest["execution_policy"]["model_inference_count_before_protocol_freeze"], 0)
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            generated = build(base / "holdout.jsonl", base / "manifest.json")
            self.assertEqual(sha256(base / "holdout.jsonl"), manifest["sha256"])
            self.assertEqual(generated["decisions"], manifest["decisions"])
            self.assertEqual(generated["contamination_audit"]["exact_normalized_matches"], 0)
            self.assertEqual(generated["contamination_audit"]["near_dataset_matches_at_or_above_0_85"], 0)

            self.assertLess(generated["contamination_audit"]["max_dataset_character_3gram_jaccard"], 0.85)
            self.assertIsNotNone(generated["contamination_audit"]["max_dataset_character_3gram_pair"])

if __name__ == "__main__":
    unittest.main()
