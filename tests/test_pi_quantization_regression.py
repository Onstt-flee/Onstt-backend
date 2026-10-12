"""Acceptance-gate tests for BF16 versus Pi Q4 output."""

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts import check_pi_quantization_regression as gate


def write_jsonl(path: Path, rows: list[dict]):
    path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")


def run_row(item_id: str, decision: str, corrected: str, valid: bool = True):
    return {
        "id": item_id,
        "response": {
            "contract_valid": valid,
            "parsed_judgment": {
                "decision": decision, "corrected_text": corrected,
            } if valid else None,
        },
    }


class PiQuantizationRegressionTests(unittest.TestCase):
    def test_identical_candidate_passes(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            dataset = [
                {"id": "A", "expected": {"decision": "acceptable", "corrected_text": "ok"},
                 "accepted_corrections": []},
                {"id": "B", "expected": {"decision": "needs_correction", "corrected_text": "fixed"},
                 "accepted_corrections": ["fixed"]},
            ]
            reference = [run_row("A", "acceptable", "ok"),
                         run_row("B", "needs_correction", "fixed")]
            write_jsonl(root / "dataset.jsonl", dataset)
            write_jsonl(root / "reference.jsonl", reference)
            write_jsonl(root / "candidate.jsonl", reference)
            argv = ["gate", "--dataset", str(root / "dataset.jsonl"),
                    "--reference", str(root / "reference.jsonl"),
                    "--candidate", str(root / "candidate.jsonl"),
                    "--output", str(root / "report.json")]
            with patch("sys.argv", argv):
                self.assertEqual(gate.main(), 0)
            report = json.loads((root / "report.json").read_text())
            self.assertTrue(report["passed"])

    def test_contract_failure_fails_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            dataset = [{"id": "A", "expected": {"decision": "acceptable",
                                                   "corrected_text": "ok"},
                        "accepted_corrections": []}]
            write_jsonl(root / "dataset.jsonl", dataset)
            write_jsonl(root / "reference.jsonl", [run_row("A", "acceptable", "ok")])
            write_jsonl(root / "candidate.jsonl", [run_row("A", "acceptable", "ok", False)])
            with patch("sys.argv", ["gate", "--dataset", str(root / "dataset.jsonl"),
                                    "--reference", str(root / "reference.jsonl"),
                                    "--candidate", str(root / "candidate.jsonl"),
                                    "--output", str(root / "report.json")]):
                self.assertEqual(gate.main(), 1)


if __name__ == "__main__":
    unittest.main()
