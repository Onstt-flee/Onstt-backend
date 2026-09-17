import json
import unittest

from evaluation.judgment.content_diagnostics import parse_content


class JudgmentContentDiagnosticsTests(unittest.TestCase):
    def test_accepts_content_even_when_edit_offsets_are_not_checked(self):
        value = {
            "decision": "needs_correction",
            "corrected_text": "学校に行きます。",
            "edits": [{"start": 999}],
            "reason_ko": "목적지 조사 교정",
        }
        self.assertEqual(parse_content(json.dumps(value)), value)

    def test_rejects_non_json_extra_fields_and_invalid_decision(self):
        self.assertIsNone(parse_content("not json"))
        self.assertIsNone(parse_content(json.dumps({
            "decision": "acceptable",
            "corrected_text": "x",
            "edits": [],
            "reason_ko": "ok",
            "extra": True,
        })))
        self.assertIsNone(parse_content(json.dumps({
            "decision": "maybe",
            "corrected_text": "x",
            "edits": [],
            "reason_ko": "ok",
        })))


if __name__ == "__main__":
    unittest.main()
