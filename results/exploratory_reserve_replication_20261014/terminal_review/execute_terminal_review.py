"""Execute authorized AI terminal accounting/replay audits, never lives or builds."""
from pathlib import Path
import hashlib
import json
import os
import subprocess
import time
import numpy as np
B=Path(__file__).resolve().parent
ROOT=B.parents[1]
S=ROOT/'outputs/autonomous_exploratory_reserve_replication_20261014'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
read=lambda p:json.loads(p.read_text())
clearance='487a9373fd036fe5589f8c29fb276809fdb4bdb1902b2cc9bc2769eb72450d01'
assert sha(S/'terminal_process_clearance.json')==clearance
assert sha(S/'budget.json')=='e8e7f316d8f28d883793d8d0e9e9b0201c57d62bab3f7eae395e88658c4e098d'
assert sha(S/'analysis_result/summary.json')=='a070f5b95edd37d95fc8d6cc9a5a87203cac3edc65baf6f18105dc36ccc3f2f9'
assert sha(B/'review_terminal.py')=='7e4f91360ffc685eeed6170a087732a507513f62f9d3fb1935606ffc32241ffe'
assert sha(S/'analysis/analyze.py')=='6111d133af55bdd6d44b9801db54fa02aa9f48f10e9a832c823e50f12fcc9778'
python=str(ROOT/'.venv/bin/python')
commands={
 'independent_raw':[python,str(B/'review_terminal.py'),'--study',str(S),'--run','--terminal-clearance-sha256',clearance,'--out',str(B/'independent_terminal_raw_review.json')],
 'frozen_reader':[python,str(S/'analysis/analyze.py'),'--study',str(S),'--out',str(B/'frozen_reader_reanalysis')],
}
env_updates={'PYTHONDONTWRITEBYTECODE':'1','ATEN_CPU_CAPABILITY':'avx2','OMP_NUM_THREADS':'1','MKL_NUM_THREADS':'1'}
record={'status':'running_authorized_offline_audit','root_terminal_clearance_sha256':clearance,'commands':commands,'cwd':str(ROOT),'environment':env_updates,'script_sha256':sha(Path(__file__)),'executions':{},'simulation_calls':0,'compilation_calls':0,'fresh_genetic_draws':0}
with (B/'terminal_execution_command.json').open('x') as f:f.write(json.dumps(record,indent=2)+'\n')
for name,argv in commands.items():
    start=time.monotonic()
    out=B/(name+'_terminal_stdout.json');err=B/(name+'_terminal_stderr.txt')
    with out.open('x') as stdout,err.open('x') as stderr:
        result=subprocess.run(argv,cwd=ROOT,env=dict(os.environ,**env_updates),stdout=stdout,stderr=stderr)
    record['executions'][name]={'exit_code':result.returncode,'elapsed_wall_seconds':time.monotonic()-start,'stdout_sha256':sha(out),'stderr_sha256':sha(err)}
    if result.returncode:
        record['status']='offline_audit_failed_preserved'
        with (B/'terminal_execution_review.json').open('x') as f:f.write(json.dumps(record,indent=2)+'\n')
        raise SystemExit(result.returncode)
original=S/'analysis_result';repeat=B/'frozen_reader_reanalysis'
assert (original/'summary.json').read_bytes()==(repeat/'summary.json').read_bytes()
assert (original/'paired_vectors.npz').read_bytes()==(repeat/'paired_vectors.npz').read_bytes()
with np.load(original/'paired_vectors.npz',allow_pickle=False) as a,np.load(repeat/'paired_vectors.npz',allow_pickle=False) as b:
    assert len(a.files)==219 and set(a.files)==set(b.files)
    assert all(a[k].dtype==b[k].dtype and a[k].shape==b[k].shape==(512,) and a[k].tobytes()==b[k].tobytes() for k in a.files)
record.update(status='complete_independent_raw_and_frozen_replay',summary_sha256=sha(repeat/'summary.json'),paired_vectors_sha256=sha(repeat/'paired_vectors.npz'),paired_vectors_bitwise_identical=219,summary_bytes_identical=True,npz_bytes_identical=True,raw_review_sha256=sha(B/'independent_terminal_raw_review.json'),frozen_files_modified=False)
with (B/'terminal_execution_review.json').open('x') as f:f.write(json.dumps(record,indent=2)+'\n')
print(json.dumps(record,indent=2))
