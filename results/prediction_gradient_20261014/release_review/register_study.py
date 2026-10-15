"""Root one-time AE registration after independently pinned preparation reviews."""
from pathlib import Path
import datetime
import hashlib
import json
import subprocess

AUDIT = Path(__file__).resolve().parent
ROOT = AUDIT.parents[2]
STUDY = ROOT / 'outputs/autonomous_prediction_gradient_20261014'
AD = ROOT / 'outputs/autonomous_visibility_dark_tail_information_20261014'


def read(path):
    return json.loads(path.read_text())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(path, value):
    with path.open('x') as stream:
        stream.write(json.dumps(value, indent=2) + '\n')


preflight = read(AUDIT / 'registration_prerequisites.json')
assert preflight['status'] == 'accepted_by_root'
assert not any((STUDY / name).exists() for name in
               ['registration.json', 'protocol.json', 'inputs', 'configs', 'ready.json', 'attempt.json'])
for name, digest in preflight['review_pins'].items():
    assert sha(ROOT / name) == digest, name
design = read(AUDIT / 'independent_source_design_review_final.json')
for name, digest in design['source_pins'].items():
    assert sha(ROOT / name) == digest, name
reader = read(AUDIT / 'reader_source_review.json')
for name, digest in reader['source_pins'].items():
    assert sha(AUDIT / name) == digest, name
assert reader['protocol_anchor'] is None
seed_path = ROOT / preflight['seed_audit_path']
assert sha(seed_path) == preflight['seed_audit_sha256']
seed = read(seed_path)
expected = {'calibration': list(range(52280000, 52280002)),
            'screen': list(range(52290000, 52290032)),
            'confirm': list(range(52300000, 52300512))}
assert seed['status'] == 'passed' and seed['seeds'] == expected
assert sha(AD / 'budget.json') == 'efde24e31dffa6c8569b47ebab24739905e1e6605efeb662b0c36bf75c0915c2'
assert sha(AD / 'terminal_process_clearance.json') == '38b58dbc1d22b7822dc54c8fe6835b8cb5fb58c8ee868d0b8446afc1a57bedae'
old = read(AD / 'resource_clearance.json')
terminal = read(AD / 'terminal_process_clearance.json')
processes = old['processes'] + terminal['processes']
groups = sorted(set(old['process_groups'] + terminal['process_groups']))
budgets = old['budget_pins'] | {str((AD / 'budget.json').relative_to(ROOT)): sha(AD / 'budget.json')}
table = {}
for path in Path('/proc').glob('[0-9]*/stat'):
    try:
        fields = path.read_text().rsplit(')', 1)[1].split()
        table[int(path.parent.name)] = {'pgrp': int(fields[2]), 'start_ticks': int(fields[19])}
    except (FileNotFoundError, ProcessLookupError, PermissionError):
        pass
for item in processes:
    actual = table.get(item['pid'])
    assert not actual or actual['start_ticks'] != item['start_ticks']
assert not any(row['pgrp'] in groups for row in table.values())
for name, digest in budgets.items():
    assert sha(ROOT / name) == digest
    budget = read(ROOT / name)
    assert budget['status'] in ['complete', 'incomplete', 'cpu_budget_exhausted', 'job_failed',
                               'interrupted', 'monitor_failed']
    assert not budget.get('running') and not budget.get('queued') and not budget.get('cleanup_error')
head = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
assert head == subprocess.check_output(['git', 'rev-parse', 'origin/master'], cwd=ROOT, text=True).strip()
assert head.startswith('f0b7ca9')
clearance = {'status': 'cleared', 'all_processes_exited': True,
             'checked_at_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
             'processes': processes, 'process_groups': groups, 'budget_pins': budgets,
             'prior_AD_terminal_sha256': sha(AD / 'terminal_process_clearance.json'),
             'prior_AD_public_milestone': head, 'host_entries_checked': len(table), 'simulation_calls': 0}
registration = {
    'study': 'AE retained-panel persistent-target gradient', 'status': 'registered',
    'registered_at_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
    'roles': ['P_D90', 'P_L92', 'H_D90', 'H_L92'],
    'panel_policy': 'entire_Y_panels_unchanged_regardless_of_AD_outcomes',
    'seeds': expected, 'seed_audit_sha256': sha(seed_path),
    'AD_terminal': {'file_pins': {str((AD / name).relative_to(ROOT)): sha(AD / name)
                               for name in ['budget.json', 'terminal_process_clearance.json']},
                    'dependency': 'clean terminal resource state only; no scientific-success prerequisite'},
    'review_pins': preflight['review_pins'],
    'scope': {'research_lives': 6208, 'validation_lives': 10, 'total_lives': 6218,
              'total_cpu_seconds': 5400, 'startup_screen_cpu_seconds': 3400,
              'confirmation_reserve_cpu_seconds': 2000, 'startup_calibration_cpu_seconds': 180,
              'max_workers': 1, 'threads_per_worker': 2},
    'authorization': 'One-time retained-source/input copying and metadata-only preparation under standing '
                     'autonomous authorization. Reuse all130 Y panel rows and exact existing V world; no '
                     'new genotypes, price changes, organism rules or ABI changes. No compilation or lives. '
                     'Root runtime release follows actual-input/reader review and prospective publication. '
                     'First attempt only, no retry, scope reduction or extension.',
    'simulation_calls': 0, 'compiled_libraries': 0, 'genetic_draws': 0}
with (STUDY / 'seed_audit.json').open('xb') as stream:
    stream.write(seed_path.read_bytes())
save(STUDY / 'resource_clearance.json', clearance)
save(STUDY / 'registration.json', registration)
print(json.dumps({'status': 'registered_not_released', 'registration_sha256': sha(STUDY / 'registration.json'),
                  'clearance_sha256': sha(STUDY / 'resource_clearance.json'),
                  'prior_processes': len(processes), 'prior_groups': len(groups), 'prior_budgets': len(budgets),
                  'simulation_calls': 0}, indent=2))
