"""Conservative, non-mutating particle-risk signals for feedback audits.

This module is deliberately not a grammar corrector.  It marks a small set of
repeatedly observed particle patterns for secondary review and never produces a
replacement, verdict, or learner-facing feedback.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
import re
from typing import Any


GATE_VERSION = "feedback-particle-risk-v0.1"

_EXISTENCE_DE = re.compile(
    r"で(?P<subject>[^、。！？?\n]{1,24})が(?P<verb>あります|います)(?:[。！？?]|$)"
)
_DESTINATION_WO = re.compile(
    r"(?P<object>[^、。！？?\s]{1,32})を(?P<verb>行きます|行きました|行く|行った)(?:[。！？?]|$)"
)

# で is natural when an event occurs at a venue.  Surface matching cannot
# resolve every semantic case, so known occurrence nouns fail open.
_OCCURRENCE_NOUNS = (
    "イベント", "会議", "試験", "祭り", "式", "コンサート", "セール",
    "事故", "火事", "工事", "授業", "公演", "大会", "展示会", "説明会",
)

# を行く can describe movement along a route rather than a destination.
_ROUTE_ENDINGS = (
    "道", "道路", "通り", "街道", "廊下", "橋", "線路", "山道", "坂道",
    "人生", "先頭", "前", "後ろ",
)


@dataclass(frozen=True)
class ParticleRiskSignal:
    code: str
    evidence_start: int
    evidence_end: int
    observed_particle: str
    predicate: str
    action: str = "secondary_review_only"

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def detect_particle_risks(text: str) -> tuple[ParticleRiskSignal, ...]:
    """Return review-only signals without suggesting or applying a correction."""
    if not isinstance(text, str) or not text.strip():
        return ()
    signals: list[ParticleRiskSignal] = []
    for match in _EXISTENCE_DE.finditer(text):
        subject = match.group("subject")
        if any(noun in subject for noun in _OCCURRENCE_NOUNS):
            continue
        signals.append(ParticleRiskSignal(
            code="existence_location_de_risk",
            evidence_start=match.start(), evidence_end=match.end(),
            observed_particle="で", predicate=match.group("verb"),
        ))
    for match in _DESTINATION_WO.finditer(text):
        object_surface = match.group("object")
        if object_surface.endswith(_ROUTE_ENDINGS):
            continue
        signals.append(ParticleRiskSignal(
            code="destination_wo_iku_risk",
            evidence_start=match.start(), evidence_end=match.end(),
            observed_particle="を", predicate=match.group("verb"),
        ))
    return tuple(signals)


def assess_candidate(text: str, judgment: dict[str, Any]) -> dict[str, Any]:
    """Classify whether a candidate already acknowledges every detected risk.

    The returned object is internal diagnostic metadata.  It never rewrites the
    judgment and is not part of the public feedback-v0.1 model input.
    """
    signals = detect_particle_risks(text)
    if not signals:
        status = "no_signal"
    elif (
        judgment.get("decision") == "needs_correction"
        and judgment.get("corrected_text") != text
        and "particle_misuse" in judgment.get("error_types", [])
    ):
        status = "acknowledged"
    else:
        status = "review_required"
    return {
        "gate_version": GATE_VERSION,
        "status": status,
        "signals": [signal.as_dict() for signal in signals],
        "mutates_judgment": False,
    }
