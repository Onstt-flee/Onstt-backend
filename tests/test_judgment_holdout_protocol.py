"""Validate the immutable v0.2 holdout execution protocol."""

import hashlib
import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
PROTOCOL = ROOT / "evaluation/judgment/holdout_v0.2.protocol.json"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class JudgmentHoldoutProtocolTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.protocol = json.loads(PROTOCOL.read_text(encoding="utf-8"))

    def test_sealed_holdout_matches_protocol(self):
        holdout = self.protocol["holdout"]
        self.assertEqual(sha256(ROOT / holdout["path"]), holdout["sha256"])
        self.assertEqual(sum(holdout["distribution"].values()), holdout["count"])

    def test_repository_inputs_match_protocol(self):
        expected = {
            "evaluation/judgment/runner.py": self.protocol["evaluation"]["runner_sha256"],
            "evaluation/judgment/scorer.py": self.protocol["evaluation"]["scorer_sha256"],
            "evaluation/judgment/candidate_selector.py": self.protocol["evaluation"]["selector_sha256"],
            "training/judgment/data/pilot_v0.2_d.jsonl": self.protocol["primary"]["dataset_sha256"],
            "training/judgment/data/pilot_v0.2_e.jsonl": self.protocol["secondary"]["dataset_sha256"],
            "training/judgment/configs/qwen3_4b_failure_focus_v0.2_d.json": self.protocol["primary"]["config_sha256"],
            "training/judgment/configs/qwen3_4b_failure_focus_v0.2_e.json": self.protocol["secondary"]["config_sha256"],
        }
        for relative, digest in expected.items():
            with self.subTest(path=relative):
                self.assertEqual(sha256(ROOT / relative), digest)

    def test_thresholds_are_frozen(self):
        thresholds = self.protocol["thresholds"]
        self.assertEqual(thresholds["contract_success_min"], {"numerator": 119, "denominator": 120})
        self.assertEqual(thresholds["overcorrection_max"], {"numerator": 1, "denominator": 50})
        self.assertEqual(thresholds["gate_accepted_correction_gain_min"], 3)
        self.assertEqual(thresholds["gate_p95_latency_ms_max"], 5000)
        self.assertEqual(thresholds["gate_p95_to_primary_ratio_max"], 2.0)


if __name__ == "__main__":
    unittest.main()
