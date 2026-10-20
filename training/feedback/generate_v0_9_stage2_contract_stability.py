"""Add Stage-1 abstention boundaries and Stage-2 recovery/style examples to feedback v0.7."""

from __future__ import annotations

from collections import Counter
import hashlib
import json
from pathlib import Path

from analyzer.feedback_contract import canonical_json, validate_input
from analyzer.feedback_two_stage_contract import parse_stage1_output, parse_stage2_output
from evaluation.feedback.build_holdout_v0_2 import input_fingerprint, judgment
from evaluation.feedback.build_holdout_v0_7 import stage1
from training.feedback.generate_v0_6_two_stage import to_chat

ROOT = Path(__file__).resolve().parents[2]
DATA = Path(__file__).resolve().parent / "data"
BASE = DATA / "feedback_v0.8.stage2-recovery-style.jsonl"
OUTPUT = DATA / "feedback_v0.9.stage2-contract-stability.jsonl"
TRAIN = DATA / "train_v0.9.stage2-contract-stability.chatml.jsonl"
EVAL = DATA / "eval_v0.9.stage2-contract-stability.chatml.jsonl"
MANIFEST = DATA / "feedback_v0.9.stage2-contract-stability.manifest.json"

PLACES = ["標準化室", "調達室", "検証室", "編集室", "包装室", "細胞培養室", "発送室", "冷却室", "加工室", "相談室", "比較室", "備蓄室", "試験室", "上映室", "切削室", "訓練室", "製本室", "加熱室", "改修室", "承認室"]
OBJECTS = ["標準票", "調達表", "検証記録", "編集原稿", "包装見本", "細胞培養記録", "発送票", "冷却試料", "加工図", "相談票", "比較表", "備蓄台帳", "試験値", "上映素材", "切削部品", "訓練日誌", "製本資料", "加熱試料", "改修図", "承認書"]
DESTINATIONS = ["標準化棟", "調達センター", "検証拠点", "編集施設", "包装工場", "培養施設", "発送所", "冷却センター", "加工研究所", "相談会場", "比較窓口", "備蓄拠点", "試験所", "上映施設", "切削工場", "訓練所", "製本センター", "加熱施設", "改修現場", "承認会場"]


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
        group_id = f"SR-{group + 1:02d}"

        valid_abstained = f"明後日の午後、{place}で{obj}を確認します。"
        abstain_candidate = judgment("insufficient_evidence", valid_abstained, [], "정보가 부족합니다.")
        valid_audit = stage1("disagree", ["wrong_decision", "unnecessary_abstention"], "완결된 문장을 불필요하게 보류했습니다.")

        incomplete = f"明後日の午後、{place}で{obj}を"
        incomplete_candidate = judgment("insufficient_evidence", incomplete, [], "서술어가 없어 판단 근거가 부족합니다.")
        incomplete_audit = stage1("agree", [], "미완성 입력을 보류한 판단이 타당합니다.")

        recovery_source = f"本日の午前は{place}で{obj}を確認します。"
        recovery_candidate = judgment("needs_correction", f"明日は{destination}で別の資料を確認します。", ["particle_misuse"], "더 자연스럽게 고쳤습니다.")
        recovery_audit = stage1("disagree", ["false_positive", "nonminimal_correction", "meaning_changed"], "정상 원문의 의미를 불필요하게 바꿨습니다.")
        recovery_expected = judgment("acceptable", recovery_source, [], "원문은 문법적으로 허용됩니다.")

        recovery_source_2 = f"夕方は{place}で{obj}を整理します。"
        recovery_candidate_2 = judgment("needs_correction", f"翌朝は{destination}で別の物を調べます。", ["verb_conjugation"], "문장을 자연스럽게 바꿨습니다.")
        recovery_audit_2 = stage1("disagree", ["false_positive", "nonminimal_correction", "meaning_changed"], "정상 원문의 시간·장소·대상을 바꿨습니다.")
        recovery_expected_2 = judgment("acceptable", recovery_source_2, [], "원문을 그대로 유지합니다.")

        formal_source = f"一昨日、{place}で{obj}を整理するました。"
        formal_candidate = judgment("needs_correction", f"一昨日、{place}で{obj}を整理してました。", ["verb_conjugation"], "활용을 교정했습니다.")
        formal_audit = stage1("disagree", ["wrong_correction"], "교정문이 목표 정중 과거형과 다릅니다.")
        formal_expected = judgment("needs_correction", f"一昨日、{place}で{obj}を整理しました。", ["verb_conjugation"], "입력 문체를 유지해 정중 과거형으로 최소 교정합니다.")

        formal_source_2 = f"先々週、{place}で{obj}を点検するました。"
        formal_candidate_2 = judgment("needs_correction", f"先々週、{place}で{obj}を点検してました。", ["verb_conjugation"], "활용을 고쳤습니다.")
        formal_audit_2 = stage1("disagree", ["wrong_correction"], "구어 축약이 아니라 입력의 정중체를 유지해야 합니다.")
        formal_expected_2 = judgment("needs_correction", f"先々週、{place}で{obj}を点検しました。", ["verb_conjugation"], "정중 과거형만 최소 교정합니다.")

        location_source = f"昨日、{place}で{obj}を確認するました。"
        changed = DESTINATIONS[(group + 9) % len(DESTINATIONS)]
        location_candidate = judgment("needs_correction", f"昨日、{changed}で{obj}を確認しました。", ["verb_conjugation"], "자연스럽게 교정했습니다.")
        location_audit = stage1("disagree", ["nonminimal_correction", "meaning_changed"], "활용 외에 장소 의미까지 변경했습니다.")
        location_expected = judgment("needs_correction", f"昨日、{place}で{obj}を確認しました。", ["verb_conjugation"], "장소와 문체를 보존하고 활용만 교정합니다.")


        incomplete_source = f"明日の午後、{place}で{obj}を……"
        incomplete_candidate = judgment("acceptable", incomplete_source, [], "문법적으로 허용됩니다.")
        incomplete_audit = stage1("disagree", ["should_abstain", "wrong_decision"], "미완성 발화를 확정 판단했습니다.")
        incomplete_expected = judgment("insufficient_evidence", incomplete_source, [], "서술어가 없어 판단을 보류합니다.")

        stage2_specs = [
            ("recover_acceptable_primary", recovery_source, recovery_candidate, recovery_audit, recovery_expected),
            ("recover_acceptable_control", recovery_source_2, recovery_candidate_2, recovery_audit_2, recovery_expected_2),
            ("formal_conjugation_primary", formal_source, formal_candidate, formal_audit, formal_expected),
            ("formal_conjugation_control", formal_source_2, formal_candidate_2, formal_audit_2, formal_expected_2),
            ("minimal_location_recovery", location_source, location_candidate, location_audit, location_expected),
            ("recover_insufficient_evidence", incomplete_source, incomplete_candidate, incomplete_audit, incomplete_expected),
        ]
        for case, text, candidate, audit, expected in stage2_specs:
            parsed, error = parse_stage2_output(canonical_json(expected), text, audit["issue_codes"])
            if parsed is None:
                raise ValueError(f"invalid stage2 gold {group_id}/{case}: {error}")
            rows.append({
                "id": f"FVT-09-{group_id}-{case}", "task": "feedback_stage2",
                "source_id": None, "pair_group": group_id, "case_type": case,
                "split_group": split, "model_input": make_input(text, candidate, level),
                "stage1_audit": audit, "expected": expected,
                "review": {"status": "generated_validated", "reviewed_at": None},
            })
    if len(rows) != 120 or len({row["id"] for row in rows}) != 120:
        raise ValueError(f"expected 120 unique targeted rows, got {len(rows)}")
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
        "holdout_v0.10": ROOT / "evaluation/feedback/holdout_v0.10.jsonl",
        "holdout_v0.11": ROOT / "evaluation/feedback/holdout_v0.11.jsonl",
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
        "schema_version": "feedback-training-manifest-v0.9-stage2-contract-stability",
        "records": len(rows), "base_records": len(base), "targeted_records": len(targeted),
        "train_records": len(splits["train"]), "eval_records": len(splits["eval"]),
        "task_counts": dict(sorted(Counter(row["task"] for row in rows).items())),
        "train_task_counts": dict(sorted(Counter(row["task"] for row in rows if row["split_group"] == "train").items())),
        "eval_task_counts": dict(sorted(Counter(row["task"] for row in rows if row["split_group"] == "eval").items())),
        "targeted_task_counts": dict(sorted(Counter(row["task"] for row in targeted).items())),
        "targeted_stage1_verdict_counts": dict(sorted(Counter(row["expected"]["verdict"] for row in targeted if row["task"] == "feedback_stage1").items())),
        "targeted_stage2_decision_counts": dict(sorted(Counter(row["expected"]["decision"] for row in targeted if row["task"] == "feedback_stage2").items())),
        "targeted_case_counts": dict(sorted(Counter(row["case_type"] for row in targeted).items())),
        "base_dataset": str(BASE.relative_to(ROOT)), "base_dataset_sha256": sha256(BASE),
        "review": {"status": "generated_validated", "reviewed_at": None},
        "holdout_used": False, "protected_overlap": overlap,
        "source_sha256": sha256(OUTPUT), "train_sha256": sha256(TRAIN), "eval_sha256": sha256(EVAL),
        "limitations": [
            "자동 생성·계약 검증 데이터이며 사람 또는 일본어 전문가 검수 데이터가 아닙니다.",
            "v0.8 전체를 유지하고 Stage 2 계약 안정성 예시 120건만 추가했습니다.",
            "봉인된 holdout v0.7~v0.11은 학습에 사용하지 않았습니다.",
        ],
    }
    MANIFEST.write_text(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
