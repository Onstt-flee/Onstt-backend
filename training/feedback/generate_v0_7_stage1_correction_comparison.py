"""Add paired Stage-1 correction-comparison examples to feedback v0.6."""

from __future__ import annotations

from collections import Counter
import hashlib
import json
from pathlib import Path

from analyzer.feedback_contract import canonical_json, validate_input
from analyzer.feedback_two_stage_contract import parse_stage1_output
from evaluation.feedback.build_holdout_v0_2 import input_fingerprint, judgment
from evaluation.feedback.build_holdout_v0_7 import stage1
from training.feedback.generate_v0_6_two_stage import to_chat

ROOT = Path(__file__).resolve().parents[2]
DATA = Path(__file__).resolve().parent / "data"
BASE = DATA / "feedback_v0.6.two-stage.jsonl"
OUTPUT = DATA / "feedback_v0.7.stage1-comparison.jsonl"
TRAIN = DATA / "train_v0.7.stage1-comparison.chatml.jsonl"
EVAL = DATA / "eval_v0.7.stage1-comparison.chatml.jsonl"
MANIFEST = DATA / "feedback_v0.7.stage1-comparison.manifest.json"

PLACES = ["校正室", "撮影室", "編集室", "試験室", "洗浄室", "測定室", "加工室", "発送室", "展示室", "管理室", "資料室", "閲覧室", "実験室", "整備室", "準備室", "会議室", "練習室", "調理室", "包装室", "修理室"]
OBJECTS = ["原稿", "写真", "映像", "試作品", "器具", "寸法", "材料", "荷物", "作品", "台帳", "文献", "雑誌", "試薬", "車両", "備品", "議事録", "台本", "食材", "商品", "部品"]
DESTINATIONS = ["出版社", "撮影所", "編集部", "試験会場", "洗浄施設", "計測センター", "加工工場", "配送拠点", "美術館", "管理棟", "図書館", "閲覧館", "研究所", "整備工場", "準備会場", "本社会議室", "稽古場", "調理学校", "包装工場", "修理工房"]


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def make_input(text: str, candidate: dict, level: str) -> dict:
    value = {"text": text, "context": None, "learner_level": level, "judgment": candidate}
    validate_input(value)
    return value


def build_targeted() -> list[dict]:
    rows = []
    for group, (place, obj, destination) in enumerate(zip(PLACES, OBJECTS, DESTINATIONS)):
        split = "eval" if group % 10 == 0 else "train"
        level = "N4" if group % 3 == 0 else "N5"
        group_id = f"CC-{group + 1:02d}"
        specs = []

        particle_source = f"翌週は{destination}を行きます。"
        specs.extend([
            ("particle_correct_agree", particle_source, judgment("needs_correction", f"翌週は{destination}に行きます。", ["particle_misuse"], "목적지 조사만 최소 교정했습니다."), stage1("agree", [], "교정문이 조사 오류를 정확히 해결했습니다.")),
            ("particle_wrong_disagree", particle_source, judgment("needs_correction", f"翌週は{destination}で行きます。", ["particle_misuse"], "목적지 조사를 교정했습니다."), stage1("disagree", ["wrong_correction"], "교정문이 목적지 조사 오류를 해결하지 못했습니다.")),
        ])

        conjugation_source = f"先月、{place}で{obj}を確認するました。"
        specs.extend([
            ("conjugation_correct_agree", conjugation_source, judgment("needs_correction", f"先月、{place}で{obj}を確認しました。", ["verb_conjugation"], "정중 과거형만 최소 교정했습니다."), stage1("agree", [], "교정문이 활용 오류를 정확히 해결했습니다.")),
            ("conjugation_wrong_disagree", conjugation_source, judgment("needs_correction", f"先月、{place}で{obj}を確認してました。", ["verb_conjugation"], "활용을 교정했습니다."), stage1("disagree", ["wrong_correction"], "교정문이 목표 정중 과거형과 다릅니다.")),
        ])

        minimal_source = f"昨日、{place}で{obj}を整理するました。"
        changed_destination = DESTINATIONS[(group + 7) % len(DESTINATIONS)]
        specs.extend([
            ("minimal_correct_agree", minimal_source, judgment("needs_correction", f"昨日、{place}で{obj}を整理しました。", ["verb_conjugation"], "활용만 최소 교정했습니다."), stage1("agree", [], "원문의 의미를 보존한 최소 교정입니다.")),
            ("nonminimal_location_disagree", minimal_source, judgment("needs_correction", f"昨日、{changed_destination}で{obj}を整理しました。", ["verb_conjugation"], "자연스럽게 교정했습니다."), stage1("disagree", ["nonminimal_correction", "meaning_changed"], "활용 외에 장소 의미까지 바꿨습니다.")),
        ])

        valid_source = f"本日の午後は{place}で{obj}を確認します。"
        specs.extend([
            ("valid_unchanged_agree", valid_source, judgment("acceptable", valid_source, [], "문법적으로 자연스러워 원문을 유지합니다."), stage1("agree", [], "허용 판단과 원문 보존이 타당합니다.")),
            ("valid_meaning_change_disagree", valid_source, judgment("needs_correction", f"明日の午前は{destination}で別の資料を確認します。", ["particle_misuse"], "더 자연스럽게 고쳤습니다."), stage1("disagree", ["false_positive", "nonminimal_correction", "meaning_changed"], "정상 원문의 시간·장소·대상을 불필요하게 바꿨습니다.")),
        ])

        for case, text, candidate, expected in specs:
            parsed, error = parse_stage1_output(canonical_json(expected))
            if parsed is None:
                raise ValueError(f"invalid stage1 gold {group_id}/{case}: {error}")
            rows.append({
                "id": f"FVT-07-{group_id}-{case}", "task": "feedback_stage1",
                "source_id": None, "pair_group": group_id, "case_type": case,
                "split_group": split, "model_input": make_input(text, candidate, level),
                "stage1_audit": None, "expected": expected,
                "review": {"status": "generated_validated", "reviewed_at": None},
            })
    if len(rows) != 160 or len({row["id"] for row in rows}) != 160:
        raise ValueError(f"expected 160 unique targeted rows, got {len(rows)}")
    return rows


def visible_fingerprint(row: dict) -> str:
    value = row["model_input"]
    return input_fingerprint({
        "text": value["text"], "context": value["context"],
        "learner_level": value["learner_level"],
        "candidate_judgment": value["judgment"],
    })


def main() -> int:
    base = load(BASE)
    targeted = build_targeted()
    rows = base + targeted
    protected = {
        "holdout_v0.7": ROOT / "evaluation/feedback/holdout_v0.7.jsonl",
        "holdout_v0.8": ROOT / "evaluation/feedback/holdout_v0.8.jsonl",
        "holdout_v0.9": ROOT / "evaluation/feedback/holdout_v0.9.jsonl",
    }
    current_inputs = {visible_fingerprint(row) for row in rows}
    current_texts = {row["model_input"]["text"] for row in rows}
    overlap = {}
    for name, path in protected.items():
        protected_rows = load(path)
        protected_inputs = {input_fingerprint(row) for row in protected_rows}
        protected_texts = {row["text"] for row in protected_rows}
        overlap[name] = {"exact_input": len(current_inputs & protected_inputs), "text": len(current_texts & protected_texts)}
    if any(value["exact_input"] or value["text"] for value in overlap.values()):
        raise ValueError(f"protected holdout overlap: {overlap}")

    OUTPUT.write_text("".join(canonical_json(row) + "\n" for row in rows), encoding="utf-8")
    splits = {"train": [], "eval": []}
    for row in rows:
        splits[row["split_group"]].append(to_chat(row))
    TRAIN.write_text("".join(canonical_json(row) + "\n" for row in splits["train"]), encoding="utf-8")
    EVAL.write_text("".join(canonical_json(row) + "\n" for row in splits["eval"]), encoding="utf-8")
    manifest = {
        "schema_version": "feedback-training-manifest-v0.7-stage1-comparison",
        "records": len(rows), "base_records": len(base), "targeted_records": len(targeted),
        "train_records": len(splits["train"]), "eval_records": len(splits["eval"]),
        "task_counts": dict(sorted(Counter(row["task"] for row in rows).items())),
        "train_task_counts": dict(sorted(Counter(row["task"] for row in rows if row["split_group"] == "train").items())),
        "eval_task_counts": dict(sorted(Counter(row["task"] for row in rows if row["split_group"] == "eval").items())),
        "targeted_verdict_counts": dict(sorted(Counter(row["expected"]["verdict"] for row in targeted).items())),
        "targeted_case_counts": dict(sorted(Counter(row["case_type"] for row in targeted).items())),
        "base_dataset": str(BASE.relative_to(ROOT)), "base_dataset_sha256": sha256(BASE),
        "review": {"status": "generated_validated", "reviewed_at": None},
        "holdout_used": False, "protected_overlap": overlap,
        "source_sha256": sha256(OUTPUT), "train_sha256": sha256(TRAIN), "eval_sha256": sha256(EVAL),
        "limitations": [
            "자동 생성·계약 검증 데이터이며 사람 또는 일본어 전문가 검수 데이터가 아닙니다.",
            "v0.6 정답을 유지하고 Stage 1 교정문 비교 최소대립쌍 160건만 추가했습니다.",
            "봉인된 holdout v0.7, v0.8, v0.9는 학습에 사용하지 않았습니다.",
        ],
    }
    MANIFEST.write_text(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
