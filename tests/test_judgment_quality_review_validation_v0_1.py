"""Tests for completed quality_review_v0.1 label validation."""

import json
import tempfile
import unittest
from pathlib import Path

from evaluation.judgment.validate_quality_review_v0_1 import (
    AUDIO_LOCK,
    validate_completed_review,
)
from scripts.run_judgment_shadow import canonical_json, sha256_bytes


class JudgmentQualityReviewValidationV01Tests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.review = self.root / "review.jsonl"
        self.manifest = self.root / "manifest.json"
        self.rows = [
            {
                "id": "QR-001",
                "text": "今日は学校に行きます。",
                "context": None,
                "learner_level": "N5",
                "grammar_decision": "acceptable",
                "corrected_text": "今日は学校に行きます。",
                "error_types": [],
                "reason_ko": "문법적으로 허용됩니다.",
                "review_status": "independently_reviewed",
                "reviewed_at": "2026-10-06",
                "audio_review": dict(AUDIO_LOCK),
            },
            {
                "id": "QR-002",
                "text": "学校を行きます。",
                "context": None,
                "learner_level": "N5",
                "grammar_decision": "needs_correction",
                "corrected_text": "学校に行きます。",
                "error_types": ["particle_misuse"],
                "reason_ko": "목적지 조사에는 に가 필요합니다.",
                "review_status": "independently_reviewed",
                "reviewed_at": "2026-10-06",
                "audio_review": dict(AUDIO_LOCK),
            },
        ]
        inputs = [
            {key: row[key] for key in ("id", "text", "context", "learner_level")}
            for row in self.rows
        ]
        self.manifest.write_text(json.dumps({
            "sample_size": 2,
            "artifacts": {
                "review_input_sha256": sha256_bytes(canonical_json(inputs).encode())
            },
        }), encoding="utf-8")

    def tearDown(self):
        self.temporary.cleanup()

    def write_rows(self):
        self.review.write_text(
            "".join(canonical_json(row) + "\n" for row in self.rows),
            encoding="utf-8",
        )

    def test_complete_labels_are_ready_without_expert_or_audio_claims(self):
        self.write_rows()
        result = validate_completed_review(self.review, self.manifest)
        self.assertTrue(result["ready_for_single_model_evaluation"])
        self.assertEqual(result["decision_counts"], {
            "acceptable": 1, "needs_correction": 1
        })
        self.assertFalse(result["expert_review_claimed"])
        self.assertEqual(result["audio_review_status"], "unavailable")

    def test_input_tampering_and_identity_fields_are_rejected(self):
        self.rows[0]["text"] = "変更された文。"
        self.rows[0]["corrected_text"] = "変更された文。"
        self.write_rows()
        with self.assertRaisesRegex(ValueError, "input text or metadata changed"):
            validate_completed_review(self.review, self.manifest)

        self.rows[0]["text"] = "今日は学校に行きます。"
        self.rows[0]["corrected_text"] = "今日は学校に行きます。"
        self.rows[0]["reviewer_name"] = "private name"
        self.write_rows()
        with self.assertRaisesRegex(ValueError, "identity fields are forbidden"):
            validate_completed_review(self.review, self.manifest)

    def test_incomplete_and_invalid_contract_labels_are_rejected(self):
        self.rows[0]["review_status"] = "pending"
        self.write_rows()
        with self.assertRaisesRegex(ValueError, "not independently reviewed"):
            validate_completed_review(self.review, self.manifest)

        self.rows[0]["review_status"] = "independently_reviewed"
        self.rows[1]["corrected_text"] = self.rows[1]["text"]
        self.write_rows()
        with self.assertRaisesRegex(ValueError, "must change"):
            validate_completed_review(self.review, self.manifest)


if __name__ == "__main__":
    unittest.main()
