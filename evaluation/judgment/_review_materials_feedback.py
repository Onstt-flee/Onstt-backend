"""Generate review materials and attach the external 30-item feedback mapping."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from . import _review_materials_base as base
from . import _review_materials_cjk as cjk


DEFAULT_MAPPING = base.BASE_DIR / "feedback_mapping_v0.1.json"


def load_feedback_mapping(path: Path, dataset_rows: list[dict[str, Any]]) -> dict[str, Any]:
    mapping = json.loads(path.read_text(encoding="utf-8"))
    items = mapping.get("items", [])
    if [item.get("feedback_no") for item in items] != list(range(1, 31)):
        raise ValueError("피드백 번호는 1부터 30까지 중복 없이 있어야 합니다.")

    rows_by_id = {row["id"]: row for row in dataset_rows}
    for item in items:
        missing_ids = [dataset_id for dataset_id in item["dataset_ids"] if dataset_id not in rows_by_id]
        if missing_ids:
            raise ValueError(f"{item['feedback_no']}번의 평가셋 ID가 없습니다: {missing_ids}")
        if item["match_type"].startswith("exact"):
            mismatches = [
                dataset_id
                for dataset_id in item["dataset_ids"]
                if rows_by_id[dataset_id]["input"]["text"] != item["input_text"]
            ]
            if mismatches:
                raise ValueError(f"{item['feedback_no']}번 exact 매칭 원문이 다릅니다: {mismatches}")
    return mapping


def add_feedback_mapping_sheet(
    workbook_path: Path,
    dataset_rows: list[dict[str, Any]],
    mapping: dict[str, Any],
) -> None:
    from openpyxl import load_workbook
    from openpyxl.formatting.rule import CellIsRule
    from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
    from openpyxl.utils import get_column_letter
    from openpyxl.worksheet.datavalidation import DataValidation

    workbook = load_workbook(workbook_path)
    if "교정피드백_매칭" in workbook.sheetnames:
        del workbook["교정피드백_매칭"]
    sheet = workbook.create_sheet("교정피드백_매칭")
    sheet.sheet_view.showGridLines = False
    sheet.sheet_properties.tabColor = "7030A0"

    navy = "17324D"
    purple = "7030A0"
    white = "FFFFFF"
    light_purple = "E4DFEC"
    light_blue = "EEF5FB"
    green = "DDEEDC"
    yellow = "FFF2CC"
    red = "F4CCCC"
    thin_gray = Side(style="thin", color="C8CDD2")
    border = Border(left=thin_gray, right=thin_gray, top=thin_gray, bottom=thin_gray)

    headers = [
        "피드백 번호",
        "평가셋 ID",
        "매칭 방식",
        "제공 원문",
        "평가셋 실제 원문",
        "평가셋 문맥",
        "제공 추천 교정문",
        "대체 허용 후보",
        "핵심 교정 포인트",
        "피드백 분류",
        "공통 진단",
        "상황별 팁",
        "현재 초안 판단",
        "현재 초안 교정문",
        "현재 계약과의 관계",
        "매칭/정책 메모",
        "매칭 검수",
        "검수일",
    ]
    sheet.merge_cells(start_row=1, start_column=1, end_row=1, end_column=len(headers))
    title = sheet.cell(1, 1, mapping["title"])
    title.font = Font(name="Noto Sans CJK KR", size=18, bold=True, color=white)
    title.fill = PatternFill("solid", fgColor=purple)
    title.alignment = Alignment(vertical="center")
    sheet.row_dimensions[1].height = 32
    sheet.merge_cells(start_row=2, start_column=1, end_row=2, end_column=len(headers))
    subtitle = sheet.cell(
        2,
        1,
        "피드백 번호는 JG ID가 아닙니다. PDF/1차 블라인드 판정 후 참고하며, 이 시트의 매칭은 원본 라벨을 자동 변경하지 않습니다.",
    )
    subtitle.font = Font(name="Noto Sans CJK KR", size=10, color="404040")
    subtitle.fill = PatternFill("solid", fgColor=light_purple)
    subtitle.alignment = Alignment(vertical="center", wrap_text=True)
    sheet.row_dimensions[2].height = 36
    for column, header in enumerate(headers, 1):
        cell = sheet.cell(4, column, header)
        cell.font = Font(name="Noto Sans CJK KR", bold=True, color=white)
        cell.fill = PatternFill("solid", fgColor=navy)
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        cell.border = border
    sheet.row_dimensions[4].height = 34

    rows_by_id = {row["id"]: row for row in dataset_rows}
    categories = mapping["categories"]
    for row_number, item in enumerate(mapping["items"], 5):
        matched_rows = [rows_by_id[dataset_id] for dataset_id in item["dataset_ids"]]
        category = categories[item["category"]]

        def joined(selector: Any) -> str:
            return "\n---\n".join(selector(row) for row in matched_rows)

        review_dates = sorted({
            row["review"]["reviewed_at"]
            for row in matched_rows
            if row["review"]["reviewed_at"]
        })
        values = [
            item["feedback_no"],
            ", ".join(item["dataset_ids"]),
            item["match_type"],
            item["input_text"],
            joined(lambda row: row["input"]["text"]),
            joined(lambda row: row["input"].get("context") or "문맥 없음"),
            item["recommended_text"],
            "\n".join(item["alternatives"]),
            item["point_ko"],
            category["title"],
            category["diagnosis_ko"],
            category["usage_tip_ko"],
            joined(lambda row: row["expected"]["decision"]),
            joined(lambda row: row["expected"]["corrected_text"]),
            item["contract_relation"],
            item["note_ko"],
            "승인",
            ", ".join(review_dates),
        ]
        for column, value in enumerate(values, 1):
            cell = sheet.cell(row_number, column, value)
            cell.font = Font(name="Noto Sans CJK KR", size=9)
            cell.alignment = Alignment(vertical="top", wrap_text=True)
            cell.border = border
            cell.fill = PatternFill("solid", fgColor=light_blue if column >= 17 else "FFFFFF")
        relation = item["contract_relation"]
        relation_color = green if relation == "aligned" else yellow
        if "conflict" in relation or "advisory" in relation:
            relation_color = red
        sheet.cell(row_number, 15).fill = PatternFill("solid", fgColor=relation_color)
        sheet.row_dimensions[row_number].height = 100 if len(item["dataset_ids"]) > 1 else 82

    widths = [12, 20, 24, 35, 35, 48, 38, 34, 32, 36, 52, 52, 25, 38, 30, 58, 15, 14]
    for column, width in enumerate(widths, 1):
        sheet.column_dimensions[get_column_letter(column)].width = width
    first_row = 5
    last_row = 4 + len(mapping["items"])
    sheet.freeze_panes = "G5"
    sheet.auto_filter.ref = f"A4:R{last_row}"
    sheet.print_title_rows = "1:4"
    sheet.sheet_properties.pageSetUpPr.fitToPage = True
    sheet.page_setup.orientation = "landscape"
    sheet.page_setup.paperSize = sheet.PAPERSIZE_A3
    sheet.page_setup.fitToWidth = 1
    sheet.page_setup.fitToHeight = 0
    validation = DataValidation(type="list", formula1='"승인,수정,보류"', allow_blank=True)
    sheet.add_data_validation(validation)
    validation.add(f"Q{first_row}:Q{last_row}")
    for status, color in (("승인", green), ("수정", yellow), ("보류", red)):
        sheet.conditional_formatting.add(
            f"Q{first_row}:Q{last_row}",
            CellIsRule(operator="equal", formula=[f'"{status}"'], fill=PatternFill("solid", fgColor=color)),
        )

    guide = workbook["사용안내"]
    guide.merge_cells(start_row=22, start_column=2, end_row=22, end_column=5)
    guide.cell(22, 2, "외부 교정 피드백 매칭")
    guide.cell(22, 2).font = Font(name="Noto Sans CJK KR", size=13, bold=True, color=white)
    guide.cell(22, 2).fill = PatternFill("solid", fgColor=purple)
    guide.merge_cells(start_row=23, start_column=2, end_row=23, end_column=5)
    guide.cell(23, 2, "‘교정피드백_매칭’ 시트는 제공받은 1~30번을 JG ID에 연결합니다. 1차 블라인드 판단 후 확인하세요.")
    guide.cell(23, 2).font = Font(name="Noto Sans CJK KR", size=10)
    guide.cell(23, 2).alignment = Alignment(vertical="top", wrap_text=True)
    guide.cell(23, 2).border = border
    guide.row_dimensions[22].height = 25
    guide.row_dimensions[23].height = 42

    workbook.calculation.fullCalcOnLoad = True
    workbook.calculation.forceFullCalc = True
    workbook.calculation.calcMode = "auto"
    workbook.save(workbook_path)


def main() -> int:
    args = cjk.parse_args()
    rows = base.load_dataset(args.dataset)
    mapping = load_feedback_mapping(DEFAULT_MAPPING, rows)
    output_dir = args.output_dir.resolve()
    workbook_path = output_dir / "judgment_review_sheet_v0.1.xlsx"
    pdf_path = output_dir / "judgment_review_packet_v0.1.pdf"

    base.build_workbook(rows, workbook_path)
    add_feedback_mapping_sheet(workbook_path, rows, mapping)
    korean_font_path = base.find_pdf_font(args.font_path)
    japanese_font_path = cjk.find_japanese_font(args.japanese_font_path, output_dir)
    korean_name, japanese_name, fully_embedded = cjk.build_cjk_pdf(
        rows, pdf_path, korean_font_path, japanese_font_path
    )

    print(f"dataset: {args.dataset.resolve()}")
    print(f"items: {len(rows)}")
    print(f"feedback mapping: {len(mapping['items'])} numbers -> {sum(len(item['dataset_ids']) for item in mapping['items'])} dataset rows")
    print(f"workbook: {workbook_path}")
    print(f"pdf: {pdf_path}")
    print(
        "pdf fonts: "
        f"korean={korean_name}, japanese={japanese_name}, "
        f"both_embedded={str(fully_embedded).lower()}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
