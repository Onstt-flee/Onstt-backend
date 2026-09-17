"""Build the controlled v0.2-B hard-negative augmentation and ChatML view."""

from __future__ import annotations

import argparse
from collections import Counter
from copy import deepcopy
import hashlib
import json
from pathlib import Path

from training.judgment.build_reason_control import controlled_expected
from training.judgment.data import (
    exact_overlap,
    load_records,
    near_seed_overlap,
    summary,
    validate_records,
)
from training.judgment.export_chatml import export


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SOURCE = Path(__file__).with_name("data") / "pilot_v0.1.reviewed.jsonl"
DEFAULT_OUTPUT = Path(__file__).with_name("data") / "pilot_v0.2_b.jsonl"
DEFAULT_AUGMENTATION = Path(__file__).with_name("data") / "hard_negatives_v0.2_b.jsonl"
DEFAULT_CHATML = Path(__file__).with_name("data") / "hard_negatives_v0.2_b_chatml"
DEFAULT_MANIFEST = Path(__file__).with_name("data") / "hard_negatives_v0.2_b.manifest.json"
SEED = ROOT / "evaluation/judgment/seed_v0.1.jsonl"
RAG_DIR = ROOT / "rag_data"
VERSION = "hard-negatives-v0.2-b"
VALIDATED_AT = "2026-09-14"


CATEGORY_PAIRS = {
    "transport_destination": {
        "error_type": "particle_misuse",
        "reason_ok": "교통수단에는 で, 이동 목적지에는 に 또는 へ를 사용합니다.",
        "reason_error": "교통수단의 では 유지하고 이동 목적지의 조사만 に 또는 へ로 고칩니다.",
        "anchor": "JT-0001",
        "items": [
            ("明後日は地下鉄で美術館に行きます。", "明後日は地下鉄で美術館を行きます。"),
            ("週末は自転車で体育館へ行きます。", "週末は自転車で体育館を行きます。"),
            ("今度は船で島に行きます。", "今度は船で島を行きます。"),
            ("午後はタクシーで大使館へ行きます。", "午後はタクシーで大使館を行きます。"),
            ("夏休みは飛行機で北海道に行きます。", "夏休みは飛行機で北海道を行きます。"),
            ("日曜日はバイクで競技場へ行きます。", "日曜日はバイクで競技場を行きます。"),
            ("来年は新幹線で福岡に行きます。", "来年は新幹線で福岡を行きます。"),
            ("夕方は路面電車で港へ行きます。", "夕方は路面電車で港を行きます。"),
            ("連休は夜行バスで仙台に行きます。", "連休は夜行バスで仙台を行きます。"),
            ("今夜はモノレールで空港へ行きます。", "今夜はモノレールで空港を行きます。"),
            ("再来週はレンタカーで温泉に行きます。", "再来週はレンタカーで温泉を行きます。"),
            ("昼過ぎは地下鉄で劇場へ行きます。", "昼過ぎは地下鉄で劇場を行きます。"),
        ],
    },
    "route_o": {
        "error_type": "particle_misuse",
        "reason_ok": "통과하거나 이동하는 경로에는 조사 を를 사용할 수 있습니다.",
        "reason_error": "통과 경로를 나타내는 장소의 조사를 を로 고칩니다.",
        "anchor": "JT-0019",
        "items": [
            ("朝、横断歩道を渡りました。", "朝、横断歩道で渡りました。"),
            ("観光客が門を通りました。", "観光客が門で通りました。"),
            ("選手は長い坂道を走りました。", "選手は長い坂道で走りました。"),
            ("夕方、商店街を歩きました。", "夕方、商店街で歩きました。"),
            ("毎日この橋を渡ります。", "毎日この橋で渡ります。"),
            ("帰りに細い路地を通ります。", "帰りに細い路地で通ります。"),
            ("週末に海岸沿いを走りました。", "週末に海岸沿いで走りました。"),
            ("登山者は森の中を進みました。", "登山者は森の中で進みました。"),
            ("車がトンネルを通過しました。", "車がトンネルで通過しました。"),
            ("子どもたちは廊下を走りました。", "子どもたちは廊下で走りました。"),
            ("私たちは遊歩道を歩きます。", "私たちは遊歩道で歩きます。"),
            ("電車が鉄橋を渡りました。", "電車が鉄橋で渡りました。"),
        ],
    },
    "plain_form": {
        "error_type": "verb_conjugation",
        "reason_ok": "문체 제약이 없는 회화에서는 올바른 보통체 과거형을 사용할 수 있습니다.",
        "reason_error": "동사를 올바른 보통체 과거형으로 활용합니다.",
        "anchor": "JT-0082",
        "items": [
            ("夕方、手紙を書いた。", "夕方、手紙を書くた。"),
            ("昨日、新しい靴を買った。", "昨日、新しい靴を買うた。"),
            ("駅前で友達を待った。", "駅前で友達を待つた。"),
            ("昨夜、小説を読んだ。", "昨夜、小説を読むた。"),
            ("放課後、弟と遊んだ。", "放課後、弟と遊ぶた。"),
            ("昼休みに先生と話した。", "昼休みに先生と話すた。"),
            ("夏に湖で泳いだ。", "夏に湖で泳ぐた。"),
            ("今朝、駅まで急いだ。", "今朝、駅まで急ぐた。"),
            ("昨晩は早く帰った。", "昨晩は早く帰るた。"),
            ("喫茶店で紅茶を飲んだ。", "喫茶店で紅茶を飲むた。"),
            ("昼に川辺を歩いた。", "昼に川辺を歩くた。"),
            ("さっき音楽を聞いた。", "さっき音楽を聞くた。"),
        ],
    },
    "explanatory_ndesu": {
        "error_type": "verb_conjugation",
        "reason_ok": "과거 사실을 설명하는 보통형＋んです 접속이 올바릅니다.",
        "reason_error": "んです 앞의 동사를 보통형 과거로 고칩니다.",
        "anchor": "JT-0073",
        "items": [
            ("昨日はずっと寮にいたんです。", "昨日はずっと寮にいましたんです。"),
            ("先週は祖母の家にいたんです。", "先週は祖母の家にいましたんです。"),
            ("午前中は研究室にいたんです。", "午前中は研究室にいましたんです。"),
            ("休みの日は一日中部屋にいたんです。", "休みの日は一日中部屋にいましたんです。"),
            ("その時は外にいたんです。", "その時は外にいましたんです。"),
            ("昼までは事務所にいたんです。", "昼までは事務所にいましたんです。"),
            ("昨日は寮にずっといたんです。", "昨日は寮にずっといましたんです。"),
            ("先週は祖母の家にしばらくいたんです。", "先週は祖母の家にしばらくいましたんです。"),
            ("午前中は研究室にずっといたんです。", "午前中は研究室にずっといましたんです。"),
            ("休みの日は部屋に一日中いたんです。", "休みの日は部屋に一日中いましたんです。"),
            ("その時は外にまだいたんです。", "その時は外にまだいましたんです。"),
            ("昼までは事務所に一人でいたんです。", "昼までは事務所に一人でいましたんです。"),
        ],
    },
    "adjective_connection_yasui": {
        "error_type": "modifier_connection",
        "reason_ok": "な형용사의 연결형과 동사 어간＋やすい 형태가 올바릅니다.",
        "reason_error": "な형용사 연결 또는 동사 어간＋やすい 형태를 고칩니다.",
        "anchor": "JT-0055",
        "items": [
            ("この地域は便利で、暮らしやすいです。", "この地域は便利なで、暮らしやすいです。"),
            ("この図書館は静かで、勉強しやすいです。", "この図書館は静かなで、勉強しやすいです。"),
            ("この案内は簡単で、分かりやすいです。", "この案内は簡単なで、分かりやすいです。"),
            ("この道は安全で、歩きやすいです。", "この道は安全なで、歩きやすいです。"),
            ("この鞄は丈夫で、使いやすいです。", "この鞄は丈夫なで、使いやすいです。"),
            ("この駅はきれいで、利用しやすいです。", "この駅はきれいなで、利用しやすいです。"),
            ("この町は平坦で、自転車で走りやすいです。", "この町は平坦で、自転車で走るやすいです。"),
            ("このペンは軽くて、書きやすいです。", "このペンは軽くて、書くやすいです。"),
            ("この説明は短くて、覚えやすいです。", "この説明は短くて、覚えるやすいです。"),
            ("この靴は柔らかくて、歩きやすいです。", "この靴は柔らかくて、歩くやすいです。"),
            ("この机は広くて、作業しやすいです。", "この机は広くて、作業するやすいです。"),
            ("この画面は明るくて、見やすいです。", "この画面は明るくて、見るやすいです。"),
        ],
    },
    "filler_preservation": {
        "error_type": "particle_misuse",
        "reason_ok": "필러는 유지하고 이동 목적지의 조사 사용이 올바른지 판단합니다.",
        "reason_error": "필러는 삭제하지 않고 이동 목적지의 조사만 に 또는 へ로 고칩니다.",
        "anchor": "JT-0100",
        "items": [
            ("ええと、土曜日は市場へ行きます。", "ええと、土曜日は市場を行きます。"),
            ("あのう、午後は市民会館に行きます。", "あのう、午後は市民会館を行きます。"),
            ("その、明後日は展望台へ行きます。", "その、明後日は展望台を行きます。"),
            ("えっと、休みには水族館に行きます。", "えっと、休みには水族館を行きます。"),
            ("あの、夕方は郵便局へ行きます。", "あの、夕方は郵便局を行きます。"),
            ("うーん、次は科学館に行きます。", "うーん、次は科学館を行きます。"),
            ("ええと、来月は植物園へ行きます。", "ええと、来月は植物園を行きます。"),
            ("あのう、今度は区役所に行きます。", "あのう、今度は区役所を行きます。"),
            ("その、週明けは研修所へ行きます。", "その、週明けは研修所を行きます。"),
            ("えっと、昼から工房に行きます。", "えっと、昼から工房を行きます。"),
            ("あの、連休には古本市へ行きます。", "あの、連休には古本市を行きます。"),
            ("うーん、明朝は診療所に行きます。", "うーん、明朝は診療所を行きます。"),
        ],
    },
    "style_advisory_boundary": {
        "error_type": "copula_conjugation",
        "reason_ok": "문체 통일 지시는 별도 조언 대상이며 문장 자체의 문법 오류로 처리하지 않습니다.",
        "reason_error": "문체 혼용은 유지하고 보통체 뒤에 잘못 붙은 です만 제거합니다.",
        "anchor": "JT-0118",
        "items": [
            ("昨日は説明会に参加しました。それから資料を読んだ。", "昨日は説明会に参加しました。それから資料を読んだです。"),
            ("朝は会議に出ました。その後で報告書を書いた。", "朝は会議に出ました。その後で報告書を書いたです。"),
            ("先週は研修を受けました。そして課題を出した。", "先週は研修を受けました。そして課題を出したです。"),
            ("午前は受付をしました。午後は案内を担当した。", "午前は受付をしました。午後は案内を担当したです。"),
            ("最初に自己紹介をしました。次に計画を話した。", "最初に自己紹介をしました。次に計画を話したです。"),
            ("昨日は工場を見学しました。それから感想をまとめた。", "昨日は工場を見学しました。それから感想をまとめたです。"),
            ("朝は資料を確認しました。その後で担当者に聞いた。", "朝は資料を確認しました。その後で担当者に聞いたです。"),
            ("先月は講座に通いました。最後に試験を受けた。", "先月は講座に通いました。最後に試験を受けたです。"),
            ("午前は発表を聞きました。午後は質問を考えた。", "午前は発表を聞きました。午後は質問を考えたです。"),
            ("昨日は面接を受けました。帰宅して結果を待った。", "昨日は面接を受けました。帰宅して結果を待ったです。"),
            ("最初に申請書を出しました。次に番号を受け取った。", "最初に申請書を出しました。次に番号を受け取ったです。"),
            ("先週は展示を見ました。そして作品について話した。", "先週は展示を見ました。そして作品について話したです。"),
        ],
    },
    "stt_orthography_boundary": {
        "error_type": "tense_mismatch",
        "reason_ok": "원음이 없는 STT 전사에서는 조사 표기의 책임을 단정하지 않고 문법 판단과 분리합니다.",
        "reason_error": "STT 조사 표기는 유지하고 명시된 과거 시간과 서술어 시제만 일치시킵니다.",
        "anchor": None,
        "items": [
            ("昨日、わたしわ資料お読みました。", "昨日、わたしわ資料お読みます。"),
            ("先週、わたしわ手紙お書きました。", "先週、わたしわ手紙お書きます。"),
            ("昨夜、わたしわ薬お飲みました。", "昨夜、わたしわ薬お飲みます。"),
            ("一昨日、わたしわ映画お見ました。", "一昨日、わたしわ映画お見ます。"),
            ("去年、わたしわ日本語お習いました。", "去年、わたしわ日本語お習います。"),
            ("今朝、わたしわ朝食お作りました。", "今朝、わたしわ朝食お作ります。"),
            ("昨日、ぼくわ切符お買いました。", "昨日、ぼくわ切符お買います。"),
            ("先週、ぼくわ写真お撮りました。", "先週、ぼくわ写真お撮ります。"),
            ("昨晩、ぼくわ音楽お聞きました。", "昨晩、ぼくわ音楽お聞きます。"),
            ("一昨日、ぼくわ荷物お送りました。", "一昨日、ぼくわ荷物お送ります。"),
            ("去年、ぼくわ車お売りました。", "去年、ぼくわ車お売ります。"),
            ("今朝、ぼくわ新聞お読みました。", "今朝、ぼくわ新聞お読みます。"),
        ],
    },
}


GENERAL_ACCEPTABLE = {
    "embedded_plain": [
        ("明日は風が強くなると思います。", None),
        ("彼は午後に戻ると思います。", None),
        ("この方法が一番早いと思います。", None),
        ("来週は忙しくなると思います。", None),
        ("その店は今日は開かないと思います。", None),
        ("電車はもう着いたと思います。", None),
    ],
    "colloquial_ellipsis": [
        ("鍵、もう見つけたよ。", "친구에게 분실물을 찾았다고 말합니다."),
        ("予約、さっき確認したよ。", "친구에게 예약 확인을 마쳤다고 말합니다."),
        ("宿題、もう終わったよ。", "친구에게 숙제를 끝냈다고 말합니다."),
        ("昼ご飯、もう食べたよ。", "친구에게 식사를 마쳤다고 말합니다."),
        ("メール、今送ったよ。", "친구에게 메일을 보냈다고 말합니다."),
        ("席、ちゃんと取ったよ。", "친구에게 자리를 확보했다고 말합니다."),
    ],
    "contraction": [
        ("今、駅で待ってる。", "친한 사이의 일상 대화입니다."),
        ("弟は部屋で寝てるよ。", "친한 사이의 일상 대화입니다."),
        ("何を探してるの？", "친한 사이의 일상 대화입니다."),
        ("外で雨が降ってる。", "친한 사이의 일상 대화입니다."),
        ("まだ仕事してる？", "친한 사이의 일상 대화입니다."),
        ("母は電話で話してる。", "친한 사이의 일상 대화입니다."),
    ],
    "short_answer": [
        ("札幌です。", "상대방이 여행 목적지를 물었습니다."),
        ("三時です。", "상대방이 약속 시간을 물었습니다."),
        ("二人です。", "상대방이 인원수를 물었습니다."),
        ("来週です。", "상대방이 일정을 물었습니다."),
        ("青い方です。", "상대방이 어느 물건인지 물었습니다."),
        ("電車です。", "상대방이 이동 수단을 물었습니다."),
    ],
}


INSUFFICIENT = {
    "silence": [(value, None) for value in ("……", "………", "…………", "（沈黙）", "［無言］", "…")],
    "filler_only": [(value, None) for value in ("あのう……", "ええと……", "その……", "えっと……", "うーん……", "あの……")],
    "truncated": [
        ("昨日、受付で担当者に", None),
        ("もし電車が遅れたら", None),
        ("この資料を作ったのは", None),
        ("来週の会議について", None),
        ("駅に着いたあとで", None),
        ("私が伝えたかったことは", None),
    ],
    "missing_audio": [
        ("明日は［聞き取れない］へ向かいます。", None),
        ("昨日は［雑音］を買いました。", None),
        ("この料理は［聞き取れない］かったです。", None),
        ("［音声欠落］ので、遅れました。", None),
        ("先生が［不明］と話しました。", None),
        ("午後に［雑音］を始めます。", None),
    ],
}


class Builder:
    def __init__(self, start: int = 301) -> None:
        self.next_id = start
        self.records: list[dict] = []
        self.metadata: list[dict] = []

    def add(
        self,
        *,
        family: str,
        split: str,
        text: str,
        context: str | None,
        decision: str,
        reason: str,
        corrected_text: str | None = None,
        error_type: str | None = None,
        pair_id: str | None = None,
        source_anchor_id: str | None = None,
    ) -> dict:
        record_id = f"JT-{self.next_id:04d}"
        generated_index = self.next_id - 301
        learner_level = "N4" if generated_index % 10 in {2, 5, 8} else "N5"
        self.next_id += 1
        corrected = text if corrected_text is None else corrected_text
        edits = []
        accepted = []
        tags = [decision, family, VERSION]
        if decision == "needs_correction":
            if not error_type or corrected == text:
                raise ValueError(f"Invalid correction for {record_id}")
            prefix = 0
            while prefix < min(len(text), len(corrected)) and text[prefix] == corrected[prefix]:
                prefix += 1
            suffix = 0
            while (
                suffix < len(text) - prefix
                and suffix < len(corrected) - prefix
                and text[len(text) - suffix - 1] == corrected[len(corrected) - suffix - 1]
            ):
                suffix += 1
            end = len(text) - suffix
            replacement_end = len(corrected) - suffix
            edits = [{
                "start": prefix,
                "end": end,
                "source": text[prefix:end],
                "replacement": corrected[prefix:replacement_end],
                "error_type": error_type,
            }]
            accepted = [corrected]
            tags.append(error_type)
        record = {
            "schema_version": "0.1",
            "id": record_id,
            "split": split,
            "template_family_id": family,
            "tags": tags,
            "input": {"text": text, "context": context, "learner_level": learner_level},
            "expected": {
                "decision": decision,
                "corrected_text": corrected,
                "edits": edits,
                "reason_ko": reason,
            },
            "accepted_corrections": accepted,
            "provenance": {
                "kind": "deterministic_template",
                "source_id": VERSION,
                "external_text_used": False,
                "generator_model": None,
                "generator_revision": None,
                "generator_prompt_sha256": None,
            },
            "review": {"status": "generated_validated", "reviewed_at": VALIDATED_AT},
        }
        self.records.append(record)
        self.metadata.append({
            "id": record_id,
            "generation_rule": family,
            "source_anchor_id": source_anchor_id,
            "pair_id": pair_id,
            "generation_version": VERSION,
            "validation_status": "generated_validated",
        })
        return record


def build_generated() -> tuple[list[dict], list[dict]]:
    builder = Builder()
    for category, config in CATEGORY_PAIRS.items():
        for index, (normal, erroneous) in enumerate(config["items"]):
            split_suffix = "train" if index < 9 else "dev"
            split = "pilot_train" if index < 9 else "pilot_dev"
            family = f"v02b_{category}_{split_suffix}"
            pair_id = f"v02b-{category}-{index + 1:02d}"
            context = None
            if category == "route_o":
                context = "장소를 동작의 무대가 아니라 출발점에서 도착점까지 통과한 경로로 설명합니다."
            elif category == "plain_form":
                context = "친구에게 지난 일을 보통체로 말합니다. 문체 통일 지시는 없습니다."
            elif category == "style_advisory_boundary":
                context = "공식 발표 연습에서 모든 문장을 です・ます체로 통일하라는 지시가 있습니다. 직접 인용이 아닙니다."
            elif category == "stt_orthography_boundary":
                context = "STT가 생성한 전사 텍스트입니다. 원음이나 대안 전사는 제공되지 않았습니다."
            normal_record = builder.add(
                family=family,
                split=split,
                text=normal,
                context=context,
                decision="acceptable",
                reason=config["reason_ok"],
                pair_id=pair_id,
                source_anchor_id=config["anchor"],
            )
            builder.add(
                family=family,
                split=split,
                text=erroneous,
                context=context,
                decision="needs_correction",
                corrected_text=normal,
                error_type=config["error_type"],
                reason=config["reason_error"],
                pair_id=pair_id,
                source_anchor_id=normal_record["id"],
            )

    general_reasons = {
        "embedded_plain": "〜と思います 앞에 보통형을 올바르게 사용했습니다.",
        "colloquial_ellipsis": "친밀한 회화에서는 문맥으로 분명한 조사를 생략할 수 있습니다.",
        "contraction": "친밀한 회화에서는 〜ている를 〜てる로 줄여 말할 수 있습니다.",
        "short_answer": "질문 문맥에서 의미가 완결된 짧은 대답이므로 허용합니다.",
    }
    for category, items in GENERAL_ACCEPTABLE.items():
        family = f"v02b_general_{category}_train"
        for text, context in items:
            builder.add(
                family=family,
                split="pilot_train",
                text=text,
                context=context,
                decision="acceptable",
                reason=general_reasons[category],
                source_anchor_id=None,
            )

    insufficient_reasons = {
        "silence": "실제 발화 내용이 없어 문법을 판단할 수 없습니다.",
        "filler_only": "필러만으로는 판단할 문장 내용이 없어 교정하지 않습니다.",
        "truncated": "문장이 끝나지 않아 누락된 내용을 추측하여 교정하지 않습니다.",
        "missing_audio": "들리지 않은 부분을 텍스트만으로 확정할 수 없어 교정하지 않습니다.",
    }
    for category, items in INSUFFICIENT.items():
        family = f"v02b_insufficient_{category}_train"
        for text, context in items:
            builder.add(
                family=family,
                split="pilot_train",
                text=text,
                context=context,
                decision="insufficient_evidence",
                reason=insufficient_reasons[category],
                source_anchor_id=None,
            )
    return builder.records, builder.metadata


def controlled_source(records: list[dict]) -> list[dict]:
    result = deepcopy(records)
    for row in result:
        row["expected"] = controlled_expected(row)
    return result


def _write_jsonl(path: Path, records: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as stream:
        for row in records:
            stream.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate_generated(generated: list[dict], metadata: list[dict]) -> dict:
    validate_records(generated, require_reviewed=True)
    if len(generated) != 240:
        raise ValueError(f"Expected 240 generated records, got {len(generated)}")
    decisions = Counter(row["expected"]["decision"] for row in generated)
    if decisions != {"acceptable": 120, "needs_correction": 96, "insufficient_evidence": 24}:
        raise ValueError(f"Unexpected generated decisions: {decisions}")
    splits = Counter(row["split"] for row in generated)
    if splits != {"pilot_train": 192, "pilot_dev": 48}:
        raise ValueError(f"Unexpected generated splits: {splits}")
    if any(row["review"]["status"] != "generated_validated" for row in generated):
        raise ValueError("Generated records must not claim human review")

    by_pair: dict[str, list[dict]] = {}
    by_id = {row["id"]: row for row in generated}
    for item in metadata:
        if item["pair_id"]:
            by_pair.setdefault(item["pair_id"], []).append(by_id[item["id"]])
    if len(by_pair) != 96:
        raise ValueError(f"Expected 96 pairs, got {len(by_pair)}")
    for pair_id, pair in by_pair.items():
        if len(pair) != 2:
            raise ValueError(f"Pair {pair_id} must contain two records")
        normal = next((row for row in pair if row["expected"]["decision"] == "acceptable"), None)
        error = next((row for row in pair if row["expected"]["decision"] == "needs_correction"), None)
        if not normal or not error:
            raise ValueError(f"Pair {pair_id} must contain acceptable and correction")
        if normal["split"] != error["split"] or normal["template_family_id"] != error["template_family_id"]:
            raise ValueError(f"Pair {pair_id} crosses split or family")
        if normal["input"]["context"] != error["input"]["context"]:
            raise ValueError(f"Pair {pair_id} changes context")
        if error["expected"]["corrected_text"] != normal["input"]["text"]:
            raise ValueError(f"Pair {pair_id} does not round-trip")
        if len(error["expected"]["edits"]) != 1:
            raise ValueError(f"Pair {pair_id} must contain exactly one edit")

    near = near_seed_overlap(generated, seed_path=SEED, threshold=0.75)
    if near:
        raise ValueError(f"Generated data overlaps seed at threshold 0.75: {near[:3]}")
    exact = exact_overlap(generated, seed_path=SEED, rag_dir=RAG_DIR)
    if exact["matches"]:
        raise ValueError(f"Generated data exactly overlaps seed/RAG: {exact['matches'][:3]}")
    return {
        "total": len(generated),
        "splits": dict(sorted(splits.items())),
        "decisions": dict(sorted(decisions.items())),
        "pairs": len(by_pair),
        "template_families": len({row["template_family_id"] for row in generated}),
        "review_status": "generated_validated",
        "expert_review_claimed": False,
        "near_seed_threshold": 0.75,
        "near_seed_matches": 0,
        "exact_seed_rag_matches": 0,
    }


def build(
    source_path: Path = DEFAULT_SOURCE,
    output_path: Path = DEFAULT_OUTPUT,
    augmentation_path: Path = DEFAULT_AUGMENTATION,
    chatml_dir: Path = DEFAULT_CHATML,
    manifest_path: Path = DEFAULT_MANIFEST,
) -> dict:
    source = load_records(source_path)
    validate_records(source, require_reviewed=True)
    generated, metadata = build_generated()
    generated_validation = validate_generated(generated, metadata)
    combined = controlled_source(source) + generated
    validate_records(combined, require_reviewed=True)
    if summary(combined)["total"] != 540:
        raise ValueError("Combined dataset must contain 540 records")

    _write_jsonl(augmentation_path, generated)
    _write_jsonl(output_path, combined)
    chatml = export(output_path, chatml_dir)
    manifest = {
        "dataset_id": "judgment-pilot-v0.2-b",
        "generation_version": VERSION,
        "validated_at": VALIDATED_AT,
        "source_dataset": str(source_path.relative_to(ROOT)),
        "source_dataset_sha256": _sha256(source_path),
        "augmentation_path": str(augmentation_path.relative_to(ROOT)),
        "augmentation_sha256": _sha256(augmentation_path),
        "combined_path": str(output_path.relative_to(ROOT)),
        "combined_sha256": _sha256(output_path),
        "policy": {
            "canonical_v0.1_modified": False,
            "model_generated_gold_used": False,
            "user_review_claimed_for_generated": False,
            "expert_review_claimed": False,
            "evaluation_seed_used_as_training_text": False,
        },
        "generated_validation": generated_validation,
        "combined_summary": summary(combined),
        "generation_metadata": metadata,
        "chatml": chatml,
    }
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--augmentation", type=Path, default=DEFAULT_AUGMENTATION)
    parser.add_argument("--chatml-dir", type=Path, default=DEFAULT_CHATML)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    args = parser.parse_args()
    report = build(args.source, args.output, args.augmentation, args.chatml_dir, args.manifest)
    print(json.dumps({
        "dataset_id": report["dataset_id"],
        "combined_sha256": report["combined_sha256"],
        "generated_validation": report["generated_validation"],
        "combined_summary": report["combined_summary"],
        "chatml": report["chatml"],
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
