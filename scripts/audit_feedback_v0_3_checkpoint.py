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
    "analyzer/feedback_contract.py",
    "analyzer/feedback_particle_risk_gate.py",
    "analyzer/feedback_admin.py",
    "deployment/feedback-staging/",
    "docs/MODEL_SYSTEM_STATUS_2026-10-15.md",
    "evaluation/feedback/HOLDOUT_V0.4_SEAL.md",
    "evaluation/feedback/build_holdout_v0_4.py",
    "evaluation/feedback/build_holdout_v0_5.py",
    "evaluation/feedback/build_holdout_v0_6.py",
    "evaluation/feedback/build_synthetic_shadow_v0_1.py",
    "evaluation/feedback/build_existence_particle_diagnostic_v0_1.py",
    "evaluation/feedback/build_existence_particle_diagnostic_v0_2.py",
    "evaluation/feedback/build_particle_risk_adversarial_v0_1.py",
    "evaluation/feedback/compare_runs.py",
    "evaluation/feedback/evaluate_particle_risk_gate.py",
    "evaluation/feedback/evaluate_particle_risk_adversarial.py",
    "evaluation/feedback/existence_particle_diagnostic_v0.1",
    "evaluation/feedback/holdout_v0.4",
    "evaluation/feedback/holdout_v0.5",
    "evaluation/feedback/holdout_v0.6",
    "evaluation/feedback/particle_risk_gate_v0.1.result.json",
    "evaluation/feedback/particle_risk_adversarial_v0.1",
    "evaluation/feedback/model_policy_v0.1.result.json",
    "evaluation/feedback/runner.py",
    "evaluation/feedback/existence_particle_diagnostic_v0.2",
    "evaluation/feedback/reparse_run.py",
    "evaluation/feedback/actual_shadow_v0.1",
    "evaluation/feedback/shadow_v0.1",
    "scripts/audit_feedback_v0_3_checkpoint.py",
    "scripts/build_feedback_actual_inputs.py",
    "scripts/run_feedback_actual_shadow.py",
    "scripts/run_feedback_synthetic_shadow.py",
    "scripts/run_feedback_worker.py",
    "scripts/run_feedback_worker_process_crash_drill.py",
    "scripts/run_feedback_worker_recovery_drill.py",
    "scripts/validate_feedback_model_policy.py",
    "scripts/verify_feedback_admin_shadow.py",
    "scripts/verify_feedback_admin_http.py",
    "tests/test_feedback_",
    "training/feedback/FEEDBACK_V0.3_",
    "training/feedback/FEEDBACK_V0.4_",
    "training/feedback/FEEDBACK_V0.5_",
    "training/feedback/FEEDBACK_PARTICLE_RISK_",
    "training/feedback/FEEDBACK_RESEARCH_FREEZE_",
    "training/feedback/config_v0.4.json",
    "training/feedback/data/eval_v0.4.chatml.jsonl",
    "training/feedback/data/feedback_v0.4",
    "training/feedback/data/train_v0.4.chatml.jsonl",
    "training/feedback/generate_v0_4.py",
    "training/feedback/config_v0.5.json",
    "training/feedback/data/eval_v0.5.chatml.jsonl",
    "training/feedback/data/feedback_v0.5",
    "training/feedback/data/train_v0.5.chatml.jsonl",
    "training/feedback/generate_v0_5.py",
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
    "evaluation/feedback/actual_shadow_v0.1.inputs.manifest.json": "a19f97f42cf2c510fe055b183104bdc464519adb8e89ddeb5b5ab3cd3cb9643f",
    "evaluation/feedback/actual_shadow_v0.1.result.json": "c05d498ba42dc18a54bdfb7c1b6b5be9011b1740de2bb49f139bae1305e0af46",
    "evaluation/feedback/actual_shadow_v0.1.admin.result.json": "bfa9cab1cbe7fe34412bfa2bcda52b1d167bdb0f7537e71d349fac40f2d96a0c",
    "evaluation/feedback/actual_shadow_v0.1.admin-http.result.json": "e0cf27040c809325ac5924e5fa8239a9e0b496888b53147edfa78534a9535d6b",
    "evaluation/feedback/holdout_v0.4.baseline-lora.result.json": "8d402b24478793bf3d782129763e10428914fafefa3b370d838c85aedb0494ac",
    "evaluation/feedback/existence_particle_diagnostic_v0.1.jsonl": "74f2d76f96c79ad942dd682157cd6520287b0cfc78c4a7aa490ca8d02d0dcd9e",
    "evaluation/feedback/existence_particle_diagnostic_v0.1.manifest.json": "842886702bd91d2dcb96fa58242b7d5a4465cf0f306de76ca842a96b9aa911e8",
    "evaluation/feedback/existence_particle_diagnostic_v0.1.protocol.json": "3fb22de6fde24c3981512922d02a3fd523c09a72ef370c45a1b38717641f8901",
    "evaluation/feedback/existence_particle_diagnostic_v0.1.result.json": "91196f37c27ae009eeed88d04b44f3f0da99c79b6da29d17049f9056e76fe523",
    "evaluation/feedback/existence_particle_diagnostic_v0.2.jsonl": "60f884018586b4ccfcbb7786f85fa37f90d62bd6ab5d7ef13ada8b40110ce6d8",
    "evaluation/feedback/existence_particle_diagnostic_v0.2.manifest.json": "b39827f49c984cacb1a8f2c97c03578efd84e2897fdee83c8ed93917b4aede8a",
    "evaluation/feedback/existence_particle_diagnostic_v0.2.protocol.json": "862efbec8677abb3d7cf526ced4cee9ff07d7122cb9f2cdf1518ed811226230c",
    "evaluation/feedback/existence_particle_diagnostic_v0.2.result.json": "c04c0f08b44688524c1d5efac8cbd17234bdf89e33a6fba4afe3e0490e9b19e7",
    "evaluation/feedback/holdout_v0.5.jsonl": "b41e4ee0553e57051c7381c95151a885ffb41979a408078e8923f723352d59fc",
    "evaluation/feedback/holdout_v0.5.manifest.json": "51f015dc2a20227a6b7d460aac2ad977559c221fddac20a6d6747a24de645ad4",
    "evaluation/feedback/holdout_v0.5.protocol.json": "5b5e10e74fd64698907e3dc726b792a2777c232bc45034ab8fa154a0c6e13de5",
    "evaluation/feedback/holdout_v0.5.baseline-lora.result.json": "ca8a1a5bde8e235bea7b6ad3fc6fb6259a32e39787cc5749895b8802b0825d38",
    "training/feedback/config_v0.4.json": "bc09eed0b73265a610cb5ac291109248fff59f6de6dd8a458246f20b1c8e3e53",
    "training/feedback/data/feedback_v0.4.jsonl": "b9bee0df8d341e83d96d1475e07a15c095cd3ef89ae9ef009f56669cc008cd8c",
    "training/feedback/data/train_v0.4.chatml.jsonl": "e85bfa7e2f1fbf0479f609b66b77d4cda186f179f40a93ff5ab7a456b20c048b",
    "training/feedback/data/eval_v0.4.chatml.jsonl": "249fcc0c62c5cfb63d94fecd512954d45d09b771909c77f205550e64938c24d7",
    "training/feedback/data/feedback_v0.4.manifest.json": "3eba228be03a43fc2ad00623bf68712fadea0785d7c27e6267a04f40910a0d37",
    "evaluation/feedback/holdout_v0.6.jsonl": "104e0811b89843debb8d9e2e9b3be337cbf528918f85606a88b17b622bef1581",
    "evaluation/feedback/holdout_v0.6.manifest.json": "9333797dfdcce9bdb75f1fc4f12e4955f3722db719dee07e2b526dca577e2499",
    "evaluation/feedback/holdout_v0.6.protocol.json": "b56c03a55c40be983a777d56bca5996a9a92f9351a42777255c7cedd8a7097ff",
    "evaluation/feedback/holdout_v0.6.baseline-lora.result.json": "a7ad770a6487f864b3b8821bfec005fa6b1290ac2701380a43cb859f076d8f8f",
    "training/feedback/config_v0.5.json": "cac379894927b87c9151b621a184a1ddab75532c13ff98cf62d920ceb773ec2d",
    "training/feedback/data/feedback_v0.5.jsonl": "991bb71e8a9115cb1b18f786f18636cd0c6e693790d16a7c22b37fb9b7b6220a",
    "training/feedback/data/train_v0.5.chatml.jsonl": "7684f1e6707da0def1e7ef603d3dbca84d79cd38e7c938a5f5ce37db1c1c2211",
    "training/feedback/data/eval_v0.5.chatml.jsonl": "e1fbc503a2016df6994e03bf816769b5fe77ba3de30bd8e3526874e7b9fb9fe9",
    "training/feedback/data/feedback_v0.5.manifest.json": "f8cc618e823e9fca85032116f5016ca9ef832a3c03955a7984d6b452a8a23edc",
    "evaluation/feedback/particle_risk_gate_v0.1.result.json": "1cac1a5a6d2aaec7a57a35d5a318a01aef002c74f7bb36ab0672246c785e5578",
    "evaluation/feedback/particle_risk_adversarial_v0.1.jsonl": "d08058fc74c5b53fddf730e5f6a9bb11affb4a595e0df4738252bdd82519bafa",
    "evaluation/feedback/particle_risk_adversarial_v0.1.manifest.json": "631a809a7eac03482cdff1ebb4dd7c8c354ad3f9fc8709a599851b531b72a9fd",
    "evaluation/feedback/particle_risk_adversarial_v0.1.protocol.json": "6c7febb9ab5aaafaed76f509c5c78880c95bcdbbfce5e486986f14030aeda68e",
    "evaluation/feedback/particle_risk_adversarial_v0.1.result.json": "f77600502b4e05ea87c1e9cbb1fb03da7c2698a867353c54cb229dfb0e9128a6",
    "deployment/feedback-staging/model-policy.json": "f94aff6d91f050b437abdc9d4bd22856f681e6d712ea170f83a0fb369972822e",
    "evaluation/feedback/model_policy_v0.1.result.json": "907b884225f3081a83016e4d4cf4a1868795dfa33d6080a55864769a1b73b25d",
}
EXTERNAL_HASHES = {
    "/home/cap-minsung/lora-adapter-bank/adapters/feedback-verifier-v0.5/adapter_model.safetensors": "f6896ab2f0fdd408fb42a4a1fa6fa28f5039f557fab25a0aa7b7a1e76af52d95",
    "/home/cap-minsung/lora-adapter-bank/adapters/feedback-verifier-v0.5/adapter_config.json": "2124306d7a848b078aff0ac5e4355e64588a904b271e4c4d95c65c0540aff1c7",
    "/home/cap-minsung/lora-adapter-bank/adapters/feedback-verifier-v0.5/run_manifest.json": "be5a802a6127d9804f3162327410aaf6cef8fbd43ef3455ba8dded9e29f80e2f",
    "/home/cap-minsung/lora-adapter-bank/runs/feedback-v0.5/holdout-v0.6-base.jsonl": "eab86a8b624b37022f47e339473883842351820c4ad99dccfebdcd3b7cff73ec",
    "/home/cap-minsung/lora-adapter-bank/runs/feedback-v0.5/holdout-v0.6-base.jsonl.manifest.json": "37fe7cc9557c63f36aa489d91f7fdbd087c22696d7de37b5d99bc71e1083549d",
    "/home/cap-minsung/lora-adapter-bank/runs/feedback-v0.5/holdout-v0.6-base.score.json": "6ae951d53e281ebf75913abf5da314df4186abcf75a9248a1da7cad062324e44",
    "/home/cap-minsung/lora-adapter-bank/runs/feedback-v0.5/holdout-v0.6-lora.jsonl": "b8af7b90cd69e1d452463f8cfeacbdc9df428cd1d80bac0e30f048cc00dd9a61",
    "/home/cap-minsung/lora-adapter-bank/runs/feedback-v0.5/holdout-v0.6-lora.jsonl.manifest.json": "6ad82446cf68bb4cf9efd2cd6e77ce94a8fa015d661cf18d0e9740d3c52e4aa4",
    "/home/cap-minsung/lora-adapter-bank/runs/feedback-v0.5/holdout-v0.6-lora.score.json": "1c95b0df858aa65bedcb379a07accbdc6e601f71c658a6ae60b8158ba6c619af",
    "/home/cap-minsung/lora-adapter-bank/adapters/feedback-verifier-v0.4/adapter_model.safetensors": "2af21a821c1f3ad816fc28035479d3525f7aa22eac70c028b1e8a752cdebc78a",
    "/home/cap-minsung/lora-adapter-bank/adapters/feedback-verifier-v0.4/adapter_config.json": "4f2279d22200ba5d64990982f0ce5361f825acbf4d4059526aa8ffad55889765",
    "/home/cap-minsung/lora-adapter-bank/adapters/feedback-verifier-v0.4/run_manifest.json": "62f7ac5bd0863ca77e5b9b681835d65f6f3a812833de184b9f4ee7d087290d09",
    "/home/cap-minsung/lora-adapter-bank/runs/feedback-v0.4/holdout-v0.5-base.jsonl": "6de71acdd4564c2066210677e58482ca2fb134e455a6b2fab4864e260606165e",
    "/home/cap-minsung/lora-adapter-bank/runs/feedback-v0.4/holdout-v0.5-base.jsonl.manifest.json": "c88021138ecdc3ed02873d8656fad920dd81693553ade40b3fbc989958e78062",
    "/home/cap-minsung/lora-adapter-bank/runs/feedback-v0.4/holdout-v0.5-base.score.json": "26c1ac0558be039c5ccbdf65cff98054ca68e68143fac89398d640f7781355f5",
    "/home/cap-minsung/lora-adapter-bank/runs/feedback-v0.4/holdout-v0.5-lora.jsonl": "57851676e541b0daddcf474e1465a589ffe51189a0f23613506bf2b1d3303219",
    "/home/cap-minsung/lora-adapter-bank/runs/feedback-v0.4/holdout-v0.5-lora.jsonl.manifest.json": "1a274cf7b97784872ff02de1824ea3bbbd190c9a7a77d7518cd9bffbab61b33b",
    "/home/cap-minsung/lora-adapter-bank/runs/feedback-v0.4/holdout-v0.5-lora.score.json": "42c0fbb23553de942860de797918adf4ebf7f0967d53f7afba3a7eacd3e2bcef",
    "/home/cap-minsung/lora-adapter-bank/adapters/feedback-verifier-v0.3/adapter_model.safetensors": "3bcbc80d1559dacf60a84c708a8ab4c51ee4bd33532acf2ab134394aa2dcd1ad",
    "/home/cap-minsung/lora-adapter-bank/runs/feedback-v0.3/holdout-v0.4.jsonl": "6d3fe9032251403e05d2c8ab970ee7bd7f1ddb11c6f9c5d2afa9e1aeab4abf32",
    "/home/cap-minsung/lora-adapter-bank/runs/feedback-v0.3/holdout-v0.4-base-retrospective.jsonl": "c2951a96421ca24db5a20d81d93b4aee59184eb70e6dc7988b344ab3d243be1c",
    "/home/cap-minsung/lora-adapter-bank/runs/feedback-v0.3/holdout-v0.4-base-retrospective.jsonl.manifest.json": "c7f15b8aa04cdfb8823358b97660b16c954508f8f66deaf2dc4657b00f4cf0ea",
    "/home/cap-minsung/lora-adapter-bank/runs/feedback-v0.3/holdout-v0.4-base-retrospective.score.json": "6183984dee6dcddb424a6a1b5c6edc354c39decc5363f8bfe0086aeba4db59be",
    "/home/cap-minsung/lora-adapter-bank/runs/feedback-v0.3/existence-particle-diagnostic-v0.1.jsonl": "49fcbbb59fcbec53e1ec0014220e411aab58bf72e8de0452c45a4e27f5acfb95",
    "/home/cap-minsung/lora-adapter-bank/runs/feedback-v0.3/existence-particle-diagnostic-v0.1.jsonl.manifest.json": "798d6b85f3bb4cee95bf5921a15b1e9cfad2cdac8b6a31198f3ed2aecaab99cb",
    "/home/cap-minsung/lora-adapter-bank/runs/feedback-v0.3/existence-particle-diagnostic-v0.1.score.json": "12e00f5d778513fa105b0fec37d8640e04c694ab5cd5b895514c15c4ea32e4f6",
    "/home/cap-minsung/lora-adapter-bank/runs/feedback-v0.3/existence-particle-diagnostic-v0.1.hardened.jsonl": "cab9fb7c6ec2dd00712dd508936a957555fa2ac9d10616794fb5fff5b3c02072",
    "/home/cap-minsung/lora-adapter-bank/runs/feedback-v0.3/existence-particle-diagnostic-v0.1.hardened.jsonl.manifest.json": "e1a485eb8caee607a1281027c030994a58265c179d933ff0628b63c7d27fe5d4",
    "/home/cap-minsung/lora-adapter-bank/runs/feedback-v0.3/existence-particle-diagnostic-v0.1.hardened.score.json": "a5aeeb6bff62d587c227712aad9b980b45ba4d833b6892f5123da199fab447a0",
    "/home/cap-minsung/lora-adapter-bank/runs/feedback-v0.3/synthetic-shadow-v0.1/judgment.jsonl": "d2a581992f4efb1a7129883a5c220dac3d7e69bdab8728c565e53fe5c296106c",
    "/home/cap-minsung/lora-adapter-bank/runs/feedback-v0.3/synthetic-shadow-v0.1.sqlite3": "e3f6e1090fbf8b29927647344adad2e143e07576aced7c26daf8f5e25d5f7ec1",
    "/home/cap-minsung/lora-adapter-bank/runs/feedback-v0.3/actual-shadow-v0.1.inputs.jsonl": "667b0b3c6a074ac9e9a1f46e5a520408dd367f2c79becfe1a7d53b08e9de1330",
    "/home/cap-minsung/lora-adapter-bank/runs/feedback-v0.3/actual-shadow-v0.1/judgment.jsonl": "cfea98563a13bd8d9e11c8797a6217b04eb8b89e2e4b042b437a76bfe6cf1e16",
    "/home/cap-minsung/lora-adapter-bank/runs/feedback-v0.3/actual-shadow-v0.1.sqlite3": "988f21db29cd5c3720f879e378e99386649ad198b4b387f2a5b40db9360f29db",
    "/home/cap-minsung/lora-adapter-bank/runs/feedback-v0.3/existence-particle-diagnostic-v0.2.jsonl": "6317612d05720d5d6de25ec8febf862571156fbfd2e75a09ef7bd4eed90c012a",
    "/home/cap-minsung/lora-adapter-bank/runs/feedback-v0.3/existence-particle-diagnostic-v0.2.jsonl.manifest.json": "1c9996e96bfbb2b8d9ed15cfdade8ae045f474545a79600b025ec371383518f4",
    "/home/cap-minsung/lora-adapter-bank/runs/feedback-v0.3/existence-particle-diagnostic-v0.2.score.json": "1ecc9e77cb2d96aa689ecd2a239c0d7287b3e5b8019a42ae5441e58132e6b897",
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
