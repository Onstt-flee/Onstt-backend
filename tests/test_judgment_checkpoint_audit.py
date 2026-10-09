"""Tests for the future-commit judgment checkpoint audit."""

import tempfile
import unittest
from pathlib import Path

from scripts.audit_judgment_checkpoint import (
    ROOT,
    audit_repository,
    prohibited_reason,
    sha256_file,
)


class JudgmentCheckpointAuditTests(unittest.TestCase):
    def test_prohibited_paths_cover_private_data_weights_and_audio(self):
        prohibited = (
            "evaluation/judgment/runs/raw.jsonl",
            "stt_data.db",
            "adapter/model.safetensors",
            "audio/sample.wav",
            ".env",
        )
        for path in prohibited:
            with self.subTest(path=path):
                self.assertIsNotNone(prohibited_reason(path))
        self.assertIsNone(prohibited_reason("evaluation/judgment/results/summary.json"))

    def test_sha256_file_is_deterministic(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "sample"
            path.write_bytes(b"checkpoint")
            self.assertEqual(
                sha256_file(path),
                "47320987f9a49d5b00119b960f247a956773f57543982b8bfcb6da5bb3afd9ef",
            )

    def test_current_repository_passes_content_free_audit(self):
        result = audit_repository(ROOT)
        self.assertTrue(result["passed"], result["errors"])
        self.assertFalse(result["content_scanned"])
        self.assertFalse(result["mutations_performed"])
        self.assertTrue(all(result["private_paths_ignored"].values()))
        self.assertTrue(all(
            item["matches"] for item in result["protected_hashes"].values()
        ))


if __name__ == "__main__":
    unittest.main()
