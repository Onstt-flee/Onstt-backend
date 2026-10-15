import json
import unittest

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


if __name__ == "__main__":
    unittest.main()
