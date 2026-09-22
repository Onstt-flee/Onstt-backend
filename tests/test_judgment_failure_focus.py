import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from training.judgment.build_failure_focus import build
from training.judgment.data import load_records, validate_records
from training.judgment.train_lora import load_chatml

ROOT=Path(__file__).resolve().parents[1]
ADD=ROOT/'training/judgment/data/failure_focus_v0.2_c.jsonl'
ALL=ROOT/'training/judgment/data/pilot_v0.2_c.jsonl'
MAN=ROOT/'training/judgment/data/failure_focus_v0.2_c.manifest.json'

class FailureFocusTests(unittest.TestCase):
 def test_distribution_hash_and_focus(self):
  add=load_records(ADD); rows=load_records(ALL); validate_records(rows,require_reviewed=True); m=json.loads(MAN.read_text())
  self.assertEqual((len(add),len(rows)),(88,628))
  self.assertEqual(hashlib.sha256(ADD.read_bytes()).hexdigest(),m['augmentation_sha256'])
  self.assertEqual(hashlib.sha256(ALL.read_bytes()).hexdigest(),m['combined_sha256'])
  self.assertEqual(len(m['focus_failure_ids']),11)
  self.assertEqual({r['review']['status'] for r in add},{'generated_validated'})
 def test_v02_chatml_has_no_positions(self):
  for split in ('pilot_train','pilot_dev'):
   rows=load_chatml(ROOT/f'training/judgment/data/failure_focus_v0.2_c_chatml/{split}.chatml.jsonl')
   for row in rows:
    expected=json.loads(row['messages'][2]['content'])
    self.assertEqual(set(expected),{'decision','corrected_text','error_types','reason_ko'})
    self.assertNotIn('edits',expected)
 def test_generation_is_reproducible(self):
  before=(ADD.read_bytes(),ALL.read_bytes(),MAN.read_bytes())
  build()
  self.assertEqual(before,(ADD.read_bytes(),ALL.read_bytes(),MAN.read_bytes()))

if __name__=='__main__': unittest.main()
