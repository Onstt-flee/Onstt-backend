"""Tests for the isolated, rejected v0.2.1 prompt experiment."""

import json
import unittest

from evaluation.judgment import runner
from evaluation.judgment.prompt_v021 import (
    PROMPT_VERSION_V21,
    SYSTEM_PROMPT_V21,
    activated_prompt,
)


class JudgmentPromptV021Tests(unittest.TestCase):
    def test_experimental_prompt_is_isolated_and_reuses_v02_contract(self):
        self.assertNotIn(PROMPT_VERSION_V21, runner.PROMPTS)
        with activated_prompt():
            request = runner.build_request(
                {"text": "まだです。", "context": None, "learner_level": "N5"},
                "test/model",
                prompt_version=PROMPT_VERSION_V21,
            )
            self.assertEqual(request["messages"][0]["content"], SYSTEM_PROMPT_V21)
            self.assertIn("문자 단위로 정확히 복사", SYSTEM_PROMPT_V21)
            raw = json.dumps({
                "decision": "insufficient_evidence",
                "corrected_text": "まだです。",
                "error_types": [],
                "reason_ko": "판단 근거가 부족합니다.",
            }, ensure_ascii=False)
            parsed, error = runner.parse_model_output(
                raw, "まだです。", PROMPT_VERSION_V21
            )
            self.assertIsNone(error)
            self.assertEqual(parsed["corrected_text"], "まだです。")
        self.assertNotIn(PROMPT_VERSION_V21, runner.PROMPTS)
        self.assertEqual(runner.PROMPT_VERSION_V2, "judgment-v0.2")


if __name__ == "__main__":
    unittest.main()
