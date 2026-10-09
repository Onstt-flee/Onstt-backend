"""Tests for the read-only real-STT shadow runner."""

import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from analyzer.judgment_service import JudgmentServiceError
from scripts.run_judgment_shadow import (
    canonical_json,
    input_snapshot_item,
    load_exclusion_snapshot,
    load_shadow_inputs,
    run_shadow,
    sha256_bytes,
)


class JudgmentShadowTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.database = self.root / "source.db"
        connection = sqlite3.connect(self.database)
        connection.executescript(
            """
            CREATE TABLE users (id INTEGER PRIMARY KEY, level TEXT);
            CREATE TABLE sessions (
                id INTEGER PRIMARY KEY, user_id INTEGER, topic TEXT
            );
            CREATE TABLE utterances (
                id INTEGER PRIMARY KEY, session_id INTEGER, stt_text TEXT,
                processed_text TEXT, normalized_text TEXT, language TEXT,
                stt_model TEXT
            );
            CREATE TABLE judgment_results (id INTEGER PRIMARY KEY);
            INSERT INTO users VALUES (1, 'N4');
            INSERT INTO sessions VALUES (1, 1, 'test');
            INSERT INTO utterances VALUES
                (1, 1, '古い文です。', NULL, NULL, 'ja', 'whisper-a'),
                (2, 1, '한국어입니다.', NULL, NULL, 'ko', 'whisper-a'),
                (3, 1, '原文三。', '処理三。', NULL, 'ja', 'whisper-b'),
                (4, 1, '原文四。', NULL, '正規四。', 'ja', 'whisper-b');
            """
        )
        connection.commit()
        connection.close()

    def tearDown(self):
        self.temporary.cleanup()

    def test_selection_is_latest_japanese_and_uses_api_text_priority(self):
        rows = load_shadow_inputs(self.database, 2)
        self.assertEqual([row["utterance_id"] for row in rows], [4, 3])
        self.assertEqual([row["text"] for row in rows], ["正規四。", "処理三。"])
        self.assertEqual([row["text_source"] for row in rows],
                         ["normalized_text", "processed_text"])
        self.assertTrue(all(row["learner_level"] == "N4" for row in rows))

    def test_authenticated_snapshot_excludes_exact_prior_inputs(self):
        prior = load_shadow_inputs(self.database, 2)
        raw = self.root / "prior-raw.jsonl"
        raw.write_text(
            "".join(canonical_json({**row, "context": None}) + "\n" for row in prior),
            encoding="utf-8",
        )
        snapshot = [input_snapshot_item(row) for row in prior]
        summary = self.root / "prior-summary.json"
        summary.write_text(json.dumps({
            "selection": {
                "selected": 2,
                "input_snapshot_sha256": sha256_bytes(
                    canonical_json(snapshot).encode()
                ),
            }
        }), encoding="utf-8")
        excluded, metadata = load_exclusion_snapshot(raw, summary)
        remaining = load_shadow_inputs(
            self.database, 1, excluded_fingerprints=excluded
        )
        self.assertEqual([row["utterance_id"] for row in remaining], [1])
        self.assertEqual(metadata["excluded_count"], 2)

        summary.write_text(json.dumps({
            "selection": {"selected": 2, "input_snapshot_sha256": "bad"}
        }), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "does not match"):
            load_exclusion_snapshot(raw, summary)

    def test_shadow_tracks_retry_recovery_privately_without_db_writes(self):
        raw = self.root / "runs" / "raw.jsonl"
        summary_path = self.root / "summary.json"
        calls = 0

        def judge(text, **kwargs):
            nonlocal calls
            calls += 1
            retry = calls == 2
            return {
                "decision": "acceptable",
                "corrected_text": text,
                "edits": [],
                "error_types": [],
                "reason_ko": "허용",
                "classification_review_required": False,
                "strategy": "d_only",
                "model_name": kwargs["model_name"],
                "adapter_name": "adapter",
                "selection_reason": "test",
                "contract_version": "judgment-v0.2",
                "latency_ms": 20.0 if retry else 10.0,
                "context": None,
                "learner_level": kwargs["learner_level"],
                "attempt_count": 2 if retry else 1,
                "retry_used": retry,
                "first_contract_error": (
                    "Non-correction decisions must preserve input text" if retry else None
                ),
            }

        summary = run_shadow(
            database_path=self.database,
            limit=2,
            raw_output=raw,
            summary_output=summary_path,
            judgment_fn=judge,
            generated_at="2026-10-01T00:00:00+00:00",
        )
        self.assertEqual(summary["results"]["successes"], 2)
        self.assertEqual(summary["results"]["first_attempt_successes"], 1)
        self.assertEqual(summary["runtime"]["model_calls"], 3)
        self.assertEqual(summary["runtime"]["retry_attempts"], 1)
        self.assertEqual(summary["runtime"]["retry_recoveries"], 1)
        self.assertEqual(summary["results"]["latency_ms"]["p95"], 19.5)
        self.assertTrue(summary["database_integrity"]["unchanged"])
        self.assertIn("正規四。", raw.read_text())
        serialized_summary = summary_path.read_text()
        self.assertNotIn("正規四。", serialized_summary)
        self.assertNotIn("utterance_id", serialized_summary)
        self.assertEqual(json.loads(serialized_summary), summary)
        connection = sqlite3.connect(self.database)
        count = connection.execute("SELECT COUNT(*) FROM judgment_results").fetchone()[0]
        connection.close()
        self.assertEqual(count, 0)

    def test_failures_are_counted_with_retry_metadata(self):
        def fail(*args, **kwargs):
            raise JudgmentServiceError(
                "bad contract",
                raw_text="{bad output}",
                attempt_count=2,
                retry_used=True,
                first_contract_error=(
                    "Non-correction decisions must preserve input text"
                ),
            )

        summary = run_shadow(
            database_path=self.database,
            limit=1,
            raw_output=self.root / "raw.jsonl",
            summary_output=self.root / "summary.json",
            judgment_fn=fail,
        )
        self.assertEqual(summary["results"]["failures"], 1)
        self.assertEqual(summary["results"]["failure_counts"],
                         {"JudgmentServiceError": 1})
        self.assertEqual(summary["runtime"]["model_calls"], 2)
        self.assertEqual(summary["runtime"]["retry_failures"], 1)
        raw_record = json.loads((self.root / "raw.jsonl").read_text())
        self.assertEqual(raw_record["raw_model_output"], "{bad output}")
        with self.assertRaisesRegex(ValueError, "found 3"):
            run_shadow(
                database_path=self.database,
                limit=4,
                raw_output=self.root / "unused.jsonl",
                summary_output=self.root / "unused.json",
                judgment_fn=fail,
            )


if __name__ == "__main__":
    unittest.main()
