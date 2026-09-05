"""Regression tests for the generated anonymous review workbook."""

from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from openpyxl import load_workbook

from evaluation.judgment import _review_materials_ambiguous as ambiguous
from evaluation.judgment import _review_materials_base as base
from evaluation.judgment import _review_materials_feedback as feedback
from evaluation.judgment import _review_materials_final as final_feedback
from evaluation.judgment import generate_review_materials as generator


class ReviewWorkbookTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp_dir = TemporaryDirectory()
        cls.workbook_path = Path(cls.temp_dir.name) / "review.xlsx"
        cls.rows = base.load_dataset(base.DEFAULT_DATASET)
        cls.correction_mapping = feedback.load_feedback_mapping(feedback.DEFAULT_MAPPING, cls.rows)
        cls.ambiguous_mapping = ambiguous.load_ambiguous_mapping(
            ambiguous.DEFAULT_AMBIGUOUS_MAPPING, cls.rows
        )
        cls.complete_mapping = generator.load_complete_mapping(
            generator.DEFAULT_COMPLETE_MAPPING, cls.rows
        )
        base.build_workbook(cls.rows, cls.workbook_path)
        feedback.add_feedback_mapping_sheet(
            cls.workbook_path, cls.rows, cls.correction_mapping
        )
        ambiguous.add_ambiguous_mapping_sheet(
            cls.workbook_path, cls.rows, cls.ambiguous_mapping
        )
        generator.add_complete_and_coverage_sheets(
            cls.workbook_path,
            cls.rows,
            cls.complete_mapping,
            cls.correction_mapping,
            cls.ambiguous_mapping,
        )
        final_feedback.add_final_feedback_sheet(
            cls.workbook_path,
            cls.rows,
            cls.complete_mapping,
            cls.correction_mapping,
            cls.ambiguous_mapping,
        )
        cls.workbook = load_workbook(cls.workbook_path, data_only=False)

    @classmethod
    def tearDownClass(cls):
        cls.workbook.close()
        cls.temp_dir.cleanup()

    def rows_by_id(self, sheet_name):
        sheet = self.workbook[sheet_name]
        return {sheet.cell(row, 1).value: row for row in range(5, 77)}

    def test_sheet_order_and_anonymous_headers(self):
        self.assertEqual(
            self.workbook.sheetnames,
            [
                "사용안내", "요약", "판단기준", "전체매칭_현황",
                "1차_블라인드", "2차_대조검수", "최종피드백_요약",
                "교정피드백_매칭", "애매문장_매칭", "완전문장_매칭",
            ],
        )
        expected_columns = {
            "1차_블라인드": 11,
            "2차_대조검수": 17,
            "최종피드백_요약": 17,
            "교정피드백_매칭": 18,
            "애매문장_매칭": 19,
            "완전문장_매칭": 13,
        }
        for name, count in expected_columns.items():
            sheet = self.workbook[name]
            headers = [sheet.cell(4, column).value for column in range(1, count + 1)]
            self.assertEqual(sheet.max_column, count)
            self.assertNotIn("검수자", headers)
            self.assertNotIn("검수자*", headers)

    def test_second_review_is_fully_approved_without_fabricating_blind_review(self):
        blind = self.workbook["1차_블라인드"]
        for row in range(5, 77):
            self.assertTrue(all(blind.cell(row, column).value is None for column in range(5, 12)))

        compare = self.workbook["2차_대조검수"]
        for row_number, source in enumerate(self.rows, 5):
            self.assertEqual(compare.cell(row_number, 1).value, source["id"])
            self.assertEqual(compare.cell(row_number, 11).value, "승인")
            self.assertEqual(compare.cell(row_number, 12).value, source["expected"]["decision"])
            self.assertEqual(compare.cell(row_number, 13).value or "", source["expected"]["corrected_text"])
            self.assertIsNone(compare.cell(row_number, 14).value)
            self.assertEqual(compare.cell(row_number, 15).value, "2026-09-04")
            self.assertIsNone(compare.cell(row_number, 16).value)
            self.assertIsNone(compare.cell(row_number, 17).value)

    def test_mapping_sheets_record_anonymous_approval_and_date(self):
        cases = [
            ("교정피드백_매칭", 5, 34, 17, 18),
            ("애매문장_매칭", 5, 18, 18, 19),
            ("완전문장_매칭", 5, 31, 12, 13),
        ]
        for name, first, last, status_column, date_column in cases:
            sheet = self.workbook[name]
            for row in range(first, last + 1):
                self.assertEqual(sheet.cell(row, status_column).value, "승인")
                self.assertEqual(sheet.cell(row, date_column).value, "2026-09-04")

    def test_final_feedback_has_all_72_unique_rows(self):
        sheet = self.workbook["최종피드백_요약"]
        ids = [sheet.cell(row, 1).value for row in range(5, 77)]
        self.assertEqual(ids, [f"JG-{number:03d}" for number in range(1, 73)])
        self.assertEqual(len(ids), len(set(ids)))
        self.assertEqual(sheet.max_row, 76)
        for row in range(5, 77):
            self.assertEqual(sheet.cell(row, 16).value, "user_reviewed")
            self.assertEqual(sheet.cell(row, 17).value, "2026-09-04")

    def test_final_feedback_preserves_raw_inputs_and_separates_examples(self):
        sheet = self.workbook["최종피드백_요약"]
        rows = self.rows_by_id("최종피드백_요약")
        expected_inputs = {
            "JG-049": "",
            "JG-056": "明日は［聞き取れない］に行きます。",
            "JG-058": "今日は［聞き取れない］かったです。",
            "JG-059": "I went to the station yesterday.",
        }
        for dataset_id, text in expected_inputs.items():
            self.assertEqual(sheet.cell(rows[dataset_id], 3).value, text or None)
        for dataset_id in [f"JG-{number:03d}" for number in range(49, 61)]:
            row = rows[dataset_id]
            self.assertEqual(sheet.cell(row, 5).value, "insufficient_evidence")
            self.assertEqual(sheet.cell(row, 6).value, sheet.cell(row, 3).value)
            self.assertEqual(sheet.cell(row, 14).value, "낮음")
        self.assertEqual(sheet.cell(rows["JG-059"], 11).value, "昨日は駅に行きました。")
        self.assertIn("번역 예시", sheet.cell(rows["JG-059"], 12).value)

    def test_context_and_advisory_boundaries_remain_distinct(self):
        sheet = self.workbook["최종피드백_요약"]
        rows = self.rows_by_id("최종피드백_요약")
        for left, right in (("JG-064", "JG-065"), ("JG-070", "JG-071")):
            self.assertEqual(sheet.cell(rows[left], 3).value, sheet.cell(rows[right], 3).value)
            self.assertNotEqual(sheet.cell(rows[left], 4).value, sheet.cell(rows[right], 4).value)
        self.assertEqual(sheet.cell(rows["JG-064"], 5).value, "acceptable")
        self.assertEqual(sheet.cell(rows["JG-065"], 5).value, "acceptable")
        self.assertIsNone(sheet.cell(rows["JG-064"], 11).value)
        self.assertIn("読みました", sheet.cell(rows["JG-065"], 11).value)
        self.assertIn("문체 개선", sheet.cell(rows["JG-065"], 8).value)
        self.assertIn("질문과 내용 불일치", sheet.cell(rows["JG-070"], 8).value)
        self.assertIn("질문과 내용 일치", sheet.cell(rows["JG-071"], 8).value)

        for dataset_id, normalized in (
            ("JG-067", "わたしは大学生です。"),
            ("JG-068", "本を読みます。"),
        ):
            row = rows[dataset_id]
            self.assertEqual(sheet.cell(row, 5).value, "acceptable")
            self.assertEqual(sheet.cell(row, 6).value, sheet.cell(row, 3).value)
            self.assertIn("표기 정규화", sheet.cell(row, 8).value)
            self.assertIn(normalized, sheet.cell(row, 11).value)
            self.assertIn("표기 조언", sheet.cell(row, 12).value)
            self.assertEqual(sheet.cell(row, 14).value, "중간")


if __name__ == "__main__":
    unittest.main()
