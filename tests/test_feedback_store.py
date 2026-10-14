import json
import os
import unittest
from unittest.mock import patch

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import models
from analyzer import feedback_store
from database import Base


HASH = "a" * 64


class FeedbackStoreTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        self.db = sessionmaker(bind=self.engine)()
        session = models.Session(topic="test")
        self.db.add(session); self.db.flush()
        utterance = models.Utterance(session_id=session.id, stt_text="学校で行きます。")
        self.db.add(utterance); self.db.flush()
        self.judgment = models.JudgmentResult(
            utterance_id=utterance.id, decision="needs_correction", corrected_text="学校に行きます。",
            edits="[]", error_types=json.dumps(["particle_misuse"]), reason_ko="조사 오류",
            classification_review_required=False, strategy="d_only", model_name="judgment-v02d",
            adapter_name="v0.2-D", selection_reason="D", contract_version="judgment-v0.2",
            context=None, learner_level="N5")
        self.db.add(self.judgment); self.db.flush()

    def tearDown(self):
        self.db.close()

    def _env(self, enabled="true"):
        return patch.dict(os.environ, {"FEEDBACK_AUDIT_ENABLED": enabled,
            "FEEDBACK_MODEL_SHA256": HASH, "FEEDBACK_ADMIN_TOKEN": "x" * 32,
            "EDGE_MODE": "false"}, clear=False)

    def test_gpu_provenance_and_job_are_created_together(self):
        with self._env():
            feedback_store.record_gpu_judgment(self.db, self.judgment, {}); self.db.commit()
        self.assertEqual(self.db.get(models.JudgmentProvenance, self.judgment.id).runtime, "gpu_bf16")
        self.assertEqual(self.db.query(models.FeedbackAuditJob).count(), 1)

    def test_disabled_still_records_provenance_without_job(self):
        with self._env("false"):
            feedback_store.record_gpu_judgment(self.db, self.judgment, {}); self.db.commit()
        self.assertIsNotNone(self.db.get(models.JudgmentProvenance, self.judgment.id))
        self.assertEqual(self.db.query(models.FeedbackAuditJob).count(), 0)

    def test_edge_enqueue_is_idempotent(self):
        payload = {"quantization": "Q5_K_M", "model_sha256": "b" * 64, "adapter_sha256": "c" * 64}
        with self._env():
            feedback_store.record_edge_judgment(self.db, self.judgment, "node", payload)
            self.db.flush()
            feedback_store.record_edge_judgment(self.db, self.judgment, "node", payload)
            self.db.commit()
        self.assertEqual(self.db.query(models.JudgmentProvenance).count(), 1)
        self.assertEqual(self.db.query(models.FeedbackAuditJob).count(), 1)

    def test_invalid_enabled_configuration_never_breaks_judgment(self):
        with patch.dict(os.environ, {"FEEDBACK_AUDIT_ENABLED": "true",
            "FEEDBACK_MODEL_SHA256": "bad", "FEEDBACK_ADMIN_TOKEN": "x" * 32,
            "EDGE_MODE": "false"}, clear=False):
            feedback_store.record_gpu_judgment(self.db, self.judgment, {}); self.db.commit()
        self.assertEqual(self.db.query(models.FeedbackAuditJob).count(), 0)


if __name__ == "__main__":
    unittest.main()
