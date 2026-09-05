"""Add the consolidated, anonymously user-reviewed feedback sheet."""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path
from typing import Any


CHECK_LABELS = {
    "check:filler_preserve": "필러 유지",
    "check:lexical_content_preserve": "의미 있는 회화 표현 유지",
    "check:style_preserve": "문체 변경 불필요",
    "check:style_advisory": "문체 개선 별도 안내",
    "check:orthography_candidate": "표기 정규화 후보",
    "check:attribution_unknown": "학습자·STT 원인 미확인",
    "check:context_mismatch": "질문과 내용 불일치",
    "check:context_match": "질문과 내용 일치",
}

EXAMPLE_TYPE_LABELS = {
    "dialogue_recovery_example": "대화 복구 예시(교정문 아님)",
    "completion_practice_example": "문장 완성 연습 예시(복원 정답 아님)",
    "slot_filling_practice_example": "빈칸 연습 예시(복원 정답 아님)",
    "translation_example": "번역 예시(교정문 아님)",
    "discourse_alternative": "담화 대안(자동 치환 금지)",
    "register_alternative": "문체 대안",
    "style_alternative": "스타일 대안",
}


def _items_by_dataset_id(mapping: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    result: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for item in mapping["items"]:
        for dataset_id in item["dataset_ids"]:
            result[dataset_id].append(item)
    return dict(result)


def _unique_texts(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        value = value.strip()
        if value and value not in seen:
            seen.add(value)
            result.append(value)
    return result


def _source_refs(
    complete_items: list[dict[str, Any]],
    correction_items: list[dict[str, Any]],
    ambiguous_items: list[dict[str, Any]],
) -> str:
    refs = [f"완전 {item['complete_no']}" for item in complete_items]
    refs += [f"교정 {item['feedback_no']}" for item in correction_items]
    refs += [f"애매 {item['ambiguous_no']}" for item in ambiguous_items]
    return ", ".join(refs) or "외부 매칭 없음(빈 입력)"


def _auxiliary_labels(row: dict[str, Any], ambiguous_items: list[dict[str, Any]]) -> str:
    labels = [CHECK_LABELS[tag] for tag in row["tags"] if tag in CHECK_LABELS]
    for item in ambiguous_items:
        if item["category"] == "other_language":
            labels.extend(["지원 범위 밖 언어", "번역 예시 분리"])
        example_type = item["example_type"]
        if example_type == "dialogue_recovery_example":
            labels.append("대화 복구 안내 분리")
        elif example_type in {"completion_practice_example", "slot_filling_practice_example"}:
            labels.append("추측 복원 금지")
    if not row["input"]["text"]:
        labels.append("빈 입력")
    return "; ".join(_unique_texts(labels)) or "없음"


def _learner_feedback(
    row: dict[str, Any],
    complete_items: list[dict[str, Any]],
    correction_items: list[dict[str, Any]],
    ambiguous_items: list[dict[str, Any]],
) -> str:
    expected = row["expected"]
    decision = expected["decision"]
    parts: list[str] = []
    if decision == "needs_correction":
        parts.append(expected["reason_ko"])
        parts.append(f"추천 문장: {expected['corrected_text']}")
        alternatives = [
            text for text in row["accepted_corrections"]
            if text != expected["corrected_text"]
        ]
        if alternatives:
            parts.append("다른 허용 표현: " + " / ".join(alternatives))
    elif decision == "insufficient_evidence":
        if ambiguous_items:
            for item in ambiguous_items:
                parts.append(f"{item['state_ko']}. {item['recommended_action_ko']}.")
                parts.append(item["note_ko"])
        else:
            parts.append(expected["reason_ko"])
    else:
        if complete_items:
            for item in complete_items:
                parts.extend([item["praise_ko"], item["context_note_ko"]])
        else:
            parts.append(expected["reason_ko"])
        for item in correction_items:
            if item["contract_relation"] != "aligned":
                parts.append(item["note_ko"])
        for item in ambiguous_items:
            parts.append(item["note_ko"])
    return " ".join(_unique_texts(parts))


def _reference_examples(
    row: dict[str, Any],
    complete_items: list[dict[str, Any]],
    correction_items: list[dict[str, Any]],
    ambiguous_items: list[dict[str, Any]],
) -> tuple[str, str]:
    decision = row["expected"]["decision"]
    tags = set(row["tags"])
    examples: list[str] = []
    kinds: list[str] = []
    for item in complete_items:
        if item["nuance_example"]:
            examples.append(item["nuance_example"])
            kinds.append("상황별 확장 예시")
    if decision == "acceptable" and {
        "check:style_advisory", "check:orthography_candidate"
    } & tags:
        for item in correction_items:
            if "advisory" in item["contract_relation"]:
                examples.append(item["recommended_text"])
                examples.extend(item["alternatives"])
                if item["contract_relation"] == "orthography_advisory":
                    kinds.append("표기 조언")
                else:
                    kinds.append("문체·스타일 조언")
    for item in ambiguous_items:
        if item["example_type"] == "style_alternative" and "check:style_preserve" in tags:
            continue
        if item["provided_example"]:
            examples.append(item["provided_example"])
            kinds.append(EXAMPLE_TYPE_LABELS[item["example_type"]])
    return "\n".join(_unique_texts(examples)), "; ".join(_unique_texts(kinds))


def _confidence(row: dict[str, Any]) -> str:
    if row["expected"]["decision"] == "insufficient_evidence":
        return "낮음"
    if {"check:style_advisory", "check:orthography_candidate"} & set(row["tags"]):
        return "중간"
    return "높음"


def _review_focus(row: dict[str, Any]) -> str:
    tags = set(row["tags"])
    if row["expected"]["decision"] == "insufficient_evidence":
        return "판단 근거 부족 — 누락 내용과 의도를 추측하지 않음"
    if "check:style_advisory" in tags:
        return "문법 판단과 공식 문체 조언 분리"
    if "check:style_preserve" in tags:
        return "문체 차이를 문법 오류로 강제하지 않음"
    if "check:orthography_candidate" in tags:
        return "문법·표기·발음·STT 귀책 분리"
    if "check:context_mismatch" in tags:
        return "문법과 질문 관련성 분리"
    if "check:context_match" in tags:
        return "동일 원문의 다른 문맥과 구분"
    if "check:filler_preserve" in tags:
        return "필러를 보존하고 실제 문법 오류만 판단"
    if "check:lexical_content_preserve" in tags:
        return "의미 있는 회화 표현을 필러로 삭제하지 않음"
    if row["expected"]["decision"] == "needs_correction":
        return "최소 교정과 원문 의미 보존"
    return "과교정 없이 원문 보존"


def add_final_feedback_sheet(
    workbook_path: Path,
    dataset_rows: list[dict[str, Any]],
    complete_mapping: dict[str, Any],
    correction_mapping: dict[str, Any],
    ambiguous_mapping: dict[str, Any],
) -> None:
    from openpyxl import load_workbook
    from openpyxl.formatting.rule import CellIsRule
    from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
    from openpyxl.utils import get_column_letter

    ids = [row["id"] for row in dataset_rows]
    if len(dataset_rows) != 72 or len(ids) != len(set(ids)):
        raise ValueError("최종 피드백 요약은 고유한 72개 평가셋 문항을 요구합니다.")

    complete_by_id = _items_by_dataset_id(complete_mapping)
    correction_by_id = _items_by_dataset_id(correction_mapping)
    ambiguous_by_id = _items_by_dataset_id(ambiguous_mapping)

    workbook = load_workbook(workbook_path)
    sheet_name = "최종피드백_요약"
    if sheet_name in workbook.sheetnames:
        del workbook[sheet_name]
    insert_at = workbook.sheetnames.index("2차_대조검수") + 1
    sheet = workbook.create_sheet(sheet_name, insert_at)
    sheet.sheet_view.showGridLines = False
    sheet.sheet_properties.tabColor = "1F4E78"

    navy = "17324D"
    white = "FFFFFF"
    light_blue = "D9EAF7"
    input_gray = "F2F2F2"
    green = "DDEEDC"
    yellow = "FFF2CC"
    red = "F4CCCC"
    thin_gray = Side(style="thin", color="C8CDD2")
    border = Border(left=thin_gray, right=thin_gray, top=thin_gray, bottom=thin_gray)

    headers = [
        "ID", "수준", "원문", "문맥", "최종 문법 판단", "최종 corrected_text",
        "허용 교정 후보", "부가 판단", "객관적 검수 근거", "학습자용 피드백",
        "참고 예시", "예시 성격", "외부 자료 매칭", "근거 신뢰도",
        "검수 초점", "검수 상태", "검수일",
    ]
    sheet.merge_cells(start_row=1, start_column=1, end_row=1, end_column=len(headers))
    title = sheet.cell(1, 1, "일본어 판단 평가셋 최종 피드백 요약")
    title.font = Font(name="Noto Sans CJK KR", size=18, bold=True, color=white)
    title.fill = PatternFill("solid", fgColor=navy)
    title.alignment = Alignment(vertical="center")
    sheet.row_dimensions[1].height = 32
    sheet.merge_cells(start_row=2, start_column=1, end_row=2, end_column=len(headers))
    subtitle = sheet.cell(
        2, 1,
        "72문항의 익명 사용자 검수 완료본입니다. 검수자 식별자는 저장하지 않으며, 일본어 전문가 검수나 교육 품질 인증을 의미하지 않습니다.",
    )
    subtitle.font = Font(name="Noto Sans CJK KR", size=10, color="404040")
    subtitle.fill = PatternFill("solid", fgColor=light_blue)
    subtitle.alignment = Alignment(vertical="center", wrap_text=True)
    sheet.row_dimensions[2].height = 36

    for column, header in enumerate(headers, 1):
        cell = sheet.cell(4, column, header)
        cell.font = Font(name="Noto Sans CJK KR", bold=True, color=white)
        cell.fill = PatternFill("solid", fgColor=navy)
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        cell.border = border
    sheet.row_dimensions[4].height = 36

    for row_number, row in enumerate(dataset_rows, 5):
        dataset_id = row["id"]
        complete_items = complete_by_id.get(dataset_id, [])
        correction_items = correction_by_id.get(dataset_id, [])
        ambiguous_items = ambiguous_by_id.get(dataset_id, [])
        reference_text, reference_types = _reference_examples(
            row, complete_items, correction_items, ambiguous_items
        )
        values = [
            dataset_id,
            row["input"]["learner_level"],
            row["input"]["text"],
            row["input"].get("context") or "문맥 없음",
            row["expected"]["decision"],
            row["expected"]["corrected_text"],
            "\n".join(row.get("accepted_corrections", [])),
            _auxiliary_labels(row, ambiguous_items),
            row["expected"]["reason_ko"],
            _learner_feedback(row, complete_items, correction_items, ambiguous_items),
            reference_text,
            reference_types,
            _source_refs(complete_items, correction_items, ambiguous_items),
            _confidence(row),
            _review_focus(row),
            row["review"]["status"],
            row["review"]["reviewed_at"] or "",
        ]
        for column, value in enumerate(values, 1):
            cell = sheet.cell(row_number, column, value)
            cell.font = Font(name="Noto Sans CJK KR", size=9)
            cell.alignment = Alignment(vertical="top", wrap_text=True)
            cell.border = border
            cell.fill = PatternFill("solid", fgColor=input_gray if column <= 4 else "FFFFFF")
        sheet.row_dimensions[row_number].height = 110

    widths = [12, 8, 36, 48, 24, 38, 38, 38, 52, 64, 42, 34, 28, 15, 48, 18, 14]
    for column, width in enumerate(widths, 1):
        sheet.column_dimensions[get_column_letter(column)].width = width

    first_row = 5
    last_row = 4 + len(dataset_rows)
    sheet.freeze_panes = "E5"
    sheet.auto_filter.ref = f"A4:Q{last_row}"
    sheet.print_title_rows = "1:4"
    sheet.sheet_properties.pageSetUpPr.fitToPage = True
    sheet.page_setup.orientation = "landscape"
    sheet.page_setup.paperSize = sheet.PAPERSIZE_A3
    sheet.page_setup.fitToWidth = 1
    sheet.page_setup.fitToHeight = 0
    for status, color in (
        ("acceptable", green),
        ("needs_correction", yellow),
        ("insufficient_evidence", red),
    ):
        sheet.conditional_formatting.add(
            f"E{first_row}:E{last_row}",
            CellIsRule(operator="equal", formula=[f'"{status}"'], fill=PatternFill("solid", fgColor=color)),
        )
    for confidence, color in (("높음", green), ("중간", yellow), ("낮음", red)):
        sheet.conditional_formatting.add(
            f"N{first_row}:N{last_row}",
            CellIsRule(operator="equal", formula=[f'"{confidence}"'], fill=PatternFill("solid", fgColor=color)),
        )

    workbook.calculation.fullCalcOnLoad = True
    workbook.calculation.forceFullCalc = True
    workbook.calculation.calcMode = "auto"
    workbook.save(workbook_path)
