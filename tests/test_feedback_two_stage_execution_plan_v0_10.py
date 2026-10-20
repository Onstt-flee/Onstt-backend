import hashlib
import json
from pathlib import Path
import unittest

from evaluation.feedback.two_stage_runner import validate_execution


ROOT = Path(__file__).resolve().parents[1]
EVAL = ROOT / "evaluation/feedback"
MODEL_ROOT = Path("/home/cap-minsung/lora-adapter-bank")


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class FeedbackTwoStageExecutionPlanV010Tests(unittest.TestCase):
    def test_plan_binds_candidate_code_and_single_use_paths(self):
        dataset = EVAL / "holdout_v0.10.jsonl"
        seal_path = EVAL / "holdout_v0.10.protocol.json"
        plan = json.loads((EVAL / "holdout_v0.10.execution-plan.json").read_text(encoding="utf-8"))
        seal = json.loads(seal_path.read_text(encoding="utf-8"))
        validate_execution(
            seal, plan, dataset_sha256=digest(dataset), seal_sha256=digest(seal_path),
            endpoint=plan["execution"]["endpoint"], output_path=Path(plan["execution"]["output_path"]),
        )
        self.assertEqual(plan["execution_count"], 0)
        self.assertFalse(plan["serving"]["flashinfer_sampler"])
        self.assertEqual(plan["serving"]["engine_version"], "0.28.0")
        self.assertTrue(plan["experiment_scope"].startswith("offline_research_only"))
        self.assertEqual(plan["candidate"]["stage1_model"], plan["candidate"]["stage2_model"])
        self.assertFalse(Path(plan["execution"]["output_path"]).is_relative_to(ROOT))

    def test_candidate_and_code_hashes_match_files(self):
        plan = json.loads((EVAL / "holdout_v0.10.execution-plan.json").read_text(encoding="utf-8"))
        candidate = plan["candidate"]
        self.assertEqual(candidate["model_sha256"], digest(MODEL_ROOT / "base-models/qwen3-8b-hf/MODEL_MANIFEST.json"))
        self.assertEqual(candidate["adapter_sha256"], digest(MODEL_ROOT / "adapters/feedback-verifier-v0.8-stage2-recovery-style/adapter_model.safetensors"))
        self.assertEqual(candidate["adapter_run_manifest_sha256"], digest(MODEL_ROOT / "adapters/feedback-verifier-v0.8-stage2-recovery-style/run_manifest.json"))
        self.assertEqual(plan["code_sha256"]["contract"], digest(ROOT / "analyzer/feedback_two_stage_contract.py"))
        self.assertEqual(plan["code_sha256"]["runner"], digest(EVAL / "two_stage_runner.py"))
        self.assertEqual(plan["code_sha256"]["scorer"], digest(EVAL / "two_stage_scorer.py"))


    def test_consumption_record_matches_single_run_and_passing_summary(self):
        plan_path = EVAL / "holdout_v0.10.execution-plan.json"
        record = json.loads((EVAL / "holdout_v0.10.execution-record.json").read_text(encoding="utf-8"))
        summary = json.loads((EVAL / "holdout_v0.10.result.json").read_text(encoding="utf-8"))
        self.assertTrue(record["consumed"])
        self.assertEqual(record["execution_count"], 1)
        self.assertEqual(record["candidate_status"], "passed_offline_thresholds")
        self.assertEqual(record["execution_plan_sha256"], digest(plan_path))
        self.assertEqual(record["result_summary_sha256"], digest(EVAL / "holdout_v0.10.result.json"))
        self.assertEqual(record["model_requests"], {"stage1": 120, "stage2": 60, "transport_success": 180})
        self.assertTrue(summary["threshold_evaluation"]["passed"])
        self.assertEqual(summary["metrics"]["stage1_contract_success_rate"], 1.0)
        self.assertEqual(summary["metrics"]["stage2_contract_success_rate"], 1.0)
        self.assertEqual(summary["metrics"]["disagreement_recall"], 1.0)
        self.assertEqual(summary["metrics"]["recommended_decision_accuracy"], 0.95)
        self.assertEqual(summary["metrics"]["accepted_correction_rate"], 1.0)


if __name__ == "__main__":
    unittest.main()
