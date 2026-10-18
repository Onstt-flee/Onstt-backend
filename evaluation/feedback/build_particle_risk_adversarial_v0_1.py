"""Build a deterministic development diagnostic for the particle-risk gate."""

from __future__ import annotations

from collections import Counter
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
OUTPUT = HERE / "particle_risk_adversarial_v0.1.jsonl"
MANIFEST = HERE / "particle_risk_adversarial_v0.1.manifest.json"
PROTOCOL = HERE / "particle_risk_adversarial_v0.1.protocol.json"


def canonical_json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build_rows() -> list[dict]:
    rows: list[tuple[str, str, list[str]]] = []

    places = ["休憩室", "倉庫", "玄関", "庭", "受付", "廊下", "屋上", "教室", "売店", "駅前"]
    things = ["給水器", "段ボール箱", "傘立て", "石のベンチ", "案内板", "消火器", "アンテナ", "時計", "雑誌", "公衆電話"]
    people = ["先生", "管理人", "警備員", "子ども", "受付係", "看護師", "作業員", "留学生", "店員", "案内人"]
    for place, thing in zip(places, things):
        rows.append((f"{place}で{thing}があります。", "inanimate_existence_error", ["existence_location_de_risk"]))
    for place, person in zip(places, people):
        rows.append((f"{place}で{person}がいます。", "animate_existence_error", ["existence_location_de_risk"]))

    destinations = ["病院", "図書館", "市役所", "空港", "美術館", "体育館", "研究室", "交番", "水族館", "展望台"]
    for place in destinations:
        rows.append((f"次の休みには{place}を行きます。", "destination_wo_error", ["destination_wo_iku_risk"]))

    known_events = ["イベント", "会議", "試験", "祭り", "コンサート", "セール", "授業", "公演", "大会", "説明会"]
    for event in known_events:
        rows.append((f"文化センターで{event}があります。", "known_occurrence_valid", []))

    unseen_events = ["講演", "発表会", "撮影会", "相談会", "面接", "健康診断", "避難訓練", "放送", "収録", "上映"]
    for event in unseen_events:
        rows.append((f"市民会館で{event}があります。", "unseen_occurrence_valid", []))

    routes = ["この道", "海沿いの道路", "中央通り", "旧街道", "長い廊下", "赤い橋", "単線の線路", "細い山道", "急な坂道", "人生"]
    for route in routes:
        rows.append((f"これから{route}を行きます。", "route_wo_valid", []))

    for place, thing in zip(places, things):
        rows.append((f"今も{place}に{thing}があります。", "existence_ni_valid", []))

    action_places = ["社員食堂", "図書館", "公園", "会議室", "体育館", "駅", "教室", "工房", "台所", "窓口"]
    actions = ["昼食を食べます", "本を読みます", "写真を撮ります", "相談します", "運動します", "友達を待ちます", "日本語を勉強します", "時計を直します", "料理を作ります", "申請します"]
    for place, action in zip(action_places, actions):
        rows.append((f"{place}で{action}。", "action_de_valid", []))

    result = []
    for index, (text, stratum, expected) in enumerate(rows, 1):
        result.append({
            "id": f"FPG-A-{index:03d}",
            "text": text,
            "stratum": stratum,
            "expected_signal_codes": expected,
            "source_kind": "deterministic_particle_risk_adversarial_v0.1",
            "review_status": "generated_validated",
        })
    if len(result) != 80 or len({row["text"] for row in result}) != 80:
        raise ValueError("particle-risk adversarial dataset must contain 80 unique texts")
    return result


def _prior_jsonl_paths() -> list[Path]:
    candidates = [
        *ROOT.glob("training/feedback/**/*.jsonl"),
        *ROOT.glob("evaluation/feedback/*.jsonl"),
    ]
    return sorted(path for path in set(candidates) if path != OUTPUT)


def _texts(path: Path) -> set[str]:
    return {
        row["text"]
        for line in path.read_text(encoding="utf-8").splitlines()
        if line and isinstance((row := json.loads(line)).get("text"), str)
    }


def main() -> int:
    rows = build_rows()
    texts = {row["text"] for row in rows}
    overlap = {
        str(path.relative_to(ROOT)): len(texts & _texts(path))
        for path in _prior_jsonl_paths()
    }
    if any(overlap.values()):
        raise ValueError("particle-risk adversarial dataset overlaps existing JSONL inputs")

    OUTPUT.write_text("".join(canonical_json(row) + "\n" for row in rows), encoding="utf-8")
    manifest = {
        "schema_version": "feedback-particle-risk-adversarial-manifest-v0.1",
        "records": len(rows),
        "sha256": sha256(OUTPUT),
        "review_status": "generated_validated",
        "human_reviewed": False,
        "expert_reviewed": False,
        "built_after_gate": True,
        "stratum_counts": dict(sorted(Counter(row["stratum"] for row in rows).items())),
        "expected_signal_rows": sum(bool(row["expected_signal_codes"]) for row in rows),
        "expected_no_signal_rows": sum(not row["expected_signal_codes"] for row in rows),
        "exact_text_overlap": overlap,
        "qualification_scope": "development_adversarial_not_holdout",
    }
    MANIFEST.write_text(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    protocol = {
        "schema_version": "feedback-particle-risk-adversarial-protocol-v0.1",
        "dataset_sha256": manifest["sha256"],
        "gate_version": "feedback-particle-risk-v0.1",
        "purpose": "development_adversarial_not_holdout",
        "built_after_gate": True,
        "independent_model_selection_evidence": False,
        "thresholds": {
            "signal_recall_min": 0.95,
            "signal_precision_min": 0.95,
            "false_signal_rate_max": 0.05,
        },
        "limitations": [
            "관문 구현 후 설계한 개발 진단셋이므로 홀드아웃이나 운영 승인 근거가 아닙니다.",
            "자동 생성·검증 자료이며 사람 또는 일본어 전문가 검수 자료가 아닙니다.",
            "표면 패턴 신호만 평가하며 문법 교정 정확도를 평가하지 않습니다.",
        ],
    }
    PROTOCOL.write_text(json.dumps(protocol, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
