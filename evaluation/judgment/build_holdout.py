"""Build the sealed, deterministic blind holdout for judgment v0.2-C."""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import random
import sys
import unicodedata

from evaluation.judgment.dataset import validate_records

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUTPUT = Path(__file__).with_name("holdout_v0.1.jsonl")
DEFAULT_MANIFEST = Path(__file__).with_name("holdout_v0.1.manifest.json")
SEED = 20260917


def _edit(text, source, replacement, error_type, occurrence=0):
    starts = []
    start = 0
    while True:
        pos = text.find(source, start)
        if pos < 0:
            break
        starts.append(pos)
        start = pos + max(1, len(source))
    if occurrence >= len(starts):
        raise ValueError(f"{source!r} not found in {text!r}")
    pos = starts[occurrence]
    return {"start": pos, "end": pos + len(source), "source": source,
            "replacement": replacement, "error_type": error_type}


def _corrected(text, edits):
    result = text
    for edit in sorted(edits, key=lambda x: x["start"], reverse=True):
        result = result[:edit["start"]] + edit["replacement"] + result[edit["end"]:]
    return result


def _row(number, text, decision, *, context=None, level="N5", group="holdout_acceptable",
         reason="문법적으로 자연스러운 문장입니다.", edits=None, accepted=None, tags=()):
    edits = edits or []
    corrected = _corrected(text, edits) if decision == "needs_correction" else text
    return {
        "schema_version": "0.1", "id": f"JH-{number:04d}", "split": "holdout_eval",
        "group_id": group, "tags": [group, f"decision:{decision}", *tags],
        "input": {"text": text, "context": context, "learner_level": level},
        "expected": {"decision": decision, "corrected_text": corrected, "edits": edits, "reason_ko": reason},
        "accepted_corrections": accepted if accepted is not None else ([corrected] if decision == "needs_correction" else []),
        "provenance": {"kind": "deterministic_template", "source_id": f"holdout-v0.1:{number:04d}", "external_text_used": False},
        "review": {"status": "generated_validated", "reviewed_at": None},
    }


def build_records():
    rows = []
    n = 1
    # 60 correct items: standard grammar plus conversational, style and STT boundaries.
    places = ["美術館", "市役所", "薬局", "水族館", "郵便局", "体育館", "展望台", "交番", "港", "温泉"]
    transports = ["地下鉄", "自転車", "タクシー", "バス", "電車"]
    for i, place in enumerate(places):
        text = f"土曜日は{transports[i % 5]}で{place}に行きます。"
        rows.append(_row(n, text, "acceptable", group="holdout_particle_ok", tags=("normal_sentence",))); n += 1
    nouns = ["薬", "切符", "傘", "鍵", "地図", "資料", "花瓶", "荷物", "案内板", "自動販売機"]
    locs = ["引き出し", "受付", "玄関", "机の下", "棚の上", "会議室", "窓際", "廊下", "入口", "公園の奥"]
    for noun, loc in zip(nouns, locs):
        rows.append(_row(n, f"{loc}に{noun}があります。", "acceptable", group="holdout_existence_ok", tags=("normal_sentence",))); n += 1
    adjective = [
        "昨日の海はとても青かったです。", "この道は思ったより長くないです。", "駅前は静かで便利です。",
        "新しい靴は軽くて歩きやすいです。", "その説明は簡単ではありません。", "この箱は重かったです。",
        "庭がきれいになりました。", "値段は高くありませんでした。", "小さな声でも聞こえました。", "元気な子どもが走っています。",
    ]
    for text in adjective:
        rows.append(_row(n, text, "acceptable", level="N4", group="holdout_conjugation_ok", tags=("normal_sentence",))); n += 1
    conversational = [
        ("ええと、明日の集合は九時ですよね。", None, ("boundary_case", "check:filler_preserve")),
        ("あのう、この席は空いていますか。", None, ("boundary_case", "check:filler_preserve")),
        ("なんか温かいもの、飲む？", "친구에게 음료를 권하는 상황", ("boundary_case", "check:style_preserve")),
        ("もう宿題、終わったよ。", "친구와 대화하는 상황", ("boundary_case", "check:style_preserve")),
        ("今どこにいるの？", "친구에게 묻는 상황", ("boundary_case", "check:style_preserve")),
        ("すみません、少し考えさせてください。", None, ("boundary_case",)),
        ("はい、今日は参加できます。", "참석 가능 여부를 묻는 질문에 답함", ("boundary_case", "check:context_match")),
        ("奈良の博物館です。", "どこへ行きますか。", ("boundary_case", "check:context_match")),
        ("まだ決めていません。", "旅行の日程は決まりましたか。", ("boundary_case", "check:context_match")),
        ("昨日は病院に行きました。そして、薬をもらった。", "친구와의 자유로운 대화", ("boundary_case", "check:style_advisory")),
    ]
    for text, context, tags in conversational:
        rows.append(_row(n, text, "acceptable", context=context, level="N4", group="holdout_conversation_boundary", tags=tags)); n += 1
    orthography = [
        "ぼくわ明日も行きます。", "映画お見ました。", "妹わ高校生です。", "水おください。", "今日わ休みです。",
        "新聞お読みます。", "先生わ教室にいます。", "音楽お聞きました。", "これわ私のです。", "駅で友達お待ちます。",
    ]
    for text in orthography:
        rows.append(_row(n, text, "acceptable", context="일본어 말하기를 STT로 전사한 결과", group="holdout_stt_boundary",
                         reason="말하기 평가에서는 조사 발음과 전사 표기를 분리하므로 문법 교정을 확정하지 않습니다.",
                         tags=("boundary_case", "check:orthography_candidate", "check:attribution_unknown"))); n += 1
    short_context = [
        ("二枚です。", "切符は何枚必要ですか。"), ("自分で持てます。", "荷物を持ちましょうか。"),
        ("再来週の火曜日です。", "試験はいつですか。"), ("駅前の書店です。", "待ち合わせ場所はどこですか。"),
        ("はい、開けてください。", "窓を開けましょうか。"), ("いいえ、まだです。", "昼ご飯は食べましたか。"),
        ("青いほうです。", "どちらの傘ですか。"), ("三人です。", "何名様ですか。"),
        ("歩いて十分です。", "駅までどのくらいですか。"), ("日曜日なら行けます。", "いつ参加できますか。"),
    ]
    for text, context in short_context:
        rows.append(_row(n, text, "acceptable", context=context, group="holdout_context_ok", tags=("boundary_case", "check:context_match"))); n += 1

    # 60 single-error minimal corrections: ten per supported error type.
    particle_cases = [
        ("来週は区役所を行きます。", "を", "に"), ("喫茶店にコーヒーを飲みました。", "に", "で"),
        ("箱の中で手紙があります。", "で", "に"), ("これは父を眼鏡です。", "を", "の"),
        ("毎晩十一時で寝ます。", "で", "に"), ("駅に新聞を買いました。", "に", "で"),
        ("庭で猫がいます。", "で", "に"), ("春を桜が咲きます。", "を", "に"),
        ("妹でプレゼントをあげました。", "で", "に"), ("空港からホテルへタクシーに行きます。", "に", "で"),
    ]
    single_sets = [("particle_misuse", particle_cases, "조사 선택을 최소한으로 바로잡아야 합니다."),
        ("verb_conjugation", [
            ("毎朝、新聞を読むます。", "読むます", "読みます"), ("昨日は早く帰るました。", "帰るました", "帰りました"),
            ("ここに座るてください。", "座るて", "座って"), ("窓を開けるてください。", "開けるて", "開けて"),
            ("弟は速く泳ぐます。", "泳ぐます", "泳ぎます"), ("先週、友達と話すました。", "話すました", "話しました"),
            ("名前を書くてください。", "書くて", "書いて"), ("音楽を聞くながら歩きます。", "聞くながら", "聞きながら"),
            ("今日は料理を作りませんだ。", "作りませんだ", "作りませんでした"), ("駅まで走りたいです。", "走りたい", "走りたい"),
        ], "동사 활용을 문맥에 맞게 고쳐야 합니다."),
        ("adjective_conjugation", [
            ("昨日の試験は難しいかったです。", "難しいかった", "難しかった"), ("この机は低いくないです。", "低いくない", "低くない"),
            ("その映画は長いくて退屈でした。", "長いくて", "長くて"), ("朝は寒いくありません。", "寒いく", "寒く"),
            ("遠足は嬉しいかったです。", "嬉しいかった", "嬉しかった"), ("この料理は辛いいです。", "辛いい", "辛い"),
            ("昨日は忙しいくなかったです。", "忙しいく", "忙しく"), ("部屋は明るいくて広いです。", "明るいくて", "明るくて"),
            ("その鞄は軽いいです。", "軽いい", "軽い"), ("道は狭いかったです。", "狭いかった", "狭かった"),
        ], "い형용사의 활용을 바로잡아야 합니다."),
        ("copula_conjugation", [
            ("今日は暇だです。", "だです", "です"), ("この地域は穏やかなです。", "穏やかなです", "穏やかです"),
            ("彼は学生ですだ。", "ですだ", "です"), ("昨日は休みでしたです。", "でしたです", "でした"),
            ("ここは安全だです。", "だです", "です"), ("その答えは簡単なです。", "簡単なです", "簡単です"),
            ("兄は医者だでした。", "だでした", "でした"), ("会議は明日ですだ。", "ですだ", "です"),
            ("この辺は便利だです。", "だです", "です"), ("予約は必要なです。", "必要なです", "必要です"),
        ], "서술 종결의 불필요한 접속을 제거해야 합니다."),
        ("modifier_connection", [
            ("立派建物が見えます。", "立派建物", "立派な建物"), ("便利のアプリを使います。", "便利のアプリ", "便利なアプリ"),
            ("新しいな店ができました。", "新しいな店", "新しい店"), ("有名の寺を見ました。", "有名の寺", "有名な寺"),
            ("大きいな橋を渡ります。", "大きいな橋", "大きい橋"), ("親切人に聞きました。", "親切人", "親切な人"),
            ("古いな写真を見つけました。", "古いな写真", "古い写真"), ("特別の料理を注文しました。", "特別の料理", "特別な料理"),
            ("丈夫の靴を選びました。", "丈夫の靴", "丈夫な靴"), ("面白いな本を借りました。", "面白いな本", "面白い本"),
        ], "명사 수식 접속을 최소 교정해야 합니다."),
        ("tense_mismatch", [
            ("昨日は市場へ行きます。", "行きます", "行きました"), ("来月、北海道へ行きました。", "行きました", "行きます"),
            ("先週の会議は長いです。", "長いです", "長かったです"), ("明日は家で休みました。", "休みました", "休みます"),
            ("昨夜は早く寝ます。", "寝ます", "寝ました"), ("来年、大学を卒業しました。", "卒業しました", "卒業します"),
            ("一昨日、手紙を書きます。", "書きます", "書きました"), ("次の日曜日に掃除しました。", "掃除しました", "掃除します"),
            ("去年は京都に住みます。", "住みます", "住んでいました"), ("明後日は朝六時に起きました。", "起きました", "起きます"),
        ], "시간 표현과 서술어의 시제를 일치시켜야 합니다.")]
    for error_type, cases, reason in single_sets:
        for text, source, replacement in cases:
            # One deliberately correct-looking source/replacement typo is repaired here.
            if source == replacement:
                text, source, replacement = "夏休みに山へ登るました。", "登るました", "登りました"
            edit = _edit(text, source, replacement, error_type)
            rows.append(_row(n, text, "needs_correction", level="N4", group=f"holdout_{error_type}", reason=reason,
                             edits=[edit], tags=(f"error:{error_type}", "minimal_pair"))); n += 1

    compound = [
        ("昨日は公民館を本を読むました。", [("を", "で", "particle_misuse", 0), ("読むました", "読みました", "verb_conjugation", 0)]),
        ("来週は静かの旅館で泊まりました。", [("静かの", "静かな", "modifier_connection", 0), ("泊まりました", "泊まります", "tense_mismatch", 0)]),
        ("小さいな鳥が屋根でいます。", [("小さいな", "小さい", "modifier_connection", 0), ("で", "に", "particle_misuse", 0)]),
        ("昨日の空は青いくて、きれいなでした。", [("青いくて", "青くて", "adjective_conjugation", 0), ("きれいなでした", "きれいでした", "copula_conjugation", 0)]),
        ("先月は便利のホテルに泊まるます。", [("便利の", "便利な", "modifier_connection", 0), ("泊まるます", "泊まりました", "verb_conjugation", 0)]),
        ("明日は図書室を勉強するました。", [("を", "で", "particle_misuse", 0), ("するました", "します", "tense_mismatch", 0)]),
    ]
    for text, specs in compound:
        edits = [_edit(text, a, b, typ, occ) for a, b, typ, occ in specs]
        edits.sort(key=lambda x: x["start"])
        rows.append(_row(n, text, "needs_correction", level="N4", group="holdout_compound", reason="서로 다른 두 문법 오류를 모두 최소 교정해야 합니다.", edits=edits,
                         tags=("compound_error", "minimal_pair"))); n += 1

    insufficient = [
        ("", None), ("……", None), ("［雑音］", None), ("あの、その、何と言えば……", None),
        ("昨日、港で友達と", None), ("もし最終バスに間に合わなかったら", None), ("この写真を撮ったのは", None), ("私は先週、歯医者に……", None),
        ("来月は［聞き取れない］へ行きます。", None), ("昨日は［聞き取れない］かったです。", None),
        ("Because I missed the bus.", None), ("다음 주에 시험이 있습니다.", None),
        ("駅に着いたけど", None), ("先生が言ったことは", None), ("雨が降っていたので", None), ("この料理、ちょっと……", None),
        ("［無音］", "질문에 대한 응답 구간"), ("えっと……その……", "여행 계획을 묻는 질문"),
        ("公園で［雑音］ました。", None), ("弟はとても［聞き取れない］です。", None),
        ("I need more time.", None), ("어제 친구를 만났어요.", None),
        ("買いたいと思っているのは", None), ("時間があれば", None),
    ]
    for text, context in insufficient:
        rows.append(_row(n, text, "insufficient_evidence", context=context, level="N4", group="holdout_insufficient",
                         reason="핵심 정보가 없거나 대상 언어의 완결된 발화가 아니므로 교정문을 추측하지 않습니다.", tags=("boundary_case", "no_guessing"))); n += 1
    if n != 151:
        raise AssertionError(n)
    random.Random(SEED).shuffle(rows)
    return rows


def _fp(text):
    text = unicodedata.normalize("NFKC", text)
    return "".join(c for c in text if not c.isspace() and not unicodedata.category(c).startswith("P"))


def _existing_strings():
    paths = [Path(__file__).with_name("seed_v0.1.jsonl"), ROOT / "training/judgment/data/pilot_v0.2_b.jsonl"]
    strings = {}
    for path in paths:
        if not path.exists():
            continue
        for line in path.read_text().splitlines():
            row = json.loads(line)
            candidates = [row.get("input", {}).get("text", ""), row.get("expected", {}).get("corrected_text", "")]
            candidates += row.get("accepted_corrections", [])
            for value in candidates:
                if value:
                    strings.setdefault(_fp(value), []).append(str(path.relative_to(ROOT)))
    rag = ROOT / "rag_data"
    if rag.exists():
        def walk(value):
            if isinstance(value, str): yield value
            elif isinstance(value, list):
                for x in value: yield from walk(x)
            elif isinstance(value, dict):
                for x in value.values(): yield from walk(x)
        for path in rag.rglob("*.json"):
            try: data = json.loads(path.read_text())
            except (UnicodeDecodeError, json.JSONDecodeError): continue
            for value in walk(data):
                if len(_fp(value)) >= 4:
                    strings.setdefault(_fp(value), []).append(str(path.relative_to(ROOT)))
    return strings


def build(output=DEFAULT_OUTPUT, manifest=DEFAULT_MANIFEST):
    rows = build_records()
    validate_records(rows)
    existing = _existing_strings()
    overlaps = []
    for row in rows:
        for value in [row["input"]["text"], row["expected"]["corrected_text"], *row["accepted_corrections"]]:
            fingerprint = _fp(value)
            if len(fingerprint) >= 4 and fingerprint in existing:
                overlaps.append({"id": row["id"], "text": value, "sources": sorted(set(existing[fingerprint]))})
    if overlaps:
        raise ValueError(f"holdout contamination: {overlaps[:5]}")
    payload = "".join(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n" for row in rows)
    output.write_text(payload)
    digest = hashlib.sha256(payload.encode()).hexdigest()
    decisions = Counter(row["expected"]["decision"] for row in rows)
    errors = Counter(edit["error_type"] for row in rows for edit in row["expected"]["edits"])
    info = {
        "dataset": str(DEFAULT_OUTPUT.relative_to(ROOT)), "schema_version": "0.1", "role": "sealed_blind_holdout",
        "generator_seed": SEED, "records": len(rows), "sha256": digest,
        "decisions": dict(sorted(decisions.items())), "error_types": dict(sorted(errors.items())),
        "compound_error_cases": sum(len(row["expected"]["edits"]) > 1 for row in rows),
        "review_status": "generated_validated", "human_reviewed": False,
        "contamination_audit": {"exact_normalized_matches": 0, "sources": ["seed_v0.1", "pilot_v0.2_b", "rag_data JSON"]},
        "seal_policy": "Do not inspect model predictions on this set during v0.2-C data or prompt development.",
    }
    manifest.write_text(json.dumps(info, ensure_ascii=False, indent=2) + "\n")
    return info


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)
    if args.check:
        expected_data, expected_manifest = args.output.read_bytes(), args.manifest.read_bytes()
        tmp_data, tmp_manifest = Path("/tmp/holdout-check.jsonl"), Path("/tmp/holdout-check.manifest.json")
        info = build(tmp_data, tmp_manifest)
        if expected_data != tmp_data.read_bytes() or expected_manifest != tmp_manifest.read_bytes():
            raise SystemExit("holdout files are not reproducible")
    else:
        info = build(args.output, args.manifest)
    print(json.dumps(info, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()
