"""Offline regression tests for the provisional judgment data and strict contract."""

from copy import deepcopy
from contextlib import redirect_stderr, redirect_stdout
import io
import json
from pathlib import Path
import unittest
from unittest.mock import patch

from evaluation.judgment.dataset import (
    DEFAULT_DATASET, load_records, main, model_inputs, rag_overlap_report,
    render_review, sentence_fingerprint, summary, validate_judgment, validate_records,
)


class JudgmentDatasetTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.records = load_records()

    def case(self, number):
        return deepcopy(self.records[number - 1])

    def test_seed_contract_and_coverage(self):
        validate_records(self.records)
        result = summary(self.records)
        self.assertEqual(result["total"], 72)
        self.assertEqual(result["decisions"], {
            "acceptable": 33, "needs_correction": 27, "insufficient_evidence": 12,
        })
        self.assertEqual(result["compound_error_cases"], 4)
        self.assertEqual(result["review_status"], {"user_reviewed": 72})
        self.assertFalse(result["linguistic_accuracy_verified"])
        for decisions in result["decisions_by_level"].values():
            self.assertEqual(set(decisions), {"acceptable", "needs_correction", "insufficient_evidence"})

    def test_empty_dataset_and_non_objects_are_rejected(self):
        for records in ([], {}, [None], [[]], [{}]):
            with self.subTest(records=records), self.assertRaises(ValueError):
                validate_records(records)

    def test_missing_and_extra_fields_are_rejected(self):
        for key in self.case(1):
            row = self.case(1)
            del row[key]
            with self.subTest(key=key), self.assertRaises(ValueError):
                validate_records([row])
        row = self.case(1)
        row["hidden_answer"] = True
        with self.assertRaises(ValueError):
            validate_records([row])

    def test_duplicate_id_and_input_are_rejected(self):
        with self.assertRaisesRegex(ValueError, "Duplicate id"):
            validate_records([self.case(1), self.case(1)])
        other = self.case(1)
        other["id"] = "JG-999"
        with self.assertRaisesRegex(ValueError, "Duplicate input"):
            validate_records([self.case(1), other])
        other["input"]["context"] = "別の会話の文脈です。"
        validate_records([self.case(1), other])

    def test_invalid_metadata_is_rejected(self):
        overrides = [
            ("schema_version", "1.0"), ("id", 1), ("split", "train"),
            ("group_id", []), ("tags", []), ("tags", [None]),
            ("provenance", {}), ("review", {}),
        ]
        for field, value in overrides:
            row = self.case(1)
            row[field] = value
            with self.subTest(field=field, value=value), self.assertRaises(ValueError):
                validate_records([row])

    def test_invalid_input_and_output_types_are_rejected(self):
        for field, value in (("text", None), ("context", []), ("learner_level", "N1")):
            row = self.case(1)
            row["input"][field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                validate_records([row])
        for field, value in (
            ("decision", None), ("decision", []), ("corrected_text", None),
            ("edits", {}), ("reason_ko", ""),
        ):
            row = self.case(1)
            row["expected"][field] = value
            with self.subTest(field=field, value=value), self.assertRaises(ValueError):
                validate_records([row])

    def test_non_correction_decisions_preserve_the_original(self):
        for number in (1, 49, 52):
            row = self.case(number)
            row["expected"]["corrected_text"] += "。"
            with self.subTest(number=number), self.assertRaises(ValueError):
                validate_records([row])
            row = self.case(number)
            row["expected"]["edits"] = self.case(25)["expected"]["edits"]
            with self.subTest(number=number), self.assertRaises(ValueError):
                validate_records([row])

    def test_correction_cannot_be_empty_or_unchanged(self):
        for corrected in ("", "   ", self.case(25)["input"]["text"]):
            row = self.case(25)
            row["expected"]["corrected_text"] = corrected
            with self.subTest(corrected=corrected), self.assertRaises(ValueError):
                validate_records([row])
        row = self.case(25)
        row["expected"]["edits"] = []
        with self.assertRaises(ValueError):
            validate_records([row])

    def test_invalid_spans_and_edit_types_are_rejected(self):
        for field, value in (
            ("start", True), ("end", 1.5), ("start", -1), ("end", 999),
            ("source", "wrong"), ("source", None), ("replacement", None),
            ("error_type", "pronunciation_error"), ("error_type", []),
        ):
            row = self.case(25)
            row["expected"]["edits"][0][field] = value
            with self.subTest(field=field, value=value), self.assertRaises(ValueError):
                validate_records([row])

    def test_unsorted_overlapping_and_noop_edits_are_rejected(self):
        row = self.case(45)
        row["expected"]["edits"].reverse()
        with self.assertRaisesRegex(ValueError, "non-overlapping"):
            validate_records([row])
        row = self.case(25)
        row["expected"]["edits"] *= 2
        with self.assertRaisesRegex(ValueError, "non-overlapping"):
            validate_records([row])
        row = self.case(25)
        row["expected"]["edits"][0]["replacement"] = "を"
        with self.assertRaisesRegex(ValueError, "change its span"):
            validate_records([row])

    def test_insertion_deletion_and_compound_reconstruction(self):
        validate_records([self.case(number) for number in (41, 42, 45, 46, 47, 48)])
        row = self.case(45)
        row["expected"]["edits"].pop()
        with self.assertRaisesRegex(ValueError, "reconstruct"):
            validate_records([row])

    def test_offsets_are_unicode_code_points_not_utf8_or_utf16(self):
        judgment = {
            "decision": "needs_correction", "corrected_text": "🙂駅に行きます。",
            "edits": [{"start": 2, "end": 3, "source": "を", "replacement": "に", "error_type": "particle_misuse"}],
            "reason_ko": "테스트용 교정입니다.",
        }
        validate_judgment(judgment, "🙂駅を行きます。")
        judgment["edits"][0].update(start=3, end=4)
        with self.assertRaisesRegex(ValueError, "source"):
            validate_judgment(judgment, "🙂駅を行きます。")

    def test_accepted_corrections_are_consistent(self):
        for number, values in ((25, []), (25, ["別の文です。"]), (1, ["別の文です。"]), (25, [None])):
            row = self.case(number)
            row["accepted_corrections"] = values
            with self.subTest(number=number, values=values), self.assertRaises(ValueError):
                validate_records([row])
        row = self.case(25)
        row["accepted_corrections"].append(row["input"]["text"])
        with self.assertRaises(ValueError):
            validate_records([row])

    def test_review_completion_requires_date_without_identity(self):
        invalid = [
            {"status": "provisional", "reviewed_at": "2026-09-04"},
            {"status": "user_reviewed", "reviewed_at": None},
            {"status": "user_reviewed", "reviewed_at": "2026-02-30"},
            {"status": "expert_reviewed", "reviewed_at": "20260904"},
        ]
        for review in invalid:
            row = self.case(1)
            row["review"] = review
            with self.subTest(review=review), self.assertRaises(ValueError):
                validate_records([row])
        for status in ("user_reviewed", "expert_reviewed"):
            row = self.case(1)
            row["review"] = {"status": status, "reviewed_at": "2026-09-04"}
            validate_records([row])
        row = self.case(1)
        row["review"]["reviewer"] = "identifier-must-not-be-stored"
        with self.assertRaises(ValueError):
            validate_records([row])

    def test_model_export_contains_no_labels_or_references(self):
        exported = model_inputs(self.records)
        self.assertEqual(len(exported), 72)
        for item, original in zip(exported, self.records):
            self.assertEqual(set(item), {"id", "input"})
            self.assertEqual(set(item["input"]), {"text", "context", "learner_level"})
            self.assertEqual(item["input"], original["input"])
        exported[0]["input"]["text"] = "changed"
        self.assertNotEqual(exported[0]["input"]["text"], self.records[0]["input"]["text"])

    def test_loader_rejects_invalid_json_duplicate_keys_and_nan(self):
        for content in ('{"id": 1, "id": 2}\n', '{"x": NaN}\n', 'not json\n', '\n'):
            with self.subTest(content=content), patch.object(Path, "open", return_value=io.StringIO(content)):
                with self.assertRaisesRegex(ValueError, ":1:"):
                    load_records(Path("bad.jsonl"))

    def test_rag_audit_finds_inputs_canonical_and_alternative_corrections(self):
        row = self.case(25)
        corpus = {"examples": [row["input"]["text"], *row["accepted_corrections"]]}
        with (
            patch.object(Path, "rglob", return_value=[Path("fixtures/source.json")]),
            patch.object(Path, "open", return_value=io.StringIO(json.dumps(corpus))),
        ):
            report = rag_overlap_report([row], Path("fixtures"))
        self.assertEqual(len(report["matches"]), 3)
        self.assertEqual(report["strings_scanned"], 3)
        self.assertEqual(sentence_fingerprint(" Ａ東京駅に行く。\n"), "A東京駅に行く")

    def test_rag_audit_reports_missing_corpus_and_skips_short_strings(self):
        with patch.object(Path, "rglob", return_value=[]):
            with self.assertRaisesRegex(ValueError, "No RAG JSON"):
                rag_overlap_report(self.records, Path("missing"))
        row = self.case(1)
        row["input"]["text"] = row["expected"]["corrected_text"] = "はい。"
        with (
            patch.object(Path, "rglob", return_value=[Path("fixtures/source.json")]),
            patch.object(Path, "open", return_value=io.StringIO('["はい。"]')),
        ):
            self.assertEqual(rag_overlap_report([row], Path("fixtures"))["matches"], [])

    def test_review_and_contract_examples_match_dataset(self):
        self.assertEqual(
            DEFAULT_DATASET.with_name("REVIEW.md").read_text(encoding="utf-8"),
            render_review(self.records),
        )
        readme = DEFAULT_DATASET.with_name("README.md").read_text(encoding="utf-8")
        example = json.loads(readme.split("```json\n", 1)[1].split("\n```", 1)[0])
        row = self.case(25)
        validate_judgment(example, row["input"]["text"])
        self.assertEqual(example["edits"], row["expected"]["edits"])

    def test_cli_validates_and_rejects_unreviewed_release(self):
        with redirect_stdout(io.StringIO()) as output:
            self.assertEqual(main([]), 0)
        self.assertEqual(json.loads(output.getvalue())["total"], 72)
        with redirect_stdout(io.StringIO()):
            self.assertEqual(main(["--require-reviewed"]), 0)
        row = self.case(1)
        row["review"] = {"status": "provisional", "reviewed_at": None}
        with redirect_stderr(io.StringIO()) as error, patch(
            "evaluation.judgment.dataset.load_records", return_value=[row],
        ):
            self.assertEqual(main(["--require-reviewed"]), 1)
        self.assertIn("Human review required", error.getvalue())

    def test_cli_label_free_export(self):
        with redirect_stdout(io.StringIO()) as output:
            self.assertEqual(main(["--inputs-only"]), 0)
        self.assertEqual(
            [json.loads(line) for line in output.getvalue().splitlines()],
            model_inputs(self.records),
        )

    def test_boundary_coverage_preserves_the_original_seed_distribution(self):
        result = summary(self.records)
        self.assertEqual(result["boundary_cases"], 12)
        self.assertEqual(summary(self.records[:60])["decisions"], {
            "acceptable": 24, "needs_correction": 24, "insufficient_evidence": 12,
        })
        for group in ("boundary_fillers", "boundary_register", "boundary_transcription", "boundary_context"):
            self.assertEqual(sum(row["group_id"] == group for row in self.records), 3)

    def test_filler_policy_keeps_content_and_only_repairs_grammar(self):
        self.assertEqual(self.case(61)["expected"]["decision"], "acceptable")
        self.assertEqual(self.case(62)["expected"]["corrected_text"], "ええと、昨日は駅で友達に会いました。")
        self.assertEqual(self.case(63)["expected"]["corrected_text"], "なんか飲む？")
        self.assertIn("check:lexical_content_preserve", self.case(63)["tags"])
        self.assertEqual(self.case(51)["expected"]["decision"], "insufficient_evidence")

    def test_register_checks_are_separate_from_grammar_decision(self):
        casual, formal, embedded = (self.case(number) for number in (64, 65, 66))
        self.assertEqual(casual["input"]["text"], formal["input"]["text"])
        self.assertNotEqual(casual["input"]["context"], formal["input"]["context"])
        self.assertIn("check:style_preserve", casual["tags"])
        self.assertIn("check:style_advisory", formal["tags"])
        for row in (casual, formal, embedded):
            self.assertEqual(row["expected"]["decision"], "acceptable")
            self.assertEqual(row["expected"]["corrected_text"], row["input"]["text"])

    def test_transcription_checks_do_not_assign_learner_blame(self):
        for number in (67, 68, 69):
            self.assertIn("check:attribution_unknown", self.case(number)["tags"])
        for number in (67, 68):
            row = self.case(number)
            self.assertIn("check:orthography_candidate", row["tags"])
            self.assertEqual(row["expected"]["decision"], "acceptable")
            self.assertEqual(row["expected"]["corrected_text"], row["input"]["text"])
        self.assertEqual(self.case(69)["expected"]["decision"], "needs_correction")

    def test_context_mismatch_can_coexist_with_a_grammar_error(self):
        mismatch, match, both = (self.case(number) for number in (70, 71, 72))
        self.assertEqual(mismatch["input"]["text"], match["input"]["text"])
        self.assertIn("check:context_mismatch", mismatch["tags"])
        self.assertIn("check:context_match", match["tags"])
        self.assertEqual(mismatch["expected"]["decision"], "acceptable")
        self.assertEqual(match["expected"]["decision"], "acceptable")
        self.assertIn("check:context_mismatch", both["tags"])
        self.assertEqual(both["expected"]["decision"], "needs_correction")
        self.assertEqual(both["expected"]["corrected_text"], "りんごが一番好きです。")

    def test_review_check_tags_are_known_and_never_become_output_fields(self):
        row = self.case(65)
        row["tags"].append("check:unknown_tag")
        with self.assertRaisesRegex(ValueError, "review check tag"):
            validate_records([row])
        for row in self.records[60:]:
            self.assertEqual(set(row["expected"]), {"decision", "corrected_text", "edits", "reason_ko"})
        row = self.case(70)
        row["expected"]["context_fit"] = "mismatch"
        with self.assertRaises(ValueError):
            validate_records([row])


if __name__ == "__main__":
    unittest.main()
