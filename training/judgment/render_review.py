"""Render canonical pilot records as a human-readable Markdown review table."""

from __future__ import annotations

import argparse
from pathlib import Path

from training.judgment.data import load_records, validate_records


def _cell(value) -> str:
    if value is None:
        return "—"
    return str(value).replace("|", "&#124;").replace("\n", "<br>") or "[빈 입력]"


def render(records: list[dict]) -> str:
    lines = [
        "# 일본어 판단 LoRA 파일럿 v0.1 — 검수용 보기",
        "",
        "상태: 300문항 모두 `provisional`. 이 문서는 검수 보기이며 JSONL이 정답 원본입니다.",
        "Qwen3-14B는 어휘·상황 후보만 제공했고 판단·교정·edit는 결정론적 템플릿으로 만들었습니다.",
        "승인 전 학습에는 사용하지 않습니다. 개인 검수자 식별자는 기록하지 않습니다.",
        "",
        "| ID | split | 수준 | 입력 | 문맥 | 판단안 | 교정안 | 오류 유형 | 근거 | 상태 |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in records:
        expected = row["expected"]
        errors = ", ".join(edit["error_type"] for edit in expected["edits"]) or "—"
        lines.append("| " + " | ".join(_cell(value) for value in (
            row["id"], row["split"], row["input"]["learner_level"], row["input"]["text"],
            row["input"]["context"], expected["decision"], expected["corrected_text"], errors,
            expected["reason_ko"], row["review"]["status"],
        )) + " |")
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    records = load_records(args.dataset)
    validate_records(records)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(render(records), encoding="utf-8")
    print(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
