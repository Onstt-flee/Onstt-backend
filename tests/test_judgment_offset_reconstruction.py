import json
import unittest

from evaluation.judgment.offset_reconstruction import rebuild_judgment


class JudgmentOffsetReconstructionTests(unittest.TestCase):
    def test_rebuilds_wrong_model_offset_from_corrected_text(self):
        raw = json.dumps({
            "decision": "needs_correction",
            "corrected_text": "学校に行きます。",
            "edits": [{
                "start": 99, "end": 100, "source": "wrong",
                "replacement": "に", "error_type": "particle_misuse",
            }],
            "reason_ko": "목적지 조사 교정",
        })
        rebuilt, error = rebuild_judgment("学校を行きます。", raw)
        self.assertIsNone(error)
        self.assertEqual(rebuilt["edits"], [{
            "start": 2, "end": 3, "source": "を",
            "replacement": "に", "error_type": "particle_misuse",
        }])

    def test_does_not_hide_noncorrection_content_change(self):
        raw = json.dumps({
            "decision": "acceptable",
            "corrected_text": "変更済み",
            "edits": [],
            "reason_ko": "허용",
        })
        rebuilt, error = rebuild_judgment("原文", raw)
        self.assertIsNone(rebuilt)
        self.assertIn("preserve", error)


if __name__ == "__main__":
    unittest.main()
