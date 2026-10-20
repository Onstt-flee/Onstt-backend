"""Build and pre-seal feedback holdout v0.9 before v0.7 training."""

from __future__ import annotations

from collections import Counter
import hashlib
import json
from pathlib import Path

from analyzer.feedback_contract import canonical_json, validate_input
from evaluation.feedback.build_holdout_v0_2 import input_fingerprint, judgment
from evaluation.feedback.build_holdout_v0_7 import stage1

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
OUTPUT = HERE / "holdout_v0.9.jsonl"
MANIFEST = HERE / "holdout_v0.9.manifest.json"
PROTOCOL = HERE / "holdout_v0.9.protocol.json"

PLACES = ["新館製本室", "保管庫", "分析室", "録音室", "研磨室", "培養室", "印刷室", "冷却室", "組立室", "検査室"]
THINGS = ["大型製本機", "標本箱", "分析装置", "録音機", "研磨台", "培養器", "印刷機", "冷却槽", "組立台", "検査器"]
PEOPLE = ["製本担当", "保管担当", "分析員", "録音技師", "研磨担当", "培養担当", "印刷担当", "冷却担当", "組立担当", "検査員"]
ACTIONS = ["冊子を綴じます", "標本を保管します", "試料を分析します", "音声を録音します", "部品を磨きます", "細胞を培養します", "資料を印刷します", "材料を冷やします", "機器を組み立てます", "製品を検査します"]
DESTINATIONS = ["製本工房", "資料館", "研究棟", "収録施設", "加工工場", "培養施設", "印刷工房", "冷却施設", "組立工場", "検査センター"]
OBJECTS = ["冊子", "標本", "試料", "音声資料", "金属部品", "培養記録", "印刷見本", "冷却記録", "組立図", "検査票"]


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def visible_input(row: dict) -> dict | None:
    required = {"text", "context", "learner_level", "candidate_judgment"}
    if required <= set(row):
        return row
    value = row.get("model_input")
    return value if isinstance(value, dict) and required <= set(value) else None


def fingerprints(rows: list[dict]) -> set[str]:
    return {input_fingerprint(value) for row in rows if (value := visible_input(row)) is not None}


def texts(rows: list[dict]) -> set[str]:
    return {value["text"] for row in rows if (value := visible_input(row)) is not None}


def build_rows() -> list[dict]:
    specs = []
    for group, (place, thing, person, action, destination, obj) in enumerate(
        zip(PLACES, THINGS, PEOPLE, ACTIONS, DESTINATIONS, OBJECTS)
    ):
        action_ok = f"午前中は{place}で{action}。"
        specs.append((action_ok, None, "agree_valid_action", judgment("acceptable", action_ok, [], "동작 장소에 で를 올바르게 사용했습니다."), stage1("agree", [], "판단과 근거가 타당합니다."), None))

        existence_ok = f"現在、{place}に{thing}があります。"
        specs.append((existence_ok, None, "agree_valid_existence", judgment("acceptable", existence_ok, [], "존재 장소에 に를 올바르게 사용했습니다."), stage1("agree", [], "허용 판단이 타당합니다."), None))

        particle_error = f"来週は{destination}を行きます。"
        particle_fixed = f"来週は{destination}に行きます。"
        specs.append((particle_error, None, "agree_correct_particle", judgment("needs_correction", particle_fixed, ["particle_misuse"], "목적지 조사만 최소 교정했습니다."), stage1("agree", [], "조사 교정이 타당합니다."), None))

        conjugation_error = f"昨日、{person}が{obj}を確認するました。"
        conjugation_fixed = f"昨日、{person}が{obj}を確認しました。"
        specs.append((conjugation_error, None, "agree_correct_conjugation", judgment("needs_correction", conjugation_fixed, ["verb_conjugation"], "동사의 정중 과거형만 교정했습니다."), stage1("agree", [], "활용 교정이 타당합니다."), None))

        person_ok = f"夕方、{person}は{place}にいました。"
        specs.append((person_ok, None, "agree_valid_person", judgment("acceptable", person_ok, [], "사람의 존재 장소 표현이 자연스럽습니다."), stage1("agree", [], "판단과 근거가 타당합니다."), None))

        wrong_particle = f"次回は{destination}を行きます。"
        specs.append((wrong_particle, None, "disagree_wrong_correction_particle", judgment("needs_correction", f"次回は{destination}で行きます。", ["particle_misuse"], "목적지 조사를 교정했습니다."), stage1("disagree", ["wrong_correction"], "교정문이 목적지 조사 오류를 해결하지 못했습니다."), judgment("needs_correction", f"次回は{destination}に行きます。", ["particle_misuse"], "목적지에는 に를 사용합니다.")))

        wrong_conjugation = f"先週、{person}が{obj}を整理するました。"
        specs.append((wrong_conjugation, None, "disagree_wrong_correction_conjugation", judgment("needs_correction", f"先週、{person}が{obj}を整理してました。", ["verb_conjugation"], "활용을 교정했습니다."), stage1("disagree", ["wrong_correction"], "교정문이 목표 정중 과거형과 다릅니다."), judgment("needs_correction", f"先週、{person}が{obj}を整理しました。", ["verb_conjugation"], "정중 과거형으로 최소 교정합니다.")))

        nonminimal_source = f"昨日、{place}で{obj}を確認するました。"
        changed_place = DESTINATIONS[(group + 3) % len(DESTINATIONS)]
        specs.append((nonminimal_source, None, "disagree_nonminimal_meaning_location", judgment("needs_correction", f"昨日、{changed_place}で{obj}を確認しました。", ["verb_conjugation"], "자연스럽게 교정했습니다."), stage1("disagree", ["nonminimal_correction", "meaning_changed"], "활용 외에 장소 의미까지 변경했습니다."), judgment("needs_correction", f"昨日、{place}で{obj}を確認しました。", ["verb_conjugation"], "활용만 최소 교정합니다.")))

        nonminimal_valid = f"本日は{place}で{action}。"
        specs.append((nonminimal_valid, None, "disagree_nonminimal_meaning_addition", judgment("needs_correction", f"明日は{destination}で別の作業をします。", ["particle_misuse"], "더 자연스럽게 바꿨습니다."), stage1("disagree", ["false_positive", "nonminimal_correction", "meaning_changed"], "허용되는 원문의 시간·장소·내용을 불필요하게 바꿨습니다."), judgment("acceptable", nonminimal_valid, [], "원문은 문법적으로 허용됩니다.")))

        missed = f"現在、{place}で{thing}があります。"
        specs.append((missed, None, "disagree_false_negative_particle", judgment("acceptable", missed, [], "문법적으로 허용됩니다."), stage1("disagree", ["false_negative"], "존재 장소 조사 오류를 놓쳤습니다."), judgment("needs_correction", f"現在、{place}に{thing}があります。", ["particle_misuse"], "존재 장소에는 に를 사용합니다.")))

        boundary = f"明朝、{person}は{place}で{action}。"
        if group % 2 == 0:
            candidate = judgment("acceptable", boundary, [], "과거 시제 오류를 교정했습니다.")
            expected1 = stage1("disagree", ["reason_mismatch"], "판단과 근거가 일치하지 않습니다.")
            family = "disagree_reason_mismatch"
        else:
            candidate = judgment("insufficient_evidence", boundary, [], "정보가 부족합니다.")
            expected1 = stage1("disagree", ["wrong_decision", "unnecessary_abstention"], "완결된 문장을 불필요하게 보류했습니다.")
            family = "disagree_unnecessary_abstention"
        specs.append((boundary, None, family, candidate, expected1, judgment("acceptable", boundary, [], "문법적으로 완결된 문장입니다.")))

        orthography = f"わたしわ{destination}に行きます。" if group % 2 == 0 else f"{obj}お確認します。"
        corrected = orthography.replace("わ", "は", 1) if "わ" in orthography else orthography.replace("お", "を", 1)
        specs.append((orthography, "STT 전사이며 원음은 제공되지 않았습니다.", "unreviewable_audio_orthography", judgment("needs_correction", corrected, ["particle_misuse"], "조사 표기를 고쳤습니다."), stage1("unreviewable", [], "원음 없이 발화와 전사 오류를 구분할 수 없습니다."), None))

    rows = []
    for index, (text, context, family, candidate, expected1, expected2) in enumerate(specs, 1):
        row = {
            "id": f"FVH-09-{index:03d}", "text": text, "context": context,
            "learner_level": "N4" if index % 4 == 0 else "N5",
            "candidate_judgment": candidate, "expected_stage1": expected1,
            "expected_stage2": expected2, "family": family,
            "source_kind": "deterministic_feedback_two_stage_holdout_v0.9",
            "review_status": "generated_validated",
        }
        validate_input({"text": text, "context": context, "learner_level": row["learner_level"], "judgment": candidate})
        if (expected1["verdict"] == "disagree") != (expected2 is not None):
            raise ValueError(f"stage boundary mismatch: {row['id']}")
        rows.append(row)
    if len(rows) != 120 or len({row["text"] for row in rows}) != 120:
        raise ValueError("holdout v0.9 must contain 120 unique texts")
    return rows


def main() -> int:
    if PROTOCOL.exists():
        raise SystemExit("refusing to regenerate sealed feedback holdout v0.9")
    rows = build_rows()
    current_inputs, current_texts = fingerprints(rows), texts(rows)
    comparisons = {
        **{f"training_v0.{version}": ROOT / f"training/feedback/data/feedback_v0.{version}.jsonl" for version in (1, 2, 3, 4, 5)},
        "training_v0.6": ROOT / "training/feedback/data/feedback_v0.6.two-stage.jsonl",
        **{f"holdout_v0.{version}": HERE / f"holdout_v0.{version}.jsonl" for version in (1, 2, 3, 4, 5, 6, 7, 8)},
        **{f"diagnostic_v0.{version}": HERE / f"existence_particle_diagnostic_v0.{version}.jsonl" for version in (1, 2)},
        "particle_adversarial_v0.1": HERE / "particle_risk_adversarial_v0.1.jsonl",
    }
    overlap = {}
    for name, path in comparisons.items():
        values = load(path)
        overlap[name] = {"exact_input": len(current_inputs & fingerprints(values)), "text": len(current_texts & texts(values))}
    if any(value["exact_input"] or value["text"] for value in overlap.values()):
        raise ValueError(f"holdout v0.9 overlap detected: {overlap}")

    OUTPUT.write_text("".join(canonical_json(row) + "\n" for row in rows), encoding="utf-8")
    manifest = {
        "schema_version": "feedback-holdout-manifest-v0.9", "dataset": OUTPUT.name,
        "sha256": sha256(OUTPUT), "records": len(rows), "review_status": "generated_validated",
        "human_reviewed": False, "expert_reviewed": False, "model_inference_count": 0,
        "qualification_scope": "future_stage1_correction_comparison_candidate_selection_only",
        "sealed_before_v0.7_training": True,
        "verdict_counts": dict(sorted(Counter(row["expected_stage1"]["verdict"] for row in rows).items())),
        "stage2_expected_rows": sum(row["expected_stage2"] is not None for row in rows),
        "family_counts": dict(sorted(Counter(row["family"] for row in rows).items())),
        "targeted_stage1_rows": sum(row["family"].startswith(("disagree_wrong_correction", "disagree_nonminimal_meaning")) for row in rows),
        "overlap": overlap,
        "limitations": [
            "자동 생성·계약 검증 데이터이며 사람 또는 일본어 전문가 검수 데이터가 아닙니다.",
            "feedback-v0.7 학습 전에 봉인하며 결과 확인 후 같은 시험지에 맞춰 수정하지 않습니다.",
            "소비된 v0.8 실패 문장을 복사하지 않고 다른 어휘와 구조로 독립 생성했습니다.",
            "기존 학습·holdout·진단 문장과 정확 입력 및 원문 중복이 없습니다.",
        ],
    }
    MANIFEST.write_text(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    protocol = {
        "schema_version": "feedback-holdout-protocol-v0.9", "dataset_sha256": manifest["sha256"],
        "contract_version": "feedback-two-stage-v0.1", "candidate_family": "feedback-verifier-v0.7-stage1-correction-comparison",
        "training_started": False, "ready_for_inference": False, "single_use": True,
        "consumed": False, "model_inference_count": 0, "temperature": 0.0, "top_p": 1.0,
        "stage1_max_tokens": 192, "stage2_max_tokens": 384,
        "thresholds": {
            "stage1_contract_success_rate_min": 0.99, "false_disagreement_rate_max": 0.02,
            "disagreement_precision_min": 0.95, "disagreement_recall_min": 0.80,
            "unreviewable_accuracy_min": 0.90, "stage2_call_discipline_rate_min": 1.0,
            "stage2_contract_success_rate_min": 0.99, "recommended_decision_accuracy_min": 0.90,
            "accepted_correction_rate_min": 0.80, "conditional_total_p95_seconds_max": 10.0,
        },
        "operational_qualification": "blocked_generated_validation_only",
    }
    PROTOCOL.write_text(json.dumps(protocol, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
