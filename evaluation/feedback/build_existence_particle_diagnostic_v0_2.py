"""Build the unseen v0.2 diagnostic for the hardened feedback prompt."""

from __future__ import annotations

from collections import Counter
import hashlib
import json
from pathlib import Path

from analyzer.feedback_contract import canonical_json, parse_output, validate_input
from evaluation.feedback.build_holdout_v0_2 import input_fingerprint, judgment
from evaluation.feedback.build_existence_particle_diagnostic_v0_1 import feedback


ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
OUTPUT = HERE / "existence_particle_diagnostic_v0.2.jsonl"
MANIFEST = HERE / "existence_particle_diagnostic_v0.2.manifest.json"
PROTOCOL = HERE / "existence_particle_diagnostic_v0.2.protocol.json"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build_rows() -> list[dict]:
    rows = []
    places = ["休憩所", "展示棚の前", "非常口のそば", "廊下の突き当たり", "庭の東側", "事務所の入口", "舞台の裏", "駐車場の端", "改札の内側", "机の下"]
    things = ["給水器", "説明書", "避難経路図", "鏡", "石のベンチ", "受付台", "予備の幕", "充電器", "精算機", "小さな箱"]
    acceptable_reasons = [
        "문법적으로 허용됩니다.", "조사 사용이 자연스럽습니다.", "문법상 수정할 부분이 없습니다.",
        "원문을 그대로 사용할 수 있습니다.", "현재 문장은 문법적으로 맞습니다.",
    ]
    for index, (place, thing) in enumerate(zip(places, things)):
        text = f"{place}で{thing}があります。"
        corrected = f"{place}に{thing}があります。"
        recommended = judgment("needs_correction", corrected, ["particle_misuse"], "존재 장소에는 조사 に가 필요합니다.")
        rows.append((text, "existence_de_false_negative", judgment("acceptable", text, [], acceptable_reasons[index % len(acceptable_reasons)]),
                     feedback("disagree", ["false_negative"], recommended, "존재 장소 조사 오류를 놓쳤습니다.")))

    for index, (place, thing) in enumerate(zip(places, things)):
        text = f"{place}に{thing}があります。"
        rows.append((text, "existence_ni_agree", judgment("acceptable", text, [], acceptable_reasons[index % len(acceptable_reasons)]),
                     feedback("agree", [], None, "존재 장소 조사 に를 올바르게 인정했습니다.")))

    action_places = ["研修室", "調理場", "受付前", "広場", "音楽室", "診察室", "印刷室", "屋外ステージ", "相談窓口", "運動場"]
    actions = ["講義を聞きます", "野菜を切ります", "順番を待ちます", "祭りを開きます", "歌を練習します", "医師と話します", "資料をコピーします", "演奏を聞きます", "質問をします", "準備運動をします"]
    for index, (place, action) in enumerate(zip(action_places, actions)):
        text = f"{place}で{action}。"
        rows.append((text, "action_de_agree", judgment("acceptable", text, [], acceptable_reasons[index % len(acceptable_reasons)]),
                     feedback("agree", [], None, "동작 장소 조사 で를 올바르게 인정했습니다.")))

    destinations = ["検査室", "天文台", "案内所", "記念館", "武道館", "実験棟", "船着き場", "植物園", "文化会館", "購買部"]
    for index, place in enumerate(destinations):
        text = f"夕方は{place}を行きます。"
        corrected = f"夕方は{place}に行きます。"
        recommended = judgment("needs_correction", corrected, ["particle_misuse"], "목적지에는 조사 に가 필요합니다.")
        rows.append((text, "destination_wo_false_negative", judgment("acceptable", text, [], acceptable_reasons[index % len(acceptable_reasons)]),
                     feedback("disagree", ["false_negative"], recommended, "목적지 조사 오류를 놓쳤습니다.")))

    result = []
    for index, (text, family, candidate, expected) in enumerate(rows, 1):
        row = {
            "id": f"FVD-EP-02-{index:03d}", "text": text, "context": None,
            "learner_level": "N4" if index % 4 == 0 else "N5",
            "candidate_judgment": candidate, "expected": expected, "family": family,
            "source_kind": "deterministic_existence_particle_diagnostic_v0.2",
            "review_status": "generated_validated",
        }
        validate_input({"text": text, "context": None, "learner_level": row["learner_level"], "judgment": candidate})
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
    prior_paths = [
        ROOT / "training/feedback/data/feedback_v0.1.jsonl",
        ROOT / "training/feedback/data/feedback_v0.2.jsonl",
        ROOT / "training/feedback/data/feedback_v0.3.jsonl",
        *(HERE / f"holdout_v0.{version}.jsonl" for version in range(1, 5)),
        HERE / "existence_particle_diagnostic_v0.1.jsonl",
    ]
    fingerprints = {input_fingerprint(row) for row in rows}
    texts = {row["text"] for row in rows}
    overlap = {}
    for path in prior_paths:
        prior = _load(path)
        overlap[str(path.relative_to(ROOT))] = {
            "exact_input": len(fingerprints & {input_fingerprint(row) for row in prior}),
            "text": len(texts & {row["text"] for row in prior}),
        }
    if any(item["exact_input"] or item["text"] for item in overlap.values()):
        raise ValueError("v0.2 diagnostic overlaps prior data")
    OUTPUT.write_text("".join(canonical_json(row) + "\n" for row in rows), encoding="utf-8")
    manifest = {
        "schema_version": "feedback-existence-particle-diagnostic-manifest-v0.2",
        "records": len(rows), "sha256": sha256(OUTPUT), "review_status": "generated_validated",
        "human_reviewed": False, "expert_reviewed": False,
        "family_counts": dict(sorted(Counter(row["family"] for row in rows).items())),
        "verdict_counts": dict(sorted(Counter(row["expected"]["verdict"] for row in rows).items())),
        "overlap": overlap, "qualification_scope": "hardened_prompt_regression_diagnostic_only",
    }
    MANIFEST.write_text(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    protocol = {
        "schema_version": "feedback-existence-particle-diagnostic-protocol-v0.2",
        "dataset_sha256": manifest["sha256"], "candidate_family": "feedback-v0.3-hardened-prompt",
        "ready_for_inference": True, "single_use": True, "consumed": False,
        "temperature": 0.0, "top_p": 1.0, "max_tokens": 512,
        "purpose": "hardened_prompt_regression_diagnostic_only",
    }
    PROTOCOL.write_text(json.dumps(protocol, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
