"""Create a content-addressed manifest for Pi GGUF artifacts."""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            value.update(chunk)
    return value.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--llama-commit", required=True)
    parser.add_argument("--model", type=Path, required=True)
    parser.add_argument("--adapter", type=Path, required=True)
    parser.add_argument(
        "--quantization", choices=("Q4_K_M", "Q5_K_M"), default="Q4_K_M"
    )
    args = parser.parse_args()
    if len(args.llama_commit) != 40 or any(c not in "0123456789abcdef" for c in args.llama_commit):
        parser.error("--llama-commit must be a full lowercase Git commit")
    for path in (args.model, args.adapter):
        if not path.is_file() or path.stat().st_size == 0:
            parser.error(f"Missing or empty artifact: {path}")
    manifest = {
        "schema_version": "pi5-judgment-model-manifest-v0.1",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "llama_cpp_commit": args.llama_commit,
        "base_model": "Qwen3-4B-Instruct-2507",
        "adapter": "judgment-qwen3-4b-failure-focus-v0.2-d",
        "quantization": args.quantization,
        "files": {
            "model": {"name": args.model.name, "size": args.model.stat().st_size,
                      "sha256": digest(args.model)},
            "adapter": {"name": args.adapter.name, "size": args.adapter.stat().st_size,
                        "sha256": digest(args.adapter)},
        },
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(manifest, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
