import json
from pathlib import Path
import subprocess
import sys
import unittest
import tempfile

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import models
from analyzer import feedback_admin


class FeedbackAdminProjectionTests(unittest.TestCase):
    def setUp(self):
        engine = create_engine(
            "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool,
        )
        models.Base.metadata.create_all(engine)
        self.db = sessionmaker(bind=engine)()
        session = models.Session(topic="admin-projection-test")
        self.db.add(session); self.db.flush()
        utterance = models.Utterance(session_id=session.id, stt_text="秘密の原文")
        self.db.add(utterance); self.db.flush()
        judgment = models.JudgmentResult(
            utterance_id=utterance.id, decision="acceptable",
            corrected_text="秘密の原文", edits="[]", error_types="[]",
            reason_ko="테스트", classification_review_required=False,
            strategy="d_only", model_name="judgment-v02d",
            adapter_name="v0.2-d", selection_reason="test",
            contract_version="judgment-v0.2", learner_level="N5",
        )
        self.db.add(judgment); self.db.flush()
        self.db.add(models.FeedbackAuditJob(
            judgment_id=judgment.id, feedback_model="feedback-qwen3-8b-v03",
            feedback_adapter="feedback-verifier-v0.3",
            feedback_model_hash="b" * 64, contract_version="feedback-v0.1",
            status="succeeded", attempts=1,
            next_attempt_at=__import__("datetime").datetime.now(__import__("datetime").timezone.utc),
        ))
        self.db.add(models.FeedbackAudit(
            judgment_id=judgment.id, verdict="disagree",
            issue_codes=json.dumps(["false_negative"]),
            recommended_judgment=json.dumps({
                "decision": "needs_correction", "corrected_text": "修正文",
                "error_types": ["particle_misuse"], "reason_ko": "권장 근거",
            }),
            recommended_edits="[]", review_reason_ko="검수 근거",
            feedback_model="feedback-qwen3-8b-v03",
            feedback_adapter="feedback-verifier-v0.3",
            feedback_model_hash="b" * 64, contract_version="feedback-v0.1",
            provenance_snapshot=json.dumps({"runtime": "gpu_bf16"}), latency_ms=10.0,
        ))
        self.db.commit()
        self.judgment_id = judgment.id

    def tearDown(self):
        self.db.close()

    def test_list_health_and_issue_projections_are_content_free(self):
        listed = feedback_admin.list_audits(self.db)
        serialized = json.dumps(listed, ensure_ascii=False, default=str)
        self.assertNotIn("秘密の原文", serialized)
        self.assertNotIn("修正文", serialized)

        health = feedback_admin.monitoring_snapshot(self.db)
        self.assertFalse(health["contains_request_content"])
        self.assertEqual(health["audit_count"], 1)

        issues = feedback_admin.issue_groups(self.db)
        self.assertEqual(issues[0]["status"], "emerging")
        self.assertNotIn("秘密の原文", json.dumps(issues, ensure_ascii=False))

    def test_detail_is_content_bearing_but_excludes_source_and_success_cannot_retry(self):
        detail = feedback_admin.audit_detail(self.db, self.judgment_id)
        self.assertEqual(detail["recommended_judgment"]["corrected_text"], "修正文")
        self.assertNotIn("秘密の原文", json.dumps(detail, ensure_ascii=False, default=str))
        self.assertFalse(feedback_admin.retry_job(self.db, self.judgment_id))

    def test_reauditing_same_judgment_does_not_inflate_recurrence(self):
        self.db.add(models.FeedbackAudit(
            judgment_id=self.judgment_id, verdict="disagree",
            issue_codes=json.dumps(["false_negative"]),
            recommended_judgment=json.dumps({
                "decision": "needs_correction", "corrected_text": "別の非公開修正文",
                "error_types": ["particle_misuse"], "reason_ko": "別の非公開根拠",
            }),
            recommended_edits="[]", review_reason_ko="別の非公開検수 근거",
            feedback_model="feedback-qwen3-8b-v04",
            feedback_adapter="feedback-verifier-v0.4",
            feedback_model_hash="c" * 64, contract_version="feedback-v0.1",
            provenance_snapshot=json.dumps({"runtime": "gpu_bf16"}), latency_ms=12.0,
        ))
        self.db.commit()

        disagreement = next(
            item for item in feedback_admin.issue_groups(self.db)
            if item["kind"] == "model_disagreement"
        )
        self.assertEqual(disagreement["count"], 1)
        self.assertEqual(disagreement["judgment_ids"], [self.judgment_id])
        self.assertEqual(disagreement["status"], "emerging")

    def test_unreviewable_and_failed_jobs_are_content_free_alerts(self):
        self.db.add(models.FeedbackAudit(
            judgment_id=self.judgment_id, verdict="unreviewable",
            issue_codes="[]", recommended_judgment=None, recommended_edits="[]",
            review_reason_ko="非公開の検수 불가 근거",
            feedback_model="feedback-qwen3-8b-v04",
            feedback_adapter="feedback-verifier-v0.4",
            feedback_model_hash="d" * 64, contract_version="feedback-v0.1",
            provenance_snapshot=json.dumps({"runtime": "gpu_bf16"}), latency_ms=9.0,
        ))
        self.db.add(models.FeedbackAuditJob(
            judgment_id=self.judgment_id, feedback_model="feedback-qwen3-8b-v05",
            feedback_adapter="feedback-verifier-v0.5",
            feedback_model_hash="e" * 64, contract_version="feedback-v0.1",
            status="failed", attempts=3, error_category="contract",
            next_attempt_at=__import__("datetime").datetime.now(
                __import__("datetime").timezone.utc
            ),
        ))
        self.db.commit()

        issues = feedback_admin.issue_groups(self.db)
        kinds = {item["kind"]: item for item in issues}
        self.assertIn("unreviewable", kinds)
        self.assertIn("audit_failure", kinds)
        self.assertEqual(kinds["audit_failure"]["error_category"], "contract")
        self.assertEqual(kinds["audit_failure"]["recommended_decision"], None)
        serialized = json.dumps(issues, ensure_ascii=False)
        self.assertNotIn("秘密の原文", serialized)
        self.assertNotIn("非公開", serialized)

    def test_verifier_direct_execution_resolves_project_modules(self):
        script = (
            Path(__file__).resolve().parents[1]
            / "scripts"
            / "verify_feedback_admin_shadow.py"
        )
        with tempfile.TemporaryDirectory() as directory:
            completed = subprocess.run(
                [sys.executable, str(script), "--help"], cwd=directory,
                capture_output=True, text=True, check=False,
            )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIn("--scope", completed.stdout)

if __name__ == "__main__":

    unittest.main()
