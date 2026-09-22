"""Build v0.2-C additions focused only on the eleven v0.2-B failures."""
from __future__ import annotations

from collections import Counter
import hashlib
import json
from pathlib import Path

from training.judgment.build_hard_negatives import Builder, ROOT, _write_jsonl
from training.judgment.data import exact_overlap, load_records, summary, validate_records
from training.judgment.export_chatml import export

BASE = Path(__file__).with_name("data") / "pilot_v0.2_b.jsonl"
ADDITION = Path(__file__).with_name("data") / "failure_focus_v0.2_c.jsonl"
OUTPUT = Path(__file__).with_name("data") / "pilot_v0.2_c.jsonl"
CHATML = Path(__file__).with_name("data") / "failure_focus_v0.2_c_chatml"
MANIFEST = Path(__file__).with_name("data") / "failure_focus_v0.2_c.manifest.json"
SEED = ROOT / "evaluation/judgment/seed_v0.1.jsonl"
RAG = ROOT / "rag_data"
VERSION = "failure-focus-v0.2-c"
VALIDATED_AT = "2026-09-17"

ACCEPTANCE = {
 "jg020_polite_acceptance": [
  ("はい、ぜひ参加したいです。", "상대방이 행사 참여를 제안했습니다."),
  ("ええ、ぜひお願いしたいです。", "상대방이 안내를 도와주겠다고 제안했습니다."),
  ("はい、ぜひ飲んでみたいです。", "상대방이 차를 권했습니다."),
  ("ぜひ、よろしくお願いします。", "상대방이 함께 진행하자고 제안했습니다."),
  ("はい、喜んでお願いします。", "상대방이 예약을 대신해 주겠다고 제안했습니다."),
  ("ええ、ぜひ見せてください。", "상대방이 사진을 보여주겠다고 했습니다."),
  ("はい、ぜひ教えてください。", "상대방이 사용법을 설명해 주겠다고 했습니다."),
  ("ぜひ一緒に行きたいです。", "상대방이 동행을 제안했습니다."),
 ],
 "jg068_stt_orthography": [
  ("雑誌お買います。", "STT가 생성한 전사 텍스트이며 원음과 대안 전사는 없습니다."),
  ("手紙お書きます。", "STT가 생성한 전사 텍스트이며 원음과 대안 전사는 없습니다."),
  ("音楽お聞きます。", "STT가 생성한 전사 텍스트이며 원음과 대안 전사는 없습니다."),
  ("写真お撮ります。", "STT가 생성한 전사 텍스트이며 원음과 대안 전사는 없습니다."),
  ("薬お飲みます。", "STT가 생성한 전사 텍스트이며 원음과 대안 전사는 없습니다."),
  ("新聞お読みます。", "STT가 생성한 전사 텍스트이며 원음과 대안 전사는 없습니다."),
  ("切符お買いました。", "STT가 생성한 전사 텍스트이며 원음과 대안 전사는 없습니다."),
  ("荷物お送りました。", "STT가 생성한 전사 텍스트이며 원음과 대안 전사는 없습니다."),
 ],
}

# Four fresh normal/error minimal pairs for each missed or non-minimal failure family.
PAIRS = {
 "jg027_existence_particle": ("particle_misuse", [
  ("倉庫の奥に道具があります。", "倉庫の奥で道具があります。"),
  ("受付の横に案内図があります。", "受付の横で案内図があります。"),
  ("机の上に申込書があります。", "机の上で申込書があります。"),
  ("玄関の前に宅配便があります。", "玄関の前で宅配便があります。"),]),
 "jg035_i_adj_past": ("adjective_conjugation", [
  ("昨夜の風は強かったです。", "昨夜の風は強いかったです。"),
  ("先週の課題は易しかったです。", "先週の課題は易しいかったです。"),
  ("昨日の道は暗かったです。", "昨日の道は暗いかったです。"),
  ("朝の電車は早かったです。", "朝の電車は早いかったです。"),]),
 "jg030_masu_past": ("verb_conjugation", [
  ("先ほど、窓口で申込書を書きました。", "先ほど、窓口で申込書を書くました。"),
  ("昨日、食堂で昼食を食べました。", "昨日、食堂で昼食を食べるました。"),
  ("さっき、受付で名前を言いました。", "さっき、受付で名前を言うました。"),
  ("昨夜、家族に電話を掛けました。", "昨夜、家族に電話を掛けるました。"),]),
 "jg034_obligation": ("verb_conjugation", [
  ("今日は薬を飲まなければなりません。", "今日は薬を飲むなければなりません。"),
  ("明朝は六時に出なければなりません。", "明朝は六時に出るなければなりません。"),
  ("今週中に返さなければなりません。", "今週中に返すなければなりません。"),
  ("授業では日本語で話さなければなりません。", "授業では日本語で話すなければなりません。"),]),
 "jg036_i_adj_negative": ("adjective_conjugation", [
  ("この上着は厚くないです。", "この上着は厚いくないです。"),
  ("その道は遠くないです。", "その道は遠いくないです。"),
  ("今日の宿題は多くないです。", "今日の宿題は多いくないです。"),
  ("この飲み物は甘くないです。", "この飲み物は甘いくないです。"),]),
 "jg037_permission": ("verb_conjugation", [
  ("ここでは帽子を取らなくてもいいです。", "ここでは帽子を取るなくてもいいです。"),
  ("明日は早く来なくてもいいです。", "明日は早く来るなくてもいいです。"),
  ("全部を覚えなくてもいいです。", "全部を覚えるなくてもいいです。"),
  ("この欄は書かなくてもいいです。", "この欄は書くなくてもいいです。"),]),
 "jg040_potential_polite": ("verb_conjugation", [
  ("姉は一人で運転できます。", "姉は一人で運転できるます。"),
  ("私は少し中国語を話せます。", "私は少し中国語を話せるます。"),
  ("祖父は眼鏡なしで読めます。", "祖父は眼鏡なしで読めるます。"),
  ("弟は百メートル泳げます。", "弟は百メートル泳げるます。"),]),
 "jg046_two_adjectives": ("adjective_conjugation", [
  ("昨日の料理は辛くて、おいしかったです。", "昨日の料理は辛いくて、おいしいでした。"),
  ("その映画は長くて、面白かったです。", "その映画は長いくて、面白いでした。"),
  ("旅館の部屋は広くて、明るかったです。", "旅館の部屋は広いくて、明るいでした。"),
  ("冬の海は冷たくて、怖かったです。", "冬の海は冷たいくて、怖いでした。"),]),
 "jg047_destination_past": ("verb_conjugation", [
  ("先週、叔母の家に行きました。", "先週、叔母の家で行くました。"),
  ("昨日、区民会館に行きました。", "昨日、区民会館で行くました。"),
  ("午前中、検査室に行きました。", "午前中、検査室で行くました。"),
  ("休みに祖父の家に行きました。", "休みに祖父の家で行くました。"),]),
}


def _sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()


def build():
    builder = Builder(start=541)
    for family, items in ACCEPTANCE.items():
        for i, (text, context) in enumerate(items):
            split = "pilot_train" if i < 6 else "pilot_dev"
            builder.add(family=f"v02c_{family}_{split}", split=split, text=text, context=context,
                        decision="acceptable", reason="문법 교정 대상이 아니며 원문의 문체·전사 경계를 유지합니다.", source_anchor_id=family)
    for family, (error_type, items) in PAIRS.items():
        for i, (normal, erroneous) in enumerate(items):
            split = "pilot_train" if i < 3 else "pilot_dev"
            fam = f"v02c_{family}_{split}"
            pair_id = f"v02c-{family}-{i+1}"
            ok = builder.add(family=fam, split=split, text=normal, context=None, decision="acceptable",
                             reason="문법과 활용이 자연스러우므로 원문을 유지합니다.", pair_id=pair_id, source_anchor_id=family)
            builder.add(family=fam, split=split, text=erroneous, context=None, decision="needs_correction",
                        corrected_text=normal, error_type=error_type,
                        reason="문체와 의미를 유지하면서 해당 문법 형태만 최소 교정합니다.", pair_id=pair_id, source_anchor_id=ok["id"])
    generated = builder.records
    for row in generated:
        row["tags"] = [VERSION if x == "hard-negatives-v0.2-b" else x for x in row["tags"]]
        row["provenance"]["source_id"] = VERSION
        row["review"]["reviewed_at"] = VALIDATED_AT
        family = row["template_family_id"]
        if row["expected"]["decision"] == "needs_correction" and "jg046_two_adjectives" in family:
            text = row["input"]["text"]
            first_source = next(x for x in ("辛いくて", "長いくて", "広いくて", "冷たいくて") if x in text)
            first_replacement = {"辛いくて":"辛くて", "長いくて":"長くて", "広いくて":"広くて", "冷たいくて":"冷たくて"}[first_source]
            second_source = next(x for x in ("おいしいでした", "面白いでした", "明るいでした", "怖いでした") if x in text)
            second_replacement = {"おいしいでした":"おいしかったです", "面白いでした":"面白かったです", "明るいでした":"明るかったです", "怖いでした":"怖かったです"}[second_source]
            row["expected"]["edits"] = [
                {"start":text.index(first_source),"end":text.index(first_source)+len(first_source),"source":first_source,"replacement":first_replacement,"error_type":"adjective_conjugation"},
                {"start":text.index(second_source),"end":text.index(second_source)+len(second_source),"source":second_source,"replacement":second_replacement,"error_type":"adjective_conjugation"},
            ]
        if row["expected"]["decision"] == "needs_correction" and "jg047_destination_past" in family:
            text = row["input"]["text"]; particle = text.index("で行くました")
            verb = text.index("行くました")
            row["expected"]["edits"] = [
                {"start":particle,"end":particle+1,"source":"で","replacement":"に","error_type":"particle_misuse"},
                {"start":verb,"end":verb+5,"source":"行くました","replacement":"行きました","error_type":"verb_conjugation"},
            ]
            if "particle_misuse" not in row["tags"]: row["tags"].append("particle_misuse")
    for item in builder.metadata:
        item["generation_version"] = VERSION
    validate_records(generated, require_reviewed=True)
    decisions = Counter(r["expected"]["decision"] for r in generated)
    if len(generated) != 88 or decisions != {"acceptable": 52, "needs_correction": 36}:
        raise ValueError(f"unexpected additions: {len(generated)}, {decisions}")
    overlap = exact_overlap(generated, seed_path=SEED, rag_dir=RAG)
    if overlap["matches"]:
        raise ValueError(f"seed/RAG exact overlap: {overlap['matches'][:3]}")
    base = load_records(BASE); validate_records(base, require_reviewed=True)
    combined = base + generated; validate_records(combined, require_reviewed=True)
    _write_jsonl(ADDITION, generated); _write_jsonl(OUTPUT, combined)
    chatml = export(OUTPUT, CHATML, output_contract="v0.2")
    manifest = {
      "dataset_id":"judgment-pilot-v0.2-c", "generation_version":VERSION, "validated_at":VALIDATED_AT,
      "source_dataset":str(BASE.relative_to(ROOT)), "source_dataset_sha256":_sha(BASE),
      "augmentation_path":str(ADDITION.relative_to(ROOT)), "augmentation_sha256":_sha(ADDITION),
      "combined_path":str(OUTPUT.relative_to(ROOT)), "combined_sha256":_sha(OUTPUT),
      "output_contract":"judgment-v0.2", "focus_failure_ids":["JG-020","JG-068","JG-027","JG-035","JG-030","JG-034","JG-036","JG-037","JG-040","JG-046","JG-047"],
      "generated_validation":{"total":len(generated),"decisions":dict(sorted(decisions.items())),"exact_seed_rag_matches":0,"human_reviewed":False,"expert_reviewed":False},
      "combined_summary":summary(combined), "generation_metadata":builder.metadata, "chatml":chatml,
    }
    MANIFEST.write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+"\n")
    return manifest

if __name__ == "__main__":
 print(json.dumps(build(),ensure_ascii=False,indent=2))
