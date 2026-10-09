"""Tests for the frozen v0.5 single-candidate decision."""
import copy, json, unittest
from pathlib import Path
from evaluation.judgment.decide_holdout_v0_5 import decide
ROOT=Path(__file__).resolve().parents[1]
P=json.loads((ROOT/'evaluation/judgment/holdout_v0.5.protocol.json').read_text())
def report():
 def m(n,d): return {'numerator':n,'denominator':d,'value':n/d}
 return {'runs':[{'run':{'model':'judgment-v02j','run_id':'test'},'metrics':{
  'json_contract_success_rate':m(120,120),'decision_accuracy':m(116,120),'overcorrection_rate':m(1,50),
  'correction_detection_precision':m(49,50),'correction_detection_recall':m(45,50),
  'correct_withholding_rate':m(18,20),'clear_case_handling_rate':m(94,100),
  'accepted_correction_rate_end_to_end':m(40,50),'compound_complete_rate':m(3,10)},
  'performance':{'latency_ms':{'p95':1200}},'case_lists':{'system_failure_ids':[],'decision_error_ids':[],
  'overcorrection_ids':['x'],'missed_correction_ids':[]}}]}
class HoldoutV05DecisionTests(unittest.TestCase):
 def test_all_thresholds_select_j(self):
  r=decide(P,report()); self.assertTrue(r['candidate']['eligible']); self.assertEqual(r['selected_candidate'],'judgment-v02j')
 def test_any_failure_selects_none(self):
  x=report(); x['runs'][0]['metrics']['accepted_correction_rate_end_to_end']={'numerator':39,'denominator':50,'value':.78}
  r=decide(P,x); self.assertFalse(r['candidate']['eligible']); self.assertIsNone(r['selected_candidate'])

 def test_observed_final_result_selects_none(self):
  report=json.loads((ROOT/'evaluation/judgment/results/qwen3-4b-v02j-holdout-v05.json').read_text())
  r=decide(P,report); self.assertFalse(r['candidate']['eligible']); self.assertIsNone(r['selected_candidate'])
  self.assertFalse(r['candidate']['eligibility_checks']['overcorrection_rate']); self.assertFalse(r['candidate']['eligibility_checks']['correction_detection_precision']); self.assertFalse(r['candidate']['eligibility_checks']['accepted_correction_rate'])
 def test_wrong_report_model_is_rejected(self):
  x=report(); x['runs'][0]['run']['model']='other'
  with self.assertRaises(ValueError): decide(P,x)
if __name__=='__main__': unittest.main()
