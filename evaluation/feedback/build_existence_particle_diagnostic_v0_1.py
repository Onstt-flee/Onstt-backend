"""Build a generated-only diagnostic for Japanese location-particle boundaries."""

from __future__ import annotations

from collections import Counter
import hashlib
import json
from pathlib import Path

from analyzer.feedback_contract import canonical_json, parse_output, validate_input
from evaluation.feedback.build_holdout_v0_2 import input_fingerprint, judgment


ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
OUTPUT = HERE / "existence_particle_diagnostic_v0.1.jsonl"
MANIFEST = HERE / "existence_particle_diagnostic_v0.1.manifest.json"
PROTOCOL = HERE / "existence_particle_diagnostic_v0.1.protocol.json"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def feedback(verdict, issues, recommended, reason):
    return {
        "verdict": verdict,
        "issue_codes": issues,
        "recommended_judgment": recommended,
        "review_reason_ko": reason,
    }


def build_rows() -> list[dict]:
    rows = []
    existence_places = ["券売所", "控室", "門の横", "階段の下", "屋根裏", "受付の奥", "倉庫の隅", "広場の中央", "校舎の裏", "窓際"]
    existence_things = ["案内図", "予備の椅子", "郵便受け", "消火器", "古い箱", "保管棚", "台車", "噴水", "自動販売機", "植木鉢"]
    for place, thing in zip(existence_places, existence_things):
        text = f"{place}で{thing}があります。"
        corrected = f"{place}に{thing}があります。"
        recommended = judgment("needs_correction", corrected, ["particle_misuse"], "존재 장소에는 조사 に가 필요합니다.")
        rows.append((text, None, "existence_de_false_negative", judgment("acceptable", text, [], "문법적으로 허용됩니다."),
                     feedback("disagree", ["false_negative"], recommended, "존재 장소 조사 오류를 놓쳤습니다.")))

    for place, thing in zip(existence_places, existence_things):
        text = f"{place}に{thing}があります。"
        rows.append((text, None, "existence_ni_agree", judgment("acceptable", text, [], "문법적으로 허용됩니다."),
                     feedback("agree", [], None, "존재 장소 조사 に를 올바르게 인정했습니다.")))

    action_places = ["工房", "体育館", "講義室", "食堂", "窓口", "中庭", "会議室", "駅前", "図書室", "作業場"]
    actions = ["模型を作ります", "体操をします", "説明を聞きます", "昼食を食べます", "申込書を書きます", "写真を撮ります", "資料を読みます", "友達を待ちます", "宿題をします", "荷物を整理します"]
    for place, action in zip(action_places, actions):
        text = f"{place}で{action}。"
        rows.append((text, None, "action_de_agree", judgment("acceptable", text, [], "문법적으로 허용됩니다."),
                     feedback("agree", [], None, "동작 장소 조사 で를 올바르게 인정했습니다.")))

    destinations = ["診察室", "展望台", "交番", "資料館", "体育館", "研究棟", "港", "温室", "公会堂", "売店"]
    for place in destinations:
        text = f"午後は{place}を行きます。"
        corrected = f"午後は{place}に行きます。"
        recommended = judgment("needs_correction", corrected, ["particle_misuse"], "목적지에는 조사 に가 필요합니다.")
        rows.append((text, None, "destination_wo_false_negative", judgment("acceptable", text, [], "문법적으로 허용됩니다."),
                     feedback("disagree", ["false_negative"], recommended, "목적지 조사 오류를 놓쳤습니다.")))

    result = []
    for index, (text, context, family, candidate, expected) in enumerate(rows, 1):
        row = {
            "id": f"FVD-EP-01-{index:03d}",
            "text": text,
            "context": context,
            "learner_level": "N4" if index % 4 == 0 else "N5",
            "candidate_judgment": candidate,
            "expected": expected,
            "family": family,
            "source_kind": "deterministic_existence_particle_diagnostic_v0.1",
            "review_status": "generated_validated",
        }
        validate_input({"text": text, "context": context, "learner_level": row["learner_level"], "judgment": candidate})
        parsed, error = parse_output(canonical_json(expected), text)
        if parsed is None:
            raise ValueError(f"invalid expected output for {row['id']}: {error}")
        result.append(row)
    return result


def _load(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def main() -> None:
    if PROTOCOL.exists() and json.loads(PROTOCOL.read_text(encoding="utf-8")).get("consumed"):
        raise SystemExit("refusing to regenerate consumed diagnostic")
    rows = build_rows()
    paths = [
        ROOT / "training/feedback/data/feedback_v0.1.jsonl",
        ROOT / "training/feedback/data/feedback_v0.2.jsonl",
        ROOT / "training/feedback/data/feedback_v0.3.jsonl",
        *(HERE / f"holdout_v0.{version}.jsonl" for version in range(1, 5)),
    ]
    fingerprints = {input_fingerprint(row) for row in rows}
    texts = {row["text"] for row in rows}
    overlaps = {}
    for path in paths:
        prior = _load(path)
        overlaps[str(path.relative_to(ROOT))] = {
            "exact_input": len(fingerprints & {input_fingerprint(row) for row in prior}),
            "text": len(texts & {row["text"] for row in prior}),
        }
    if any(value["exact_input"] or value["text"] for value in overlaps.values()):
        raise ValueError("diagnostic overlaps existing feedback data")
    OUTPUT.write_text("".join(canonical_json(row) + "\n" for row in rows), encoding="utf-8")
    manifest = {
        "schema_version": "feedback-existence-particle-diagnostic-manifest-v0.1",
        "records": len(rows),
        "sha256": sha256(OUTPUT),
        "review_status": "generated_validated",
        "human_reviewed": False,
        "expert_reviewed": False,
        "family_counts": dict(sorted(Counter(row["family"] for row in rows).items())),
        "verdict_counts": dict(sorted(Counter(row["expected"]["verdict"] for row in rows).items())),
        "overlap": overlaps,
        "qualification_scope": "post_selection_regression_diagnostic_only",
    }
    MANIFEST.write_text(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    protocol = {
        "schema_version": "feedback-existence-particle-diagnostic-protocol-v0.1",
        "dataset_sha256": manifest["sha256"],
        "candidate_family": "feedback-v0.3",
        "ready_for_inference": True,
        "single_use": True,
        "consumed": False,
        "temperature": 0.0,
        "top_p": 1.0,
        "max_tokens": 512,
        "purpose": "post_selection_regression_diagnostic_only",
    }
    PROTOCOL.write_text(json.dumps(protocol, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
