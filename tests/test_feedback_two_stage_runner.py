import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
import unittest

from analyzer.feedback_contract import canonical_json
from evaluation.feedback.two_stage_runner import claim_execution, run_one, validate_execution


ROOT = Path(__file__).resolve().parents[1]
HERE = ROOT / "evaluation/feedback"


def row():
    text = "有名店で時計があります。"
    return {
        "id": "x",
        "text": text,
        "context": None,
        "learner_level": "N5",
        "candidate_judgment": {"decision": "acceptable", "corrected_text": text, "error_types": [], "reason_ko": "허용됩니다."},
    }


class FeedbackTwoStageRunnerTests(unittest.TestCase):
    def test_current_v07_seal_cannot_run_without_separate_ready_plan(self):
        seal_path = HERE / "holdout_v0.7.protocol.json"
        seal = json.loads(seal_path.read_text(encoding="utf-8"))
        plan = {
            "dataset_sha256": seal["dataset_sha256"],
            "seal_protocol_sha256": hashlib.sha256(seal_path.read_bytes()).hexdigest(),
            "contract_version": "feedback-two-stage-v0.1",
            "ready_for_inference": False,
            "single_use": True,
            "consumed": False,
            "candidate": {"stage1_model": "a", "stage2_model": "b", "model_sha256": "c", "adapter_sha256": "d"},
            "code_sha256": {"contract": "a" * 64, "runner": "b" * 64, "scorer": "c" * 64},
        }
        with self.assertRaisesRegex(ValueError, "not ready"):
            validate_execution(seal, plan, dataset_sha256=seal["dataset_sha256"], seal_sha256=plan["seal_protocol_sha256"])

    def test_agree_does_not_call_stage2(self):
        calls = []
        def call_fn(**kwargs):
            calls.append(kwargs["request_body"]["max_tokens"])
            return {"transport_success": True, "raw_text": canonical_json({"verdict": "agree", "issue_codes": [], "review_reason_ko": "타당합니다."}), "latency_ms": 100}
        result = run_one(row(), endpoint="http://local", stage1_model="s1", stage2_model="s2", timeout=1, call_fn=call_fn)
        self.assertEqual(calls, [192])
        self.assertFalse(result["stage2_called"])
        self.assertTrue(result["combined_contract_success"])
        self.assertEqual(result["total_latency_ms"], 100)

    def test_disagree_calls_stage2_exactly_once(self):
        calls = []
        def call_fn(**kwargs):
            max_tokens = kwargs["request_body"]["max_tokens"]
            calls.append(max_tokens)
            if max_tokens == 192:
                content = {"verdict": "disagree", "issue_codes": ["false_negative"], "review_reason_ko": "오류 누락"}
                return {"transport_success": True, "raw_text": canonical_json(content), "latency_ms": 100}
            content = {"decision": "needs_correction", "corrected_text": "有名店に時計があります。", "error_types": ["particle_misuse"], "reason_ko": "존재 장소에는 に가 필요합니다."}
            return {"transport_success": True, "raw_text": canonical_json(content), "latency_ms": 150}
        result = run_one(row(), endpoint="http://local", stage1_model="s1", stage2_model="s2", timeout=1, call_fn=call_fn)
        self.assertEqual(calls, [192, 384])
        self.assertTrue(result["stage2_called"])
        self.assertTrue(result["combined_contract_success"])
        self.assertEqual(result["total_latency_ms"], 250)

    def test_invalid_stage1_fails_closed_without_stage2(self):
        calls = []
        def call_fn(**kwargs):
            calls.append(1)
            return {"transport_success": True, "raw_text": "not-json", "latency_ms": 50}
        result = run_one(row(), endpoint="http://local", stage1_model="s1", stage2_model="s2", timeout=1, call_fn=call_fn)
        self.assertEqual(len(calls), 1)
        self.assertFalse(result["stage2_called"])
        self.assertFalse(result["combined_contract_success"])

    def test_ready_plan_binds_endpoint_output_and_single_use_claim(self):
        seal_path = HERE / "holdout_v0.7.protocol.json"
        seal = json.loads(seal_path.read_text(encoding="utf-8"))
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            output = root / "result.jsonl"
            plan = {
                "dataset_sha256": seal["dataset_sha256"],
                "seal_protocol_sha256": hashlib.sha256(seal_path.read_bytes()).hexdigest(),
                "contract_version": "feedback-two-stage-v0.1",
                "ready_for_inference": True,
                "single_use": True,
                "consumed": False,
                "candidate": {
                    "stage1_model": "s1", "stage2_model": "s2",
                    "model_sha256": "d" * 64, "adapter_sha256": "e" * 64,
                },
                "code_sha256": {"contract": "a" * 64, "runner": "b" * 64, "scorer": "c" * 64},
                "execution": {
                    "endpoint": "http://127.0.0.1:1235/v1/chat/completions",
                    "output_path": str(output.resolve()),
                    "claim_path": str((root / "claimed.json").resolve()),
                    "receipt_path": str((root / "receipt.json").resolve()),
                },
            }
            validate_execution(
                seal, plan, dataset_sha256=seal["dataset_sha256"],
                seal_sha256=plan["seal_protocol_sha256"],
                endpoint=plan["execution"]["endpoint"], output_path=output,
            )
            with self.assertRaisesRegex(ValueError, "endpoint differs"):
                validate_execution(
                    seal, plan, dataset_sha256=seal["dataset_sha256"],
                    seal_sha256=plan["seal_protocol_sha256"], endpoint="http://wrong", output_path=output,
                )
            claim_execution(plan, plan_sha256="f" * 64)
            with self.assertRaisesRegex(FileExistsError, "already been claimed"):
                claim_execution(plan, plan_sha256="f" * 64)

    def test_direct_script_execution_resolves_project_modules(self):
        completed = subprocess.run(
            [str(ROOT / "venv/bin/python"), str(HERE / "two_stage_runner.py"), "--help"],
            cwd="/tmp", capture_output=True, text=True, check=False,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIn("Single-use offline runner", completed.stdout)


if __name__ == "__main__":
    unittest.main()
