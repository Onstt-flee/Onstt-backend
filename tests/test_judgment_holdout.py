import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from evaluation.judgment.build_holdout import build
from evaluation.judgment.dataset import load_records, validate_records

ROOT=Path(__file__).resolve().parents[1]
DATA=ROOT/'evaluation/judgment/holdout_v0.1.jsonl'
MANIFEST=ROOT/'evaluation/judgment/holdout_v0.1.manifest.json'

class JudgmentHoldoutTests(unittest.TestCase):
 def test_manifest_distribution_hash_and_status(self):
  rows=load_records(DATA); validate_records(rows); m=json.loads(MANIFEST.read_text())
  self.assertEqual(len(rows),150); self.assertEqual(len({r['id'] for r in rows}),150)
  self.assertEqual({r['split'] for r in rows},{'holdout_eval'})
  self.assertEqual({r['review']['status'] for r in rows},{'generated_validated'})
  self.assertEqual({r['review']['reviewed_at'] for r in rows},{None})
  self.assertEqual(hashlib.sha256(DATA.read_bytes()).hexdigest(),m['sha256'])
  self.assertEqual(m['decisions'],{'acceptable':60,'insufficient_evidence':24,'needs_correction':66})
  self.assertFalse(m['human_reviewed']); self.assertEqual(m['contamination_audit']['exact_normalized_matches'],0)
 def test_reproducible(self):
  with tempfile.TemporaryDirectory() as d:
   a,b=Path(d)/'a.jsonl',Path(d)/'b.json'
   build(a,b)
   self.assertEqual(a.read_bytes(),DATA.read_bytes()); self.assertEqual(b.read_bytes(),MANIFEST.read_bytes())

if __name__=='__main__': unittest.main()
