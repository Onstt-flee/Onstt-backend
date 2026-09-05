"""Generate the human-review workbook and printable blind-review packet."""

from __future__ import annotations

import argparse
import html
import json
import os
from pathlib import Path
from typing import Any


BASE_DIR = Path(__file__).resolve().parent
DEFAULT_DATASET = BASE_DIR / "seed_v0.1.jsonl"
DEFAULT_OUTPUT_DIR = BASE_DIR / "review_materials"


def load_dataset(path: Path) -> list[dict[str, Any]]:
    rows = [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    if not rows:
        raise ValueError(f"데이터셋이 비어 있습니다: {path}")

    ids = [row["id"] for row in rows]
    if len(ids) != len(set(ids)):
        raise ValueError("중복 문항 ID가 있습니다.")
    return rows


def stringify(value: Any) -> str:
    if value in (None, [], {}):
        return ""
    if isinstance(value, str):
        return value
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def build_workbook(rows: list[dict[str, Any]], output_path: Path) -> None:
    try:
        from openpyxl import Workbook
        from openpyxl.formatting.rule import CellIsRule
        from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
        from openpyxl.utils import get_column_letter
        from openpyxl.worksheet.datavalidation import DataValidation
    except ImportError as exc:  # pragma: no cover - developer convenience
        raise RuntimeError(
            "Excel 생성에는 openpyxl이 필요합니다. "
            "venv/bin/pip install -r evaluation/judgment/review-requirements.txt"
        ) from exc

    workbook = Workbook()
    workbook.remove(workbook.active)

    navy = "17324D"
    light_blue = "EEF5FB"
    green = "DDEEDC"
    yellow = "FFF2CC"
    red = "F4CCCC"
    gray = "E7E6E6"
    white = "FFFFFF"
    orange = "FCE4D6"
    thin_gray = Side(style="thin", color="C8CDD2")
    border = Border(left=thin_gray, right=thin_gray, top=thin_gray, bottom=thin_gray)
    body_alignment = Alignment(vertical="top", wrap_text=True)

    def title(ws: Any, text: str, subtitle: str, last_column: int) -> None:
        ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=last_column)
        cell = ws.cell(1, 1, text)
        cell.font = Font(name="Noto Sans CJK KR", size=18, bold=True, color=white)
        cell.fill = PatternFill("solid", fgColor=navy)
        cell.alignment = Alignment(vertical="center")
        ws.row_dimensions[1].height = 32
        ws.merge_cells(start_row=2, start_column=1, end_row=2, end_column=last_column)
        cell = ws.cell(2, 1, subtitle)
        cell.font = Font(name="Noto Sans CJK KR", size=10, color="404040")
        cell.fill = PatternFill("solid", fgColor=light_blue)
        cell.alignment = Alignment(vertical="center", wrap_text=True)
        ws.row_dimensions[2].height = 36

    def table_header(ws: Any, row_number: int, labels: list[str]) -> None:
        for column, label in enumerate(labels, 1):
            cell = ws.cell(row_number, column, label)
            cell.font = Font(name="Noto Sans CJK KR", bold=True, color=white)
            cell.fill = PatternFill("solid", fgColor=navy)
            cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
            cell.border = border
        ws.row_dimensions[row_number].height = 32

    def finish_table(ws: Any, min_row: int, max_row: int, max_column: int) -> None:
        for row in ws.iter_rows(min_row=min_row, max_row=max_row, max_col=max_column):
            for cell in row:
                cell.font = Font(name="Noto Sans CJK KR", size=10)
                cell.alignment = body_alignment
                cell.border = border

    guide = workbook.create_sheet("사용안내")
    guide.sheet_view.showGridLines = False
    title(
        guide,
        "일본어 판단 평가셋 사람 검수표 v0.1",
        f"대상: {len(rows)}개 합성 문항 · 익명 사용자 검수 완료 · Excel 기록본이 검수 결과 취합의 기준입니다.",
        6,
    )
    guide.column_dimensions["A"].width = 4
    guide.column_dimensions["B"].width = 24
    guide.column_dimensions["C"].width = 31
    guide.column_dimensions["D"].width = 31
    guide.column_dimensions["E"].width = 31
    guide.column_dimensions["F"].width = 4
    guide_rows = [
        (4, "권장 사용 순서", navy),
        (5, "1", "‘최종피드백_요약’에서 72문항의 판단·교정·부가 조언·신뢰도를 한 번에 확인합니다."),
        (6, "2", "‘2차_대조검수’에서 익명 사용자 승인·확정 판단·교정문·검수일을 확인합니다."),
        (7, "3", "세 매칭 시트에서 외부 번호와 JG ID, 교정문·복구문·스타일 조언의 분리를 확인합니다."),
        (8, "4", "독립 재검수가 필요할 때만 PDF 또는 ‘1차_블라인드’ 시트를 사용합니다."),
        (10, "중요 원칙", navy),
        (11, "블라인드", "1차 판단 전에는 ‘2차_대조검수’의 초안 정답을 열어보지 않습니다."),
        (12, "승인", "현재 초안 판단·교정·근거를 그대로 채택할 때만 선택합니다."),
        (13, "수정", "라벨, 교정문, 근거 또는 문항 문맥을 고쳐야 할 때 선택합니다. 재확인 전 JSONL은 provisional을 유지합니다."),
        (14, "보류", "검토자 사이에 이견이 있거나 일본어 전문가 확인이 필요할 때 선택합니다."),
        (15, "제외", "문항이 인위적이거나 중복·범위 밖이라 시험지에서 제거/대체해야 할 때 선택합니다."),
        (17, "완료 기준", navy),
        (18, "필수", "72개 전체가 승인·수정·보류·제외 중 하나로 처리되고 검수일이 기록되어야 합니다."),
        (19, "전문가", "가능하면 전체를 검수합니다. 최소한 needs_correction, 경계 사례, 복수 정답과 정상 문장 표본은 전문가에게 전달합니다."),
        (20, "반영", "익명 사용자 승인 결과를 seed_v0.1.jsonl과 Excel에 반영했습니다. 변경 시 자동 검사를 다시 실행합니다."),
    ]
    for row_number, label, content in guide_rows:
        if content == navy:
            guide.merge_cells(start_row=row_number, start_column=2, end_row=row_number, end_column=5)
            cell = guide.cell(row_number, 2, label)
            cell.font = Font(name="Noto Sans CJK KR", size=13, bold=True, color=white)
            cell.fill = PatternFill("solid", fgColor=navy)
            cell.alignment = Alignment(vertical="center")
            guide.row_dimensions[row_number].height = 25
            continue
        guide.cell(row_number, 2, label)
        guide.merge_cells(start_row=row_number, start_column=3, end_row=row_number, end_column=5)
        guide.cell(row_number, 3, content)
        for cell in guide[row_number][1:5]:
            cell.border = border
            cell.alignment = body_alignment
            cell.font = Font(name="Noto Sans CJK KR", size=10, bold=cell.column == 2)
        guide.row_dimensions[row_number].height = 42

    criteria = workbook.create_sheet("판단기준")
    criteria.sheet_view.showGridLines = False
    title(
        criteria,
        "검수 기준",
        "문법 판단과 필러·문체·표기·문맥 보조 항목을 분리합니다. acceptable은 모든 품질 차원을 통과했다는 뜻이 아닙니다.",
        5,
    )
    for column, width in zip("ABCDE", [21, 28, 54, 47, 22]):
        criteria.column_dimensions[column].width = width
    labels = ["구분", "상태/항목", "판정 기준", "확인 질문", "대표 문항"]
    table_header(criteria, 4, labels)
    criteria_rows = [
        ("문법 판단", "acceptable", "주어진 텍스트의 문법 구조를 고칠 필요가 없음. 원문과 수정 구간을 유지.", "명확한 문법 오류가 정말 없는가? 단순한 취향 수정은 아닌가?", "JG-001, 003"),
        ("문법 판단", "needs_correction", "의미를 보존하는 최소 교정의 근거가 명확함. 모든 명확한 오류를 기록.", "의미·시제·긍부정·말투를 보존했는가?", "JG-009, 062"),
        ("문법 판단", "insufficient_evidence", "전사 누락·녹음 중단·비일본어 등으로 문법 판단 증거가 부족함.", "짧다는 이유만으로 보류한 것은 아닌가? 시스템 실패와 섞지 않았는가?", "JG-051 등"),
        ("경계 기준", "필러·간투어", "문장에 포함된 필러는 유지하고 명확한 문법 오류만 교정. 필러뿐이면 보류.", "あのう/ええと를 가독성 이유로 삭제하지 않았는가? なんか의 문장 역할은 무엇인가?", "JG-061~063"),
        ("경계 기준", "문체 혼용", "혼용만으로 문법 오류로 만들지 않음. 명시적 문체 요구 불일치는 별도 제안.", "직접 인용·종속절·담화 효과를 단순 혼용으로 오인하지 않았는가?", "JG-064~066"),
        ("경계 기준", "표기·STT·발음", "표기 정규화 후보와 문법 오류를 분리. 원음 없이 학습자/STT 귀책을 단정하지 않음.", "현재 문법 전용 계약에서 처리할 사항인가? 원음이 실제로 있는가?", "JG-067~069"),
        ("경계 기준", "질문 관련성", "문법 판단과 질문 적합성을 분리. 동문서답을 고치려고 새 내용을 생성하지 않음.", "문법 오류와 문맥 불일치가 동시에 존재하는가?", "JG-070~072"),
        ("교정 품질", "최소 교정", "필요한 부분만 바꾸고 원문 의미와 화자의 말투를 보존.", "더 작은 수정으로 같은 오류를 해결할 수 있는가?", "전체"),
        ("교정 품질", "오류 구간", "Unicode 코드 포인트 기준 0부터 시작하는 [start,end). edits 적용 결과가 corrected_text와 일치.", "source가 원문 구간과 같고 edits가 겹치지 않는가?", "needs_correction"),
        ("교정 품질", "복수 정답", "に/へ처럼 둘 이상의 자연스러운 교정 후보를 인정. 후보 목록 밖도 사람이 검토.", "문자열이 다르다는 이유만으로 정답을 배제하지 않았는가?", "복수 후보 문항"),
        ("설명 품질", "reason_ko", "판단과 실제 교정에 대응하는 짧고 이해하기 쉬운 한국어 근거.", "확인하지 않은 발음·의도·능력·오류 원인을 단정하지 않았는가?", "전체"),
    ]
    for row_number, values in enumerate(criteria_rows, 5):
        for column, value in enumerate(values, 1):
            criteria.cell(row_number, column, value)
        criteria.row_dimensions[row_number].height = 72
    finish_table(criteria, 5, 4 + len(criteria_rows), len(labels))
    criteria.freeze_panes = "A5"
    criteria.auto_filter.ref = f"A4:E{4 + len(criteria_rows)}"
    criteria.print_title_rows = "1:4"
    criteria.sheet_properties.pageSetUpPr.fitToPage = True
    criteria.page_setup.fitToWidth = 1
    criteria.page_setup.fitToHeight = 0
    criteria.sheet_properties.tabColor = "70AD47"

    blind = workbook.create_sheet("1차_블라인드")
    blind.sheet_view.showGridLines = False
    title(
        blind,
        "1차 블라인드 검수",
        "독립 재검수가 필요할 때 사용합니다. 기존 초안 정답은 포함하지 않았습니다. 회색 열은 문항 정보, 파란색 열은 검수 입력입니다.",
        11,
    )
    blind_headers = [
        "ID", "수준", "검수 문장", "문맥", "독립 판단*", "교정문",
        "오류 유형/구간", "판단 근거", "보조 항목", "추가 의견", "검수일*",
    ]
    table_header(blind, 4, blind_headers)
    blind_widths = [12, 8, 34, 45, 23, 34, 28, 42, 28, 38, 14]
    for index, width in enumerate(blind_widths, 1):
        blind.column_dimensions[get_column_letter(index)].width = width
    for row_number, item in enumerate(rows, 5):
        input_data = item["input"]
        values = [
            item["id"], input_data["learner_level"], input_data["text"],
            input_data.get("context") or "", "", "", "", "", "", "", "",
        ]
        for column, value in enumerate(values, 1):
            blind.cell(row_number, column, value)
        for column in range(1, 5):
            blind.cell(row_number, column).fill = PatternFill("solid", fgColor=gray)
        for column in range(5, 12):
            blind.cell(row_number, column).fill = PatternFill("solid", fgColor=light_blue)
        blind.row_dimensions[row_number].height = 72
    first_data_row = 5
    last_data_row = 4 + len(rows)
    finish_table(blind, first_data_row, last_data_row, len(blind_headers))
    blind.freeze_panes = "E5"
    blind.auto_filter.ref = f"A4:K{last_data_row}"
    blind.print_title_rows = "1:4"
    blind.sheet_properties.pageSetUpPr.fitToPage = True
    blind.page_setup.orientation = "landscape"
    blind.page_setup.paperSize = blind.PAPERSIZE_A3
    blind.page_setup.fitToWidth = 1
    blind.page_setup.fitToHeight = 0
    blind.sheet_properties.tabColor = "5B9BD5"
    decision_validation = DataValidation(
        type="list", formula1='"acceptable,needs_correction,insufficient_evidence"', allow_blank=True
    )
    decision_validation.error = "세 가지 문법 판단 중 하나를 선택하세요."
    decision_validation.errorTitle = "허용되지 않은 판단"
    decision_validation.prompt = "문법 판단을 선택하세요."
    decision_validation.promptTitle = "1차 독립 판단"
    decision_validation.showErrorMessage = True
    decision_validation.showInputMessage = True
    blind.add_data_validation(decision_validation)
    decision_validation.add(f"E{first_data_row}:E{last_data_row}")
    for status, color in (("acceptable", green), ("needs_correction", yellow), ("insufficient_evidence", red)):
        blind.conditional_formatting.add(
            f"E{first_data_row}:E{last_data_row}",
            CellIsRule(operator="equal", formula=[f'"{status}"'], fill=PatternFill("solid", fgColor=color)),
        )

    compare = workbook.create_sheet("2차_대조검수")
    compare.sheet_view.showGridLines = False
    title(
        compare,
        "2차 익명 대조 검수",
        "2026-09-04에 취합·대조한 결과를 익명 사용자 승인으로 기록했습니다. 전문가 검수 완료를 의미하지 않습니다.",
        17,
    )
    compare_headers = [
        "ID", "수준", "검수 문장", "문맥", "초안 판단", "초안 교정문", "초안 edits",
        "허용 교정 후보", "초안 근거", "태그", "최종 처리*", "확정 판단", "확정 교정문",
        "수정/보류/제외 사유", "검수일*", "전문가 필요", "전문가 의견",
    ]
    table_header(compare, 4, compare_headers)
    compare_widths = [12, 8, 34, 45, 23, 34, 38, 36, 44, 33, 15, 23, 34, 42, 14, 14, 42]
    for index, width in enumerate(compare_widths, 1):
        compare.column_dimensions[get_column_letter(index)].width = width
    for row_number, item in enumerate(rows, 5):
        input_data = item["input"]
        expected = item["expected"]
        values = [
            item["id"], input_data["learner_level"], input_data["text"], input_data.get("context") or "",
            expected["decision"], expected["corrected_text"], stringify(expected["edits"]),
            stringify(item.get("accepted_corrections", [])), expected["reason_ko"],
            ", ".join(item.get("tags", [])), "승인", expected["decision"],
            expected["corrected_text"], "", item["review"]["reviewed_at"] or "", "", "",
        ]
        for column, value in enumerate(values, 1):
            compare.cell(row_number, column, value)
        for column in range(1, 11):
            compare.cell(row_number, column).fill = PatternFill("solid", fgColor=orange)
        for column in range(11, 18):
            compare.cell(row_number, column).fill = PatternFill("solid", fgColor=light_blue)
        compare.row_dimensions[row_number].height = 86
    finish_table(compare, first_data_row, last_data_row, len(compare_headers))
    compare.freeze_panes = "K5"
    compare.auto_filter.ref = f"A4:Q{last_data_row}"
    compare.print_title_rows = "1:4"
    compare.sheet_properties.pageSetUpPr.fitToPage = True
    compare.page_setup.orientation = "landscape"
    compare.page_setup.paperSize = compare.PAPERSIZE_A3
    compare.page_setup.fitToWidth = 1
    compare.page_setup.fitToHeight = 0
    compare.sheet_properties.tabColor = "ED7D31"
    disposition_validation = DataValidation(type="list", formula1='"승인,수정,보류,제외"', allow_blank=True)
    compare.add_data_validation(disposition_validation)
    disposition_validation.add(f"K{first_data_row}:K{last_data_row}")
    confirmed_decision_validation = DataValidation(
        type="list", formula1='"acceptable,needs_correction,insufficient_evidence"', allow_blank=True
    )
    compare.add_data_validation(confirmed_decision_validation)
    confirmed_decision_validation.add(f"L{first_data_row}:L{last_data_row}")
    expert_validation = DataValidation(type="list", formula1='"아니오,예"', allow_blank=True)
    compare.add_data_validation(expert_validation)
    expert_validation.add(f"P{first_data_row}:P{last_data_row}")
    for status, color in (("승인", green), ("수정", yellow), ("보류", red), ("제외", gray)):
        compare.conditional_formatting.add(
            f"K{first_data_row}:K{last_data_row}",
            CellIsRule(operator="equal", formula=[f'"{status}"'], fill=PatternFill("solid", fgColor=color)),
        )

    summary = workbook.create_sheet("요약", 1)
    summary.sheet_view.showGridLines = False
    title(
        summary,
        "검수 완료 요약",
        "수식 기반 현황판입니다. Excel/LibreOffice에서 파일을 열면 입력 내용에 따라 자동 계산됩니다.",
        5,
    )
    for column, width in zip("ABCDE", [34, 18, 18, 38, 5]):
        summary.column_dimensions[column].width = width
    table_header(summary, 4, ["지표", "건수", "비율", "완료 기준/해석", ""])
    summary_rows = [
        ("전체 문항", f"=COUNTA('2차_대조검수'!A{first_data_row}:A{last_data_row})", "=B5/B5", "72개 전체가 처리 대상"),
        ("1차 판단 완료", f'=COUNTIF(\'1차_블라인드\'!E{first_data_row}:E{last_data_row},"<>")', "=B6/$B$5", "초안 정답을 보기 전 독립 판단"),
        ("2차 최종 처리 완료", f'=COUNTIF(\'2차_대조검수\'!K{first_data_row}:K{last_data_row},"<>")', "=B7/$B$5", "승인·수정·보류·제외 중 하나"),
        ("승인", f'=COUNTIF(\'2차_대조검수\'!K{first_data_row}:K{last_data_row},"승인")', "=B8/$B$5", "초안 그대로 채택"),
        ("수정", f'=COUNTIF(\'2차_대조검수\'!K{first_data_row}:K{last_data_row},"수정")', "=B9/$B$5", "확정 판단/교정과 사유 입력 필요"),
        ("보류", f'=COUNTIF(\'2차_대조검수\'!K{first_data_row}:K{last_data_row},"보류")', "=B10/$B$5", "쟁점 또는 전문가 확인 필요"),
        ("제외", f'=COUNTIF(\'2차_대조검수\'!K{first_data_row}:K{last_data_row},"제외")', "=B11/$B$5", "대체 또는 제거 사유 필요"),
        ("미처리", "=B5-B7", "=B12/$B$5", "최종 목표 0건"),
        ("전문가 검수 필요", f'=COUNTIF(\'2차_대조검수\'!P{first_data_row}:P{last_data_row},"예")', "=B13/$B$5", "전문가에게 별도 전달"),
    ]
    for row_number, values in enumerate(summary_rows, 5):
        for column, value in enumerate(values, 1):
            summary.cell(row_number, column, value)
        summary.cell(row_number, 3).number_format = "0.0%"
        summary.row_dimensions[row_number].height = 30
    finish_table(summary, 5, 4 + len(summary_rows), 4)
    for cell in ("A12", "B12", "C12"):
        summary[cell].fill = PatternFill("solid", fgColor=red)
    summary.sheet_properties.tabColor = "A5A5A5"

    for ws in workbook.worksheets:
        ws.sheet_view.zoomScale = 85
        ws.sheet_properties.outlinePr.summaryBelow = True
    workbook.calculation.fullCalcOnLoad = True
    workbook.calculation.forceFullCalc = True
    workbook.calculation.calcMode = "auto"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    workbook.save(output_path)


def find_pdf_font(explicit_path: Path | None) -> Path | None:
    candidates: list[Path] = []
    if explicit_path:
        candidates.append(explicit_path)
    configured = os.environ.get("JUDGMENT_PDF_FONT")
    if configured:
        candidates.append(Path(configured))
    candidates.extend(
        [
            BASE_DIR / "review_materials" / "NotoSansKR.ttf",
            Path("/usr/share/fonts/truetype/noto/NotoSansKR-Regular.ttf"),
            Path("/usr/share/fonts/opentype/noto/NotoSansCJKkr-Regular.otf"),
        ]
    )
    return next((candidate for candidate in candidates if candidate.is_file()), None)


def build_pdf(
    rows: list[dict[str, Any]], output_path: Path, font_path: Path | None
) -> tuple[str, bool]:
    try:
        from reportlab.lib import colors
        from reportlab.lib.enums import TA_CENTER, TA_LEFT
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
        from reportlab.lib.units import mm
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.cidfonts import UnicodeCIDFont
        from reportlab.pdfbase.ttfonts import TTFont
        from reportlab.platypus import (
            KeepTogether, PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle,
        )
    except ImportError as exc:  # pragma: no cover - developer convenience
        raise RuntimeError(
            "PDF 생성에는 reportlab이 필요합니다. "
            "venv/bin/pip install -r evaluation/judgment/review-requirements.txt"
        ) from exc

    embedded = False
    if font_path:
        pdfmetrics.registerFont(TTFont("ReviewCJK", str(font_path)))
        font_name = "ReviewCJK"
        embedded = True
    else:
        pdfmetrics.registerFont(UnicodeCIDFont("HYSMyeongJo-Medium"))
        font_name = "HYSMyeongJo-Medium"

    page_width, _ = A4
    navy = colors.HexColor("#17324D")
    blue = colors.HexColor("#DCEAF7")
    light_blue = colors.HexColor("#F3F7FA")
    line = colors.HexColor("#AAB4BD")
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "ReviewTitle", parent=styles["Title"], fontName=font_name, fontSize=23,
        leading=31, textColor=navy, alignment=TA_CENTER, wordWrap="CJK", spaceAfter=8 * mm,
    )
    subtitle_style = ParagraphStyle(
        "ReviewSubtitle", parent=styles["Normal"], fontName=font_name, fontSize=11,
        leading=18, textColor=colors.HexColor("#3D4A55"), alignment=TA_CENTER, wordWrap="CJK",
    )
    heading_style = ParagraphStyle(
        "ReviewHeading", parent=styles["Heading2"], fontName=font_name, fontSize=15,
        leading=20, textColor=navy, wordWrap="CJK", spaceBefore=4 * mm, spaceAfter=3 * mm,
    )
    body_style = ParagraphStyle(
        "ReviewBody", parent=styles["BodyText"], fontName=font_name, fontSize=9.2,
        leading=14, textColor=colors.HexColor("#20262C"), alignment=TA_LEFT, wordWrap="CJK",
    )
    small_style = ParagraphStyle("ReviewSmall", parent=body_style, fontSize=7.8, leading=11)
    item_heading_style = ParagraphStyle(
        "ItemHeading", parent=body_style, fontSize=11, leading=15, textColor=colors.white,
    )
    sentence_style = ParagraphStyle("Sentence", parent=body_style, fontSize=12, leading=18)

    def para(value: Any, style: Any = body_style) -> Any:
        text = html.escape(str(value)) if value not in (None, "") else "없음"
        return Paragraph(text.replace("\n", "<br/>"), style)

    def footer(canvas: Any, doc: Any) -> None:
        canvas.saveState()
        canvas.setFont(font_name, 7.5)
        canvas.setFillColor(colors.HexColor("#68737D"))
        canvas.drawString(18 * mm, 10 * mm, "일본어 판단 평가셋 v0.1 · 독립 블라인드 재검수본")
        canvas.drawRightString(page_width - 18 * mm, 10 * mm, f"{doc.page}")
        canvas.restoreState()

    doc = SimpleDocTemplate(
        str(output_path), pagesize=A4, rightMargin=17 * mm, leftMargin=17 * mm,
        topMargin=17 * mm, bottomMargin=17 * mm,
        title="일본어 판단 평가셋 v0.1 사람 검수 패킷", author="Onstt-backend",
        subject="72개 합성 문항의 독립 블라인드 재검수",
    )
    story: list[Any] = [
        Spacer(1, 20 * mm),
        Paragraph("일본어 판단 평가셋<br/>사람 검수 패킷 v0.1", title_style),
        Paragraph(f"검수 대상 {len(rows)}문항 · 독립 블라인드 재검수용 · 확정 정답 미포함", subtitle_style),
        Spacer(1, 18 * mm),
        Table(
            [
                [para("검수 기준일"), para("2026-09-04")],
                [para("검수 범위"), para(f"전체 {len(rows)}문항")],
            ],
            colWidths=[35 * mm, 110 * mm],
            style=TableStyle([
                ("GRID", (0, 0), (-1, -1), 0.6, line), ("BACKGROUND", (0, 0), (0, -1), blue),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ("RIGHTPADDING", (0, 0), (-1, -1), 8), ("TOPPADDING", (0, 0), (-1, -1), 8),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
            ]),
        ),
        Spacer(1, 18 * mm),
        Paragraph(
            "먼저 이 PDF에서 독립 판단을 완료한 뒤 Excel의 ‘2차_대조검수’ 시트에서 기존 초안과 비교합니다. "
            "현재 라벨은 익명 사용자 검수를 완료했으며, 일본어 전문가 검수나 교육 품질 인증을 의미하지 않습니다.",
            body_style,
        ),
        PageBreak(),
        Paragraph("1. 핵심 판단 기준", heading_style),
    ]
    label_table = [
        [para("판단", small_style), para("사용 기준", small_style)],
        [para("acceptable", small_style), para("문법 구조를 고칠 필요가 없습니다. 표기·발음·문체·문맥까지 모두 정상이라는 뜻은 아닙니다.", small_style)],
        [para("needs_correction", small_style), para("의미를 보존하는 최소 문법 교정의 근거가 명확합니다. 복합 오류는 모두 기록합니다.", small_style)],
        [para("insufficient_evidence", small_style), para("전사 누락·녹음 중단·비일본어 등으로 판단 증거가 부족합니다. 짧다는 이유만으로 쓰지 않습니다.", small_style)],
    ]
    story.append(Table(
        label_table, colWidths=[43 * mm, 112 * mm], repeatRows=1,
        style=TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), navy), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("GRID", (0, 0), (-1, -1), 0.5, line), ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 7), ("RIGHTPADDING", (0, 0), (-1, -1), 7),
            ("TOPPADDING", (0, 0), (-1, -1), 7), ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
        ]),
    ))
    story.extend([Spacer(1, 5 * mm), Paragraph("2. 경계 사례 기준", heading_style)])
    boundary_rows = [
        ("필러", "문장에 포함된 필러는 유지하고 문법 오류만 교정합니다. 필러뿐이면 보류합니다."),
        ("문체", "혼용만으로 문법 오류로 만들지 않습니다. 명시적 요구와의 불일치는 별도 의견입니다."),
        ("표기/STT", "표기 후보와 문법 오류를 분리하며, 원음 없이 학습자와 STT 중 원인을 단정하지 않습니다."),
        ("질문 적합성", "동문서답과 문법 판단을 분리하며, 질문에 맞추기 위해 새 답을 생성하지 않습니다."),
    ]
    story.append(Table(
        [[para("항목", small_style), para("기준", small_style)]]
        + [[para(name, small_style), para(rule, small_style)] for name, rule in boundary_rows],
        colWidths=[35 * mm, 120 * mm],
        style=TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), navy), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("GRID", (0, 0), (-1, -1), 0.5, line), ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 7), ("RIGHTPADDING", (0, 0), (-1, -1), 7),
            ("TOPPADDING", (0, 0), (-1, -1), 6), ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ]),
    ))
    story.extend([
        Spacer(1, 5 * mm), Paragraph("3. 문항별 체크리스트", heading_style),
        Paragraph(
            "[ ] text·context·level을 함께 확인  &nbsp;&nbsp; "
            "[ ] 의미·시제·긍부정·말투 보존  &nbsp;&nbsp; "
            "[ ] 필요한 부분만 최소 교정<br/>"
            "[ ] 복합 오류 누락 없음  &nbsp;&nbsp; "
            "[ ] 여러 자연스러운 교정 후보 고려  &nbsp;&nbsp; "
            "[ ] 근거 없는 발음·의도·귀책 단정 없음<br/>"
            "[ ] reason_ko가 판단·교정에 대응  &nbsp;&nbsp; "
            "[ ] 이견은 보류하고 전문가 필요 여부 표시", body_style,
        ),
        Spacer(1, 5 * mm), Paragraph("4. 기록 방법", heading_style),
        Paragraph(
            "각 문항에서 먼저 독립 판단과 교정문을 작성합니다. 그다음 Excel에서 초안과 비교해 승인·수정·보류·제외를 기록합니다. "
            "PDF 필기본은 증빙/공유용이고, 최종 취합은 Excel을 기준으로 합니다.", body_style,
        ),
        PageBreak(),
    ])

    for index, item in enumerate(rows):
        input_data = item["input"]
        context = input_data.get("context") or "없음"
        header = Table(
            [[Paragraph(f"{html.escape(item['id'])} · {html.escape(input_data['learner_level'])}", item_heading_style)]],
            colWidths=[176 * mm],
            style=TableStyle([
                ("BACKGROUND", (0, 0), (-1, -1), navy), ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ("RIGHTPADDING", (0, 0), (-1, -1), 8), ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ]),
        )
        card_rows = [
            [para("검수 문장", small_style), para(input_data["text"], sentence_style)],
            [para("문맥", small_style), para(context, body_style)],
            [para("독립 판단", small_style), para("[ ] acceptable    [ ] needs_correction    [ ] insufficient_evidence", body_style)],
            [para("교정문", small_style), para("________________________________________________________________________________", body_style)],
            [para("오류 유형/구간", small_style), para("________________________________________________________________________________", body_style)],
            [para("근거·보조 항목", small_style), para("________________________________________________________________________________<br/>________________________________________________________________________________", body_style)],
            [para("2차 처리", small_style), para("[ ] 승인    [ ] 수정    [ ] 보류    [ ] 제외       전문가 필요: [ ] 아니오  [ ] 예", body_style)],
        ]
        card = Table(
            card_rows, colWidths=[30 * mm, 146 * mm],
            style=TableStyle([
                ("GRID", (0, 0), (-1, -1), 0.5, line), ("BACKGROUND", (0, 0), (0, -1), blue),
                ("BACKGROUND", (1, 0), (1, 1), light_blue), ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 6), ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ]),
        )
        story.append(KeepTogether([header, card]))
        if index % 2 == 0:
            story.append(Spacer(1, 6 * mm))
        elif index != len(rows) - 1:
            story.append(PageBreak())

    output_path.parent.mkdir(parents=True, exist_ok=True)
    doc.build(story, onFirstPage=footer, onLaterPages=footer)
    return font_name, embedded


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument(
        "--font-path", type=Path,
        help="PDF에 포함할 한글·일본어 지원 TTF/OTF. 미지정 시 시스템 글꼴 또는 CID 폴백을 사용합니다.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    rows = load_dataset(args.dataset)
    output_dir = args.output_dir.resolve()
    workbook_path = output_dir / "judgment_review_sheet_v0.1.xlsx"
    pdf_path = output_dir / "judgment_review_packet_v0.1.pdf"
    build_workbook(rows, workbook_path)
    selected_font = find_pdf_font(args.font_path)
    font_name, embedded = build_pdf(rows, pdf_path, selected_font)
    print(f"dataset: {args.dataset.resolve()}")
    print(f"items: {len(rows)}")
    print(f"workbook: {workbook_path}")
    print(f"pdf: {pdf_path}")
    print(f"pdf font: {font_name} (embedded={str(embedded).lower()})")
    if not embedded:
        print("warning: PDF 뷰어 글꼴 대체에 의존합니다. --font-path로 Noto Sans KR을 권장합니다.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
