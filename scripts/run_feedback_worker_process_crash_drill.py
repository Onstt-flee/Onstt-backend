"""Kill a real feedback worker mid-request and verify lease recovery."""

from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import threading
import time
from typing import Any

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import models


ROOT = Path(__file__).resolve().parents[1]


def canonical(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def judgment_snapshot(db: Any) -> str:
    rows = db.query(models.JudgmentResult).order_by(models.JudgmentResult.id).all()
    values = [{
        "id": row.id, "utterance_id": row.utterance_id,
        "decision": row.decision, "corrected_text": row.corrected_text,
        "edits": row.edits, "error_types": row.error_types,
        "reason_ko": row.reason_ko,
        "classification_review_required": row.classification_review_required,
        "strategy": row.strategy, "model_name": row.model_name,
        "adapter_name": row.adapter_name, "selection_reason": row.selection_reason,
        "contract_version": row.contract_version, "latency_ms": row.latency_ms,
        "context": row.context, "learner_level": row.learner_level,
    } for row in rows]
    return hashlib.sha256(canonical(values).encode("utf-8")).hexdigest()


class StubState:
    def __init__(self, first_delay: float):
        self.first_delay = first_delay
        self.request_count = 0
        self.first_started = threading.Event()
        self.lock = threading.Lock()


def handler_factory(state: StubState):
    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):  # noqa: N802
            length = int(self.headers.get("Content-Length", "0"))
            self.rfile.read(length)
            with state.lock:
                state.request_count += 1
                request_number = state.request_count
            if request_number == 1:
                state.first_started.set()
                time.sleep(state.first_delay)
            content = canonical({
                "verdict": "agree", "issue_codes": [],
                "recommended_judgment": None,
                "review_reason_ko": "프로세스 복구 훈련 응답",
            })
            payload = canonical({
                "id": "stub", "object": "chat.completion",
                "choices": [{"index": 0, "message": {
                    "role": "assistant", "content": content,
                }, "finish_reason": "stop"}],
            }).encode("utf-8")
            try:
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers(); self.wfile.write(payload)
            except (BrokenPipeError, ConnectionResetError):
                pass

        def log_message(self, format, *args):
            return

    return Handler


def wait_for(predicate, timeout: float, description: str):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        value = predicate()
        if value:
            return value
        time.sleep(0.05)
    raise TimeoutError(f"timed out waiting for {description}")


def worker_env(database: Path, endpoint: str) -> dict[str, str]:
    env = os.environ.copy()
    env.update({
        "STT_DATABASE_URL": f"sqlite:///{database}",
        "FEEDBACK_AUDIT_ENABLED": "true",
        "FEEDBACK_ENDPOINT": endpoint,
        "FEEDBACK_MODEL": "process-crash-drill",
        "FEEDBACK_ADAPTER": "process-crash-drill",
        "FEEDBACK_MODEL_SHA256": "f" * 64,
        "FEEDBACK_ADMIN_TOKEN": "process-crash-drill-admin-token-123456",
        "FEEDBACK_TIMEOUT_SECONDS": "120",
    })
    return env


def start_worker(database: Path, endpoint: str) -> subprocess.Popen:
    return subprocess.Popen(
        [sys.executable, str(ROOT / "scripts/run_feedback_worker.py")],
        cwd=ROOT, env=worker_env(database, endpoint),
        stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL, start_new_session=True,
    )


def run(source: Path, database: Path, *, first_delay: float = 10.0) -> dict[str, Any]:
    source = source.resolve(); database = database.resolve()
    source_hash_before = sha256_file(source)
    if database.exists():
        database.unlink()
    database.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, database)

    engine = create_engine(f"sqlite:///{database}", connect_args={"check_same_thread": False})
    SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    with SessionLocal() as db:
        judgment_id = db.query(models.JudgmentResult.id).order_by(models.JudgmentResult.id).first()[0]
        before_snapshot = judgment_snapshot(db)
        baseline_audits = db.query(models.FeedbackAudit).count()
        job = models.FeedbackAuditJob(
            judgment_id=judgment_id, feedback_model="process-crash-drill",
            feedback_adapter="process-crash-drill", feedback_model_hash="f" * 64,
            contract_version="feedback-v0.1", status="pending", attempts=0,
            next_attempt_at=datetime.now(timezone.utc) - timedelta(seconds=1),
        )
        db.add(job); db.commit(); db.refresh(job); job_id = job.id

    state = StubState(first_delay)
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler_factory(state))
    server.daemon_threads = True
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    endpoint = f"http://127.0.0.1:{server.server_port}/v1/chat/completions"
    first_worker = second_worker = None
    try:
        first_worker = start_worker(database, endpoint)
        if not state.first_started.wait(timeout=15):
            raise TimeoutError("first worker did not start the feedback request")
        first_worker.kill()
        first_exit_code = first_worker.wait(timeout=10)

        def running_after_crash():
            with SessionLocal() as db:
                value = db.get(models.FeedbackAuditJob, job_id)
                return value if value.status == "running" and value.attempts == 1 else None

        crashed_job = wait_for(running_after_crash, 5, "crashed running lease")
        lease_was_future = crashed_job.lease_expires_at is not None
        with SessionLocal() as db:
            value = db.get(models.FeedbackAuditJob, job_id)
            value.lease_expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
            value.next_attempt_at = datetime.now(timezone.utc) - timedelta(seconds=1)
            db.commit()

        second_worker = start_worker(database, endpoint)

        def succeeded_after_restart():
            with SessionLocal() as db:
                value = db.get(models.FeedbackAuditJob, job_id)
                return value if value.status == "succeeded" else None

        recovered_job = wait_for(succeeded_after_restart, 15, "restarted worker recovery")
        second_worker.terminate()
        second_exit_code = second_worker.wait(timeout=10)

        with SessionLocal() as db:
            after_snapshot = judgment_snapshot(db)
            audits = db.query(models.FeedbackAudit).filter_by(
                judgment_id=judgment_id, feedback_model_hash="f" * 64,
                contract_version="feedback-v0.1",
            ).all()
            final_audits = db.query(models.FeedbackAudit).count()
        result = {
            "schema_version": "feedback-worker-process-crash-drill-v0.1",
            "scope": "isolated_synthetic_database_copy",
            "quality_claim_allowed": False,
            "source_database_sha256_before": source_hash_before,
            "source_database_sha256_after": sha256_file(source),
            "source_database_unchanged": source_hash_before == sha256_file(source),
            "working_database_sha256": None,
            "first_worker": {
                "terminated_by_signal": first_exit_code < 0,
                "exit_code": first_exit_code,
                "job_status_after_crash": "running",
                "attempts_after_crash": 1,
                "lease_present_after_crash": lease_was_future,
            },
            "restarted_worker": {
                "exit_code": second_exit_code,
                "final_job_status": recovered_job.status,
                "final_attempts": recovered_job.attempts,
            },
            "stub_request_count": state.request_count,
            "recovery_audit_count": len(audits),
            "duplicate_recovery_audit_count": len(audits) - len({a.id for a in audits}),
            "audit_count_delta": final_audits - baseline_audits,
            "judgments_unchanged": before_snapshot == after_snapshot,
            "judgment_snapshot_before_sha256": before_snapshot,
            "judgment_snapshot_after_sha256": after_snapshot,
            "contains_request_content": False,
        }
    finally:
        for process in (first_worker, second_worker):
            if process is not None and process.poll() is None:
                process.kill(); process.wait(timeout=10)
        server.shutdown(); server.server_close(); thread.join(timeout=5)
        engine.dispose()
    result["working_database_sha256"] = sha256_file(database)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--database", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()
    if args.output.exists() and not args.overwrite:
        print(f"refusing to overwrite {args.output}", file=sys.stderr); return 1
    try:
        result = run(args.source, args.database)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    except (OSError, TimeoutError, ValueError) as exc:
        print(f"process crash drill failed: {exc}", file=sys.stderr); return 1
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
