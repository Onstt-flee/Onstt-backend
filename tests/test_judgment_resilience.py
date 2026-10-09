"""Concurrency and injected-failure tests for judgment staging."""

import unittest
from unittest.mock import patch

from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import crud
import main
import models
from analyzer.judgment_monitor import reset_for_tests
from analyzer.judgment_service import JudgmentServiceError
from scripts.run_judgment_resilience_probe import EXPECTED, run_probe


class JudgmentResilienceProbeTests(unittest.TestCase):
    def setUp(self):
        reset_for_tests()
        engine = create_engine(
            "sqlite://", connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        models.Base.metadata.create_all(engine)
        self.db = sessionmaker(bind=engine)()
        session = models.Session(topic="resilience")
        self.db.add(session)
        self.db.flush()
        utterance = models.Utterance(session_id=session.id, stt_text="まだです。")
        self.db.add(utterance)
        self.db.commit()
        self.utterance_id = utterance.id

    def tearDown(self):
        self.db.close()
        reset_for_tests()

    @staticmethod
    def payload():
        return {
            "decision": "acceptable",
            "corrected_text": "まだです。",
            "edits": [],
            "error_types": [],
            "reason_ko": "허용됩니다.",
            "classification_review_required": False,
            "strategy": "d_only",
            "model_name": "judgment-v02d",
            "adapter_name": "judgment-qwen3-4b-failure-focus-v0.2-d",
            "selection_reason": "primary_selected_by_holdout_v0.3",
            "contract_version": "judgment-v0.2",
            "latency_ms": 10.0,
            "context": None,
            "learner_level": "N5",
            "attempt_count": 1,
            "retry_used": False,
            "first_contract_error": None,
        }

    def assert_service_503(self, error):
        with patch.object(main, "judgment_enabled", return_value=True), patch.object(
            main, "run_judgment", side_effect=error
        ):
            with self.assertRaises(HTTPException) as raised:
                main.judge_utterance(self.utterance_id, None, self.db)
        self.assertEqual(raised.exception.status_code, 503)

    def enabled_status(self):
        with patch.dict("os.environ", {"JUDGMENT_ENABLED": "true"}, clear=True):
            return main.judgment_health_check()

    def test_concurrent_accounting_is_exact_and_content_free(self):
        result = run_probe()
        self.assertTrue(result["passed"], result["mismatches"])
        self.assertEqual(
            result["measurement_scope"],
            "monitor_accounting_only_not_model_or_api_load",
        )
        self.assertFalse(result["contains_request_content"])
        self.assertFalse(result["mutations_performed"])
        for key, expected in EXPECTED.items():
            self.assertEqual(result["metrics"][key], expected)
        self.assertEqual(result["metrics"]["operational_state"], "ready")
        self.assertEqual(result["metrics"]["latency_ms"]["sample_count"], 700)

    def test_timeout_is_503_sanitized_and_not_persisted(self):
        self.assert_service_503(
            JudgmentServiceError("private endpoint socket timed out")
        )
        status = self.enabled_status()
        self.assertEqual(status["failure_categories"], {"timeout": 1})
        self.assertNotIn("private endpoint", str(status))
        self.assertEqual(crud.get_judgments_by_utterance(self.db, self.utterance_id), [])

    def test_retry_failure_is_counted_once_and_not_persisted(self):
        self.assert_service_503(JudgmentServiceError(
            "private retry output",
            attempt_count=2,
            retry_used=True,
            first_contract_error="private contract detail",
        ))
        status = self.enabled_status()
        self.assertEqual(status["failure_total"], 1)
        self.assertEqual(status["retry_used_total"], 1)
        self.assertEqual(status["retry_recovered_total"], 0)
        self.assertEqual(
            status["failure_categories"], {"preservation_retry_failed": 1}
        )
        self.assertNotIn("private", str(status))
        self.assertEqual(crud.get_judgments_by_utterance(self.db, self.utterance_id), [])

    def test_persistence_failure_is_degraded_without_false_success(self):
        with patch.object(main, "judgment_enabled", return_value=True), patch.object(
            main, "run_judgment", return_value=self.payload()
        ), patch.object(
            main.crud, "create_judgment", side_effect=RuntimeError("db down")
        ):
            with self.assertRaisesRegex(RuntimeError, "db down"):
                main.judge_utterance(self.utterance_id, None, self.db)
        status = self.enabled_status()
        self.assertEqual(status["operational_state"], "degraded")
        self.assertEqual(status["success_total"], 0)
        self.assertEqual(status["failure_categories"], {"persistence_failure": 1})
        self.assertEqual(crud.get_judgments_by_utterance(self.db, self.utterance_id), [])


if __name__ == "__main__":
    unittest.main()
