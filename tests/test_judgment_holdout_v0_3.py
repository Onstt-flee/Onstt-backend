"""Protect the sealed v0.3 holdout before v0.2-F training."""

import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from evaluation.judgment.build_holdout_v0_3 import DATA, MANIFEST, build, build_records


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class JudgmentHoldoutV03Tests(unittest.TestCase):
    def test_distribution_and_unique_ids(self):
        rows = build_records()
        self.assertEqual(len(rows), 120)
        self.assertEqual(len({row["id"] for row in rows}), 120)
        decisions = [row["expected"]["decision"] for row in rows]
        self.assertEqual(decisions.count("acceptable"), 50)
        self.assertEqual(decisions.count("needs_correction"), 50)
        self.assertEqual(decisions.count("insufficient_evidence"), 20)

    def test_checked_in_artifacts_are_deterministic(self):
        manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        self.assertEqual(sha256(DATA), manifest["sha256"])
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            generated = build(base / "holdout.jsonl", base / "manifest.json")
            self.assertEqual(sha256(base / "holdout.jsonl"), manifest["sha256"])
            self.assertEqual(generated["decisions"], manifest["decisions"])
            self.assertEqual(generated["contamination_audit"]["exact_normalized_matches"], 0)
            self.assertEqual(generated["contamination_audit"]["near_dataset_matches_at_or_above_0_85"], 0)


if __name__ == "__main__":
    unittest.main()
