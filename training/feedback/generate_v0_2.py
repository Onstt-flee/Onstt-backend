"""Generate diverse, paired feedback-v0.2 training data without v0.3 leakage."""

from __future__ import annotations

from collections import Counter
import hashlib
import json
from pathlib import Path

from analyzer.feedback_contract import SYSTEM_PROMPT, canonical_json, parse_output, validate_input
from evaluation.feedback.build_holdout_v0_2 import (
    alternative_error_type,
    append_before_terminal,
    gold_judgment,
    input_fingerprint,
    judgment,
)


ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
DATA = HERE / "data"
SOURCE = ROOT / "training/judgment/data/pilot_v0.2_d.jsonl"
HOLDOUT = ROOT / "evaluation/feedback/holdout_v0.3.jsonl"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def feedback(verdict, issues, recommended, reason):
    return {
        "verdict": verdict,
        "issue_codes": issues,
        "recommended_judgment": recommended,
        "review_reason_ko": reason,
    }


def is_stt_orthography(row):
    tags = " ".join(row.get("tags", [])).lower()
    context = row["input"].get("context") or ""
    return "stt_orthography" in tags and ("원음" in context or "STT" in context)


def orthography_candidate(text):
    changed = text.replace("わ", "は", 1) if "わ" in text else text.replace("お", "を", 1)
    if changed == text:
        raise ValueError(f"no orthographic particle surface found: {text}")
    return judgment("needs_correction", changed, ["particle_misuse"], "조사 표기를 교정했습니다.")


def paired_cases(source_row, source_index):
    text = source_row["input"]["text"]
    gold = gold_judgment(source_row)
    cases = [(
        gold,
        feedback("agree", [], None, "판단, 교정문과 근거가 모두 타당합니다."),
        "agree_anchor",
    )]
    if gold["decision"] == "acceptable":
        if is_stt_orthography(source_row):
            cases.append((
                orthography_candidate(text),
                feedback("unreviewable", [], None, "원음이 없어 발화 오류와 STT 표기 오류를 구분할 수 없습니다."),
                "audio_required_unreviewable",
            ))
        elif source_index % 3 == 0:
            candidate = judgment("needs_correction", append_before_terminal(text), ["modifier_connection"], "더 자연스럽게 고쳤습니다.")
            cases.append((candidate, feedback("disagree", ["false_positive", "nonminimal_correction"], gold, "허용되는 원문을 불필요하게 바꾸었습니다."), "false_positive"))
        elif source_index % 3 == 1:
            candidate = judgment("insufficient_evidence", text, [], "문맥이 없어 판단할 수 없습니다.")
            cases.append((candidate, feedback("disagree", ["wrong_decision", "unnecessary_abstention"], gold, "제공 정보만으로 판단 가능한 문장을 불필요하게 보류했습니다."), "unnecessary_abstention"))
        else:
            candidate = judgment("acceptable", text, [], "과거 시제 오류를 교정했습니다.")
            cases.append((candidate, feedback("disagree", ["reason_mismatch"], gold, "판단과 근거 설명이 일치하지 않습니다."), "reason_mismatch"))
    elif gold["decision"] == "needs_correction":
        mode = source_index % 3
        if mode == 0:
            candidate = judgment("acceptable", text, [], "문법적으로 허용됩니다.")
            cases.append((candidate, feedback("disagree", ["false_negative"], gold, "명확한 오류를 놓쳤습니다."), "false_negative"))
        elif mode == 1:
            candidate = judgment("needs_correction", gold["corrected_text"], [alternative_error_type(gold["error_types"])], "다른 오류 유형으로 분류했습니다.")
            cases.append((candidate, feedback("disagree", ["wrong_error_type"], gold, "교정문은 맞지만 오류 유형이 틀렸습니다."), "wrong_error_type"))
        else:
            candidate = judgment("needs_correction", append_before_terminal(gold["corrected_text"]), gold["error_types"], "더 자연스럽게 다듬었습니다.")
            cases.append((candidate, feedback("disagree", ["wrong_correction", "nonminimal_correction"], gold, "필수 교정 외의 표현을 추가했습니다."), "wrong_correction"))
    else:
        candidate = judgment("acceptable", text, [], "문법적으로 허용되는 완결문입니다.")
        cases.append((candidate, feedback("disagree", ["wrong_decision", "should_abstain"], gold, "누락 정보를 추측하지 말고 보류해야 합니다."), "should_abstain"))
        invented = judgment("needs_correction", append_before_terminal(text, "です"), ["copula_conjugation"], "누락된 종결을 보완했습니다.")
        cases.append((invented, feedback("disagree", ["should_abstain", "wrong_correction"], gold, "근거 없이 누락 내용을 생성했습니다."), "invented_correction"))
    return cases


def build_rows():
    source_rows = [json.loads(line) for line in SOURCE.read_text(encoding="utf-8").splitlines() if line]
    holdout_texts = {
        json.loads(line)["text"]
        for line in HOLDOUT.read_text(encoding="utf-8").splitlines() if line
    }
    rows = []
    for source_index, source_row in enumerate(source_rows):
        if source_row["input"]["text"] in holdout_texts:
            continue
        for candidate, expected, case_type in paired_cases(source_row, source_index):
            row = {
                "id": f"FVT-02-{len(rows) + 1:04d}",
                "source_judgment_id": source_row["id"],
                "source_index": source_index,
                "split_group": "eval" if source_index % 10 == 0 else "train",
                "text": source_row["input"]["text"],
                "context": source_row["input"]["context"],
                "learner_level": source_row["input"]["learner_level"],
                "candidate_judgment": candidate,
                "expected": expected,
                "case_type": case_type,
                "review": {"status": "generated_validated", "reviewed_at": None},
            }
            model_input = {"text": row["text"], "context": row["context"], "learner_level": row["learner_level"], "judgment": candidate}
            validate_input(model_input)
            parsed, error = parse_output(canonical_json(expected), row["text"])
            if parsed is None:
                raise ValueError(f"invalid output for {row['id']}: {error}")
            rows.append(row)
    return rows


def main():
    DATA.mkdir(parents=True, exist_ok=True)
    rows = build_rows()
    source_path = DATA / "feedback_v0.2.jsonl"
    source_path.write_text("".join(canonical_json(row) + "\n" for row in rows), encoding="utf-8")
    splits = {"train": [], "eval": []}
    for row in rows:
        model_input = {"text": row["text"], "context": row["context"], "learner_level": row["learner_level"], "judgment": row["candidate_judgment"]}
        chat = {"messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": canonical_json(model_input)},
            {"role": "assistant", "content": canonical_json(row["expected"])},
        ]}
        splits[row["split_group"]].append(chat)
    train_path = DATA / "train_v0.2.chatml.jsonl"
    eval_path = DATA / "eval_v0.2.chatml.jsonl"
    train_path.write_text("".join(canonical_json(row) + "\n" for row in splits["train"]), encoding="utf-8")
    eval_path.write_text("".join(canonical_json(row) + "\n" for row in splits["eval"]), encoding="utf-8")
    holdout = [json.loads(line) for line in HOLDOUT.read_text(encoding="utf-8").splitlines() if line]
    current = {input_fingerprint(row) for row in rows}
    manifest = {
        "schema_version": "feedback-training-manifest-v0.2",
        "records": len(rows), "train_records": len(splits["train"]), "eval_records": len(splits["eval"]),
        "source_judgment_dataset": str(SOURCE.relative_to(ROOT)), "source_judgment_sha256": sha(SOURCE),
        "source_judgment_records_used": len({row["source_judgment_id"] for row in rows}),
        "source_judgment_records_excluded_for_holdout_text_overlap": 1,
        "review_status": "generated_validated", "holdout_used": False,
        "holdout_v0.3_exact_input_overlap": len(current & {input_fingerprint(row) for row in holdout}),
        "verdict_counts": dict(sorted(Counter(row["expected"]["verdict"] for row in rows).items())),
        "case_type_counts": dict(sorted(Counter(row["case_type"] for row in rows).items())),
        "source_sha256": sha(source_path), "train_sha256": sha(train_path), "eval_sha256": sha(eval_path),
    }
    (DATA / "feedback_v0.2.manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
