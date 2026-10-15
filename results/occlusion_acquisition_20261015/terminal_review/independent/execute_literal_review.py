"""One root-authorized AN terminal-only offline audit, preserving commands and output."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import time

ROOT=Path(__file__).resolve().parents[3]
STUDY=ROOT/'outputs/autonomous_occlusion_acquisition_20261015'
SOURCE=ROOT/'outputs/audit_occlusion_acquisition_20261015/new_terminal_prep'
OUT=STUDY/'terminal_review/independent'
TERMINAL=STUDY/'terminal_review'
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def save(path,value):
    with path.open('x') as stream:stream.write(json.dumps(value,indent=2)+'\n')
prepared=json.loads((SOURCE/'helper_preparation_review.json').read_text())
assert all(sha(SOURCE/name)==digest for name,digest in prepared['source_pins'].items())
assert not OUT.exists()
command=[str(ROOT/'.venv/bin/python'),str(SOURCE/'verify_terminal_raw.py'),'--study',str(STUDY),'--out',str(OUT),
    '--protocol-sha256','ca277b17294bbce52a4fd6bde77e5847b6b5230c00d285ba8492538f7508b26b',
    '--budget-sha256','29f26b5c8331c155bb9974ccdc286c3049660e9181b6fea1323ab08d2bac5365',
    '--clearance-sha256','775de9ed8ff0a8378bff671d96883ba3fefdc07799e6c23cad5e4f0fe72216cf']
save(TERMINAL/'independent_command.json',{'command':command,'cwd':'/','environment':{'PYTHONDONTWRITEBYTECODE':'1'},'script_sha256':sha(Path(__file__))})
start=time.perf_counter()
with (TERMINAL/'independent.stdout.txt').open('x') as out,(TERMINAL/'independent.stderr.txt').open('x') as err:
    result=subprocess.run(command,cwd='/',env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1'),stdout=out,stderr=err,check=False)
paths=[TERMINAL/'independent_command.json',TERMINAL/'independent.stdout.txt',TERMINAL/'independent.stderr.txt']
if OUT.exists():
    for name in ('verify_terminal_raw.py','helper_preparation_review.json'):
        shutil.copyfile(SOURCE/name,OUT/name)
    shutil.copyfile(Path(__file__),OUT/Path(__file__).name)
    paths.extend(path for path in OUT.rglob('*') if path.is_file())
receipt={'status':'passed' if result.returncode==0 else 'failed','exit_code':result.returncode,
         'wall_seconds':time.perf_counter()-start,'source_pins':prepared['source_pins'],
         'files':{str(path.relative_to(STUDY)):sha(path) for path in sorted(paths)},
         'new_simulations':0,'builds':0,'genetic_draws':0}
save(TERMINAL/'independent_execution_review.json',receipt)
print(json.dumps({'status':receipt['status'],'exit_code':result.returncode,'receipt_sha256':sha(TERMINAL/'independent_execution_review.json')}))
raise SystemExit(result.returncode)
