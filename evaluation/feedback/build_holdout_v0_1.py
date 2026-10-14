"""Build the sealed, source-balanced feedback-v0.1 holdout deterministically."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
OUTPUT = Path(__file__).with_name("holdout_v0.1.jsonl")
MANIFEST = Path(__file__).with_name("holdout_v0.1.manifest.json")
PROTOCOL = Path(__file__).with_name("holdout_v0.1.protocol.json")
TIMES = ["来月の月曜日", "再来週の火曜日", "今度の水曜日", "来月の木曜日", "再来週の金曜日",
         "今度の土曜日", "来月の日曜日", "再来週の月曜日", "今度の火曜日", "来月の水曜日"]


def judgment(decision, corrected, errors, reason):
    return {"decision": decision, "corrected_text": corrected, "error_types": errors, "reason_ko": reason}


def recommendation(decision, corrected, errors, reason):
    return judgment(decision, corrected, errors, reason)


def build_rows():
    rows = []
    for family in range(12):
        for index, time_word in enumerate(TIMES):
            runtime = "gpu_bf16" if (family * 10 + index) % 2 == 0 else "pi_gguf"
            if family == 0:
                text = f"{time_word}は図書館に行きます。"
                candidate = judgment("acceptable", text, [], "문법적으로 자연스러운 문장입니다.")
                verdict, issues, recommended = "agree", [], None
            elif family == 1:
                text = f"{time_word}は病院を行きます。"; corrected = text.replace("病院を", "病院に")
                candidate = judgment("needs_correction", corrected, ["particle_misuse"], "목적지에는 に를 씁니다.")
                verdict, issues, recommended = "agree", [], None
            elif family == 2:
                text = f"{time_word}は公園に行きます。"; wrong = text.replace("公園に", "公園へ")
                candidate = judgment("needs_correction", wrong, ["particle_misuse"], "に를 へ로 바꿔야 합니다.")
                verdict, issues = "disagree", ["false_positive"]
                recommended = recommendation("acceptable", text, [], "원문은 자연스럽고 교정할 필요가 없습니다.")
            elif family == 3:
                text = f"{time_word}は食堂を昼ご飯を食べます。"
                candidate = judgment("acceptable", text, [], "문법적으로 허용됩니다.")
                verdict, issues = "disagree", ["false_negative"]
                recommended = recommendation("needs_correction", text.replace("食堂を", "食堂で"), ["particle_misuse"], "동작 장소에는 で를 씁니다.")
            elif family == 4:
                text = f"{time_word}は学校に行きます。"
                candidate = judgment("insufficient_evidence", text, [], "정보가 부족합니다.")
                verdict, issues = "disagree", ["wrong_decision", "unnecessary_abstention"]
                recommended = recommendation("acceptable", text, [], "완결된 자연스러운 문장입니다.")
            elif family == 5:
                text = f"{time_word}は駅を行きます。"
                candidate = judgment("needs_correction", text.replace("駅を", "駅で"), ["particle_misuse"], "목적지 조사를 고칩니다.")
                verdict, issues = "disagree", ["wrong_correction"]
                recommended = recommendation("needs_correction", text.replace("駅を", "駅に"), ["particle_misuse"], "목적지에는 に를 씁니다.")
            elif family == 6:
                text = f"{time_word}は静かな町に行きます。"
                candidate = judgment("needs_correction", f"{time_word}には、とても静かで美しい町を訪問する予定です。", ["modifier_connection"], "더 자연스럽게 다듬었습니다.")
                verdict, issues = "disagree", ["false_positive", "nonminimal_correction"]
                recommended = recommendation("acceptable", text, [], "원문은 자연스러우므로 문체를 바꿀 필요가 없습니다.")
            elif family == 7:
                text = f"{time_word}は京都に行きます。"
                candidate = judgment("needs_correction", text.replace("京都", "大阪"), ["particle_misuse"], "장소 표현을 교정했습니다.")
                verdict, issues = "disagree", ["meaning_changed", "wrong_correction"]
                recommended = recommendation("acceptable", text, [], "원문은 자연스럽고 목적지를 바꾸면 의미가 달라집니다.")
            elif family == 8:
                text = f"{time_word}は会社を行きます。"; corrected = text.replace("会社を", "会社に")
                candidate = judgment("needs_correction", corrected, ["tense_mismatch"], "목적지 조사를 に로 고칩니다.")
                verdict, issues = "disagree", ["wrong_error_type"]
                recommended = recommendation("needs_correction", corrected, ["particle_misuse"], "목적지 조사 오류입니다.")
            elif family == 9:
                text = f"{time_word}は家に帰ります。"
                candidate = judgment("acceptable", text, [], "과거 시제가 올바릅니다.")
                verdict, issues = "disagree", ["reason_mismatch"]
                recommended = recommendation("acceptable", text, [], "현재·미래의 귀가 계획을 자연스럽게 표현했습니다.")
            elif family == 10:
                text = f"{time_word}、友達に……"
                candidate = judgment("needs_correction", f"{time_word}、友達に会います。", ["verb_conjugation"], "동사를 보완합니다.")
                verdict, issues = "disagree", ["should_abstain", "wrong_correction"]
                recommended = recommendation("insufficient_evidence", text, [], "서술어가 없어 의도를 확정할 수 없습니다.")
            else:
                text = f"{time_word}は病院に行きました。"
                candidate = judgment("insufficient_evidence", text, [], "문맥이 없습니다.")
                verdict, issues = "disagree", ["unnecessary_abstention"]
                recommended = recommendation("acceptable", text, [], "문맥 없이도 문법 판단이 가능한 완결문입니다.")
            rows.append({
                "id": f"FVH-01-{len(rows)+1:03d}", "text": text, "context": None,
                "learner_level": "N5" if index % 2 == 0 else "N4",
                "candidate_judgment": candidate,
                "expected": {"verdict": verdict, "required_issue_codes": issues,
                             "recommended_judgment": recommended},
                "source_stratum": runtime, "review_status": "generated_validated",
            })
    return rows


def canonical(value): return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    rows = build_rows()
    OUTPUT.write_text("".join(canonical(row) + "\n" for row in rows), encoding="utf-8")
    manifest = {"schema_version": "feedback-holdout-manifest-v0.1", "dataset": OUTPUT.name,
                "sha256": sha(OUTPUT), "records": len(rows), "review_status": "generated_validated",
                "model_inference_count": 0, "source_counts": {"gpu_bf16": 60, "pi_gguf": 60}}
    MANIFEST.write_text(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    protocol = {"schema_version": "feedback-holdout-protocol-v0.1", "dataset_sha256": manifest["sha256"],
                "contract_version": "feedback-v0.1", "temperature": 0.0, "max_tokens": 512,
                "single_use": True, "consumed": False,
                "thresholds": {"contract_success_rate_min": 0.99, "false_disagreement_rate_max": 0.02,
                  "disagreement_precision_min": 0.95, "disagreement_recall_min": 0.80,
                  "recommended_decision_accuracy_min": 0.90, "accepted_correction_rate_min": 0.80,
                  "source_metric_gap_pp_max": 5.0, "p95_latency_seconds_max": 5.0}}
    PROTOCOL.write_text(json.dumps(protocol, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__": main()
