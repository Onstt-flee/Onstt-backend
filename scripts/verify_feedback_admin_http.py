"""HTTP/Swagger smoke test for feedback-admin projections on an isolated DB copy."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import secrets
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import time
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parents[1]
FORBIDDEN_LIST_KEYS = {
    "text", "stt_text", "context", "corrected_text", "reason_ko",
    "review_reason_ko", "recommended_judgment", "recommended_edits",
}
ADMIN_PATHS = {
    "/health/feedback",
    "/ready/feedback",
    "/admin/feedback/audits",
    "/admin/feedback/audits/{judgment_id}",
    "/admin/feedback/audits/{judgment_id}/retry",
    "/admin/feedback/issues",
}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def http_json(
    base_url: str,
    path: str,
    *,
    token: str | None = None,
    method: str = "GET",
    parse_json: bool = True,
) -> tuple[int, Any]:
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    request = Request(base_url + path, headers=headers, method=method)
    try:
        with urlopen(request, timeout=5) as response:
            body = response.read()
            return response.status, json.loads(body) if body and parse_json else body.decode()
    except HTTPError as exc:
        body = exc.read()
        return exc.code, json.loads(body) if body else None


def wait_until_ready(base_url: str, process: subprocess.Popen[bytes]) -> None:
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError(f"API process exited with code {process.returncode}")
        try:
            status, _ = http_json(base_url, "/health")
            if status == 200:
                return
        except (URLError, TimeoutError, json.JSONDecodeError):
            pass
        time.sleep(0.1)
    raise RuntimeError("API did not become ready within 30 seconds")


def start_api(database: Path, port: int, token: str, *, enabled: bool) -> subprocess.Popen[bytes]:
    environment = os.environ.copy()
    environment.update({
        "STT_DATABASE_URL": "sqlite:///" + str(database),
        "FEEDBACK_AUDIT_ENABLED": "true" if enabled else "false",
        "FEEDBACK_ENDPOINT": "http://127.0.0.1:1235/v1/chat/completions",
        "FEEDBACK_MODEL": "feedback-qwen3-8b-v03",
        "FEEDBACK_ADAPTER": "feedback-verifier-v0.3",
        "FEEDBACK_MODEL_SHA256": "3bcbc80d1559dacf60a84c708a8ab4c51ee4bd33532acf2ab134394aa2dcd1ad",
        "FEEDBACK_ADMIN_TOKEN": token,
        "JUDGMENT_ENABLED": "false",
        "JUDGMENT_SHADOW_ENABLED": "false",
        "EDGE_MODE": "false",
        "EDGE_SYNC_ENABLED": "false",
    })
    process = subprocess.Popen(
        [
            sys.executable, "-m", "uvicorn", "main:app",
            "--host", "127.0.0.1", "--port", str(port), "--log-level", "warning",
        ],
        cwd=ROOT,
        env=environment,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        wait_until_ready(f"http://127.0.0.1:{port}", process)
    except Exception:
        stop_api(process)
        raise
    return process


def stop_api(process: subprocess.Popen[bytes] | None) -> None:
    if process is None or process.poll() is not None:
        return
    process.terminate()
    try:
        process.wait(timeout=10)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=10)


def source_text_for_judgment(database: Path, judgment_id: int) -> str:
    connection = sqlite3.connect(database)
    try:
        row = connection.execute(
            """
            SELECT utterances.stt_text
            FROM judgment_results
            JOIN utterances ON utterances.id = judgment_results.utterance_id
            WHERE judgment_results.id = ?
            """,
            (judgment_id,),
        ).fetchone()
    finally:
        connection.close()
    if row is None:
        raise ValueError("detail judgment is missing its source utterance")
    return row[0]


def run(database: Path, *, port: int) -> dict[str, Any]:
    database = database.resolve()
    source_before = sha256_file(database)
    token = secrets.token_urlsafe(32)
    enabled_process: subprocess.Popen[bytes] | None = None
    disabled_process: subprocess.Popen[bytes] | None = None

    with tempfile.TemporaryDirectory(prefix="feedback-admin-http-") as directory:
        copy_path = Path(directory) / "shadow.sqlite3"
        shutil.copy2(database, copy_path)
        copy_before = sha256_file(copy_path)
        try:
            enabled_process = start_api(copy_path, port, token, enabled=True)
            base_url = f"http://127.0.0.1:{port}"

            docs_status, _ = http_json(base_url, "/docs", parse_json=False)
            openapi_status, openapi = http_json(base_url, "/openapi.json")
            unauthenticated_status, _ = http_json(base_url, "/admin/feedback/audits")
            health_status, health = http_json(base_url, "/health/feedback", token=token)
            list_status, audits = http_json(
                base_url, "/admin/feedback/audits?limit=500", token=token
            )
            issues_status, issues = http_json(base_url, "/admin/feedback/issues", token=token)
            readiness_status, readiness = http_json(base_url, "/ready/feedback", token=token)

            if not audits:
                raise ValueError("authenticated audit list is empty")
            judgment_id = audits[0]["judgment_id"]
            detail_status, detail = http_json(
                base_url, f"/admin/feedback/audits/{judgment_id}", token=token
            )
            retry_status, _ = http_json(
                base_url, f"/admin/feedback/audits/{judgment_id}/retry",
                token=token, method="POST",
            )
            source_text = source_text_for_judgment(copy_path, judgment_id)
            stop_api(enabled_process)
            enabled_process = None

            disabled_process = start_api(copy_path, port + 1, token, enabled=False)
            disabled_status, _ = http_json(
                f"http://127.0.0.1:{port + 1}", "/health/feedback", token=token
            )
        finally:
            stop_api(enabled_process)
            stop_api(disabled_process)

        copy_after = sha256_file(copy_path)

    source_after = sha256_file(database)
    leaked_keys = sorted({
        key for row in audits for key in row if key in FORBIDDEN_LIST_KEYS
    })
    issue_status_counts: dict[str, int] = {}
    issue_kind_counts: dict[str, int] = {}
    for issue in issues:
        issue_status_counts[issue["status"]] = issue_status_counts.get(issue["status"], 0) + 1
        issue_kind_counts[issue["kind"]] = (
            issue_kind_counts.get(issue["kind"], 0) + issue["count"]
        )

    checks = {
        "docs_200": docs_status == 200,
        "openapi_200": openapi_status == 200,
        "admin_paths_present": ADMIN_PATHS.issubset(openapi["paths"]),
        "unauthenticated_is_401": unauthenticated_status == 401,
        "health_200": health_status == 200,
        "audit_list_200": list_status == 200,
        "issues_200": issues_status == 200,
        "detail_200": detail_status == 200,
        "succeeded_retry_is_409": retry_status == 409,
        "stopped_model_readiness_is_503": readiness_status == 503,
        "disabled_feature_is_503": disabled_status == 503,
        "audit_list_content_free": not leaked_keys,
        "detail_excludes_source_text": source_text not in json.dumps(
            detail, ensure_ascii=False
        ),
        "health_content_free": health.get("contains_request_content") is False,
        "source_database_unchanged": source_before == source_after,
        "temporary_copy_unchanged": copy_before == copy_after,
    }
    if not all(checks.values()):
        failed = sorted(name for name, passed in checks.items() if not passed)
        raise ValueError(f"HTTP smoke checks failed: {failed}")

    return {
        "schema_version": "feedback-admin-http-shadow-v0.2",
        "scope": "actual_stored_stt_operational_shadow_only",
        "quality_claim_allowed": False,
        "database_sha256_before": source_before,
        "database_sha256_after": source_after,
        "database_unchanged": True,
        "checks": checks,
        "http": {
            "docs_status": docs_status,
            "openapi_status": openapi_status,
            "unauthenticated_audit_list_status": unauthenticated_status,
            "authenticated_health_status": health_status,
            "authenticated_audit_list_status": list_status,
            "authenticated_issue_list_status": issues_status,
            "authenticated_detail_status": detail_status,
            "succeeded_job_retry_status": retry_status,
            "model_stopped_readiness_status": readiness_status,
            "model_stopped_readiness_reason": readiness.get("reason"),
            "disabled_health_status": disabled_status,
        },
        "projections": {
            "audit_list_count": len(audits),
            "audit_list_contains_content_keys": False,
            "health_contains_request_content": False,
            "issue_group_count": len(issues),
            "issue_status_counts": dict(sorted(issue_status_counts.items())),
            "issue_kind_member_counts": dict(sorted(issue_kind_counts.items())),
            "detail_contains_source_text": False,
        },
        "limitations": (
            "Actual stored-STT operational wiring and access-control evidence only; "
            "not a language-quality or production-approval claim."
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--port", type=int, default=18001)
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()

    if not 1024 <= args.port <= 65534:
        print("port must leave room for the disabled-server port", file=sys.stderr)
        return 1
    if args.output.exists() and not args.overwrite:
        print(f"refusing to overwrite {args.output}", file=sys.stderr)
        return 1
    try:
        result = run(args.database, port=args.port)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        temporary = args.output.with_suffix(args.output.suffix + ".tmp")
        temporary.write_text(
            json.dumps(result, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        temporary.replace(args.output)
    except (OSError, RuntimeError, ValueError, URLError, json.JSONDecodeError) as exc:
        print(f"verification failed: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
