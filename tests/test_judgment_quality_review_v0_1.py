"""Tests for the sealed real-STT quality review sample."""

import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from evaluation.judgment.build_quality_review_v0_1 import (
    build_quality_review,
    select_quality_sample,
)
from scripts.run_judgment_shadow import (
    canonical_json,
    input_snapshot_item,
    sha256_bytes,
)


class JudgmentQualityReviewV01Tests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.database = self.root / "source.db"
        connection = sqlite3.connect(self.database)
        connection.executescript(
            """
            CREATE TABLE users (id INTEGER PRIMARY KEY, level TEXT);
            CREATE TABLE sessions (id INTEGER PRIMARY KEY, user_id INTEGER);
            CREATE TABLE utterances (
                id INTEGER PRIMARY KEY, session_id INTEGER, raw_audio_path TEXT,
                audio_path TEXT, stt_text TEXT, processed_text TEXT,
                normalized_text TEXT, language TEXT, stt_model TEXT
            );
            CREATE TABLE judgment_results (id INTEGER PRIMARY KEY);
            INSERT INTO users VALUES (1, 'N5');
            INSERT INTO sessions VALUES (1, 1);
            INSERT INTO utterances VALUES
                (1,1,NULL,NULL,'文一。',NULL,NULL,'ja','model-a'),
                (2,1,NULL,NULL,'文二。',NULL,NULL,'ja','model-a'),
                (3,1,NULL,NULL,'文三。',NULL,NULL,'ja','model-a'),
                (4,1,NULL,NULL,'文四。',NULL,NULL,'ja','model-a'),
                (5,1,NULL,NULL,'文五。',NULL,NULL,'ja','model-b'),
                (6,1,NULL,NULL,'文六。',NULL,NULL,'ja','model-b'),
                (7,1,NULL,NULL,'文七。',NULL,NULL,'ja','model-b'),
                (8,1,NULL,NULL,'文八。',NULL,NULL,'ja','model-b');
            """
        )
        connection.commit()
        connection.close()
        self.prior_raw = self.root / "prior.jsonl"
        prior = {
            "utterance_id": 1,
            "text": "文一。",
            "text_source": "stt_text",
            "learner_level": "N5",
            "stt_model": "model-a",
        }
        self.prior_raw.write_text(canonical_json(prior) + "\n", encoding="utf-8")
        snapshot_sha = sha256_bytes(
            canonical_json([input_snapshot_item(prior)]).encode()
        )
        self.prior_summary = self.root / "prior.json"
        self.prior_summary.write_text(json.dumps({
            "selection": {"selected": 1, "input_snapshot_sha256": snapshot_sha}
        }), encoding="utf-8")

    def tearDown(self):
        self.temporary.cleanup()

    def test_selection_is_deterministic_and_quota_guarded(self):
        rows = [
            {
                "utterance_id": index,
                "text": f"text-{index}",
                "text_source": "stt_text",
                "learner_level": "N5",
                "stt_model": "a" if index < 4 else "b",
            }
            for index in range(1, 7)
        ]
        first = select_quality_sample(rows, {"a": 2, "b": 2}, seed="fixed")
        second = select_quality_sample(list(reversed(rows)), {"a": 2, "b": 2}, seed="fixed")
        self.assertEqual(first, second)
        with self.assertRaisesRegex(ValueError, "Need 4 rows for a"):
            select_quality_sample(rows, {"a": 4})

    def test_build_separates_blind_review_from_private_mapping(self):
        review = self.root / "runs" / "review.jsonl"
        mapping = self.root / "runs" / "mapping.jsonl"
        manifest_path = self.root / "manifest.json"
        database_before = self.database.read_bytes()
        manifest = build_quality_review(
            database_path=self.database,
            prior_runs=[(self.prior_raw, self.prior_summary)],
            review_output=review,
            mapping_output=mapping,
            manifest_output=manifest_path,
            quotas={"model-a": 2, "model-b": 2},
            seed="fixed",
            sealed_at="2026-10-06T00:00:00+00:00",
        )
        self.assertEqual(manifest["sample_size"], 4)
        self.assertEqual(manifest["model_inference_count"], 0)
        self.assertEqual(self.database.read_bytes(), database_before)
        review_rows = [json.loads(line) for line in review.read_text().splitlines()]
        mapping_rows = [json.loads(line) for line in mapping.read_text().splitlines()]
        self.assertEqual(len(review_rows), 4)
        self.assertEqual(len(mapping_rows), 4)
        self.assertTrue(all(row["review_status"] == "pending" for row in review_rows))
        self.assertTrue(all(row["grammar_decision"] is None for row in review_rows))
        self.assertTrue(all(row["audio_review"]["status"] == "unavailable" for row in review_rows))
        private_review = review.read_text()
        self.assertNotIn("utterance_id", private_review)
        self.assertNotIn("stt_model", private_review)
        self.assertNotIn("model_output", private_review)
        self.assertTrue(all("utterance_id" in row for row in mapping_rows))
        self.assertTrue(manifest["database_integrity"]["unchanged"])

    def test_fixed_inputs_reproduce_private_artifact_hashes(self):
        outputs = []
        for suffix in ("a", "b"):
            manifest = build_quality_review(
                database_path=self.database,
                prior_runs=[(self.prior_raw, self.prior_summary)],
                review_output=self.root / suffix / "review.jsonl",
                mapping_output=self.root / suffix / "mapping.jsonl",
                manifest_output=self.root / suffix / "manifest.json",
                quotas={"model-a": 2, "model-b": 2},
                seed="fixed",
                sealed_at="2026-10-06T00:00:00+00:00",
            )
            outputs.append((
                manifest["artifacts"]["review_sha256"],
                manifest["artifacts"]["mapping_sha256"],
            ))
        self.assertEqual(outputs[0], outputs[1])


if __name__ == "__main__":
    unittest.main()
