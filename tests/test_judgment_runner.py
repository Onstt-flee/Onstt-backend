"""Tests for the label-free offline judgment runner."""

from copy import deepcopy
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from evaluation.judgment.dataset import DEFAULT_DATASET, load_records, model_inputs
from evaluation.judgment.runner import (
    PROMPT_VERSION,
    SYSTEM_PROMPT,
    _artifact_paths,
    build_messages,
    build_request,
    call_endpoint,
    parse_model_output,
    run_evaluation,
)


class FakeResponse:
    def __init__(self, payload, status=200):
        self.payload = payload.encode("utf-8")
        self.status = status

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self):
        return self.payload

    def getcode(self):
        return self.status


class JudgmentRunnerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.records = load_records()
        cls.exported = model_inputs(cls.records)

    def test_messages_are_built_from_allowlisted_input_only(self):
        record = deepcopy(self.records[24])
        record["expected"]["reason_ko"] = "SECRET_GOLD_REASON"
        record["accepted_corrections"].append("SECRET_GOLD_CORRECTION")
        exported = model_inputs([record])[0]
        request = build_request(exported["input"], "test/model")
        serialized = json.dumps(request, ensure_ascii=False)
        self.assertNotIn(record["id"], serialized)
        self.assertNotIn("SECRET_GOLD_REASON", serialized)
        self.assertNotIn("SECRET_GOLD_CORRECTION", serialized)
        self.assertNotIn("expected", serialized)
        self.assertNotIn("accepted_corrections", serialized)
        self.assertEqual(
            json.loads(request["messages"][1]["content"]),
            record["input"],
        )

    def test_message_and_generation_validation(self):
        valid = self.exported[0]["input"]
        self.assertEqual(build_messages(valid)[0]["content"], SYSTEM_PROMPT)
        invalid_inputs = [
            {**valid, "answer": "leak"},
            {**valid, "text": None},
            {**valid, "context": []},
            {**valid, "learner_level": "N1"},
        ]
        for value in invalid_inputs:
            with self.subTest(value=value), self.assertRaises(ValueError):
                build_messages(value)
        for kwargs in (
            {"temperature": -0.1},
            {"temperature": 2.1},
            {"top_p": 0},
            {"top_p": 1.1},
            {"max_tokens": 0},
            {"max_tokens": True},
        ):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                build_request(valid, "test/model", **kwargs)

    def test_strict_parser_accepts_contract_and_rejects_repairs(self):
        record = self.records[24]
        raw = json.dumps(record["expected"], ensure_ascii=False)
        parsed, error = parse_model_output(raw, record["input"]["text"])
        self.assertEqual(parsed, record["expected"])
        self.assertIsNone(error)
        invalid = [
            f"```json\n{raw}\n```",
            '{"decision":"acceptable","decision":"needs_correction"}',
            '{"decision":NaN}',
            "[]",
            "",
        ]
        for value in invalid:
            with self.subTest(value=value):
                parsed, error = parse_model_output(
                    value,
                    record["input"]["text"],
                )
                self.assertIsNone(parsed)
                self.assertTrue(error)

    def test_openai_envelope_is_preserved_and_content_extracted(self):
        judgment = self.records[0]["expected"]
        envelope = {
            "choices": [{
                "message": {
                    "content": json.dumps(judgment, ensure_ascii=False),
                },
            }],
            "usage": {"prompt_tokens": 10, "completion_tokens": 20},
        }
        captured = {}

        def opener(request, timeout):
            captured["request"] = request
            captured["timeout"] = timeout
            return FakeResponse(json.dumps(envelope, ensure_ascii=False))

        result = call_endpoint(
            endpoint="http://127.0.0.1:1234/v1/chat/completions",
            request_body=build_request(
                self.exported[0]["input"],
                "test/model",
            ),
            timeout=3,
            api_key="secret-token",
            opener=opener,
        )
        self.assertTrue(result["transport_success"])
        self.assertEqual(json.loads(result["raw_response"]), envelope)
        self.assertEqual(json.loads(result["raw_text"]), judgment)
        self.assertEqual(result["usage"]["completion_tokens"], 20)
        self.assertEqual(captured["timeout"], 3)
        self.assertEqual(
            captured["request"].get_header("Authorization"),
            "Bearer secret-token",
        )
        self.assertNotIn("secret-token", json.dumps(result))

    def test_invalid_server_envelope_is_a_transport_failure(self):
        result = call_endpoint(
            endpoint="http://127.0.0.1:1234/v1/chat/completions",
            request_body=build_request(
                self.exported[0]["input"],
                "test/model",
            ),
            timeout=3,
            opener=lambda *_args, **_kwargs: FakeResponse('{"choices":[]}'),
        )
        self.assertFalse(result["transport_success"])
        self.assertIn("Invalid server response", result["error"])
        self.assertEqual(result["raw_response"], '{"choices":[]}')

    def test_complete_run_writes_atomic_label_free_artifacts(self):
        calls = []

        def transport(**kwargs):
            calls.append(kwargs)
            model_input = json.loads(
                kwargs["request_body"]["messages"][1]["content"]
            )
            if len(calls) == 2:
                return {
                    "transport_success": False,
                    "http_status": None,
                    "raw_text": "",
                    "raw_response": "",
                    "usage": None,
                    "error": "offline",
                    "latency_ms": 1.0,
                }
            judgment = {
                "decision": "acceptable",
                "corrected_text": model_input["text"],
                "edits": [],
                "reason_ko": "문법 교정이 필요하지 않습니다.",
            }
            raw = json.dumps(judgment, ensure_ascii=False)
            return {
                "transport_success": True,
                "http_status": 200,
                "raw_text": raw,
                "raw_response": json.dumps({"choices": []}),
                "usage": None,
                "error": None,
                "latency_ms": 2.0,
            }

        with TemporaryDirectory() as directory:
            output = Path(directory) / "run.jsonl"
            manifest = run_evaluation(
                dataset_path=DEFAULT_DATASET,
                endpoint="http://127.0.0.1:1234/v1/chat/completions",
                model="test/model",
                output_path=output,
                limit=2,
                api_key="secret-token",
                transport=transport,
            )
            rows = [
                json.loads(line)
                for line in output.read_text().splitlines()
            ]
            partial, manifest_path = _artifact_paths(output)
            stored_manifest = json.loads(manifest_path.read_text())
            self.assertFalse(partial.exists())
            self.assertEqual(
                [row["id"] for row in rows],
                ["JG-001", "JG-002"],
            )
            self.assertEqual(manifest["input_count"], 2)
            self.assertEqual(manifest["transport_success_count"], 1)
            self.assertEqual(manifest["transport_failure_count"], 1)
            self.assertEqual(manifest["contract_valid_count"], 1)
            self.assertEqual(stored_manifest, manifest)
            self.assertEqual(manifest["prompt_version"], PROMPT_VERSION)
            self.assertNotIn("secret-token", output.read_text())
            self.assertNotIn("secret-token", manifest_path.read_text())
            for row in rows:
                serialized = json.dumps(
                    row["request"],
                    ensure_ascii=False,
                )
                self.assertNotIn("expected", serialized)
                self.assertNotIn("accepted_corrections", serialized)
                self.assertNotIn(row["id"], serialized)
            with self.assertRaises(FileExistsError):
                run_evaluation(
                    dataset_path=DEFAULT_DATASET,
                    endpoint="http://127.0.0.1:1234/v1/chat/completions",
                    model="test/model",
                    output_path=output,
                    limit=1,
                    transport=transport,
                )

    def test_selection_and_endpoint_guards(self):
        with TemporaryDirectory() as directory:
            common = {
                "dataset_path": DEFAULT_DATASET,
                "model": "test/model",
                "output_path": Path(directory) / "run.jsonl",
                "transport": lambda **_kwargs: {},
            }
            for override in (
                {"endpoint": "file:///tmp/server"},
                {
                    "endpoint":
                        "http://user:password@localhost:1234/v1/chat/completions",
                },
                {
                    "endpoint":
                        "http://localhost:1234/v1/chat/completions?token=secret",
                },
                {"endpoint": "http://localhost:1234", "limit": 0},
                {
                    "endpoint": "http://localhost:1234",
                    "selected_ids": ["JG-999"],
                },
                {
                    "endpoint": "http://localhost:1234",
                    "selected_ids": ["JG-001", "JG-001"],
                },
            ):
                with (
                    self.subTest(override=override),
                    self.assertRaises(ValueError),
                ):
                    run_evaluation(**common, **override)


if __name__ == "__main__":
    unittest.main()
