"""Route and persistence tests for the isolated judgment API."""

import unittest
from unittest.mock import patch

from fastapi import BackgroundTasks, HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import crud
import main
import models
import schemas
from analyzer.judgment_service import JudgmentServiceError
from analyzer.judgment_monitor import reset_for_tests
from analyzer.judgment_shadow import reset_for_tests as reset_shadow


class JudgmentApiTests(unittest.TestCase):
    def setUp(self):
        reset_for_tests()
        reset_shadow()
        engine = create_engine(
            "sqlite://", connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        models.Base.metadata.create_all(engine)
        self.db = sessionmaker(bind=engine)()
        user = models.User(name="learner", level="N4")
        self.db.add(user)
        self.db.flush()
        session = models.Session(user_id=user.id, topic="test")
        self.db.add(session)
        self.db.flush()
        utterance = models.Utterance(session_id=session.id, stt_text="学校を行きます。")
        self.db.add(utterance)
        self.db.commit()
        self.utterance_id = utterance.id

    def tearDown(self):
        self.db.close()
        reset_for_tests()
        reset_shadow()

    @staticmethod
    def judgment_payload(level="N4"):
        return {
            "decision": "needs_correction",
            "corrected_text": "学校に行きます。",
            "edits": [{
                "start": 2, "end": 3, "source": "を", "replacement": "に",
                "error_type": "particle_misuse",
            }],
            "error_types": ["particle_misuse"],
            "reason_ko": "목적지 조사를 고칩니다.",
            "classification_review_required": False,
            "strategy": "d_only",
            "model_name": "judgment-v02d",
            "adapter_name": "judgment-qwen3-4b-failure-focus-v0.2-d",
            "selection_reason": "primary_selected_by_holdout_v0.3",
            "contract_version": "judgment-v0.2",
            "latency_ms": 10.0,
            "context": None,
            "learner_level": level,
            "attempt_count": 2,
            "retry_used": True,
            "first_contract_error": "test-only-internal",
        }

    def assert_http_error(self, status, function, *args, **kwargs):
        with self.assertRaises(HTTPException) as raised:
            function(*args, **kwargs)
        self.assertEqual(raised.exception.status_code, status)
        return raised.exception

    def test_missing_empty_and_disabled_guards(self):
        self.assert_http_error(404, main.judge_utterance, 999, None, self.db)
        utterance = crud.get_utterance(self.db, self.utterance_id)
        utterance.stt_text = "   "
        self.db.commit()
        self.assert_http_error(400, main.judge_utterance, self.utterance_id, None, self.db)
        utterance.stt_text = "まだです。"
        self.db.commit()
        with patch.object(main, "judgment_enabled", return_value=False):
            error = self.assert_http_error(
                503, main.judge_utterance, self.utterance_id, None, self.db
            )
        self.assertIn("disabled", error.detail)

    def test_request_level_overrides_user_level_and_result_is_persisted(self):
        payload = self.judgment_payload(level="N5")
        with patch.object(main, "judgment_enabled", return_value=True), patch.object(
            main, "run_judgment", return_value=payload
        ) as run:
            response = main.judge_utterance(
                self.utterance_id,
                schemas.JudgmentRequest(context="등교", learner_level="N5"),
                self.db,
            )
        run.assert_called_once_with(
            "学校を行きます。", context="등교", learner_level="N5"
        )
        self.assertEqual(response["decision"], "needs_correction")
        self.assertEqual(response["learner_level"], "N5")
        self.assertNotIn("confidence", response)
        self.assertNotIn("attempt_count", response)
        self.assertNotIn("retry_used", response)
        self.assertNotIn("first_contract_error", response)
        stored = main.read_utterance_judgments(self.utterance_id, self.db)
        self.assertEqual(len(stored), 1)
        self.assertEqual(stored[0]["edits"][0]["source"], "を")

    def test_user_level_then_n5_default_priority(self):
        with patch.object(main, "judgment_enabled", return_value=True), patch.object(
            main, "run_judgment", return_value=self.judgment_payload("N4")
        ) as run:
            main.judge_utterance(self.utterance_id, None, self.db)
        self.assertEqual(run.call_args.kwargs["learner_level"], "N4")

        session = models.Session(user_id=None, topic="anonymous")
        self.db.add(session)
        self.db.flush()
        utterance = models.Utterance(session_id=session.id, stt_text="まだです。")
        self.db.add(utterance)
        self.db.commit()
        payload = self.judgment_payload("N5")
        payload.update({"decision": "acceptable", "corrected_text": "まだです。",
                        "edits": [], "error_types": []})
        with patch.object(main, "judgment_enabled", return_value=True), patch.object(
            main, "run_judgment", return_value=payload
        ) as run:
            main.judge_utterance(utterance.id, schemas.JudgmentRequest(), self.db)
        self.assertEqual(run.call_args.kwargs["learner_level"], "N5")


    def test_insufficient_evidence_is_stored_as_language_judgment(self):
        payload = self.judgment_payload("N4")
        payload.update({
            "decision": "insufficient_evidence",
            "corrected_text": "学校を行きます。",
            "edits": [],
            "error_types": [],
        })
        with patch.object(main, "judgment_enabled", return_value=True), patch.object(
            main, "run_judgment", return_value=payload
        ):
            result = main.judge_utterance(self.utterance_id, None, self.db)

        self.assertEqual(result["decision"], "insufficient_evidence")
        self.assertEqual(result["edits"], [])
        self.assertEqual(self.db.query(models.JudgmentResult).one().decision,
                         "insufficient_evidence")

    def test_model_failure_is_503_and_not_persisted(self):
        with patch.object(main, "judgment_enabled", return_value=True), patch.object(
            main, "run_judgment", side_effect=JudgmentServiceError("bad contract")
        ):
            error = self.assert_http_error(
                503, main.judge_utterance, self.utterance_id, None, self.db
            )
        self.assertIn("bad contract", error.detail)
        self.assertEqual(crud.get_judgments_by_utterance(self.db, self.utterance_id), [])

    def test_existing_analyze_path_remains_separate(self):
        analysis = {
            "primary_type": "statement", "candidate_types": [],
            "classification_reason": "test", "needs_deep_analysis": True,
            "is_correct": True, "corrected_text": "学校を行きます。",
            "error_types": [], "feedback_ko": "ok", "feedback_ja": "ok",
        }
        tasks = BackgroundTasks()
        with patch.object(main, "run_analysis", return_value=analysis), patch.object(
            main, "schedule_judgment_shadow", return_value=False
        ) as schedule:
            result = main.analyze_utterance(self.utterance_id, tasks, self.db)
        self.assertEqual(result.utterance_id, self.utterance_id)
        schedule.assert_called_once_with(tasks, "学校を行きます。", "N4")
        self.assertEqual(crud.get_judgments_by_utterance(self.db, self.utterance_id), [])

    def test_openapi_exposes_isolated_judgment_contract(self):
        schema = main.app.openapi()
        self.assertIn("/health/judgment", schema["paths"])
        self.assertIn("/utterances/{utterance_id}/judgment", schema["paths"])
        self.assertIn("/utterances/{utterance_id}/judgments", schema["paths"])
        response_schema = schema["components"]["schemas"]["JudgmentResponse"]["properties"]
        self.assertNotIn("confidence", response_schema)
        self.assertIn("edits", response_schema)


    def test_monitoring_endpoint_aggregates_without_request_content(self):
        payload = self.judgment_payload("N4")
        with patch.object(main, "judgment_enabled", return_value=True), patch.object(
            main, "run_judgment", return_value=payload
        ):
            main.judge_utterance(self.utterance_id, None, self.db)

        with patch.dict("os.environ", {"JUDGMENT_ENABLED": "true"}, clear=True):
            status = main.judgment_health_check()
        self.assertEqual(status["request_total"], 1)
        self.assertEqual(status["model_invocation_total"], 1)
        self.assertEqual(status["success_total"], 1)
        self.assertEqual(status["decision_counts"], {"needs_correction": 1})
        self.assertEqual(status["retry_used_total"], 1)
        self.assertEqual(status["retry_recovered_total"], 1)
        self.assertFalse(status["contains_request_content"])
        self.assertIn("shadow", status)
        self.assertFalse(status["shadow"]["persists_results"])
        serialized = str(status)
        self.assertNotIn("学校", serialized)
        self.assertNotIn("utterance_id", serialized)


if __name__ == "__main__":
    unittest.main()
