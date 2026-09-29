"""Deterministic v0.2-D augmentation from development-set failure families only.

This builder reads holdouts solely for contamination checks. It never uses their
labels as generation inputs and never calls a model.
"""

from __future__ import annotations

from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path

from training.judgment.build_hard_negatives import Builder, _write_jsonl
from training.judgment.data import load_records, summary, validate_records
from training.judgment.export_chatml import export


ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT / "training/judgment/data"
BASE = DATA_DIR / "pilot_v0.2_c.jsonl"
ADDITION = DATA_DIR / "failure_focus_v0.2_d.jsonl"
COMBINED = DATA_DIR / "pilot_v0.2_d.jsonl"
CHATML = DATA_DIR / "failure_focus_v0.2_d_chatml"
MANIFEST = DATA_DIR / "failure_focus_v0.2_d.manifest.json"
AUDIT_DATASETS = (
    ROOT / "evaluation/judgment/seed_v0.1.jsonl",
    ROOT / "evaluation/judgment/holdout_v0.1.jsonl",
    ROOT / "evaluation/judgment/holdout_v0.2.jsonl",
    BASE,
)
VERSION = "failure-focus-v0.2-d"
VALIDATED_AT = "2026-09-22"
NEAR_THRESHOLD = 0.85


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _fingerprint(text: str) -> str:
    from training.judgment.data import fingerprint
    return fingerprint(text)


def _trigrams(text: str) -> set[str]:
    text = _fingerprint(text)
    return {text[index:index + 3] for index in range(len(text) - 2)}


def _edits(text: str, changes: list[tuple[str, str, str]]) -> list[dict]:
    edits = []
    for source, replacement, error_type in changes:
        if text.count(source) != 1:
            raise ValueError(f"Expected one {source!r} in {text!r}")
        start = text.index(source)
        edits.append({"start": start, "end": start + len(source), "source": source,
                      "replacement": replacement, "error_type": error_type})
    edits.sort(key=lambda item: item["start"])
    if any(left["end"] > right["start"] for left, right in zip(edits, edits[1:])):
        raise ValueError(f"Overlapping edits in {text!r}")
    return edits


def _apply(text: str, edits: list[dict]) -> str:
    for edit in reversed(edits):
        text = text[:edit["start"]] + edit["replacement"] + text[edit["end"]:]
    return text


def build_generated() -> list[dict]:
    builder = Builder(start=629)

    def add(family: str, index: int, dev_indices: set[int], text: str, decision: str,
            *, reason: str, context: str | None = None,
            changes: list[tuple[str, str, str]] | None = None,
            anchor: str | None = None, pair: str | None = None):
        split = "pilot_dev" if index in dev_indices else "pilot_train"
        edits = _edits(text, changes) if changes else []
        corrected = _apply(text, edits) if edits else text
        row = builder.add(
            family=f"v02d_{family}_{split}", split=split, text=text,
            context=context, decision=decision, reason=reason,
            corrected_text=corrected if edits else None,
            error_type=edits[0]["error_type"] if edits else None,
            pair_id=pair, source_anchor_id=anchor,
        )
        if edits:
            row["expected"]["edits"] = edits
            for error_type in dict.fromkeys(edit["error_type"] for edit in edits):
                if error_type not in row["tags"]:
                    row["tags"].append(error_type)
        return row

    route_ok = [
        "昼下がりに住宅街の路地を歩きました。",
        "雨上がりに川の土手を走りました。",
        "観光客は城門をくぐって庭園に入りました。",
        "私は木造の橋をゆっくり渡りました。",
        "バスは細い峠道を通りました。",
        "家族で旧道を歩いて駅へ向かいました。",
        "犬は庭の小道を走り回りました。",
        "山の尾根を慎重に歩きました。",
        "校舎の渡り廊下を急いで通りました。",
        "船は狭い水路を進みました。",
        "夕暮れに砂浜を散歩しました。",
        "登山客は沢沿いの道を下りました。",
    ]
    for index, text in enumerate(route_ok):
        add("route_wo_ok", index, {4, 9}, text, "acceptable", anchor="JG-003",
            reason="이동 경로나 통과 지점에 쓰인 を는 문법적으로 허용합니다.")

    style_ok = [
        "今日は先に弁当を買うよ。", "昨日は祖父の家に泊まった。",
        "この写真、あとで送るね。", "明日の朝、駅で待ってる。",
        "資料はもう印刷したよ。", "その店には行ったことがあるよ。",
        "今夜は少し遅くなる。", "週末、近くの山に登るよ。",
        "この荷物、私が持つね。", "また連絡するから待ってて。",
        "昨日は雨で家にいた。", "明日はゆっくり休むよ。",
    ]
    for index, text in enumerate(style_ok):
        add("plain_style_ok", index, {4, 9}, text, "acceptable", anchor="JG-006",
            context="친한 친구와의 일상 대화",
            reason="문맥에 맞는 보통체를 정중체로 바꿀 필요가 없습니다.")

    existence = [
        ("研究室の冷蔵庫", "試薬"), ("研究棟の廊下", "先生"),
        ("車の後部座席", "傘"), ("港の待合室", "自動販売機"),
        ("和室の押し入れ", "布団"), ("旅館の玄関", "犬"),
        ("校庭の隅", "古い桜の木"), ("商店の入り口", "小さな看板"),
        ("キッチンの棚", "予備の皿"), ("病院の廊下", "消火器"),
        ("図書館の地下", "閲覧室"), ("駅のホーム", "時計"),
    ]
    for index, (place, thing) in enumerate(existence):
        predicate = "います" if index in {1, 5} else "あります"
        add("existence_ni_ok", index, {3, 7, 11},
            f"{place}に{thing}が{predicate}。", "acceptable", anchor="JG-027",
            reason="사람·동물·사물의 존재 장소를 に로 나타낸 문장입니다.",
            pair=f"v02d-existence-{index + 1}")

    adjectives = [
        ("昨日の講義", "長かった"), ("昨夜の雪", "深かった"),
        ("このかばん", "軽かった"), ("先週の仕事", "忙しかった"),
        ("朝の空気", "冷たかった"), ("宿の廊下", "狭かった"),
        ("昨日の試合", "面白かった"), ("冬の海", "青かった"),
        ("試験の問題", "難しかった"), ("子どもの声", "大きかった"),
        ("午後の日差し", "強かった"), ("あの部屋", "明るかった"),
    ]
    for index, (subject, predicate) in enumerate(adjectives):
        add("adjective_past_ok", index, {3, 7, 11},
            f"{subject}は{predicate}です。", "acceptable", anchor="JG-035",
            reason="い형용사의 과거형이 올바릅니다.",
            pair=f"v02d-adjective-{index + 1}")

    stt_ok = [
        "今日は弟わ午前中に休みます。", "この雑誌お昨日買いました。",
        "姉わ午後に戻ります。", "新しい靴お買いました。",
        "母わ今、庭にいます。", "夕飯お家で作りました。",
    ]
    for index, text in enumerate(stt_ok):
        add("stt_orthography_ok", index, {4}, text, "acceptable", anchor="JG-068",
            context="일본어 말하기를 STT로 전사한 결과; 원음과 대안 전사는 없음",
            reason="원음 없이 조사 표기를 학습자의 문법 오류로 단정하지 않습니다.")

    filler_ok = [
        "えっと、予約番号を教えてください。", "あのう、今日は何時に閉まりますか。",
        "その、少しだけ質問してもいいですか。", "うーん、明日の予定を確認します。",
        "ええと、この薬はいつ飲みますか。", "あの、席を替えてもいいですか。",
    ]
    for index, text in enumerate(filler_ok):
        add("filler_ok", index, {4}, text, "acceptable", anchor="JG-006",
            reason="자연스러운 필러는 문법 교정 대상이 아닙니다.")

    destinations = [
        ("午前中は税務署を行きます。", "税務署を", "税務署に"),
        ("今度、古書店を行きます。", "古書店を", "古書店に"),
        ("夕食後は交番を行きます。", "交番を", "交番に"),
        ("来週、音楽ホールを行きます。", "音楽ホールを", "音楽ホールに"),
        ("明日は理髪店を行きます。", "理髪店を", "理髪店に"),
        ("午後から市立図書館を行きます。", "市立図書館を", "市立図書館に"),
        ("日曜には園芸店を行きます。", "園芸店を", "園芸店に"),
        ("診察後、薬局を行きます。", "薬局を", "薬局に"),
    ]
    for index, (text, source, replacement) in enumerate(destinations):
        add("destination_wo_error", index, {3, 7}, text, "needs_correction",
            changes=[(source, replacement, "particle_misuse")], anchor="JG-003",
            reason="이 문맥의 を는 이동 경로가 아니라 목적지 표시의 조사 오용입니다.")

    for index, (place, thing) in enumerate(existence[:8]):
        predicate = "います" if index in {1, 5} else "あります"
        text = f"{place}で{thing}が{predicate}。"
        add("existence_de_error", index, {3, 7}, text, "needs_correction",
            changes=[(f"{place}で", f"{place}に", "particle_misuse")],
            anchor="JG-027", pair=f"v02d-existence-{index + 1}",
            reason="존재 장소를 나타내는 조사 で만 に로 고칩니다.")

    for index, (subject, predicate) in enumerate(adjectives[:8]):
        wrong = predicate.replace("かった", "いかった")
        text = f"{subject}は{wrong}です。"
        add("adjective_past_error", index, {3, 7}, text, "needs_correction",
            changes=[(wrong, predicate, "adjective_conjugation")],
            anchor="JG-035", pair=f"v02d-adjective-{index + 1}",
            reason="い형용사의 과거형에서 불필요한 い를 제거합니다.")

    plain_verbs = [
        ("昨日、祖母に手紙を書くた。", "書くた", "書いた"),
        ("さっき駅で友達に会うた。", "会うた", "会った"),
        ("昼休みに本を読むた。", "読むた", "読んだ"),
        ("週末に母を手伝うた。", "手伝うた", "手伝った"),
        ("昨夜は早く寝るた。", "寝るた", "寝た"),
        ("午後に公園を走るた。", "走るた", "走った"),
    ]
    for index, (text, source, replacement) in enumerate(plain_verbs):
        add("plain_verb_error", index, {4}, text, "needs_correction",
            context="친한 친구와의 일상 대화",
            changes=[(source, replacement, "verb_conjugation")], anchor="JG-006",
            reason="보통체 문체를 유지하면서 동사의 과거 활용만 고칩니다.")

    compound_place_verb = [
        ("昨日", "音楽室", "ピアノ", "弾くました", "弾きました"),
        ("先週", "調理室", "ケーキ", "作るました", "作りました"),
        ("今朝", "校庭", "写真", "撮るました", "撮りました"),
        ("昨日", "会議室", "資料", "配るました", "配りました"),
        ("先週", "研究室", "報告書", "書くました", "書きました"),
    ]
    for index, (time, place, obj, wrong, correct) in enumerate(compound_place_verb):
        text = f"{time}、{place}を{obj}を{wrong}。"
        add("compound_place_verb", index, set(), text, "needs_correction",
            changes=[(f"{place}を", f"{place}で", "particle_misuse"),
                     (wrong, correct, "verb_conjugation")], anchor="JG-027",
            reason="동작 장소 조사와 동사 정중 과거형을 각각 최소 교정합니다.")

    compound_adj_destination = [
        ("寒いかった", "寒かった", "温泉"),
        ("暑いかった", "暑かった", "市民プール"),
        ("眠いかった", "眠かった", "寮"),
        ("忙しいかった", "忙しかった", "郵便局"),
        ("涼しいかった", "涼しかった", "植物園"),
    ]
    for index, (wrong, correct, place) in enumerate(compound_adj_destination):
        ending = "行きませんでした" if index == 3 else "行きました"
        text = f"昨日は{wrong}ので、{place}を{ending}。"
        add("compound_adj_destination", index, {4}, text, "needs_correction",
            changes=[(wrong, correct, "adjective_conjugation"),
                     (f"{place}を", f"{place}に", "particle_misuse")],
            anchor="JG-035", reason="형용사 과거형과 목적지 조사를 각각 최소 교정합니다.")

    english = [
        "Could you repeat the last question?", "Yesterday I borrowed a dictionary.",
        "Please wait near the entrance.", "We visited a small museum.",
        "I need to check the train schedule.", "She works at the local clinic.",
        "I lost my notebook this morning.",
    ]
    for index, text in enumerate(english):
        add("english_out_of_scope", index, {6}, text, "insufficient_evidence",
            anchor="JG-059", reason="일본어 판단 대상 밖의 영어 발화이며 번역은 교정이 아닙니다.")

    korean = [
        "오늘은 버스를 타고 회사에 갑니다.", "어제 저녁에 동생을 만났어요.",
        "아침에 지갑을 집에 두고 왔습니다.", "다음 달에 병원에 갈 예정입니다.",
        "저는 주말마다 산책합니다.", "그 책은 이미 다 읽었습니다.",
        "잠시만 기다려 주시겠어요?",
    ]
    for index, text in enumerate(korean):
        add("korean_out_of_scope", index, {6}, text, "insufficient_evidence",
            anchor="JG-060", reason="일본어 판단 대상 밖의 한국어 발화이며 번역은 교정이 아닙니다.")

    incomplete = [
        "来週の面接が終わったら", "私はその知らせを聞いて",
        "もし道が混んでいたら", "昨日の会議で決まったのは",
    ]
    for index, text in enumerate(incomplete):
        add("incomplete_utterance", index, {3}, text, "insufficient_evidence",
            reason="끝나지 않은 발화의 뒷부분을 추측하지 않습니다.")

    noise = ["［音声欠落］の後で帰りました。", "窓の外に［雑音］がいます。"]
    for index, text in enumerate(noise):
        add("missing_audio_span", index, {1}, text, "insufficient_evidence",
            reason="핵심 단어의 음성이 누락되어 문법 판단을 보류합니다.")

    generated = builder.records
    for row in generated:
        row["tags"] = [VERSION if tag == "hard-negatives-v0.2-b" else tag
                       for tag in row["tags"]]
        row["provenance"]["source_id"] = VERSION
        row["review"]["reviewed_at"] = VALIDATED_AT
    if len(generated) != 120:
        raise ValueError(f"Expected 120 new records, got {len(generated)}")
    if Counter(row["expected"]["decision"] for row in generated) != {
        "acceptable": 60, "needs_correction": 40, "insufficient_evidence": 20,
    }:
        raise ValueError("Unexpected v0.2-D decision distribution")
    if Counter(row["split"] for row in generated) != {
        "pilot_train": 96, "pilot_dev": 24,
    }:
        raise ValueError("Unexpected v0.2-D split distribution")
    if sum(len(row["expected"]["edits"]) > 1 for row in generated) != 10:
        raise ValueError("Expected exactly ten compound corrections")
    pair_splits = defaultdict(set)
    pair_counts = Counter()
    for row, metadata in zip(generated, builder.metadata):
        pair_id = metadata["pair_id"]
        if pair_id:
            pair_splits[pair_id].add(row["split"])
            pair_counts[pair_id] += 1
    if any(len(splits) != 1 for splits in pair_splits.values()):
        raise ValueError("Normal/error pairs must remain in one split")
    if sum(count == 2 for count in pair_counts.values()) != 16:
        raise ValueError("Expected sixteen complete normal/error pairs")
    validate_records(generated, require_reviewed=True)
    return generated


def _audit(generated: list[dict]) -> dict:
    references = defaultdict(set)
    source_hashes = {}
    for path in AUDIT_DATASETS:
        source_hashes[str(path.relative_to(ROOT))] = _sha256(path)
        for row in load_records(path):
            for value in {row["input"]["text"], row["expected"]["corrected_text"],
                          *row["accepted_corrections"]}:
                if len(fp := _fingerprint(value)) >= 4:
                    references[fp].add(str(path.relative_to(ROOT)))
    for path in sorted((ROOT / "rag_data").rglob("*.json")):
        source_hashes[str(path.relative_to(ROOT))] = _sha256(path)

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
                references[fp].add(str(path.relative_to(ROOT)))

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
    if len(base) != 628 or len(combined) != 748 or combined[:628] != base:
        raise ValueError("The v0.2-C base must remain unchanged")
    _write_jsonl(ADDITION, generated)
    _write_jsonl(COMBINED, combined)
    chatml = export(COMBINED, CHATML, output_contract="v0.2")
    manifest = {
        "dataset_id": "judgment-pilot-v0.2-d", "generation_version": VERSION,
        "validated_at": VALIDATED_AT, "output_contract": "judgment-v0.2",
        "source_dataset": str(BASE.relative_to(ROOT)), "source_dataset_sha256": _sha256(BASE),
        "augmentation_path": str(ADDITION.relative_to(ROOT)),
        "augmentation_sha256": _sha256(ADDITION),
        "combined_path": str(COMBINED.relative_to(ROOT)),
        "combined_sha256": _sha256(COMBINED),
        "augmentation_summary": summary(generated), "combined_summary": summary(combined),
        "generated_validation": {
            "records": len(generated), "human_reviewed": False, "expert_reviewed": False,
            "compound_error_cases": 10, "contamination_audit": audit,
        },
        "chatml": chatml,
        "holdout_policy": "Holdouts used only for overlap audit; no model predictions inspected or used for training.",
    }
    MANIFEST.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return manifest


if __name__ == "__main__":
    print(json.dumps(build(), ensure_ascii=False, indent=2))
