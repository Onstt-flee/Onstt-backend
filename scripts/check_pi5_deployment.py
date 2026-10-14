"""Fail-closed Raspberry Pi 5 model/runtime preflight."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import subprocess
import sys
from pathlib import Path
from urllib.request import urlopen


MIN_MEMORY_KIB = 14 * 1024 * 1024


def sha256(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            value.update(chunk)
    return value.hexdigest()


def parse_memtotal(text: str) -> int:
    for line in text.splitlines():
        if line.startswith("MemTotal:"):
            fields = line.split()
            if len(fields) >= 2 and fields[1].isdigit():
                return int(fields[1])
    raise ValueError("MemTotal not found")


def read_os_release(text: str) -> dict[str, str]:
    result = {}
    for line in text.splitlines():
        if "=" in line and not line.lstrip().startswith("#"):
            key, value = line.split("=", 1)
            result[key] = value.strip().strip('"')
    return result


def load_manifest(
    path: Path,
    allowed_quantizations: frozenset[str] = frozenset({"Q4_K_M"}),
) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    if value.get("schema_version") != "pi5-judgment-model-manifest-v0.1":
        raise ValueError("Unsupported model manifest")
    if value.get("quantization") not in allowed_quantizations:
        allowed = ", ".join(sorted(allowed_quantizations))
        raise ValueError(f"Manifest quantization must be one of: {allowed}")
    return value


def live_alias(endpoint: str) -> bool:
    with urlopen(endpoint.rstrip("/") + "/v1/models", timeout=5) as response:
        body = json.loads(response.read().decode("utf-8"))
    return any(row.get("id") == "judgment-v02d" for row in body.get("data", []))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--model-dir", type=Path, required=True)
    parser.add_argument("--llama-server", type=Path, required=True)
    parser.add_argument("--live-endpoint")
    parser.add_argument(
        "--allow-candidate-q5",
        action="store_true",
        help="allow Q5_K_M only for an explicit candidate benchmark",
    )
    args = parser.parse_args()
    checks: dict[str, object] = {}
    errors: list[str] = []

    machine = platform.machine().lower()
    checks["architecture"] = machine
    if machine not in {"aarch64", "arm64"}:
        errors.append("Architecture must be aarch64")
    if sys.version_info[:2] != (3, 12):
        errors.append("Python 3.12 is required")
    checks["python"] = platform.python_version()

    model_text = Path("/proc/device-tree/model").read_text(errors="replace").rstrip("\x00")
    checks["hardware_model"] = model_text
    if "Raspberry Pi 5" not in model_text:
        errors.append("Hardware must be Raspberry Pi 5")

    memory_kib = parse_memtotal(Path("/proc/meminfo").read_text())
    checks["memory_kib"] = memory_kib
    if memory_kib < MIN_MEMORY_KIB:
        errors.append("At least 14 GiB visible RAM is required")

    release = read_os_release(Path("/etc/os-release").read_text())
    checks["os"] = {key: release.get(key) for key in ("ID", "VERSION_CODENAME")}
    if release.get("VERSION_CODENAME") != "bookworm":
        errors.append("Raspberry Pi OS Bookworm is required")

    try:
        mount = subprocess.run(
            ["findmnt", "-n", "-o", "SOURCE,TARGET,FSTYPE", "--target", str(args.model_dir)],
            check=True, capture_output=True, text=True,
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError) as exc:
        mount = f"unavailable: {exc}"
        errors.append("Could not resolve model storage mount")
    checks["model_mount"] = mount
    if "nvme" not in mount.lower():
        errors.append("Model directory must reside on NVMe storage")

    if not args.llama_server.is_file() or not os.access(args.llama_server, os.X_OK):
        errors.append("llama-server is missing or not executable")
    checks["llama_server"] = str(args.llama_server)

    try:
        allowed_quantizations = frozenset(
            {"Q4_K_M", "Q5_K_M"} if args.allow_candidate_q5 else {"Q4_K_M"}
        )
        manifest = load_manifest(args.manifest, allowed_quantizations)
        for role in ("model", "adapter"):
            entry = manifest["files"][role]
            artifact = args.model_dir / entry["name"]
            if not artifact.is_file():
                errors.append(f"Missing {role} artifact")
                continue
            if artifact.stat().st_size != entry["size"] or sha256(artifact) != entry["sha256"]:
                errors.append(f"{role} artifact does not match manifest")
        checks["manifest"] = str(args.manifest)
    except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        errors.append(f"Invalid manifest: {exc}")

    try:
        throttled = subprocess.run(
            ["vcgencmd", "get_throttled"], check=True, capture_output=True, text=True
        ).stdout.strip()
        checks["throttled"] = throttled
        if throttled != "throttled=0x0":
            errors.append("Power or thermal throttling has been recorded")
    except (OSError, subprocess.CalledProcessError):
        errors.append("vcgencmd throttling check failed")

    if args.live_endpoint:
        try:
            checks["model_alias_present"] = live_alias(args.live_endpoint)
            if not checks["model_alias_present"]:
                errors.append("judgment-v02d model alias is missing")
        except Exception as exc:
            errors.append(f"Live model readiness failed: {exc}")

    result = {"ready": not errors, "checks": checks, "errors": errors}
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
