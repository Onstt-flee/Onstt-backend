"""Tests for the immutable offline judgment scorer and comparison report."""

from copy import deepcopy
import hashlib
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from evaluation.judgment.dataset import DEFAULT_DATASET, load_records
from evaluation.judgment.runner import _artifact_paths, run_evaluation
from evaluation.judgment.scorer import (
    compare_runs,
    load_verified_run,
    score_run,
    write_report,
)


class JudgmentScorerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.records = load_records()
        cls.by_id = {row["id"]: row for row in cls.records}
        cls.input_to_id = {
            json.dumps(
                row["input"],
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            ): row["id"]
            for row in cls.records
        }

    def make_run(
        self,
        directory,
        *,
        name="run",
        model="test/model",
        ids=None,
        overrides=None,
        failures=None,
        temperature=0.0,
    ):
        overrides = overrides or {}
        failures = set(failures or [])

        def transport(**kwargs):
            model_input = json.loads(
                kwargs["request_body"]["messages"][1]["content"]
            )
            key = json.dumps(
                model_input,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            )
            row_id = self.input_to_id[key]
            if row_id in failures:
                return {
                    "transport_success": False,
                    "http_status": None,
                    "raw_text": "",
                    "raw_response": "",
                    "usage": None,
                    "error": "offline",
                    "latency_ms": 5.0,
                }
            judgment = deepcopy(
                overrides.get(row_id, self.by_id[row_id]["expected"])
            )
            raw = json.dumps(judgment, ensure_ascii=False)
            envelope = {
                "choices": [{"message": {"content": raw}}],
                "usage": {
                    "prompt_tokens": 10,
                    "completion_tokens": 20,
                    "total_tokens": 30,
                },
            }
            return {
                "transport_success": True,
                "http_status": 200,
                "raw_text": raw,
                "raw_response": json.dumps(
                    envelope, ensure_ascii=False
                ),
                "usage": envelope["usage"],
                "error": None,
                "latency_ms": 10.0,
            }

        output = Path(directory) / f"{name}.jsonl"
        run_evaluation(
            dataset_path=DEFAULT_DATASET,
            endpoint="http://127.0.0.1:1234/v1/chat/completions",
            model=model,
            output_path=output,
            selected_ids=ids,
            temperature=temperature,
            transport=transport,
        )
        return output

    def test_perfect_run_scores_decisions_corrections_edits_and_boundaries(self):
        with TemporaryDirectory() as directory:
            output = self.make_run(
                directory,
                ids=[
                    "JG-001", "JG-025", "JG-047", "JG-049",
                    "JG-061", "JG-067", "JG-070",
                ],
            )
            report = score_run(output)
            metrics = report["metrics"]
            self.assertEqual(
                metrics["json_contract_success_rate"]["value"], 1
            )
            self.assertEqual(metrics["decision_accuracy"]["value"], 1)
            self.assertEqual(metrics["overcorrection_rate"]["value"], 0)
            self.assertEqual(
                metrics["correction_detection_precision"]["value"], 1
            )
            self.assertEqual(
                metrics["correction_detection_recall"]["value"], 1
            )
            self.assertEqual(
                metrics["correct_withholding_rate"]["value"], 1
            )
            self.assertEqual(
                metrics["accepted_correction_rate_end_to_end"]["value"], 1
            )
            self.assertEqual(metrics["edit_micro_recall"]["value"], 1)
            self.assertEqual(
                metrics["compound_complete_rate"]["value"], 1
            )
            self.assertEqual(
                metrics["compound_missing_edit_count"], 0
            )
            self.assertTrue(report["meets_all_targets"])
            self.assertEqual(
                report["confusion_matrix"]["insufficient_evidence"]
                ["insufficient_evidence"],
                1,
            )
            self.assertEqual(
                report["performance"]["usage_totals"]["total_tokens"],
                210,
            )
            self.assertIn("boundary_case", report["by_review_tag"])
            interval = metrics["decision_accuracy"]["ci95_wilson"]
            self.assertLess(interval[0], 1)
            self.assertEqual(interval[1], 1)

    def test_transport_and_contract_failures_are_system_failures(self):
        overcorrection = {
            "decision": "needs_correction",
            "corrected_text": "明日は電車で病院に行きます！",
            "edits": [{
                "start": 13,
                "end": 14,
                "source": "。",
                "replacement": "！",
                "error_type": "copula_conjugation",
            }],
            "reason_ko": "테스트용 과교정입니다.",
        }
        missed = {
            "decision": "acceptable",
            "corrected_text": "明日は電車で病院を行きます。",
            "edits": [],
            "reason_ko": "테스트용 미탐지입니다.",
        }
        with TemporaryDirectory() as directory:
            output = self.make_run(
                directory,
                ids=["JG-001", "JG-025", "JG-049"],
                overrides={"JG-001": overcorrection, "JG-025": missed},
                failures={"JG-049"},
            )
            report = score_run(output)
            metrics = report["metrics"]
            self.assertEqual(report["counts"]["system_failures"], 1)
            self.assertEqual(report["counts"]["transport_failures"], 1)
            self.assertEqual(metrics["overcorrection_rate"]["value"], 1)
            self.assertEqual(
                metrics["correction_detection_precision"]["value"], 0
            )
            self.assertEqual(
                metrics["correction_detection_recall"]["value"], 0
            )
            self.assertEqual(
                metrics["correct_withholding_rate"]["value"], 0
            )
            self.assertEqual(
                report["confusion_matrix"]["insufficient_evidence"]
                ["system_failure"],
                1,
            )
            self.assertEqual(
                report["case_lists"]["system_failure_ids"], ["JG-049"]
            )
            self.assertFalse(report["meets_all_targets"])

    def test_accepted_alternative_is_not_canonical_or_exact_edit(self):
        alternative = {
            "decision": "needs_correction",
            "corrected_text": "明日は電車で病院へ行きます。",
            "edits": [{
                "start": 8,
                "end": 9,
                "source": "を",
                "replacement": "へ",
                "error_type": "particle_misuse",
            }],
            "reason_ko": "목적지 조사로 へ를 사용합니다.",
        }
        with TemporaryDirectory() as directory:
            output = self.make_run(
                directory,
                ids=["JG-025"],
                overrides={"JG-025": alternative},
            )
            report = score_run(output)
            metrics = report["metrics"]
            self.assertEqual(
                metrics["accepted_correction_rate_end_to_end"]["value"], 1
            )
            self.assertEqual(
                metrics["canonical_correction_exact_rate_end_to_end"]
                ["value"],
                0,
            )
            self.assertEqual(
                metrics["exact_canonical_edits_rate_end_to_end"]["value"],
                0,
            )
            self.assertEqual(
                report["case_lists"]["noncanonical_but_accepted_ids"],
                ["JG-025"],
            )

    def test_run_and_manifest_tampering_is_rejected(self):
        with TemporaryDirectory() as directory:
            output = self.make_run(directory, ids=["JG-001"])
            output.write_text(
                output.read_text(encoding="utf-8") + "\n",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "output SHA-256"):
                load_verified_run(output)

    def test_model_visible_input_tampering_is_rejected_even_with_new_hash(self):
        with TemporaryDirectory() as directory:
            output = self.make_run(directory, ids=["JG-001"])
            row = json.loads(output.read_text(encoding="utf-8"))
            visible = json.loads(
                row["request"]["messages"][1]["content"]
            )
            visible["answer"] = "gold leak"
            row["request"]["messages"][1]["content"] = json.dumps(
                visible, ensure_ascii=False, sort_keys=True,
                separators=(",", ":"),
            )
            output.write_text(
                json.dumps(
                    row,
                    ensure_ascii=False,
                    sort_keys=True,
                    separators=(",", ":"),
                )
                + "\n",
                encoding="utf-8",
            )
            _, manifest_path = _artifact_paths(output)
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["output_sha256"] = hashlib.sha256(
                output.read_bytes()
            ).hexdigest()
            manifest_path.write_text(
                json.dumps(manifest, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "allowlisted"):
                load_verified_run(output)

    def test_comparison_requires_same_inputs_and_configuration(self):
        with TemporaryDirectory() as directory:
            first = self.make_run(
                directory,
                name="a",
                model="model-a",
                ids=["JG-001", "JG-025"],
            )
            second = self.make_run(
                directory,
                name="b",
                model="model-b",
                ids=["JG-001", "JG-025"],
                temperature=0.5,
            )
            with self.assertRaisesRegex(
                ValueError, "generation settings"
            ):
                compare_runs([first, second])
            report = compare_runs(
                [first, second], allow_mixed_config=True
            )
            self.assertEqual(len(report["leaderboard"]), 2)
            self.assertEqual(
                report["leaderboard"][0]["model"], "model-a"
            )

            third = self.make_run(
                directory,
                name="c",
                model="model-c",
                ids=["JG-001"],
            )
            with self.assertRaisesRegex(ValueError, "input IDs"):
                compare_runs(
                    [first, third], allow_mixed_config=True
                )

    def test_reports_are_atomic_and_refuse_accidental_overwrite(self):
        with TemporaryDirectory() as directory:
            output = self.make_run(
                directory,
                ids=["JG-001", "JG-025", "JG-049"],
            )
            report = compare_runs([output])
            prefix = Path(directory) / "reports" / "comparison"
            json_path, markdown_path = write_report(report, prefix)
            self.assertTrue(json_path.is_file())
            self.assertTrue(markdown_path.is_file())
            stored = json.loads(json_path.read_text(encoding="utf-8"))
            self.assertEqual(stored["leaderboard"], report["leaderboard"])
            markdown = markdown_path.read_text(encoding="utf-8")
            self.assertIn("오프라인 채점 보고서", markdown)
            self.assertIn("95% CI", markdown)
            with self.assertRaises(FileExistsError):
                write_report(report, prefix)


if __name__ == "__main__":
    unittest.main()
