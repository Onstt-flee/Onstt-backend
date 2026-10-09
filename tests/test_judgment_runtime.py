import json
import os
import threading
import unittest
from unittest.mock import patch

from analyzer.judgment_runtime import (
    JudgmentOverloadedError,
    JudgmentShuttingDownError,
    readiness_snapshot,
    reserve_capacity,
    reset_for_tests,
    runtime_snapshot,
    set_accepting,
    wait_for_idle,
)


class Response:
    def __init__(self, payload=None):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self):
        return b"" if self.payload is None else json.dumps(self.payload).encode()


class JudgmentRuntimeTests(unittest.TestCase):
    def setUp(self):
        reset_for_tests()

    def tearDown(self):
        reset_for_tests()

    def test_capacity_rejects_immediately_and_releases_slot(self):
        entered = threading.Event()
        release = threading.Event()

        def hold():
            with reserve_capacity():
                entered.set()
                release.wait(1)

        with patch.dict(os.environ, {
            "JUDGMENT_MAX_CONCURRENCY": "1",
            "JUDGMENT_QUEUE_TIMEOUT_SECONDS": "0",
        }, clear=True):
            worker = threading.Thread(target=hold)
            worker.start()
            self.assertTrue(entered.wait(1))
            with self.assertRaises(JudgmentOverloadedError):
                with reserve_capacity():
                    pass
            self.assertEqual(runtime_snapshot()["active_requests"], 1)
            release.set()
            worker.join(1)
            self.assertTrue(wait_for_idle(0.1))
            with reserve_capacity():
                self.assertEqual(runtime_snapshot()["active_requests"], 1)

    def test_shutdown_rejects_new_work_and_drains_existing(self):
        entered = threading.Event()
        release = threading.Event()

        def hold():
            with reserve_capacity():
                entered.set()
                release.wait(1)

        with patch.dict(os.environ, {"JUDGMENT_MAX_CONCURRENCY": "1"}, clear=True):
            worker = threading.Thread(target=hold)
            worker.start()
            self.assertTrue(entered.wait(1))
            set_accepting(False)
            with self.assertRaises(JudgmentShuttingDownError):
                with reserve_capacity():
                    pass
            self.assertFalse(wait_for_idle(0))
            release.set()
            worker.join(1)
            self.assertTrue(wait_for_idle(0.1))

    def test_readiness_is_fail_closed_and_content_free(self):
        environment = {
            "JUDGMENT_ENABLED": "true",
            "JUDGMENT_ENDPOINT": "http://127.0.0.1:1234/v1/chat/completions",
            "JUDGMENT_MODEL": "judgment-v02d",
        }

        def opener(request, timeout):
            self.assertEqual(timeout, 2.0)
            if request.full_url.endswith("/health"):
                return Response()
            return Response({"data": [{"id": "judgment-v02d"}]})

        with patch.dict(os.environ, environment, clear=True):
            ready = readiness_snapshot(opener=opener)
            self.assertTrue(ready["ready"])
            self.assertEqual(ready["reason"], "ready")
            self.assertFalse(ready["contains_request_content"])
            missing = readiness_snapshot(
                opener=lambda *_args, **_kwargs: Response({"data": []})
            )
            self.assertFalse(missing["ready"])
        self.assertNotIn("endpoint", json.dumps(ready))


if __name__ == "__main__":
    unittest.main()
