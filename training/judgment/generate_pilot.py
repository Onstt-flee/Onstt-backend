"""Generate the deterministic 300-record judgment LoRA pilot dataset."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from training.judgment.data import exact_overlap, near_seed_overlap, summary, validate_records
from training.judgment.pilot_acceptable import add_acceptable_natural


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUTPUT = Path(__file__).with_name("data") / "pilot_v0.1.jsonl"
DEFAULT_MANIFEST = Path(__file__).with_name("data") / "pilot_v0.1.manifest.json"
LEXICON_SOURCE = Path(__file__).with_name("sources") / "qwen3_14b_lexicon_v0.1.json"
SEED_DATASET = ROOT / "evaluation" / "judgment" / "seed_v0.1.jsonl"
RAG_DIR = ROOT / "rag_data"

GENERATOR_MODEL = "Qwen/Qwen3-14B"
GENERATOR_REVISION = "40c069824f4251a91eefaf281ebe4c544efd3e18"
GENERATOR_PROMPT_SHA256 = "33ebd26a4dfa94ed46118c9a0e9c04dcc62c561327b7de34e09279a5a68077f6"

DEV_FAMILIES = {
    "acceptable_route", "acceptable_filler", "acceptable_short_answer",
    "particle_destination", "verb_polite_nonpast", "adjective_past",
    "copula_i_adjective", "insufficient_truncated",
}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


class Builder:
    def __init__(self) -> None:
        self.records: list[dict] = []

    def _base(self, family: str, text: str, context: str | None, tags: list[str]) -> dict:
        index = len(self.records)
        level = "N4" if index % 10 in {2, 5, 8} else "N5"
        return {
            "schema_version": "0.1",
            "id": f"JT-{index + 1:04d}",
            "split": "pilot_dev" if family in DEV_FAMILIES else "pilot_train",
            "template_family_id": family,
            "tags": tags,
            "input": {"text": text, "context": context, "learner_level": level},
            "provenance": {
                "kind": "local_model_assisted",
                "source_id": "qwen3_14b_lexicon_v0.1",
                "external_text_used": False,
                "generator_model": GENERATOR_MODEL,
                "generator_revision": GENERATOR_REVISION,
                "generator_prompt_sha256": GENERATOR_PROMPT_SHA256,
            },
            "review": {"status": "provisional", "reviewed_at": None},
        }

    def acceptable(self, family: str, text: str, context: str | None, reason: str) -> None:
        record = self._base(family, text, context, ["acceptable", family])
        record["expected"] = {
            "decision": "acceptable", "corrected_text": text, "edits": [], "reason_ko": reason,
        }
        record["accepted_corrections"] = []
        self.records.append(record)

    def insufficient(self, family: str, text: str, context: str | None, reason: str) -> None:
        record = self._base(family, text, context, ["insufficient_evidence", family])
        record["expected"] = {
            "decision": "insufficient_evidence", "corrected_text": text,
            "edits": [], "reason_ko": reason,
        }
        record["accepted_corrections"] = []
        self.records.append(record)

    def correction(
        self,
        family: str,
        text: str,
        replacements: list[tuple[str, str, str]],
        reason: str,
        context: str | None = None,
    ) -> None:
        edits = []
        search_from = 0
        for source, replacement, error_type in replacements:
            start = text.find(source, search_from)
            if start < 0:
                raise ValueError(f"Cannot find {source!r} in {text!r}")
            end = start + len(source)
            edits.append({
                "start": start, "end": end, "source": source,
                "replacement": replacement, "error_type": error_type,
            })
            search_from = end
        corrected = text
        for edit in reversed(edits):
            corrected = corrected[:edit["start"]] + edit["replacement"] + corrected[edit["end"]:]
        record = self._base(
            family, text, context,
            ["needs_correction", family, *sorted({item[2] for item in replacements})],
        )
        record["expected"] = {
            "decision": "needs_correction", "corrected_text": corrected,
            "edits": edits, "reason_ko": reason,
        }
        record["accepted_corrections"] = [corrected]
        self.records.append(record)


def _single_corrections(builder: Builder) -> None:
    places = ["公園", "駅", "スーパー", "図書館", "カフェ", "病院", "学校", "レストラン", "コンビニ", "ホテル", "神社", "駅前", "銀行", "会社", "空港", "郵便局", "市役所"]

    for place in places[:6]:
        builder.correction("particle_destination", f"明後日は{place}を行きます。", [("を行", "に行", "particle_misuse")], "목적지를 나타내는 조사로 고칩니다.")
    action_pairs = [("学校", "本"), ("売店", "傘"), ("コンビニ", "飲み物"), ("書店", "雑誌"), ("神社", "お守り"), ("駅前", "弁当")]
    for place, obj in action_pairs:
        builder.correction("particle_action_location", f"昨日は{place}を{obj}を買いました。", [(f"{place}を", f"{place}で", "particle_misuse")], "구매가 일어난 장소에는 で를 사용합니다.")
    existence_pairs = [("学校", "図書室"), ("ホテル", "荷物"), ("銀行", "ATM"), ("会社", "会議室"), ("市役所", "相談窓口")]
    for place, obj in existence_pairs:
        builder.correction("particle_existence", f"{place}で{obj}があります。", [(f"{place}で", f"{place}に", "particle_misuse")], "존재 장소에는 に를 사용합니다.")

    verb_sets = [
        ("毎朝、手紙を書きくます。", "書きくます", "書きます"),
        ("週末に服を買うます。", "買うます", "買います"),
        ("駅で友達を待つます。", "待つます", "待ちます"),
        ("先生の話を聞くます。", "聞くます", "聞きます"),
        ("日本語で話すます。", "話すます", "話します"),
        ("公園で遊ぶます。", "遊ぶます", "遊びます"),
        ("昨日、手紙を書きくました。", "書きくました", "書きました"),
        ("先週、服を買うました。", "買うました", "買いました"),
        ("駅で友達を待つました。", "待つました", "待ちました"),
        ("先生の話を聞くました。", "聞くました", "聞きました"),
        ("日本語で話すました。", "話すました", "話しました"),
        ("公園で遊ぶました。", "遊ぶました", "遊びました"),
        ("この用紙に住所を書きてください。", "書きて", "書いて"),
        ("少し待ちてください。", "待ちて", "待って"),
        ("この本を読みてください。", "読みて", "読んで"),
        ("もう一度話すてください。", "話すて", "話して"),
        ("駅まで歩くてください。", "歩くて", "歩いて"),
    ]
    for index, (text, source, replacement) in enumerate(verb_sets):
        family = ("verb_polite_nonpast" if index < 6 else "verb_polite_past" if index < 12 else "verb_te_form")
        builder.correction(family, text, [(source, replacement, "verb_conjugation")], "동사의 활용 형태를 문형에 맞게 고칩니다.")

    adjective_sets = [
        ("昨日は寒いかったです。", "寒いかった", "寒かった"),
        ("料理は美味しいかったです。", "美味しいかった", "美味しかった"),
        ("鞄は重いかったです。", "重いかった", "重かった"),
        ("試験は難しいかったです。", "難しいかった", "難しかった"),
        ("旅行は楽しいかったです。", "楽しいかった", "楽しかった"),
        ("部屋は暑いかったです。", "暑いかった", "暑かった"),
        ("この時計は高いくないです。", "高いくない", "高くない"),
        ("道は長いくないです。", "長いくない", "長くない"),
        ("今日は忙しいくないです。", "忙しいくない", "忙しくない"),
        ("この服は安いくないです。", "安いくない", "安くない"),
        ("荷物は大きいくないです。", "大きいくない", "大きくない"),
        ("駅は遠いくないです。", "遠いくない", "遠くない"),
        ("この店は安いて便利です。", "安いて", "安くて"),
        ("今日は寒いて大変です。", "寒いて", "寒くて"),
        ("道は長いて暗いです。", "長いて", "長くて"),
        ("鞄は軽いて便利です。", "軽いて", "軽くて"),
        ("料理は辛いて美味しいです。", "辛いて", "辛くて"),
    ]
    for index, (text, source, replacement) in enumerate(adjective_sets):
        family = "adjective_past" if index < 6 else "adjective_negative" if index < 12 else "adjective_connection"
        builder.correction(family, text, [(source, replacement, "adjective_conjugation")], "い형용사의 활용을 문형에 맞게 고칩니다.")

    copula_sets = [
        ("今朝は寒いだです。", "いだです", "いです"),
        ("この鞄は大きいだです。", "いだです", "いです"),
        ("料理は美味しいだです。", "いだです", "いです"),
        ("駅は遠いだです。", "いだです", "いです"),
        ("この服は安いだです。", "いだです", "いです"),
        ("道は長いだです。", "いだです", "いです"),
        ("この町は静かなです。", "静かなです", "静かです"),
        ("先生は元気なです。", "元気なです", "元気です"),
        ("問題は簡単なです。", "簡単なです", "簡単です"),
        ("この店は有名なです。", "有名なです", "有名です"),
        ("説明は自然なです。", "自然なです", "自然です"),
        ("今日は特別なです。", "特別なです", "特別です"),
        ("私は旅行が好きだです。", "好きだです", "好きです"),
        ("妹は音楽が好きだです。", "好きだです", "好きです"),
        ("友達は映画が好きだです。", "好きだです", "好きです"),
        ("父は料理が好きだです。", "好きだです", "好きです"),
        ("先生は読書が好きだです。", "好きだです", "好きです"),
    ]
    for index, (text, source, replacement) in enumerate(copula_sets):
        family = "copula_i_adjective" if index < 6 else "copula_na_adjective" if index < 12 else "copula_preference"
        builder.correction(family, text, [(source, replacement, "copula_conjugation")], "서술어의 정중 종결 형태를 올바르게 고칩니다.")

    modifier_sets = [
        ("静か町に住んでいます。", "静か町", "静かな町"),
        ("有名店で食べました。", "有名店", "有名な店"),
        ("元気子どもが遊んでいます。", "元気子ども", "元気な子ども"),
        ("簡単問題を解きました。", "簡単問題", "簡単な問題"),
        ("特別日になりました。", "特別日", "特別な日"),
        ("自然日本語を話します。", "自然日本語", "自然な日本語"),
        ("新しい安いな時計を買いました。", "安いな時計", "安い時計"),
        ("大きいな鞄を持っています。", "大きいな鞄", "大きい鞄"),
        ("美味しいな料理を食べました。", "美味しいな料理", "美味しい料理"),
        ("長いな道を歩きました。", "長いな道", "長い道"),
        ("寒いな朝でした。", "寒いな朝", "寒い朝"),
        ("楽しいな旅行でした。", "楽しいな旅行", "楽しい旅行"),
        ("これは先生を本です。", "先生を本", "先生の本"),
        ("あれは友達を傘です。", "友達を傘", "友達の傘"),
        ("これは父を時計です。", "父を時計", "父の時計"),
        ("それは妹を鞄です。", "妹を鞄", "妹の鞄"),
        ("これは店をカードです。", "店をカード", "店のカード"),
    ]
    for index, (text, source, replacement) in enumerate(modifier_sets):
        family = "modifier_na_missing" if index < 6 else "modifier_i_extra_na" if index < 12 else "modifier_noun_link"
        builder.correction(family, text, [(source, replacement, "modifier_connection")], "명사를 수식하거나 연결하는 형태를 고칩니다.")

    tense_sets = [
        ("昨日は図書館で勉強します。", "勉強します", "勉強しました"),
        ("先週は東京へ行きます。", "行きます", "行きました"),
        ("去年は日本語を習います。", "習います", "習いました"),
        ("一時間前に昼ご飯を食べます。", "食べます", "食べました"),
        ("昨夜は映画を見ます。", "見ます", "見ました"),
        ("二日前はホテルに泊まります。", "泊まります", "泊まりました"),
        ("明日は病院へ行きました。", "行きました", "行きます"),
        ("来週は試験を受けました。", "受けました", "受けます"),
        ("来年は京都に住みました。", "住みました", "住みます"),
        ("一時間後に出発しました。", "出発しました", "出発します"),
        ("明日の夜は友達に会いました。", "会いました", "会います"),
        ("来月は新しい仕事を始めました。", "始めました", "始めます"),
        ("旅行は明日始まりました。", "始まりました", "始まります"),
        ("会議は来週終わりました。", "終わりました", "終わります"),
        ("工事は来年始まりました。", "始まりました", "始まります"),
        ("説明会は一時間後に始まりました。", "始まりました", "始まります"),
        ("イベントは今夜始まりました。", "始まりました", "始まります"),
    ]
    for index, (text, source, replacement) in enumerate(tense_sets):
        family = "tense_past_present" if index < 6 else "tense_future_past" if index < 12 else "tense_contextual"
        builder.correction(family, text, [(source, replacement, "tense_mismatch")], "명시된 시간 표현과 서술어 시제를 일치시킵니다.")


def _compound_corrections(builder: Builder) -> None:
    particle_verb = [
        ("昨日は学校を本を読むました。", [("学校を", "学校で", "particle_misuse"), ("読むました", "読みました", "verb_conjugation")]),
        ("先週は図書館を新聞を読むました。", [("図書館を", "図書館で", "particle_misuse"), ("読むました", "読みました", "verb_conjugation")]),
        ("昨日は店を服を買うました。", [("店を", "店で", "particle_misuse"), ("買うました", "買いました", "verb_conjugation")]),
        ("先週は公園を友達と話すました。", [("公園を", "公園で", "particle_misuse"), ("話すました", "話しました", "verb_conjugation")]),
        ("昨日は駅を先生を待つました。", [("駅を", "駅で", "particle_misuse"), ("待つました", "待ちました", "verb_conjugation")]),
        ("先週はカフェを手紙を書くました。", [("カフェを", "カフェで", "particle_misuse"), ("書くました", "書きました", "verb_conjugation")]),
    ]
    for text, edits in particle_verb:
        builder.correction("compound_particle_verb", text, edits, "장소 조사와 동사 과거 활용을 각각 고칩니다.")

    modifier_location = [
        ("白い小さいな犬が庭でいます。", [("小さいな", "小さい", "modifier_connection"), ("庭で", "庭に", "particle_misuse")]),
        ("大きいな鞄が部屋であります。", [("大きいな", "大きい", "modifier_connection"), ("部屋で", "部屋に", "particle_misuse")]),
        ("静か町で公園があります。", [("静か", "静かな", "modifier_connection"), ("町で", "町に", "particle_misuse")]),
        ("有名店で時計があります。", [("有名", "有名な", "modifier_connection"), ("店で", "店に", "particle_misuse")]),
        ("安いなホテルでカフェがあります。", [("安いな", "安い", "modifier_connection"), ("ホテルで", "ホテルに", "particle_misuse")]),
        ("自然日本語の本が机であります。", [("自然日本語", "自然な日本語", "modifier_connection"), ("机で", "机に", "particle_misuse")]),
    ]
    for text, edits in modifier_location:
        builder.correction("compound_modifier_location", text, edits, "명사 수식과 존재 장소 조사를 모두 고칩니다.")

    adjective_tense = [
        ("昨日の料理は美味しいかったので、明日も食べました。", [("美味しいかった", "美味しかった", "adjective_conjugation"), ("明日も食べました", "明日も食べます", "tense_mismatch")]),
        ("昨日は寒いかったので、明日は家にいました。", [("寒いかった", "寒かった", "adjective_conjugation"), ("明日は家にいました", "明日は家にいます", "tense_mismatch")]),
        ("先週は忙しいかったですが、来週は休みました。", [("忙しいかった", "忙しかった", "adjective_conjugation"), ("来週は休みました", "来週は休みます", "tense_mismatch")]),
        ("昨日の鞄は重いかったので、明日は使いませんでした。", [("重いかった", "重かった", "adjective_conjugation"), ("明日は使いませんでした", "明日は使いません", "tense_mismatch")]),
        ("去年の旅行は楽しいかったので、来年も行きました。", [("楽しいかった", "楽しかった", "adjective_conjugation"), ("来年も行きました", "来年も行きます", "tense_mismatch")]),
        ("昨夜は暑いかったですが、明日は涼しかったです。", [("暑いかった", "暑かった", "adjective_conjugation"), ("明日は涼しかったです", "明日は涼しいです", "tense_mismatch")]),
    ]
    for text, edits in adjective_tense:
        if any(source == replacement for source, replacement, _ in edits):
            continue
        builder.correction("compound_adjective_tense", text, edits, "형용사 활용과 시간에 맞지 않는 시제를 모두 고칩니다.")


def _add_insufficient(builder: Builder) -> None:
    silence = ["（無言）", "［無音］", "……（沈黙）", "（返答なし）", "［発話なし］", "……？", "（考え中）", "［沈黙が続く］", "（声なし）"]
    for text in silence:
        builder.insufficient("insufficient_silence", text, "실제 일본어 발화가 기록되지 않았습니다.", "판단할 일본어 발화 내용이 없습니다.")
    fillers = ["えっと……", "あのですね……", "うーん……", "その……", "まあ……", "ええと、その……", "あのう……", "そうですね……", "ちょっと、その……"]
    for text in fillers:
        builder.insufficient("insufficient_filler_only", text, "머뭇거림 뒤의 본문이 녹음되지 않았습니다.", "필러만 있고 판단할 명제가 없습니다.")
    truncated = [
        "今朝、駅で先生に", "来週、友達と映画を", "この料理を作ったのは", "もし時間があったら", "昨日、病院から",
        "日本に来てからずっと", "私が一番好きなのは", "雨が降らなければ", "その本を読んだあとで",
    ]
    for text in truncated:
        builder.insufficient("insufficient_truncated", text, "녹음이 문장 중간에서 종료되었습니다.", "누락된 서술어나 절을 추측하지 않습니다.")
    missing = ["今日は［音声欠落］です。", "明日は［判別不能］へ行きます。", "［環境音のみ］", "駅で［一部欠落］を買いました。", "昨日は［音声なし］。", "［録音失敗］", "先生が［聞き取り不能］と言いました。", "この本は［雑音区間］です。", "［発話区間なし］"]
    for text in missing:
        builder.insufficient("insufficient_missing_audio", text, "대괄호 부분의 원음과 대안 전사가 제공되지 않았습니다.", "누락되거나 식별할 수 없는 구간을 임의로 채우지 않습니다.")
    foreign = ["I will visit the library tomorrow.", "Please wait here for a moment.", "My friend bought a new camera.", "We studied Japanese last night.", "내일은 병원에 갈 예정입니다.", "친구와 도서관에서 공부했습니다.", "이 가방은 생각보다 무겁습니다.", "다시 한번 천천히 말해주세요.", "오늘 저녁에는 집에서 쉽니다."]
    for text in foreign:
        builder.insufficient("insufficient_out_of_scope", text, None, "일본어 문법 판단 범위 밖의 입력이며 번역문을 정답으로 만들지 않습니다.")


def build_records() -> list[dict]:
    with LEXICON_SOURCE.open(encoding="utf-8") as stream:
        lexicon = json.load(stream)["accepted_after_manual_screening"]
    builder = Builder()
    add_acceptable_natural(builder, lexicon)
    _single_corrections(builder)
    _compound_corrections(builder)
    _add_insufficient(builder)
    validate_records(builder.records)
    return builder.records


def write_jsonl(path: Path, records: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as stream:
        for record in records:
            stream.write(json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    args = parser.parse_args()
    records = build_records()
    if len(records) != 300:
        raise ValueError(f"Expected 300 records, got {len(records)}")
    write_jsonl(args.output, records)
    overlap = exact_overlap(records, seed_path=SEED_DATASET, rag_dir=RAG_DIR)
    if overlap["matches"]:
        raise ValueError(f"Exact seed/RAG overlap: {overlap['matches']}")
    manifest = {
        "schema_version": "0.1",
        "dataset_id": "judgment-pilot-v0.1",
        "created_at": "2026-09-13",
        "status": "provisional",
        "dataset_path": str(args.output.relative_to(ROOT)),
        "dataset_sha256": _sha256(args.output),
        "lexicon_source_path": str(LEXICON_SOURCE.relative_to(ROOT)),
        "lexicon_source_sha256": _sha256(LEXICON_SOURCE),
        "seed_eval_sha256": _sha256(SEED_DATASET),
        "summary": summary(records),
        "exact_seed_rag_overlap": overlap,
        "near_seed_overlap_threshold": 0.85,
        "near_seed_overlap_for_manual_review": near_seed_overlap(records, seed_path=SEED_DATASET),
        "generation_policy": {
            "model_role": "lexical_and_situation_drafts_only",
            "gold_labels_and_edits": "deterministic_templates_and_python_offsets",
            "external_text_used": False,
            "seed_eval_used_for_generation": False,
        },
    }
    args.manifest.parent.mkdir(parents=True, exist_ok=True)
    args.manifest.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "dataset": str(args.output), "manifest": str(args.manifest),
        "dataset_sha256": manifest["dataset_sha256"], **manifest["summary"],
        "near_seed_review_count": len(manifest["near_seed_overlap_for_manual_review"]),
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
