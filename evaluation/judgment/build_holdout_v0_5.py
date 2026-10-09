"""Build and seal the final v0.5 holdout before v0.2-J training."""

from __future__ import annotations

from collections import Counter, defaultdict
from copy import deepcopy
from difflib import SequenceMatcher
import hashlib
import json
from pathlib import Path
import random
import re

from evaluation.judgment.build_holdout_v0_4 import build_records as build_v04
from evaluation.judgment.dataset import sentence_fingerprint, validate_records

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "evaluation/judgment/holdout_v0.5.jsonl"
MANIFEST = ROOT / "evaluation/judgment/holdout_v0.5.manifest.json"
SHUFFLE_SEED = 20261010
NEAR_THRESHOLD = 0.85
SOURCE_FILES = (
    ROOT / "evaluation/judgment/seed_v0.1.jsonl",
    ROOT / "evaluation/judgment/holdout_v0.1.jsonl",
    ROOT / "evaluation/judgment/holdout_v0.2.jsonl",
    ROOT / "evaluation/judgment/holdout_v0.3.jsonl",
    ROOT / "evaluation/judgment/holdout_v0.4.jsonl",
    ROOT / "training/judgment/data/pilot_v0.2_i.jsonl",
)

REPLACEMENTS = (
    ("夕方なら", "昼休みなら"), ("あと五分", "あと十分"), ("私も見たい", "僕も試したい"),
    ("もう帰ろう", "そろそろ出よう"), ("南口", "北改札"), ("この席", "窓側の席"),
    ("明日の朝", "週末の午後"), ("その袋", "この箱"), ("少し残ってる", "半分残ってる"),
    ("先に始めよう", "準備を始めよう"), ("集合場所", "受付時間"), ("領収書", "申込用紙"),
    ("来月から部署", "来週から担当"), ("こちらに座って", "ここで待って"),
    ("予約番号", "整理券"), ("港の防波堤", "湖畔の木道"), ("大学の中庭", "美術館の回廊"),
    ("寺の石段", "神社の参道"), ("川沿いの細道", "海辺の遊歩道"),
    ("地下街の通路", "空港の連絡路"), ("工場の見学路", "城跡の外周"),
    ("丘の遊歩道", "森の散策路"), ("駅の連絡通路を急いで通りました。", "市役所のロビーを足早に抜けました。"),
    ("診察室の入口", "図書室の入口"), ("資料館の受付", "体育館の受付"),
    ("共同玄関の脇", "管理棟の脇"), ("理科室の窓側", "音楽室の窓側"),
    ("宿直室の机上", "放送室の机上"), ("講義室の後方", "会議室の後方"),
    ("調理室の壁際", "工作室の壁際"), ("展望室の中央", "展示室の中央"),
    ("消毒液", "返却箱"), ("案内図", "利用案内"), ("宅配ボックス", "回収容器"),
    ("標本棚", "譜面台"), ("懐中電灯", "予備電池"), ("予備机", "折り畳み椅子"),
    ("冷凍庫", "工具棚"), ("望遠鏡", "案内端末"),
    ("先日の講演", "昨日の説明会"), ("早朝の海風", "夜の山風"), ("昨日の坂道", "今朝の階段"),
    ("先週の試合", "前回の発表"), ("手続きの流れ", "登録の方法"), ("叔父", "父"),
    ("毎朝新聞", "毎晩雑誌"), ("早めに家", "七時に寮"), ("祖父", "母"),
    ("庭で花", "ベランダで野菜"), ("このかばん", "その上着"), ("妹", "兄"),
    ("新しい教室", "別の会議室"), ("保健所", "市民会館"), ("海洋研究所", "文化交流館"),
    ("公証役場", "年金事務所"), ("修理工場", "物流センター"), ("科学館", "歴史資料館"),
    ("労働局", "税務署"), ("展示会場", "研修会場"), ("交番", "案内所"),
    ("打ち合わせ", "授業"), ("井戸水", "麦茶"), ("山道", "登山道"), ("あの荷物", "この荷物"),
    ("昨日の風", "今朝の風"), ("その問題", "今回の問題"), ("先月の部屋", "以前の部屋"),
    ("昨夜の星", "今夜の月"), ("玄関", "廊下"), ("新しい靴", "古い靴"),
    ("申込書", "連絡票"), ("先輩", "同僚"), ("廊下", "入口"), ("毎晩、薬", "毎朝、牛乳"),
    ("昨日、窓", "今朝、扉"), ("この線", "白い線"), ("静か部屋", "便利場所"),
    ("丈夫な靴", "親切な人"), ("便利場所", "安全場所"), ("涼しいだです", "暖かいだです"),
    ("熱心係員", "丁寧係員"), ("この机", "その棚"), ("複雑問題", "重要課題"),
    ("その答え", "この説明"), ("印刷室", "発送室"), ("視聴覚室", "講堂"),
    ("作業場", "倉庫"), ("談話室", "待合室"), ("直売所", "市場"),
    ("研修室", "教室"), ("洗濯室", "乾燥室"), ("準備室", "事務室"),
    ("相談室", "応接室"), ("食堂", "休憩室"),
    ("The package should arrive before noon.", "The museum closes earlier on Fridays."),
    ("I forgot my umbrella on the train.", "I left my notebook at the library."),
    ("Could you check the meeting room?", "Could you reserve a table for four?"),
    ("My cousin moved to a coastal town.", "My neighbor started a new job."),
    ("다음 주에 건강검진을 받습니다.", "이번 주말에 가족을 만납니다."),
    ("오늘은 지하철이 많이 붐볐습니다.", "어제는 도서관에서 공부했습니다."),
    ("もし受付がもう閉まっていたら", "もし予約が取れなかったら"),
    ("昨日、取引先の担当者に", "今朝、駅前の店員に"),
    ("この装置を交換したのは", "その資料を提出したのは"),
    ("駅の階段で落としたのは", "公園のベンチに置いたのは"),
    ("説明が予定より長くなったので", "作業が思ったより遅れたので"),
    ("私が倉庫から持ってきた箱は", "父が旅行先で買った土産は"),
    ("明日は［聞き取れない］に集合します。", "来週は［聞き取れない］で研修します。"),
    ("昨日、［雑音］を受け取りました。", "先ほど、［雑音］を確認しました。"),
    ("今朝は［聞き取れない］くなりました。", "夕方は［聞き取れない］かったです。"),
    ("［雑音］から電話がありました。", "［雑音］へ連絡しました。"),
    ("ええと、あの……", "あの、その……"), ("［長い雑音］", "［音声途切れ］"),
    ("あの、つまり……", "えっと、それで……"),
    ("薬お食後に飲みます。", "水お食前に飲みます。"),
    ("今日わ早く帰ります。", "明日わ少し休みます。"),
    ("先生わ会議中です。", "父わ外出中です。"),
    ("朝から労働局", "午前中に区役所"),
    ("荷物お受付に預けました。", "上着お窓口に預けました。"),
    ("弟わ七時に起きました。", "姉わ六時に出発しました。"),
    ("資料お机に置きました。", "鍵お棚に置きました。"),
    ("私わ来月引っ越します。", "僕わ来週帰国します。"),
    ("手紙お祖母に送りました。", "写真お友達に送りました。"),
    ("静かな部屋", "便利な場所"), ("便利な場所", "安全な場所"),
    ("涼しいです", "暖かいです"), ("熱心な係員", "丁寧な係員"),
    ("複雑な問題", "重要な課題"),
)


_REPLACEMENT_MAP = dict(REPLACEMENTS)
_REPLACEMENT_PATTERN = re.compile("|".join(
    re.escape(value) for value in sorted(_REPLACEMENT_MAP, key=len, reverse=True)
))


def transform(text: str) -> str:
    return _REPLACEMENT_PATTERN.sub(lambda match: _REPLACEMENT_MAP[match.group(0)], text)


def rebuild_edits(source: str, target: str, error_types: list[str]) -> list[dict]:
    edits = []
    opcodes = [op for op in SequenceMatcher(a=source, b=target, autojunk=False).get_opcodes() if op[0] != "equal"]
    if len(opcodes) != len(error_types):
        raise ValueError(f"Edit count changed: {source!r} -> {target!r}")
    for (opcode, i1, i2, j1, j2), error_type in zip(opcodes, error_types):
        edits.append({"start": i1, "end": i2, "source": source[i1:i2],
                      "replacement": target[j1:j2], "error_type": error_type})
    return edits


def build_records() -> list[dict]:
    rows = []
    for number, original in enumerate(build_v04(), 1):
        row = deepcopy(original)
        source = transform(original["input"]["text"])
        target = transform(original["expected"]["corrected_text"])
        types = [edit["error_type"] for edit in original["expected"]["edits"]]
        row["id"] = f"JH-{number + 510:04d}"
        row["group_id"] = original["group_id"].replace("_v4", "_v5")
        row["tags"] = [tag.replace("_v4", "_v5") for tag in original["tags"]]
        row["input"]["text"] = source
        row["expected"]["corrected_text"] = target if row["expected"]["decision"] == "needs_correction" else source
        row["expected"]["edits"] = rebuild_edits(source, target, types) if types else []
        row["accepted_corrections"] = [target] if types else []
        row["provenance"] = {"kind": "deterministic_template",
                             "source_id": f"holdout-v0.5:{number:04d}",
                             "external_text_used": False}
        rows.append(row)
    random.Random(SHUFFLE_SEED).shuffle(rows)
    validate_records(rows)
    return rows


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


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

    direct, near, maximum, maximum_pair = [], [], 0.0, None
    prior = [(value, _grams(fp)) for value in historical if len(fp := sentence_fingerprint(value)) >= 5]
    for row in rows:
        for value in {row["input"]["text"], row["expected"]["corrected_text"], *row["accepted_corrections"]}:
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
                if score > maximum:
                    maximum, maximum_pair = score, {"id": row["id"], "text": value,
                        "previous": previous, "jaccard": round(score, 4)}
                if score >= NEAR_THRESHOLD:
                    near.append({"id": row["id"], "text": value, "previous": previous,
                                 "jaccard": round(score, 4)})
    if direct:
        raise ValueError(f"Holdout overlaps existing data: {direct[:5]}")
    if near:
        raise ValueError(f"Holdout near-duplicates existing data: {near[:5]}")

    payload = "".join(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n" for row in rows)
    data_path.write_text(payload, encoding="utf-8")
    dataset_hash = hashlib.sha256(payload.encode()).hexdigest()
    info = {
        "dataset": str(data_path.relative_to(ROOT)) if data_path.is_relative_to(ROOT) else str(data_path),
        "schema_version": "0.1", "role": "sealed_blind_holdout",
        "generator_seed": SHUFFLE_SEED, "records": len(rows), "sha256": dataset_hash,
        "decisions": dict(sorted(Counter(row["expected"]["decision"] for row in rows).items())),
        "groups": dict(sorted(Counter(row["group_id"] for row in rows).items())),
        "compound_error_cases": sum(len(row["expected"]["edits"]) > 1 for row in rows),
        "review_status": "generated_validated", "human_reviewed": False, "expert_reviewed": False,
        "contamination_audit": {
            "exact_normalized_matches": 0, "near_dataset_matches_at_or_above_0_85": 0,
            "max_dataset_character_3gram_jaccard": round(maximum, 4),
            "max_dataset_character_3gram_pair": maximum_pair,
            "source_sha256": dict(sorted(source_hashes.items())),
            "limitation": "Exact audit includes RAG; near audit covers canonical datasets. v0.5 uses the same category/template families as v0.4 with deterministic lexical variation, so structural independence is limited.",
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
