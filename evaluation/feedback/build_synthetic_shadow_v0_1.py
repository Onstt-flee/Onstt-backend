"""Build 200 label-free synthetic inputs for a dual-model staging shadow run.

The strata are generation metadata only.  They are never sent to either model
and are not gold labels, so this set cannot be used to claim language quality.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
OUTPUT = ROOT / "evaluation/feedback/shadow_v0.1.inputs.jsonl"
MANIFEST = ROOT / "evaluation/feedback/shadow_v0.1.inputs.manifest.json"


def canonical(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _rows() -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []

    times = ["明日は", "来週は", "今日は", "土曜日は", "来月は"]
    destinations = ["学校", "病院", "図書館", "駅", "公園", "会社", "大学", "銀行"]
    for time in times:
        for destination in destinations:
            rows.append({
                "text": f"{time}{destination}に行きます。",
                "context": None,
                "learner_level": "N5",
                "stratum": "acceptable_like",
            })

    places = ["図書館", "食堂", "公園", "教室", "家"]
    actions = [
        ("本を読みます", "N5"),
        ("昼ご飯を食べます", "N5"),
        ("友達と話します", "N5"),
        ("日本語を勉強します", "N5"),
        ("写真を撮りました", "N4"),
        ("音楽を聞きました", "N4"),
        ("宿題をしました", "N5"),
        ("少し休みました", "N5"),
    ]
    for place in places:
        for action, level in actions:
            rows.append({
                "text": f"昨日は{place}で{action}。",
                "context": None,
                "learner_level": level,
                "stratum": "acceptable_like",
            })

    for time in times:
        for destination in destinations:
            rows.append({
                "text": f"{time}{destination}を行きます。",
                "context": None,
                "learner_level": "N5",
                "stratum": "correction_like",
            })

    malformed = [
        ("毎朝、顔を洗うます。", "N5"),
        ("昨日、本を読むました。", "N5"),
        ("ここで少し待つてください。", "N5"),
        ("駅で友達に会いてください。", "N5"),
        ("このスープは熱いかったです。", "N5"),
        ("このかばんは重いくないです。", "N5"),
        ("ここは静かなです。", "N5"),
        ("きれい部屋に住んでいます。", "N5"),
        ("安いな時計を買いました。", "N5"),
        ("今日は寒いだです。", "N5"),
    ]
    prefixes = ["", "ええと、", "先生、", "旅行では、"]
    for prefix in prefixes:
        for text, level in malformed:
            rows.append({
                "text": prefix + text,
                "context": None,
                "learner_level": level,
                "stratum": "correction_like",
            })

    incomplete = [
        "昨日、駅で友達に", "もし明日雨が降ったら", "この本を読んだのは",
        "私は昨日、病院に……", "明日は［聞き取れない］に行きます。",
        "今日は［聞き取れない］かったです。", "［雑音のみ］", "……",
        "あの、ええと……", "I went to the station yesterday.",
    ]
    for index, text in enumerate(incomplete):
        for context in (None, "일본어 회화 연습 중인 학습자 발화"):
            rows.append({
                "text": text,
                "context": context,
                "learner_level": "N5" if index % 2 == 0 else "N4",
                "stratum": "insufficient_like",
            })

    boundaries = [
        ("あのう、来週は大阪に行きます。", None),
        ("なんか飲む？", "친구에게 묻는 상황"),
        ("昨日は図書館に行きました。そして本を読んだ。", "친구와의 일상 대화"),
        ("昨日は図書館に行きました。そして本を読んだ。", "면접에서 정중하게 답하는 상황"),
        ("わたしわ大学生です。", "음성 인식 전사이며 원음은 제공되지 않음"),
        ("本お読みます。", "음성 인식 전사이며 원음은 제공되지 않음"),
        ("京都です。", "어디로 여행 가나요?"),
        ("京都です。", "무슨 과일을 좋아하나요?"),
        ("パン、もう買ったよ。", "친구와 대화"),
        ("今、何してる？", "친구와 대화"),
    ]
    for text, context in boundaries:
        for level in ("N5", "N4"):
            rows.append({
                "text": text,
                "context": context,
                "learner_level": level,
                "stratum": "boundary_like",
            })

    if len(rows) != 200:
        raise AssertionError(f"expected 200 rows, got {len(rows)}")
    return [
        {"id": f"FSS-{index:04d}", "input": {
            "text": row["text"], "context": row["context"],
            "learner_level": row["learner_level"],
        }, "stratum": row["stratum"]}
        for index, row in enumerate(rows, 1)
    ]


def build(output: Path = OUTPUT, manifest_path: Path = MANIFEST) -> dict[str, object]:
    rows = _rows()
    payload = "".join(canonical(row) + "\n" for row in rows).encode("utf-8")
    output.write_bytes(payload)
    counts: dict[str, int] = {}
    for row in rows:
        counts[str(row["stratum"])] = counts.get(str(row["stratum"]), 0) + 1
    manifest = {
        "schema_version": "synthetic-feedback-shadow-v0.1",
        "purpose": "label_free_operational_shadow_only",
        "quality_claim_allowed": False,
        "input_count": len(rows),
        "unique_id_count": len({row["id"] for row in rows}),
        "stratum_counts": counts,
        "inputs_sha256": hashlib.sha256(payload).hexdigest(),
        "model_visibility": ["text", "context", "learner_level"],
        "hidden_metadata": ["id", "stratum"],
    }
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return manifest


if __name__ == "__main__":
    print(json.dumps(build(), ensure_ascii=False, indent=2))
