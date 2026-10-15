"""Root one-time AF registration; no engine import, genetic draw or simulation."""
from pathlib import Path
import datetime
import hashlib
import json
import subprocess

AUDIT = Path(__file__).resolve().parent
ROOT = AUDIT.parents[1]
STUDY = ROOT / 'outputs/autonomous_prediction_continuation_20261014'
AE = ROOT / 'results/prediction_gradient_20261014'
VIEW = ROOT / 'results/ae_watchable_20261014'

def read(p):
    return json.loads(p.read_text())

def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()

def save(p, value):
    with p.open('x') as stream:
        stream.write(json.dumps(value, indent=2, allow_nan=False) + '\n')

def pins(base, mapping):
    for name, digest in mapping.items():
        assert sha(base / name) == digest, name

assert not any((STUDY / name).exists() for name in ['registration.json','protocol.json','inputs',
    'configs','initialization','preparation_claim.json','generation_claim.json','ready.json','attempt.json',
    'budget.json','runs','confirmation','logs','build-cache'])
reviews = ['source_preparation_review.json','reader_source_review.json','analyzer_peer_review.json',
           'independent_source_design_review.json','cost_feasibility.json',
           'namespace/seed_audit.json','namespace/candidate_namespace_review.json',
           'namespace/final_namespace_delta.json','namespace/watchable_publication_supplement.json',
           'watchable_ui_scientific_review.json']
review_pins = {str((AUDIT / name).relative_to(ROOT)): sha(AUDIT / name) for name in reviews}
producer = read(AUDIT / reviews[0])
reader = read(AUDIT / reviews[1])
peer = read(AUDIT / reviews[2])
design = read(AUDIT / reviews[3])
assert producer['status'] == 'passed_source_only_unregistered'
assert reader['status'] == 'source_only_reviewed_unbound' and reader['protocol_sha256'] is None
assert peer['status'] == 'approved_source_only_unbound'
assert design['status'] == 'passed_source_design' and design['cost_projection']['feasible']
pins(STUDY, producer['source_pins'])
pins(AUDIT / 'analysis', reader['source_pins'])
pins(STUDY, reader['producer_pins'])
pins(AUDIT / 'analysis', peer['analysis_pins'])
pins(STUDY, peer['producer_pins'])
pins(ROOT, design['source_pins'])
seed_path = AUDIT / 'namespace/seed_audit.json'
assert sha(seed_path) == '96abcd3e6a81ad8c0710b0ac870c993bb01dc115d08eb8920c000251e01960d8'
seed = read(seed_path)
assert seed['status'] == 'passed' and seed['runs'] == [53224,53225]
assert seed['run_backgrounds'] == {'53224':'D90','53225':'L92'}
assert seed['confirmation_seeds'] == list(range(52310000,52310512))
assert all(len(set(ids)) == len(ids) == 64 for ids in seed['run_life_seeds'].values())
all_ids = seed['confirmation_seeds'] + sum(seed['run_life_seeds'].values(), [])
assert len(set(all_ids)) == 640 and 11 not in all_ids
supplement = read(AUDIT / 'namespace/watchable_publication_supplement.json')
assert supplement['status'] == 'passed' and supplement['previous_seed_audit_sha256'] == sha(seed_path)
assert supplement['public_manifest_sha256'] == sha(VIEW / 'manifest.json')
for item in supplement['exact_source_copy_pairs']:
    assert sha(ROOT / item['source']) == sha(ROOT / item['copy']) == item['sha256']
required = ['protocol.json','selection.json','operations/budget.json','analysis_result/summary.json',
            'confirmation_roles.json','confirmation_genotypes.npz','startup_identity.json',
            'operations/terminal_process_clearance.json','manifest.json']
ae_pins = {name: sha(AE / name) for name in required}
assert ae_pins['protocol.json'] == '0f5a591fbfb66fd29b5f9cd11d42b482eb8cb09e74613b17cc384ed2c3daa849'
assert ae_pins['operations/budget.json'] == '2b5518ca6fb48c11a827def46151ed1f01951854e2567c932c44eeacd14a28af'
assert read(AE / 'analysis_result/summary.json')['status'] == 'complete'
old = read(AE / 'operations/resource_clearance.json')
terminal = read(AE / 'operations/terminal_process_clearance.json')
viewer = read(VIEW / 'validation_budget.json')
assert terminal['all_processes_exited'] and viewer['all_processes_exited']
processes = old['processes'] + terminal['processes'] + viewer['processes']
groups = sorted(set(old['process_groups'] + terminal['process_groups'] + viewer['process_groups']))
budgets = old['budget_pins'] | {str(p.relative_to(ROOT)):sha(p) for p in
    [AE / 'operations/budget.json', VIEW / 'validation_budget.json']}
table = {}
for p in Path('/proc').glob('[0-9]*/stat'):
    try:
        f = p.read_text().rsplit(')',1)[1].split()
        table[int(p.parent.name)] = {'pgrp':int(f[2]),'start_ticks':int(f[19])}
    except (FileNotFoundError,ProcessLookupError,PermissionError):
        pass
for item in processes:
    actual = table.get(item['pid'])
    assert not actual or actual['start_ticks'] != item['start_ticks'], item
assert not any(v['pgrp'] in groups for v in table.values())
assert 1321448 not in table, 'viewer helper PID remains present'
for name,digest in budgets.items():
    assert sha(ROOT / name) == digest
    b = read(ROOT / name)
    assert b['status'] in ['complete','incomplete','cpu_budget_exhausted','job_failed','interrupted','monitor_failed']
    assert not b.get('running') and not b.get('queued') and not b.get('cleanup_error')
head = subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
assert head == subprocess.check_output(['git','rev-parse','origin/master'],cwd=ROOT,text=True).strip()
assert head.startswith('2cba717')
for p in [AE / name for name in required] + [VIEW / 'manifest.json', ROOT / 'results/atlas/persistent_target.html']:
    assert subprocess.check_output(['git','show',head+':'+str(p.relative_to(ROOT))],cwd=ROOT) == p.read_bytes()
now = datetime.datetime.now(datetime.timezone.utc).isoformat()
preflight = {'status':'accepted_by_root','review_pins':review_pins,'seed_audit_path':str(seed_path.relative_to(ROOT)),
             'seed_audit_sha256':sha(seed_path),'source_producer_files':len(producer['source_pins']),
             'reader_protocol_bound':False,'simulation_calls':0,'genetic_draws':0}
clearance = {'status':'cleared','all_processes_exited':True,'checked_at_utc':now,'processes':processes,
    'process_groups':groups,'budget_pins':budgets,'host_entries_checked':len(table),
    'prior_AE_terminal_sha256':sha(AE / 'operations/terminal_process_clearance.json'),
    'prior_published_milestone':head,'viewer_helper_pid_absent':1321448,
    'viewer_helper_identity_limitation':'Parent start ticks not recorded; PID absent and helper session exited0.',
    'simulation_calls':0}
registration = {'study':'AF ordinary persistent-target continuation','status':'registered',
    'registered_at_utc':now,'founder_policy':'both_AE_selected_regardless_of_confirmation_sign',
    'runs':seed['runs'],'run_backgrounds':seed['run_backgrounds'],'confirmation_seeds':seed['confirmation_seeds'],
    'native_seed_audit_sha256':sha(seed_path),'AE_complete':{'file_pins':ae_pins,
    'dependency':'Completed fixed input provenance and clean resource state; no positive outcome prerequisite.'},
    'review_pins':review_pins,'resource_clearance_sha256':None,
    'scope':{'native_search_lives':8268,'confirmation_lives':2048,'research_lives':10316,'golden_lives':6,
    'total_lives':10322,'total_cpu_seconds':5400,'startup_search_cpu_seconds':3400,
    'confirmation_reserve_cpu_seconds':2000,'max_search_workers':2,'threads_per_worker':2,
    'max_simulation_threads':4,'generations_per_start':4},
    'authorization':'One invocation of frozen prepare.py --prepare is authorized under standing autonomous scope. '
    'Copy fixed inputs and generate exactly one ordinary32-parent initialization per start with recorded native RNG '
    'operations. No engine build or life. Actual-input/reader review and prospective publication precede root '
    'runtime release. First attempt only; no retry, resume, scope reduction or extension. Unchanged prices, ABI3, '
    'persistent-target world and local asynchronous rules. No paid compute.',
    'simulation_calls':0,'compiled_libraries':0,'genetic_draws_at_registration':0}
save(AUDIT / 'registration_prerequisites.json',preflight)
with (STUDY / 'seed_audit.json').open('xb') as stream:
    stream.write(seed_path.read_bytes())
save(STUDY / 'resource_clearance.json',clearance)
registration['resource_clearance_sha256'] = sha(STUDY / 'resource_clearance.json')
save(STUDY / 'registration.json',registration)
print(json.dumps({'status':'registered_not_released','registration_sha256':sha(STUDY / 'registration.json'),
    'clearance_sha256':sha(STUDY / 'resource_clearance.json'),'prior_processes':len(processes),
    'prior_groups':len(groups),'prior_budgets':len(budgets),'simulation_calls':0},indent=2))
