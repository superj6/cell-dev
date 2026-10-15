"""Replay the exploratory repricing using the archived compact input vectors."""
from pathlib import Path
import json,hashlib
import numpy as np
HERE=Path(__file__).resolve().parent
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
summary=json.loads((HERE/'summary.json').read_text())
meta=json.loads((HERE/'inputs/source_metadata.json').read_text())
assert sha(HERE/'inputs/source_vectors.npz')==meta['source_vectors_sha256']
assert sha(HERE/'paired_vectors.npz')==summary['paired_vectors_sha256']
assert sha(HERE/'analyze.py')==summary['analysis_sha256']
assert sha(HERE/'PLAN.md')==summary['plan_sha256']
source=np.load(HERE/'inputs/source_vectors.npz',allow_pickle=False)
saved=np.load(HERE/'paired_vectors.npz',allow_pickle=False)
assert set(source.files)==set(meta['extracted_vectors']) and len(source.files)==24
assert set(saved.files)==set(summary['comparisons']) and len(saved.files)==36
for name,item in summary['comparisons'].items():
 prefix=f"within__{item['world']}__{item['comparison']}"
 v=source[prefix+'__F']+(item['capture_value']/500-1)*source[prefix+'__F__capture_income']
 assert v.shape==(512,) and np.isfinite(v).all()
 assert v.dtype==saved[name].dtype and v.tobytes()==saved[name].tobytes(),name
 mean=float(v.mean());se=float(v.std(ddof=1)/np.sqrt(len(v)))
 assert mean==item['mean_F_change'] and se==item['paired_se']
 assert item['above_3se']==(mean>3*se) and item['below_minus_3se']==(mean < -3*se)
print(json.dumps({'status':'passed','paired_vectors_bitwise_equal':36,'summaries_exact':36,'new_lives':0}))
