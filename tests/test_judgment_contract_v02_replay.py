import json
import unittest

from evaluation.judgment.contract_v02_replay import _to_v02_raw


class JudgmentContractV02ReplayTests(unittest.TestCase):
    def test_removes_positions_and_deduplicates_error_types(self):
        raw = json.dumps({
            "decision": "needs_correction",
            "corrected_text": "学校に行きました。",
            "edits": [
                {"start": 2, "end": 3, "source": "を", "replacement": "に", "error_type": "particle_misuse"},
                {"start": 4, "end": 7, "source": "くます", "replacement": "きました", "error_type": "verb_conjugation"},
                {"start": 99, "end": 100, "source": "x", "replacement": "y", "error_type": "verb_conjugation"},
            ],
            "reason_ko": "조사와 활용 교정",
        })
        converted = json.loads(_to_v02_raw(raw))
        self.assertEqual(set(converted), {"decision", "corrected_text", "error_types", "reason_ko"})
        self.assertEqual(converted["error_types"], ["particle_misuse", "verb_conjugation"])

    def test_rejects_non_v01_shapes(self):
        with self.assertRaises(ValueError):
            _to_v02_raw('{"decision":"acceptable"}')


if __name__ == "__main__":
    unittest.main()
