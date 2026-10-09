import unittest
from unittest.mock import patch

from fastapi import HTTPException, Response
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import main
import models
from analyzer.judgment_monitor import reset_for_tests as reset_monitor
from analyzer.judgment_runtime import (
    JudgmentOverloadedError,
    JudgmentRuntimeConfigurationError,
    JudgmentShuttingDownError,
    reset_for_tests as reset_runtime,
)


class JudgmentRuntimeApiTests(unittest.TestCase):
    def setUp(self):
        reset_monitor()
        reset_runtime()
        engine = create_engine(
            "sqlite://", connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        models.Base.metadata.create_all(engine)
        self.db = sessionmaker(bind=engine)()
        session = models.Session(topic="runtime")
        self.db.add(session)
        self.db.flush()
        utterance = models.Utterance(session_id=session.id, stt_text="まだです。")
        self.db.add(utterance)
        self.db.commit()
        self.utterance_id = utterance.id

    def tearDown(self):
        self.db.close()
        reset_monitor()
        reset_runtime()

    def _assert_boundary(self, error, expected_status, category):
        with patch.object(main, "judgment_enabled", return_value=True), patch.object(
            main, "reserve_capacity", side_effect=error
        ):
            with self.assertRaises(HTTPException) as raised:
                main.judge_utterance(self.utterance_id, None, self.db)
        self.assertEqual(raised.exception.status_code, expected_status)
        if expected_status == 429:
            self.assertEqual(raised.exception.headers, {"Retry-After": "1"})
        status = main.judgment_health_check()
        self.assertEqual(status["rejection_counts"], {category: 1})
        self.assertEqual(status["model_invocation_total"], 0)
        self.assertEqual(self.db.query(models.JudgmentResult).count(), 0)

    def test_overload_shutdown_and_bad_configuration_fail_before_model(self):
        cases = (
            (JudgmentOverloadedError("full"), 429, "overloaded"),
            (JudgmentShuttingDownError("draining"), 503, "shutting_down"),
            (JudgmentRuntimeConfigurationError("bad"), 503,
             "runtime_configuration"),
        )
        for error, status, category in cases:
            with self.subTest(category=category):
                reset_monitor()
                self._assert_boundary(error, status, category)

    def test_readiness_status_and_openapi_path(self):
        response = Response()
        unavailable = {
            "schema_version": "judgment-readiness-v0.1",
            "ready": False,
            "reason": "model_unavailable",
            "enabled": True,
            "accepting": True,
            "active_requests": 0,
            "max_concurrency": 4,
            "model_health": False,
            "model_alias_present": False,
            "contains_request_content": False,
        }
        with patch.object(main, "readiness_snapshot", return_value=unavailable):
            result = main.judgment_readiness_check(response)
        self.assertEqual(response.status_code, 503)
        self.assertEqual(result["reason"], "model_unavailable")
        self.assertIn("/ready/judgment", main.app.openapi()["paths"])


if __name__ == "__main__":
    unittest.main()
