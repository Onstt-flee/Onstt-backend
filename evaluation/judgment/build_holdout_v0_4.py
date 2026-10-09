"""Build and seal the untouched v0.4 judgment holdout before v0.2-H work."""

from __future__ import annotations

from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import random

from evaluation.judgment.build_holdout import _corrected, _edit
from evaluation.judgment.dataset import sentence_fingerprint, validate_records


ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "evaluation/judgment/holdout_v0.4.jsonl"
MANIFEST = ROOT / "evaluation/judgment/holdout_v0.4.manifest.json"
SOURCE_FILES = (
    ROOT / "evaluation/judgment/seed_v0.1.jsonl",
    ROOT / "evaluation/judgment/holdout_v0.1.jsonl",
    ROOT / "evaluation/judgment/holdout_v0.2.jsonl",
    ROOT / "evaluation/judgment/holdout_v0.3.jsonl",
    ROOT / "training/judgment/data/pilot_v0.2_g.jsonl",
    ROOT / "training/judgment/data/failure_focus_v0.2_e.jsonl",
    ROOT / "training/judgment/data/failure_focus_v0.2_f.jsonl",
)
SHUFFLE_SEED = 20261004
NEAR_THRESHOLD = 0.85


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _row(number: int, text: str, decision: str, group: str, *, context=None,
         level="N5", edits=None, reason=None, tags=()):
    edits = edits or []
    corrected = _corrected(text, edits) if decision == "needs_correction" else text
    reasons = {
        "acceptable": "주어진 문맥에서는 문법 교정이 필요하지 않습니다.",
        "needs_correction": "의미와 문체를 유지하면서 명확한 문법 오류만 최소 교정합니다.",
        "insufficient_evidence": "누락되었거나 범위 밖인 입력을 추측하여 교정하지 않습니다.",
    }
    return {
        "schema_version": "0.1", "id": f"JH-{number + 390:04d}",
        "split": "holdout_eval", "group_id": group,
        "tags": [group, f"decision:{decision}", *tags],
        "input": {"text": text, "context": context, "learner_level": level},
        "expected": {"decision": decision, "corrected_text": corrected, "edits": edits,
                     "reason_ko": reason or reasons[decision]},
        "accepted_corrections": [corrected] if decision == "needs_correction" else [],
        "provenance": {"kind": "deterministic_template",
                       "source_id": f"holdout-v0.4:{number:04d}",
                       "external_text_used": False},
        "review": {"status": "generated_validated", "reviewed_at": None},
    }


def build_records() -> list[dict]:
    rows: list[dict] = []

    def add(text, decision, group, **kwargs):
        rows.append(_row(len(rows) + 1, text, decision, group, **kwargs))

    # Acceptable: concise speech, register preservation, particles and conjugations.
    for text in [
        "うん、夕方なら大丈夫。", "あと五分で着くよ。", "それ、私も見たい。",
        "今日はもう帰ろう。", "駅の南口で待ってるね。", "この席、空いてる？",
        "明日の朝に連絡する。", "その袋、ここに置いて。", "まだ少し残ってるよ。",
        "じゃあ、先に始めようか。",
    ]:
        add(text, "acceptable", "short_colloquial_ok_v4",
            context="친한 사람과 나누는 일상 대화", tags=("boundary_case", "check:style_preserve"))

    for text in [
        "ええと、集合場所を確認します。", "あのう、領収書をいただけますか。",
        "その、来月から部署が変わります。", "あの、こちらに座ってもいいですか。",
        "えっと、予約番号はこれです。",
    ]:
        add(text, "acceptable", "filler_content_ok_v4",
            tags=("boundary_case", "check:filler_preserve"))

    for text in [
        "港の防波堤を端まで歩きました。", "大学の中庭を斜めに横切りました。",
        "寺の石段をゆっくり上りました。", "川沿いの細道を自転車で走りました。",
        "地下街の通路をまっすぐ進みました。", "工場の見学路を一周しました。",
        "丘の遊歩道を夕方散歩しました。", "駅の連絡通路を急いで通りました。",
    ]:
        add(text, "acceptable", "route_wo_ok_v4", tags=("boundary_case", "route_wo"))

    for place, thing in [
        ("診察室の入口", "消毒液"), ("資料館の受付", "案内図"),
        ("共同玄関の脇", "宅配ボックス"), ("理科室の窓側", "標本棚"),
        ("宿直室の机上", "懐中電灯"), ("講義室の後方", "予備机"),
        ("調理室の壁際", "冷凍庫"), ("展望室の中央", "望遠鏡"),
    ]:
        add(f"{place}に{thing}があります。", "acceptable", "existence_ni_ok_v4")

    for text in [
        "先日の講演は興味深かったです。", "早朝の海風はかなり冷たかったです。",
        "昨日の坂道はきつかったです。", "先週の試合は惜しかったです。",
        "手続きの流れは複雑ではありません。", "叔父は毎朝新聞を読みます。",
        "明日は早めに家を出ます。", "祖父は庭で花を育てています。",
        "このかばんは軽くて丈夫です。", "妹は漢字を丁寧に書きます。",
        "来月から新しい教室を使います。",
    ]:
        add(text, "acceptable", "conjugation_ok_v4")

    for text in [
        "弟わ七時に起きました。", "荷物お受付に預けました。", "今日わ早く帰ります。",
        "薬お食後に飲みます。", "私わ来月引っ越します。", "手紙お祖母に送りました。",
        "先生わ会議中です。", "資料お机に置きました。",
    ]:
        add(text, "acceptable", "stt_orthography_boundary_v4",
            context="일본어 말하기의 STT 전사이며 원음과 대안 전사는 제공되지 않음",
            reason="조사 발음과 전사 표기는 원음 없이 학습자의 문법 오류로 확정하지 않습니다.",
            tags=("boundary_case", "check:orthography_candidate", "check:attribution_unknown"))

    # Needs correction: balanced single errors plus ten compound cases.
    for text, source, target in [
        ("午後は保健所を行きます。", "保健所を", "保健所に"),
        ("来週、海洋研究所を行きます。", "海洋研究所を", "海洋研究所に"),
        ("明日は公証役場を行きます。", "公証役場を", "公証役場に"),
        ("夕方、修理工場を行きます。", "修理工場を", "修理工場に"),
        ("土曜日は科学館を行きます。", "科学館を", "科学館に"),
        ("朝から労働局を行きます。", "労働局を", "労働局に"),
        ("明後日、展示会場を行きます。", "展示会場を", "展示会場に"),
        ("昼過ぎに交番を行きます。", "交番を", "交番に"),
    ]:
        add(text, "needs_correction", "destination_particle_error_v4",
            edits=[_edit(text, source, target, "particle_misuse")])

    existence_errors = [
        ("診察室の入口", "消毒液"), ("資料館の受付", "案内図"),
        ("共同玄関の脇", "宅配ボックス"), ("理科室の窓側", "標本棚"),
        ("宿直室の机上", "懐中電灯"), ("講義室の後方", "予備机"),
        ("調理室の壁際", "冷凍庫"), ("展望室の中央", "望遠鏡"),
    ]
    for place, thing in existence_errors:
        text = f"{place}で{thing}があります。"
        add(text, "needs_correction", "existence_de_error_v4",
            edits=[_edit(text, f"{place}で", f"{place}に", "particle_misuse")])

    for text, source, target in [
        ("昨日の打ち合わせは長いかったです。", "長いかった", "長かった"),
        ("今朝の井戸水は冷たいいかったです。", "冷たいいかった", "冷たかった"),
        ("先週の山道は険しいかったです。", "険しいかった", "険しかった"),
        ("あの荷物は重いかったです。", "重いかった", "重かった"),
        ("昨日の風は弱いかったです。", "弱いかった", "弱かった"),
        ("その問題は易しいかったです。", "易しいかった", "易しかった"),
        ("先月の部屋は狭いかったです。", "狭いかった", "狭かった"),
        ("昨夜の星は明るいかったです。", "明るいかった", "明るかった"),
    ]:
        add(text, "needs_correction", "adjective_past_error_v4",
            edits=[_edit(text, source, target, "adjective_conjugation")])

    for text, source, target in [
        ("毎朝、玄関を磨くます。", "磨くます", "磨きます"),
        ("昨日、新しい靴を履くました。", "履くました", "履きました"),
        ("申込書に住所を書くてください。", "書くて", "書いて"),
        ("先週、先輩を誘うました。", "誘うました", "誘いました"),
        ("廊下で少し立つてください。", "立つて", "立って"),
        ("毎晩、薬を飲むます。", "飲むます", "飲みます"),
        ("昨日、窓を閉めるました。", "閉めるました", "閉めました"),
        ("この線に沿うて歩いてください。", "沿うて", "沿って"),
    ]:
        add(text, "needs_correction", "verb_conjugation_error_v4",
            edits=[_edit(text, source, target, "verb_conjugation")])

    for text, source, target, error_type in [
        ("静か部屋で勉強します。", "静か部屋", "静かな部屋", "modifier_connection"),
        ("丈夫な靴が欲しいだです。", "欲しいだです", "欲しいです", "copula_conjugation"),
        ("便利場所を探しています。", "便利場所", "便利な場所", "modifier_connection"),
        ("今日は涼しいだです。", "涼しいだです", "涼しいです", "copula_conjugation"),
        ("熱心係員に手順を聞きました。", "熱心係員", "熱心な係員", "modifier_connection"),
        ("この机は丈夫だです。", "丈夫だです", "丈夫です", "copula_conjugation"),
        ("複雑問題を説明します。", "複雑問題", "複雑な問題", "modifier_connection"),
        ("その答えは正しいだです。", "正しいだです", "正しいです", "copula_conjugation"),
    ]:
        add(text, "needs_correction", "modifier_copula_error_v4",
            edits=[_edit(text, source, target, error_type)])

    for time, place, obj, wrong, correct in [
        ("昨日", "印刷室", "資料", "刷るました", "刷りました"),
        ("先週", "視聴覚室", "映像", "見るました", "見ました"),
        ("今朝", "作業場", "道具", "運ぶました", "運びました"),
        ("昨夜", "談話室", "友人", "待つました", "待ちました"),
        ("先月", "直売所", "野菜", "買うました", "買いました"),
        ("午後", "研修室", "報告", "聞くました", "聞きました"),
        ("昨日", "洗濯室", "毛布", "洗うました", "洗いました"),
        ("今朝", "準備室", "鍵", "探すました", "探しました"),
        ("先週", "相談室", "担当者", "会うました", "会いました"),
        ("昨晩", "食堂", "夕食", "食べるました", "食べました"),
    ]:
        text = f"{time}、{place}を{obj}を{wrong}。"
        add(text, "needs_correction", "compound_particle_verb_error_v4", level="N4",
            edits=[_edit(text, f"{place}を", f"{place}で", "particle_misuse"),
                   _edit(text, wrong, correct, "verb_conjugation")],
            tags=("compound_error",))

    # Insufficient evidence: preserve literal input and never translate or complete it.
    for text in [
        "The package should arrive before noon.", "I forgot my umbrella on the train.",
        "Could you check the meeting room?", "My cousin moved to a coastal town.",
        "다음 주에 건강검진을 받습니다.", "오늘은 지하철이 많이 붐볐습니다.",
    ]:
        add(text, "insufficient_evidence", "foreign_language_boundary_v4",
            tags=("boundary_case", "no_translation_as_correction"))

    for text in [
        "もし受付がもう閉まっていたら", "昨日、取引先の担当者に",
        "この装置を交換したのは", "駅の階段で落としたのは",
        "説明が予定より長くなったので", "私が倉庫から持ってきた箱は",
    ]:
        add(text, "insufficient_evidence", "incomplete_utterance_v4",
            tags=("boundary_case", "no_guessing"))

    for text in [
        "明日は［聞き取れない］に集合します。", "昨日、［雑音］を受け取りました。",
        "今朝は［聞き取れない］くなりました。", "［雑音］から電話がありました。",
    ]:
        add(text, "insufficient_evidence", "missing_audio_span_v4",
            tags=("boundary_case", "no_guessing"))

    for text in ["……", "ええと、あの……", "［長い雑音］", "あの、つまり……"]:
        add(text, "insufficient_evidence", "no_proposition_v4",
            tags=("boundary_case", "no_guessing"))

    expected = {"acceptable": 50, "needs_correction": 50, "insufficient_evidence": 20}
    if Counter(row["expected"]["decision"] for row in rows) != expected:
        raise AssertionError("Unexpected holdout distribution")
    random.Random(SHUFFLE_SEED).shuffle(rows)
    validate_records(rows)
    return rows


def _strings(path: Path):
    for line in path.read_text(encoding="utf-8").splitlines():
        row = json.loads(line)
        yield row["input"]["text"]
        yield row["expected"]["corrected_text"]
        yield from row.get("accepted_corrections", [])


def _nested_strings(value):
    if isinstance(value, str):
        yield value
    elif isinstance(value, list):
        for item in value:
            yield from _nested_strings(item)
    elif isinstance(value, dict):
        for item in value.values():
            yield from _nested_strings(item)


def _grams(value: str) -> set[str]:
    return {value[index:index + 3] for index in range(len(value) - 2)}


def build(data_path: Path = DATA, manifest_path: Path = MANIFEST) -> dict:
    rows = build_records()
    corpus = defaultdict(set)
    historical = set()
    source_hashes = {}
    for path in SOURCE_FILES:
        label = str(path.relative_to(ROOT))
        source_hashes[label] = _sha256(path)
        for value in _strings(path):
            historical.add(value)
            fp = sentence_fingerprint(value)
            if len(fp) >= 4:
                corpus[fp].add(label)

    for path in sorted((ROOT / "rag_data").rglob("*.json")):
        label = str(path.relative_to(ROOT))
        source_hashes[label] = _sha256(path)
        for value in _nested_strings(json.loads(path.read_text(encoding="utf-8"))):
            fp = sentence_fingerprint(value)
            if len(fp) >= 4:
                corpus[fp].add(label)

    direct = []
    prior = [(value, _grams(fp)) for value in historical
             if len(fp := sentence_fingerprint(value)) >= 5]
    near, maximum, maximum_pair = [], 0.0, None
    for row in rows:
        values = {row["input"]["text"], row["expected"]["corrected_text"],
                  *row["accepted_corrections"]}
        for value in values:
            fp = sentence_fingerprint(value)
            if len(fp) >= 4 and fp in corpus:
                direct.append({"id": row["id"], "text": value,
                               "sources": sorted(corpus[fp])})
            if len(fp) < 5:
                continue
            current = _grams(fp)
            for previous, other in prior:
                common = len(current & other)
                if not common:
                    continue
                score = common / len(current | other)
                if score > maximum:
                    maximum = score
                    maximum_pair = {"id": row["id"], "text": value,
                                    "previous": previous, "jaccard": round(score, 4)}
                if score >= NEAR_THRESHOLD:
                    near.append({"id": row["id"], "text": value,
                                 "previous": previous, "jaccard": round(score, 4)})
    if direct:
        raise ValueError(f"Holdout overlaps existing data: {direct[:5]}")
    if near:
        raise ValueError(f"Holdout near-duplicates existing data: {near[:5]}")

    payload = "".join(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n"
                      for row in rows)
    data_path.write_text(payload, encoding="utf-8")
    dataset_hash = hashlib.sha256(payload.encode()).hexdigest()
    info = {
        "dataset": str(data_path.relative_to(ROOT)) if data_path.is_relative_to(ROOT) else str(data_path),
        "schema_version": "0.1", "role": "sealed_blind_holdout",
        "generator_seed": SHUFFLE_SEED, "records": len(rows), "sha256": dataset_hash,
        "decisions": dict(sorted(Counter(row["expected"]["decision"] for row in rows).items())),
        "groups": dict(sorted(Counter(row["group_id"] for row in rows).items())),
        "compound_error_cases": sum(len(row["expected"]["edits"]) > 1 for row in rows),
        "review_status": "generated_validated", "human_reviewed": False,
        "expert_reviewed": False,
        "contamination_audit": {
            "exact_normalized_matches": 0,
            "near_dataset_matches_at_or_above_0_85": 0,
            "max_dataset_character_3gram_jaccard": round(maximum, 4),
            "max_dataset_character_3gram_pair": maximum_pair,
            "source_sha256": dict(sorted(source_hashes.items())),
            "limitation": "Exact audit includes RAG; near audit covers canonical datasets. Semantic and pretraining overlap are not ruled out.",
        },
        "execution_policy": {
            "model_inference_count_before_protocol_freeze": 0,
            "labels_must_not_be_used_for_training_or_selection": True,
            "single_use_after_model_and_threshold_freeze": True,
        },
    }
    manifest_path.write_text(json.dumps(info, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return info


if __name__ == "__main__":
    print(json.dumps(build(), ensure_ascii=False, indent=2))
