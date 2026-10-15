"""Extract compact, hash-bound score vectors from the completed AC archive."""
from pathlib import Path
import json,hashlib
import numpy as np
ROOT=Path(__file__).resolve().parents[2]
STUDY=Path(__file__).resolve().parent
AC=ROOT/'results/visibility_flash_gradient_20261014'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
record=json.loads((STUDY/'summary.json').read_text())
for rel in ['protocol.json','analysis_result/summary.json','analysis_result/paired_vectors.npz']:
 expected=record['input_pins']['outputs/autonomous_visibility_flash_gradient_20261014/'+rel]
 assert sha(AC/rel)==expected
summary=json.loads((AC/'analysis_result/summary.json').read_text())
a=np.load(AC/'analysis_result/paired_vectors.npz',allow_pickle=False)
needed={}
for world,items in summary['contrasts']['within'].items():
 for key in items:
  for metric in ['F','F__capture_income']:
   name=f'within__{world}__{key}__{metric}';needed[name]=a[name]
(STUDY/'inputs').mkdir(exist_ok=False)
np.savez_compressed(STUDY/'inputs/source_vectors.npz',**needed)
metadata={'source_study':'AC','public_commit':'8076858','original_capture_value':500,'worlds':summary['worlds'],
 'roles':summary['roles'],'fixed_paired_lives':512,
 'AC_public_pins':{str((AC/rel).relative_to(ROOT)):sha(AC/rel) for rel in ['protocol.json','analysis_result/summary.json','analysis_result/paired_vectors.npz']},
 'extracted_vectors':sorted(needed),'source_vectors_sha256':sha(STUDY/'inputs/source_vectors.npz'),
 'extraction_script_sha256':sha(Path(__file__))}
(STUDY/'inputs/source_metadata.json').write_text(json.dumps(metadata,indent=2)+'\n')
print(json.dumps({'extracted_vectors':len(needed),'new_lives':0}))
