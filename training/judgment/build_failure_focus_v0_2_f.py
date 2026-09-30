"""Build v0.2-F data after the consumed v0.2 holdout safety failure.

All holdouts are read only for deterministic contamination checks. Their
labels and model outputs are not used to construct training examples.
"""

from __future__ import annotations

from collections import Counter, defaultdict
import json
from pathlib import Path

from training.judgment.build_hard_negatives import Builder, _write_jsonl
from training.judgment.build_failure_focus_v0_2_d import (
    _apply, _edits, _fingerprint, _sha256, _trigrams,
)
from training.judgment.data import load_records, summary, validate_records
from training.judgment.export_chatml import export


ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT / "training/judgment/data"
BASE = DATA_DIR / "pilot_v0.2_e.jsonl"
ADDITION = DATA_DIR / "failure_focus_v0.2_f.jsonl"
COMBINED = DATA_DIR / "pilot_v0.2_f.jsonl"
CHATML = DATA_DIR / "failure_focus_v0.2_f_chatml"
MANIFEST = DATA_DIR / "failure_focus_v0.2_f.manifest.json"
AUDIT_DATASETS = (
    ROOT / "evaluation/judgment/seed_v0.1.jsonl",
    ROOT / "evaluation/judgment/holdout_v0.1.jsonl",
    ROOT / "evaluation/judgment/holdout_v0.2.jsonl",
    ROOT / "evaluation/judgment/holdout_v0.3.jsonl",
    BASE,
)
VERSION = "failure-focus-v0.2-f"
VALIDATED_AT = "2026-09-30"
NEAR_THRESHOLD = 0.85


def build_generated() -> list[dict]:
    builder = Builder(start=829)

    def add(family: str, index: int, text: str, decision: str, *, reason: str,
            context: str | None = None,
            changes: list[tuple[str, str, str]] | None = None,
            pair: str | None = None, dev: bool = False):
        edits = _edits(text, changes) if changes else []
        row = builder.add(
            family=f"v02f_{family}_{'dev' if dev else 'train'}",
            split="pilot_dev" if dev else "pilot_train",
            text=text, context=context, decision=decision, reason=reason,
            corrected_text=_apply(text, edits) if edits else None,
            error_type=edits[0]["error_type"] if edits else None,
            pair_id=pair, source_anchor_id=None,
        )
        if edits:
            row["expected"]["edits"] = edits
            for error_type in dict.fromkeys(edit["error_type"] for edit in edits):
                if error_type not in row["tags"]:
                    row["tags"].append(error_type)
        return row

    plain_style_ok = [
        "今夜は少し早めに休む。", "明日は妹と買い物に行くよ。",
        "昨日は駅前の店で昼ご飯を食べた。", "この荷物はあとで片づけるね。",
        "来週から朝の電車を一本早くする。", "さっき先生にメールを送ったよ。",
        "今日は家で静かに本を読む。", "その話は昨日初めて聞いた。",
        "夕方になったら犬と散歩するよ。", "週末は祖母の家に泊まる。",
        "今朝は目覚ましより先に起きた。", "会議が終わったらすぐ戻るね。",
        "次の休みは部屋をきれいにする。", "昨日の夜は音楽を聞いて過ごした。",
        "今日は自転車で会社まで行くよ。", "帰ったら写真をみんなに見せるね。",
    ]
    for index, text in enumerate(plain_style_ok):
        add("plain_tense_ok", index, text, "acceptable",
            context="친한 사람과의 일상 대화", dev=index in {3, 7, 11, 15},
            reason="문맥에 맞는 보통체와 시제를 그대로 유지합니다.")

    route_wo_ok = [
        "朝の市場をゆっくり歩きました。", "子どもたちは広い運動場を走りました。",
        "列車は長いトンネルを通りました。", "観光船が古い水門をくぐりました。",
        "帰りに桜並木を散歩しました。", "登山客は岩場の細い道を進みました。",
        "毎朝、犬と堤防を歩いています。", "バスは海沿いの道路を走ります。",
        "選手は競技場を二周走りました。", "私たちは竹林の小径を抜けました。",
        "自転車で湖畔の道を一周しました。", "夕方、商店街をぶらぶら歩きました。",
        "鳥が低い門をくぐって庭に入りました。", "救急車が交差点を通過しました。",
        "旅人は山あいの旧街道を歩きました。", "船は島の間の海峡を進みました。",
    ]
    for index, text in enumerate(route_wo_ok):
        add("route_wo_ok", index, text, "acceptable", dev=index in {3, 7, 11, 15},
            reason="이동 경로나 통과 공간에 쓰인 を는 올바르므로 유지합니다.")

    adjective_pairs = [
        ("昨日の夕焼けは赤かったです。", "昨日の夕焼けは赤いかったです。", "赤いかった", "赤かった"),
        ("先月の出張は長かったです。", "先月の出張は長いかったです。", "長いかった", "長かった"),
        ("朝の風は冷たかったです。", "朝の風は冷たいかったです。", "冷たいかった", "冷たかった"),
        ("この案内板は読みやすかったです。", "この案内板は読みやすいかったです。", "読みやすいかった", "読みやすかった"),
        ("昨日の荷物は重かったです。", "昨日の荷物は重いかったです。", "重いかった", "重かった"),
        ("旅行中の天気は良かったです。", "旅行中の天気は良いかったです。", "良いかった", "良かった"),
        ("先週の課題は難しかったです。", "先週の課題は難しいかったです。", "難しいかった", "難しかった"),
        ("海辺の夕日は美しかったです。", "海辺の夕日は美しいかったです。", "美しいかった", "美しかった"),
        ("昨夜のスープは熱かったです。", "昨夜のスープは熱いかったです。", "熱いかった", "熱かった"),
        ("先日の講演は短かったです。", "先日の講演は短いかったです。", "短いかった", "短かった"),
        ("昨日見た映画は面白かったです。", "昨日見た映画は面白いかったです。", "面白いかった", "面白かった"),
        ("ホテルの部屋は広かったです。", "ホテルの部屋は広いかったです。", "広いかった", "広かった"),
    ]
    for index, (correct, wrong, source, replacement) in enumerate(adjective_pairs):
        dev = index in {3, 7, 11}
        pair = f"v02f-adjective-past-{index + 1}"
        add("adjective_past_ok", index, correct, "acceptable", pair=pair, dev=dev,
            reason="い형용사의 과거 정중형이 올바르므로 유지합니다.")
        add("adjective_past_error", index, wrong, "needs_correction", pair=pair, dev=dev,
            changes=[(source, replacement, "adjective_conjugation")],
            reason="い형용사의 과거형만 최소 교정합니다.")

    verb_pairs = [
        ("土曜日にベランダを掃きます。", "土曜日にベランダを掃くます。", "掃くます", "掃きます"),
        ("会議の内容をノートに書きます。", "会議の内容をノートに書くます。", "書くます", "書きます"),
        ("夏は市民プールで泳ぎます。", "夏は市民プールで泳ぐます。", "泳ぐます", "泳ぎます"),
        ("受付で担当者と話します。", "受付で担当者と話すます。", "話すます", "話します"),
        ("駅の前で十分待ちます。", "駅の前で十分待つます。", "待つます", "待ちます"),
        ("休日は公園で子どもと遊びます。", "休日は公園で子どもと遊ぶます。", "遊ぶます", "遊びます"),
        ("朝食のあとで薬を飲みます。", "朝食のあとで薬を飲むます。", "飲むます", "飲みます"),
        ("仕事が終わったら家に帰ります。", "仕事が終わったら家に帰るます。", "帰るます", "帰ります"),
        ("旅行の前に切符を買います。", "旅行の前に切符を買うます。", "買うます", "買います"),
        ("毎晩、短い記事を読みます。", "毎晩、短い記事を読むます。", "読むます", "読みます"),
        ("週末は川沿いを走ります。", "週末は川沿いを走るます。", "走るます", "走ります"),
        ("誕生日に友達へ写真を送ります。", "誕生日に友達へ写真を送るます。", "送るます", "送ります"),
    ]
    for index, (correct, wrong, source, replacement) in enumerate(verb_pairs):
        dev = index in {3, 7, 11}
        pair = f"v02f-godan-polite-{index + 1}"
        add("godan_polite_ok", index, correct, "acceptable", pair=pair, dev=dev,
            reason="1그룹 동사의 정중형 접속이 올바르므로 유지합니다.")
        add("godan_polite_error", index, wrong, "needs_correction", pair=pair, dev=dev,
            changes=[(source, replacement, "verb_conjugation")],
            reason="원문의 의미와 정중체를 유지하며 동사 접속만 고칩니다.")

    compound_pairs = [
        ("午後は科学館に行きます。", "午後は科学館を行くます。", [("科学館を", "科学館に", "particle_misuse"), ("行くます", "行きます", "verb_conjugation")]),
        ("明日は市役所に行きます。", "明日は市役所を行くます。", [("市役所を", "市役所に", "particle_misuse"), ("行くます", "行きます", "verb_conjugation")]),
        ("週末は植物園に行きます。", "週末は植物園を行くます。", [("植物園を", "植物園に", "particle_misuse"), ("行くます", "行きます", "verb_conjugation")]),
        ("来月は領事館に行きます。", "来月は領事館を行くます。", [("領事館を", "領事館に", "particle_misuse"), ("行くます", "行きます", "verb_conjugation")]),
        ("昼休みに郵便局に行きます。", "昼休みに郵便局を行くます。", [("郵便局を", "郵便局に", "particle_misuse"), ("行くます", "行きます", "verb_conjugation")]),
        ("授業のあとで体育館に行きます。", "授業のあとで体育館を行くます。", [("体育館を", "体育館に", "particle_misuse"), ("行くます", "行きます", "verb_conjugation")]),
        ("小さい鳥が中庭にいます。", "小さいな鳥が中庭でいます。", [("小さいな", "小さい", "modifier_connection"), ("中庭で", "中庭に", "particle_misuse")]),
        ("白い猫が階段の下にいます。", "白いな猫が階段の下でいます。", [("白いな", "白い", "modifier_connection"), ("階段の下で", "階段の下に", "particle_misuse")]),
        ("丸い鏡が玄関にあります。", "丸いな鏡が玄関であります。", [("丸いな", "丸い", "modifier_connection"), ("玄関で", "玄関に", "particle_misuse")]),
        ("古い地図が書斎にあります。", "古いな地図が書斎であります。", [("古いな", "古い", "modifier_connection"), ("書斎で", "書斎に", "particle_misuse")]),
        ("赤い箱が棚の上にあります。", "赤いな箱が棚の上であります。", [("赤いな", "赤い", "modifier_connection"), ("棚の上で", "棚の上に", "particle_misuse")]),
        ("細い道が森の奥にあります。", "細いな道が森の奥であります。", [("細いな", "細い", "modifier_connection"), ("森の奥で", "森の奥に", "particle_misuse")]),
    ]
    for index, (correct, wrong, changes) in enumerate(compound_pairs):
        dev = index in {3, 7, 11}
        pair = f"v02f-compound-{index + 1}"
        add("compound_ok", index, correct, "acceptable", pair=pair, dev=dev,
            reason="조사와 활용이 모두 올바르므로 원문을 유지합니다.")
        add("compound_error", index, wrong, "needs_correction", pair=pair, dev=dev,
            changes=changes,
            reason="두 문법 오류를 모두 고치되 원문의 의미와 문체를 유지합니다.")

    foreign = [
        "이번 주말에는 가족과 등산을 갑니다.", "회의 자료는 책상 위에 있습니다.",
        "저는 아침마다 지하철을 탑니다.", "도서관은 오후 여섯 시에 닫습니다.",
        "The train leaves from platform four.", "My brother works near the airport.",
        "Please put the receipt in this envelope.", "We visited the museum last Saturday.",
    ]
    for index, text in enumerate(foreign):
        add("foreign_boundary", index, text, "insufficient_evidence", dev=index in {3, 7},
            reason="일본어 문법 판단 범위 밖의 입력이므로 번역문을 생성하지 않습니다.")

    incomplete = [
        ("昨日、会社の近くで……", "발화가 중간에 끊겨 뒤의 서술어를 확인할 수 없음"),
        ("もし来週の試験に合格したら……", "조건절 뒤 결과절이 녹음되지 않음"),
        ("新しい企画を提案したのは……", "강조 구문 뒤의 핵심 정보가 누락됨"),
        ("駅に着いたあと、友達と……", "발화 종료 전에 녹음이 중단됨"),
        ("明日の午後は［聞き取れない］へ行きます。", "목적지 구간이 잡음으로 식별되지 않음"),
        ("昨日の会議は［聞き取れない］かったです。", "형용사 어간을 들을 수 없음"),
        ("あの、次の電車は……", "질문이나 서술의 끝부분이 누락됨"),
        ("旅行から帰ったら、まず……", "행동을 나타내는 서술어가 녹음되지 않음"),
    ]
    for index, (text, context) in enumerate(incomplete):
        add("incomplete_boundary", index, text, "insufficient_evidence",
            context=context, dev=index in {3, 7},
            reason="누락된 내용을 추측해 완성하지 않고 판단을 보류합니다.")

    generated = builder.records
    for row in generated:
        row["tags"] = [VERSION if tag == "hard-negatives-v0.2-b" else tag
                       for tag in row["tags"]]
        row["provenance"]["source_id"] = VERSION
        row["review"]["reviewed_at"] = VALIDATED_AT

    expected = {"acceptable": 68, "needs_correction": 36,
                "insufficient_evidence": 16}
    if len(generated) != 120 or Counter(row["expected"]["decision"] for row in generated) != expected:
        raise ValueError("Unexpected v0.2-F size or decision distribution")
    if Counter(row["split"] for row in generated) != {"pilot_train": 90, "pilot_dev": 30}:
        raise ValueError("Unexpected v0.2-F split distribution")
    if sum(len(row["expected"]["edits"]) > 1 for row in generated) != 12:
        raise ValueError("Expected exactly twelve compound corrections")
    pair_splits = defaultdict(set)
    for row, metadata in zip(generated, builder.metadata):
        if metadata["pair_id"]:
            pair_splits[metadata["pair_id"]].add(row["split"])
    if len(pair_splits) != 36 or any(len(splits) != 1 for splits in pair_splits.values()):
        raise ValueError("Expected 36 co-located normal/error pairs")
    validate_records(generated, require_reviewed=True)
    return generated


def _audit(generated: list[dict]) -> dict:
    references = defaultdict(set)
    source_hashes = {}
    for path in AUDIT_DATASETS:
        relative = str(path.relative_to(ROOT))
        source_hashes[relative] = _sha256(path)
        for row in load_records(path):
            for value in {row["input"]["text"], row["expected"]["corrected_text"],
                          *row["accepted_corrections"]}:
                if len(fp := _fingerprint(value)) >= 4:
                    references[fp].add(relative)
    for path in sorted((ROOT / "rag_data").rglob("*.json")):
        relative = str(path.relative_to(ROOT))
        source_hashes[relative] = _sha256(path)

        def strings(value):
            if isinstance(value, str):
                yield value
            elif isinstance(value, list):
                for item in value:
                    yield from strings(item)
            elif isinstance(value, dict):
                for item in value.values():
                    yield from strings(item)

        for value in strings(json.loads(path.read_text(encoding="utf-8"))):
            if len(fp := _fingerprint(value)) >= 4:
                references[fp].add(relative)

    exact = []
    for row in generated:
        for value in {row["input"]["text"], row["expected"]["corrected_text"],
                      *row["accepted_corrections"]}:
            fp = _fingerprint(value)
            if len(fp) >= 4 and fp in references:
                exact.append({"id": row["id"], "text": value,
                              "sources": sorted(references[fp])})
    if exact:
        raise ValueError(f"Exact normalized overlap: {exact[:8]}")

    old_grams = [(fp, _trigrams(fp)) for fp, sources in references.items()
                 if len(fp) >= 5 and any(source.endswith(".jsonl") for source in sources)]
    near, highest = [], 0.0
    for row in generated:
        for value in {row["input"]["text"], row["expected"]["corrected_text"],
                      *row["accepted_corrections"]}:
            current = _trigrams(value)
            if not current:
                continue
            for previous, grams in old_grams:
                common = len(current & grams)
                if not common:
                    continue
                score = common / len(current | grams)
                highest = max(highest, score)
                if score >= NEAR_THRESHOLD:
                    near.append({"id": row["id"], "text": value,
                                 "previous": previous, "jaccard": round(score, 4)})
    if near:
        raise ValueError(f"Near-duplicate dataset overlap: {near[:8]}")
    return {
        "exact_normalized_matches": 0,
        "near_dataset_matches_at_or_above_0_85": 0,
        "max_dataset_character_3gram_jaccard": round(highest, 4),
        "source_sha256": source_hashes,
        "limitation": "Exact overlap includes RAG JSON. Near audit covers existing datasets only; semantic or pretraining overlap is not ruled out.",
    }


def build() -> dict:
    generated = build_generated()
    audit = _audit(generated)
    base = load_records(BASE)
    validate_records(base, require_reviewed=True)
    combined = base + generated
    validate_records(combined, require_reviewed=True)
    if len(base) != 828 or len(combined) != 948 or combined[:828] != base:
        raise ValueError("The v0.2-E base must remain unchanged")
    _write_jsonl(ADDITION, generated)
    _write_jsonl(COMBINED, combined)
    chatml = export(COMBINED, CHATML, output_contract="v0.2")
    manifest = {
        "dataset_id": "judgment-pilot-v0.2-f", "generation_version": VERSION,
        "validated_at": VALIDATED_AT, "output_contract": "judgment-v0.2",
        "source_dataset": str(BASE.relative_to(ROOT)), "source_dataset_sha256": _sha256(BASE),
        "augmentation_path": str(ADDITION.relative_to(ROOT)),
        "augmentation_sha256": _sha256(ADDITION),
        "combined_path": str(COMBINED.relative_to(ROOT)),
        "combined_sha256": _sha256(COMBINED),
        "augmentation_summary": summary(generated), "combined_summary": summary(combined),
        "generated_validation": {
            "records": len(generated), "human_reviewed": False, "expert_reviewed": False,
            "compound_error_cases": 12, "paired_cases": 36,
            "contamination_audit": audit,
        },
        "chatml": chatml,
        "holdout_policy": "Holdouts used only for overlap audit; no model predictions inspected or used for training.",
        "sealed_holdout_policy": "holdout_v0.3 remains inference-free until v0.2-F data, adapter and thresholds are committed.",
    }
    MANIFEST.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return manifest


if __name__ == "__main__":
    print(json.dumps(build(), ensure_ascii=False, indent=2))
