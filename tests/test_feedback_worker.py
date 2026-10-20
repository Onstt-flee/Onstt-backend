import json
import unittest

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import models
from analyzer.feedback_service import FeedbackServiceError
from analyzer.feedback_worker import process_one
from database import Base


class FeedbackWorkerTests(unittest.TestCase):
    def setUp(self):
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)
        self.db = sessionmaker(bind=engine)()
        session = models.Session(topic="test"); self.db.add(session); self.db.flush()
        utterance = models.Utterance(session_id=session.id, stt_text="学校で行きます。")
        self.db.add(utterance); self.db.flush()
        judgment = models.JudgmentResult(
            utterance_id=utterance.id, decision="needs_correction", corrected_text="学校に行きます。",
            edits="[]", error_types=json.dumps(["particle_misuse"]), reason_ko="조사",
            classification_review_required=False, strategy="d_only", model_name="judge",
            adapter_name="D", selection_reason="D", contract_version="judgment-v0.2",
            learner_level="N5")
        self.db.add(judgment); self.db.flush()
        self.job = models.FeedbackAuditJob(
            judgment_id=judgment.id, feedback_model="feedback", feedback_adapter="v1",
            feedback_model_hash="a" * 64, contract_version="feedback-v0.1", status="pending",
            attempts=0, next_attempt_at=__import__("datetime").datetime.now(__import__("datetime").timezone.utc))
        self.db.add(self.job); self.db.commit()

    def tearDown(self): self.db.close()

    def test_success_stores_audit_without_changing_judgment(self):
        original = self.db.get(models.JudgmentResult, self.job.judgment_id).corrected_text
        def runner(*args, **kwargs):
            return {"verdict": "agree", "issue_codes": [], "recommended_judgment": None,
                    "review_reason_ko": "타당합니다.", "latency_ms": 4.0}
        self.assertTrue(process_one(self.db, runner=runner))
        self.assertEqual(self.db.get(models.FeedbackAuditJob, self.job.id).status, "succeeded")
        self.assertEqual(self.db.query(models.FeedbackAudit).count(), 1)
        self.assertEqual(self.db.get(models.JudgmentResult, self.job.judgment_id).corrected_text, original)

    def test_worker_passes_job_contract_version_to_runner(self):
        job = self.db.get(models.FeedbackAuditJob, self.job.id)
        job.contract_version = "feedback-two-stage-v0.1"
        self.db.commit()
        seen = {}
        def runner(*args, **kwargs):
            seen.update(kwargs)
            return {"verdict": "agree", "issue_codes": [], "recommended_judgment": None,
                    "review_reason_ko": "타당합니다.", "latency_ms": 4.0}
        process_one(self.db, runner=runner)
        self.assertEqual(seen["contract_version"], "feedback-two-stage-v0.1")
        audit = self.db.query(models.FeedbackAudit).one()
        self.assertEqual(audit.contract_version, "feedback-two-stage-v0.1")

    def test_failure_retries_then_stays_failed(self):
        def runner(*args, **kwargs): raise FeedbackServiceError("contract")
        for expected in ("pending", "pending", "failed"):
            job = self.db.get(models.FeedbackAuditJob, self.job.id)
            job.next_attempt_at = __import__("datetime").datetime.now(__import__("datetime").timezone.utc)
            self.db.commit()
            process_one(self.db, runner=runner)
            self.assertEqual(self.db.get(models.FeedbackAuditJob, self.job.id).status, expected)
        self.assertEqual(self.db.query(models.FeedbackAudit).count(), 0)

    def test_stage_contract_category_is_preserved_for_retry(self):
        def runner(*args, **kwargs): raise FeedbackServiceError("contract_stage2")
        process_one(self.db, runner=runner)
        job = self.db.get(models.FeedbackAuditJob, self.job.id)
        self.assertEqual(job.status, "pending")
        self.assertEqual(job.error_category, "contract_stage2")


if __name__ == "__main__": unittest.main()
