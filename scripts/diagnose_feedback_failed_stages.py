"""Re-run terminal feedback failures once and emit content-free stage counts.

The isolated shadow database is opened read-only. Text and raw model output are
never written to the report, and the source database hash is checked unchanged.
This is operational diagnosis, not a quality evaluation or model-selection run.
"""

from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import sys

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import models
from analyzer.feedback_service import FeedbackServiceError, judgment_input, run_feedback


SCHEMA_VERSION = "feedback-failed-stage-diagnostic-v0.1"


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def run(database: Path) -> dict[str, object]:
    database = database.resolve()
    if not database.is_file():
        raise FileNotFoundError(database)
    try:
        database.relative_to(ROOT)
    except ValueError:
        pass
    else:
        raise ValueError("content-bearing database must stay outside the repository")

    before = file_sha256(database)
    engine = create_engine(
        f"sqlite:///file:{database}?mode=ro&uri=true",
        connect_args={"check_same_thread": False},
    )
    SessionLocal = sessionmaker(bind=engine)
    counts: Counter[str] = Counter()
    with SessionLocal() as db:
        jobs = (
            db.query(models.FeedbackAuditJob)
            .filter(models.FeedbackAuditJob.status == "failed")
            .order_by(models.FeedbackAuditJob.id)
            .all()
        )
        for job in jobs:
            judgment = db.get(models.JudgmentResult, job.judgment_id)
            utterance = db.get(models.Utterance, judgment.utterance_id) if judgment else None
            if judgment is None or utterance is None:
                counts["missing_input"] += 1
                continue
            try:
                run_feedback(
                    utterance.stt_text,
                    context=judgment.context,
                    learner_level=judgment.learner_level,
                    judgment=judgment_input(judgment),
                    model_name=job.feedback_model,
                    contract_version=job.contract_version,
                )
            except FeedbackServiceError as exc:
                counts[exc.category] += 1
            else:
                counts["diagnostic_retry_succeeded"] += 1
    engine.dispose()
    after = file_sha256(database)
    if before != after:
        raise RuntimeError("read-only diagnostic changed the source database")
    return {
        "schema_version": SCHEMA_VERSION,
        "operational_diagnostic_only": True,
        "quality_claim_allowed": False,
        "failed_job_count": sum(counts.values()),
        "outcome_counts": dict(sorted(counts.items())),
        "database_sha256_before": before,
        "database_sha256_after": after,
        "database_unchanged": True,
        "content_included": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--database", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = run(args.database)
    rendered = json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.write_text(rendered, encoding="utf-8")
    sys.stdout.write(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
