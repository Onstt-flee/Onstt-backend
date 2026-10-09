"""Tests for aggregate-only stored-STT boundary dry-run."""

import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from scripts.run_judgment_boundary_dry_run import run_boundary_dry_run


class JudgmentBoundaryDryRunTests(unittest.TestCase):
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
                (1, 1, '今日は学校に行きます。', NULL, NULL, 'ja', 'whisper-a'),
                (2, 1, '내일 학교에 갑니다.', NULL, NULL, 'ja', 'whisper-a'),
                (3, 1, 'I went home.', NULL, NULL, 'ja', 'whisper-a'),
                (4, 1, '［雑音］', NULL, NULL, 'ja', 'whisper-b'),
                (5, 1, '本お読みます。', NULL, NULL, 'ja', 'whisper-b'),
                (6, 1, '원문', 'AIを勉強します。', NULL, 'ja', 'whisper-b'),
                (7, 1, 'excluded', NULL, NULL, 'ko', 'whisper-c');
            """
        )
        connection.commit()
        connection.close()

    def tearDown(self):
        self.temporary.cleanup()

    def test_all_eligible_rows_are_aggregated_without_private_output_or_writes(self):
        output = self.root / "result.json"
        before = self.database.read_bytes()
        result = run_boundary_dry_run(
            database_path=self.database,
            summary_output=output,
            generated_at="2026-10-06T00:00:00+00:00",
        )
        self.assertEqual(result["selection"]["available"], 6)
        self.assertEqual(result["selection"]["selected"], 6)
        self.assertEqual(result["routing"]["counts"], {
            "deterministic": 3,
            "model": 3,
        })
        self.assertEqual(result["routing"]["boundary_type_counts"], {
            "no_proposition": 1,
            "out_of_scope_language": 2,
        })
        self.assertEqual(result["routing"]["model_call_avoided_count"], 3)
        self.assertEqual(result["advisories"]["rows"], 1)
        self.assertEqual(result["runtime"]["model_calls"], 0)
        self.assertEqual(result["runtime"]["database_writes"], 0)
        self.assertEqual(result["runtime"]["judgment_results_written"], 0)
        self.assertTrue(result["database"]["unchanged"])
        self.assertEqual(self.database.read_bytes(), before)

        rendered = output.read_text(encoding="utf-8")
        for private in (
            "今日は学校に行きます。",
            "내일 학교에 갑니다.",
            "I went home.",
            "本お読みます。",
            "AIを勉強します。",
            '"utterance_id"',
        ):
            self.assertNotIn(private, rendered)
        self.assertEqual(json.loads(rendered), result)

    def test_limit_and_output_guards(self):
        result = run_boundary_dry_run(
            database_path=self.database,
            summary_output=self.root / "limited.json",
            limit=2,
        )
        self.assertEqual(result["selection"]["available"], 6)
        self.assertEqual(result["selection"]["selected"], 2)
        with self.assertRaisesRegex(ValueError, "positive integer"):
            run_boundary_dry_run(
                database_path=self.database,
                summary_output=self.root / "bad.json",
                limit=0,
            )
        with self.assertRaisesRegex(ValueError, "must not overwrite"):
            run_boundary_dry_run(
                database_path=self.database,
                summary_output=self.database,
            )


if __name__ == "__main__":
    unittest.main()
