"""Render the future-vs-GitHub architecture document as a CJK-safe PDF."""

from __future__ import annotations

import argparse
import html
import re
from pathlib import Path
from typing import Iterable

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.platypus import (
    Flowable,
    KeepTogether,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)


BASE_DIR = Path(__file__).resolve().parent
DEFAULT_SOURCE = BASE_DIR / "SYSTEM_ARCHITECTURE_FUTURE_VS_GITHUB.md"
DEFAULT_OUTPUT = BASE_DIR / "system_architecture_future_vs_github.pdf"

KR_FONT = "HYSMyeongJo-Medium"
JP_FONT = "HeiseiMin-W3"
JAPANESE_RUN = re.compile(
    r"([\u2e80-\u2eff\u3000-\u30ff\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff\uff66-\uff9f]+)"
)


def register_fonts() -> None:
    pdfmetrics.registerFont(UnicodeCIDFont(KR_FONT))
    pdfmetrics.registerFont(UnicodeCIDFont(JP_FONT))
    pdfmetrics.registerFontFamily(
        KR_FONT,
        normal=KR_FONT,
        bold=KR_FONT,
        italic=KR_FONT,
        boldItalic=KR_FONT,
    )
    pdfmetrics.registerFontFamily(
        JP_FONT,
        normal=JP_FONT,
        bold=JP_FONT,
        italic=JP_FONT,
        boldItalic=JP_FONT,
    )


def cjk_markup(value: str, *, code: bool = False) -> str:
    escaped = html.escape(value, quote=False)
    placeholders: dict[str, str] = {}

    def save(fragment: str) -> str:
        key = f"@@MARKUP{len(placeholders)}@@"
        placeholders[key] = fragment
        return key

    escaped = re.sub(
        r"\[([^\]]+)\]\((https?://[^)]+)\)",
        lambda match: save(
            f'<link href="{html.escape(match.group(2), quote=True)}" '
            f'color="#1F5A7A">{match.group(1)}</link>'
        ),
        escaped,
    )
    escaped = re.sub(r"\*\*(.+?)\*\*", lambda match: save(f"<b>{match.group(1)}</b>"), escaped)
    escaped = re.sub(
        r"`([^`]+)`",
        lambda match: save(
            f'<font name="Courier" color="#7A3E00">{match.group(1)}</font>'
        ),
        escaped,
    )
    if code:
        escaped = escaped.replace("  ", "&nbsp;&nbsp;").replace("\t", "&nbsp;&nbsp;&nbsp;&nbsp;")
    escaped = JAPANESE_RUN.sub(
        lambda match: f'<font name="{JP_FONT}">{match.group(1)}</font>', escaped
    )
    for key, fragment in placeholders.items():
        fragment = JAPANESE_RUN.sub(
            lambda match: f'<font name="{JP_FONT}">{match.group(1)}</font>', fragment
        )
        escaped = escaped.replace(key, fragment)
    return escaped


class ArchitectureDiagram(Flowable):
    """Compact labelled architecture diagrams drawn directly into the PDF."""

    WIDTH = 176 * mm

    def __init__(self, kind: str):
        heights = {"existing": 104 * mm, "target": 128 * mm, "mlops": 103 * mm, "sequence": 132 * mm}
        super().__init__()
        self.kind = kind
        self.width = self.WIDTH
        self.height = heights[kind]

    @staticmethod
    def _box(canvas, x, y, width, height, lines, fill, stroke="#9AA8B3", size=8.2):
        canvas.setFillColor(colors.HexColor(fill))
        canvas.setStrokeColor(colors.HexColor(stroke))
        canvas.setLineWidth(0.7)
        canvas.roundRect(x, y, width, height, 5, fill=1, stroke=1)
        canvas.setFillColor(colors.HexColor("#17324D"))
        canvas.setFont(KR_FONT, size)
        leading = size + 3
        total = leading * len(lines)
        baseline = y + (height + total) / 2 - leading + 1
        for index, line in enumerate(lines):
            canvas.drawCentredString(x + width / 2, baseline - index * leading, line)

    @staticmethod
    def _arrow(canvas, x1, y1, x2, y2, label=None):
        canvas.setStrokeColor(colors.HexColor("#5D6D79"))
        canvas.setFillColor(colors.HexColor("#5D6D79"))
        canvas.setLineWidth(1.1)
        canvas.line(x1, y1, x2, y2)
        angle_horizontal = abs(x2 - x1) >= abs(y2 - y1)
        if angle_horizontal:
            direction = 1 if x2 >= x1 else -1
            canvas.line(x2, y2, x2 - direction * 5, y2 + 3)
            canvas.line(x2, y2, x2 - direction * 5, y2 - 3)
        else:
            direction = 1 if y2 >= y1 else -1
            canvas.line(x2, y2, x2 + 3, y2 - direction * 5)
            canvas.line(x2, y2, x2 - 3, y2 - direction * 5)
        if label:
            canvas.setFont(KR_FONT, 6.8)
            canvas.setFillColor(colors.HexColor("#3F4D57"))
            canvas.drawCentredString((x1 + x2) / 2, (y1 + y2) / 2 + 4, label)

    @staticmethod
    def _title(canvas, width, height, title, subtitle):
        canvas.setFont(KR_FONT, 12)
        canvas.setFillColor(colors.HexColor("#17324D"))
        canvas.drawString(0, height - 15, title)
        canvas.setFont(KR_FONT, 7.4)
        canvas.setFillColor(colors.HexColor("#5D6D79"))
        canvas.drawRightString(width, height - 15, subtitle)
        canvas.setStrokeColor(colors.HexColor("#D5DEE5"))
        canvas.line(0, height - 21, width, height - 21)

    def draw(self):
        if self.kind == "existing":
            self._draw_existing()
        elif self.kind == "target":
            self._draw_target()
        elif self.kind == "mlops":
            self._draw_mlops()
        else:
            self._draw_sequence()

    def _draw_existing(self):
        c = self.canv
        w, h = self.width, self.height
        self._title(c, w, h, "기존 GitHub 런타임 구조", "origin/api @ df66945")
        bw, bh = 82, 42
        self._box(c, 5, 205, bw, bh, ["Raspberry Pi", "Audio + STT"], "#E8F1F7")
        self._box(c, 112, 205, bw, bh, ["FastAPI", "main.py"], "#DDEEDC")
        self._box(c, 220, 235, 92, bh, ["SQLite", "4 tables"], "#F2F2F2")
        self._box(c, 220, 165, 92, 54, ["Analyzer", "validate / classify", "early return"], "#FFF2CC")
        self._box(c, 344, 215, 138, 62, ["Local RAG", "vocab / grammar / error", "TF-IDF examples"], "#FCE4D6")
        self._box(c, 344, 125, 138, 55, ["Prompt + LLM Client", "localhost:1234", "fixed model"], "#E4DFEC")
        self._box(c, 220, 90, 92, 46, ["LLM Parser", "binary result"], "#F4CCCC")
        self._box(c, 112, 90, bw, 46, ["CRUD", "save analysis"], "#D9EAF7")
        self._arrow(c, 87, 226, 112, 226, "HTTP")
        self._arrow(c, 194, 232, 220, 248, "CRUD")
        self._arrow(c, 194, 214, 220, 192, "analyze")
        self._arrow(c, 312, 196, 344, 238, "4 searches")
        self._arrow(c, 312, 180, 344, 151, "prompt")
        self._arrow(c, 344, 143, 312, 113, "raw JSON")
        self._arrow(c, 220, 113, 194, 113, "result")
        self._arrow(c, 153, 90, 250, 69, "SQLite 저장")
        c.setFont(KR_FONT, 7.5)
        c.setFillColor(colors.HexColor("#8A3D3D"))
        c.drawString(5, 38, "핵심 제약: 운영 경로와 모델 평가 결합 · 이진 판단 · 고정 endpoint/model · 문맥/수준 미전달")

    def _draw_target(self):
        c = self.canv
        w, h = self.width, self.height
        self._title(c, w, h, "목표 운영 아키텍처", "계층형 모놀리스 + 독립 GPU inference")
        self._box(c, 4, 300, 88, 45, ["Edge / Client", "Pi STT + idempotency"], "#E8F1F7")
        self._box(c, 111, 300, 88, 45, ["API v1", "auth / validation"], "#DDEEDC")
        self._box(c, 218, 300, 102, 45, ["Application", "JudgmentService", "bounded shadow queue"], "#FFF2CC", size=7.2)
        self._box(c, 345, 300, 137, 45, ["Domain Contract", "decision / edit / advisory"], "#FCE4D6")
        self._arrow(c, 92, 322, 111, 322)
        self._arrow(c, 199, 322, 218, 322)
        self._arrow(c, 320, 322, 345, 322)

        self._box(c, 4, 210, 105, 55, ["Input Gate", "snapshot + language", "system status split"], "#F2F2F2")
        self._box(c, 128, 210, 105, 55, ["Morphology Port", "Sudachi soft features", "fallback"], "#E8F1F7")
        self._box(c, 252, 210, 105, 55, ["Retrieval Port", "TF-IDF first", "versioned evidence"], "#FCE4D6")
        self._box(c, 376, 210, 106, 55, ["Model Gateway", "alias + immutable rev", "timeout / circuit"], "#E4DFEC")
        self._arrow(c, 269, 300, 56, 265, "orchestrate")
        self._arrow(c, 109, 237, 128, 237)
        self._arrow(c, 233, 237, 252, 237)
        self._arrow(c, 357, 237, 376, 237)

        self._box(c, 68, 122, 130, 55, ["Output Gate", "strict JSON + span", "no false acceptable"], "#F4CCCC")
        self._box(c, 218, 122, 130, 55, ["Policy Composer", "grammar vs advisory", "learner feedback"], "#DDEEDC")
        self._box(c, 368, 122, 114, 55, ["Persistence", "runs / edits / evidence", "Alembic"], "#D9EAF7")
        self._arrow(c, 429, 210, 198, 149, "model output")
        self._arrow(c, 198, 149, 218, 149)
        self._arrow(c, 348, 149, 368, 149)

        self._box(c, 4, 44, 144, 46, ["PostgreSQL prod", "SQLite dev"], "#F2F2F2")
        self._box(c, 170, 44, 144, 46, ["Observability", "logs / metrics / traces"], "#FFF2CC")
        self._box(c, 336, 44, 146, 46, ["Model Registry", "base / LoRA / prompt"], "#E4DFEC")
        self._arrow(c, 425, 122, 408, 90)
        self._arrow(c, 368, 145, 242, 90, "request ID")
        self._arrow(c, 429, 210, 409, 90, "deployment")
        c.setFont(KR_FONT, 7.3)
        c.setFillColor(colors.HexColor("#355A3A"))
        c.drawString(4, 18, "실시간 경로와 오프라인 평가를 분리하고, 언어학·검색은 판정기가 아닌 선택적 근거로 사용")

    def _draw_mlops(self):
        c = self.canv
        w, h = self.width, self.height
        self._title(c, w, h, "오프라인 모델 수명주기", "정답 비노출 · 고정 시험지 · 승인 기반 승격")
        y = 215
        xs = [2, 100, 198, 296, 394]
        labels = [
            ["Reviewed Data", "seed/dev/test"],
            ["Leakage Guard", "group/template"],
            ["Runner", "raw outputs"],
            ["Scorer", "quality + speed"],
            ["Selection", "smallest viable"],
        ]
        fills = ["#E8F1F7", "#F4CCCC", "#FFF2CC", "#DDEEDC", "#E4DFEC"]
        for x, lines, fill in zip(xs, labels, fills):
            self._box(c, x, y, 88, 45, lines, fill)
        for index in range(len(xs) - 1):
            self._arrow(c, xs[index] + 88, y + 22, xs[index + 1], y + 22)

        self._box(c, 100, 120, 120, 54, ["Failure Analysis", "grammar / overcorrection", "JSON / latency"], "#FCE4D6")
        self._box(c, 244, 120, 120, 54, ["Targeted Train Data", "3,000 + review", "test excluded"], "#E8F1F7")
        self._box(c, 388, 120, 94, 54, ["One LoRA", "BF16", "24 GPU h cap"], "#E4DFEC")
        self._arrow(c, 438, 215, 160, 174, "if needed")
        self._arrow(c, 220, 147, 244, 147)
        self._arrow(c, 364, 147, 388, 147)

        self._box(c, 244, 42, 120, 46, ["Ablation", "base / Sudachi / RAG"], "#FFF2CC")
        self._box(c, 388, 42, 94, 46, ["Registry", "shadow / canary"], "#DDEEDC")
        self._arrow(c, 435, 120, 304, 88)
        self._arrow(c, 364, 65, 388, 65)
        self._arrow(c, 435, 42, 438, 20, "rollback")
        c.setFont(KR_FONT, 7.2)
        c.setFillColor(colors.HexColor("#8A3D3D"))
        c.drawString(2, 14, "평가모델의 제안은 후보일 뿐이며 사람 검수와 고정 시험을 통과하기 전 자동 재학습·자동 배포 금지")

    def _draw_sequence(self):
        c = self.canv
        w, h = self.width, self.height
        self._title(c, w, h, "실시간 판단 시퀀스", "언어 판단과 실행 장애의 의미 분리")
        left_x, right_x = 18, 280
        box_w, box_h, gap = 205, 42, 12
        left_steps = [
            ["1. API 검증", "auth · idempotency · request ID"],
            ["2. 입력 스냅샷", "원문 · 정규화 · 수준 · 문맥"],
            ["3. Input Gate", "지원 언어 · 누락 · 잡음 상태"],
            ["4. Sudachi 특징", "실패 허용 · soft evidence"],
            ["5. Retrieval Planner", "필요 자료만 검색 · fallback"],
        ]
        right_steps = [
            ["6. Model Router", "alias → base/adapter/prompt"],
            ["7. 판단모델", "decision · correction · edits"],
            ["8. Output Gate", "schema · span · reconstruction"],
            ["9. Policy Composer", "grammar / advisory 분리"],
            ["10. 저장 및 응답", "audit · evidence · latency"],
        ]
        top = 315
        for index, lines in enumerate(left_steps):
            y = top - index * (box_h + gap)
            self._box(c, left_x, y, box_w, box_h, lines, "#E8F1F7" if index % 2 == 0 else "#F2F2F2")
            if index:
                self._arrow(c, left_x + box_w / 2, y + box_h + gap, left_x + box_w / 2, y + box_h)
        for index, lines in enumerate(right_steps):
            y = top - index * (box_h + gap)
            self._box(c, right_x, y, box_w, box_h, lines, "#FFF2CC" if index < 2 else "#DDEEDC")
            if index:
                self._arrow(c, right_x + box_w / 2, y + box_h + gap, right_x + box_w / 2, y + box_h)
        last_left_y = top - 4 * (box_h + gap)
        self._arrow(c, left_x + box_w, last_left_y + box_h / 2, right_x, top + box_h / 2, "versioned evidence")
        c.setFont(KR_FONT, 7.3)
        c.setFillColor(colors.HexColor("#8A3D3D"))
        c.drawString(18, 28, "timeout / unavailable / invalid output → execution_status 실패, 문법 insufficient_evidence와 합치지 않음")


def build_styles():
    sample = getSampleStyleSheet()
    navy = colors.HexColor("#17324D")
    dark = colors.HexColor("#222B31")
    muted = colors.HexColor("#52616B")
    return {
        "title": ParagraphStyle(
            "DocTitle", parent=sample["Title"], fontName=KR_FONT, fontSize=23,
            leading=31, textColor=navy, alignment=TA_CENTER, spaceAfter=8 * mm,
        ),
        "subtitle": ParagraphStyle(
            "DocSubtitle", parent=sample["Normal"], fontName=KR_FONT, fontSize=12,
            leading=19, textColor=muted, alignment=TA_CENTER, spaceAfter=5 * mm,
        ),
        "h1": ParagraphStyle(
            "H1", parent=sample["Heading1"], fontName=KR_FONT, fontSize=17,
            leading=23, textColor=navy, spaceBefore=7 * mm, spaceAfter=3 * mm,
        ),
        "h2": ParagraphStyle(
            "H2", parent=sample["Heading2"], fontName=KR_FONT, fontSize=13,
            leading=18, textColor=colors.HexColor("#1F5A7A"), spaceBefore=5 * mm,
            spaceAfter=2.5 * mm,
        ),
        "h3": ParagraphStyle(
            "H3", parent=sample["Heading3"], fontName=KR_FONT, fontSize=11,
            leading=16, textColor=colors.HexColor("#355A3A"), spaceBefore=3.5 * mm,
            spaceAfter=2 * mm,
        ),
        "body": ParagraphStyle(
            "Body", parent=sample["BodyText"], fontName=KR_FONT, fontSize=8.7,
            leading=14, textColor=dark, alignment=TA_LEFT, wordWrap="CJK",
            spaceAfter=2.2 * mm,
        ),
        "bullet": ParagraphStyle(
            "Bullet", parent=sample["BodyText"], fontName=KR_FONT, fontSize=8.5,
            leading=13.5, leftIndent=5 * mm, firstLineIndent=-3.5 * mm,
            textColor=dark, wordWrap="CJK", spaceAfter=1.2 * mm,
        ),
        "number": ParagraphStyle(
            "Number", parent=sample["BodyText"], fontName=KR_FONT, fontSize=8.5,
            leading=13.5, leftIndent=6 * mm, firstLineIndent=-5 * mm,
            textColor=dark, wordWrap="CJK", spaceAfter=1.2 * mm,
        ),
        "code": ParagraphStyle(
            "Code", parent=sample["Code"], fontName=KR_FONT, fontSize=7.1,
            leading=10.5, textColor=colors.HexColor("#24343E"), wordWrap="CJK",
        ),
        "table": ParagraphStyle(
            "TableText", parent=sample["BodyText"], fontName=KR_FONT, fontSize=6.9,
            leading=10.2, textColor=dark, wordWrap="CJK",
        ),
        "table_header": ParagraphStyle(
            "TableHeader", parent=sample["BodyText"], fontName=KR_FONT, fontSize=7.1,
            leading=10.5, textColor=colors.white, alignment=TA_CENTER, wordWrap="CJK",
        ),
        "caption": ParagraphStyle(
            "Caption", parent=sample["BodyText"], fontName=KR_FONT, fontSize=7.3,
            leading=11, textColor=muted, alignment=TA_CENTER, spaceAfter=3 * mm,
        ),
    }


def table_widths(column_count: int, available: float) -> list[float]:
    presets = {
        2: [0.28, 0.72],
        3: [0.20, 0.34, 0.46],
        4: [0.17, 0.25, 0.29, 0.29],
    }
    fractions = presets.get(column_count, [1 / column_count] * column_count)
    return [available * fraction for fraction in fractions]


def make_table(rows: list[list[str]], styles, available: float) -> Table:
    column_count = max(len(row) for row in rows)
    normalized = [row + [""] * (column_count - len(row)) for row in rows]
    data = []
    for row_index, row in enumerate(normalized):
        style = styles["table_header"] if row_index == 0 else styles["table"]
        data.append([Paragraph(cjk_markup(cell), style) for cell in row])
    table = Table(
        data,
        colWidths=table_widths(column_count, available),
        repeatRows=1,
        hAlign="LEFT",
    )
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#17324D")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F4F7F9")]),
        ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#B8C3CB")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    return table


def is_separator(row: str) -> bool:
    cells = [cell.strip() for cell in row.strip().strip("|").split("|")]
    return bool(cells) and all(re.fullmatch(r":?-{3,}:?", cell) for cell in cells)


def parse_table(lines: list[str], start: int) -> tuple[list[list[str]], int]:
    raw = []
    index = start
    while index < len(lines) and lines[index].strip().startswith("|"):
        raw.append(lines[index])
        index += 1
    if len(raw) >= 2 and is_separator(raw[1]):
        raw.pop(1)
    rows = [[cell.strip() for cell in line.strip().strip("|").split("|")] for line in raw]
    return rows, index


def code_block(lines: list[str], start: int) -> tuple[str, int]:
    block = []
    index = start + 1
    while index < len(lines) and not lines[index].strip().startswith("```"):
        block.append(lines[index])
        index += 1
    return "\n".join(block), min(index + 1, len(lines))


def paragraph_block(lines: list[str], start: int) -> tuple[str, int]:
    parts = []
    index = start
    special = re.compile(r"^(#{1,3})\s|^-\s|^\d+\.\s|^\||^```|^\[PAGEBREAK\]$|^\[DIAGRAM:")
    while index < len(lines):
        stripped = lines[index].strip()
        if not stripped or (index != start and special.match(stripped)):
            break
        parts.append(stripped)
        index += 1
    return " ".join(parts), index


def markdown_to_story(source: str, styles, available: float) -> list:
    lines = source.splitlines()
    story: list = []
    index = 0
    title_seen = False
    while index < len(lines):
        raw = lines[index]
        stripped = raw.strip()
        if not stripped:
            index += 1
            continue
        if stripped == "[PAGEBREAK]":
            story.append(PageBreak())
            index += 1
            continue
        diagram_match = re.fullmatch(r"\[DIAGRAM:(existing|target|mlops|sequence)\]", stripped)
        if diagram_match:
            kind = diagram_match.group(1)
            story.extend([
                Spacer(1, 2 * mm),
                ArchitectureDiagram(kind),
                Paragraph(
                    cjk_markup({
                        "existing": "그림 1. 기존 GitHub 런타임의 실제 호출·저장 구조",
                        "target": "그림 2. 향후 운영 런타임의 책임 분리 구조",
                        "mlops": "그림 3. 데이터에서 승인된 모델 배포까지의 오프라인 수명주기",
                        "sequence": "그림 4. 한 발화가 최종 판단으로 저장되는 순서",
                    }[kind]),
                    styles["caption"],
                ),
            ])
            index += 1
            continue
        if stripped.startswith("```"):
            content, index = code_block(lines, index)
            code_para = Paragraph(cjk_markup(content, code=True).replace("\n", "<br/>"), styles["code"])
            box = Table([[code_para]], colWidths=[available], hAlign="LEFT")
            box.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F2F5F7")),
                ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#C6D0D7")),
                ("LEFTPADDING", (0, 0), (-1, -1), 7),
                ("RIGHTPADDING", (0, 0), (-1, -1), 7),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ]))
            story.extend([box, Spacer(1, 2.5 * mm)])
            continue
        if stripped.startswith("|"):
            rows, index = parse_table(lines, index)
            story.extend([make_table(rows, styles, available), Spacer(1, 3 * mm)])
            continue
        heading = re.match(r"^(#{1,3})\s+(.+)$", stripped)
        if heading:
            level = len(heading.group(1))
            text = heading.group(2)
            if level == 1 and not title_seen:
                story.extend([
                    Spacer(1, 23 * mm),
                    Paragraph(cjk_markup(text), styles["title"]),
                ])
                title_seen = True
            elif level == 2 and text == "기존 GitHub 구조 대비 상세 설계서":
                story.append(Paragraph(cjk_markup(text), styles["subtitle"]))
            else:
                story.append(Paragraph(cjk_markup(text), styles[f"h{level}"]))
            index += 1
            continue
        if stripped.startswith("- "):
            story.append(Paragraph("• " + cjk_markup(stripped[2:]), styles["bullet"]))
            index += 1
            continue
        numbered = re.match(r"^(\d+)\.\s+(.+)$", stripped)
        if numbered:
            story.append(Paragraph(f"{numbered.group(1)}. " + cjk_markup(numbered.group(2)), styles["number"]))
            index += 1
            continue
        text, index = paragraph_block(lines, index)
        story.append(Paragraph(cjk_markup(text), styles["body"]))
    return story


def footer(canvas, doc) -> None:
    canvas.saveState()
    canvas.setStrokeColor(colors.HexColor("#D5DEE5"))
    canvas.line(18 * mm, 13 * mm, A4[0] - 18 * mm, 13 * mm)
    canvas.setFont(KR_FONT, 7)
    canvas.setFillColor(colors.HexColor("#687781"))
    canvas.drawString(18 * mm, 9 * mm, "일본어 STT 교정·판단 튜터 시스템 목표 아키텍처")
    canvas.drawRightString(A4[0] - 18 * mm, 9 * mm, f"{doc.page}")
    canvas.restoreState()


def build_pdf(source_path: Path, output_path: Path) -> None:
    register_fonts()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    doc = SimpleDocTemplate(
        str(output_path),
        pagesize=A4,
        leftMargin=17 * mm,
        rightMargin=17 * mm,
        topMargin=16 * mm,
        bottomMargin=18 * mm,
        title="일본어 STT 교정·판단 튜터 시스템 목표 아키텍처",
        author="Onstt-backend architecture working document",
        subject="기존 GitHub 구조와 목표 시스템 구조의 상세 비교",
        creator="ReportLab",
    )
    styles = build_styles()
    source = source_path.read_text(encoding="utf-8")
    story = markdown_to_story(source, styles, doc.width)
    doc.build(story, onFirstPage=footer, onLaterPages=footer)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    build_pdf(args.source.resolve(), args.output.resolve())
    print(f"source: {args.source.resolve()}")
    print(f"pdf: {args.output.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
