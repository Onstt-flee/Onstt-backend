"""Train an explicitly experimental LoRA adapter from the provisional pilot."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import json
from pathlib import Path
import platform
import time


ROOT = Path(__file__).resolve().parents[2]
CONFIG_KEYS = {
    "experiment_id", "status", "model_path", "train_file", "eval_file",
    "source_dataset", "output_dir", "max_length", "num_train_epochs", "max_steps",
    "learning_rate", "per_device_train_batch_size", "gradient_accumulation_steps",
    "warmup_steps", "weight_decay", "lora_r", "lora_alpha", "lora_dropout",
    "target_modules", "seed",
}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _resolve(value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else ROOT / path


def load_config(path: Path) -> dict:
    config = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(config, dict) or set(config) != CONFIG_KEYS:
        missing = sorted(CONFIG_KEYS - set(config if isinstance(config, dict) else {}))
        extra = sorted(set(config if isinstance(config, dict) else {}) - CONFIG_KEYS)
        raise ValueError(f"Invalid config keys; missing={missing}, extra={extra}")
    if config["status"] not in {
        "experimental_provisional", "user_reviewed", "reviewed_with_generated",
        "generated_validated",
    }:
        raise ValueError(
            "status must be experimental_provisional, user_reviewed, "
            "or reviewed_with_generated"
        )
    if config["max_length"] < 1 or config["max_length"] > 2048:
        raise ValueError("max_length must be between 1 and 2048")
    if type(config["max_steps"]) is not int or config["max_steps"] == 0 or config["max_steps"] < -1:
        raise ValueError("max_steps must be -1 or a positive integer")
    if not config["target_modules"] or len(config["target_modules"]) != len(set(config["target_modules"])):
        raise ValueError("target_modules must be a non-empty unique list")
    for key in ("model_path", "train_file", "eval_file", "source_dataset"):
        if not _resolve(config[key]).exists():
            raise ValueError(f"Missing {key}: {_resolve(config[key])}")
    return config


def load_chatml(path: Path) -> list[dict]:
    records = []
    with path.open(encoding="utf-8") as stream:
        for line_number, line in enumerate(stream, 1):
            row = json.loads(line)
            if set(row) != {"messages"}:
                raise ValueError(f"{path}:{line_number}: only messages is allowed")
            messages = row["messages"]
            if not isinstance(messages, list) or len(messages) != 3:
                raise ValueError(f"{path}:{line_number}: expected exactly three messages")
            if [message.get("role") for message in messages] != ["system", "user", "assistant"]:
                raise ValueError(f"{path}:{line_number}: invalid role order")
            if any(set(message) != {"role", "content"} for message in messages):
                raise ValueError(f"{path}:{line_number}: invalid message keys")
            try:
                model_input = json.loads(messages[1]["content"])
                expected = json.loads(messages[2]["content"])
            except (TypeError, json.JSONDecodeError) as exc:
                raise ValueError(f"{path}:{line_number}: content must be JSON") from exc
            valid_inputs = [
                {"context", "learner_level", "text"},
                {"context", "judgment", "learner_level", "text"},
            ]
            if set(model_input) not in valid_inputs:
                raise ValueError(f"{path}:{line_number}: invalid model input")
            valid_v01 = {"corrected_text", "decision", "edits", "reason_ko"}
            valid_v02 = {"corrected_text", "decision", "error_types", "reason_ko"}
            valid_feedback = {"verdict", "issue_codes", "recommended_judgment", "review_reason_ko"}
            if frozenset(expected) not in {frozenset(valid_v01), frozenset(valid_v02), frozenset(valid_feedback)}:
                raise ValueError(f"{path}:{line_number}: invalid expected output")
            records.append(row)
    if not records:
        raise ValueError(f"Empty ChatML file: {path}")
    return records


def validate_inputs(config: dict) -> dict:
    train_path = _resolve(config["train_file"])
    eval_path = _resolve(config["eval_file"])
    source_path = _resolve(config["source_dataset"])
    train = load_chatml(train_path)
    evaluation = load_chatml(eval_path)
    train_inputs = {row["messages"][1]["content"] for row in train}
    eval_inputs = {row["messages"][1]["content"] for row in evaluation}
    overlap = train_inputs & eval_inputs
    if overlap:
        raise ValueError(f"Train/eval input overlap: {len(overlap)}")
    source_statuses = set()
    with source_path.open(encoding="utf-8") as stream:
        for line in stream:
            source_statuses.add(json.loads(line)["review"]["status"])
    expected_statuses = {
        "experimental_provisional": {"provisional"},
        "user_reviewed": {"user_reviewed"},
        "reviewed_with_generated": {"user_reviewed", "generated_validated"},
        "generated_validated": {"generated_validated"},
    }[config["status"]]
    if source_statuses != expected_statuses:
        raise ValueError(
            f"Expected source statuses {sorted(expected_statuses)}, "
            f"got {sorted(source_statuses)}"
        )
    return {
        "train_count": len(train),
        "eval_count": len(evaluation),
        "train_sha256": _sha256(train_path),
        "eval_sha256": _sha256(eval_path),
        "source_dataset_sha256": _sha256(source_path),
        "source_review_statuses": sorted(source_statuses),
    }


def _dataset_rows(rows: list[dict]) -> list[dict]:
    return [
        {"prompt": row["messages"][:2], "completion": [row["messages"][2]]}
        for row in rows
    ]


def train(config: dict, validation: dict, *, output_dir: Path, smoke: bool) -> dict:
    import torch
    from datasets import Dataset
    from peft import LoraConfig
    from transformers import AutoModelForCausalLM, AutoTokenizer
    from trl import SFTConfig, SFTTrainer

    if output_dir.exists() and any(output_dir.iterdir()):
        raise ValueError(f"Refusing to overwrite non-empty output directory: {output_dir}")
    output_dir.mkdir(parents=True, exist_ok=True)

    model_path = _resolve(config["model_path"])
    train_rows = load_chatml(_resolve(config["train_file"]))
    eval_rows = load_chatml(_resolve(config["eval_file"]))
    if smoke:
        train_rows = train_rows[:8]
        eval_rows = eval_rows[:8]

    tokenizer = AutoTokenizer.from_pretrained(model_path, local_files_only=True)
    if tokenizer.pad_token_id is None:
        tokenizer.pad_token = tokenizer.eos_token
    model = AutoModelForCausalLM.from_pretrained(
        model_path,
        dtype=torch.bfloat16,
        attn_implementation="sdpa",
        local_files_only=True,
    )
    model.config.use_cache = False

    peft_config = LoraConfig(
        task_type="CAUSAL_LM",
        r=config["lora_r"],
        lora_alpha=config["lora_alpha"],
        lora_dropout=config["lora_dropout"],
        target_modules=config["target_modules"],
        bias="none",
    )
    args = SFTConfig(
        output_dir=str(output_dir),
        max_length=config["max_length"],
        num_train_epochs=config["num_train_epochs"],
        max_steps=1 if smoke else config["max_steps"],
        learning_rate=config["learning_rate"],
        per_device_train_batch_size=config["per_device_train_batch_size"],
        per_device_eval_batch_size=1,
        gradient_accumulation_steps=1 if smoke else config["gradient_accumulation_steps"],
        warmup_steps=0 if smoke else config["warmup_steps"],
        weight_decay=config["weight_decay"],
        lr_scheduler_type="cosine",
        optim="adamw_torch_fused",
        bf16=True,
        tf32=True,
        gradient_checkpointing=True,
        completion_only_loss=True,
        packing=False,
        shuffle_dataset=True,
        eval_strategy="no",
        save_strategy="no",
        logging_steps=1,
        report_to="none",
        seed=config["seed"],
        data_seed=config["seed"],
    )
    trainer = SFTTrainer(
        model=model,
        args=args,
        train_dataset=Dataset.from_list(_dataset_rows(train_rows)),
        eval_dataset=Dataset.from_list(_dataset_rows(eval_rows)),
        processing_class=tokenizer,
        peft_config=peft_config,
    )
    trainer.model.print_trainable_parameters()
    started = time.monotonic()
    train_result = trainer.train()
    evaluation = trainer.evaluate()
    trainer.save_model(str(output_dir))
    tokenizer.save_pretrained(str(output_dir))

    effective_hyperparameters = {key: config[key] for key in (
        "max_length", "num_train_epochs", "learning_rate",
        "per_device_train_batch_size", "gradient_accumulation_steps",
        "warmup_steps", "weight_decay", "lora_r", "lora_alpha",
        "lora_dropout", "target_modules", "seed",
    )}
    if smoke:
        effective_hyperparameters.update({
            "max_steps": 1,
            "gradient_accumulation_steps": 1,
            "warmup_steps": 0,
        })
    else:
        effective_hyperparameters["max_steps"] = config["max_steps"]

    manifest = {
        "experiment_id": config["experiment_id"] + ("-smoke" if smoke else ""),
        "status": config["status"],
        "created_at": datetime.now(timezone.utc).isoformat(),
        "elapsed_seconds": round(time.monotonic() - started, 3),
        "smoke": smoke,
        "model_path": str(model_path),
        "model_manifest_sha256": _sha256(model_path / "MODEL_MANIFEST.json"),
        "output_dir": str(output_dir),
        "input_validation": validation,
        "effective_train_count": len(train_rows),
        "effective_eval_count": len(eval_rows),
        "hyperparameters": effective_hyperparameters,
        "train_metrics": train_result.metrics,
        "eval_metrics": evaluation,
        "runtime": {
            "python": platform.python_version(),
            "torch": torch.__version__,
            "cuda": torch.version.cuda,
            "gpu": torch.cuda.get_device_name(0),
            "transformers": importlib.metadata.version("transformers"),
            "trl": importlib.metadata.version("trl"),
            "peft": importlib.metadata.version("peft"),
            "datasets": importlib.metadata.version("datasets"),
            "accelerate": importlib.metadata.version("accelerate"),
        },
    }
    (output_dir / "run_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--validate-only", action="store_true")
    parser.add_argument("--smoke", action="store_true")
    parser.add_argument(
        "--acknowledge-provisional",
        action="store_true",
        help="Required: confirms this is not reviewed or production training data.",
    )
    args = parser.parse_args()
    config = load_config(args.config)
    validation = validate_inputs(config)
    if args.validate_only:
        print(json.dumps(validation, ensure_ascii=False, indent=2))
        return 0
    if config["status"] == "experimental_provisional" and not args.acknowledge_provisional:
        raise ValueError("Provisional training requires --acknowledge-provisional")
    output_dir = args.output_dir or _resolve(config["output_dir"])
    if args.smoke and args.output_dir is None:
        raise ValueError("Smoke training requires an explicit --output-dir")
    manifest = train(config, validation, output_dir=output_dir, smoke=args.smoke)
    print(json.dumps(manifest, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
