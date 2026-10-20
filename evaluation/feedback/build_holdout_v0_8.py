"""Build and pre-seal feedback holdout v0.8 before v0.6 training."""

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
OUTPUT = HERE / "holdout_v0.8.jsonl"
MANIFEST = HERE / "holdout_v0.8.manifest.json"
PROTOCOL = HERE / "holdout_v0.8.protocol.json"

PLACES = ["配電室", "裁断室", "乾燥室", "調色室", "計量室", "梱包室", "試写室", "製図室", "消毒室", "選別室"]
THINGS = ["配電盤", "裁断機", "乾燥棚", "調色台", "計量器", "梱包台", "映写機", "製図台", "消毒器", "選別機"]
PEOPLE = ["電気技師", "裁断担当", "乾燥担当", "調色担当", "計量担当", "梱包担当", "映写技師", "設計士", "衛生担当", "選別担当"]
ACTIONS = ["電圧を確認します", "布を裁断します", "材料を乾かします", "塗料を混ぜます", "原料を量ります", "商品を包みます", "映像を確認します", "図面を引きます", "器具を消毒します", "部品を選別します"]
DESTINATIONS = ["変電所", "縫製工房", "乾燥施設", "塗装工房", "計量センター", "物流倉庫", "上映館", "設計事務所", "衛生管理室", "選別工場"]
REPORTS = ["点検記録", "裁断指示書", "乾燥記録", "調色表", "計量票", "梱包明細", "試写記録", "設計図", "消毒記録", "選別報告"]


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def fingerprints(rows: list[dict]) -> set[str]:
    required = {"text", "context", "learner_level", "candidate_judgment"}
    return {input_fingerprint(row) for row in rows if required <= set(row)}


def build_rows() -> list[dict]:
    specs = []
    for group, (place, thing, person, action, destination, report) in enumerate(
        zip(PLACES, THINGS, PEOPLE, ACTIONS, DESTINATIONS, REPORTS)
    ):
        valid_existence = f"本日、{place}に{thing}があります。"
        specs.append((valid_existence, None, "agree_valid_existence", judgment("acceptable", valid_existence, [], "존재 장소 조사가 자연스럽습니다."), stage1("agree", [], "판단과 근거가 타당합니다."), None))

        valid_action = f"作業時間は{place}で{action}。"
        specs.append((valid_action, None, "agree_valid_action", judgment("acceptable", valid_action, [], "동작 장소 조사 で가 자연스럽습니다."), stage1("agree", [], "허용 판단이 타당합니다."), None))

        destination_error = f"来月は{destination}を行きます。"
        destination_gold = judgment("needs_correction", f"来月は{destination}に行きます。", ["particle_misuse"], "목적지에는 조사 に를 사용합니다.")
        specs.append((destination_error, None, "agree_correct_particle", destination_gold, stage1("agree", [], "최소 교정이 타당합니다."), None))

        conjugation_error = f"先ほど、{place}で{report}を読むました。"
        conjugation_gold = judgment("needs_correction", f"先ほど、{place}で{report}を読みました。", ["verb_conjugation"], "読む의 정중 과거형을 고칩니다.")
        specs.append((conjugation_error, None, "agree_correct_conjugation", conjugation_gold, stage1("agree", [], "동사 활용 교정이 타당합니다."), None))

        valid_person = f"夕方、{person}は{place}にいました。"
        specs.append((valid_person, None, "agree_valid_person", judgment("acceptable", valid_person, [], "사람의 존재 장소에 に가 자연스럽습니다."), stage1("agree", [], "허용 판단이 타당합니다."), None))

        missed_particle = f"本日、{place}で{thing}があります。"
        specs.append((missed_particle, None, "disagree_false_negative_particle", judgment("acceptable", missed_particle, [], "문법적으로 허용됩니다."), stage1("disagree", ["false_negative"], "조사 오류를 놓쳤습니다."), judgment("needs_correction", f"本日、{place}に{thing}があります。", ["particle_misuse"], "존재 장소에는 に가 필요합니다.")))

        missed_conjugation = f"毎月、{person}が{report}を整理するます。"
        specs.append((missed_conjugation, None, "disagree_false_negative_conjugation", judgment("acceptable", missed_conjugation, [], "문법적으로 허용됩니다."), stage1("disagree", ["false_negative"], "활용 오류를 놓쳤습니다."), judgment("needs_correction", f"毎月、{person}が{report}を整理します。", ["verb_conjugation"], "整理する의 정중형을 고칩니다.")))

        false_positive = f"午後の作業は{place}で{action}。"
        specs.append((false_positive, None, "disagree_false_positive", judgment("needs_correction", false_positive.replace("で", "に", 1), ["particle_misuse"], "장소 조사를 고쳤습니다."), stage1("disagree", ["false_positive", "wrong_correction"], "올바른 동작 장소 조사를 바꾸면 안 됩니다."), judgment("acceptable", false_positive, [], "동작 장소에는 で가 자연스럽습니다.")))

        wrong = f"次回は{destination}を行きます。"
        specs.append((wrong, None, "disagree_wrong_correction", judgment("needs_correction", f"次回は{destination}で行きます。", ["particle_misuse"], "조사를 교정했습니다."), stage1("disagree", ["wrong_correction"], "교정 조사가 잘못됐습니다."), judgment("needs_correction", f"次回は{destination}に行きます。", ["particle_misuse"], "목적지에는 に를 사용합니다.")))

        nonminimal = f"昨日、{place}で{report}を読むました。"
        changed = DESTINATIONS[(group + 4) % len(DESTINATIONS)]
        specs.append((nonminimal, None, "disagree_nonminimal_meaning", judgment("needs_correction", f"昨日、{changed}で{report}を読みました。", ["verb_conjugation"], "자연스럽게 고쳤습니다."), stage1("disagree", ["nonminimal_correction", "meaning_changed"], "활용 외 장소까지 바꿨습니다."), judgment("needs_correction", f"昨日、{place}で{report}を読みました。", ["verb_conjugation"], "활용만 최소 교정합니다.")))

        boundary = f"明朝、{person}は{place}で{action}。"
        if group % 2 == 0:
            candidate = judgment("acceptable", boundary, [], "문법 오류를 교정했습니다.")
            expected1 = stage1("disagree", ["reason_mismatch"], "판단과 근거가 일치하지 않습니다.")
            family = "disagree_reason_mismatch"
        else:
            candidate = judgment("insufficient_evidence", boundary, [], "정보가 부족합니다.")
            expected1 = stage1("disagree", ["wrong_decision", "unnecessary_abstention"], "완결된 문장을 불필요하게 보류했습니다.")
            family = "disagree_unnecessary_abstention"
        specs.append((boundary, None, family, candidate, expected1, judgment("acceptable", boundary, [], "문법적으로 완결된 문장입니다.")))

        orthography = f"ぼくわ{destination}に行きます。" if group % 2 == 0 else f"{report}お確認します。"
        corrected = orthography.replace("わ", "は", 1) if "わ" in orthography else orthography.replace("お", "を", 1)
        specs.append((orthography, "STT 전사이며 원음은 제공되지 않았습니다.", "unreviewable_audio_orthography", judgment("needs_correction", corrected, ["particle_misuse"], "조사 표기를 고쳤습니다."), stage1("unreviewable", [], "원음 없이 발화와 전사 오류를 구분할 수 없습니다."), None))

    rows = []
    for index, (text, context, family, candidate, expected1, expected2) in enumerate(specs, 1):
        row = {
            "id": f"FVH-08-{index:03d}", "text": text, "context": context,
            "learner_level": "N4" if index % 4 == 0 else "N5",
            "candidate_judgment": candidate, "expected_stage1": expected1,
            "expected_stage2": expected2, "family": family,
            "source_kind": "deterministic_feedback_two_stage_holdout_v0.8",
            "review_status": "generated_validated",
        }
        validate_input({"text": text, "context": context, "learner_level": row["learner_level"], "judgment": candidate})
        if (expected1["verdict"] == "disagree") != (expected2 is not None):
            raise ValueError(f"stage boundary mismatch: {row['id']}")
        rows.append(row)
    if len(rows) != 120 or len({row["text"] for row in rows}) != 120:
        raise ValueError("holdout v0.8 must contain 120 unique texts")
    return rows


def main() -> int:
    if PROTOCOL.exists():
        raise SystemExit("refusing to regenerate sealed feedback holdout v0.8")
    rows = build_rows()
    current_inputs, current_texts = fingerprints(rows), {row["text"] for row in rows}
    comparisons = {
        **{f"training_v0.{version}": ROOT / f"training/feedback/data/feedback_v0.{version}.jsonl" for version in (1, 2, 3, 4, 5)},
        **{f"holdout_v0.{version}": HERE / f"holdout_v0.{version}.jsonl" for version in (1, 2, 3, 4, 5, 6, 7)},
        **{f"diagnostic_v0.{version}": HERE / f"existence_particle_diagnostic_v0.{version}.jsonl" for version in (1, 2)},
        "particle_adversarial_v0.1": HERE / "particle_risk_adversarial_v0.1.jsonl",
    }
    overlap = {}
    for name, path in comparisons.items():
        values = load(path)
        overlap[name] = {"exact_input": len(current_inputs & fingerprints(values)), "text": len(current_texts & {row["text"] for row in values})}
    if any(value["exact_input"] or value["text"] for value in overlap.values()):
        raise ValueError(f"holdout v0.8 overlap detected: {overlap}")

    OUTPUT.write_text("".join(canonical_json(row) + "\n" for row in rows), encoding="utf-8")
    manifest = {
        "schema_version": "feedback-holdout-manifest-v0.8", "dataset": OUTPUT.name,
        "sha256": sha256(OUTPUT), "records": len(rows), "review_status": "generated_validated",
        "human_reviewed": False, "expert_reviewed": False, "model_inference_count": 0,
        "qualification_scope": "future_stage_specific_candidate_selection_only",
        "sealed_before_v0.6_training": True,
        "verdict_counts": dict(sorted(Counter(row["expected_stage1"]["verdict"] for row in rows).items())),
        "stage2_expected_rows": sum(row["expected_stage2"] is not None for row in rows),
        "family_counts": dict(sorted(Counter(row["family"] for row in rows).items())),
        "overlap": overlap,
        "limitations": [
            "자동 생성·계약 검증 데이터이며 사람 또는 일본어 전문가 검수 데이터가 아닙니다.",
            "feedback-v0.6 학습 전에 봉인하며 결과 확인 후 같은 시험지에 맞춰 수정하지 않습니다.",
            "기존 학습·holdout·진단 문장과 정확 입력 및 원문 중복이 없습니다.",
        ],
    }
    MANIFEST.write_text(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    protocol = {
        "schema_version": "feedback-holdout-protocol-v0.8", "dataset_sha256": manifest["sha256"],
        "contract_version": "feedback-two-stage-v0.1", "candidate_family": "feedback-verifier-v0.6-stage-specific",
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
