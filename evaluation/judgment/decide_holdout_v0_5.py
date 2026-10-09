"""Apply the frozen holdout v0.5 single-candidate policy without model calls."""
from __future__ import annotations
import argparse, hashlib, json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
ROOT=Path(__file__).resolve().parents[2]
DEFAULT_PROTOCOL=ROOT/'evaluation/judgment/holdout_v0.5.protocol.json'
DEFAULT_REPORT=ROOT/'evaluation/judgment/results/qwen3-4b-v02j-holdout-v05.json'
DEFAULT_OUTPUT=ROOT/'evaluation/judgment/holdout_v0.5.result.json'

def sha256(path: Path)->str: return hashlib.sha256(path.read_bytes()).hexdigest()
def _metric(run:dict[str,Any],name:str)->dict[str,Any]: return run['metrics'][name]
def summarize(run:dict[str,Any])->dict[str,Any]:
    names=('json_contract_success_rate','decision_accuracy','overcorrection_rate',
           'correction_detection_precision','correction_detection_recall',
           'correct_withholding_rate','clear_case_handling_rate',
           'accepted_correction_rate_end_to_end','compound_complete_rate')
    return {'model':run['run']['model'],'run_id':run['run']['run_id'],
            'metrics':{n:{k:_metric(run,n)[k] for k in ('numerator','denominator','value')} for n in names},
            'p95_latency_ms':run['performance']['latency_ms']['p95'],
            'system_failure_ids':run['case_lists']['system_failure_ids'],
            'decision_error_ids':run['case_lists']['decision_error_ids'],
            'overcorrection_ids':run['case_lists']['overcorrection_ids'],
            'missed_correction_ids':run['case_lists']['missed_correction_ids']}

def decide(protocol:dict[str,Any], report:dict[str,Any])->dict[str,Any]:
    runs=report['runs']
    if len(runs)!=1 or runs[0]['run']['model']!=protocol['candidate']['served_model']:
        raise ValueError('Report must contain exactly the frozen J candidate')
    s=summarize(runs[0]); m=s['metrics']; t=protocol['eligibility_thresholds']
    checks={
      'json_contract_success_rate':m['json_contract_success_rate']['value']>=t['json_contract_success_rate_min'],
      'overcorrection_rate':m['overcorrection_rate']['value']<=t['overcorrection_rate_max'] and m['overcorrection_rate']['numerator']<=t['overcorrection_max_count_among_50_acceptable'],
      'correction_detection_precision':m['correction_detection_precision']['value']>=t['correction_detection_precision_min'],
      'correction_detection_recall':m['correction_detection_recall']['value']>=t['correction_detection_recall_min'],
      'clear_case_handling_rate':m['clear_case_handling_rate']['value']>=t['clear_case_handling_rate_min'],
      'correct_withholding_rate':m['correct_withholding_rate']['value']>=t['correct_withholding_rate_min'],
      'accepted_correction_rate':m['accepted_correction_rate_end_to_end']['value']>=t['accepted_correction_rate_min'],
      'compound_complete_rate':m['compound_complete_rate']['value']>=t['compound_complete_rate_min'],
      'p95_latency_ms':s['p95_latency_ms']<=t['p95_latency_ms_max']}
    eligible=all(checks.values())
    return {'candidate':{**s,'eligibility_checks':checks,'eligible':eligible},
            'selected_candidate':s['model'] if eligible else None,
            'selection_decision':'j_met_all_thresholds' if eligible else 'j_failed_one_or_more_thresholds',
            'operational_promotion_allowed':eligible}

def build_result(protocol_path:Path,report_path:Path,created_at:str|None=None)->dict[str,Any]:
    protocol=json.loads(protocol_path.read_text()); report=json.loads(report_path.read_text())
    result=decide(protocol,report)
    result.update({'schema_version':'judgment-holdout-v0.5-result-1',
      'created_at':created_at or datetime.now(timezone.utc).isoformat(),'status':'consumed',
      'protocol_path':str(protocol_path.resolve()),'protocol_sha256':sha256(protocol_path),
      'holdout_sha256':protocol['holdout']['sha256'],'comparison_report_path':str(report_path.resolve()),
      'comparison_report_sha256':sha256(report_path),
      'execution_policy':{'j_inference_count':1,'rerun_for_model_selection_allowed':False,
                          'further_lora_tuning_on_v0_5_allowed':False}})
    return result

def main(argv=None)->int:
    p=argparse.ArgumentParser(description=__doc__); p.add_argument('--protocol',type=Path,default=DEFAULT_PROTOCOL)
    p.add_argument('--report',type=Path,default=DEFAULT_REPORT); p.add_argument('--output',type=Path,default=DEFAULT_OUTPUT)
    p.add_argument('--created-at'); p.add_argument('--overwrite',action='store_true'); a=p.parse_args(argv)
    if a.output.exists() and not a.overwrite: raise SystemExit(f'Output already exists: {a.output}')
    r=build_result(a.protocol.resolve(),a.report.resolve(),a.created_at)
    a.output.write_text(json.dumps(r,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'output':str(a.output.resolve()),'selected_candidate':r['selected_candidate'],
                      'selection_decision':r['selection_decision']},ensure_ascii=False,indent=2)); return 0
if __name__=='__main__': raise SystemExit(main())
