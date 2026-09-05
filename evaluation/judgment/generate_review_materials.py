"""Generate review materials with complete, correction, and ambiguity mappings."""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path
from typing import Any

from . import _review_materials_ambiguous as ambiguous
from . import _review_materials_base as base
from . import _review_materials_cjk as cjk
from . import _review_materials_feedback as feedback
from . import _review_materials_final as final_feedback


DEFAULT_COMPLETE_MAPPING = base.BASE_DIR / "complete_mapping_v0.1.json"


def load_complete_mapping(
    path: Path, dataset_rows: list[dict[str, Any]]
) -> dict[str, Any]:
    mapping = json.loads(path.read_text(encoding="utf-8"))
    items = mapping.get("items", [])
    if [item.get("complete_no") for item in items] != list(range(1, 28)):
        raise ValueError("완전 문장 번호는 1부터 27까지 중복 없이 있어야 합니다.")

    rows_by_id = {row["id"]: row for row in dataset_rows}
    assigned_ids: list[str] = []
    for item in items:
        for dataset_id in item["dataset_ids"]:
            if dataset_id not in rows_by_id:
                raise ValueError(f"{item['complete_no']}번의 평가셋 ID가 없습니다: {dataset_id}")
            if rows_by_id[dataset_id]["input"]["text"] != item["input_text"]:
                raise ValueError(f"{item['complete_no']}번 원문이 {dataset_id}와 다릅니다.")
            assigned_ids.append(dataset_id)
    if len(assigned_ids) != len(set(assigned_ids)):
        raise ValueError("완전 문장 목록 안에서 평가셋 ID가 중복 배정됐습니다.")
    return mapping


def reverse_mapping(mapping: dict[str, Any], number_key: str) -> dict[str, list[int]]:
    result: dict[str, list[int]] = defaultdict(list)
    for item in mapping["items"]:
        for dataset_id in item["dataset_ids"]:
            result[dataset_id].append(item[number_key])
    return dict(result)


def add_complete_and_coverage_sheets(
    workbook_path: Path,
    dataset_rows: list[dict[str, Any]],
    complete_mapping: dict[str, Any],
    correction_mapping: dict[str, Any],
    ambiguous_mapping: dict[str, Any],
) -> tuple[int, int, list[str]]:
    from openpyxl import load_workbook
    from openpyxl.formatting.rule import CellIsRule
    from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
    from openpyxl.utils import get_column_letter
    from openpyxl.worksheet.datavalidation import DataValidation

    workbook = load_workbook(workbook_path)
    for sheet_name in ("완전문장_매칭", "전체매칭_현황"):
        if sheet_name in workbook.sheetnames:
            del workbook[sheet_name]

    navy = "17324D"
    green_title = "548235"
    teal_title = "0F6B78"
    white = "FFFFFF"
    light_green = "E2F0D9"
    light_teal = "DDEBF7"
    input_blue = "EEF5FB"
    green = "DDEEDC"
    yellow = "FFF2CC"
    red = "F4CCCC"
    gray = "E7E6E6"
    thin_gray = Side(style="thin", color="C8CDD2")
    border = Border(left=thin_gray, right=thin_gray, top=thin_gray, bottom=thin_gray)

    def set_title(sheet: Any, text: str, subtitle: str, columns: int, color: str) -> None:
        sheet.merge_cells(start_row=1, start_column=1, end_row=1, end_column=columns)
        cell = sheet.cell(1, 1, text)
        cell.font = Font(name="Noto Sans CJK KR", size=18, bold=True, color=white)
        cell.fill = PatternFill("solid", fgColor=color)
        cell.alignment = Alignment(vertical="center")
        sheet.row_dimensions[1].height = 32
        sheet.merge_cells(start_row=2, start_column=1, end_row=2, end_column=columns)
        cell = sheet.cell(2, 1, subtitle)
        cell.font = Font(name="Noto Sans CJK KR", size=10, color="404040")
        cell.fill = PatternFill("solid", fgColor=light_green if color == green_title else light_teal)
        cell.alignment = Alignment(vertical="center", wrap_text=True)
        sheet.row_dimensions[2].height = 36

    def set_headers(sheet: Any, headers: list[str]) -> None:
        for column, header in enumerate(headers, 1):
            cell = sheet.cell(4, column, header)
            cell.font = Font(name="Noto Sans CJK KR", bold=True, color=white)
            cell.fill = PatternFill("solid", fgColor=navy)
            cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
            cell.border = border
        sheet.row_dimensions[4].height = 36

    rows_by_id = {row["id"]: row for row in dataset_rows}
    complete = workbook.create_sheet("완전문장_매칭")
    complete.sheet_view.showGridLines = False
    complete.sheet_properties.tabColor = green_title
    complete_headers = [
        "완전 문장 번호",
        "평가셋 ID",
        "매칭 방식",
        "제공 원문",
        "평가셋 문맥",
        "상황별 확장 표현",
        "핵심 긍정 피드백",
        "문맥·과교정 주의",
        "현재 초안 판단",
        "현재 초안 corrected_text",
        "태그",
        "매칭 검수",
        "검수일",
    ]
    set_title(
        complete,
        complete_mapping["title"],
        "번호는 JG ID와 독립적입니다. 중복된 りんご 문장은 문맥 기준으로 JG-070과 JG-071에 각각 배정했습니다.",
        len(complete_headers),
        green_title,
    )
    set_headers(complete, complete_headers)
    for row_number, item in enumerate(complete_mapping["items"], 5):
        matched_rows = [rows_by_id[dataset_id] for dataset_id in item["dataset_ids"]]

        def joined(selector: Any) -> str:
            return "\n---\n".join(selector(row) for row in matched_rows)

        review_dates = sorted({
            row["review"]["reviewed_at"]
            for row in matched_rows
            if row["review"]["reviewed_at"]
        })
        values = [
            item["complete_no"],
            ", ".join(item["dataset_ids"]),
            item["match_type"],
            item["input_text"],
            joined(lambda row: row["input"].get("context") or "문맥 없음"),
            item["nuance_example"],
            item["praise_ko"],
            item["context_note_ko"],
            joined(lambda row: row["expected"]["decision"]),
            joined(lambda row: row["expected"]["corrected_text"]),
            joined(lambda row: ", ".join(row.get("tags", []))),
            "승인",
            ", ".join(review_dates),
        ]
        for column, value in enumerate(values, 1):
            cell = complete.cell(row_number, column, value)
            cell.font = Font(name="Noto Sans CJK KR", size=9)
            cell.alignment = Alignment(vertical="top", wrap_text=True)
            cell.border = border
            cell.fill = PatternFill("solid", fgColor=input_blue if column >= 12 else white)
        complete.row_dimensions[row_number].height = 82
    complete_widths = [14, 18, 26, 38, 52, 42, 48, 58, 24, 38, 40, 15, 14]
    for column, width in enumerate(complete_widths, 1):
        complete.column_dimensions[get_column_letter(column)].width = width
    complete.freeze_panes = "F5"
    complete.auto_filter.ref = "A4:M31"
    complete.print_title_rows = "1:4"
    complete.sheet_properties.pageSetUpPr.fitToPage = True
    complete.page_setup.orientation = "landscape"
    complete.page_setup.paperSize = complete.PAPERSIZE_A3
    complete.page_setup.fitToWidth = 1
    complete.page_setup.fitToHeight = 0
    validation = DataValidation(type="list", formula1='"승인,수정,보류"', allow_blank=True)
    complete.add_data_validation(validation)
    validation.add("L5:L31")
    for status, color in (("승인", green), ("수정", yellow), ("보류", red)):
        complete.conditional_formatting.add(
            "L5:L31",
            CellIsRule(operator="equal", formula=[f'"{status}"'], fill=PatternFill("solid", fgColor=color)),
        )

    complete_reverse = reverse_mapping(complete_mapping, "complete_no")
    correction_reverse = reverse_mapping(correction_mapping, "feedback_no")
    ambiguous_reverse = reverse_mapping(ambiguous_mapping, "ambiguous_no")
    mapped_ids = set(complete_reverse) | set(correction_reverse) | set(ambiguous_reverse)
    nonempty_ids = {row["id"] for row in dataset_rows if row["input"]["text"]}
    empty_ids = [row["id"] for row in dataset_rows if not row["input"]["text"]]
    unmatched_nonempty = sorted(nonempty_ids - mapped_ids)
    if unmatched_nonempty:
        raise ValueError(f"비어 있지 않은 미매칭 문항이 있습니다: {unmatched_nonempty}")
    if mapped_ids - nonempty_ids:
        raise ValueError(f"빈 입력 또는 알 수 없는 문항이 매칭됐습니다: {sorted(mapped_ids - nonempty_ids)}")

    coverage = workbook.create_sheet("전체매칭_현황", 3)
    coverage.sheet_view.showGridLines = False
    coverage.sheet_properties.tabColor = teal_title
    coverage_headers = [
        "평가셋 ID",
        "원문",
        "현재 초안 판단",
        "완전 문장 번호",
        "교정 피드백 번호",
        "애매 문장 번호",
        "매칭 상태",
        "비고",
    ]
    set_title(
        coverage,
        "전체 평가셋 매칭 현황",
        f"전체 {len(dataset_rows)}문항 중 비어 있지 않은 {len(nonempty_ids)}문항은 모두 매칭됐습니다. 빈 입력 {', '.join(empty_ids)}는 문장 목록 매칭 대상에서 제외하되 별도 기록합니다.",
        len(coverage_headers),
        teal_title,
    )
    set_headers(coverage, coverage_headers)
    for row_number, row in enumerate(dataset_rows, 5):
        dataset_id = row["id"]
        sources = sum(
            bool(mapping.get(dataset_id))
            for mapping in (complete_reverse, correction_reverse, ambiguous_reverse)
        )
        if not row["input"]["text"]:
            status = "빈 입력·매칭 제외"
            note = "문장이 없어 외부 문장 번호와 매칭하지 않음; 평가셋에는 유지"
            status_color = gray
        elif sources > 1:
            status = "매칭 완료·복수 목록"
            note = "동일 문장이 서로 다른 외부 분류표에도 포함됨"
            status_color = yellow
        else:
            status = "매칭 완료"
            note = ""
            status_color = green
        values = [
            dataset_id,
            row["input"]["text"],
            row["expected"]["decision"],
            ", ".join(map(str, complete_reverse.get(dataset_id, []))),
            ", ".join(map(str, correction_reverse.get(dataset_id, []))),
            ", ".join(map(str, ambiguous_reverse.get(dataset_id, []))),
            status,
            note,
        ]
        for column, value in enumerate(values, 1):
            cell = coverage.cell(row_number, column, value)
            cell.font = Font(name="Noto Sans CJK KR", size=9)
            cell.alignment = Alignment(vertical="top", wrap_text=True)
            cell.border = border
        coverage.cell(row_number, 7).fill = PatternFill("solid", fgColor=status_color)
        coverage.row_dimensions[row_number].height = 42
    coverage_widths = [14, 42, 26, 18, 20, 18, 24, 55]
    for column, width in enumerate(coverage_widths, 1):
        coverage.column_dimensions[get_column_letter(column)].width = width
    coverage.freeze_panes = "D5"
    coverage.auto_filter.ref = f"A4:H{4 + len(dataset_rows)}"
    coverage.print_title_rows = "1:4"
    coverage.sheet_properties.pageSetUpPr.fitToPage = True
    coverage.page_setup.orientation = "landscape"
    coverage.page_setup.fitToWidth = 1
    coverage.page_setup.fitToHeight = 0

    guide = workbook["사용안내"]
    guide.merge_cells(start_row=28, start_column=2, end_row=28, end_column=5)
    guide.cell(28, 2, "완전 문장 및 전체 매칭 현황")
    guide.cell(28, 2).font = Font(name="Noto Sans CJK KR", size=13, bold=True, color=white)
    guide.cell(28, 2).fill = PatternFill("solid", fgColor=green_title)
    guide.merge_cells(start_row=29, start_column=2, end_row=29, end_column=5)
    guide.cell(29, 2, "‘완전문장_매칭’에서 1~27번을 확인하고, ‘전체매칭_현황’에서 비어 있지 않은 71문항의 전체 커버리지를 확인합니다.")
    guide.cell(29, 2).font = Font(name="Noto Sans CJK KR", size=10)
    guide.cell(29, 2).alignment = Alignment(vertical="top", wrap_text=True)
    guide.cell(29, 2).border = border
    guide.row_dimensions[28].height = 25
    guide.row_dimensions[29].height = 42

    workbook.calculation.fullCalcOnLoad = True
    workbook.calculation.forceFullCalc = True
    workbook.calculation.calcMode = "auto"
    workbook.save(workbook_path)
    return len(nonempty_ids), len(mapped_ids), empty_ids


def main() -> int:
    args = cjk.parse_args()
    rows = base.load_dataset(args.dataset)
    correction_mapping = feedback.load_feedback_mapping(feedback.DEFAULT_MAPPING, rows)
    ambiguous_mapping = ambiguous.load_ambiguous_mapping(
        ambiguous.DEFAULT_AMBIGUOUS_MAPPING, rows
    )
    complete_mapping = load_complete_mapping(DEFAULT_COMPLETE_MAPPING, rows)
    output_dir = args.output_dir.resolve()
    workbook_path = output_dir / "judgment_review_sheet_v0.1.xlsx"
    pdf_path = output_dir / "judgment_review_packet_v0.1.pdf"

    base.build_workbook(rows, workbook_path)
    feedback.add_feedback_mapping_sheet(workbook_path, rows, correction_mapping)
    ambiguous.add_ambiguous_mapping_sheet(workbook_path, rows, ambiguous_mapping)
    nonempty_count, mapped_count, empty_ids = add_complete_and_coverage_sheets(
        workbook_path,
        rows,
        complete_mapping,
        correction_mapping,
        ambiguous_mapping,
    )
    final_feedback.add_final_feedback_sheet(
        workbook_path,
        rows,
        complete_mapping,
        correction_mapping,
        ambiguous_mapping,
    )
    korean_font_path = base.find_pdf_font(args.font_path)
    japanese_font_path = cjk.find_japanese_font(args.japanese_font_path, output_dir)
    korean_name, japanese_name, fully_embedded = cjk.build_cjk_pdf(
        rows, pdf_path, korean_font_path, japanese_font_path
    )

    print(f"dataset: {args.dataset.resolve()}")
    print(f"items: {len(rows)}")
    print(f"complete mapping: {len(complete_mapping['items'])} -> {sum(len(item['dataset_ids']) for item in complete_mapping['items'])} rows")
    print(f"correction mapping: {len(correction_mapping['items'])} -> {sum(len(item['dataset_ids']) for item in correction_mapping['items'])} rows")
    print(f"ambiguous mapping: {len(ambiguous_mapping['items'])} -> {sum(len(item['dataset_ids']) for item in ambiguous_mapping['items'])} rows")
    print(f"coverage: {mapped_count}/{nonempty_count} non-empty rows; empty tracked={','.join(empty_ids)}")
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
