"""Build and pre-seal feedback holdout v0.11 before v0.9 training."""

from __future__ import annotations

from collections import Counter
import hashlib
import json
from pathlib import Path

from analyzer.feedback_contract import canonical_json, validate_input
from evaluation.feedback.build_holdout_v0_2 import input_fingerprint, judgment
from evaluation.feedback.build_holdout_v0_7 import stage1
from analyzer.feedback_two_stage_contract import parse_stage1_output, parse_stage2_output

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
OUTPUT = HERE / "holdout_v0.11.jsonl"
MANIFEST = HERE / "holdout_v0.11.manifest.json"
PROTOCOL = HERE / "holdout_v0.11.protocol.json"

PLACES = ["校正ラボ", "資材庫", "計測区画", "収録室", "梱包室", "水耕室", "文書出力室", "低温庫", "組立区画", "受付室"]
THINGS = ["校正器", "交換部品", "計測盤", "録音卓", "梱包台", "栽培棚", "文書出力機", "低温容器", "組立機", "受付端末"]
PEOPLE = ["校正担当", "資材係", "計測担当", "収録担当", "梱包係", "栽培担当", "印刷係", "低温管理者", "機器組立担当", "受付係"]
ACTIONS = ["基準値を確認します", "部品を整理します", "波形を測定します", "音声を収録します", "商品を梱包します", "野菜を栽培します", "書類を出力します", "検体を保存します", "装置を組み立てます", "申請を受け付けます"]
DESTINATIONS = ["校正棟", "資材センター", "計測所", "録音センター", "梱包工場", "栽培ハウス", "印刷所", "低温施設", "機器組立棟", "受付窓口"]
OBJECTS = ["校正票", "資材表", "計測記録", "収録一覧", "梱包見本", "水耕記録", "印刷原稿", "保存記録", "機器構成図", "受付票"]


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def visible_input(row: dict) -> dict | None:
    required = {"text", "context", "learner_level", "candidate_judgment"}
    if required <= set(row):
        return row
    value = row.get("model_input")
    model_required = {"text", "context", "learner_level", "judgment"}
    if isinstance(value, dict) and model_required <= set(value):
        return {
            "text": value["text"],
            "context": value["context"],
            "learner_level": value["learner_level"],
            "candidate_judgment": value["judgment"],
        }
    return None


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
        specs.append((action_ok, None, "disagree_false_positive_rewrite", judgment("needs_correction", f"明日は{destination}で別の作業をします。", ["particle_misuse"], "더 자연스럽게 교정했습니다."), stage1("disagree", ["false_positive", "nonminimal_correction", "meaning_changed"], "허용 문장을 불필요하게 바꾸고 의미도 변경했습니다."), judgment("acceptable", action_ok, [], "원문은 문법적으로 허용됩니다.")))

        existence_ok = f"現在、{place}に{thing}があります。"
        specs.append((existence_ok, None, "agree_valid_existence", judgment("acceptable", existence_ok, [], "존재 장소에 に를 올바르게 사용했습니다."), stage1("agree", [], "허용 판단이 타당합니다."), None))

        particle_error = f"来週は{destination}を行きます。"
        particle_fixed = f"来週は{destination}に行きます。"
        specs.append((particle_error, None, "agree_correct_particle", judgment("needs_correction", particle_fixed, ["particle_misuse"], "목적지 조사만 최소 교정했습니다."), stage1("agree", [], "조사 교정이 타당합니다."), None))

        conjugation_error = f"昨日、{person}が{obj}を確認するました。"
        conjugation_fixed = f"昨日、{person}が{obj}を確認しました。"
        specs.append((conjugation_error, None, "agree_correct_conjugation", judgment("needs_correction", conjugation_fixed, ["verb_conjugation"], "동사의 정중 과거형만 교정했습니다."), stage1("agree", [], "활용 교정이 타당합니다."), None))

        if group % 2 == 0:
            person_source = f"夕方、{person}は{place}でいました。"
            person_fixed = f"夕方、{person}は{place}にいました。"
            specs.append((person_source, None, "disagree_wrong_error_type", judgment("needs_correction", person_fixed, ["verb_conjugation"], "동사 활용을 교정했습니다."), stage1("disagree", ["wrong_error_type", "reason_mismatch"], "교정문은 타당하지만 오류 유형과 근거가 맞지 않습니다."), judgment("needs_correction", person_fixed, ["particle_misuse"], "사람의 존재 장소에는 に를 사용합니다.")))
        else:
            fragment = f"夕方、{person}は{place}に……"
            specs.append((fragment, None, "disagree_should_abstain", judgment("acceptable", fragment, [], "문법적으로 허용됩니다."), stage1("disagree", ["should_abstain", "wrong_decision"], "발화가 끝나지 않아 확정 판단할 근거가 부족합니다."), judgment("insufficient_evidence", fragment, [], "미완성 발화이므로 판단을 보류합니다.")))

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
            "id": f"FVH-11-{index:03d}", "text": text, "context": context,
            "learner_level": "N4" if index % 4 == 0 else "N5",
            "candidate_judgment": candidate, "expected_stage1": expected1,
            "expected_stage2": expected2, "family": family,
            "source_kind": "deterministic_feedback_two_stage_holdout_v0.11",
            "review_status": "generated_validated",
        }
        validate_input({"text": text, "context": context, "learner_level": row["learner_level"], "judgment": candidate})
        parsed_stage1, stage1_error = parse_stage1_output(canonical_json(expected1))
        if parsed_stage1 is None:
            raise ValueError(f"invalid stage-1 gold {row['id']}: {stage1_error}")
        if expected2 is not None:
            parsed_stage2, stage2_error = parse_stage2_output(canonical_json(expected2), text, expected1["issue_codes"])
            if parsed_stage2 is None:
                raise ValueError(f"invalid stage-2 gold {row['id']}: {stage2_error}")
        if (expected1["verdict"] == "disagree") != (expected2 is not None):
            raise ValueError(f"stage boundary mismatch: {row['id']}")
        rows.append(row)
    if len(rows) != 120 or len({row["text"] for row in rows}) != 120:
        raise ValueError("holdout v0.11 must contain 120 unique texts")
    return rows


def main() -> int:
    if PROTOCOL.exists():
        raise SystemExit("refusing to regenerate sealed feedback holdout v0.11")
    rows = build_rows()
    current_inputs, current_texts = fingerprints(rows), texts(rows)
    comparisons = {
        **{f"training_v0.{version}": ROOT / f"training/feedback/data/feedback_v0.{version}.jsonl" for version in (1, 2, 3, 4, 5)},
        "training_v0.6": ROOT / "training/feedback/data/feedback_v0.6.two-stage.jsonl",
        "training_v0.7": ROOT / "training/feedback/data/feedback_v0.7.stage1-comparison.jsonl",
        "training_v0.8": ROOT / "training/feedback/data/feedback_v0.8.stage2-recovery-style.jsonl",
        **{f"holdout_v0.{version}": HERE / f"holdout_v0.{version}.jsonl" for version in (1, 2, 3, 4, 5, 6, 7, 8, 9, 10)},
        **{f"diagnostic_v0.{version}": HERE / f"existence_particle_diagnostic_v0.{version}.jsonl" for version in (1, 2)},
        "particle_adversarial_v0.1": HERE / "particle_risk_adversarial_v0.1.jsonl",
    }
    overlap = {}
    for name, path in comparisons.items():
        values = load(path)
        overlap[name] = {"exact_input": len(current_inputs & fingerprints(values)), "text": len(current_texts & texts(values))}
    if any(value["exact_input"] or value["text"] for value in overlap.values()):
        raise ValueError(f"holdout v0.11 overlap detected: {overlap}")

    OUTPUT.write_text("".join(canonical_json(row) + "\n" for row in rows), encoding="utf-8")
    manifest = {
        "schema_version": "feedback-holdout-manifest-v0.11", "dataset": OUTPUT.name,
        "sha256": sha256(OUTPUT), "records": len(rows), "review_status": "generated_validated",
        "human_reviewed": False, "expert_reviewed": False, "model_inference_count": 0,
        "qualification_scope": "future_stage2_contract_stability_candidate_selection_only",
        "sealed_before_v0.9_training": True,
        "verdict_counts": dict(sorted(Counter(row["expected_stage1"]["verdict"] for row in rows).items())),
        "stage2_expected_rows": sum(row["expected_stage2"] is not None for row in rows),
        "family_counts": dict(sorted(Counter(row["family"] for row in rows).items())),
        "targeted_stage2_rows": sum(row["expected_stage2"] is not None for row in rows),
        "overlap": overlap,
        "limitations": [
            "자동 생성·계약 검증 데이터이며 사람 또는 일본어 전문가 검수 데이터가 아닙니다.",
            "feedback-v0.9 학습 전에 봉인하며 결과 확인 후 같은 시험지에 맞춰 수정하지 않습니다.",
            "소비된 v0.10 문장을 복사하지 않고 다른 어휘와 구조로 독립 생성했습니다.",
            "기존 학습·holdout·진단 문장과 정확 입력 및 원문 중복이 없습니다.",
        ],
    }
    MANIFEST.write_text(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    protocol = {
        "schema_version": "feedback-holdout-protocol-v0.11", "dataset_sha256": manifest["sha256"],
        "contract_version": "feedback-two-stage-v0.1", "candidate_family": "feedback-verifier-v0.9-stage2-contract-stability",
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
