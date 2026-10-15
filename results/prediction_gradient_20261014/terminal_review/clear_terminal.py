"""Record settled AE processes after its monitored attempt, before outcome analysis."""
from pathlib import Path
import json,hashlib,datetime
ROOT=Path(__file__).resolve().parents[3]
STUDY=ROOT/'outputs/autonomous_prediction_gradient_20261014'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p):return json.loads(p.read_text())
b=read(STUDY/'budget.json')
assert b['status'] in ['complete','incomplete','cpu_budget_exhausted','job_failed','interrupted','monitor_failed']
assert not b.get('running') and not b.get('queued') and not b.get('cleanup_error')
processes=b['process_identities'];groups=b['owned_process_groups'];table={}
for path in Path('/proc').glob('[0-9]*/stat'):
 try:
  fields=path.read_text().rsplit(')',1)[1].split();table[int(path.parent.name)]={'pgrp':int(fields[2]),'start_ticks':int(fields[19])}
 except (FileNotFoundError,ProcessLookupError,PermissionError):pass
for item in processes:
 row=table.get(item['pid']);assert not row or row['start_ticks']!=item['start_ticks']
assert not any(x['pgrp'] in groups for x in table.values())
ready=read(STUDY/'ready.json')
for name,digest in ready['source_pins'].items():assert sha(STUDY/name)==digest,name
for name,digest in ready['production_pins'].items():assert sha(ROOT/name)==digest,name
value={'status':'cleared','all_processes_exited':True,'checked_at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'budget_sha256':sha(STUDY/'budget.json'),'processes':processes,'process_groups':groups,'host_entries_checked':len(table),'study_cpu_seconds':b['cpu_seconds'],'scientific_analysis':'not_yet_run','released_local_pins_unchanged':len(ready['source_pins']),'released_production_pins_unchanged':len(ready['production_pins'])}
if b['status']=='complete':value.update(research_lives=6208,validation_lives=10)
with (STUDY/'terminal_process_clearance.json').open('x') as f:f.write(json.dumps(value,indent=2)+'\n')
print(json.dumps({**{k:v for k,v in value.items() if k not in ['processes','process_groups']},'processes':len(processes),'groups':len(groups),'clearance_sha256':sha(STUDY/'terminal_process_clearance.json')},indent=2))
