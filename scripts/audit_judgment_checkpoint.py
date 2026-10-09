"""Fail-closed, content-free audit for a future judgment checkpoint commit."""

from __future__ import annotations

import argparse
import fnmatch
import hashlib
import json
import subprocess
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
MAX_CHANGED_FILE_BYTES = 10 * 1024 * 1024
EXPECTED_HASHES = {
    "stt_data.db": "ef3b42b92516c5332f2ed1dcd63ffe1a9c2ff8a53650c24a32205a0161ff09c9",
    "evaluation/judgment/holdout_v0.4.jsonl": (
        "904ca090ccd0e209f95fa68a6a3e9fd762a0009c802f7eae7670838f9558221e"
    ),
}
REQUIRED_PATHS = (
    "analyzer/judgment_service.py",
    "analyzer/judgment_monitor.py",
    "analyzer/judgment_runtime.py",
    "analyzer/judgment_shadow.py",
    "docs/JUDGMENT_STAGING_RUNBOOK.md",
    "deployment/judgment-staging/judgment-staging.env.example",
    "deployment/judgment-staging/judgment-vllm.service",
    "deployment/judgment-staging/stt-api-judgment-staging.service",
    "deployment/judgment-staging/user/judgment-vllm.service",
    "deployment/judgment-staging/user/stt-api-judgment-staging.service",
    "scripts/install_judgment_user_services.sh",
    "scripts/check_judgment_user_staging.sh",
    "scripts/manage_judgment_user_staging.py",
    "tests/test_judgment_user_staging_manager.py",
    "evaluation/judgment/holdout_v0.4.manifest.json",
    "scripts/check_judgment_staging.py",
    "scripts/run_judgment_staging_load.py",
    "tests/test_judgment_monitor.py",
    "tests/test_judgment_deployment_templates.py",
    "tests/test_judgment_runtime.py",
    "tests/test_judgment_shadow_integration.py",
    "training/judgment/STAGING_ANALYZE_SHADOW_RESULT.md",
    "training/judgment/STAGING_RUNTIME_SAFETY_RESULT.md",
    "training/judgment/STAGING_SOAK_RECOVERY_RESULT.md",
    "training/judgment/STAGING_DEPLOYMENT_TEMPLATE_RESULT.md",
    "deployment/judgment-staging/README.md",
)
EXPECTED_IGNORED_PATHS = (
    "evaluation/judgment/runs/shadow_v0.1/raw.jsonl",
    "evaluation/judgment/runs/shadow_v0.2/raw.jsonl",
    "evaluation/judgment/runs/quality_review_v0.1/review.jsonl",
    "evaluation/judgment/runs/quality_review_v0.1/mapping.jsonl",
)
PROHIBITED_PATTERNS = (
    ".env",
    "evaluation/judgment/runs/*",
    "venv/*",
    "venv.backup-*/*",
    "*.db",
    "*.sqlite3",
    "*.safetensors",
    "*.gguf",
    "*.bin",
    "*.pt",
    "*.pth",
    "*.wav",
    "*.mp3",
    "*.m4a",
)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def changed_paths(root: Path) -> list[str]:
    completed = subprocess.run(
        ["git", "status", "--porcelain=v1", "-z", "--untracked-files=all"],
        cwd=root,
        check=True,
        capture_output=True,
    )
    entries = completed.stdout.decode("utf-8", errors="strict").split("\0")
    paths: list[str] = []
    index = 0
    while index < len(entries):
        entry = entries[index]
        index += 1
        if not entry:
            continue
        status = entry[:2]
        paths.append(entry[3:])
        if "R" in status or "C" in status:
            if index >= len(entries) or not entries[index]:
                raise RuntimeError("malformed git rename/copy status")
            paths.append(entries[index])
            index += 1
    return sorted(set(paths))


def prohibited_reason(path: str) -> str | None:
    normalized = path.replace("\\", "/")
    for pattern in PROHIBITED_PATTERNS:
        if fnmatch.fnmatch(normalized, pattern):
            return pattern
    return None


def is_ignored(root: Path, path: str) -> bool:
    result = subprocess.run(
        ["git", "check-ignore", "--quiet", "--no-index", path],
        cwd=root,
        check=False,
    )
    return result.returncode == 0


def audit_repository(root: Path = ROOT) -> dict[str, Any]:
    root = root.resolve()
    errors: list[str] = []
    paths = changed_paths(root)
    prohibited = {
        path: reason for path in paths
        if (reason := prohibited_reason(path)) is not None
    }
    if prohibited:
        errors.append("prohibited changed paths are present")

    oversized = {}
    for path in paths:
        absolute = root / path
        if absolute.is_file() and absolute.stat().st_size > MAX_CHANGED_FILE_BYTES:
            oversized[path] = absolute.stat().st_size
    if oversized:
        errors.append("changed files exceed the 10 MiB checkpoint limit")

    missing_required = [path for path in REQUIRED_PATHS if not (root / path).is_file()]
    if missing_required:
        errors.append("required checkpoint files are missing")

    ignored = {path: is_ignored(root, path) for path in EXPECTED_IGNORED_PATHS}
    if not all(ignored.values()):
        errors.append("private raw/review paths are not all Git-ignored")

    hashes = {}
    for path, expected in EXPECTED_HASHES.items():
        absolute = root / path
        actual = sha256_file(absolute) if absolute.is_file() else None
        hashes[path] = {"expected": expected, "actual": actual, "matches": actual == expected}
        if actual != expected:
            errors.append(f"protected hash mismatch: {path}")

    return {
        "schema_version": "judgment-checkpoint-audit-v0.1",
        "passed": not errors,
        "errors": errors,
        "changed_path_count": len(paths),
        "changed_paths": paths,
        "prohibited_changed_paths": prohibited,
        "oversized_changed_files": oversized,
        "required_paths_present": not missing_required,
        "missing_required_paths": missing_required,
        "private_paths_ignored": ignored,
        "protected_hashes": hashes,
        "content_scanned": False,
        "mutations_performed": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    args = parser.parse_args()
    result = audit_repository(args.root)
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    if not result["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
