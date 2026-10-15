"""Root one-time AG registration after source, namespace and resource review."""
from pathlib import Path
import datetime
import hashlib
import json
import subprocess

AUDIT=Path(__file__).resolve().parent
ROOT=AUDIT.parents[1]
STUDY=ROOT/'outputs/autonomous_visibility_dark_tail_gradient_20261014'
AF=ROOT/'outputs/autonomous_prediction_continuation_20261014'
PUBLIC_AF=ROOT/'results/prediction_continuation_20261014'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p):return json.loads(p.read_text())
def save(p,value):
 with p.open('x') as f:f.write(json.dumps(value,indent=2,allow_nan=False)+'\n')
def pins(base,values):
 for name,digest in values.items():assert sha(base/name)==digest,name

preflight=read(AUDIT/'registration_prerequisites.json')
assert preflight['status']=='accepted_by_root'
assert not any((STUDY/n).exists() for n in ['registration.json','seed_audit.json','resource_clearance.json',
 'protocol.json','inputs','configs','preparation_claim.json','ready.json','attempt.json','budget.json',
 'measurement','logs','build-cache'])
pins(ROOT,preflight['review_pins'])
producer=read(AUDIT/'source_preparation_review.json')
reader=read(AUDIT/'reader_source_review.json')
peer=read(AUDIT/'analyzer_peer_review.json')
design=read(AUDIT/'independent_source_design_review.json')
assert producer['status']=='passed_source_only_unregistered'
assert reader['status']=='source_only_reviewed_unbound' and reader['protocol_sha256'] is None
assert peer['status']=='approved_source_only_unbound'
assert design['status']=='passed_source_design'
pins(STUDY,producer['source_pins']);pins(AUDIT/'analysis',reader['source_pins'])
pins(STUDY,reader['producer_pins']);pins(AUDIT/'analysis',peer['analysis_source_pins'])
pins(STUDY,peer['producer_source_pins']);pins(ROOT,design['source_pins'])
seed_path=ROOT/preflight['seed_audit_path']
assert sha(seed_path)==preflight['seed_audit_sha256']
seed=read(seed_path)
expected={'calibration':list(range(52320000,52320002)),
          'screen':list(range(52330000,52330032)),
          'confirm':list(range(52340000,52340512))}
assert seed['status']=='passed' and seed['seeds']==expected
assert sha(AF/'budget.json')=='2393cfe4e90ed229b95562461755f39eb05b0fffaf31b2a9539ee29b14e51cd6'
assert sha(AF/'terminal_process_clearance.json')=='d6d29d5a472178588b14bbed8389834672e0161049ed93b02d320f205da0644f'
old=read(AF/'resource_clearance.json');terminal=read(AF/'terminal_process_clearance.json')
assert terminal['status']=='cleared' and terminal['all_processes_exited']
processes=old['processes']+terminal['processes']
groups=sorted(set(old['process_groups']+terminal['process_groups']))
budgets=old['budget_pins']|{str((AF/'budget.json').relative_to(ROOT)):sha(AF/'budget.json')}
table={}
for p in Path('/proc').glob('[0-9]*/stat'):
 try:
  f=p.read_text().rsplit(')',1)[1].split();table[int(p.parent.name)]={'pgrp':int(f[2]),'start_ticks':int(f[19])}
 except (FileNotFoundError,ProcessLookupError,PermissionError):pass
for item in processes:
 row=table.get(item['pid']);assert not row or row['start_ticks']!=item['start_ticks']
assert not any(row['pgrp'] in groups for row in table.values())
for name,digest in budgets.items():
 assert sha(ROOT/name)==digest
 b=read(ROOT/name)
 assert b['status'] in ['complete','incomplete','cpu_budget_exhausted','job_failed','interrupted','monitor_failed']
 assert not b.get('running') and not b.get('queued') and not b.get('cleanup_error')
head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
assert head==subprocess.check_output(['git','rev-parse','origin/master'],cwd=ROOT,text=True).strip()
assert head.startswith('2e41e69')
for name in ['manifest.json','operations/budget.json','operations/terminal_process_clearance.json','analysis_result/summary.json']:
 p=PUBLIC_AF/name
 assert subprocess.check_output(['git','show',head+':'+str(p.relative_to(ROOT))],cwd=ROOT)==p.read_bytes()
now=datetime.datetime.now(datetime.timezone.utc).isoformat()
clearance={'status':'cleared','all_processes_exited':True,'checked_at_utc':now,'processes':processes,
 'process_groups':groups,'budget_pins':budgets,'prior_AF_terminal_sha256':sha(AF/'terminal_process_clearance.json'),
 'prior_AF_public_milestone':head,'host_entries_checked':len(table),'simulation_calls':0}
registration={'study':'AG retained-panel dark-flash gradient','status':'registered','registered_at_utc':now,
 'roles':['P_D90','P_L92','H_D90','H_L92'],
 'panel_policy':'entire_Y_panels_unchanged_regardless_of_AF_outcomes',
 'seeds':expected,'seed_audit_sha256':sha(seed_path),
 'AF_terminal':{'file_pins':{str((AF/n).relative_to(ROOT)):sha(AF/n) for n in
 ['budget.json','terminal_process_clearance.json']},
 'dependency':'Clean terminal resource state only; no scientific-success prerequisite.'},
 'review_pins':preflight['review_pins'],
 'scope':{'research_lives':6208,'validation_lives':10,'total_lives':6218,'total_cpu_seconds':5400,
 'startup_screen_cpu_seconds':3400,'confirmation_reserve_cpu_seconds':2000,
 'startup_calibration_cpu_seconds':180,'max_workers':1,'threads_per_worker':2},
 'authorization':'One invocation of frozen prepare.py --prepare is authorized under standing autonomous scope. '
 'Copy all existing Y panel rows and all 130 AC timing rows, exactly matching AD production dark-flash ABI4 world. '
 'No new genotypes, price changes, organism rules, global channels or ABI changes; no compilation or lives. '
 'Actual-input/reader review and prospective publication precede root runtime release. First attempt only, '
 'no retry, scope reduction or extension. No paid compute or larger task-family rollout.',
 'simulation_calls':0,'compiled_libraries':0,'genetic_draws':0}
with (STUDY/'seed_audit.json').open('xb') as f:f.write(seed_path.read_bytes())
save(STUDY/'resource_clearance.json',clearance)
save(STUDY/'registration.json',registration)
print(json.dumps({'status':'registered_not_released','registration_sha256':sha(STUDY/'registration.json'),
 'clearance_sha256':sha(STUDY/'resource_clearance.json'),'prior_processes':len(processes),
 'prior_groups':len(groups),'prior_budgets':len(budgets),'simulation_calls':0},indent=2))
