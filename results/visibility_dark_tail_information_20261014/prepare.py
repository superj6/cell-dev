"""AD source-only preparation; actual input copying requires later root registration.

This entry point never generates a controller/genotype, compiles a kernel, or runs a life.
"""
from __future__ import annotations

import argparse
import copy
import json
import math
import os
import subprocess
import sys

import numpy as np
from contracts import ROLES, SCOPE, VALIDATION_MATRIX, WORLD, stage_seeds, transfer_candidates

from common import ROOT, SIZES, STUDY, read, sha, verify_pins

X2 = ROOT / 'results/visibility_information_x2_20261014'
X2_PROTOCOL = 'a2e3699ca131b0091473097607be054d6908c4470aadd1996ad5f2acc0a75d99'
Y = ROOT / 'results/visibility_gradient_20261014'
Y_PROTOCOL = '1880ff6e21b4689031e892d9dc6765a8d9673a35efeefb213acf268f5370adf4'
POLICY = 'retained_X2_flash_controllers_with_physical_amplitude_only'
SOURCE_MAP = {'budget.json': 'operations/budget.json',
              'summary.json': 'postanalysis/working_results/summary.json'}


def freeze(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('xb') as stream:
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())


def freeze_json(path, value):
    freeze(path, (json.dumps(value, indent=2, allow_nan=False) + '\n').encode())


def registration():
    reg = read(STUDY / 'registration.json')
    if reg.get('status') != 'registered' or reg.get('roles') != ROLES or reg.get('candidate_policy') != POLICY:
        raise ValueError('root registration of the fixed candidate policy required')
    seeds = stage_seeds(reg)
    audit = read(STUDY / 'seed_audit.json')
    if (sha(STUDY / 'seed_audit.json') != reg['seed_audit_sha256']
            or audit.get('status') != 'passed' or audit.get('seeds') != seeds):
        raise ValueError('reviewed exact stage namespaces required')
    terminal = reg['AC_terminal']
    verify_pins(terminal['file_pins'], ROOT)
    name = 'outputs/autonomous_visibility_flash_gradient_20261014/budget.json'
    if name not in terminal['file_pins']:
        raise ValueError('terminal AC budget must be pinned')
    budget = read(ROOT / name)
    if (budget.get('status') not in ('complete', 'incomplete', 'cpu_budget_exhausted', 'job_failed',
                                    'interrupted', 'monitor_failed')
            or budget.get('running') or budget.get('queued') or budget.get('cleanup_error')):
        raise ValueError('clean AC terminal state required, not scientific success')
    return reg, seeds


def prepare():
    forbidden = ('protocol.json', 'inputs', 'original', 'bundle.json', 'preparation_claim.json',
                 'ready.json', 'attempt.json', 'budget.json', 'validation', 'rows', 'logs', 'build-cache')
    if any((STUDY / name).exists() for name in forbidden):
        raise ValueError('first preparation refuses any prior input copying or runtime artifacts')
    os.environ.setdefault('ATEN_CPU_CAPABILITY', 'avx2')
    sys.dont_write_bytecode = True
    reg, seeds = registration()
    if sha(X2 / 'protocol.json') != X2_PROTOCOL or sha(Y / 'protocol.json') != Y_PROTOCOL:
        raise ValueError('retained source protocol differs')
    xp, yp = read(X2 / 'protocol.json'), read(Y / 'protocol.json')
    verify_pins(xp['file_pins'], X2)
    verify_pins(yp['production_pins'], ROOT)
    if any(read(X2 / SOURCE_MAP[name]).get('status') != 'complete' for name in ('budget.json', 'summary.json')):
        raise ValueError('complete, corrected X2 information measurement required')
    from numerical import check
    check(xp['numerical_identity'])  # Runtime metadata only; no standard identity invocation.
    source_world = xp['worlds']['flash5_dim25']
    candidates, transfer = transfer_candidates(source_world['candidates'])
    snapshot = json.loads(subprocess.check_output([sys.executable, str(STUDY / 'production_snapshot.py')],
                                                 cwd=ROOT, env=dict(os.environ, PYTHONDONTWRITEBYTECODE='1')))
    old = source_world['production']
    expected_world = dict(old['world'], visibility_low=0.)
    expected_packed = list(old['packed_world'])
    if len(expected_packed) != 70 or expected_packed[69] != .25:
        raise ValueError('retained ABI4 amplitude coordinate differs')
    expected_packed[69] = 0.
    if (snapshot['original_world'] != old['world'] or snapshot['world'] != expected_world
            or snapshot['packed_world'] != expected_packed
            or snapshot['sizes'] != [4,875,129,70,58,5,23,1024,7,18]):
        raise ValueError('only the approved visibility_low constant may differ')
    if any(yp['production_pins'].get(name) != digest for name, digest in snapshot['module_pins'].items()):
        raise ValueError('production snapshot import closure is not pinned')
    world = copy.deepcopy(source_world)
    if world['scratch_slots']['dark_amp'] != .25 or world['packed_world'][16] != .25:
        raise ValueError('retained scratch physical amplitude differs')
    world['scratch_slots']['dark_amp'] = 0.
    world['packed_world'][16] = 0.
    world['production'] = {key: snapshot[key] for key in ('preset', 'world', 'packed_world', 'sizes')}
    world['candidates'] = candidates
    old_complete = read(X2 / 'rows/flash5_dim25/complete.json')
    verify_pins(old_complete['checkpoint_pins'], X2 / 'rows/flash5_dim25')
    timings, origins = {}, {}
    names = ['protocol.json', 'budget.json', 'summary.json', 'rows/flash5_dim25/complete.json']
    for candidate in source_world['candidates']:
        role = candidate['role']
        base = 'rows/flash5_dim25/' + role
        row_path = X2 / base / 'row.npz'
        checkpoint = read(X2 / base / 'checkpoint.json')
        identity = {'protocol_sha256': X2_PROTOCOL, 'world': 'flash5_dim25',
                    'candidate': candidate, 'seeds': xp['seeds']}
        if checkpoint.get('identity') != identity or checkpoint.get('row_sha256') != sha(row_path):
            raise ValueError('retained whole-row timing provenance differs')
        with np.load(row_path, allow_pickle=False) as row:
            cpu, wall = float(row['cpu_seconds']), float(row['wall_seconds'])
            if (json.loads(str(row['identity'])) != identity or row['ledger'].shape != (512,57)
                    or not math.isfinite(cpu) or cpu <= 0 or not math.isfinite(wall) or wall < 0):
                raise ValueError('invalid retained timing row')
        timings[role] = cpu / 512
        names.extend([base + '/row.npz', base + '/checkpoint.json'])
    startup_path = Y / 'startup_identity.json'
    startup = read(startup_path)['identity']
    metadata = {key: value for key, value in startup.items() if key not in ('kernels', 'golden')}
    if metadata != yp['expected_startup_metadata']:
        raise ValueError('retained standard identity metadata differs')
    # No kernel source, input or candidate bytes are copied before all read-only checks above pass.
    freeze_json(STUDY / 'preparation_claim.json', {'status': 'first_preparation',
                'registration_sha256': sha(STUDY / 'registration.json'), 'simulation_calls': 0,
                'compiled_libraries': 0, 'controller_or_genotype_draws': 0})
    source_bundle = read(X2 / 'bundle.json')
    for name, digest in source_bundle['file_pins'].items():
        source = X2 / name
        if sha(source) != digest or not name.startswith('original/'):
            raise ValueError('retained complete ABI3 source bundle differs')
        freeze(STUDY / name, source.read_bytes())
        origins[name] = {'source': str(source.relative_to(ROOT)), 'sha256': digest}
    freeze_json(STUDY / 'bundle.json', {'status': 'copied_byte_identical', 'origins': origins,
                                      'file_pins': source_bundle['file_pins']})
    freeze(STUDY / 'inputs/recovered_inputs.json', (X2 / 'inputs/recovered_inputs.json').read_bytes())
    for name in names:
        source = X2 / SOURCE_MAP.get(name, name)
        freeze(STUDY / 'inputs/X2' / name, source.read_bytes())
    freeze(STUDY / 'inputs/Y/startup_identity.json', startup_path.read_bytes())
    freeze(STUDY / 'inputs/Y/protocol.json', (Y / 'protocol.json').read_bytes())
    freeze_json(STUDY / 'inputs/production_snapshot.json', snapshot)
    freeze_json(STUDY / 'inputs/candidate_transfer.json', transfer)
    freeze_json(STUDY / 'inputs/timing.json', {'cpu_per_life': timings, 'lives_per_role': 512,
                'source_protocol_sha256': X2_PROTOCOL, 'total_cpu_seconds': sum(timings.values()) * 512})
    pinned = [path for folder in ('original','inputs') for path in (STUDY / folder).rglob('*') if path.is_file()]
    pinned += list(STUDY.glob('*.py')) + [STUDY / name for name in
        ('README.md','PREREG.md','SCHEMA.md','bundle.json','registration.json','seed_audit.json','preparation_claim.json')]
    production_pins = dict(xp['production_pins'], **yp['production_pins'])
    verify_pins(production_pins, ROOT)
    protocol = {'format': 1, 'study': 'AD fully dark flash information', 'status': 'prepared_not_released',
        'T': 1024, 'n': 512, 'seeds': seeds['research'], 'validation_seeds': seeds['validation'],
        'worlds': {WORLD: world}, 'abi3_sizes': SIZES, 'monitor_scope': SCOPE,
        'validation_matrix': VALIDATION_MATRIX, 'X2_protocol_sha256': X2_PROTOCOL,
        'candidate_policy': POLICY, 'candidate_transfer': transfer, 'historical_cpu_per_life': timings,
        'expected_numerical_identity': startup, 'numerical_identity': xp['numerical_identity'],
        'production_binding': {'status': 'complete', 'physical_delta': {'visibility_low': [.25, 0.]},
                               'note': 'existing ABI4 physics; exact source/preset packing checked'},
        'production_pins': production_pins, 'production_module_pins': snapshot['module_pins'],
        'raw_ledger_aliases': xp['raw_ledger_aliases'], 'analysis': xp['analysis'],
        'file_pins': {str(path.relative_to(STUDY)): sha(path) for path in sorted(pinned)},
        'simulation_calls_completed': 0, 'compiled_libraries': 0}
    freeze_json(STUDY / 'protocol.json', protocol)
    print(json.dumps({'status': 'prepared_unreleased', 'protocol_sha256': sha(STUDY / 'protocol.json'),
                      'candidates': 13, 'copied_historical_timing_rows': 13, 'simulation_calls': 0,
                      'compiled_libraries': 0, 'controller_or_genotype_draws': 0}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--prepare', action='store_true')
    args = parser.parse_args()
    if args.prepare:
        prepare()
    else:
        print(json.dumps({'status': 'source_only_unregistered', 'monitor_scope': SCOPE,
                          'validation_matrix': VALIDATION_MATRIX, 'planned_simulation_calls': 6732,
                          'simulation_calls': 0, 'compiled_libraries': 0, 'copied_inputs': 0}))
