"""Regression checks for LLM response validation, without external services."""

import json
import unittest

from analyzer.llm_parser import (
    REQUIRED_FIELDS,
    normalize_llm_result,
    parse_llm_response,
)


ORIGINAL_TEXT = "学校を行きます。"
CORRECTED_TEXT = "学校に行きます。"
MODEL_NAME = "test-model"
ADAPTER_NAME = "test-adapter"


class LLMParserTests(unittest.TestCase):
    def valid_payload(self, **overrides):
        payload = {
            "is_correct": False,
            "corrected_text": CORRECTED_TEXT,
            "error_types": ["particle_misuse"],
            "feedback_ko": "이동 목적지에는 조사 に를 사용합니다.",
            "feedback_ja": "移動先には助詞「に」を使います。",
            "confidence": 0.85,
        }
        payload.update(overrides)
        return payload

    def parse(self, payload, original_text=ORIGINAL_TEXT):
        raw_text = json.dumps(payload, ensure_ascii=False)
        return parse_llm_response(
            raw_text,
            original_text,
            model_name=MODEL_NAME,
            adapter_name=ADAPTER_NAME,
        )

    def assert_fallback(self, result, original_text=ORIGINAL_TEXT, field=None):
        self.assertIs(result["parse_success"], False)
        self.assertIsNone(result["is_correct"])
        self.assertEqual(result["confidence"], 0.0)
        self.assertEqual(result["corrected_text"], original_text)
        self.assertEqual(result["error_types"], [])
        self.assertIsInstance(result["parse_error"], str)
        self.assertTrue(result["parse_error"].strip())
        self.assertIn(result["parse_error"], result["feedback_ko"])
        if field is not None:
            self.assertIn(field, result["parse_error"])

    def assert_success(self, result):
        self.assertIs(result["parse_success"], True)
        self.assertIsNone(result["parse_error"])
        self.assertEqual(result["model_name"], MODEL_NAME)
        self.assertEqual(result["adapter_name"], ADAPTER_NAME)

    def test_empty_and_partial_objects_use_fallback(self):
        for payload in (
            {},
            {"is_correct": True},
            {"corrected_text": ORIGINAL_TEXT},
            {"is_correct": True, "corrected_text": ORIGINAL_TEXT},
            {"unrelated": "not an analysis result"},
        ):
            with self.subTest(payload=payload):
                result = self.parse(payload)

                self.assert_fallback(result)
                self.assertEqual(result["model_name"], MODEL_NAME)
                self.assertEqual(result["adapter_name"], ADAPTER_NAME)
                self.assertEqual(
                    result["raw_text"], json.dumps(payload, ensure_ascii=False)
                )

    def test_each_required_field_is_checked(self):
        self.assertEqual(
            REQUIRED_FIELDS,
            {
                "is_correct", "corrected_text", "error_types",
                "feedback_ko", "feedback_ja", "confidence",
            },
        )
        for field in sorted(REQUIRED_FIELDS):
            with self.subTest(field=field):
                payload = self.valid_payload()
                del payload[field]

                self.assert_fallback(self.parse(payload), field=field)

    def test_unknown_correctness_cannot_be_inferred_from_text(self):
        for value in (None, "", " \t", "maybe", 0, 1, [], {}):
            for corrected_text in (ORIGINAL_TEXT, CORRECTED_TEXT):
                with self.subTest(value=value, corrected_text=corrected_text):
                    result = self.parse(self.valid_payload(
                        is_correct=value, corrected_text=corrected_text
                    ))

                    self.assert_fallback(result, field="is_correct")

    def test_missing_or_invalid_correction_cannot_default_to_original(self):
        for value in (None, "", " \t\n\u3000", 0, 1, False, [], {}):
            with self.subTest(value=value):
                result = self.parse(self.valid_payload(corrected_text=value))

                self.assert_fallback(result, field="corrected_text")

    def test_feedback_fields_must_be_strings(self):
        for field in ("feedback_ko", "feedback_ja"):
            for value in (None, 0, False, [], {}):
                with self.subTest(field=field, value=value):
                    result = self.parse(self.valid_payload(**{field: value}))

                    self.assert_fallback(result, field=field)

    def test_error_types_must_be_a_string_or_a_list_of_strings(self):
        for value in (None, 0, False, {}, [None], [1], ["particle_misuse", {}]):
            with self.subTest(value=value):
                result = self.parse(self.valid_payload(error_types=value))

                self.assert_fallback(result, field="error_types")

    def test_confidence_must_be_finite_and_numeric(self):
        for value in (
            None, "", " \t", "high", True, False, [], {},
            "NaN", "Infinity", "-Infinity", "1e10000", 10 ** 400,
            float("nan"), float("inf"), float("-inf"),
        ):
            with self.subTest(value=value):
                result = self.parse(self.valid_payload(confidence=value))

                self.assert_fallback(result, field="confidence")

    def test_direct_normalization_also_validates_required_fields_and_values(self):
        payloads = [{}, {"is_correct": True}]
        for field in sorted(REQUIRED_FIELDS):
            payload = self.valid_payload()
            del payload[field]
            payloads.append(payload)
        payloads.extend((
            self.valid_payload(is_correct=None),
            self.valid_payload(is_correct="unknown"),
            self.valid_payload(corrected_text=None),
            self.valid_payload(corrected_text=" \n"),
            self.valid_payload(corrected_text=123),
            self.valid_payload(feedback_ko=None),
            self.valid_payload(feedback_ja=[]),
            self.valid_payload(error_types=[None]),
            self.valid_payload(confidence=True),
            self.valid_payload(confidence=float("nan")),
        ))
        for payload in payloads:
            with self.subTest(payload=payload):
                raw_text = json.dumps(payload, ensure_ascii=False)
                result = normalize_llm_result(
                    payload, ORIGINAL_TEXT, raw_text,
                    model_name=MODEL_NAME, adapter_name=ADAPTER_NAME,
                )

                self.assert_fallback(result)
                self.assertEqual(result["raw_text"], raw_text)
                self.assertEqual(result["model_name"], MODEL_NAME)
                self.assertEqual(result["adapter_name"], ADAPTER_NAME)

    def test_direct_normalization_rejects_non_objects(self):
        for payload in (None, [], "not an object", True, 1):
            with self.subTest(payload=payload):
                raw_text = json.dumps(payload)
                result = normalize_llm_result(payload, ORIGINAL_TEXT, raw_text)

                self.assert_fallback(result)
                self.assertEqual(result["raw_text"], raw_text)

    def test_complete_correct_response_is_preserved(self):
        payload = self.valid_payload(
            is_correct=True, corrected_text=CORRECTED_TEXT, error_types=[],
            feedback_ko="자연스러운 일본어입니다.",
            feedback_ja="自然な日本語です。",
        )

        result = self.parse(payload, original_text=CORRECTED_TEXT)

        self.assert_success(result)
        for field in REQUIRED_FIELDS:
            self.assertEqual(result[field], payload[field])

    def test_complete_incorrect_response_is_preserved(self):
        payload = self.valid_payload()

        result = self.parse(payload)

        self.assert_success(result)
        for field in REQUIRED_FIELDS:
            self.assertEqual(result[field], payload[field])

    def test_code_fences_and_surrounding_explanation_remain_supported(self):
        raw_json = json.dumps(self.valid_payload(), ensure_ascii=False)
        for raw_text in (
            raw_json,
            f"```json\n{raw_json}\n```",
            f"```\n{raw_json}\n```",
            f"결과는 다음과 같습니다.\n{raw_json}\n분석을 마쳤습니다.",
        ):
            with self.subTest(raw_text=raw_text):
                result = parse_llm_response(
                    raw_text, ORIGINAL_TEXT,
                    model_name=MODEL_NAME, adapter_name=ADAPTER_NAME,
                )

                self.assert_success(result)
                self.assertIs(result["is_correct"], False)
                self.assertEqual(result["corrected_text"], CORRECTED_TEXT)
                self.assertEqual(result["raw_text"], raw_text)

    def test_recognized_boolean_strings_remain_supported(self):
        for value, expected in (
            ("true", True), (" YES ", True), ("correct", True),
            ("정답", True), ("맞음", True),
            ("false", False), (" NO ", False), ("incorrect", False),
            ("오답", False), ("틀림", False),
        ):
            with self.subTest(value=value):
                original_text = CORRECTED_TEXT if expected else ORIGINAL_TEXT
                payload = self.valid_payload(
                    is_correct=value, error_types=[] if expected else ["particle_misuse"]
                )

                result = self.parse(payload, original_text=original_text)

                self.assert_success(result)
                self.assertIs(result["is_correct"], expected)

    def test_numeric_confidence_and_clamping_remain_supported(self):
        for value, expected in (
            (0, 0.0), (1, 1.0), (0.75, 0.75), ("0.85", 0.85),
            (-0.5, 0.0), (1.5, 1.0),
        ):
            with self.subTest(value=value):
                result = self.parse(self.valid_payload(confidence=value))

                self.assert_success(result)
                self.assertEqual(result["confidence"], expected)

    def test_error_type_array_and_string_coercion_remain_supported(self):
        expected = ["particle_misuse", "unnatural_expression"]
        for value in (
            expected,
            '["particle_misuse", "unnatural_expression"]',
            "particle_misuse, unnatural_expression",
        ):
            with self.subTest(value=value):
                result = self.parse(self.valid_payload(error_types=value))

                self.assert_success(result)
                self.assertEqual(result["error_types"], expected)

    def test_empty_feedback_and_error_types_remain_supported(self):
        for error_types in ([], "", " \t", "[]"):
            with self.subTest(error_types=error_types):
                result = self.parse(self.valid_payload(
                    is_correct=True, corrected_text=CORRECTED_TEXT,
                    error_types=error_types, feedback_ko="", feedback_ja="",
                ), original_text=CORRECTED_TEXT)

                self.assert_success(result)
                self.assertIs(result["is_correct"], True)
                self.assertEqual(result["error_types"], [])
                self.assertEqual(result["feedback_ko"], "")
                self.assertEqual(result["feedback_ja"], "")

    def test_original_correction_comparison_policy_is_preserved(self):
        # These are complete responses; comparison still reconciles the LLM's
        # contradictory correctness claim as before this validation fix.
        changed = self.parse(self.valid_payload(is_correct=True))
        unchanged = self.parse(self.valid_payload(corrected_text=ORIGINAL_TEXT))

        self.assert_success(changed)
        self.assertIs(changed["is_correct"], False)
        self.assert_success(unchanged)
        self.assertIs(unchanged["is_correct"], True)
        self.assertEqual(unchanged["error_types"], [])

    def test_empty_non_json_and_malformed_responses_keep_fallback(self):
        for raw_text in (
            None, "", " \n", "분석할 수 없습니다.", "[]", "null",
            '{"is_correct":', '{"is_correct": false,}',
        ):
            with self.subTest(raw_text=raw_text):
                result = parse_llm_response(raw_text, ORIGINAL_TEXT)

                self.assert_fallback(result)
                self.assertEqual(result["raw_text"], raw_text or "")


if __name__ == "__main__":
    unittest.main()
