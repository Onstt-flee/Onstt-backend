import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from evaluation.judgment.dataset import DEFAULT_DATASET, load_records, model_inputs
from evaluation.judgment.runner import (
    PROMPT_VERSION_V2,
    SYSTEM_PROMPT_V2,
    build_request,
    parse_model_output,
    run_evaluation,
)
from evaluation.judgment.scorer import load_verified_run, score_verified_run


class JudgmentContractV02Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.records = load_records()
        cls.inputs = model_inputs(cls.records)

    def test_prompt_requests_position_free_contract(self):
        request = build_request(
            self.inputs[0]["input"], "test/model",
            prompt_version=PROMPT_VERSION_V2,
        )
        self.assertEqual(request["messages"][0]["content"], SYSTEM_PROMPT_V2)
        self.assertIn('"error_types"', SYSTEM_PROMPT_V2)
        self.assertNotIn('"start"', SYSTEM_PROMPT_V2)
        self.assertNotIn('"edits"', SYSTEM_PROMPT_V2)

    def test_backend_builds_unicode_diff(self):
        raw = json.dumps({
            "decision": "needs_correction",
            "corrected_text": "学校に行きます。",
            "error_types": ["particle_misuse"],
            "reason_ko": "목적지 조사를 최소 교정합니다.",
        }, ensure_ascii=False)
        parsed, error = parse_model_output(
            raw, "学校を行きます。", PROMPT_VERSION_V2
        )
        self.assertIsNone(error)
        self.assertEqual(parsed["edits"], [{
            "start": 2,
            "end": 3,
            "source": "を",
            "replacement": "に",
            "error_type": "particle_misuse",
        }])
        self.assertFalse(parsed["classification_review_required"])

    def test_type_diff_mismatch_is_reviewable_not_contract_failure(self):
        raw = json.dumps({
            "decision": "needs_correction",
            "corrected_text": "友達の家に行きました。",
            "error_types": ["particle_misuse", "verb_conjugation", "tense_mismatch"],
            "reason_ko": "조사와 활용을 최소 교정합니다.",
        }, ensure_ascii=False)
        parsed, error = parse_model_output(
            raw, "友達の家で行くました。", PROMPT_VERSION_V2
        )
        self.assertIsNone(error)
        self.assertTrue(parsed["classification_review_required"])
        self.assertEqual(len(parsed["edits"]), 2)
        self.assertEqual(parsed["corrected_text"], "友達の家に行きました。")

    def test_noncorrection_preserves_input_and_has_no_types(self):
        valid = json.dumps({
            "decision": "acceptable",
            "corrected_text": "まだです。",
            "error_types": [],
            "reason_ko": "문맥상 완결된 응답입니다.",
        }, ensure_ascii=False)
        parsed, error = parse_model_output(valid, "まだです。", PROMPT_VERSION_V2)
        self.assertIsNone(error)
        self.assertEqual(parsed["edits"], [])
        invalid = json.dumps({
            "decision": "acceptable",
            "corrected_text": "まだです。",
            "error_types": ["particle_misuse"],
            "reason_ko": "허용",
        }, ensure_ascii=False)
        parsed, error = parse_model_output(invalid, "まだです。", PROMPT_VERSION_V2)
        self.assertIsNone(parsed)
        self.assertIn("must not contain", error)

    def test_v02_run_is_verified_and_scored(self):
        def transport(**kwargs):
            model_input = json.loads(
                kwargs["request_body"]["messages"][1]["content"]
            )
            raw = json.dumps({
                "decision": "acceptable",
                "corrected_text": model_input["text"],
                "error_types": [],
                "reason_ko": "문법 교정이 필요하지 않습니다.",
            }, ensure_ascii=False)
            return {
                "transport_success": True,
                "http_status": 200,
                "raw_text": raw,
                "raw_response": json.dumps({"choices": []}),
                "usage": None,
                "error": None,
                "latency_ms": 1.0,
            }

        with TemporaryDirectory() as directory:
            output = Path(directory) / "v02.jsonl"
            manifest = run_evaluation(
                dataset_path=DEFAULT_DATASET,
                endpoint="http://127.0.0.1:1234/v1/chat/completions",
                model="test/v02",
                output_path=output,
                limit=1,
                prompt_version=PROMPT_VERSION_V2,
                transport=transport,
            )
            self.assertEqual(manifest["prompt_version"], PROMPT_VERSION_V2)
            verified = load_verified_run(output)
            report = score_verified_run(verified)
            self.assertEqual(report["metrics"]["json_contract_success_rate"]["numerator"], 1)


if __name__ == "__main__":
    unittest.main()
