"""Build v0.2-G synthetic data for non-correction contract preservation.

No operational STT text or model output is used. Consumed holdouts and older
augmentations are read only for deterministic contamination checks.
"""

from __future__ import annotations

from collections import Counter, defaultdict
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
ADDITION = DATA_DIR / "contract_preservation_v0.2_g.jsonl"
COMBINED = DATA_DIR / "pilot_v0.2_g.jsonl"
CHATML = DATA_DIR / "contract_preservation_v0.2_g_chatml"
MANIFEST = DATA_DIR / "contract_preservation_v0.2_g.manifest.json"
AUDIT_DATASETS = (
    ROOT / "evaluation/judgment/seed_v0.1.jsonl",
    ROOT / "evaluation/judgment/holdout_v0.1.jsonl",
    ROOT / "evaluation/judgment/holdout_v0.2.jsonl",
    ROOT / "evaluation/judgment/holdout_v0.3.jsonl",
    BASE,
    DATA_DIR / "failure_focus_v0.2_e.jsonl",
    DATA_DIR / "failure_focus_v0.2_f.jsonl",
)
VERSION = "contract-preservation-v0.2-g"
VALIDATED_AT = "2026-10-03"
NEAR_THRESHOLD = 0.85


def build_generated() -> list[dict]:
    builder = Builder(start=949)

    def add(family: str, index: int, text: str, decision: str, *, reason: str,
            context: str | None = None,
            changes: list[tuple[str, str, str]] | None = None,
            pair: str | None = None, dev: bool = False):
        edits = _edits(text, changes) if changes else []
        row = builder.add(
            family=f"v02g_{family}_{'dev' if dev else 'train'}",
            split="pilot_dev" if dev else "pilot_train",
            text=text,
            context=context,
            decision=decision,
            reason=reason,
            corrected_text=_apply(text, edits) if edits else None,
            error_type=edits[0]["error_type"] if edits else None,
            pair_id=pair,
            source_anchor_id=None,
        )
        if edits:
            row["expected"]["edits"] = edits
            for error_type in dict.fromkeys(edit["error_type"] for edit in edits):
                if error_type not in row["tags"]:
                    row["tags"].append(error_type)
        return row

    short_colloquial = [
        "うん、もう着いたよ。", "いや、今日は行かない。", "これ、借りてもいい？",
        "あとで電話するね。", "今ちょうど食べてる。", "それ、私も知ってるよ。",
        "まだ決めてないんだ。", "ちょっと外を見てくる。", "駅ならすぐそこだよ。",
        "今日はもう帰るね。", "その話、初めて聞いた。", "たぶん間に合うと思う。",
        "こっちは準備できてるよ。", "先に席を取っておくね。", "今は手が離せない。",
        "明日なら大丈夫だよ。", "それで問題ないと思う。", "もう少しだけ待ってて。",
        "鍵は机の上にあるよ。", "この道で合ってるよ。",
    ]
    for index, text in enumerate(short_colloquial):
        add("short_colloquial_ok", index, text, "acceptable",
            context="친한 사람과 나누는 일상 대화", dev=index % 4 == 3,
            reason="문맥에 맞는 짧은 구어체이므로 원문을 그대로 유지합니다.")

    fillers = [
        "えっと、集合場所は南口ですよね。", "あの、領収書を一枚ください。",
        "うーん、その時間なら空いています。", "その、資料は机に置きました。",
        "ええと、次の便は午後三時です。", "あのう、窓を開けてもいいですか。",
        "まあ、今回はこの案で進めます。", "ほら、向こうに看板があります。",
        "えっと、この番号で予約しました。", "あの、先ほど電話した者です。",
        "うーん、今日は歩いて帰ります。", "その、入口は反対側にあります。",
    ]
    for index, text in enumerate(fillers):
        add("filler_literal_ok", index, text, "acceptable", dev=index % 4 == 3,
            reason="필러와 구두점을 삭제하거나 다듬지 않고 원문을 유지합니다.")

    opaque_stt = [
        "今朝わ薬お飲みました。", "弟わ写真お二枚撮りました。",
        "昨日わ資料お家で読みました。", "母わ切符お先に買いました。",
        "午後わ荷物お受付に預けます。", "友達わ音楽お静かに聞いています。",
        "先週わ手紙お三通書きました。", "父わ新聞お毎朝読んでいます。",
    ]
    for index, text in enumerate(opaque_stt):
        add("stt_orthography_preserve", index, text, "acceptable",
            context="일본어 말하기의 STT 전사이며 원음과 대안 전사는 없음",
            dev=index % 4 == 3,
            reason="원음 없이 표기 책임을 단정하거나 전사 문자열을 바꾸지 않습니다.")

    incomplete = [
        "来月の研修が終わったあと……", "もし受付に誰もいなかったら……",
        "昨日、担当者から聞いた話では……", "この申請書を書いたのは……",
        "駅前の店で待っていたけれど……", "次の休みに時間があれば……",
        "会議で最初に説明したのは……", "その荷物を玄関まで運んで……",
        "新しい機械の使い方について……", "さっき電話をかけたところ……",
        "先生に相談しようと思って……", "旅行の予定を変更した理由は……",
        "この薬を飲んだあとに……", "雨が強くならないうちに……",
        "来週の発表で使う資料を……", "窓の近くに置いてあったのは……",
        "友達が駅に着くまで……", "明日の朝、出発する前に……",
        "店員さんに値段を聞いたら……", "あの書類を提出した人は……",
    ]
    for index, text in enumerate(incomplete):
        add("incomplete_literal_hold", index, text, "insufficient_evidence",
            context="발화가 표시된 지점에서 끝났으며 뒤 내용은 녹음되지 않음",
            dev=index % 4 == 3,
            reason="누락된 뒤 내용을 완성하거나 원문의 일부를 삭제하지 않습니다.")

    noisy = [
        "明日は［聞き取れない］で打ち合わせます。", "受付の横に［雑音］があります。",
        "昨日は［音声欠落］かったです。", "この箱を［聞き取れない］へ運びます。",
        "先生が［雑音］と説明しました。", "午後から［音声欠落］に参加します。",
        "私は［聞き取れない］を二つ買いました。", "駅で［雑音］に会いました。",
    ]
    for index, text in enumerate(noisy):
        add("missing_span_literal_hold", index, text, "insufficient_evidence",
            context="대괄호 구간의 음성을 복원할 근거가 없음", dev=index % 4 == 3,
            reason="식별되지 않은 구간을 추측하거나 표식을 삭제하지 않습니다.")

    foreign = [
        "Please leave the package at the front desk.",
        "The briefing begins shortly after noon.",
        "오늘 오후에는 도서관에서 공부합니다.",
        "회의가 끝나면 바로 연락할게요.",
    ]
    for index, text in enumerate(foreign):
        add("foreign_literal_hold", index, text, "insufficient_evidence",
            dev=index == 3,
            reason="일본어 판단 범위 밖의 입력을 번역하거나 줄이지 않고 유지합니다.")

    pairs = [
        ("毎週、屋上の花に水をやります。", "毎週、屋上の花に水をやるます。",
         "やるます", "やります", "verb_conjugation"),
        ("昨夜の風は弱かったです。", "昨夜の風は弱いかったです。",
         "弱いかった", "弱かった", "adjective_conjugation"),
        ("この通りは静かです。", "この通りは静かなです。",
         "静かなです", "静かです", "copula_conjugation"),
        ("便利な道具を使っています。", "便利道具を使っています。",
         "便利道具", "便利な道具", "modifier_connection"),
        ("午後は資料館に行きます。", "午後は資料館を行きます。",
         "資料館を", "資料館に", "particle_misuse"),
        ("倉庫の奥に予備の椅子があります。", "倉庫の奥で予備の椅子があります。",
         "倉庫の奥で", "倉庫の奥に", "particle_misuse"),
        ("先月、その講座を受けました。", "先月、その講座を受けます。",
         "受けます", "受けました", "tense_mismatch"),
        ("ここでは上着を脱がなくてもいいです。", "ここでは上着を脱ぐなくてもいいです。",
         "脱ぐなくても", "脱がなくても", "verb_conjugation"),
        ("改札の前でしばらく待ってください。", "改札の前でしばらく待つてください。",
         "待つて", "待って", "verb_conjugation"),
        ("妹は一人で泳げます。", "妹は一人で泳げるます。",
         "泳げるます", "泳げます", "verb_conjugation"),
        ("昨日は何も買いませんでした。", "昨日は何も買いませんでしたです。",
         "買いませんでしたです", "買いませんでした", "copula_conjugation"),
        ("この机はあまり高くないです。", "この机はあまり高いくないです。",
         "高いくない", "高くない", "adjective_conjugation"),
    ]
    for index, (correct, wrong, source, replacement, error_type) in enumerate(pairs):
        dev = index % 4 == 3
        pair = f"v02g-contract-pair-{index + 1}"
        add("minimal_pair_ok", index, correct, "acceptable", pair=pair, dev=dev,
            reason="문법적으로 올바른 원문을 교정 대상으로 바꾸지 않습니다.")
        add("minimal_pair_error", index, wrong, "needs_correction", pair=pair, dev=dev,
            changes=[(source, replacement, error_type)],
            reason="명시된 문법 오류 한 곳만 고치고 나머지 원문은 유지합니다.")

    standalone_errors = [
        ("朝は駅前の店を行きます。", "店を", "店に", "particle_misuse"),
        ("倉庫の入口で案内板があります。", "倉庫の入口で", "倉庫の入口に", "particle_misuse"),
        ("毎週、観察記録を書くます。", "書くます", "書きます", "verb_conjugation"),
        ("さっき友達に会うました。", "会うました", "会いました", "verb_conjugation"),
        ("ここで靴を脱ぐてください。", "脱ぐて", "脱いで", "verb_conjugation"),
        ("昨日の海は青いかったです。", "青いかった", "青かった", "adjective_conjugation"),
        ("この毛布は暖かいくないです。", "暖かいくない", "暖かくない", "adjective_conjugation"),
        ("親切人に道を聞きました。", "親切人", "親切な人", "modifier_connection"),
        ("細いな道を通りました。", "細いな道", "細い道", "modifier_connection"),
        ("この作業場は安全なです。", "安全なです", "安全です", "copula_conjugation"),
        ("来週、その試験を受けました。", "受けました", "受けます", "tense_mismatch"),
        ("一昨日は予定より早く帰ります。", "帰ります", "帰りました", "tense_mismatch"),
    ]
    for index, (text, source, replacement, error_type) in enumerate(standalone_errors):
        add("explicit_error", index, text, "needs_correction", dev=index % 4 == 3,
            changes=[(source, replacement, error_type)],
            reason="교정이 필요한 문법 형태만 최소한으로 바꿉니다.")

    generated = builder.records
    for row in generated:
        row["tags"] = [
            VERSION if tag == "hard-negatives-v0.2-b" else tag
            for tag in row["tags"]
        ]
        row["provenance"]["source_id"] = VERSION
        row["review"]["reviewed_at"] = VALIDATED_AT

    expected_decisions = {
        "acceptable": 52, "insufficient_evidence": 32, "needs_correction": 24,
    }
    if len(generated) != 108:
        raise ValueError(f"Expected 108 new records, got {len(generated)}")
    if Counter(row["expected"]["decision"] for row in generated) != expected_decisions:
        raise ValueError("Unexpected v0.2-G decision distribution")
    if Counter(row["split"] for row in generated) != {
        "pilot_train": 81, "pilot_dev": 27,
    }:
        raise ValueError("Unexpected v0.2-G split distribution")
    pair_splits = defaultdict(set)
    pair_counts = Counter()
    for row, metadata in zip(generated, builder.metadata):
        if metadata["pair_id"]:
            pair_splits[metadata["pair_id"]].add(row["split"])
            pair_counts[metadata["pair_id"]] += 1
    if len(pair_splits) != 12 or any(
        len(splits) != 1 for splits in pair_splits.values()
    ) or any(count != 2 for count in pair_counts.values()):
        raise ValueError("Expected twelve co-located complete minimal pairs")
    validate_records(generated, require_reviewed=True)
    return generated


def _audit(generated: list[dict]) -> dict:
    references: dict[str, set[str]] = defaultdict(set)
    source_hashes = {}
    for path in AUDIT_DATASETS:
        relative = str(path.relative_to(ROOT))
        source_hashes[relative] = _sha256(path)
        for row in load_records(path):
            values = {
                row["input"]["text"], row["expected"]["corrected_text"],
                *row["accepted_corrections"],
            }
            for value in values:
                if len(fp := _fingerprint(value)) >= 4:
                    references[fp].add(relative)
    for path in sorted((ROOT / "rag_data").rglob("*.json")):
        relative = str(path.relative_to(ROOT))
        source_hashes[relative] = _sha256(path)

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
                references[fp].add(relative)

    exact = []
    for row in generated:
        values = {
            row["input"]["text"], row["expected"]["corrected_text"],
            *row["accepted_corrections"],
        }
        for value in values:
            fp = _fingerprint(value)
            if len(fp) >= 4 and fp in references:
                exact.append({
                    "id": row["id"], "text": value,
                    "sources": sorted(references[fp]),
                })
    if exact:
        raise ValueError(f"Exact normalized overlap: {exact[:8]}")

    old_grams = [
        (fp, _trigrams(fp))
        for fp, sources in references.items()
        if len(fp) >= 5 and any(source.endswith(".jsonl") for source in sources)
    ]
    near, highest = [], 0.0
    for row in generated:
        values = {
            row["input"]["text"], row["expected"]["corrected_text"],
            *row["accepted_corrections"],
        }
        for value in values:
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
                    near.append({
                        "id": row["id"], "text": value,
                        "previous": previous, "jaccard": round(score, 4),
                    })
    if near:
        raise ValueError(f"Near-duplicate dataset overlap: {near[:8]}")
    return {
        "exact_normalized_matches": 0,
        "near_dataset_matches_at_or_above_0_85": 0,
        "max_dataset_character_3gram_jaccard": round(highest, 4),
        "source_sha256": source_hashes,
        "limitation": (
            "Exact overlap includes RAG JSON. Near audit covers existing "
            "datasets only; semantic or pretraining overlap is not ruled out."
        ),
    }


def build() -> dict:
    generated = build_generated()
    audit = _audit(generated)
    base = load_records(BASE)
    validate_records(base, require_reviewed=True)
    combined = base + generated
    validate_records(combined, require_reviewed=True)
    if len(base) != 748 or len(combined) != 856 or combined[:748] != base:
        raise ValueError("The selected v0.2-D base must remain unchanged")
    _write_jsonl(ADDITION, generated)
    _write_jsonl(COMBINED, combined)
    chatml = export(COMBINED, CHATML, output_contract="v0.2")
    manifest = {
        "dataset_id": "judgment-pilot-v0.2-g",
        "generation_version": VERSION,
        "validated_at": VALIDATED_AT,
        "output_contract": "judgment-v0.2",
        "source_dataset": str(BASE.relative_to(ROOT)),
        "source_dataset_sha256": _sha256(BASE),
        "augmentation_path": str(ADDITION.relative_to(ROOT)),
        "augmentation_sha256": _sha256(ADDITION),
        "combined_path": str(COMBINED.relative_to(ROOT)),
        "combined_sha256": _sha256(COMBINED),
        "augmentation_summary": summary(generated),
        "combined_summary": summary(combined),
        "generated_validation": {
            "records": len(generated),
            "human_reviewed": False,
            "expert_reviewed": False,
            "operational_text_used": False,
            "paired_cases": 12,
            "noncorrection_cases": 84,
            "contamination_audit": audit,
        },
        "chatml": chatml,
        "holdout_policy": (
            "All holdouts and rejected augmentations are used only for overlap "
            "audit; labels and model predictions are not generation inputs."
        ),
        "shadow_policy": (
            "No operational shadow text or raw model response is present in "
            "the augmentation."
        ),
    }
    MANIFEST.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return manifest


if __name__ == "__main__":
    print(json.dumps(build(), ensure_ascii=False, indent=2))
