import hashlib
import json
from pathlib import Path
import unittest

from training.judgment.apply_user_review import apply_review, load_review_source
from training.judgment.data import load_records, summary, validate_records


ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "training" / "judgment" / "data" / "pilot_v0.1.jsonl"
REVIEW = ROOT / "training" / "judgment" / "data" / "pilot_v0.1.user_review.jsonl"
REVIEWED = ROOT / "training" / "judgment" / "data" / "pilot_v0.1.reviewed.jsonl"
MANIFEST = ROOT / "training" / "judgment" / "data" / "pilot_v0.1.reviewed.manifest.json"


class JudgmentUserReviewTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.base = load_records(BASE)
        cls.reviews = load_review_source(REVIEW)
        cls.reviewed = load_records(REVIEWED)

    def test_reviewed_dataset_is_reproducible_and_complete(self):
        self.assertEqual(apply_review(self.base, self.reviews), self.reviewed)
        validate_records(self.reviewed, require_reviewed=True)
        self.assertEqual(summary(self.reviewed)["decisions"], {
            "acceptable": 136,
            "insufficient_evidence": 45,
            "needs_correction": 119,
        })
        self.assertTrue(all(
            row["review"] == {
                "status": "user_reviewed", "reviewed_at": "2026-09-14"
            }
            for row in self.reviewed
        ))

    def test_confirmed_lexical_compound_decisions(self):
        by_id = {row["id"]: row for row in self.reviewed}
        self.assertEqual(by_id["JT-0205"]["expected"], {
            "decision": "acceptable",
            "corrected_text": "有名店で食べました。",
            "edits": [],
            "reason_ko": "'有名店'은 하나의 합성 명사로 쓰이므로 문법적 오류가 없습니다.",
        })
        self.assertEqual(
            by_id["JT-0247"]["expected"]["corrected_text"],
            "有名店に時計があります。",
        )
        self.assertEqual(by_id["JT-0247"]["expected"]["edits"], [{
            "start": 3,
            "end": 4,
            "source": "で",
            "replacement": "に",
            "error_type": "particle_misuse",
        }])

    def test_review_source_is_anonymous_and_has_no_placeholder_citations(self):
        self.assertEqual(len(self.reviews), 300)
        self.assertTrue(all("reviewer" not in row for row in self.reviews))
        self.assertTrue(all("[cite:" not in row["reason_ko"] for row in self.reviews))

    def test_reviewed_manifest_hashes_match(self):
        manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        self.assertEqual(
            manifest["dataset_sha256"],
            hashlib.sha256(REVIEWED.read_bytes()).hexdigest(),
        )
        self.assertEqual(
            manifest["review_source_sha256"],
            hashlib.sha256(REVIEW.read_bytes()).hexdigest(),
        )
        self.assertEqual(manifest["summary"], summary(self.reviewed))
        self.assertFalse(manifest["review_policy"]["reviewer_identity_stored"])
        self.assertFalse(manifest["review_policy"]["expert_review_claimed"])


if __name__ == "__main__":
    unittest.main()
