"""Validate the frozen v0.3 D/F holdout execution protocol."""

import hashlib
import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
PROTOCOL = ROOT / "evaluation/judgment/holdout_v0.3.protocol.json"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class JudgmentHoldoutV03ProtocolTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.protocol = json.loads(PROTOCOL.read_text(encoding="utf-8"))

    def test_holdout_and_manifest_match_protocol(self):
        holdout = self.protocol["holdout"]
        self.assertEqual(sha256(ROOT / holdout["path"]), holdout["sha256"])
        self.assertEqual(sha256(ROOT / holdout["manifest_path"]), holdout["manifest_sha256"])
        manifest = json.loads((ROOT / holdout["manifest_path"]).read_text(encoding="utf-8"))
        self.assertEqual(manifest["sha256"], holdout["sha256"])
        self.assertEqual(manifest["records"], holdout["records"])
        self.assertEqual(sum(manifest["decisions"].values()), holdout["records"])
        self.assertTrue(holdout["single_use"])

    def test_repository_inputs_match_protocol(self):
        protocol = self.protocol
        expected = {
            protocol["primary"]["dataset_path"]: protocol["primary"]["dataset_sha256"],
            protocol["primary"]["config_path"]: protocol["primary"]["config_sha256"],
            protocol["secondary"]["dataset_path"]: protocol["secondary"]["dataset_sha256"],
            protocol["secondary"]["config_path"]: protocol["secondary"]["config_sha256"],
            "evaluation/judgment/runner.py": protocol["inference"]["runner_sha256"],
            "evaluation/judgment/scorer.py": protocol["inference"]["scorer_sha256"],
            "evaluation/judgment/candidate_selector.py": protocol["selector"]["core_sha256"],
            "evaluation/judgment/candidate_selector_v0_2.py": protocol["selector"]["wrapper_sha256"],
        }
        for relative, digest in expected.items():
            with self.subTest(path=relative):
                self.assertEqual(sha256(ROOT / relative), digest)

    def test_external_model_inputs_match_protocol(self):
        protocol = self.protocol
        base_manifest = Path(protocol["base_model"]["path"]) / "MODEL_MANIFEST.json"
        self.assertEqual(sha256(base_manifest), protocol["base_model"]["manifest_sha256"])
        for role in ("primary", "secondary"):
            adapter = Path(protocol[role]["adapter_path"]) / "adapter_model.safetensors"
            with self.subTest(role=role):
                self.assertEqual(sha256(adapter), protocol[role]["adapter_sha256"])

    def test_thresholds_and_execution_policy_are_frozen(self):
        protocol = self.protocol
        safety = protocol["safety_thresholds"]
        gate = protocol["gate_adoption_thresholds"]
        policy = protocol["execution_policy"]
        self.assertEqual(safety["json_contract_success_rate_min"], 0.99)
        self.assertEqual(safety["overcorrection_max_count_among_50_acceptable"], 1)
        self.assertEqual(safety["correction_detection_precision_min"], 0.95)
        self.assertEqual(safety["correction_detection_recall_min"], 0.80)
        self.assertEqual(gate["accepted_correction_gain_min_count"], 2)
        self.assertEqual(gate["conditional_gate_p95_ms_max"], 5000)
        self.assertEqual(gate["conditional_gate_p95_to_primary_ratio_max"], 2.0)
        self.assertTrue(policy["run_primary_exactly_once"])
        self.assertTrue(policy["run_secondary_exactly_once"])
        self.assertTrue(policy["no_rule_model_or_threshold_change_after_results"])
        self.assertEqual(protocol["status"], "frozen_before_inference")


if __name__ == "__main__":
    unittest.main()
