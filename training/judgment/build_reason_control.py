"""Build the v0.2-A ChatML view with deterministic training rationales."""

from __future__ import annotations

import argparse
from collections import Counter
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

from evaluation.judgment.runner import SYSTEM_PROMPT
from training.judgment.data import load_records, validate_records


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SOURCE = Path(__file__).with_name("data") / "pilot_v0.1.reviewed.jsonl"
DEFAULT_OUTPUT_DIR = Path(__file__).with_name("data") / "reason_control_v0.2_a"
DEFAULT_MANIFEST = Path(__file__).with_name("data") / "reason_control_v0.2_a.manifest.json"
CONTROL_VERSION = "reason-control-v0.2-a"


REASONS_BY_FAMILY = {
    "acceptable_action_location": "동작이 일어나는 장소에 조사 で를 올바르게 사용했습니다.",
    "acceptable_colloquial_ellipsis": "친밀한 회화에서는 문맥으로 분명한 조사를 생략할 수 있습니다.",
    "acceptable_conditional_potential": "조건을 나타내는 なら와 가능형의 연결이 올바릅니다.",
    "acceptable_contraction": "친밀한 회화에서는 〜ている를 〜てる로 줄여 말할 수 있습니다.",
    "acceptable_destination": "이동 목적지에 조사 に를 올바르게 사용했습니다.",
    "acceptable_embedded_plain": "〜と思います 앞의 보통형 접속이 올바릅니다.",
    "acceptable_filler": "문두의 자연스러운 필러는 문법 오류가 아니므로 유지합니다.",
    "acceptable_i_modifier": "い형용사가 명사를 직접 수식하는 형태가 올바릅니다.",
    "acceptable_i_past_negative": "い형용사의 과거 부정형 〜くなかった가 올바릅니다.",
    "acceptable_lexical_compound": "有名店은 하나의 합성명사로 사용할 수 있어 な를 넣지 않아도 됩니다.",
    "acceptable_na_modifier": "な형용사가 〜な 형태로 명사를 올바르게 수식합니다.",
    "acceptable_possession": "명사 사이의 소유·소속 관계에 조사 の를 올바르게 사용했습니다.",
    "acceptable_route": "이동하거나 통과하는 경로에 조사 を를 올바르게 사용했습니다.",
    "acceptable_short_answer": "질문 문맥에서 의미가 완결된 짧은 대답이므로 허용합니다.",
    "acceptable_style_switch": "주어진 회화 문맥에서는 정중체와 보통체의 전환을 문법 오류로 보지 않습니다.",
    "acceptable_te_request": "동사의 て형과 〜てください의 연결이 올바릅니다.",
    "adjective_connection": "い형용사의 연결형은 어미 い를 くて로 바꿉니다.",
    "adjective_negative": "い형용사의 부정형은 어미 い를 くない로 바꿉니다.",
    "adjective_past": "い형용사의 과거형은 어미 い를 かった로 바꿉니다.",
    "compound_adjective_tense": "い형용사 활용과 시간 표현에 맞는 서술어 시제를 각각 고칩니다.",
    "compound_modifier_location": "형용사의 명사 수식 형태와 존재 장소의 조사 に를 각각 고칩니다.",
    "compound_particle_verb": "동작 장소의 조사 で와 동사의 과거 정중형을 각각 고칩니다.",
    "copula_i_adjective": "い형용사의 정중 종결에는 だ를 덧붙이지 않습니다.",
    "copula_na_adjective": "な형용사의 정중 종결에서는 어간에 です를 붙입니다.",
    "copula_preference": "好き의 정중 종결은 だです가 아니라 好きです입니다.",
    "insufficient_filler_only": "필러만으로는 판단할 문장 내용이 없어 교정하지 않습니다.",
    "insufficient_missing_audio": "들리지 않은 부분을 텍스트만으로 확정할 수 없어 교정하지 않습니다.",
    "insufficient_out_of_scope": "일본어가 아닌 발화는 문법 교정 대신 번역 범위로 분리합니다.",
    "insufficient_silence": "실제 발화 내용이 없어 문법을 판단할 수 없습니다.",
    "insufficient_truncated": "문장이 끝나지 않아 누락된 내용을 추측하여 교정하지 않습니다.",
    "modifier_i_extra_na": "い형용사가 명사를 수식할 때는 な를 붙이지 않습니다.",
    "modifier_na_missing": "な형용사가 명사를 수식할 때는 어간 뒤에 な를 붙입니다.",
    "modifier_noun_link": "명사와 명사의 소유·소속 관계는 조사 の로 연결합니다.",
    "particle_action_location": "동작이 일어나는 장소에는 조사 で를 사용합니다.",
    "particle_destination": "이동 목적지에는 조사 に 또는 へ를 사용합니다.",
    "particle_existence": "사물의 존재 장소에는 조사 に를 사용합니다.",
    "particle_existence_lexical_compound": "합성명사 有名店은 유지하고 존재 장소의 조사 で만 に로 고칩니다.",
    "tense_contextual": "명시된 미래 시간과 맞도록 서술어를 비과거형으로 고칩니다.",
    "tense_future_past": "미래 시간 표현과 맞도록 과거형 서술어를 비과거형으로 고칩니다.",
    "tense_past_present": "과거 시간 표현과 맞도록 비과거형 서술어를 과거형으로 고칩니다.",
    "verb_polite_nonpast": "5단 동사의 어미를 い단으로 바꾸어 ます에 연결합니다.",
    "verb_polite_past": "5단 동사의 어미를 い단으로 바꾸어 ました에 연결합니다.",
    "verb_te_form": "동사의 활용 규칙에 맞는 て형으로 고칩니다.",
}


def _canonical(value) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _display_path(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def controlled_expected(record: dict) -> dict:
    expected = deepcopy(record["expected"])
    expected["reason_ko"] = REASONS_BY_FAMILY[record["template_family_id"]]
    return expected


def validate_control(records: list[dict]) -> dict:
    validate_records(records, require_reviewed=True)
    families = {row["template_family_id"] for row in records}
    configured = set(REASONS_BY_FAMILY)
    if families != configured:
        raise ValueError(
            f"Reason family mismatch; missing={sorted(families - configured)}, "
            f"extra={sorted(configured - families)}"
        )

    changed = 0
    for row in records:
        original = row["expected"]
        controlled = controlled_expected(row)
        for key in ("decision", "corrected_text", "edits"):
            if controlled[key] != original[key]:
                raise ValueError(f"Gold field changed for {row['id']}: {key}")
        if not controlled["reason_ko"].strip():
            raise ValueError(f"Blank controlled reason for {row['id']}")
        changed += controlled["reason_ko"] != original["reason_ko"]

    return {
        "total": len(records),
        "changed_reason_count": changed,
        "unchanged_gold_fields": ["decision", "corrected_text", "edits"],
        "review_statuses": sorted({row["review"]["status"] for row in records}),
        "families": len(families),
        "decisions": dict(sorted(Counter(
            row["expected"]["decision"] for row in records
        ).items())),
    }


def build(source: Path, output_dir: Path, manifest_path: Path) -> dict:
    records = load_records(source)
    validation = validate_control(records)
    output_dir.mkdir(parents=True, exist_ok=True)

    outputs = {}
    for split in sorted({row["split"] for row in records}):
        output = output_dir / f"{split}.chatml.jsonl"
        with output.open("w", encoding="utf-8", newline="\n") as stream:
            for row in records:
                if row["split"] != split:
                    continue
                sample = {
                    "messages": [
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": _canonical(row["input"])},
                        {"role": "assistant", "content": _canonical(controlled_expected(row))},
                    ]
                }
                stream.write(json.dumps(sample, ensure_ascii=False, separators=(",", ":")) + "\n")
        outputs[split] = {
            "path": _display_path(output),
            "count": sum(row["split"] == split for row in records),
            "sha256": _sha256(output),
        }

    manifest = {
        "experiment_view": "judgment-reason-control-v0.2-a",
        "control_version": CONTROL_VERSION,
        "created_at": datetime.now(timezone.utc).date().isoformat(),
        "source_dataset": _display_path(source),
        "source_dataset_sha256": _sha256(source),
        "policy": {
            "canonical_source_modified": False,
            "human_review_reason_used_for_training": False,
            "model_generated_gold_used": False,
            "expert_review_claimed": False,
        },
        "validation": validation,
        "reason_by_family": dict(sorted(REASONS_BY_FAMILY.items())),
        "outputs": outputs,
    }
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    args = parser.parse_args()
    manifest = build(args.source, args.output_dir, args.manifest)
    print(json.dumps(manifest, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
