"""Tests for label-independent offline boundary-policy replay."""

from copy import deepcopy
import unittest

from evaluation.judgment.boundary_gate_replay import replay_boundary_policy


def judgment(text, decision):
    return {
        "decision": decision,
        "corrected_text": text,
        "error_types": [],
        "edits": [],
        "reason_ko": "테스트 판단",
        "classification_review_required": False,
    }


def response(parsed, *, valid=True):
    return {
        "transport_success": True,
        "http_status": 200,
        "raw_text": "{}",
        "raw_response": "{}",
        "usage": None,
        "error": None,
        "latency_ms": 1.0,
        "contract_valid": valid,
        "contract_error": None if valid else "bad contract",
        "parsed_judgment": parsed if valid else None,
    }


def verified_fixture():
    inputs = [
        ("A", "내일 학교에 갑니다.", None),
        ("B", "", None),
        ("C", "京都です。", None),
    ]
    rows = []
    records = []
    for item_id, text, context in inputs:
        model = judgment(text, "acceptable")
        rows.append({
            "id": item_id,
            "input": {
                "text": text,
                "context": context,
                "learner_level": "N5",
            },
            "response": response(
                model if item_id != "B" else None,
                valid=item_id != "B",
            ),
        })
        expected_decision = (
            "insufficient_evidence" if item_id in {"A", "B"} else "acceptable"
        )
        records.append({
            "id": item_id,
            "tags": [],
            "input": rows[-1]["input"],
            "expected": judgment(text, expected_decision),
            "accepted_corrections": [],
        })
    return {
        "run_path": "/tmp/source.jsonl",
        "manifest_path": "/tmp/source.jsonl.manifest.json",
        "dataset_path": "/tmp/dataset.jsonl",
        "dataset_sha256": "dataset-hash",
        "manifest": {
            "run_id": "run-id",
            "model": "model",
            "output_sha256": "run-hash",
            "prompt_version": "judgment-v0.2",
            "prompt_sha256": "prompt-hash",
            "generation": {
                "temperature": 0.0,
                "top_p": 1.0,
                "max_tokens": 512,
            },
            "input_ids": ["A", "B", "C"],
        },
        "rows": rows,
        "records": records,
    }


class JudgmentBoundaryGateReplayTests(unittest.TestCase):
    def test_replay_recovers_preclassified_boundaries(self):
        report = replay_boundary_policy(verified_fixture())
        self.assertEqual(report["model_call_avoided_ids"], ["A", "B"])
        self.assertEqual(report["changed_ids"], ["A", "B"])
        self.assertEqual(
            report["before"]["json_contract_success_rate"]["numerator"], 2
        )
        self.assertEqual(
            report["after"]["json_contract_success_rate"]["numerator"], 3
        )
        self.assertEqual(report["after_system_failure_ids"], [])
        self.assertEqual(
            report["after"]["correct_withholding_rate"]["numerator"], 2
        )

    def test_routing_does_not_read_gold_labels(self):
        first = verified_fixture()
        second = deepcopy(first)
        for record in second["records"]:
            record["expected"]["decision"] = "acceptable"
        report_a = replay_boundary_policy(first)
        report_b = replay_boundary_policy(second)
        self.assertEqual(
            report_a["model_call_avoided_ids"],
            report_b["model_call_avoided_ids"],
        )
        self.assertEqual(
            report_a["orthography_override_ids"],
            report_b["orthography_override_ids"],
        )
        self.assertEqual(report_a["changed_ids"], report_b["changed_ids"])


if __name__ == "__main__":
    unittest.main()
