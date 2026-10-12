"""Deterministic helpers for Pi deployment artifacts."""

import json
import tempfile
import unittest
from pathlib import Path

from scripts.check_pi5_deployment import load_manifest, parse_memtotal, read_os_release
from scripts.summarize_pi5_benchmark import percentile
from scripts.write_pi_model_manifest import digest


class Pi5DeploymentTests(unittest.TestCase):
    def test_platform_parsers(self):
        self.assertEqual(parse_memtotal("MemTotal:       16384000 kB\n"), 16384000)
        self.assertEqual(
            read_os_release('ID=raspbian\nVERSION_CODENAME="bookworm"\n'),
            {"ID": "raspbian", "VERSION_CODENAME": "bookworm"},
        )
        with self.assertRaises(ValueError):
            parse_memtotal("MemFree: 1 kB")

    def test_manifest_validation_and_digest(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            artifact = root / "model.gguf"
            artifact.write_bytes(b"gguf-test")
            self.assertEqual(len(digest(artifact)), 64)
            manifest = root / "manifest.json"
            manifest.write_text(json.dumps({
                "schema_version": "pi5-judgment-model-manifest-v0.1",
                "quantization": "Q4_K_M",
            }), encoding="utf-8")
            self.assertEqual(load_manifest(manifest)["quantization"], "Q4_K_M")
            manifest.write_text(json.dumps({
                "schema_version": "wrong", "quantization": "Q4_K_M"
            }), encoding="utf-8")
            with self.assertRaises(ValueError):
                load_manifest(manifest)

    def test_nearest_rank_percentile(self):
        self.assertIsNone(percentile([], 0.95))
        self.assertEqual(percentile([3, 1, 2, 4], 0.50), 2)
        self.assertEqual(percentile(list(range(1, 21)), 0.95), 19)


if __name__ == "__main__":
    unittest.main()
