"""Read-only preflight checks for the feature-flagged judgment staging stack."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import sqlite3
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Callable

from analyzer.judgment_service import DEFAULT_ADAPTER, DEFAULT_MODEL

DEFAULT_API_BASE = "http://127.0.0.1:8001"
DEFAULT_JUDGMENT_ENDPOINT = "http://127.0.0.1:1234/v1/chat/completions"
Opener = Callable[..., Any]


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def check_configuration(environment: dict[str, str]) -> dict[str, Any]:
    enabled = environment.get("JUDGMENT_ENABLED", "false").strip().lower()
    endpoint = environment.get("JUDGMENT_ENDPOINT", DEFAULT_JUDGMENT_ENDPOINT)
    model = environment.get("JUDGMENT_MODEL", DEFAULT_MODEL)
    adapter = environment.get("JUDGMENT_ADAPTER", DEFAULT_ADAPTER)
    timeout_raw = environment.get("JUDGMENT_TIMEOUT_SECONDS", "120")
    shadow_raw = environment.get("JUDGMENT_SHADOW_ENABLED", "false").strip().lower()
    shadow_queue_raw = environment.get("JUDGMENT_SHADOW_QUEUE_MAX_SIZE", "64")
    shadow_ttl_raw = environment.get("JUDGMENT_SHADOW_ITEM_TTL_SECONDS", "30")
    shadow_admission_rps_raw = environment.get("JUDGMENT_SHADOW_ADMISSION_RPS", "1")
    shadow_admission_burst_raw = environment.get("JUDGMENT_SHADOW_ADMISSION_BURST", "1")
    errors = []
    if enabled not in {"1", "true", "yes", "on"}:
        errors.append("JUDGMENT_ENABLED is not enabled for staging")
    if endpoint != DEFAULT_JUDGMENT_ENDPOINT:
        errors.append(f"JUDGMENT_ENDPOINT must be {DEFAULT_JUDGMENT_ENDPOINT}")
    if model != DEFAULT_MODEL:
        errors.append(f"JUDGMENT_MODEL must be {DEFAULT_MODEL}")
    if adapter != DEFAULT_ADAPTER:
        errors.append(f"JUDGMENT_ADAPTER must be {DEFAULT_ADAPTER}")
    if shadow_raw not in {"1", "true", "yes", "on", "0", "false", "no", "off"}:
        errors.append("JUDGMENT_SHADOW_ENABLED must be a boolean value")
    try:
        timeout = float(timeout_raw)
        if timeout <= 0:
            raise ValueError
    except ValueError:
        errors.append("JUDGMENT_TIMEOUT_SECONDS must be positive")
        timeout = None
    try:
        shadow_queue_size = int(shadow_queue_raw)
        if shadow_queue_size <= 0:
            raise ValueError
    except ValueError:
        errors.append("JUDGMENT_SHADOW_QUEUE_MAX_SIZE must be a positive integer")
        shadow_queue_size = None
    try:
        shadow_ttl = float(shadow_ttl_raw)
        if not math.isfinite(shadow_ttl) or shadow_ttl <= 0:
            raise ValueError
    except ValueError:
        errors.append("JUDGMENT_SHADOW_ITEM_TTL_SECONDS must be positive")
        shadow_ttl = None
    try:
        shadow_admission_rps = float(shadow_admission_rps_raw)
        if not math.isfinite(shadow_admission_rps) or shadow_admission_rps <= 0:
            raise ValueError
    except ValueError:
        errors.append("JUDGMENT_SHADOW_ADMISSION_RPS must be positive")
        shadow_admission_rps = None
    try:
        shadow_admission_burst = int(shadow_admission_burst_raw)
        if shadow_admission_burst <= 0:
            raise ValueError
    except ValueError:
        errors.append("JUDGMENT_SHADOW_ADMISSION_BURST must be a positive integer")
        shadow_admission_burst = None
    return {
        "passed": not errors,
        "errors": errors,
        "effective": {
            "enabled": enabled in {"1", "true", "yes", "on"},
            "endpoint": endpoint,
            "model": model,
            "adapter": adapter,
            "shadow_enabled": shadow_raw in {"1", "true", "yes", "on"},
            "shadow_queue_max_size": shadow_queue_size,
            "shadow_item_ttl_seconds": shadow_ttl,
            "shadow_admission_rps": shadow_admission_rps,
            "shadow_admission_burst": shadow_admission_burst,
            "timeout_seconds": timeout,
        },
    }


def database_snapshot(database_path: Path) -> dict[str, Any]:
    resolved = database_path.resolve()
    if not resolved.is_file():
        raise FileNotFoundError(f"Database not found: {resolved}")
    connection = sqlite3.connect(f"file:{resolved}?mode=ro", uri=True)
    try:
        utterances = connection.execute("SELECT COUNT(*) FROM utterances").fetchone()[0]
        judgments = connection.execute(
            "SELECT COUNT(*) FROM judgment_results"
        ).fetchone()[0]
    finally:
        connection.close()
    return {
        "path": str(resolved),
        "sha256": sha256_file(resolved),
        "utterances": utterances,
        "judgment_results": judgments,
        "read_only": True,
    }


def _request_json(url: str, opener: Opener, timeout: float = 5.0) -> Any:
    request = urllib.request.Request(url, method="GET")
    with opener(request, timeout=timeout) as response:
        body = response.read()
    if not body:
        return None
    return json.loads(body.decode("utf-8"))


def check_live_services(
    *,
    api_base: str,
    judgment_endpoint: str,
    model_name: str,
    opener: Opener = urllib.request.urlopen,
) -> dict[str, Any]:
    api_base = api_base.rstrip("/")
    endpoint = urllib.parse.urlsplit(judgment_endpoint)
    model_base = urllib.parse.urlunsplit(
        (endpoint.scheme, endpoint.netloc, "", "", "")
    ).rstrip("/")
    checks = {}
    errors = []
    urls = {
        "model_health": f"{model_base}/health",
        "model_list": f"{model_base}/v1/models",
        "api_health": f"{api_base}/health",
        "api_readiness": f"{api_base}/ready/judgment",
        "api_openapi": f"{api_base}/openapi.json",
    }
    payloads = {}
    for name, url in urls.items():
        try:
            payloads[name] = _request_json(url, opener)
            checks[name] = True
        except Exception as exc:
            checks[name] = False
            errors.append(f"{name}: {exc}")
    readiness = payloads.get("api_readiness")
    readiness_ok = isinstance(readiness, dict) and readiness.get("ready") is True
    checks["api_readiness_state"] = readiness_ok
    if not readiness_ok:
        errors.append("judgment API is not ready")
    models = payloads.get("model_list")
    model_ids = []
    if isinstance(models, dict) and isinstance(models.get("data"), list):
        model_ids = [item.get("id") for item in models["data"] if isinstance(item, dict)]
    alias_present = model_name in model_ids
    checks["model_alias"] = alias_present
    if not alias_present:
        errors.append(f"model alias missing: {model_name}")
    openapi = payloads.get("api_openapi")
    paths = openapi.get("paths", {}) if isinstance(openapi, dict) else {}
    required = {
        "/health/judgment",
        "/ready/judgment",
        "/utterances/{utterance_id}/judgment",
        "/utterances/{utterance_id}/judgments",
    }
    judgment_paths_present = required.issubset(paths)
    checks["judgment_openapi_paths"] = judgment_paths_present
    if not judgment_paths_present:
        errors.append("judgment API paths are missing from OpenAPI")
    return {
        "passed": not errors,
        "checks": checks,
        "errors": errors,
        "model_ids": model_ids,
        "required_judgment_paths": sorted(required),
    }


def run_preflight(
    *,
    database_path: Path,
    api_base: str,
    environment: dict[str, str],
    skip_live: bool = False,
    opener: Opener = urllib.request.urlopen,
) -> dict[str, Any]:
    configuration = check_configuration(environment)
    database = database_snapshot(database_path)
    live = None
    if not skip_live and configuration["passed"]:
        live = check_live_services(
            api_base=api_base,
            judgment_endpoint=configuration["effective"]["endpoint"],
            model_name=configuration["effective"]["model"],
            opener=opener,
        )
    passed = configuration["passed"] and (skip_live or bool(live and live["passed"]))
    return {
        "schema_version": "judgment-staging-preflight-v0.1",
        "passed": passed,
        "configuration": configuration,
        "database": database,
        "live_services": live,
        "mutations_performed": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", type=Path, default=Path("stt_data.db"))
    parser.add_argument("--api-base", default=DEFAULT_API_BASE)
    parser.add_argument("--skip-live", action="store_true")
    args = parser.parse_args()
    result = run_preflight(
        database_path=args.database,
        api_base=args.api_base,
        environment=dict(os.environ),
        skip_live=args.skip_live,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if not result["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
