"""Build and seal the GPU-only feedback-v0.4 internal holdout.

The texts are deterministic templates authored for this holdout.  They are not
human/expert reviewed and must not be used to claim production quality.
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
OUTPUT = HERE / "holdout_v0.4.jsonl"
MANIFEST = HERE / "holdout_v0.4.manifest.json"
PROTOCOL = HERE / "holdout_v0.4.protocol.json"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def feedback(verdict, issues, recommended, reason):
    return {
        "verdict": verdict,
        "issue_codes": issues,
        "recommended_judgment": recommended,
        "review_reason_ko": reason,
    }


def _acceptable_sources():
    subjects = ["祖父", "姉", "店員", "先生", "隣人", "叔母", "学生", "駅員", "父", "母"]
    objects = ["雑誌", "手紙", "資料", "地図", "新聞", "小説", "案内", "日記", "予定表", "報告書"]
    rows = [
        (f"{subject}は毎晩{obj}を読みます。", None, "ordinary_japanese_ok")
        for subject, obj in zip(subjects, objects)
    ]
    routes = ["川沿い", "商店街", "海辺", "林道", "歩道橋", "校庭", "遊歩道", "参道", "地下道", "砂浜"]
    rows += [(f"休日は{route}をゆっくり歩きます。", None, "route_wo_ok") for route in routes]
    places = ["資料室", "展示室", "倉庫", "受付", "研究室", "玄関", "待合室", "売店", "廊下", "事務室"]
    things = ["古い地図", "木の棚", "案内板", "小さな机", "観葉植物", "傘立て", "長い椅子", "冷蔵庫", "消火器", "複写機"]
    rows += [(f"{place}に{thing}があります。", None, "existence_ni_ok") for place, thing in zip(places, things)]
    adjectives = ["暖かかった", "静かでした", "広くありません", "便利でした", "難しくなかった", "にぎやかでした", "新しかった", "安全でした", "遠くありません", "複雑ではありません"]
    nouns = ["会場", "旅館", "図書室", "道順", "課題", "市場", "設備", "入口", "駅", "手続き"]
    rows += [(f"その{noun}は{adjective}。", None, "predicate_form_ok") for noun, adjective in zip(nouns, adjectives)]
    orthography = [
        "わたしわ夕方に帰ります。", "ぼくわ図書館へ行きます。", "本お二冊借りました。",
        "水お少し飲みました。", "妹わ来週来ます。", "父わ駅で待っています。",
        "書類お棚に置きました。", "手紙お昨日送りました。", "友達わ京都に住んでいます。",
        "薬お朝飲みました。",
    ]
    rows += [(text, "STT 전사이며 원음은 제공되지 않았습니다.", "stt_orthography_boundary") for text in orthography]
    return rows


def _correction_sources():
    destinations = ["診療所", "美術館", "市役所", "体育館", "郵便局", "水族館", "交番", "展望台", "空港", "公民館"]
    rows = [(f"明日は{place}を行きます。", f"明日は{place}に行きます。", "particle_misuse", "destination_particle_error") for place in destinations]
    places = ["物置", "会議室", "車庫", "庭先", "食器棚", "教室", "台所", "休憩室", "受付", "廊下"]
    things = ["工具箱", "時計", "自転車", "植木鉢", "皿", "黒板", "電子レンジ", "給水機", "番号札", "非常口"]
    rows += [(f"{place}で{thing}があります。", f"{place}に{thing}があります。", "particle_misuse", "existence_de_error") for place, thing in zip(places, things)]
    verbs = [("書くます", "書きます"), ("泳ぐます", "泳ぎます"), ("話すます", "話します"), ("待つます", "待ちます"), ("遊ぶます", "遊びます"), ("読むました", "読みました"), ("買うました", "買いました"), ("急ぐました", "急ぎました"), ("立つました", "立ちました"), ("休むました", "休みました")]
    rows += [(f"毎日ここで{bad}。", f"毎日ここで{good}。", "verb_conjugation", "verb_conjugation_error") for bad, good in verbs]
    adjectives = [("暑いかった", "暑かった"), ("長いかった", "長かった"), ("安いくない", "安くない"), ("狭いくない", "狭くない"), ("早いかった", "早かった"), ("重いくない", "重くない"), ("楽しいかった", "楽しかった"), ("忙しいくない", "忙しくない"), ("近いかった", "近かった"), ("明るいくない", "明るくない")]
    rows += [(f"昨日は{bad}です。", f"昨日は{good}です。", "adjective_conjugation", "adjective_conjugation_error") for bad, good in adjectives]
    modifiers = [("親切人", "親切な人"), ("便利店", "便利な店"), ("静か場所", "静かな場所"), ("有名作家", "有名な作家"), ("丈夫鞄", "丈夫な鞄"), ("きれい景色", "きれいな景色"), ("簡単問題", "簡単な問題"), ("安全道", "安全な道"), ("大切資料", "大切な資料"), ("丁寧説明", "丁寧な説明")]
    rows += [(f"これは{bad}です。", f"これは{good}です。", "modifier_connection", "modifier_connection_error") for bad, good in modifiers]
    return rows


def _insufficient_sources():
    rows = [(text, "incomplete_utterance") for text in [
        "もし明日早く終わったら", "駅に着いたとき", "この資料を読んだのは", "先生に相談したあとで", "雨がやんだので",
        "昨日、受付で係の人に", "次回の研修について", "私は朝から図書室で", "新しい申込書を", "昼休みに同僚と",
    ]]
    rows += [(text, "missing_or_noise_span") for text in [
        "明後日は［聞き取れない］へ出発します。", "今日は［雑音］かったです。", "受付に［聞き取れない］があります。", "［雑音のみ］", "このあと［音声欠落］",
    ]]
    rows += [(text, "foreign_language_boundary") for text in [
        "I will visit the museum tomorrow.", "Please leave the parcel by the window.", "내일은 도서관에 갑니다.", "오늘 회의는 세 시에 시작합니다.", "Je vais à la gare demain.",
    ]]
    return rows


def build_rows():
    rows = []
    acceptable = _acceptable_sources()
    for index, (text, context, family) in enumerate(acceptable):
        gold = judgment("acceptable", text, [], "제공된 범위에서 문법적으로 허용됩니다.")
        if family == "stt_orthography_boundary":
            changed = text.replace("わ", "は", 1) if "わ" in text else text.replace("お", "を", 1)
            candidate = judgment("needs_correction", changed, ["particle_misuse"], "조사 표기를 바로잡았습니다.")
            expected = feedback("unreviewable", [], None, "원음이 없어 발화 오류와 STT 전사 오류를 구분할 수 없습니다.")
            case_type = "audio_required_unreviewable"
        elif index < 15:
            candidate, expected, case_type = gold, feedback("agree", [], None, "허용되는 일본어를 그대로 인정한 판단입니다."), "agree_valid_japanese"
        elif index < 25:
            candidate = judgment("needs_correction", text[:-1] + "ね。", ["modifier_connection"], "더 자연스럽게 고쳤습니다.")
            expected = feedback("disagree", ["false_positive", "nonminimal_correction"], gold, "문법상 허용되는 원문을 불필요하게 바꾸었습니다.")
            case_type = "false_positive"
        elif index < 35:
            candidate = judgment("insufficient_evidence", text, [], "일본어인지 판단할 수 없습니다.")
            expected = feedback("disagree", ["wrong_decision", "unnecessary_abstention"], gold, "완결된 일본어 문장이므로 판단을 보류할 이유가 없습니다.")
            case_type = "valid_japanese_not_foreign"
        else:
            candidate = judgment("acceptable", text, [], "조사 오류를 교정했습니다.")
            expected = feedback("disagree", ["reason_mismatch"], gold, "허용 판단과 오류를 교정했다는 근거가 일치하지 않습니다.")
            case_type = "reason_mismatch"
        rows.append((text, context, family, candidate, expected, case_type))

    for index, (text, corrected, error_type, family) in enumerate(_correction_sources()):
        gold = judgment("needs_correction", corrected, [error_type], "문법 오류를 최소 범위로 교정해야 합니다.")
        if index < 15:
            candidate, expected, case_type = gold, feedback("agree", [], None, "오류 판단과 최소 교정이 타당합니다."), "agree_correction"
        elif index < 30:
            candidate = judgment("acceptable", text, [], "문법적으로 허용됩니다.")
            expected = feedback("disagree", ["false_negative"], gold, "명확한 문법 오류를 놓쳤습니다.")
            case_type = "false_negative"
        elif index < 40:
            candidate = judgment("needs_correction", corrected[:-1] + "ね。", [error_type], "자연스럽게 다듬었습니다.")
            expected = feedback("disagree", ["wrong_correction", "nonminimal_correction"], gold, "필수 교정 외의 표현을 추가했습니다.")
            case_type = "wrong_correction"
        else:
            alternative = "tense_mismatch" if error_type != "tense_mismatch" else "particle_misuse"
            candidate = judgment("needs_correction", corrected, [alternative], "다른 오류 유형으로 분류했습니다.")
            expected = feedback("disagree", ["wrong_error_type"], gold, "교정문은 맞지만 오류 유형이 일치하지 않습니다.")
            case_type = "wrong_error_type"
        rows.append((text, None, family, candidate, expected, case_type))

    for index, (text, family) in enumerate(_insufficient_sources()):
        gold = judgment("insufficient_evidence", text, [], "정보가 부족해 교정 내용을 확정할 수 없습니다.")
        if index < 10:
            candidate, expected, case_type = gold, feedback("agree", [], None, "누락 정보를 추측하지 않고 보류한 판단입니다."), "agree_abstention"
        elif index < 15:
            candidate = judgment("acceptable", text, [], "문법적으로 허용됩니다.")
            expected = feedback("disagree", ["wrong_decision", "should_abstain"], gold, "누락되거나 식별되지 않은 내용을 근거 없이 허용했습니다.")
            case_type = "should_abstain"
        else:
            candidate = judgment("needs_correction", text + "です。", ["copula_conjugation"], "일본어 문장으로 보완했습니다.")
            expected = feedback("disagree", ["should_abstain", "wrong_correction"], gold, "외국어 또는 누락 입력을 임의의 일본어로 교정할 수 없습니다.")
            case_type = "foreign_language_not_correction"
        rows.append((text, None, family, candidate, expected, case_type))

    result = []
    for index, (text, context, family, candidate, expected, case_type) in enumerate(rows, 1):
        row = {
            "id": f"FVH-04-{index:03d}", "text": text, "context": context,
            "learner_level": "N5" if index % 3 else "N4",
            "candidate_judgment": candidate, "expected": expected,
            "family": family, "case_type": case_type,
            "source_kind": "deterministic_feedback_v0.4_template",
            "review_status": "generated_validated",
        }
        validate_input({"text": text, "context": context, "learner_level": row["learner_level"], "judgment": candidate})
        parsed, error = parse_output(canonical_json(expected), text)
        if parsed is None:
            raise ValueError(f"invalid expected output for {row['id']}: {error}")
        result.append(row)
    return result


def _load(path: Path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def main():
    existing_protocol = None
    if PROTOCOL.exists():
        existing_protocol = json.loads(PROTOCOL.read_text(encoding="utf-8"))
        if existing_protocol.get("single_use") and existing_protocol.get("consumed"):
            raise SystemExit("refusing to regenerate consumed feedback holdout v0.4")
    rows = build_rows()
    OUTPUT.write_text("".join(canonical_json(row) + "\n" for row in rows), encoding="utf-8")
    current = {input_fingerprint(row) for row in rows}
    current_texts = {row["text"] for row in rows}
    comparisons = {
        "feedback_training_v0.1": ROOT / "training/feedback/data/feedback_v0.1.jsonl",
        "feedback_training_v0.2": ROOT / "training/feedback/data/feedback_v0.2.jsonl",
        "feedback_holdout_v0.1": HERE / "holdout_v0.1.jsonl",
        "feedback_holdout_v0.2": HERE / "holdout_v0.2.jsonl",
        "feedback_holdout_v0.3": HERE / "holdout_v0.3.jsonl",
    }
    loaded = {name: _load(path) for name, path in comparisons.items()}
    overlap = {name: len(current & {input_fingerprint(row) for row in values}) for name, values in loaded.items()}
    text_overlap = {name: len(current_texts & {row["text"] for row in values}) for name, values in loaded.items()}
    manifest = {
        "schema_version": "feedback-holdout-manifest-v0.4", "dataset": OUTPUT.name,
        "sha256": sha(OUTPUT), "records": len(rows), "review_status": "generated_validated",
        "human_reviewed": False, "expert_reviewed": False, "model_inference_count": 0,
        "qualification_scope": "gpu_internal_model_selection_only",
        "verdict_counts": dict(sorted(Counter(row["expected"]["verdict"] for row in rows).items())),
        "case_type_counts": dict(sorted(Counter(row["case_type"] for row in rows).items())),
        "family_counts": dict(sorted(Counter(row["family"] for row in rows).items())),
        "exact_input_overlap": overlap,
        "text_overlap": text_overlap,
        "limitations": [
            "자동 생성·계약 검증 데이터이며 사람 또는 일본어 전문가 검수 데이터가 아닙니다.",
            "GPU 전용 내부 후보 비교용이며 운영 품질이나 실제 학습자 품질을 증명하지 않습니다.",
            "Pi 런타임 격차 평가는 이번 시험 범위에서 제외했습니다.",
        ],
    }
    MANIFEST.write_text(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    preserve_binding = existing_protocol if existing_protocol and existing_protocol.get("dataset_sha256") == manifest["sha256"] else {}
    protocol = {
        "schema_version": "feedback-holdout-protocol-v0.4", "dataset_sha256": manifest["sha256"],
        "contract_version": "feedback-v0.1", "candidate_family": "feedback-v0.3",
        "adapter_sha256": preserve_binding.get("adapter_sha256"),
        "training_data_sha256": preserve_binding.get("training_data_sha256"),
        "training_config_sha256": preserve_binding.get("training_config_sha256"),
        "training_run": preserve_binding.get("training_run"),
        "ready_for_inference": preserve_binding.get("ready_for_inference", False),
        "single_use": True, "consumed": False,
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
