"""Fail-closed consistency checks for the frozen feedback model policy."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
POLICY = ROOT / "deployment/feedback-staging/model-policy.json"
ENV_EXAMPLE = ROOT / "deployment/feedback-staging/feedback-staging.env.example"
SERVICE = ROOT / "deployment/feedback-staging/feedback-vllm.service"
PARTICLE_RESULT = ROOT / "evaluation/feedback/particle_risk_adversarial_v0.1.result.json"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _env(path: Path) -> dict[str, str]:
    result = {}
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        result[key] = value
    return result


def validate(
    policy: dict[str, Any],
    env: dict[str, str],
    service_text: str,
    particle_result: dict[str, Any],
) -> dict[str, Any]:
    production = policy.get("production", {})
    shadow = policy.get("shadow", {})
    next_experiment = policy.get("next_experiment", {})
    artifacts = {item.get("name"): item for item in policy.get("research_artifacts", [])}
    checks = {
        "no_production_model": production.get("approved_model") is None,
        "default_disabled": (
            production.get("audit_enabled_by_default") is False
            and env.get("FEEDBACK_AUDIT_ENABLED") == "false"
        ),
        "no_learner_exposure": production.get("learner_exposure_allowed") is False,
        "no_automatic_retraining": production.get("automatic_retraining_allowed") is False,
        "shadow_alias_matches_env": env.get("FEEDBACK_MODEL") == shadow.get("model_alias"),
        "shadow_adapter_matches_env": env.get("FEEDBACK_ADAPTER") == shadow.get("adapter"),
        "shadow_hash_matches_env": env.get("FEEDBACK_MODEL_SHA256") == shadow.get("adapter_sha256"),
        "shadow_service_is_pinned": (
            f"{shadow.get('model_alias')}=" in service_text
            and f"/{shadow.get('adapter')}" in service_text
        ),
        "v04_rejected": artifacts.get("feedback-verifier-v0.4", {}).get("status") == "rejected",
        "v05_rejected": artifacts.get("feedback-verifier-v0.5", {}).get("status") == "rejected",
        "particle_gate_offline": (
            artifacts.get("feedback-particle-risk-v0.1", {}).get("status") == "offline_research_only"
            and particle_result.get("decision") == "failed_development_diagnostic"
            and particle_result.get("operational_activation_allowed") is False
        ),
        "next_experiment_not_authorized": next_experiment.get("authorized") is False,
        "new_holdout_required": (
            next_experiment.get("requires_presealed_unused_evaluation_set") is True
            and next_experiment.get("may_reuse_consumed_holdouts_for_selection") is False
        ),
        "diagnostic_overfit_forbidden": next_experiment.get(
            "may_tune_exception_list_to_particle_adversarial_v0_1"
        ) is False,
    }
    failures = sorted(name for name, passed in checks.items() if not passed)
    return {
        "schema_version": "feedback-model-policy-validation-v0.1",
        "passed": not failures,
        "checks": checks,
        "failures": failures,
        "production_model": production.get("approved_model"),
        "shadow_model_alias": shadow.get("model_alias"),
        "learner_exposure_allowed": production.get("learner_exposure_allowed"),
        "next_experiment_authorized": next_experiment.get("authorized"),
        "content_free": True,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    policy = json.loads(POLICY.read_text(encoding="utf-8"))
    particle_result = json.loads(PARTICLE_RESULT.read_text(encoding="utf-8"))
    result = validate(policy, _env(ENV_EXAMPLE), SERVICE.read_text(encoding="utf-8"), particle_result)
    result["policy_sha256"] = sha256(POLICY)
    result["particle_result_sha256"] = sha256(PARTICLE_RESULT)
    payload = json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.write_text(payload, encoding="utf-8")
    print(payload, end="")
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
