"""Fail-closed lifecycle manager for no-sudo judgment staging services."""

from __future__ import annotations

import argparse
import json
import os
import stat
import subprocess
import tempfile
import time
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from scripts.check_judgment_staging import (
    DEFAULT_API_BASE,
    DEFAULT_JUDGMENT_ENDPOINT,
    check_live_services,
)


MODEL_SERVICE = "judgment-vllm.service"
API_SERVICE = "stt-api-judgment-staging.service"
MODEL_HEALTH = "http://127.0.0.1:1234/health"
MODEL_LIST = "http://127.0.0.1:1234/v1/models"
API_READINESS = "http://127.0.0.1:8001/ready/judgment"
MODEL_ALIAS = "judgment-v02d"
Runner = Callable[..., subprocess.CompletedProcess[str]]
Opener = Callable[..., Any]


@dataclass(frozen=True)
class UserStagingPaths:
    environment: Path
    database: Path


def default_paths() -> UserStagingPaths:
    home = Path.home()
    config = Path(os.environ.get("XDG_CONFIG_HOME", home / ".config"))
    state = Path(os.environ.get("XDG_STATE_HOME", home / ".local/state"))
    return UserStagingPaths(
        environment=config / "stt-api/judgment-staging.env",
        database=state / "stt-api-judgment-staging/stt_data.db",
    )


def _safe_environment_stat(path: Path) -> os.stat_result:
    metadata = path.lstat()
    if stat.S_ISLNK(metadata.st_mode) or not stat.S_ISREG(metadata.st_mode):
        raise RuntimeError("private environment must be a regular non-symlink file")
    if metadata.st_uid != os.getuid():
        raise RuntimeError("private environment must be owned by the current user")
    if stat.S_IMODE(metadata.st_mode) & 0o077:
        raise RuntimeError("private environment permissions must not allow group/other access")
    return metadata


def environment_flag(path: Path, name: str) -> bool:
    _safe_environment_stat(path)
    prefix = f"{name}="
    values = [
        line.split("=", 1)[1].strip().lower()
        for line in path.read_text().splitlines()
        if line.startswith(prefix)
    ]
    if len(values) != 1 or values[0] not in {"true", "false"}:
        raise RuntimeError(f"private environment needs exactly one true/false {name}")
    return values[0] == "true"


def environment_enabled(path: Path) -> bool:
    return environment_flag(path, "JUDGMENT_ENABLED")


def set_environment_flag(path: Path, name: str, enabled: bool) -> None:
    metadata = _safe_environment_stat(path)
    lines = path.read_text().splitlines(keepends=True)
    prefix = f"{name}="
    indices = [i for i, line in enumerate(lines) if line.startswith(prefix)]
    if len(indices) != 1:
        raise RuntimeError(f"private environment needs exactly one {name}")
    current = lines[indices[0]].split("=", 1)[1].strip().lower()
    if current not in {"true", "false"}:
        raise RuntimeError(f"{name} must be true or false")
    newline = "\n" if lines[indices[0]].endswith("\n") else ""
    lines[indices[0]] = f"{name}={'true' if enabled else 'false'}{newline}"
    temporary_name: str | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=path.parent, prefix=f".{path.name}.", delete=False
        ) as handle:
            temporary_name = handle.name
            handle.writelines(lines)
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temporary_name, stat.S_IMODE(metadata.st_mode))
        os.replace(temporary_name, path)
        temporary_name = None
    finally:
        if temporary_name is not None:
            Path(temporary_name).unlink(missing_ok=True)


def set_environment_enabled(path: Path, enabled: bool) -> None:
    set_environment_flag(path, "JUDGMENT_ENABLED", enabled)


def _run(runner: Runner, *arguments: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return runner(
        ["systemctl", "--user", *arguments],
        check=check,
        capture_output=True,
        text=True,
    )


def service_state(service: str, runner: Runner = subprocess.run) -> str:
    result = _run(runner, "is-active", service, check=False)
    return result.stdout.strip() or "unknown"


def _request_json(url: str, opener: Opener, timeout: float = 3.0) -> Any:
    with opener(url, timeout=timeout) as response:
        body = response.read()
    return json.loads(body.decode("utf-8")) if body else None


def _wait_until(check: Callable[[], bool], timeout: float, interval: float = 1.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            if check():
                return
        except Exception:
            pass
        time.sleep(interval)
    raise TimeoutError("staging service did not become ready before timeout")


def model_ready(opener: Opener = urllib.request.urlopen) -> bool:
    _request_json(MODEL_HEALTH, opener)
    payload = _request_json(MODEL_LIST, opener)
    models = payload.get("data", []) if isinstance(payload, dict) else []
    return MODEL_ALIAS in {
        item.get("id") for item in models if isinstance(item, dict)
    }


def api_ready(opener: Opener = urllib.request.urlopen) -> bool:
    payload = _request_json(API_READINESS, opener)
    return isinstance(payload, dict) and payload.get("ready") is True


def status(paths: UserStagingPaths, runner: Runner = subprocess.run) -> dict[str, Any]:
    return {
        "schema_version": "judgment-user-staging-manager-v0.1",
        "environment_enabled": environment_enabled(paths.environment),
        "shadow_enabled": environment_flag(paths.environment, "JUDGMENT_SHADOW_ENABLED"),
        "database_present": paths.database.is_file(),
        "model_service": service_state(MODEL_SERVICE, runner),
        "api_service": service_state(API_SERVICE, runner),
        "contains_request_content": False,
    }


def stop(paths: UserStagingPaths, runner: Runner = subprocess.run) -> dict[str, Any]:
    errors: list[str] = []
    for service in (API_SERVICE, MODEL_SERVICE):
        try:
            _run(runner, "stop", service)
        except Exception:
            errors.append(f"failed_to_stop:{service}")
    set_environment_flag(paths.environment, "JUDGMENT_SHADOW_ENABLED", False)
    set_environment_enabled(paths.environment, False)
    result = status(paths, runner)
    result["stop_errors"] = errors
    if errors:
        raise RuntimeError(",".join(errors))
    return result


def start(
    paths: UserStagingPaths,
    *,
    timeout: float = 180.0,
    enable_shadow: bool = False,
    runner: Runner = subprocess.run,
    opener: Opener = urllib.request.urlopen,
) -> dict[str, Any]:
    if timeout <= 0:
        raise ValueError("timeout must be positive")
    if not paths.database.is_file():
        raise FileNotFoundError(f"staging database not found: {paths.database}")
    if service_state(API_SERVICE, runner) == "active" or service_state(MODEL_SERVICE, runner) == "active":
        raise RuntimeError("staging services must be inactive before managed start")
    set_environment_enabled(paths.environment, True)
    set_environment_flag(paths.environment, "JUDGMENT_SHADOW_ENABLED", enable_shadow)
    try:
        _run(runner, "daemon-reload")
        _run(runner, "start", MODEL_SERVICE)
        _wait_until(lambda: model_ready(opener), timeout)
        _run(runner, "start", API_SERVICE)
        _wait_until(lambda: api_ready(opener), min(timeout, 60.0))
        live = check_live_services(
            api_base=DEFAULT_API_BASE,
            judgment_endpoint=DEFAULT_JUDGMENT_ENDPOINT,
            model_name=MODEL_ALIAS,
            opener=opener,
        )
        if not live["passed"]:
            raise RuntimeError("live staging preflight failed")
        result = status(paths, runner)
        result["live_preflight_passed"] = True
        return result
    except BaseException:
        for service in (API_SERVICE, MODEL_SERVICE):
            _run(runner, "stop", service, check=False)
        set_environment_flag(paths.environment, "JUDGMENT_SHADOW_ENABLED", False)
        set_environment_enabled(paths.environment, False)
        raise


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("start", "status", "stop"))
    parser.add_argument("--timeout", type=float, default=180.0)
    parser.add_argument(
        "--shadow", action="store_true",
        help="enable response-independent /analyze shadow calls for this start",
    )
    args = parser.parse_args()
    paths = default_paths()
    if args.command == "start":
        result = start(paths, timeout=args.timeout, enable_shadow=args.shadow)
    elif args.command == "stop":
        result = stop(paths)
    else:
        result = status(paths)
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
