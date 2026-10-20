"""Build and seal the unused two-stage feedback holdout v0.7.

Deterministic generated validation data; not human or expert review.  This
builder is frozen before implementation of the two-stage verifier contract.
"""

from __future__ import annotations

from collections import Counter
import hashlib
import json
from pathlib import Path

from analyzer.feedback_contract import canonical_json, validate_input
from evaluation.feedback.build_holdout_v0_2 import input_fingerprint, judgment


ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
OUTPUT = HERE / "holdout_v0.7.jsonl"
MANIFEST = HERE / "holdout_v0.7.manifest.json"
PROTOCOL = HERE / "holdout_v0.7.protocol.json"

PLACES = ["検疫室", "音響室", "標本庫", "発酵室", "観測小屋", "製本室", "鑑定室", "収蔵庫", "温室", "操舵室"]
THINGS = ["検査台", "音響卓", "標本箱", "発酵槽", "観測機器", "製本機", "鑑定用ライト", "保存棚", "加湿器", "航海計器"]
PEOPLE = ["検疫官", "音響技師", "学芸員", "醸造担当", "観測員", "製本職人", "鑑定士", "保存担当", "園芸員", "航海士"]
ACTIONS = ["書類を確認します", "音量を調整します", "標本を整理します", "温度を測ります", "星を観察します", "表紙を直します", "資料を調べます", "作品を保管します", "苗に水をやります", "進路を確認します"]
DESTINATIONS = ["検疫所", "録音スタジオ", "自然史博物館", "醸造研究所", "天体観測所", "古書修復所", "宝石鑑定所", "美術品保管所", "植物研究園", "海事資料館"]
REPORTS = ["検疫記録", "録音記録", "標本目録", "発酵記録", "観測日誌", "製本指示書", "鑑定報告", "収蔵目録", "栽培日誌", "航海日誌"]


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def input_fingerprints(rows: list[dict]) -> set[str]:
    required = {"text", "context", "learner_level", "candidate_judgment"}
    return {input_fingerprint(row) for row in rows if required <= set(row)}


def stage1(verdict: str, issues: list[str], reason: str) -> dict:
    return {"verdict": verdict, "issue_codes": issues, "review_reason_ko": reason}


def build_rows() -> list[dict]:
    specs = []
    for group, (place, thing, person, action, destination, report) in enumerate(
        zip(PLACES, THINGS, PEOPLE, ACTIONS, DESTINATIONS, REPORTS)
    ):
        valid_existence = f"現在、{place}に{thing}があります。"
        specs.append((valid_existence, None, "agree_valid_existence", judgment("acceptable", valid_existence, [], "존재 장소 조사와 서술어가 자연스럽습니다."), stage1("agree", [], "판단과 근거가 타당합니다."), None))

        valid_action = f"午前中は{place}で{action}。"
        specs.append((valid_action, None, "agree_valid_action", judgment("acceptable", valid_action, [], "동작 장소 조사 で가 자연스럽습니다."), stage1("agree", [], "문법 판단이 타당합니다."), None))

        destination_error = f"次の研修では{destination}を行きます。"
        destination_gold = judgment("needs_correction", f"次の研修では{destination}に行きます。", ["particle_misuse"], "목적지에는 조사 に를 사용합니다.")
        specs.append((destination_error, None, "agree_correct_particle", destination_gold, stage1("agree", [], "최소 조사 교정이 타당합니다."), None))

        conjugation_error = f"昨日、{place}で{report}を読むました。"
        conjugation_gold = judgment("needs_correction", f"昨日、{place}で{report}を読みました。", ["verb_conjugation"], "読む의 정중 과거형은 読みました입니다.")
        specs.append((conjugation_error, None, "agree_correct_conjugation", conjugation_gold, stage1("agree", [], "동사 활용 교정이 타당합니다."), None))

        valid_person = f"今朝、{person}は{place}にいました。"
        specs.append((valid_person, None, "agree_valid_person", judgment("acceptable", valid_person, [], "사람의 존재 장소에 に를 올바르게 사용했습니다."), stage1("agree", [], "허용 판단이 타당합니다."), None))

        missed_particle = f"現在、{place}で{thing}があります。"
        missed_particle_gold = judgment("needs_correction", f"現在、{place}に{thing}があります。", ["particle_misuse"], "사물의 존재 장소에는 조사 に가 필요합니다.")
        specs.append((missed_particle, None, "disagree_false_negative_particle", judgment("acceptable", missed_particle, [], "문법적으로 허용됩니다."), stage1("disagree", ["false_negative"], "명확한 조사 오류를 놓쳤습니다."), missed_particle_gold))

        missed_conjugation = f"毎週、{person}が{report}を確認するます。"
        missed_conjugation_gold = judgment("needs_correction", f"毎週、{person}が{report}を確認します。", ["verb_conjugation"], "確認する의 정중형은 確認します입니다.")
        specs.append((missed_conjugation, None, "disagree_false_negative_conjugation", judgment("acceptable", missed_conjugation, [], "문법적으로 허용됩니다."), stage1("disagree", ["false_negative"], "동사 활용 오류를 놓쳤습니다."), missed_conjugation_gold))

        false_positive = f"午後は{place}で{action}。"
        false_positive_gold = judgment("acceptable", false_positive, [], "동작이 일어나는 장소에는 조사 で가 자연스럽습니다.")
        specs.append((false_positive, None, "disagree_false_positive", judgment("needs_correction", false_positive.replace("で", "に", 1), ["particle_misuse"], "장소 조사를 교정했습니다."), stage1("disagree", ["false_positive", "wrong_correction"], "올바른 동작 장소 조사를 바꾸면 안 됩니다."), false_positive_gold))

        wrong_correction = f"来年度は{destination}を行きます。"
        wrong_correction_gold = judgment("needs_correction", f"来年度は{destination}に行きます。", ["particle_misuse"], "목적지에는 조사 に가 필요합니다.")
        specs.append((wrong_correction, None, "disagree_wrong_correction", judgment("needs_correction", f"来年度は{destination}で行きます。", ["particle_misuse"], "목적지 조사를 교정했습니다."), stage1("disagree", ["wrong_correction"], "오류는 찾았지만 교정 조사가 잘못됐습니다."), wrong_correction_gold))

        nonminimal = f"先週、{place}で{report}を読むました。"
        nonminimal_gold = judgment("needs_correction", f"先週、{place}で{report}を読みました。", ["verb_conjugation"], "문체와 의미를 유지하며 활용만 고칩니다.")
        changed_place = DESTINATIONS[(group + 3) % len(DESTINATIONS)]
        specs.append((nonminimal, None, "disagree_nonminimal_meaning", judgment("needs_correction", f"先週、{changed_place}で{report}を読みました。", ["verb_conjugation"], "자연스럽게 고쳤습니다."), stage1("disagree", ["nonminimal_correction", "meaning_changed"], "활용 외 장소까지 바꿔 원문 의미를 변경했습니다."), nonminimal_gold))

        if group % 2 == 0:
            boundary_text = f"来週、{person}は{place}にいます。"
            boundary_candidate = judgment("acceptable", boundary_text, [], "문법 오류를 최소 교정했습니다.")
            boundary_stage1 = stage1("disagree", ["reason_mismatch"], "허용 판단과 오류 교정 근거가 일치하지 않습니다.")
            boundary_gold = judgment("acceptable", boundary_text, [], "완결된 문법적으로 허용되는 문장입니다.")
            boundary_family = "disagree_reason_mismatch"
        else:
            boundary_text = f"来週、{person}は{place}で{action}。"
            boundary_candidate = judgment("insufficient_evidence", boundary_text, [], "정보가 부족해 판단할 수 없습니다.")
            boundary_stage1 = stage1("disagree", ["wrong_decision", "unnecessary_abstention"], "완결된 문장이므로 보류할 이유가 없습니다.")
            boundary_gold = judgment("acceptable", boundary_text, [], "문법적으로 완결된 문장입니다.")
            boundary_family = "disagree_unnecessary_abstention"
        specs.append((boundary_text, None, boundary_family, boundary_candidate, boundary_stage1, boundary_gold))

        orthography = f"わたしわ{destination}に行きます。" if group % 2 == 0 else f"{report}お読みます。"
        corrected = orthography.replace("わ", "は", 1) if "わ" in orthography else orthography.replace("お", "を", 1)
        specs.append((orthography, "STT 전사이며 원음은 제공되지 않았습니다.", "unreviewable_audio_orthography", judgment("needs_correction", corrected, ["particle_misuse"], "조사 표기를 고쳤습니다."), stage1("unreviewable", [], "원음 없이 발화 오류와 전사 오류를 구분할 수 없습니다."), None))

    rows = []
    for index, (text, context, family, candidate, expected_stage1, expected_stage2) in enumerate(specs, 1):
        row = {
            "id": f"FVH-07-{index:03d}",
            "text": text,
            "context": context,
            "learner_level": "N4" if index % 3 == 0 else "N5",
            "candidate_judgment": candidate,
            "expected_stage1": expected_stage1,
            "expected_stage2": expected_stage2,
            "family": family,
            "source_kind": "deterministic_feedback_two_stage_holdout_v0.7",
            "review_status": "generated_validated",
        }
        validate_input({"text": text, "context": context, "learner_level": row["learner_level"], "judgment": candidate})
        if expected_stage1["verdict"] == "disagree" and expected_stage2 is None:
            raise ValueError(f"{row['id']} disagree requires stage-2 recommendation")
        if expected_stage1["verdict"] != "disagree" and expected_stage2 is not None:
            raise ValueError(f"{row['id']} non-disagree must not have stage-2 recommendation")
        rows.append(row)
    if len(rows) != 120 or len({row["text"] for row in rows}) != 120:
        raise ValueError("holdout v0.7 must contain 120 unique texts")
    return rows


def main() -> int:
    if PROTOCOL.exists():
        raise SystemExit("refusing to regenerate sealed feedback holdout v0.7")
    rows = build_rows()
    current_inputs = input_fingerprints(rows)
    current_texts = {row["text"] for row in rows}
    comparisons = {
        **{f"training_v0.{version}": ROOT / f"training/feedback/data/feedback_v0.{version}.jsonl" for version in (1, 2, 3, 4, 5)},
        **{f"holdout_v0.{version}": HERE / f"holdout_v0.{version}.jsonl" for version in (1, 2, 3, 4, 5, 6)},
        **{f"diagnostic_v0.{version}": HERE / f"existence_particle_diagnostic_v0.{version}.jsonl" for version in (1, 2)},
        "particle_adversarial_v0.1": HERE / "particle_risk_adversarial_v0.1.jsonl",
    }
    overlap = {}
    for name, path in comparisons.items():
        values = load(path)
        overlap[name] = {
            "exact_input": len(current_inputs & input_fingerprints(values)),
            "text": len(current_texts & {row["text"] for row in values}),
        }
    if any(item["exact_input"] or item["text"] for item in overlap.values()):
        raise ValueError(f"holdout v0.7 overlap detected: {overlap}")

    OUTPUT.write_text("".join(canonical_json(row) + "\n" for row in rows), encoding="utf-8")
    verdicts = Counter(row["expected_stage1"]["verdict"] for row in rows)
    manifest = {
        "schema_version": "feedback-holdout-manifest-v0.7",
        "dataset": OUTPUT.name,
        "sha256": sha256(OUTPUT),
        "records": len(rows),
        "review_status": "generated_validated",
        "human_reviewed": False,
        "expert_reviewed": False,
        "model_inference_count": 0,
        "qualification_scope": "future_two_stage_candidate_selection_only",
        "sealed_before_two_stage_implementation": True,
        "verdict_counts": dict(sorted(verdicts.items())),
        "stage2_expected_rows": sum(row["expected_stage2"] is not None for row in rows),
        "family_counts": dict(sorted(Counter(row["family"] for row in rows).items())),
        "overlap": overlap,
        "limitations": [
            "자동 생성·계약 검증 데이터이며 사람 또는 일본어 전문가 검수 데이터가 아닙니다.",
            "2단계 계약 구현 전에 봉인했으며 결과 확인 후 같은 시험지에 맞춰 수정하지 않습니다.",
            "기존 학습·holdout·진단 문장과 정확 입력 및 원문 중복이 없습니다.",
        ],
    }
    MANIFEST.write_text(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    protocol = {
        "schema_version": "feedback-holdout-protocol-v0.7",
        "dataset_sha256": manifest["sha256"],
        "contract_version": "feedback-two-stage-v0.1-preimplementation-seal",
        "candidate_family": "feedback-two-stage-v0.1",
        "implementation_started": False,
        "ready_for_inference": False,
        "single_use": True,
        "consumed": False,
        "model_inference_count": 0,
        "temperature": 0.0,
        "top_p": 1.0,
        "stage1_max_tokens": 192,
        "stage2_max_tokens": 384,
        "thresholds": {
            "stage1_contract_success_rate_min": 0.99,
            "false_disagreement_rate_max": 0.02,
            "disagreement_precision_min": 0.95,
            "disagreement_recall_min": 0.80,
            "unreviewable_accuracy_min": 0.90,
            "stage2_call_discipline_rate_min": 1.0,
            "stage2_contract_success_rate_min": 0.99,
            "recommended_decision_accuracy_min": 0.90,
            "accepted_correction_rate_min": 0.80,
            "conditional_total_p95_seconds_max": 10.0
        },
        "operational_qualification": "blocked_preimplementation_seal_only",
    }
    PROTOCOL.write_text(json.dumps(protocol, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
