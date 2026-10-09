"""Validate the frozen final v0.5/J execution protocol."""
import hashlib, json, unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
PROTOCOL=ROOT/'evaluation/judgment/holdout_v0.5.protocol.json'
def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()
class JudgmentHoldoutV05ProtocolTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls): cls.p=json.loads(PROTOCOL.read_text())
 def test_holdout_and_manifest_match(self):
  h=self.p['holdout']; self.assertEqual(sha(ROOT/h['path']),h['sha256']); self.assertEqual(sha(ROOT/h['manifest_path']),h['manifest_sha256'])
  m=json.loads((ROOT/h['manifest_path']).read_text()); self.assertEqual(m['sha256'],h['sha256']); self.assertEqual(m['records'],120); self.assertEqual(h['model_inference_count_before_protocol_freeze'],0)
 def test_repository_inputs_match(self):
  p=self.p; expected={p['candidate']['dataset_path']:p['candidate']['dataset_sha256'],p['candidate']['config_path']:p['candidate']['config_sha256'],'evaluation/judgment/runner.py':p['inference']['runner_sha256'],'evaluation/judgment/scorer.py':p['inference']['scorer_sha256']}
  for path,digest in expected.items(): self.assertEqual(sha(ROOT/path),digest,path)
 def test_external_model_inputs_match(self):
  p=self.p; self.assertEqual(sha(Path(p['base_model']['path'])/'MODEL_MANIFEST.json'),p['base_model']['manifest_sha256'])
  self.assertEqual(sha(Path(p['candidate']['adapter_path'])/'adapter_model.safetensors'),p['candidate']['adapter_sha256'])
  self.assertEqual(sha(Path(p['candidate']['adapter_path'])/'run_manifest.json'),p['candidate']['run_manifest_sha256'])
 def test_thresholds_and_end_policy_are_frozen(self):
  p=self.p; t=p['eligibility_thresholds']; self.assertEqual(t['json_contract_success_rate_min'],.99); self.assertEqual(t['overcorrection_max_count_among_50_acceptable'],1); self.assertEqual(t['accepted_correction_rate_min'],.8); self.assertEqual(t['compound_complete_rate_min'],.3); self.assertEqual(t['p95_latency_ms_max'],1500)
  self.assertTrue(p['inference']['run_candidate_exactly_once']); self.assertTrue(p['execution_policy']['no_rerun_for_model_selection']); self.assertTrue(p['execution_policy']['no_further_lora_tuning_on_v0_5']); self.assertEqual(p['status'],'frozen_before_inference')
if __name__=='__main__': unittest.main()
