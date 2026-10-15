"""Build feedback-v0.3 data with targeted valid-Japanese boundary anchors."""

from __future__ import annotations

from collections import Counter
import hashlib
import json
from pathlib import Path

from analyzer.feedback_contract import SYSTEM_PROMPT, canonical_json, parse_output, validate_input
from evaluation.feedback.build_holdout_v0_2 import input_fingerprint, judgment


ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
DATA = HERE / "data"
BASE = DATA / "feedback_v0.2.jsonl"
HOLDOUT = ROOT / "evaluation/feedback/holdout_v0.4.jsonl"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def feedback(verdict, issues, recommended, reason):
    return {
        "verdict": verdict,
        "issue_codes": issues,
        "recommended_judgment": recommended,
        "review_reason_ko": reason,
    }


def _valid_japanese_texts():
    subjects = ["兄", "妹", "祖母", "部長", "医師", "職員", "友人", "先輩", "後輩", "管理人"]
    objects = ["申込書", "時刻表", "料理本", "契約書", "処方箋", "名簿", "写真集", "議事録", "教科書", "掲示物"]
    rows = [(f"{subject}は昼休みに{obj}を確認します。", "ordinary_japanese_ok") for subject, obj in zip(subjects, objects)]
    routes = ["堤防", "並木道", "農道", "横断歩道", "橋", "坂道", "通路", "石段", "河原", "公園の外周"]
    rows += [(f"朝は{route}をゆっくり走りました。", "route_wo_ok") for route in routes]
    places = ["書庫", "講堂", "調理室", "医務室", "機械室", "改札口", "屋上", "地下室", "相談室", "作業室"]
    things = ["脚立", "演台", "大型の鍋", "救急箱", "制御盤", "券売機", "給水タンク", "古い箱", "丸い机", "工具棚"]
    rows += [(f"{place}に{thing}があります。", "existence_ni_ok") for place, thing in zip(places, things)]
    nouns = ["説明", "温泉", "坂", "会議", "箱", "庭", "講義", "操作", "連絡", "予約方法"]
    predicates = ["丁寧でした", "熱くなかったです", "急ではありません", "長くありませんでした", "丈夫でした", "静かでした", "難しくなかったです", "簡単でした", "遅くありません", "複雑ではありません"]
    rows += [(f"その{noun}は{predicate}。", "predicate_form_ok") for noun, predicate in zip(nouns, predicates)]
    colloquial = [
        "もう昼ご飯、食べた？", "この電車、次で降りるよ。", "ちょっと窓を開けてもいい？", "あとで連絡するね。", "今日は先に帰る。",
        "その本、まだ読んでる？", "ここ、座っても大丈夫？", "明日なら時間あるよ。", "荷物、そこに置いて。", "駅まで一緒に歩こう。",
    ]
    rows += [(text, "short_colloquial_ok") for text in colloquial]
    contexts = [
        "質問：どこで待ちますか。 回答：受付です。", "質問：宿題は終わりましたか。 回答：まだです。",
        "質問：参加しますか。 回答：はい、参加します。", "質問：何個必要ですか。 回答：二つです。",
        "質問：誰が作りましたか。 回答：母です。", "質問：何時に来ますか。 回答：九時です。",
        "質問：飲み物は要りますか。 回答：水をお願いします。", "質問：京都へ行きますか。 回答：来週行きます。",
        "質問：この席は空いていますか。 回答：はい、空いています。", "質問：駅は近いですか。 回答：歩いて五分です。",
    ]
    rows += [(text, "contextual_short_answer_ok") for text in contexts]
    return rows


def _insufficient_texts():
    return [(text, family) for text, family in [
        ("もし会議が予定より長引いたら", "incomplete_condition"), ("駅前の店で友達と", "incomplete_predicate"),
        ("この申込書を書いたのは", "incomplete_clause"), ("来週の出張について", "incomplete_topic"),
        ("荷物を受付の人に", "incomplete_predicate"), ("雨が強くなってきたので", "incomplete_reason"),
        ("［聞き取れない］に置きました。", "missing_audio_span"), ("今朝は［雑音］かったです。", "missing_audio_span"),
        ("［音声なし］", "no_proposition"), ("あの、ええと……", "filler_only"),
        ("We met near the library.", "foreign_language"), ("Please open the window.", "foreign_language"),
        ("오늘은 버스로 회사에 갑니다.", "foreign_language"), ("내일 다시 전화하겠습니다.", "foreign_language"),
        ("Voy a la estación mañana.", "foreign_language"), ("Je voudrais un café.", "foreign_language"),
        ("明日は［音声欠落］へ", "missing_audio_span"), ("このあと先生に……", "incomplete_predicate"),
        ("昼休みが終わったあと", "incomplete_clause"), ("［大きな雑音］", "no_proposition"),
    ]]


def _correction_texts():
    destinations = ["動物園", "保健室", "展覧会", "税務署"]
    rows = [(f"午後は{place}を行きます。", f"午後は{place}に行きます。", "particle_misuse", "destination_particle") for place in destinations]
    rows += [
        ("工房で大きな機械があります。", "工房に大きな機械があります。", "particle_misuse", "existence_particle"),
        ("応接室で長いソファがあります。", "応接室に長いソファがあります。", "particle_misuse", "existence_particle"),
        ("倉庫で予備の椅子があります。", "倉庫に予備の椅子があります。", "particle_misuse", "existence_particle"),
        ("門の横で案内所があります。", "門の横に案内所があります。", "particle_misuse", "existence_particle"),
        ("毎朝ここで働くます。", "毎朝ここで働きます。", "verb_conjugation", "verb_conjugation"),
        ("昨日は長く歩くました。", "昨日は長く歩きました。", "verb_conjugation", "verb_conjugation"),
        ("毎週この店で買うます。", "毎週この店で買います。", "verb_conjugation", "verb_conjugation"),
        ("先ほど担当者と話すました。", "先ほど担当者と話しました。", "verb_conjugation", "verb_conjugation"),
        ("昨日の風は強いかったです。", "昨日の風は強かったです。", "adjective_conjugation", "adjective_conjugation"),
        ("この箱は軽いくないです。", "この箱は軽くないです。", "adjective_conjugation", "adjective_conjugation"),
        ("先週の試験は易しいかったです。", "先週の試験は易しかったです。", "adjective_conjugation", "adjective_conjugation"),
        ("この道は短いくないです。", "この道は短くないです。", "adjective_conjugation", "adjective_conjugation"),
        ("これは複雑手続きです。", "これは複雑な手続きです。", "modifier_connection", "modifier_connection"),
        ("あれは立派建物です。", "あれは立派な建物です。", "modifier_connection", "modifier_connection"),
        ("ここは安全場所です。", "ここは安全な場所です。", "modifier_connection", "modifier_connection"),
        ("彼は真面目学生です。", "彼は真面目な学生です。", "modifier_connection", "modifier_connection"),
    ]
    return rows


def targeted_rows():
    groups = []
    for text, family in _valid_japanese_texts():
        gold = judgment("acceptable", text, [], "제공된 범위에서 문법적으로 허용됩니다.")
        groups.append((text, None, family, [
            (gold, feedback("agree", [], None, "완결된 일본어 문장을 올바르게 허용했습니다."), "valid_japanese_agree"),
            (judgment("insufficient_evidence", text, [], "일본어가 아닌 입력이라 판단할 수 없습니다."), feedback("disagree", ["wrong_decision", "unnecessary_abstention"], gold, "일본어가 아닌 입력이 아니라 문법 판단이 가능한 완결문입니다."), "valid_japanese_not_foreign"),
        ]))
    for text, family in _insufficient_texts():
        gold = judgment("insufficient_evidence", text, [], "누락되거나 다른 언어인 입력이라 교정을 확정할 수 없습니다.")
        groups.append((text, None, family, [
            (gold, feedback("agree", [], None, "근거가 부족한 입력을 추측하지 않고 보류했습니다."), "boundary_abstention_agree"),
            (judgment("acceptable", text, [], "문법적으로 허용되는 일본어입니다."), feedback("disagree", ["wrong_decision", "should_abstain"], gold, "완결된 일본어로 볼 근거가 없어 판단을 보류해야 합니다."), "boundary_should_abstain"),
        ]))
    for text, corrected, error_type, family in _correction_texts():
        gold = judgment("needs_correction", corrected, [error_type], "문법 오류를 최소 범위로 교정해야 합니다.")
        groups.append((text, None, family, [
            (gold, feedback("agree", [], None, "오류 판단과 최소 교정이 타당합니다."), "correction_agree"),
            (judgment("acceptable", text, [], "문법적으로 허용됩니다."), feedback("disagree", ["false_negative"], gold, "명확한 문법 오류를 놓쳤습니다."), "correction_false_negative"),
        ]))

    rows = []
    for group_index, (text, context, family, cases) in enumerate(groups):
        split = "eval" if group_index % 10 == 0 else "train"
        for candidate, expected, case_type in cases:
            row = {
                "id": f"FVT-03-{len(rows) + 1:04d}", "source_judgment_id": f"target-v03-{group_index + 1:03d}",
                "source_index": group_index, "split_group": split, "text": text, "context": context,
                "learner_level": "N4" if group_index % 4 == 0 else "N5",
                "candidate_judgment": candidate, "expected": expected,
                "case_type": case_type, "target_family": family,
                "review": {"status": "generated_validated", "reviewed_at": None},
            }
            validate_input({"text": text, "context": context, "learner_level": row["learner_level"], "judgment": candidate})
            parsed, error = parse_output(canonical_json(expected), text)
            if parsed is None:
                raise ValueError(f"invalid output for {row['id']}: {error}")
            rows.append(row)
    return rows


def build_rows():
    base = [json.loads(line) for line in BASE.read_text(encoding="utf-8").splitlines() if line]
    return base + targeted_rows()


def _load(path: Path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def main():
    rows = build_rows()
    holdout = _load(HOLDOUT)
    holdout_inputs = {input_fingerprint(row) for row in holdout}
    holdout_texts = {row["text"] for row in holdout}
    current_inputs = {input_fingerprint(row) for row in rows}
    current_texts = {row["text"] for row in rows}
    if current_inputs & holdout_inputs or current_texts & holdout_texts:
        raise ValueError("feedback-v0.3 training data overlaps sealed holdout v0.4")

    source_path = DATA / "feedback_v0.3.jsonl"
    source_path.write_text("".join(canonical_json(row) + "\n" for row in rows), encoding="utf-8")
    splits = {"train": [], "eval": []}
    for row in rows:
        model_input = {"text": row["text"], "context": row["context"], "learner_level": row["learner_level"], "judgment": row["candidate_judgment"]}
        splits[row["split_group"]].append({"messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": canonical_json(model_input)},
            {"role": "assistant", "content": canonical_json(row["expected"])},
        ]})
    train_path = DATA / "train_v0.3.chatml.jsonl"
    eval_path = DATA / "eval_v0.3.chatml.jsonl"
    train_path.write_text("".join(canonical_json(row) + "\n" for row in splits["train"]), encoding="utf-8")
    eval_path.write_text("".join(canonical_json(row) + "\n" for row in splits["eval"]), encoding="utf-8")
    manifest = {
        "schema_version": "feedback-training-manifest-v0.3", "records": len(rows),
        "train_records": len(splits["train"]), "eval_records": len(splits["eval"]),
        "base_dataset": str(BASE.relative_to(ROOT)), "base_dataset_sha256": sha(BASE),
        "targeted_records": len(targeted_rows()), "review_status": "generated_validated",
        "holdout_used": False, "holdout_v0.4_sha256": sha(HOLDOUT),
        "holdout_v0.4_exact_input_overlap": len(current_inputs & holdout_inputs),
        "holdout_v0.4_text_overlap": len(current_texts & holdout_texts),
        "verdict_counts": dict(sorted(Counter(row["expected"]["verdict"] for row in rows).items())),
        "case_type_counts": dict(sorted(Counter(row["case_type"] for row in rows).items())),
        "source_sha256": sha(source_path), "train_sha256": sha(train_path), "eval_sha256": sha(eval_path),
        "limitations": [
            "자동 생성·계약 검증 데이터이며 사람 또는 일본어 전문가 검수 데이터가 아닙니다.",
            "feedback-v0.2 실패 유형을 일반화한 새 문장으로 보강했으며 소비된 holdout 문장을 재사용하지 않았습니다.",
        ],
    }
    (DATA / "feedback_v0.3.manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
