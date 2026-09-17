import hashlib
import json
from collections import Counter
from pathlib import Path
import unittest

from training.judgment.build_hard_negatives import (
    DEFAULT_AUGMENTATION,
    DEFAULT_MANIFEST,
    DEFAULT_OUTPUT,
    DEFAULT_SOURCE,
    build_generated,
    controlled_source,
    validate_generated,
)
from training.judgment.data import load_records, summary, validate_records
from training.judgment.train_lora import load_config, validate_inputs


ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "training/judgment/configs/qwen3_4b_hard_negatives_v0.2_b.json"


class JudgmentHardNegativeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = load_records(DEFAULT_SOURCE)
        cls.generated = load_records(DEFAULT_AUGMENTATION)
        cls.combined = load_records(DEFAULT_OUTPUT)
        cls.manifest = json.loads(DEFAULT_MANIFEST.read_text(encoding="utf-8"))

    def test_generated_dataset_is_reproducible_and_controlled(self):
        generated, metadata = build_generated()
        self.assertEqual(generated, self.generated)
        report = validate_generated(generated, metadata)
        self.assertEqual(report["total"], 240)
        self.assertEqual(report["pairs"], 96)
        self.assertEqual(report["near_seed_matches"], 0)
        self.assertEqual(report["exact_seed_rag_matches"], 0)
        self.assertEqual(report["decisions"], {
            "acceptable": 120,
            "insufficient_evidence": 24,
            "needs_correction": 96,
        })
        self.assertEqual(report["splits"], {"pilot_dev": 48, "pilot_train": 192})
        self.assertEqual(Counter(row["input"]["learner_level"] for row in generated), {"N5": 168, "N4": 72})

    def test_combined_dataset_preserves_reviewed_gold_except_reason(self):
        self.assertEqual(self.combined[:300], controlled_source(self.source))
        self.assertEqual(self.combined[300:], self.generated)
        validate_records(self.combined, require_reviewed=True)
        self.assertEqual(summary(self.combined)["decisions"], {
            "acceptable": 256,
            "insufficient_evidence": 69,
            "needs_correction": 215,
        })
        self.assertEqual(summary(self.combined)["splits"], {
            "pilot_dev": 108,
            "pilot_train": 432,
        })

    def test_generated_records_never_claim_human_or_expert_review(self):
        self.assertTrue(all(
            row["review"] == {
                "status": "generated_validated", "reviewed_at": "2026-09-14"
            }
            for row in self.generated
        ))
        self.assertFalse(self.manifest["policy"]["user_review_claimed_for_generated"])
        self.assertFalse(self.manifest["policy"]["expert_review_claimed"])
        self.assertFalse(self.manifest["policy"]["model_generated_gold_used"])

    def test_minimal_pairs_round_trip_and_stay_in_one_family(self):
        metadata = {item["id"]: item for item in self.manifest["generation_metadata"]}
        pairs = {}
        by_id = {row["id"]: row for row in self.generated}
        for item in metadata.values():
            if item["pair_id"]:
                pairs.setdefault(item["pair_id"], []).append(by_id[item["id"]])
        self.assertEqual(len(pairs), 96)
        for pair in pairs.values():
            normal = next(row for row in pair if row["expected"]["decision"] == "acceptable")
            error = next(row for row in pair if row["expected"]["decision"] == "needs_correction")
            self.assertEqual(error["expected"]["corrected_text"], normal["input"]["text"])
            self.assertEqual(error["split"], normal["split"])
            self.assertEqual(error["template_family_id"], normal["template_family_id"])
            self.assertEqual(error["input"]["context"], normal["input"]["context"])
            self.assertEqual(len(error["expected"]["edits"]), 1)

    def test_policy_boundaries_preserve_non_grammar_content(self):
        route = [row for row in self.generated if "route_o" in row["template_family_id"]]
        self.assertTrue(route)
        self.assertTrue(all("통과한 경로" in row["input"]["context"] for row in route))

        stt = [row for row in self.generated if "stt_orthography" in row["template_family_id"]]
        self.assertEqual(len(stt), 24)
        for row in stt:
            self.assertIn("원음이나 대안 전사는 제공되지 않았습니다", row["input"]["context"])
            if row["expected"]["decision"] == "needs_correction":
                self.assertTrue("わ" in row["expected"]["corrected_text"])
                self.assertTrue("お" in row["expected"]["corrected_text"])

        style = [row for row in self.generated if "style_advisory" in row["template_family_id"]]
        self.assertEqual(len(style), 24)
        normals = [row for row in style if row["expected"]["decision"] == "acceptable"]
        self.assertTrue(all("ました" in row["input"]["text"] and "た。" in row["input"]["text"] for row in normals))

    def test_manifest_hashes_and_training_config_match(self):
        self.assertEqual(
            self.manifest["augmentation_sha256"],
            hashlib.sha256(DEFAULT_AUGMENTATION.read_bytes()).hexdigest(),
        )
        self.assertEqual(
            self.manifest["combined_sha256"],
            hashlib.sha256(DEFAULT_OUTPUT.read_bytes()).hexdigest(),
        )
        report = validate_inputs(load_config(CONFIG))
        self.assertEqual(report["train_count"], 432)
        self.assertEqual(report["eval_count"], 108)
        self.assertEqual(load_config(CONFIG)["max_steps"], 45)
        self.assertEqual(
            report["source_review_statuses"],
            ["generated_validated", "user_reviewed"],
        )


if __name__ == "__main__":
    unittest.main()
