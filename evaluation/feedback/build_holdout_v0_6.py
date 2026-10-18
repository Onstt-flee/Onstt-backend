"""Build and seal feedback holdout v0.6 before feedback-v0.5 training.

Deterministic generated validation data; not human or expert review.
"""
from __future__ import annotations

from collections import Counter
import hashlib
import json
from pathlib import Path

from analyzer.feedback_contract import canonical_json, parse_output, validate_input
from evaluation.feedback.build_holdout_v0_2 import input_fingerprint, judgment


ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
OUTPUT = HERE / "holdout_v0.6.jsonl"
MANIFEST = HERE / "holdout_v0.6.manifest.json"
PROTOCOL = HERE / "holdout_v0.6.protocol.json"

PLACES = ["調整室", "配電室", "飼育室", "梱包室", "測量室", "修復室", "消毒室", "製図室", "乾燥室", "試写室"]
THINGS = ["制御盤", "変圧器", "給水器", "包装機", "測量器", "修復台", "消毒器", "製図台", "乾燥機", "映写機"]
PEOPLE = ["技師", "電気係", "飼育員", "梱包係", "測量士", "修復師", "衛生係", "設計士", "乾燥担当", "映写技師"]
ACTIONS = ["機器を調整します", "配線を確認します", "動物を世話します", "荷物を包みます", "土地を測ります", "資料を修復します", "器具を消毒します", "図面を引きます", "材料を乾かします", "映像を試写します"]
DESTINATIONS = ["調整センター", "変電所", "動物保護所", "配送拠点", "測量事務所", "文化財研究所", "衛生管理所", "設計事務所", "乾燥施設", "映像資料館"]
ORTHOGRAPHY = ["わたしわ調整室に行きます。", "資料お配電室に運びます。", "友達わ飼育室にいます。", "荷物お梱包室に置きます。", "兄わ測量室で働きます。", "写真お修復室で見ます。", "母わ消毒室で待ちます。", "図面お製図室に置きます。", "妹わ乾燥室にいます。", "映像お試写室で確認します。"]
REASONS = ["조사와 서술어의 관계가 자연스럽습니다.", "원문을 유지해도 문법상 문제가 없습니다.", "제공된 문맥에서 허용되는 일본어입니다.", "문장 구조와 조사 선택이 자연스럽습니다."]


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def feedback(verdict, issues, recommended, reason):
    return {"verdict": verdict, "issue_codes": issues, "recommended_judgment": recommended, "review_reason_ko": reason}


def build_rows() -> list[dict]:
    specs = []
    for group, (place, thing, person, action, destination, orthography) in enumerate(
        zip(PLACES, THINGS, PEOPLE, ACTIONS, DESTINATIONS, ORTHOGRAPHY)
    ):
        normal = [
            (f"{place}に{thing}があります。", "inanimate_existence_ni_agree"),
            (f"{place}に{person}がいます。", "animate_existence_ni_agree"),
            (f"来春は{destination}に行きます。", "destination_ni_agree"),
        ]
        for index, (text, family) in enumerate(normal):
            candidate = judgment("acceptable", text, [], REASONS[(group + index) % len(REASONS)])
            expected = feedback("agree", [], None, "판단·원문 유지·근거가 서로 일치합니다.")
            specs.append((text, None, family, candidate, expected, "agree_reason_variant"))

        corrected_cases = [
            (f"早朝は{place}で{person}がいます。", f"早朝は{place}に{person}がいます。", "animate_existence_de_correct_audit"),
            (f"再来月は{destination}を行きます。", f"再来月は{destination}に行きます。", "destination_wo_correct_audit"),
        ]
        for text, corrected, family in corrected_cases:
            candidate = judgment("needs_correction", corrected, ["particle_misuse"], "조사 오류를 최소 범위로 교정했습니다.")
            expected = feedback("agree", [], None, "오류 탐지와 최소 교정이 모두 타당합니다.")
            specs.append((text, None, family, candidate, expected, "agree_correction"))

        missed_cases = [
            (f"夕刻は{place}で{thing}があります。", f"夕刻は{place}に{thing}があります。", "inanimate_existence_de_false_negative"),
            (f"昼前は{place}で{person}がいます。", f"昼前は{place}に{person}がいます。", "animate_existence_de_false_negative"),
            (f"今度は{destination}を行きます。", f"今度は{destination}に行きます。", "destination_wo_false_negative"),
        ]
        for text, corrected, family in missed_cases:
            gold = judgment("needs_correction", corrected, ["particle_misuse"], "조사 오류를 최소 범위로 교정해야 합니다.")
            candidate = judgment("acceptable", text, [], REASONS[group % len(REASONS)])
            expected = feedback("disagree", ["false_negative"], gold, "명확한 조사 오류를 놓쳤습니다.")
            specs.append((text, None, family, candidate, expected, "false_negative_semantic_lock"))

        false_positives = [
            (f"午後は{place}で{action}。", "で", "に", "action_de_false_positive", "동작 장소 조사 で가 자연스럽습니다."),
            (f"夜間は{place}に{thing}があります。", "に", "で", "inanimate_existence_ni_false_positive", "존재 장소 조사 に가 자연스럽습니다."),
        ]
        for text, source, replacement, family, reason in false_positives:
            candidate = judgment("needs_correction", text.replace(source, replacement, 1), ["particle_misuse"], "장소 조사를 교정했습니다.")
            gold = judgment("acceptable", text, [], reason)
            expected = feedback("disagree", ["false_positive", "wrong_correction"], gold, "올바른 조사 선택을 바꾸면 안 됩니다.")
            specs.append((text, None, family, candidate, expected, "false_positive_semantic_lock"))

        if group % 2 == 0:
            text = f"翌春は{destination}に行きます。"
            candidate = judgment("acceptable", text, [], "목적지 조사 오류를 교정했습니다.")
            gold = judgment("acceptable", text, [], "목적지 조사 に를 올바르게 사용했습니다.")
            expected = feedback("disagree", ["reason_mismatch"], gold, "허용 판단과 근거 설명이 일치하지 않습니다.")
            specs.append((text, None, "acceptable_reason_mismatch", candidate, expected, "reason_mismatch"))
        else:
            text = f"翌週は{place}で{action}。"
            candidate = judgment("insufficient_evidence", text, [], "일본어인지 판단할 수 없습니다.")
            gold = judgment("acceptable", text, [], "완결된 일본어 문장입니다.")
            expected = feedback("disagree", ["wrong_decision", "unnecessary_abstention"], gold, "완결된 일본어이므로 보류할 이유가 없습니다.")
            specs.append((text, None, "valid_japanese_unnecessary_abstention", candidate, expected, "unnecessary_abstention"))

        changed = orthography.replace("わ", "は", 1) if "わ" in orthography else orthography.replace("お", "を", 1)
        candidate = judgment("needs_correction", changed, ["particle_misuse"], "조사 표기를 바로잡았습니다.")
        expected = feedback("unreviewable", [], None, "원음이 없어 발화 오류와 전사 오류를 구분할 수 없습니다.")
        specs.append((orthography, "STT 전사이며 원음은 제공되지 않았습니다.", "stt_orthography_unreviewable", candidate, expected, "audio_required_unreviewable"))

    rows = []
    for index, (text, context, family, candidate, expected, case_type) in enumerate(specs, 1):
        row = {
            "id": f"FVH-06-{index:03d}", "text": text, "context": context,
            "learner_level": "N4" if index % 4 == 0 else "N5",
            "candidate_judgment": candidate, "expected": expected, "family": family,
            "case_type": case_type, "source_kind": "deterministic_feedback_v0.6_template",
            "review_status": "generated_validated",
        }
        validate_input({"text": text, "context": context, "learner_level": row["learner_level"], "judgment": candidate})
        parsed, error = parse_output(canonical_json(expected), text)
        if parsed is None:
            raise ValueError(f"invalid expected output for {row['id']}: {error}")
        rows.append(row)
    if len(rows) != 120:
        raise ValueError(f"expected 120 rows, got {len(rows)}")
    return rows


def main() -> None:
    if PROTOCOL.exists() and json.loads(PROTOCOL.read_text(encoding="utf-8")).get("consumed"):
        raise SystemExit("refusing to regenerate consumed feedback holdout v0.6")
    rows = build_rows()
    OUTPUT.write_text("".join(canonical_json(row) + "\n" for row in rows), encoding="utf-8")
    current_inputs = {input_fingerprint(row) for row in rows}
    current_texts = {row["text"] for row in rows}
    comparisons = {
        **{f"training_v0.{version}": ROOT / f"training/feedback/data/feedback_v0.{version}.jsonl" for version in (1, 2, 3, 4)},
        **{f"holdout_v0.{version}": HERE / f"holdout_v0.{version}.jsonl" for version in (1, 2, 3, 4, 5)},
        **{f"diagnostic_v0.{version}": HERE / f"existence_particle_diagnostic_v0.{version}.jsonl" for version in (1, 2)},
    }
    overlap = {}
    for name, path in comparisons.items():
        values = load(path)
        overlap[name] = {
            "exact_input": len(current_inputs & {input_fingerprint(row) for row in values}),
            "text": len(current_texts & {row["text"] for row in values}),
        }
    if any(item["exact_input"] or item["text"] for item in overlap.values()):
        raise ValueError(f"holdout v0.6 overlap detected: {overlap}")
    manifest = {
        "schema_version": "feedback-holdout-manifest-v0.6", "dataset": OUTPUT.name,
        "sha256": sha(OUTPUT), "records": len(rows), "review_status": "generated_validated",
        "human_reviewed": False, "expert_reviewed": False, "model_inference_count": 0,
        "qualification_scope": "gpu_internal_model_selection_only",
        "verdict_counts": dict(sorted(Counter(row["expected"]["verdict"] for row in rows).items())),
        "case_type_counts": dict(sorted(Counter(row["case_type"] for row in rows).items())),
        "family_counts": dict(sorted(Counter(row["family"] for row in rows).items())),
        "overlap": overlap,
        "limitations": [
            "자동 생성·계약 검증 데이터이며 사람 또는 일본어 전문가 검수 데이터가 아닙니다.",
            "feedback-v0.5 학습 전에 봉인하며 소비 후 재튜닝에 사용하지 않습니다.",
            "기존 학습·holdout·조사 진단 문장을 포함하지 않습니다.",
        ],
    }
    MANIFEST.write_text(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    protocol = {
        "schema_version": "feedback-holdout-protocol-v0.6", "dataset_sha256": manifest["sha256"],
        "contract_version": "feedback-v0.1", "candidate_family": "feedback-v0.5",
        "adapter_sha256": None, "training_data_sha256": None, "training_config_sha256": None,
        "training_run": None, "ready_for_inference": False, "single_use": True, "consumed": False,
        "temperature": 0.0, "top_p": 1.0, "max_tokens": 512,
        "serving": {"engine": "vllm", "reasoning_parser": "qwen3", "flashinfer_sampler": False},
        "thresholds": {
            "contract_success_rate_min": 0.99, "false_disagreement_rate_max": 0.02,
            "disagreement_precision_min": 0.95, "disagreement_recall_min": 0.80,
            "recommended_decision_accuracy_min": 0.90, "accepted_correction_rate_min": 0.80,
            "p95_latency_seconds_max": 5.0,
        },
        "operational_qualification": "blocked_internal_generated_validation_only",
    }
    PROTOCOL.write_text(json.dumps(protocol, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
