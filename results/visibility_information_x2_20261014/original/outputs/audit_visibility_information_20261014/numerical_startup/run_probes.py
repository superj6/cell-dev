"""Bounded no-simulation probe under the exact X monitor numerical environment."""
import hashlib
import json
import os
from pathlib import Path
import subprocess

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
env=dict(os.environ,ATEN_CPU_CAPABILITY='avx2',OMP_WAIT_POLICY='PASSIVE',OMP_NUM_THREADS='1',OMP_THREAD_LIMIT='1',
 MKL_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',NUMEXPR_NUM_THREADS='1',PYTHONUNBUFFERED='1',
 CELL_DEV_CACHE=str(HERE/'unused-kernel-cache'),CELLDEV_VISIBILITY_MONITOR_PID=str(os.getpid()),PYTHONDONTWRITEBYTECODE='1')
env.pop('CELLDEV_THREADS_FILE',None)
cases=['old_fresh','candidate_fresh','candidate_frozen_first','candidate_production_first','candidate_system_first']
results=[]
for case in cases:
 result=subprocess.run([str(ROOT/'.venv/bin/python'),str(HERE/'probe.py'),case],cwd=ROOT,env=env,capture_output=True,text=True,check=True)
 value=json.loads(result.stdout)
 (HERE/(case+'.json')).write_text(json.dumps(value,indent=2)+'\n')
 results.append(value)
expected=[False,True,True,True,False]
if [r['equal_expected'] for r in results]!=expected:
 raise ValueError('startup fix did not preserve exact identity and negative rejection')
if (HERE/'unused-kernel-cache').exists():raise ValueError('unexpected kernel-cache activity')
receipt={'status':'pass','cases':[{k:x[k] for k in ['case','equal_expected','compiled_libraries','simulation_calls']} for x in results],
 'environment_overrides':{k:env[k] for k in ['ATEN_CPU_CAPABILITY','OMP_WAIT_POLICY','OMP_NUM_THREADS','OMP_THREAD_LIMIT','MKL_NUM_THREADS','OPENBLAS_NUM_THREADS','NUMEXPR_NUM_THREADS','PYTHONUNBUFFERED','PYTHONDONTWRITEBYTECODE']},
 'source_sha256':{name:hashlib.sha256((HERE/name).read_bytes()).hexdigest() for name in ['probe.py','run_probes.py']},
 'note':'Frozen X files unchanged; old fresh startup fails exactly as recorded, all consistent-start cases pass, deliberate wrong-library-first remains rejected.'}
(HERE/'receipt.json').write_text(json.dumps(receipt,indent=2)+'\n')
print(json.dumps(receipt,indent=2))
