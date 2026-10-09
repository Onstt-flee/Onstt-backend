import io
import json
import unittest

from scripts.run_judgment_staging_load import run_phase, run_probe


class Response:
    status = 200

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self):
        return json.dumps({
            "decision": "acceptable",
            "corrected_text": "synthetic",
            "edits": [],
            "error_types": [],
            "reason_ko": "synthetic",
            "strategy": "d_only",
            "model_name": "judgment-v02d",
            "adapter_name": "adapter",
            "selection_reason": "test",
            "contract_version": "judgment-v0.2",
            "latency_ms": 1.0,
            "created_at": "2026-10-06T00:00:00Z",
        }).encode()


class JudgmentStagingLoadTests(unittest.TestCase):
    def test_phase_aggregates_without_returning_content(self):
        result = run_phase(
            api_base="http://127.0.0.1:8001",
            utterance_ids=[1, 2],
            concurrency=2,
            request_count=4,
            timeout=1,
            opener=lambda *_args, **_kwargs: Response(),
        )
        self.assertEqual(result["success_count"], 4)
        self.assertEqual(result["contract_valid_count"], 4)
        self.assertNotIn("corrected_text", json.dumps(result))

    def test_probe_is_content_free_and_has_stable_plan_hash(self):
        kwargs = dict(
            api_base="http://127.0.0.1:8001",
            utterance_ids=[10, 11],
            phases=[(1, 2), (2, 2)],
            timeout=1,
            opener=lambda *_args, **_kwargs: Response(),
        )
        first = run_probe(**kwargs)
        second = run_probe(**kwargs)
        self.assertEqual(first["input_plan_sha256"], second["input_plan_sha256"])
        self.assertEqual(first["total_requests"], 4)
        self.assertTrue(first["contains_request_or_response_content"] is False)


if __name__ == "__main__":
    unittest.main()
