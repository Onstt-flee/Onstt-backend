import json
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import unittest

from evaluation.feedback.build_synthetic_shadow_v0_1 import build
from scripts.run_feedback_synthetic_shadow import load_inputs, percentile
from scripts.build_feedback_actual_inputs import build as build_actual


class FeedbackSyntheticShadowTests(unittest.TestCase):
    def test_generator_creates_200_label_free_unique_inputs(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "inputs.jsonl"
            manifest_path = Path(directory) / "manifest.json"
            manifest = build(output, manifest_path)
            rows = load_inputs(output)
        self.assertEqual(len(rows), 200)
        self.assertEqual(len({row["id"] for row in rows}), 200)
        self.assertEqual(manifest["stratum_counts"], {
            "acceptable_like": 80,
            "correction_like": 80,
            "insufficient_like": 20,
            "boundary_like": 20,
        })
        self.assertFalse(manifest["quality_claim_allowed"])
        for row in rows:
            self.assertEqual(set(row["input"]), {"text", "context", "learner_level"})
            self.assertNotIn("expected", json.dumps(row, ensure_ascii=False))

    def test_percentile_uses_nearest_rank(self):
        self.assertEqual(percentile([1.0, 2.0, 3.0, 4.0], 0.95), 4.0)
        self.assertIsNone(percentile([], 0.95))

    def test_actual_input_builder_keeps_content_outside_manifest(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            database = root / "source.db"
            connection = sqlite3.connect(database)
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
                INSERT INTO users VALUES (1, 'N5');
                INSERT INTO sessions VALUES (1, 1, 'test');
                """
            )
            connection.executemany(
                "INSERT INTO utterances VALUES (?, 1, ?, NULL, NULL, 'ja', 'test')",
                [(index, f"発話{index}です。") for index in range(1, 201)],
            )
            connection.commit()
            connection.close()
            private = root / "private" / "inputs.jsonl"
            manifest_path = root / "manifest.json"
            manifest = build_actual(database, private, manifest_path)
            self.assertEqual(manifest["input_count"], 200)
            self.assertFalse(manifest["contains_source_text"])
            self.assertFalse(manifest["contains_user_ids"])
            self.assertEqual(len(load_inputs(private)), 200)
            self.assertNotIn("発話", manifest_path.read_text(encoding="utf-8"))

    def test_direct_script_execution_resolves_project_modules(self):
        script = Path(__file__).resolve().parents[1] / "scripts" / "run_feedback_synthetic_shadow.py"
        with tempfile.TemporaryDirectory() as directory:
            completed = subprocess.run(
                [sys.executable, str(script), "--help"],
                cwd=directory,
                capture_output=True,
                text=True,
                check=False,
            )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIn("--scope", completed.stdout)


if __name__ == "__main__":
    unittest.main()
