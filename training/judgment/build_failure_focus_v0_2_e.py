"""Build v0.2-E data for minimal-correction regressions found in v0.2-D.

Holdouts are read only for contamination checks. Their labels and model outputs
are never used to construct examples.
"""

from __future__ import annotations

from collections import Counter, defaultdict
import hashlib
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
BASE = DATA_DIR / "pilot_v0.2_d.jsonl"
ADDITION = DATA_DIR / "failure_focus_v0.2_e.jsonl"
COMBINED = DATA_DIR / "pilot_v0.2_e.jsonl"
CHATML = DATA_DIR / "failure_focus_v0.2_e_chatml"
MANIFEST = DATA_DIR / "failure_focus_v0.2_e.manifest.json"
AUDIT_DATASETS = (
    ROOT / "evaluation/judgment/seed_v0.1.jsonl",
    ROOT / "evaluation/judgment/holdout_v0.1.jsonl",
    ROOT / "evaluation/judgment/holdout_v0.2.jsonl",
    BASE,
)
VERSION = "failure-focus-v0.2-e"
VALIDATED_AT = "2026-09-29"
NEAR_THRESHOLD = 0.85


def build_generated() -> list[dict]:
    builder = Builder(start=749)

    def add(family: str, index: int, text: str, decision: str, *, reason: str,
            context: str | None = None,
            changes: list[tuple[str, str, str]] | None = None,
            pair: str | None = None, dev: bool = False):
        edits = _edits(text, changes) if changes else []
        row = builder.add(
            family=f"v02e_{family}_{'dev' if dev else 'train'}",
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

    potential_pairs = [
        ("妹は英語を話せます。", "妹は英語を話せるます。", "話せるます", "話せます"),
        ("父は大型車を運転できます。", "父は大型車を運転できるます。", "できるます", "できます"),
        ("佐藤さんは難しい漢字を読めます。", "佐藤さんは難しい漢字を読めるます。", "読めるます", "読めます"),
        ("私は二百メートル泳げます。", "私は二百メートル泳げるます。", "泳げるます", "泳げます"),
    ]
    connective_pairs = [
        ("この毛布は柔らかくて、暖かいです。", "この毛布は柔らかいくて、暖かいです。", "柔らかいくて", "柔らかくて"),
        ("あの道は細くて、暗かったです。", "あの道は細いくて、暗かったです。", "細いくて", "細くて"),
        ("新しい机は広くて、使いやすいです。", "新しい机は広いくて、使いやすいです。", "広いくて", "広くて"),
        ("旅館の料理は多くて、おいしかったです。", "旅館の料理は多いくて、おいしかったです。", "多いくて", "多くて"),
    ]
    modifier_pairs = [
        ("大きい窓から海が見えます。", "大きいな窓から海が見えます。", "大きいな", "大きい"),
        ("赤い傘を玄関に置きました。", "赤いな傘を玄関に置きました。", "赤いな", "赤い"),
        ("面白い映画を家族と見ました。", "面白いな映画を家族と見ました。", "面白いな", "面白い"),
        ("古い時計が棚にあります。", "古いな時計が棚にあります。", "古いな", "古い"),
    ]
    compound_pairs = [
        ("この教室は広くて、静かです。", "この教室は広いくて、静かなです。",
         [("広いくて", "広くて", "adjective_conjugation"),
          ("静かなです", "静かです", "copula_conjugation")]),
        ("白い猫が廊下にいます。", "白いな猫が廊下でいます。",
         [("白いな", "白い", "modifier_connection"),
          ("廊下で", "廊下に", "particle_misuse")]),
        ("弟は速く走れます。", "弟は速いく走れるます。",
         [("速いく", "速く", "adjective_conjugation"),
          ("走れるます", "走れます", "verb_conjugation")]),
        ("この鞄は軽くて、丈夫です。", "この鞄は軽いくて、丈夫なです。",
         [("軽いくて", "軽くて", "adjective_conjugation"),
          ("丈夫なです", "丈夫です", "copula_conjugation")]),
    ]

    pair_groups = (
        ("potential_polite", potential_pairs),
        ("i_adjective_connective", connective_pairs),
        ("i_adjective_modifier", modifier_pairs),
    )
    for family, pairs in pair_groups:
        for index, (correct, wrong, source, replacement) in enumerate(pairs):
            dev = index == 3
            pair = f"v02e-{family}-{index + 1}"
            add(f"{family}_ok", index, correct, "acceptable", dev=dev, pair=pair,
                reason="현재 문체와 활용이 자연스러우므로 원문을 유지합니다.")
            add(f"{family}_error", index, wrong, "needs_correction", dev=dev,
                pair=pair, changes=[(source, replacement,
                    "verb_conjugation" if family == "potential_polite"
                    else "adjective_conjugation" if family == "i_adjective_connective"
                    else "modifier_connection")],
                reason="원문의 정중체와 의미를 유지하면서 잘못된 활용만 최소 교정합니다.")

    for index, (correct, wrong, changes) in enumerate(compound_pairs):
        dev = index == 3
        pair = f"v02e-compound-{index + 1}"
        add("compound_ok", index, correct, "acceptable", dev=dev, pair=pair,
            reason="형용사 활용과 문체가 모두 자연스럽습니다.")
        add("compound_error", index, wrong, "needs_correction", dev=dev,
            pair=pair, changes=changes,
            reason="복합 오류를 모두 고치되 의미와 정중체는 그대로 유지합니다.")

    colloquial = [
        "今、何見てる？", "今日はどこで食べる？", "昨日の試合、見た？", "誰と話してる？",
        "このあと何する？", "明日もここに来る？", "その映画、知ってる？", "駅まで歩いて帰る？",
    ]
    for index, text in enumerate(colloquial):
        add("colloquial_question_ok", index, text, "acceptable", dev=index in {3, 7},
            reason="완결된 자연스러운 구어체 의문문이므로 문맥이 없어도 보류하지 않습니다.")

    polite_ok = [
        "姉は一人で着物を着られます。", "祖父は小さい文字も読めます。",
        "この部屋は明るくて、暖かいです。", "青い鳥が庭にいます。",
        "兄は一時間続けて歩けます。", "この椅子は低くて、座りやすいです。",
        "丸い机を窓際に置きました。", "母は地図がなくても帰れます。",
    ]
    for index, text in enumerate(polite_ok):
        add("polite_form_ok", index, text, "acceptable", dev=index in {3, 7},
            reason="정중체와 활용이 모두 자연스러우므로 원문을 유지합니다.")

    extra_potential = [
        ("彼はこの機械を使えるます。", "使えるます", "使えます"),
        ("私は辛い料理も食べられるます。", "食べられるます", "食べられます"),
        ("山田さんは中国語を書けるます。", "書けるます", "書けます"),
        ("妹は自転車に乗れるます。", "乗れるます", "乗れます"),
    ]
    for index, (text, source, replacement) in enumerate(extra_potential):
        add("potential_polite_extra", index, text, "needs_correction", dev=index == 3,
            changes=[(source, replacement, "verb_conjugation")],
            reason="정중체를 보통체로 바꾸지 않고 가능 동사의 접속만 고칩니다.")

    extra_connective = [
        ("この箱は重いくて、運びにくいです。", "重いくて", "重くて"),
        ("駅は近いくて、便利です。", "近いくて", "近くて"),
        ("昨日の風は強いくて、冷たかったです。", "強いくて", "強くて"),
        ("この説明は長いくて、分かりにくいです。", "長いくて", "長くて"),
    ]
    for index, (text, source, replacement) in enumerate(extra_connective):
        add("i_adjective_connective_extra", index, text, "needs_correction", dev=index == 3,
            changes=[(source, replacement, "adjective_conjugation")],
            reason="い형용사의 연결형만 고치고 나머지 문체는 유지합니다.")

    extra_modifier = [
        ("安いな切符を二枚買いました。", "安いな", "安い"),
        ("長いな橋をゆっくり渡りました。", "長いな", "長い"),
        ("涼しいな風が窓から入ります。", "涼しいな", "涼しい"),
        ("新しいな靴を旅行に持っていきます。", "新しいな", "新しい"),
    ]
    for index, (text, source, replacement) in enumerate(extra_modifier):
        add("i_adjective_modifier_extra", index, text, "needs_correction", dev=index == 3,
            changes=[(source, replacement, "modifier_connection")],
            reason="い형용사의 명사 수식에서 불필요한 な만 제거합니다.")

    compound_extra = [
        ("この宿は古いくて、静かなです。", [("古いくて", "古くて", "adjective_conjugation"), ("静かなです", "静かです", "copula_conjugation")]),
        ("小さいな犬が玄関でいます。", [("小さいな", "小さい", "modifier_connection"), ("玄関で", "玄関に", "particle_misuse")]),
        ("姉は速いく泳げるます。", [("速いく", "速く", "adjective_conjugation"), ("泳げるます", "泳げます", "verb_conjugation")]),
        ("黄色いな花が机の上であります。", [("黄色いな", "黄色い", "modifier_connection"), ("机の上で", "机の上に", "particle_misuse")]),
        ("この薬は苦いくて、飲みにくいでした。", [("苦いくて", "苦くて", "adjective_conjugation"), ("飲みにくいでした", "飲みにくかったです", "adjective_conjugation")]),
        ("弟は小さいな字も読めるます。", [("小さいな", "小さい", "modifier_connection"), ("読めるます", "読めます", "verb_conjugation")]),
        ("昨日の部屋は寒いくて、不便なでした。", [("寒いくて", "寒くて", "adjective_conjugation"), ("不便なでした", "不便でした", "copula_conjugation")]),
        ("丸いな時計が受付であります。", [("丸いな", "丸い", "modifier_connection"), ("受付で", "受付に", "particle_misuse")]),
    ]
    for index, (text, changes) in enumerate(compound_extra):
        add("compound_extra", index, text, "needs_correction", dev=index in {3, 7},
            changes=changes,
            reason="두 오류를 모두 고치되 원문의 의미와 정중체를 유지합니다.")

    existence_extra = [
        ("温室の奥で珍しい花があります。", "温室の奥で", "温室の奥に"),
        ("校舎の屋上で大きなアンテナがあります。", "校舎の屋上で", "校舎の屋上に"),
        ("待合室で案内係がいます。", "待合室で", "待合室に"),
        ("倉庫の入口で警備員がいます。", "倉庫の入口で", "倉庫の入口に"),
    ]
    for index, (text, source, replacement) in enumerate(existence_extra):
        add("existence_extra", index, text, "needs_correction", dev=index == 3,
            changes=[(source, replacement, "particle_misuse")],
            reason="존재 장소를 나타내는 조사 で만 に로 고칩니다.")

    foreign = [
        "회의는 오후 세 시에 시작합니다.", "금요일 저녁에는 도서관에 갑니다.",
        "제 동생은 일본 영화를 좋아합니다.", "다음 역에서 내려야 합니다.",
        "The meeting starts after lunch.", "My sister can read this map.",
        "Please leave the package by the door.", "We are waiting near the ticket gate.",
    ]
    for index, text in enumerate(foreign):
        add("foreign_out_of_scope", index, text, "insufficient_evidence",
            dev=index in {3, 7},
            reason="일본어 문법 판단 대상 밖의 입력이며 번역을 교정문으로 생성하지 않습니다.")

    generated = builder.records
    for row in generated:
        row["tags"] = [VERSION if tag == "hard-negatives-v0.2-b" else tag
                       for tag in row["tags"]]
        row["provenance"]["source_id"] = VERSION
        row["review"]["reviewed_at"] = VALIDATED_AT

    expected_decisions = {"acceptable": 32, "needs_correction": 40,
                          "insufficient_evidence": 8}
    if len(generated) != 80 or Counter(row["expected"]["decision"] for row in generated) != expected_decisions:
        raise ValueError("Unexpected v0.2-E size or decision distribution")
    split_counts = Counter(row["split"] for row in generated)
    if split_counts != {"pilot_train": 60, "pilot_dev": 20}:
        raise ValueError(f"Unexpected v0.2-E split distribution: {split_counts}")
    if sum(len(row["expected"]["edits"]) > 1 for row in generated) != 12:
        raise ValueError("Expected exactly twelve compound corrections")
    pair_splits = defaultdict(set)
    for row, metadata in zip(generated, builder.metadata):
        if metadata["pair_id"]:
            pair_splits[metadata["pair_id"]].add(row["split"])
    if len(pair_splits) != 16 or any(len(splits) != 1 for splits in pair_splits.values()):
        raise ValueError("Expected sixteen co-located normal/error pairs")
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
    if len(base) != 748 or len(combined) != 828 or combined[:748] != base:
        raise ValueError("The v0.2-D base must remain unchanged")
    _write_jsonl(ADDITION, generated)
    _write_jsonl(COMBINED, combined)
    chatml = export(COMBINED, CHATML, output_contract="v0.2")
    manifest = {
        "dataset_id": "judgment-pilot-v0.2-e", "generation_version": VERSION,
        "validated_at": VALIDATED_AT, "output_contract": "judgment-v0.2",
        "source_dataset": str(BASE.relative_to(ROOT)), "source_dataset_sha256": _sha256(BASE),
        "augmentation_path": str(ADDITION.relative_to(ROOT)),
        "augmentation_sha256": _sha256(ADDITION),
        "combined_path": str(COMBINED.relative_to(ROOT)),
        "combined_sha256": _sha256(COMBINED),
        "augmentation_summary": summary(generated), "combined_summary": summary(combined),
        "generated_validation": {
            "records": len(generated), "human_reviewed": False, "expert_reviewed": False,
            "compound_error_cases": 12, "paired_cases": 16,
            "contamination_audit": audit,
        },
        "chatml": chatml,
        "holdout_policy": "Holdouts used only for overlap audit; no model predictions inspected or used for training.",
    }
    MANIFEST.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return manifest


if __name__ == "__main__":
    print(json.dumps(build(), ensure_ascii=False, indent=2))
