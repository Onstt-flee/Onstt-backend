"""Audit 200 actual GPU judgments in an isolated, content-bearing SQLite copy.

The source database is opened read-only.  The tracked summary contains only
counts, latency aggregates and hashes; text remains in the private isolated DB.
This label-free run validates operation, not Japanese-language quality.
"""

from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import statistics
import sys
from typing import Any, Callable

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import models
from analyzer.feedback_store import configuration_error, record_gpu_judgment
from analyzer.feedback_worker import process_one
from database import Base
from scripts.run_feedback_synthetic_shadow import canonical, judgment_snapshot, percentile


SAMPLE_SIZE = 200
SCHEMA_VERSION = "actual-gpu-feedback-shadow-result-v0.1"
REQUIRED_SOURCE_TABLES = {"utterances", "judgment_results", "judgment_provenance"}


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _private_path(path: Path, repository_root: Path) -> None:
    resolved = path.resolve()
    try:
        resolved.relative_to(repository_root.resolve())
    except ValueError:
        return
    raise ValueError(f"content-bearing shadow artifact must stay outside Git workspace: {resolved}")


def _open_read_only(path: Path) -> sqlite3.Connection:
    if not path.is_file():
        raise FileNotFoundError(path)
    connection = sqlite3.connect(f"file:{path.resolve()}?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    return connection


def source_counts(connection: sqlite3.Connection) -> dict[str, int]:
    tables = {
        row[0] for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        )
    }
    missing = REQUIRED_SOURCE_TABLES - tables
    if missing:
        raise ValueError(f"source database missing required tables: {sorted(missing)}")
    return {
        table: int(connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])
        for table in sorted(REQUIRED_SOURCE_TABLES)
    }


def select_rows(
    connection: sqlite3.Connection,
    *,
    after_judgment_id: int,
    judgment_model: str,
    judgment_adapter: str,
    sample_size: int = SAMPLE_SIZE,
) -> list[dict[str, Any]]:
    if after_judgment_id < 0:
        raise ValueError("after_judgment_id must be nonnegative")
    if sample_size != SAMPLE_SIZE:
        raise ValueError(f"actual shadow requires exactly {SAMPLE_SIZE} judgments")
    rows = connection.execute(
        """
        SELECT
            j.id AS source_judgment_id,
            u.stt_text,
            j.decision,
            j.corrected_text,
            j.edits,
            j.error_types,
            j.reason_ko,
            j.classification_review_required,
            j.strategy,
            j.model_name,
            j.adapter_name,
            j.selection_reason,
            j.contract_version,
            j.latency_ms,
            j.context,
            j.learner_level,
            p.model_sha256,
            p.adapter_sha256,
            p.runtime,
            p.quantization
        FROM judgment_results AS j
        JOIN utterances AS u ON u.id = j.utterance_id
        JOIN judgment_provenance AS p ON p.judgment_id = j.id
        WHERE j.id > ?
          AND p.runtime = 'gpu_bf16'
          AND j.model_name = ?
          AND j.adapter_name = ?
        ORDER BY j.id
        LIMIT ?
        """,
        (after_judgment_id, judgment_model, judgment_adapter, sample_size),
    ).fetchall()
    values = [dict(row) for row in rows]
    if len(values) != sample_size:
        raise ValueError(
            f"insufficient eligible GPU judgments: expected {sample_size}, got {len(values)}"
        )
    if len({row["source_judgment_id"] for row in values}) != sample_size:
        raise ValueError("source judgment IDs must be unique")
    for row in values:
        if not isinstance(row["stt_text"], str) or not row["stt_text"].strip():
            raise ValueError("eligible source judgment contains blank text")
        if row["learner_level"] not in {"N5", "N4"}:
            raise ValueError("eligible source judgment contains unsupported learner level")
        if row["quantization"] not in {None, "BF16"}:
            raise ValueError("gpu_bf16 judgment has inconsistent quantization")
    return values


def selection_sha256(rows: list[dict[str, Any]]) -> str:
    return hashlib.sha256(canonical(rows).encode("utf-8")).hexdigest()


def copy_to_isolated_db(rows: list[dict[str, Any]], session_factory: Callable) -> None:
    with session_factory() as db:
        shadow_session = models.Session(topic="actual-gpu-feedback-shadow-v0.1")
        db.add(shadow_session)
        db.flush()
        for row in rows:
            utterance = models.Utterance(
                session_id=shadow_session.id,
                stt_text=row["stt_text"],
                language="ja",
                stt_model="actual-shadow-private-copy",
            )
            db.add(utterance)
            db.flush()
            judgment = models.JudgmentResult(
                utterance_id=utterance.id,
                decision=row["decision"],
                corrected_text=row["corrected_text"],
                edits=row["edits"],
                error_types=row["error_types"],
                reason_ko=row["reason_ko"],
                classification_review_required=bool(row["classification_review_required"]),
                strategy=row["strategy"],
                model_name=row["model_name"],
                adapter_name=row["adapter_name"],
                selection_reason=row["selection_reason"],
                contract_version=row["contract_version"],
                latency_ms=row["latency_ms"],
                context=row["context"],
                learner_level=row["learner_level"],
            )
            db.add(judgment)
            db.flush()
            record_gpu_judgment(
                db,
                judgment,
                {
                    "model_sha256": row["model_sha256"],
                    "adapter_sha256": row["adapter_sha256"],
                },
            )
        db.commit()


def run(
    args: argparse.Namespace,
    *,
    worker_runner: Callable | None = None,
) -> dict[str, Any]:
    repository_root = ROOT
    source_path = args.source_database.resolve()
    isolated_path = args.isolated_database.resolve()
    summary_path = args.summary.resolve()
    _private_path(isolated_path, repository_root)
    if source_path == isolated_path:
        raise ValueError("source and isolated database paths must differ")
    if isolated_path.exists() and not args.overwrite:
        raise FileExistsError(f"refusing to overwrite {isolated_path}")
    if summary_path.exists() and not args.overwrite:
        raise FileExistsError(f"refusing to overwrite {summary_path}")
    if isolated_path.exists():
        isolated_path.unlink()
    if summary_path.exists():
        summary_path.unlink()
    isolated_path.parent.mkdir(parents=True, exist_ok=True)

    if configuration_error() is not None:
        raise ValueError(f"feedback configuration invalid: {configuration_error()}")
    if os.getenv("FEEDBACK_AUDIT_ENABLED", "").lower() not in {"1", "true", "yes", "on"}:
        raise ValueError("FEEDBACK_AUDIT_ENABLED must be true for the isolated shadow")

    source_file_before = file_sha256(source_path)
    with _open_read_only(source_path) as source:
        counts_before = source_counts(source)
        rows = select_rows(
            source,
            after_judgment_id=args.after_judgment_id,
            judgment_model=args.judgment_model,
            judgment_adapter=args.judgment_adapter,
        )
    selected_sha = selection_sha256(rows)

    engine = create_engine(
        f"sqlite:///{isolated_path}",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    copy_to_isolated_db(rows, SessionLocal)

    with SessionLocal() as db:
        before_hash = judgment_snapshot(db)
        queued = db.query(models.FeedbackAuditJob).count()
    if queued != SAMPLE_SIZE:
        raise ValueError(f"expected {SAMPLE_SIZE} isolated audit jobs, got {queued}")

    attempts = 0
    for _ in range(queued):
        with SessionLocal() as db:
            if worker_runner is None:
                worked = process_one(db)
            else:
                worked = process_one(db, runner=worker_runner)
        if not worked:
            break
        attempts += 1

    with SessionLocal() as db:
        after_hash = judgment_snapshot(db)
        jobs = db.query(models.FeedbackAuditJob).all()
        audits = db.query(models.FeedbackAudit).all()
        job_counts = Counter(job.status for job in jobs)
        verdict_counts = Counter(audit.verdict for audit in audits)
        issue_counts: Counter[str] = Counter()
        latencies: list[float] = []
        for audit in audits:
            issue_counts.update(json.loads(audit.issue_codes))
            if audit.latency_ms is not None:
                latencies.append(float(audit.latency_ms))
        duplicate_jobs = len(jobs) - len(
            {(job.judgment_id, job.feedback_model_hash, job.contract_version) for job in jobs}
        )
        duplicate_audits = len(audits) - len(
            {(audit.judgment_id, audit.feedback_model_hash, audit.contract_version) for audit in audits}
        )

    with _open_read_only(source_path) as source:
        counts_after = source_counts(source)
        rows_after = select_rows(
            source,
            after_judgment_id=args.after_judgment_id,
            judgment_model=args.judgment_model,
            judgment_adapter=args.judgment_adapter,
        )
    source_file_after = file_sha256(source_path)
    source_unchanged = (
        source_file_before == source_file_after
        and counts_before == counts_after
        and selected_sha == selection_sha256(rows_after)
    )
    success_rate = len(audits) / SAMPLE_SIZE
    gate_passed = (
        queued == SAMPLE_SIZE
        and attempts == SAMPLE_SIZE
        and success_rate >= 0.99
        and duplicate_jobs == 0
        and duplicate_audits == 0
        and before_hash == after_hash
        and source_unchanged
    )
    summary = {
        "schema_version": SCHEMA_VERSION,
        "scope": "actual_gpu_judgment_operational_shadow_only",
        "quality_claim_allowed": False,
        "source_runtime": "gpu_bf16",
        "selection": {
            "after_judgment_id": args.after_judgment_id,
            "selected_count": len(rows),
            "selected_max_judgment_id": rows[-1]["source_judgment_id"],
            "selection_sha256": selected_sha,
            "judgment_model": args.judgment_model,
            "judgment_adapter": args.judgment_adapter,
        },
        "private_artifacts": {
            "source_database_path": str(source_path),
            "source_database_sha256": source_file_before,
            "isolated_database_path": str(isolated_path),
            "isolated_database_sha256": file_sha256(isolated_path),
        },
        "feedback": {
            "model": os.environ["FEEDBACK_MODEL"],
            "adapter": os.environ["FEEDBACK_ADAPTER"],
            "adapter_sha256": os.environ["FEEDBACK_MODEL_SHA256"],
            "queued": queued,
            "attempted_once": attempts,
            "job_status_counts": dict(sorted(job_counts.items())),
            "audit_count": len(audits),
            "contract_success_rate": round(success_rate, 6),
            "verdict_counts": dict(sorted(verdict_counts.items())),
            "issue_counts": dict(sorted(issue_counts.items())),
            "latency_ms": {
                "p50": round(statistics.median(latencies), 3) if latencies else None,
                "p95": percentile(latencies, 0.95),
            },
        },
        "integrity": {
            "source_counts_before": counts_before,
            "source_counts_after": counts_after,
            "source_database_unchanged": source_unchanged,
            "isolated_judgments_unchanged": before_hash == after_hash,
            "duplicate_job_count": duplicate_jobs,
            "duplicate_audit_count": duplicate_audits,
            "tracked_summary_contains_no_text_or_user_ids": True,
        },
        "operational_gate": {
            "passed": gate_passed,
            "requirements": {
                "selected_and_queued": SAMPLE_SIZE,
                "contract_success_rate_min": 0.99,
                "duplicate_jobs_max": 0,
                "duplicate_audits_max": 0,
                "source_writes_max": 0,
                "judgment_mutations_max": 0,
            },
        },
        "limitations": [
            "No gold labels or audio evidence are used.",
            "Verdict and issue counts are not language-quality metrics.",
            "This result cannot enable learner-visible warnings or automatic retraining.",
        ],
    }
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-database", type=Path, required=True)
    parser.add_argument("--isolated-database", type=Path, required=True)
    parser.add_argument("--summary", type=Path, required=True)
    parser.add_argument("--after-judgment-id", type=int, required=True)
    parser.add_argument("--judgment-model", default="judgment-v02d")
    parser.add_argument(
        "--judgment-adapter",
        default="judgment-qwen3-4b-failure-focus-v0.2-d",
    )
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()
    try:
        print(json.dumps(run(args), ensure_ascii=False, indent=2))
    except (KeyError, OSError, ValueError, sqlite3.Error) as exc:
        print(f"actual feedback shadow failed: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
