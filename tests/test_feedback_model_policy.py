import copy
import json
from pathlib import Path
import unittest

from scripts.validate_feedback_model_policy import _env, validate


ROOT = Path(__file__).resolve().parents[1]
DEPLOY = ROOT / "deployment/feedback-staging"


def inputs():
    return (
        json.loads((DEPLOY / "model-policy.json").read_text(encoding="utf-8")),
        _env(DEPLOY / "feedback-staging.env.example"),
        (DEPLOY / "feedback-vllm.service").read_text(encoding="utf-8"),
        json.loads((ROOT / "evaluation/feedback/particle_risk_adversarial_v0.1.result.json").read_text(encoding="utf-8")),
    )


class FeedbackModelPolicyTests(unittest.TestCase):
    def test_current_policy_is_frozen_disabled_and_consistent(self):
        result = validate(*inputs())
        self.assertTrue(result["passed"], result["failures"])
        self.assertIsNone(result["production_model"])
        self.assertEqual(result["shadow_model_alias"], "feedback-qwen3-8b-v03")
        self.assertFalse(result["learner_exposure_allowed"])
        self.assertFalse(result["next_experiment_authorized"])
        self.assertTrue(result["content_free"])

    def test_accidental_v05_activation_fails_closed(self):
        policy, env, service, particle = inputs()
        changed = copy.deepcopy(policy)
        changed["production"]["approved_model"] = "feedback-verifier-v0.5"
        changed["production"]["learner_exposure_allowed"] = True
        result = validate(changed, env, service, particle)
        self.assertFalse(result["passed"])
        self.assertIn("no_production_model", result["failures"])
        self.assertIn("no_learner_exposure", result["failures"])

    def test_reusing_consumed_holdout_or_tuning_to_diagnostic_fails(self):
        policy, env, service, particle = inputs()
        changed = copy.deepcopy(policy)
        changed["next_experiment"]["authorized"] = True
        changed["next_experiment"]["may_reuse_consumed_holdouts_for_selection"] = True
        changed["next_experiment"]["may_tune_exception_list_to_particle_adversarial_v0_1"] = True
        result = validate(changed, env, service, particle)
        self.assertFalse(result["passed"])
        self.assertIn("next_experiment_not_authorized", result["failures"])
        self.assertIn("new_holdout_required", result["failures"])
        self.assertIn("diagnostic_overfit_forbidden", result["failures"])


if __name__ == "__main__":
    unittest.main()
