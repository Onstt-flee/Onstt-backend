import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from training.judgment.data import exact_overlap, load_records, summary, validate_records
from training.judgment.export_chatml import export
from training.judgment.generate_pilot import RAG_DIR, SEED_DATASET, build_records


ROOT = Path(__file__).resolve().parents[1]
DATASET = ROOT / "training" / "judgment" / "data" / "pilot_v0.1.jsonl"
MANIFEST = ROOT / "training" / "judgment" / "data" / "pilot_v0.1.manifest.json"


class JudgmentTrainingDataTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.records = load_records(DATASET)

    def test_pilot_distribution_and_contract(self):
        validate_records(self.records)
        report = summary(self.records)
        self.assertEqual(report["total"], 300)
        self.assertEqual(report["splits"], {"pilot_dev": 60, "pilot_train": 240})
        self.assertEqual(report["decisions"], {
            "acceptable": 135,
            "insufficient_evidence": 45,
            "needs_correction": 120,
        })
        self.assertEqual(report["levels"], {"N4": 90, "N5": 210})
        self.assertEqual(report["review_status"], {"provisional": 300})
        self.assertEqual(report["compound_corrections"], 18)

    def test_single_error_types_have_seventeen_examples_each(self):
        counts = {error_type: 0 for error_type in (
            "particle_misuse", "verb_conjugation", "adjective_conjugation",
            "copula_conjugation", "modifier_connection", "tense_mismatch",
        )}
        for row in self.records:
            edits = row["expected"]["edits"]
            if len(edits) == 1:
                counts[edits[0]["error_type"]] += 1
        self.assertEqual(set(counts.values()), {17})

    def test_template_families_do_not_cross_splits(self):
        family_splits = {}
        for row in self.records:
            family_splits.setdefault(row["template_family_id"], set()).add(row["split"])
        self.assertTrue(all(len(splits) == 1 for splits in family_splits.values()))

    def test_validator_rejects_family_leakage(self):
        records = copy.deepcopy(self.records)
        family = records[0]["template_family_id"]
        member = next(row for row in records[1:] if row["template_family_id"] == family)
        member["split"] = "pilot_dev" if member["split"] == "pilot_train" else "pilot_train"
        with self.assertRaisesRegex(ValueError, "Template families cross splits"):
            validate_records(records)

    def test_no_exact_seed_or_rag_overlap(self):
        self.assertEqual(
            exact_overlap(self.records, seed_path=SEED_DATASET, rag_dir=RAG_DIR)["matches"],
            [],
        )

    def test_generator_is_deterministic(self):
        self.assertEqual(build_records(), build_records())

    def test_manifest_matches_dataset(self):
        manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        self.assertEqual(manifest["summary"], summary(self.records))
        self.assertEqual(
            manifest["dataset_sha256"], hashlib.sha256(DATASET.read_bytes()).hexdigest(),
        )
        self.assertEqual(manifest["exact_seed_rag_overlap"]["matches"], [])

    def test_chatml_requires_review_by_default_and_hides_metadata(self):
        with tempfile.TemporaryDirectory() as directory:
            output_dir = Path(directory)
            with self.assertRaisesRegex(ValueError, "not reviewed"):
                export(DATASET, output_dir)
            result = export(DATASET, output_dir, allow_provisional=True)
            self.assertEqual(sum(item["count"] for item in result.values()), 300)
            for item in result.values():
                with Path(item["path"]).open(encoding="utf-8") as stream:
                    for line in stream:
                        sample = json.loads(line)
                        self.assertEqual(set(sample), {"messages"})
                        self.assertEqual([message["role"] for message in sample["messages"]], ["system", "user", "assistant"])
                        user_input = json.loads(sample["messages"][1]["content"])
                        self.assertEqual(set(user_input), {"text", "context", "learner_level"})
                        self.assertNotIn("JT-", sample["messages"][1]["content"])


if __name__ == "__main__":
    unittest.main()
