"""Content-free Raspberry Pi benchmark summary tests."""

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.summarize_pi5_benchmark import build_report, main, validated_sha256


HASH_A = "a" * 64
HASH_B = "b" * 64
HASH_C = "c" * 64


def valid_records(count=50, latency_ms=1000):
    return [
        {"response": {"contract_valid": True, "latency_ms": latency_ms}}
        for _ in range(count)
    ]


class Pi5BenchmarkTests(unittest.TestCase):
    def report(self, records=None, **overrides):
        values = {
            "memory_peak_bytes": 4 * 1024 ** 3,
            "throttled_before": "throttled=0x0",
            "throttled_after": "throttled=0x0",
            "quantization": "Q5_K_M",
            "model_sha256": HASH_A,
            "adapter_sha256": HASH_B,
            "run_sha256": HASH_C,
        }
        values.update(overrides)
        return build_report(valid_records() if records is None else records, **values)

    def test_passing_q5_report_preserves_content_free_provenance(self):
        report = self.report()
        self.assertTrue(report["passed"])
        self.assertEqual(report["schema_version"], "pi5-benchmark-summary-v0.2")
        self.assertEqual(report["artifacts"]["quantization"], "Q5_K_M")
        self.assertEqual(report["artifacts"]["raw_run_sha256"], HASH_C)
        self.assertFalse(report["contains_request_content"])

    def test_zero_memory_or_throttling_fails_gate(self):
        self.assertFalse(self.report(memory_peak_bytes=0)["passed"])
        self.assertFalse(self.report(throttled_after="throttled=0x50000")["passed"])

    def test_invalid_hash_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "lowercase SHA-256"):
            validated_sha256("not-a-hash")

    def test_cli_writes_passing_summary_and_returns_zero(self):
        with tempfile.TemporaryDirectory() as directory:
            run = Path(directory) / "run.jsonl"
            output = Path(directory) / "summary.json"
            run.write_text(
                "".join(json.dumps(row) + "\n" for row in valid_records()),
                encoding="utf-8",
            )
            argv = [
                "summarize_pi5_benchmark", "--run", str(run), "--output", str(output),
                "--memory-peak-bytes", str(4 * 1024 ** 3),
                "--throttled-before", "throttled=0x0",
                "--throttled-after", "throttled=0x0", "--quantization", "Q5_K_M",
                "--model-sha256", HASH_A, "--adapter-sha256", HASH_B,
            ]
            with patch.object(sys, "argv", argv):
                self.assertEqual(main(), 0)
            self.assertTrue(json.loads(output.read_text(encoding="utf-8"))["passed"])


if __name__ == "__main__":
    unittest.main()
