import os
import unittest
from unittest.mock import patch

from fastapi import HTTPException, Response

import main


TOKEN = "t" * 32


class FeedbackAdminApiTests(unittest.TestCase):
    def test_requires_bearer_token(self):
        with patch.dict(os.environ, {"FEEDBACK_AUDIT_ENABLED": "true",
                "FEEDBACK_MODEL_SHA256": "a" * 64, "FEEDBACK_ADMIN_TOKEN": TOKEN}, clear=False):
            with self.assertRaises(HTTPException) as caught:
                main.require_feedback_admin(None)
        self.assertEqual(caught.exception.status_code, 401)

    def test_disabled_is_503_after_authentication(self):
        with patch.dict(os.environ, {"FEEDBACK_AUDIT_ENABLED": "false",
                "FEEDBACK_ADMIN_TOKEN": TOKEN}, clear=False):
            with self.assertRaises(HTTPException) as caught:
                main.require_feedback_admin(f"Bearer {TOKEN}")
        self.assertEqual(caught.exception.status_code, 503)

    def test_ready_when_validly_configured(self):
        with patch.dict(os.environ, {"FEEDBACK_AUDIT_ENABLED": "true",
                "FEEDBACK_MODEL_SHA256": "a" * 64, "FEEDBACK_ADMIN_TOKEN": TOKEN}, clear=False):
            self.assertIsNone(main.require_feedback_admin(f"Bearer {TOKEN}"))
            with patch.object(main, "feedback_readiness_snapshot", return_value={
                    "ready": True, "reason": "ready", "contains_request_content": False}):
                result = main.feedback_readiness(Response(), None)
        self.assertTrue(result["ready"])


if __name__ == "__main__": unittest.main()
