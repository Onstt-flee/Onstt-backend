import json
import unittest

from analyzer.feedback_contract import canonical_json, parse_output
from analyzer.feedback_service import FeedbackServiceError, run_feedback
from analyzer.feedback_two_stage_contract import (
    build_stage1_request,
    build_stage2_request,
    combine_outputs,
    parse_stage1_output,
    parse_stage2_output,
    should_call_stage2,
)


TEXT = "有名店で時計があります。"
MODEL_INPUT = {
    "text": TEXT,
    "context": None,
    "learner_level": "N5",
    "judgment": {
        "decision": "acceptable",
        "corrected_text": TEXT,
        "error_types": [],
        "reason_ko": "문법적으로 허용됩니다.",
    },
}


class FeedbackTwoStageContractTests(unittest.TestCase):
    def test_stage1_is_source_blind_small_and_strict(self):
        request = build_stage1_request(MODEL_INPUT, "feedback-v06")
        self.assertEqual(request["max_tokens"], 192)
        visible = request["messages"][1]["content"]
        self.assertNotIn("runtime", visible)
        self.assertNotIn("quantization", visible)
        parsed, error = parse_stage1_output('{"verdict":"disagree","issue_codes":["false_negative"],"review_reason_ko":"오류를 놓쳤습니다."}')
        self.assertIsNone(error)
        self.assertEqual(parsed["verdict"], "disagree")
        invalid, error = parse_stage1_output('{"verdict":"agree","issue_codes":[],"review_reason_ko":"맞습니다.","extra":1}')
        self.assertIsNone(invalid)
        self.assertIn("exactly three", error)

    def test_stage1_enforces_issue_presence_by_verdict(self):
        for raw in (
            '{"verdict":"disagree","issue_codes":[],"review_reason_ko":"불일치"}',
            '{"verdict":"agree","issue_codes":["false_positive"],"review_reason_ko":"일치"}',
            '{"verdict":"unreviewable","issue_codes":["should_abstain"],"review_reason_ko":"검수 불가"}',
        ):
            parsed, error = parse_stage1_output(raw)
            self.assertIsNone(parsed)
            self.assertIsNotNone(error)

    def test_stage2_is_called_only_for_disagree(self):
        disagree = {"verdict": "disagree", "issue_codes": ["false_negative"], "review_reason_ko": "오류 누락"}
        agree = {"verdict": "agree", "issue_codes": [], "review_reason_ko": "타당함"}
        self.assertTrue(should_call_stage2(disagree))
        self.assertFalse(should_call_stage2(agree))
        request = build_stage2_request(MODEL_INPUT, disagree, "feedback-v06")
        self.assertEqual(request["max_tokens"], 384)
        with self.assertRaisesRegex(ValueError, "only after disagree"):
            build_stage2_request(MODEL_INPUT, agree, "feedback-v06")

    def test_stage2_enforces_semantic_issue_decision_rules(self):
        acceptable = {"decision": "acceptable", "corrected_text": TEXT, "error_types": [], "reason_ko": "허용 문장입니다."}
        parsed, error = parse_stage2_output(canonical_json(acceptable), TEXT, ["false_negative"])
        self.assertIsNone(parsed)
        self.assertIn("false_negative requires", error)
        corrected = {"decision": "needs_correction", "corrected_text": "有名店に時計があります。", "error_types": ["particle_misuse"], "reason_ko": "존재 장소에는 に가 필요합니다."}
        parsed, error = parse_stage2_output(canonical_json(corrected), TEXT, ["false_negative"])
        self.assertIsNone(error)
        self.assertEqual(parsed["decision"], "needs_correction")

    def test_combined_output_is_compatible_with_existing_storage_contract(self):
        stage1 = {"verdict": "disagree", "issue_codes": ["false_negative"], "review_reason_ko": "조사 오류를 놓쳤습니다."}
        raw_stage2 = {"decision": "needs_correction", "corrected_text": "有名店に時計があります。", "error_types": ["particle_misuse"], "reason_ko": "존재 장소에는 に가 필요합니다."}
        stage2, error = parse_stage2_output(canonical_json(raw_stage2), TEXT, stage1["issue_codes"])
        self.assertIsNone(error)
        combined = combine_outputs(stage1, stage2)
        reparsed, error = parse_output(canonical_json({**combined, "recommended_judgment": raw_stage2}), TEXT)
        self.assertIsNone(error)
        self.assertEqual(reparsed["recommended_judgment"]["corrected_text"], "有名店に時計があります。")
        with self.assertRaisesRegex(ValueError, "must not include"):
            combine_outputs({"verdict": "agree", "issue_codes": [], "review_reason_ko": "타당함"}, stage2)


class FeedbackTwoStageServiceTests(unittest.TestCase):
    def _transport(self, outputs):
        calls = []
        queue = list(outputs)
        def transport(**kwargs):
            calls.append(kwargs["request_body"])
            raw, latency = queue.pop(0)
            return {"transport_success": True, "raw_text": raw, "latency_ms": latency}
        return transport, calls

    def test_agree_stops_after_stage1(self):
        transport, calls = self._transport([(
            canonical_json({"verdict": "agree", "issue_codes": [], "review_reason_ko": "타당합니다."}), 3.0
        )])
        result = run_feedback(
            TEXT, context=None, learner_level="N5", judgment=MODEL_INPUT["judgment"],
            model_name="feedback-v08", contract_version="feedback-two-stage-v0.1",
            transport=transport,
        )
        self.assertEqual(result["verdict"], "agree")
        self.assertIsNone(result["recommended_judgment"])
        self.assertEqual(result["latency_ms"], 3.0)
        self.assertEqual(len(calls), 1)

    def test_disagree_calls_stage2_and_builds_backend_edits(self):
        stage1 = canonical_json({
            "verdict": "disagree", "issue_codes": ["false_negative"],
            "review_reason_ko": "오류를 놓쳤습니다.",
        })
        stage2 = canonical_json({
            "decision": "needs_correction", "corrected_text": "有名店に時計があります。",
            "error_types": ["particle_misuse"], "reason_ko": "존재 장소에는 に를 씁니다.",
        })
        transport, calls = self._transport([(stage1, 4.0), (stage2, 6.0)])
        result = run_feedback(
            TEXT, context=None, learner_level="N5", judgment=MODEL_INPUT["judgment"],
            model_name="feedback-v08", contract_version="feedback-two-stage-v0.1",
            transport=transport,
        )
        self.assertEqual(result["verdict"], "disagree")
        self.assertEqual(result["latency_ms"], 10.0)
        self.assertEqual(len(calls), 2)
        edit = result["recommended_judgment"]["edits"][0]
        self.assertEqual((edit["source"], edit["replacement"]), ("で", "に"))

    def test_stage2_contract_failure_discards_partial_result(self):
        stage1 = canonical_json({
            "verdict": "disagree", "issue_codes": ["false_negative"],
            "review_reason_ko": "오류를 놓쳤습니다.",
        })
        transport, calls = self._transport([(stage1, 2.0), ("{}", 2.0)])
        with self.assertRaises(FeedbackServiceError) as raised:
            run_feedback(
                TEXT, context=None, learner_level="N5", judgment=MODEL_INPUT["judgment"],
                model_name="feedback-v08", contract_version="feedback-two-stage-v0.1",
                transport=transport,
            )
        self.assertEqual(raised.exception.category, "contract_stage2")
        self.assertEqual(len(calls), 2)

    def test_stage1_contract_failure_is_classified_before_stage2(self):
        transport, calls = self._transport([("{}", 2.0)])
        with self.assertRaises(FeedbackServiceError) as raised:
            run_feedback(
                TEXT, context=None, learner_level="N5", judgment=MODEL_INPUT["judgment"],
                model_name="feedback-v08", contract_version="feedback-two-stage-v0.1",
                transport=transport,
            )
        self.assertEqual(raised.exception.category, "contract_stage1")
        self.assertEqual(len(calls), 1)

    def test_unknown_contract_fails_before_transport(self):
        transport, calls = self._transport([])
        with self.assertRaises(FeedbackServiceError) as raised:
            run_feedback(
                TEXT, context=None, learner_level="N5", judgment=MODEL_INPUT["judgment"],
                model_name="feedback-v08", contract_version="unknown", transport=transport,
            )
        self.assertEqual(raised.exception.category, "configuration")
        self.assertEqual(calls, [])


if __name__ == "__main__":
    unittest.main()
