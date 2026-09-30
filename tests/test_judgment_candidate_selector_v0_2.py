"""Test explicit model identity around the frozen candidate selector."""

import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from evaluation.judgment.candidate_selector_v0_2 import build_named_selected_run


class JudgmentCandidateSelectorV02Tests(unittest.TestCase):
    def test_explicit_model_name_is_written_and_reverified(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "selected.jsonl"
            manifest_path = output.with_name(f"{output.name}.manifest.json")
            audit_path = output.with_name(f"{output.name}.selection.json")

            def fake_build(*args, **kwargs):
                output.write_text(json.dumps({
                    "request": {"model": "old-name"}, "id": "JG-001",
                }) + "\n", encoding="utf-8")
                manifest_path.write_text(json.dumps({
                    "model": "old-name", "output_sha256": "old-hash",
                }), encoding="utf-8")
                audit_path.write_text("{}", encoding="utf-8")
                return {}

            with patch("evaluation.judgment.candidate_selector_v0_2.build_selected_run",
                       side_effect=fake_build), patch(
                "evaluation.judgment.candidate_selector_v0_2.load_verified_run"
            ) as verified:
                result = build_named_selected_run(
                    Path("primary"), Path("secondary"), output,
                    model_name="judgment-v02d-gated-v02f",
                    dataset_path=Path("dataset"),
                )

            row = json.loads(output.read_text(encoding="utf-8"))
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            audit = json.loads(audit_path.read_text(encoding="utf-8"))
            expected_hash = hashlib.sha256(output.read_bytes()).hexdigest()
            self.assertEqual(row["request"]["model"], "judgment-v02d-gated-v02f")
            self.assertEqual(manifest["model"], "judgment-v02d-gated-v02f")
            self.assertEqual(manifest["output_sha256"], expected_hash)
            self.assertEqual(audit["derived_model"], "judgment-v02d-gated-v02f")
            self.assertEqual(result["manifest"], manifest)
            verified.assert_called_once_with(output.resolve(), dataset_path=Path("dataset"))

    def test_blank_model_name_is_rejected_before_build(self):
        with patch("evaluation.judgment.candidate_selector_v0_2.build_selected_run") as build:
            with self.assertRaisesRegex(ValueError, "model_name must be nonblank"):
                build_named_selected_run(
                    Path("primary"), Path("secondary"), Path("output"),
                    model_name="   ",
                )
            build.assert_not_called()


if __name__ == "__main__":
    unittest.main()
