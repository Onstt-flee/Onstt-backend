"""Fail-closed audit for feedback-v0.3 and its operational-shadow follow-up."""

from __future__ import annotations

import argparse
import fnmatch
import hashlib
import json
from pathlib import Path
import re
import subprocess
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
MAX_BYTES = 10 * 1024 * 1024
DEFERRED_PI_PATHS = {
    "deployment/feedback-staging/finalize-runtime-pairs.sh",
    "deployment/judgment-pi5/run-feedback-pairs-50.sh",
    "evaluation/feedback/RUNTIME_PAIR_INTAKE.md",
    "tests/test_pi5_deployment_templates.py",
}
CHECKPOINT_ROOT_FILES = {"README.md", "PROGRESS.md"}
CHECKPOINT_PREFIXES = (
    "deployment/feedback-staging/",
    "docs/MODEL_SYSTEM_STATUS_2026-10-15.md",
    "evaluation/feedback/HOLDOUT_V0.4_SEAL.md",
    "evaluation/feedback/build_holdout_v0_4.py",
    "evaluation/feedback/build_synthetic_shadow_v0_1.py",
    "evaluation/feedback/holdout_v0.4",
    "evaluation/feedback/actual_shadow_v0.1",
    "evaluation/feedback/shadow_v0.1",
    "scripts/audit_feedback_v0_3_checkpoint.py",
    "scripts/build_feedback_actual_inputs.py",
    "scripts/run_feedback_actual_shadow.py",
    "scripts/run_feedback_synthetic_shadow.py",
    "scripts/run_feedback_worker.py",
    "scripts/run_feedback_worker_process_crash_drill.py",
    "scripts/run_feedback_worker_recovery_drill.py",
    "scripts/verify_feedback_admin_shadow.py",
    "tests/test_feedback_",
    "training/feedback/FEEDBACK_V0.3_",
    "training/feedback/config_v0.3.json",
    "training/feedback/data/eval_v0.3.chatml.jsonl",
    "training/feedback/data/feedback_v0.3",
    "training/feedback/data/train_v0.3.chatml.jsonl",
    "training/feedback/generate_v0_3.py",
)
PROHIBITED = (
    ".env", "*.db", "*.sqlite3", "*.safetensors", "*.gguf", "*.bin",
    "*.pt", "*.pth", "*.wav", "*.mp3", "evaluation/feedback/runs/*",
    "evaluation/feedback/intake/*",
)
KEY_HASHES = {
    "evaluation/feedback/holdout_v0.4.jsonl": "c22c5ddb0153c60d7087ef1e26580e669ea974e2bdafb0e65142f9eaeed60802",
    "evaluation/feedback/holdout_v0.4.protocol.json": "24d7d692faf8994da7dc3779f3e9f0eb8da60bfca7b3d82fbd2559fb8a533d94",
    "evaluation/feedback/holdout_v0.4.result.json": "a047f090d23c199d5186b2c636e0361705541abd42c40bfdcd49fe5efb10cfd7",
    "training/feedback/config_v0.3.json": "998a7a8d89dee594780a5a2aa2a03ee3059e34836609c943b2c626aca0457bef",
    "training/feedback/data/feedback_v0.3.jsonl": "fca3ba047ffc5c19b2af5a3c515538bfda22ae92e50b0d5c3d611ee643a8d196",
    "evaluation/feedback/shadow_v0.1.inputs.jsonl": "495a2c2b07a542422161b76b3377733ad12cb301283402b7aec97444cce03d27",
    "evaluation/feedback/shadow_v0.1.result.json": "4e22d092b19dc889e01cf0a28a1237131bda56d82ad5a9d6d391fa755809ca3d",
    "evaluation/feedback/shadow_v0.1.admin.result.json": "bd0b91c55d565f0b80cdfe9b691cb265473efcef3ce5b48d736f5e4747971f72",
    "evaluation/feedback/shadow_v0.1.admin-http.result.json": "5b96156811f88948e3431c8b47281ba8670ed1e01781e626d5de6f8bccc4ef72",
    "evaluation/feedback/shadow_v0.1.worker-recovery.result.json": "3bdfadb9cfb0aefe18f4b540ca6089a2aafdd7d6b0cfe74d0042485640b60213",
    "evaluation/feedback/shadow_v0.1.worker-process-crash.result.json": "9aebca946465ed31d8a124e63bdbc774896b92097bfb857b201cc5dbd8c8cb16",
}
EXTERNAL_HASHES = {
    "/home/cap-minsung/lora-adapter-bank/adapters/feedback-verifier-v0.3/adapter_model.safetensors": "3bcbc80d1559dacf60a84c708a8ab4c51ee4bd33532acf2ab134394aa2dcd1ad",
    "/home/cap-minsung/lora-adapter-bank/runs/feedback-v0.3/holdout-v0.4.jsonl": "6d3fe9032251403e05d2c8ab970ee7bd7f1ddb11c6f9c5d2afa9e1aeab4abf32",
    "/home/cap-minsung/lora-adapter-bank/runs/feedback-v0.3/synthetic-shadow-v0.1/judgment.jsonl": "d2a581992f4efb1a7129883a5c220dac3d7e69bdab8728c565e53fe5c296106c",
    "/home/cap-minsung/lora-adapter-bank/runs/feedback-v0.3/synthetic-shadow-v0.1.sqlite3": "e3f6e1090fbf8b29927647344adad2e143e07576aced7c26daf8f5e25d5f7ec1",
}
SECRET_PATTERNS = {
    "private_key": re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    "aws_access_key": re.compile(r"AKIA[0-9A-Z]{16}"),
    "github_token": re.compile(r"gh[pousr]_[A-Za-z0-9_]{20,}"),
    "huggingface_token": re.compile(r"hf_[A-Za-z0-9]{20,}"),
}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def git_output(root: Path, *args: str) -> bytes:
    return subprocess.run(
        ["git", *args], cwd=root, check=True, capture_output=True,
    ).stdout


def changed_paths(root: Path) -> list[str]:
    values = git_output(root, "status", "--porcelain=v1", "-z", "--untracked-files=all")
    entries = values.decode("utf-8").split("\0")
    paths: list[str] = []
    index = 0
    while index < len(entries):
        entry = entries[index]; index += 1
        if not entry:
            continue
        paths.append(entry[3:])
        if "R" in entry[:2] or "C" in entry[:2]:
            paths.append(entries[index]); index += 1
    return sorted(set(paths))


def is_checkpoint(path: str) -> bool:
    return path in CHECKPOINT_ROOT_FILES or any(path.startswith(prefix) for prefix in CHECKPOINT_PREFIXES)


def prohibited_reason(path: str) -> str | None:
    return next((pattern for pattern in PROHIBITED if fnmatch.fnmatch(path, pattern)), None)


def verify_hashes(values: dict[str, str], *, root: Path | None = None) -> dict[str, dict[str, Any]]:
    result = {}
    for name, expected in values.items():
        path = (root / name) if root is not None else Path(name)
        actual = sha256_file(path) if path.is_file() else None
        result[name] = {"expected": expected, "actual": actual, "matches": actual == expected}
    return result


def audit(root: Path = ROOT, *, require_external: bool = True) -> dict[str, Any]:
    root = root.resolve()
    changed = changed_paths(root)
    deferred = sorted(path for path in changed if path in DEFERRED_PI_PATHS)
    checkpoint = sorted(path for path in changed if path not in DEFERRED_PI_PATHS and is_checkpoint(path))
    unknown = sorted(set(changed) - set(deferred) - set(checkpoint))
    staged = [value for value in git_output(root, "diff", "--cached", "--name-only")
              .decode("utf-8").splitlines() if value]
    prohibited = {path: prohibited_reason(path) for path in checkpoint if prohibited_reason(path)}
    oversized = {
        path: (root / path).stat().st_size for path in checkpoint
        if (root / path).is_file() and (root / path).stat().st_size > MAX_BYTES
    }
    secrets: dict[str, list[str]] = {}
    for path in checkpoint:
        absolute = root / path
        if not absolute.is_file():
            continue
        text = absolute.read_text(encoding="utf-8", errors="ignore")
        matches = [name for name, pattern in SECRET_PATTERNS.items() if pattern.search(text)]
        if matches:
            secrets[path] = matches
    internal_hashes = verify_hashes(KEY_HASHES, root=root)
    external_hashes = verify_hashes(EXTERNAL_HASHES)
    ignored_checks = {}
    for path in (
        "evaluation/feedback/runs/example.jsonl",
        "evaluation/feedback/intake/example.jsonl",
        "example.safetensors", "example.sqlite3",
    ):
        code = subprocess.run(["git", "check-ignore", "--quiet", "--no-index", path], cwd=root).returncode
        ignored_checks[path] = code == 0

    errors = []
    if unknown: errors.append("unclassified changed paths")
    if staged: errors.append("files are already staged")
    if prohibited: errors.append("prohibited checkpoint paths")
    if oversized: errors.append("checkpoint files exceed 10 MiB")
    if secrets: errors.append("secret-like token patterns found")
    if not all(item["matches"] for item in internal_hashes.values()): errors.append("internal hash mismatch")
    if require_external and not all(item["matches"] for item in external_hashes.values()): errors.append("external hash mismatch")
    if not all(ignored_checks.values()): errors.append("private artifact ignore rule missing")
    return {
        "schema_version": "feedback-v0.3-checkpoint-audit-v0.1",
        "passed": not errors, "errors": errors,
        "changed_path_count": len(changed),
        "checkpoint_path_count": len(checkpoint),
        "deferred_pi_path_count": len(deferred),
        "checkpoint_paths": checkpoint, "deferred_pi_paths": deferred,
        "unknown_paths": unknown, "staged_paths": staged,
        "prohibited_checkpoint_paths": prohibited,
        "oversized_checkpoint_files": oversized,
        "secret_pattern_matches": secrets,
        "internal_hashes": internal_hashes,
        "external_hashes": external_hashes,
        "external_hashes_required": require_external,
        "private_artifact_ignore_rules": ignored_checks,
        "content_scanned_for_secret_patterns": True,
        "mutations_performed": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = audit(args.root)
    payload = json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.write_text(payload, encoding="utf-8")
    print(payload, end="")
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
