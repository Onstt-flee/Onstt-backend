"""Generate the Excel review sheet and a CJK-safe printable PDF packet."""

from __future__ import annotations

import argparse
import os
import re
from pathlib import Path

from . import _review_materials_base as base


JAPANESE_RUN = re.compile(
    r"([\u2e80-\u2eff\u3000-\u30ff\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff\uff66-\uff9f]+)"
)


def find_japanese_font(explicit_path: Path | None, output_dir: Path) -> Path | None:
    candidates: list[Path] = []
    if explicit_path:
        candidates.append(explicit_path)
    configured = os.environ.get("JUDGMENT_PDF_JAPANESE_FONT")
    if configured:
        candidates.append(Path(configured))
    candidates.extend(
        [
            output_dir / "NotoSansJP.ttf",
            Path("/usr/share/fonts/truetype/noto/NotoSansJP-Regular.ttf"),
        ]
    )
    return next((path for path in candidates if path.is_file()), None)


def build_cjk_pdf(
    rows: list[dict],
    output_path: Path,
    korean_font_path: Path | None,
    japanese_font_path: Path | None,
) -> tuple[str, str, bool]:
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.cidfonts import UnicodeCIDFont
    from reportlab.pdfbase.ttfonts import TTFont

    if japanese_font_path:
        pdfmetrics.registerFont(TTFont("ReviewJapanese", str(japanese_font_path)))
        japanese_font_name = "ReviewJapanese"
    else:
        pdfmetrics.registerFont(UnicodeCIDFont("HeiseiMin-W3"))
        japanese_font_name = "HeiseiMin-W3"

    original_escape = base.html.escape

    def escape_with_japanese_fallback(value: str, quote: bool = True) -> str:
        escaped = original_escape(value, quote=quote).replace("&lt;br/&gt;", "<br/>")
        return JAPANESE_RUN.sub(
            lambda match: f'<font name="{japanese_font_name}">{match.group(1)}</font>',
            escaped,
        )

    base.html.escape = escape_with_japanese_fallback
    try:
        korean_font_name, korean_embedded = base.build_pdf(
            rows, output_path, korean_font_path
        )
    finally:
        base.html.escape = original_escape

    return (
        korean_font_name,
        japanese_font_name,
        bool(korean_embedded and japanese_font_path),
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, default=base.DEFAULT_DATASET)
    parser.add_argument("--output-dir", type=Path, default=base.DEFAULT_OUTPUT_DIR)
    parser.add_argument(
        "--font-path",
        type=Path,
        help="PDF 한글용 TTF/OTF. 이전 명령과 호환을 위해 이 옵션명을 유지합니다.",
    )
    parser.add_argument("--japanese-font-path", type=Path, help="PDF 일본어용 TTF/OTF")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    rows = base.load_dataset(args.dataset)
    output_dir = args.output_dir.resolve()
    workbook_path = output_dir / "judgment_review_sheet_v0.1.xlsx"
    pdf_path = output_dir / "judgment_review_packet_v0.1.pdf"
    korean_font_path = base.find_pdf_font(args.font_path)
    japanese_font_path = find_japanese_font(args.japanese_font_path, output_dir)

    base.build_workbook(rows, workbook_path)
    korean_name, japanese_name, fully_embedded = build_cjk_pdf(
        rows,
        pdf_path,
        korean_font_path,
        japanese_font_path,
    )

    print(f"dataset: {args.dataset.resolve()}")
    print(f"items: {len(rows)}")
    print(f"workbook: {workbook_path}")
    print(f"pdf: {pdf_path}")
    print(
        "pdf fonts: "
        f"korean={korean_name}, japanese={japanese_name}, "
        f"both_embedded={str(fully_embedded).lower()}"
    )
    if not fully_embedded:
        print("warning: 하나 이상의 CJK 글꼴이 PDF 뷰어의 대체 기능에 의존합니다.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
