"""Root AI registration draft: an independent matched-pair replication, with no engine execution."""
from pathlib import Path
import datetime
import hashlib
import json
import subprocess

AUDIT = Path(__file__).resolve().parent
ROOT = AUDIT.parents[1]
STUDY = ROOT / 'outputs/autonomous_exploratory_reserve_replication_20261014'
AE = ROOT / 'results/prediction_gradient_20261014'
AH = ROOT / 'outputs/autonomous_exploratory_reserve_20261014'
AH_PUBLIC = ROOT / 'results/exploratory_reserve_20261014'


def read(path):
    return json.loads(path.read_text())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(path, value):
    with path.open('x') as stream:
        stream.write(json.dumps(value, indent=2, allow_nan=False) + '\n')


def check_pins(base, mapping):
    for name, digest in mapping.items():
        assert sha(base / name) == digest, name


assert not any((STUDY / name).exists() for name in [
    'registration.json', 'protocol.json', 'inputs', 'configs', 'initialization',
    'preparation_claim.json', 'generation_claim.json', 'ready.json', 'attempt.json',
    'budget.json', 'runs', 'confirmation', 'logs', 'build-cache'])

# Root writes this accepted review bundle only after inspecting the actual schemas.
accepted = read(AUDIT / 'registration_review_acceptance.json')
assert accepted['status'] == 'accepted_by_root'
review_pins = accepted['review_pins']
check_pins(ROOT, review_pins)
check_pins(STUDY, accepted['producer_source_pins'])
check_pins(AUDIT / 'analysis', accepted['reader_source_pins'])
assert accepted['reader_protocol_bound'] is False
assert accepted['scientific_scope'] == 'one_independent_replication_four_generation_pair_two_fresh_reserves'

seed_path = AUDIT / 'namespace/seed_audit.json'
assert sha(seed_path) == accepted['seed_audit_sha256']
seed = read(seed_path)
assert seed['status'] == 'passed' and seed['paired_native_seed'] == 53227
assert seed['confirmation_seeds'] == list(range(52360000, 52360512))
native = seed['run_life_seeds']
assert set(native) == {'control', 'reserve'}
assert native['control'] == native['reserve'] == seed['intentional_overlap']
assert len(set(native['control'])) == len(native['control']) == 64
all_ids = native['control'] + seed['confirmation_seeds']
assert len(set(all_ids)) == 576 and 11 not in all_ids

required = ['protocol.json', 'selection.json', 'operations/budget.json',
            'analysis_result/summary.json', 'confirmation_roles.json',
            'confirmation_genotypes.npz', 'startup_identity.json',
            'operations/terminal_process_clearance.json', 'manifest.json']
ae_pins = {name: sha(AE / name) for name in required}
assert ae_pins['protocol.json'] == '0f5a591fbfb66fd29b5f9cd11d42b482eb8cb09e74613b17cc384ed2c3daa849'
assert read(AE / 'analysis_result/summary.json')['status'] == 'complete'
assert read(AE / 'confirmation_roles.json')['panel_rows']['H_L92'] == 31

prior = read(AH / 'resource_clearance.json')
terminal = read(AH / 'terminal_process_clearance.json')
assert prior['all_processes_exited'] and terminal['all_processes_exited']
processes = prior['processes'] + terminal['processes']
groups = sorted(set(prior['process_groups'] + terminal['process_groups']))
budgets = prior['budget_pins'] | {str((AH / 'budget.json').relative_to(ROOT)): sha(AH / 'budget.json')}
table = {}
for path in Path('/proc').glob('[0-9]*/stat'):
    try:
        fields = path.read_text().rsplit(')', 1)[1].split()
        table[int(path.parent.name)] = {'pgrp': int(fields[2]), 'start_ticks': int(fields[19])}
    except (FileNotFoundError, ProcessLookupError, PermissionError):
        pass
for item in processes:
    actual = table.get(item['pid'])
    assert not actual or actual['start_ticks'] != item['start_ticks'], item
assert not any(item['pgrp'] in groups for item in table.values())
for name, digest in budgets.items():
    assert sha(ROOT / name) == digest, name
    budget = read(ROOT / name)
    assert budget['status'] in ['complete', 'incomplete', 'cpu_budget_exhausted',
                                'job_failed', 'interrupted', 'monitor_failed']
    assert not budget.get('running') and not budget.get('queued') and not budget.get('cleanup_error')
for name in ['budget.json', 'terminal_process_clearance.json']:
    assert (AH / name).read_bytes() == (AH_PUBLIC / 'operations' / name).read_bytes()

head = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
assert head == subprocess.check_output(['git', 'rev-parse', 'origin/master'], cwd=ROOT, text=True).strip()
assert head == accepted['prior_published_milestone']
for path in [AE / name for name in required] + [AH_PUBLIC / 'manifest.json',
        AH_PUBLIC / 'operations/budget.json', AH_PUBLIC / 'operations/terminal_process_clearance.json']:
    assert subprocess.check_output(['git', 'show', head + ':' + str(path.relative_to(ROOT))], cwd=ROOT) == path.read_bytes()

now = datetime.datetime.now(datetime.timezone.utc).isoformat()
clearance = {'status': 'cleared', 'all_processes_exited': True, 'checked_at_utc': now,
    'processes': processes, 'process_groups': groups, 'budget_pins': budgets,
    'host_entries_checked': len(table), 'prior_AH_terminal_sha256': sha(AH / 'terminal_process_clearance.json'),
    'prior_published_milestone': head, 'simulation_calls': 0}
registration = {'study': 'AI paired exploratory reserve replication', 'status': 'registered',
    'registered_at_utc': now, 'runs': ['control', 'reserve'], 'founder_policy': 'fixed_AE_L92_row31',
    'paired_native_seed': seed['paired_native_seed'], 'confirmation_seeds': seed['confirmation_seeds'],
    'native_seed_audit_sha256': sha(seed_path), 'AE_complete': {'file_pins': ae_pins},
    'AH_terminal': {'file_pins': {str((AH / name).relative_to(ROOT)): sha(AH / name)
                                for name in ['budget.json', 'terminal_process_clearance.json']},
                    'dependency': 'Completed AH resource state; AI is motivated by the observed AH relative endpoint advantage.'},
    'review_pins': review_pins, 'resource_clearance_sha256': None,
    'scope': {'native_search_lives': 8268, 'confirmation_lives': 1536, 'research_lives': 9804,
              'golden_lives': 6, 'total_lives': 9810, 'total_cpu_seconds': 5400,
              'startup_search_cpu_seconds': 3400, 'confirmation_reserve_cpu_seconds': 2000,
              'max_search_workers': 2, 'threads_per_worker': 2, 'max_simulation_threads': 4,
              'generations_per_arm': 4, 'reserved_offspring': 2, 'active_reserve_generations': [0, 1, 2]},
    'authorization': 'One invocation of frozen prepare.py --prepare is authorized under standing minor-selection '
        'and autonomous-work permission. Copy fixed AE L92 inputs and generate exactly one shared ordinary '
        '32-parent initialization, with native RNG operations recorded and identical copies for both arms. '
        'No engine builds or lives. Actual input, reader and source reviews plus prospective publication precede '
        'separate root runtime release. First attempt only; no retry, resume, scope reduction or extension. '
        'Task F, prices, ABI3 world, local asynchronous rules and production defaults are unchanged. '
        'This repeats the frozen AH policy with an independent native seed. The two-slot external reserve is independent of captures, morphology and genotype. No paid compute.',
    'simulation_calls': 0, 'compiled_libraries': 0, 'genetic_draws_at_registration': 0}

save(AUDIT / 'registration_prerequisites.json', accepted)
with (STUDY / 'seed_audit.json').open('xb') as stream:
    stream.write(seed_path.read_bytes())
save(STUDY / 'resource_clearance.json', clearance)
registration['resource_clearance_sha256'] = sha(STUDY / 'resource_clearance.json')
save(STUDY / 'registration.json', registration)
print(json.dumps({'status': 'registered_not_released', 'registration_sha256': sha(STUDY / 'registration.json'),
    'clearance_sha256': sha(STUDY / 'resource_clearance.json'), 'prior_processes': len(processes),
    'prior_groups': len(groups), 'prior_budgets': len(budgets), 'simulation_calls': 0}, indent=2))
