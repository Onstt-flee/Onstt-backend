"""Build the untouched v0.3 judgment holdout before v0.2-F training."""

from __future__ import annotations

from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import random

from evaluation.judgment.build_holdout import _edit, _corrected
from evaluation.judgment.dataset import sentence_fingerprint, validate_records


ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "evaluation/judgment/holdout_v0.3.jsonl"
MANIFEST = ROOT / "evaluation/judgment/holdout_v0.3.manifest.json"
SOURCE_FILES = (
    ROOT / "evaluation/judgment/seed_v0.1.jsonl",
    ROOT / "evaluation/judgment/holdout_v0.1.jsonl",
    ROOT / "evaluation/judgment/holdout_v0.2.jsonl",
    ROOT / "training/judgment/data/pilot_v0.2_e.jsonl",
)
SHUFFLE_SEED = 20260929


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _row(number: int, text: str, decision: str, group: str, *, context=None,
         level="N5", edits=None, reason=None, tags=()):
    edits = edits or []
    corrected = _corrected(text, edits) if decision == "needs_correction" else text
    reasons = {
        "acceptable": "주어진 문맥에서는 문법 교정이 필요하지 않습니다.",
        "needs_correction": "의미와 문체를 유지하면서 표시된 문법 오류만 고칩니다.",
        "insufficient_evidence": "발화가 누락되었거나 대상 언어의 판단 근거가 부족해 교정문을 추측하지 않습니다.",
    }
    return {
        "schema_version": "0.1", "id": f"JH-{number + 270:04d}", "split": "holdout_eval",
        "group_id": group, "tags": [group, f"decision:{decision}", *tags],
        "input": {"text": text, "context": context, "learner_level": level},
        "expected": {"decision": decision, "corrected_text": corrected, "edits": edits,
                     "reason_ko": reason or reasons[decision]},
        "accepted_corrections": [corrected] if decision == "needs_correction" else [],
        "provenance": {"kind": "deterministic_template", "source_id": f"holdout-v0.3:{number:04d}",
                       "external_text_used": False},
        "review": {"status": "generated_validated", "reviewed_at": None},
    }


def build_records() -> list[dict]:
    rows = []

    def add(text, decision, group, **kwargs):
        rows.append(_row(len(rows) + 1, text, decision, group, **kwargs))

    routes = [
        "城跡の小道を朝ゆっくり歩きました。", "運河沿いの遊歩道を二十分走りました。",
        "古い商店街を自転車で通り抜けました。", "校舎の渡り廊下を静かに歩きました。",
        "竹林の道を一人で散歩しました。", "競技場の外周を三周走りました。",
        "雪の山道を慎重に下りました。", "市場の中央通路を通って出口へ行きました。",
        "田んぼの間の道を夕方走りました。", "美術館の長い廊下を歩いて戻りました。",
    ]
    for text in routes:
        add(text, "acceptable", "route_wo_ok_v3", tags=("boundary_case", "route_wo"))

    casual = [
        "明日は家でゆっくり休むよ。", "あとでその写真を見るね。", "今夜、駅まで迎えに行く。",
        "この荷物、私が運ぶよ。", "週末は妹と買い物する。", "授業が終わったら電話するね。",
        "今日は先にシャワーを浴びる。", "その本、明日返すよ。", "うん、昼からなら会えるよ。",
        "昨日は家で音楽を聞いてた。",
    ]
    for text in casual:
        add(text, "acceptable", "casual_style_ok_v3", context="친한 친구와의 일상 대화",
            tags=("boundary_case", "check:style_preserve"))

    existences = [
        ("研究室の棚", "顕微鏡"), ("受付の机", "呼び出しベル"), ("倉庫の入口", "台車"),
        ("音楽室の隅", "古いピアノ"), ("洗面所の壁", "大きな鏡"), ("会議室の奥", "予備の椅子"),
        ("職員室の窓辺", "小さな鉢植え"), ("体育館の入口", "靴箱"), ("売店の横", "自動販売機"),
        ("屋上の中央", "給水タンク"),
    ]
    for place, thing in existences:
        add(f"{place}に{thing}があります。", "acceptable", "existence_ni_ok_v3")

    adjectives = [
        ("昨日の風", "強かった"), ("先月の旅行", "楽しかった"), ("今朝の紅茶", "熱かった"),
        ("あの説明", "分かりやすかった"), ("先週の宿題", "多かった"), ("昨日の道", "滑りやすかった"),
        ("去年の冬", "寒かった"), ("その箱", "軽かった"), ("今朝のパン", "柔らかかった"),
        ("あの山", "高かった"),
    ]
    for subject, predicate in adjectives:
        add(f"{subject}は{predicate}です。", "acceptable", "adjective_past_ok_v3")

    for text in [
        "ええと、次の信号を左に曲がります。", "あのう、注文を変更したいです。",
        "その、明日は少し早く来ます。", "あの、窓を開けてもいいですか。",
        "ええと、この荷物はどこに置きますか。",
    ]:
        add(text, "acceptable", "filler_ok_v3", tags=("boundary_case", "check:filler_preserve"))
    for text in ["姉わ午後に帰ります。", "新聞お朝読みました。", "明日わ会社に行きます。", "写真お父に送りました。", "私わ駅で待ちます。"]:
        add(text, "acceptable", "stt_orthography_boundary_v3",
            context="일본어 말하기를 STT로 전사한 결과; 원음과 대안 전사는 없음",
            reason="조사 발음과 전사 표기는 원음 없이 학습자의 문법 오류로 확정하지 않습니다.",
            tags=("boundary_case", "check:orthography_candidate", "check:attribution_unknown"))

    destinations = [
        ("午後は市役所を行きます。", "市役所を", "市役所に"), ("来週、動物病院を行きます。", "動物病院を", "動物病院に"),
        ("明日は文化センターを行きます。", "文化センターを", "文化センターに"), ("夕方、薬局を行きます。", "薬局を", "薬局に"),
        ("日曜日に展望台を行きます。", "展望台を", "展望台に"), ("朝から税務署を行きます。", "税務署を", "税務署に"),
        ("来月は水族館を行きます。", "水族館を", "水族館に"), ("昼休みに郵便窓口を行きます。", "郵便窓口を", "郵便窓口に"),
        ("土曜日は陶芸教室を行きます。", "陶芸教室を", "陶芸教室に"), ("明後日、整形外科を行きます。", "整形外科を", "整形外科に"),
    ]
    for text, source, target in destinations:
        add(text, "needs_correction", "destination_particle_error_v3",
            edits=[_edit(text, source, target, "particle_misuse")])

    for place, thing in existences:
        text = f"{place}で{thing}があります。"
        add(text, "needs_correction", "existence_de_error_v3",
            edits=[_edit(text, f"{place}で", f"{place}に", "particle_misuse")])

    for subject, predicate in adjectives:
        wrong = predicate.replace("かった", "いかった")
        text = f"{subject}は{wrong}です。"
        add(text, "needs_correction", "adjective_past_error_v3",
            edits=[_edit(text, wrong, predicate, "adjective_conjugation")])

    verbs = [
        ("毎朝、庭を掃くます。", "掃くます", "掃きます"), ("昨日、果物を買うました。", "買うました", "買いました"),
        ("ここに番号を書くてください。", "書くて", "書いて"), ("先週、部長に会うました。", "会うました", "会いました"),
        ("入口で少し待つてください。", "待つて", "待って"), ("毎晩、日記を書くます。", "書くます", "書きます"),
        ("昨日、九時に寝るました。", "寝るました", "寝ました"), ("この橋を渡るてください。", "渡るて", "渡って"),
        ("先月、木を植えるました。", "植えるました", "植えました"), ("毎週、祖母に電話するます。", "電話するます", "電話します"),
    ]
    for text, source, target in verbs:
        add(text, "needs_correction", "verb_conjugation_error_v3",
            edits=[_edit(text, source, target, "verb_conjugation")])

    compound = [
        ("昨日", "工作室", "箱", "作るました", "作りました"), ("先週", "読書室", "資料", "読むました", "読みました"),
        ("今朝", "実験室", "結果", "書くました", "書きました"), ("昨日", "音楽室", "先生", "待つました", "待ちました"),
        ("先月", "売店", "手帳", "買うました", "買いました"), ("昨夜", "和室", "手紙", "書くました", "書きました"),
        ("午後", "練習室", "発音", "練習するました", "練習しました"), ("昨日", "調理場", "魚", "焼くました", "焼きました"),
        ("今朝", "資料室", "辞書", "探すました", "探しました"), ("先週", "講堂", "友達", "会うました", "会いました"),
    ]
    for time, place, obj, wrong, correct in compound:
        text = f"{time}、{place}を{obj}を{wrong}。"
        add(text, "needs_correction", "compound_particle_verb_error_v3", level="N4",
            edits=[_edit(text, f"{place}を", f"{place}で", "particle_misuse"),
                   _edit(text, wrong, correct, "verb_conjugation")], tags=("compound_error",))

    for text in [
        "I left the keys on the kitchen table.", "The museum closes at six.", "Please send me the updated schedule.",
        "My brother started a new job.", "오늘 저녁에 운동할 거예요.", "어제 새 신발을 샀습니다.",
        "주말에 부모님을 만날 예정입니다.", "이 음식은 조금 맵습니다.",
    ]:
        add(text, "insufficient_evidence", "foreign_language_boundary_v3",
            tags=("boundary_case", "no_translation_as_correction"))
    for text in [
        "もし電車が予定より遅れたら", "昨日、会社の同僚に", "この景色を撮影したのは", "駅前で偶然見かけたのは",
        "会議が予定より長引いたので", "私が昨日借りた本は", "旅行中に食べたかったのは", "次の授業で説明するのは",
    ]:
        add(text, "insufficient_evidence", "incomplete_utterance_v3", tags=("boundary_case", "no_guessing"))
    for text in ["明日は［聞き取れない］で会います。", "昨日、［雑音］を直しました。", "今朝は［聞き取れない］かったです。", "［雑音］へ向かいました。"]:
        add(text, "insufficient_evidence", "missing_audio_span_v3", tags=("boundary_case", "no_guessing"))

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
        yield from row["accepted_corrections"]


def _grams(value: str) -> set[str]:
    return {value[index:index + 3] for index in range(len(value) - 2)}


def build(data_path: Path = DATA, manifest_path: Path = MANIFEST) -> dict:
    rows = build_records()
    corpus = defaultdict(set)
    historical = set()
    source_hashes = {}
    for path in SOURCE_FILES:
        source_hashes[str(path.relative_to(ROOT))] = _sha256(path)
        for value in _strings(path):
            historical.add(value)
            fp = sentence_fingerprint(value)
            if len(fp) >= 4:
                corpus[fp].add(str(path.relative_to(ROOT)))
    for path in sorted((ROOT / "rag_data").rglob("*.json")):
        source_hashes[str(path.relative_to(ROOT))] = _sha256(path)

        def nested_strings(value):
            if isinstance(value, str):
                yield value
            elif isinstance(value, list):
                for item in value:
                    yield from nested_strings(item)
            elif isinstance(value, dict):
                for item in value.values():
                    yield from nested_strings(item)

        for value in nested_strings(json.loads(path.read_text(encoding="utf-8"))):
            fp = sentence_fingerprint(value)
            if len(fp) >= 4:
                corpus[fp].add(str(path.relative_to(ROOT)))

    direct = []
    prior = [(value, _grams(fp)) for value in historical
             if len(fp := sentence_fingerprint(value)) >= 5]
    near, maximum = [], 0.0
    for row in rows:
        values = {row["input"]["text"], row["expected"]["corrected_text"], *row["accepted_corrections"]}
        for value in values:
            fp = sentence_fingerprint(value)
            if len(fp) >= 4 and fp in corpus:
                direct.append({"id": row["id"], "text": value, "sources": sorted(corpus[fp])})
            if len(fp) < 5:
                continue
            current = _grams(fp)
            for previous, other in prior:
                common = len(current & other)
                if not common:
                    continue
                score = common / len(current | other)
                maximum = max(maximum, score)
                if score >= 0.85:
                    near.append({"id": row["id"], "text": value, "previous": previous,
                                 "jaccard": round(score, 4)})
    if direct:
        raise ValueError(f"Holdout overlaps existing data: {direct[:5]}")
    if near:
        raise ValueError(f"Holdout near-duplicates existing data: {near[:5]}")

    payload = "".join(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n" for row in rows)
    data_path.write_text(payload, encoding="utf-8")
    try:
        dataset_label = str(data_path.relative_to(ROOT))
    except ValueError:
        dataset_label = str(data_path)
    info = {
        "dataset": dataset_label, "schema_version": "0.1",
        "role": "sealed_blind_holdout", "generator_seed": SHUFFLE_SEED,
        "records": len(rows), "sha256": hashlib.sha256(payload.encode()).hexdigest(),
        "decisions": dict(sorted(Counter(row["expected"]["decision"] for row in rows).items())),
        "groups": dict(sorted(Counter(row["group_id"] for row in rows).items())),
        "compound_error_cases": sum(len(row["expected"]["edits"]) > 1 for row in rows),
        "review_status": "generated_validated", "human_reviewed": False, "expert_reviewed": False,
        "contamination_audit": {
            "exact_normalized_matches": 0, "near_dataset_matches_at_or_above_0_85": 0,
            "max_dataset_character_3gram_jaccard": round(maximum, 4),
            "source_sha256": source_hashes,
            "limitation": "Exact and character 3-gram checks do not exclude paraphrase or pretraining overlap.",
        },
        "seal_policy": "Do not run a model until v0.2-F data, adapter, selector and thresholds are committed.",
    }
    manifest_path.write_text(json.dumps(info, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return info


if __name__ == "__main__":
    print(json.dumps(build(), ensure_ascii=False, indent=2))
