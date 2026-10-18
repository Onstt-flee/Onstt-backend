import json
from pathlib import Path
import tempfile
import unittest

from evaluation.feedback.reparse_run import main


class FeedbackReparseRunTests(unittest.TestCase):
    def test_hardened_contract_rejects_semantic_issue_decision_conflict(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            dataset = root / "dataset.jsonl"
            run = root / "run.jsonl"
            output = root / "reparsed.jsonl"
            dataset.write_text(json.dumps({"id": "x", "text": "学校に行きます。"}, ensure_ascii=False) + "\n")
            raw = json.dumps({
                "verdict": "disagree",
                "issue_codes": ["false_negative"],
                "recommended_judgment": {
                    "decision": "acceptable",
                    "corrected_text": "学校に行きます。",
                    "error_types": [],
                    "reason_ko": "문법적으로 허용됩니다.",
                },
                "review_reason_ko": "오류를 놓쳤습니다.",
            }, ensure_ascii=False)
            run.write_text(json.dumps({"id": "x", "raw_text": raw}, ensure_ascii=False) + "\n")
            import sys
            previous = sys.argv
            try:
                sys.argv = ["reparse", "--dataset", str(dataset), "--run", str(run), "--output", str(output)]
                main()
            finally:
                sys.argv = previous
            row = json.loads(output.read_text(encoding="utf-8"))
            self.assertFalse(row["contract_success"])
            self.assertIn("false_negative requires", row["contract_error"])


if __name__ == "__main__":
    unittest.main()
