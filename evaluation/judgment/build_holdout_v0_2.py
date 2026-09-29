"""Build a new, untouched judgment holdout; never query a model here."""

from __future__ import annotations

from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import random

from evaluation.judgment.build_holdout import _edit, _corrected
from evaluation.judgment.dataset import sentence_fingerprint, validate_records


ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "evaluation/judgment/holdout_v0.2.jsonl"
MANIFEST = ROOT / "evaluation/judgment/holdout_v0.2.manifest.json"
SOURCE_FILES = (
    ROOT / "evaluation/judgment/seed_v0.1.jsonl",
    ROOT / "evaluation/judgment/holdout_v0.1.jsonl",
    ROOT / "training/judgment/data/pilot_v0.2_c.jsonl",
)
SHUFFLE_SEED = 20260922


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _row(number: int, text: str, decision: str, group: str, *, context=None,
         level="N5", edits=None, reason=None, tags=()):
    edits = edits or []
    corrected = _corrected(text, edits) if decision == "needs_correction" else text
    default_reasons = {
        "acceptable": "주어진 문맥에서는 문법 교정이 필요하지 않습니다.",
        "needs_correction": "의미와 문체를 유지하면서 표시된 문법 오류만 고칩니다.",
        "insufficient_evidence": "발화가 누락되었거나 대상 언어의 판단 근거가 부족해 교정문을 추측하지 않습니다.",
    }
    return {
        "schema_version": "0.1", "id": f"JH-{number + 150:04d}", "split": "holdout_eval",
        "group_id": group, "tags": [group, f"decision:{decision}", *tags],
        "input": {"text": text, "context": context, "learner_level": level},
        "expected": {"decision": decision, "corrected_text": corrected, "edits": edits,
                     "reason_ko": reason or default_reasons[decision]},
        "accepted_corrections": [corrected] if decision == "needs_correction" else [],
        "provenance": {"kind": "deterministic_template", "source_id": f"holdout-v0.2:{number:04d}",
                       "external_text_used": False},
        "review": {"status": "generated_validated", "reviewed_at": None},
    }


def build_records() -> list[dict]:
    rows = []

    def add(text, decision, group, **kwargs):
        rows.append(_row(len(rows) + 1, text, decision, group, **kwargs))

    routes = [
        "川沿いの道を一時間歩きました。", "港の遊歩道を夕暮れに歩きました。",
        "桜並木を自転車で通りました。", "長い廊下を静かに歩きました。",
        "石畳の通りを歩いて帰りました。", "湖の周りを一周走りました。",
        "細い山道を慎重に登りました。", "駅前の広場を通って帰りました。",
        "海沿いの道を朝早く走りました。", "地下の通路を歩いて出口へ向かいました。",
    ]
    for text in routes:
        add(text, "acceptable", "route_wo_ok", tags=("boundary_case", "route_wo"))

    casual = [
        "明日、先に帰るね。", "今夜は家で食べるよ。", "その映画、もう見た？",
        "あとで電話してもいい？", "昨日はずっと本を読んでた。", "これ、私が持っていくよ。",
        "駅に着いたら連絡するね。", "今日は少し早く寝る。", "その話、あとで聞かせて。",
        "うん、週末なら行けるよ。",
    ]
    for text in casual:
        add(text, "acceptable", "casual_style_ok", context="친한 친구와의 일상 대화",
            tags=("boundary_case", "check:style_preserve"))

    existences = [
        ("資料室の棚", "古い地図"), ("保健室の机", "体温計"),
        ("玄関の横", "傘立て"), ("教室の後ろ", "大きな時計"),
        ("台所の引き出し", "栓抜き"), ("公民館の入口", "案内図"),
        ("事務所の壁", "予定表"), ("車庫の奥", "工具箱"),
        ("図書室の窓際", "観葉植物"), ("駅の改札口", "案内板"),
    ]
    for place, thing in existences:
        add(f"{place}に{thing}があります。", "acceptable", "existence_ni_ok")

    adjective_pairs = [
        ("昨日の坂道", "急しかった"), ("先週の会議", "短かった"),
        ("今朝の水", "冷たかった"), ("先日の嵐", "激しかった"),
        ("あの部屋", "狭かった"), ("去年の夏", "暑かった"),
        ("昨日の夕食", "おいしかった"), ("今朝の空", "暗かった"),
        ("その問題", "難しかった"), ("この靴", "安かった"),
    ]
    for subject, predicate in adjective_pairs:
        add(f"{subject}は{predicate}です。", "acceptable", "adjective_past_ok")

    fillers = [
        "ええと、次の角を右に曲がります。", "あのう、予約の時間を確認したいです。",
        "ええと、この書類はどこに出しますか。", "あの、もう一枚もらえますか。",
        "その、今日は少し遅れます。",
    ]
    for text in fillers:
        add(text, "acceptable", "filler_ok", tags=("boundary_case", "check:filler_preserve"))
    stt = [
        "弟わ明日も学校に行きます。", "映画お昨日見ました。",
        "今日わ図書室にいます。", "手紙お母に送りました。",
        "ぼくわ午後から働きます。",
    ]
    for text in stt:
        add(text, "acceptable", "stt_orthography_boundary",
            context="일본어 말하기를 STT로 전사한 결과; 원음과 대안 전사는 없음",
            reason="조사 발음과 전사 표기는 원음 없이 학습자의 문법 오류로 확정하지 않습니다.",
            tags=("boundary_case", "check:orthography_candidate", "check:attribution_unknown"))

    destinations = [
        ("明後日は眼科を行きます。", "眼科を", "眼科に"),
        ("来月、区民館を行きます。", "区民館を", "区民館に"),
        ("午後は銀行を行きます。", "銀行を", "銀行に"),
        ("来週、植物園を行きます。", "植物園を", "植物園に"),
        ("土曜日に水泳教室を行きます。", "水泳教室を", "水泳教室に"),
        ("明日は歯科医院を行きます。", "歯科医院を", "歯科医院に"),
        ("夕方、郵便局を行きます。", "郵便局を", "郵便局に"),
        ("週末に科学館を行きます。", "科学館を", "科学館に"),
        ("朝から交番を行きます。", "交番を", "交番に"),
        ("来週は市民病院を行きます。", "市民病院を", "市民病院に"),
    ]
    for text, source, replacement in destinations:
        add(text, "needs_correction", "destination_particle_error",
            edits=[_edit(text, source, replacement, "particle_misuse")])

    for place, thing in existences:
        text = f"{place}で{thing}があります。"
        add(text, "needs_correction", "existence_de_error",
            edits=[_edit(text, f"{place}で", f"{place}に", "particle_misuse")])

    for subject, predicate in adjective_pairs:
        source = predicate.replace("かった", "いかった")
        text = f"{subject}は{source}です。"
        add(text, "needs_correction", "adjective_past_error",
            edits=[_edit(text, source, predicate, "adjective_conjugation")])

    verbs = [
        ("毎朝、玄関を掃くます。", "掃くます", "掃きます"),
        ("昨日、切符を買うました。", "買うました", "買いました"),
        ("ここに住所を書くてください。", "書くて", "書いて"),
        ("先ほど、先生に会うました。", "会うました", "会いました"),
        ("少しだけ待つてください。", "待つて", "待って"),
        ("毎晩、窓を閉めるます。", "閉めるます", "閉めます"),
        ("昨日、家で休むました。", "休むました", "休みました"),
        ("この道を渡るてください。", "渡るて", "渡って"),
        ("先週、庭に花を植えるました。", "植えるました", "植えました"),
        ("毎週、父に電話するます。", "電話するます", "電話します"),
    ]
    for text, source, replacement in verbs:
        add(text, "needs_correction", "verb_conjugation_error",
            edits=[_edit(text, source, replacement, "verb_conjugation")])

    compound = [
        ("昨日", "工房", "絵", "描くました", "描きました"),
        ("先週", "喫茶室", "手紙", "書くました", "書きました"),
        ("昨日", "体育館", "友達", "待つました", "待ちました"),
        ("今朝", "台所", "パン", "焼くました", "焼きました"),
        ("昨日", "図工室", "模型", "作るました", "作りました"),
        ("先月", "駅の売店", "雑誌", "買うました", "買いました"),
        ("昨夜", "書斎", "小説", "読むました", "読みました"),
        ("午後", "学習室", "漢字", "練習するました", "練習しました"),
        ("昨日", "調理室", "夕飯", "作るました", "作りました"),
        ("今朝", "書店", "新刊", "探すました", "探しました"),
    ]
    for time, place, obj, wrong, correct in compound:
        text = f"{time}、{place}を{obj}を{wrong}。"
        edits = [_edit(text, f"{place}を", f"{place}で", "particle_misuse"),
                 _edit(text, wrong, correct, "verb_conjugation")]
        add(text, "needs_correction", "compound_particle_verb_error",
            level="N4", edits=edits, tags=("compound_error",))

    foreign = [
        "I forgot my umbrella at home.", "The train arrived early today.",
        "Can you open the window?", "My sister bought a blue bag.",
        "오늘 오후에 도서관에 갑니다.", "저는 어제 커피를 마셨어요.",
        "다음 주에 친구를 만날 거예요.", "이 책은 생각보다 어렵습니다.",
    ]
    for text in foreign:
        add(text, "insufficient_evidence", "foreign_language_boundary",
            tags=("boundary_case", "no_translation_as_correction"))
    incomplete = [
        "もし来週の予定が変わったら", "昨日、大学の先生に", "この機械を使ったのは",
        "帰り道で見つけたのは", "電車が遅れていたので", "私が探している書類は",
        "あの店で買いたかったのは", "次の休みに行こうと思うのは",
    ]
    for text in incomplete:
        add(text, "insufficient_evidence", "incomplete_utterance",
            tags=("boundary_case", "no_guessing"))
    missing = [
        "来週は［聞き取れない］で働きます。", "昨日、［雑音］を読みました。",
        "昨夜の外は［聞き取れない］かったです。", "［雑音］に行きました。",
    ]
    for text in missing:
        add(text, "insufficient_evidence", "missing_audio_span",
            tags=("boundary_case", "no_guessing"))

    if Counter(row["expected"]["decision"] for row in rows) != {
        "acceptable": 50, "needs_correction": 50, "insufficient_evidence": 20,
    }:
        raise AssertionError("Unexpected holdout distribution")
    random.Random(SHUFFLE_SEED).shuffle(rows)
    validate_records(rows)
    return rows


def _source_strings() -> tuple[dict[str, set[str]], dict[str, str]]:
    corpus = defaultdict(set)
    hashes = {}
    for path in SOURCE_FILES:
        hashes[str(path.relative_to(ROOT))] = _sha256(path)
        for line in path.read_text(encoding="utf-8").splitlines():
            row = json.loads(line)
            values = [row["input"]["text"], row["expected"]["corrected_text"],
                      *row["accepted_corrections"]]
            for value in values:
                if len(fp := sentence_fingerprint(value)) >= 4:
                    corpus[fp].add(str(path.relative_to(ROOT)))
    rag = ROOT / "rag_data"
    for path in sorted(rag.rglob("*.json")):
        hashes[str(path.relative_to(ROOT))] = _sha256(path)
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
            if len(fp := sentence_fingerprint(value)) >= 4:
                corpus[fp].add(str(path.relative_to(ROOT)))
    return corpus, hashes


def _near_dataset_matches(rows: list[dict], threshold: float = 0.85) -> tuple[list[dict], float]:
    """Audit character 3-gram overlap against earlier training/evaluation text."""
    historical = set()
    for path in SOURCE_FILES:
        for line in path.read_text(encoding="utf-8").splitlines():
            row = json.loads(line)
            historical.update((row["input"]["text"], row["expected"]["corrected_text"],
                               *row["accepted_corrections"]))

    def grams(value: str) -> set[str]:
        return {value[index:index + 3] for index in range(len(value) - 2)}

    indexed = [(value, grams(fp)) for value in historical
               if len(fp := sentence_fingerprint(value)) >= 5]
    near, highest = [], 0.0
    for row in rows:
        values = {row["input"]["text"], row["expected"]["corrected_text"],
                  *row["accepted_corrections"]}
        for value in values:
            fp = sentence_fingerprint(value)
            if len(fp) < 5:
                continue
            current = grams(fp)
            for previous, other in indexed:
                common = len(current & other)
                if not common:
                    continue
                score = common / len(current | other)
                highest = max(highest, score)
                if score >= threshold:
                    near.append({"id": row["id"], "text": value,
                                 "previous": previous, "jaccard": round(score, 4)})
    return near, round(highest, 4)


def build(data_path: Path = DATA, manifest_path: Path = MANIFEST) -> dict:
    rows = build_records()
    corpus, source_hashes = _source_strings()
    matches = []
    for row in rows:
        values = {row["input"]["text"], row["expected"]["corrected_text"],
                  *row["accepted_corrections"]}
        for value in values:
            fp = sentence_fingerprint(value)
            if len(fp) >= 4 and fp in corpus:
                matches.append({"id": row["id"], "text": value, "sources": sorted(corpus[fp])})
    if matches:
        raise ValueError(f"Holdout overlaps existing data: {matches[:5]}")
    near, max_jaccard = _near_dataset_matches(rows)
    if near:
        raise ValueError(f"Holdout near-duplicates existing datasets: {near[:5]}")
    payload = "".join(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n" for row in rows)
    data_path.write_text(payload, encoding="utf-8")
    info = {
        "dataset": str(DATA.relative_to(ROOT)), "schema_version": "0.1",
        "role": "sealed_blind_holdout", "generator_seed": SHUFFLE_SEED,
        "records": len(rows), "sha256": hashlib.sha256(payload.encode("utf-8")).hexdigest(),
        "decisions": dict(sorted(Counter(row["expected"]["decision"] for row in rows).items())),
        "groups": dict(sorted(Counter(row["group_id"] for row in rows).items())),
        "compound_error_cases": sum(len(row["expected"]["edits"]) > 1 for row in rows),
        "review_status": "generated_validated", "human_reviewed": False, "expert_reviewed": False,
        "contamination_audit": {
            "exact_normalized_matches": 0, "normalization": "NFKC, strip whitespace/punctuation",
            "minimum_fingerprint_length": 4, "source_sha256": source_hashes,
            "near_dataset_matches_at_or_above_0_85": 0,
            "max_dataset_character_3gram_jaccard": max_jaccard,
            "limitation": "Exact match includes RAG JSON; near-duplicate audit covers three prior datasets only. Paraphrase and pretraining overlap are not excluded.",
        },
        "seal_policy": "Do not inspect model predictions until v0.2-D data, adapter and evaluation protocol are fixed; evaluate once for final comparison.",
    }
    manifest_path.write_text(json.dumps(info, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return info


if __name__ == "__main__":
    print(json.dumps(build(), ensure_ascii=False, indent=2))
