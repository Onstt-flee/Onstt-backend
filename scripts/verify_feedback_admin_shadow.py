"""Verify protected feedback-admin projections against a shadow SQLite DB.

Only content-free aggregates and hashes are written. The database is opened
read-only and its byte hash must remain unchanged.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import models
from analyzer import feedback_admin


FORBIDDEN_LIST_KEYS = {
    "text", "stt_text", "context", "corrected_text", "reason_ko",
    "review_reason_ko", "recommended_judgment", "recommended_edits",
}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def verify(database: Path, *, scope: str = "synthetic_operational_shadow_only") -> dict[str, Any]:
    database = database.resolve()
    before_hash = sha256_file(database)
    url = f"sqlite:///file:{database}?mode=ro&uri=true"
    engine = create_engine(url, connect_args={"check_same_thread": False})
    SessionLocal = sessionmaker(bind=engine)
    with SessionLocal() as db:
        health = feedback_admin.monitoring_snapshot(db)
        audits = feedback_admin.list_audits(db, limit=500)
        issues = feedback_admin.issue_groups(db)
        succeeded_ids = [job.judgment_id for job in db.query(models.FeedbackAuditJob)
                         .filter_by(status="succeeded").all()]
        detail_count = sum(
            feedback_admin.audit_detail(db, judgment_id) is not None
            for judgment_id in succeeded_ids
        )
        retryable_succeeded = sum(
            feedback_admin.retry_job(db, judgment_id)
            for judgment_id in succeeded_ids
        )
    engine.dispose()
    after_hash = sha256_file(database)

    leaked_keys = sorted({key for row in audits for key in row if key in FORBIDDEN_LIST_KEYS})
    if health.get("contains_request_content") is not False:
        raise ValueError("health projection must declare content-free output")
    if leaked_keys:
        raise ValueError("audit list exposes content-bearing keys")
    if len(audits) != health["audit_count"]:
        raise ValueError("audit list and health count differ")
    if detail_count != health["audit_count"]:
        raise ValueError("not every succeeded audit has a detail record")
    if retryable_succeeded:
        raise ValueError("succeeded jobs must not be retryable")
    if before_hash != after_hash:
        raise ValueError("read-only admin verification changed the database")

    issue_counts: dict[str, int] = {}
    statuses: dict[str, int] = {}
    runtimes: dict[str, int] = {}
    kinds: dict[str, int] = {}
    failure_categories: dict[str, int] = {}
    for issue in issues:
        code = issue.get("issue_code")
        if code is not None:
            issue_counts[code] = issue_counts.get(code, 0) + issue["count"]
        statuses[issue["status"]] = statuses.get(issue["status"], 0) + 1
        runtimes[issue["runtime"]] = runtimes.get(issue["runtime"], 0) + issue["count"]
        kinds[issue["kind"]] = kinds.get(issue["kind"], 0) + issue["count"]
        category = issue.get("error_category")
        if category is not None:
            failure_categories[category] = (
                failure_categories.get(category, 0) + issue["count"]
            )

    return {
        "schema_version": "feedback-admin-shadow-verification-v0.1",
        "scope": scope,
        "quality_claim_allowed": False,
        "database_sha256_before": before_hash,
        "database_sha256_after": after_hash,
        "database_unchanged": True,
        "health": {
            "job_counts": health["job_counts"],
            "audit_count": health["audit_count"],
            "disagreement_count": health["disagreement_count"],
            "unreviewable_count": health["unreviewable_count"],
            "contains_request_content": health["contains_request_content"],
        },
        "admin_projections": {
            "list_count": len(audits),
            "list_contains_content_keys": False,
            "detail_resolvable_count": detail_count,
            "succeeded_retryable_count": retryable_succeeded,
            "issue_group_count": len(issues),
            "issue_counts": dict(sorted(issue_counts.items())),
            "issue_kind_counts": dict(sorted(kinds.items())),
            "failure_category_counts": dict(sorted(failure_categories.items())),
            "issue_status_counts": dict(sorted(statuses.items())),
            "runtime_counts": dict(sorted(runtimes.items())),
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument(
        "--scope",
        choices=("synthetic_operational_shadow_only", "actual_stored_stt_operational_shadow_only"),
        default="synthetic_operational_shadow_only",
    )
    args = parser.parse_args()
    if args.output.exists() and not args.overwrite:
        print(f"refusing to overwrite {args.output}", file=sys.stderr)
        return 1
    try:
        result = verify(args.database, scope=args.scope)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(result, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    except (OSError, ValueError) as exc:
        print(f"verification failed: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
