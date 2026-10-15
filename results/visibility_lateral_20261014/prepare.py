"""AA source-only preparation; actual fixed inputs require reviewed terminal Z and root registration."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import sys
from dataclasses import asdict, replace
from pathlib import Path

os.environ.setdefault('ATEN_CPU_CAPABILITY', 'avx2')
sys.dont_write_bytecode = True
STUDY = Path(__file__).resolve().parent
ROOT = STUDY.parents[1]
Z = ROOT / 'outputs/autonomous_visibility_continuation_20261014'
Z_PROTOCOL = '2e3e2a2f7bd19f8a10620f8bf4c23a5eb31d4c033a48c0939bf421d234be2935'
LABELS = ['D90', 'L92', 'Y_D90', 'Y_L92', 'Z_D90', 'Z_L92']
CONDITIONS = ['normal', 'freeze', 'freeze+lateral_off']
sys.path.insert(0, str(ROOT))


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


def freeze(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and path.read_bytes() != data:
        raise ValueError('prepared input changed: ' + str(path))
    path.write_bytes(data)


def freeze_json(path, value):
    freeze(path, (json.dumps(value, indent=2, allow_nan=False) + '\n').encode())


def cost_projection(rates):
    if set(rates) != set(LABELS) or any(not math.isfinite(v) or v <= 0 for v in rates.values()):
        raise ValueError('all six positive actual Z confirmation costs required')
    projected = 180 + 1.5 * 3 * 128 * sum(rates.values())
    return {'rates_cpu_per_life': rates, 'projected_cpu_seconds': projected,
            'formula': '180 + 1.5 * 3 * 128 * sum(six_cpu_per_life)',
            'release_threshold_cpu_seconds': 1190, 'feasible': projected <= 1190,
            'limitation': 'Unlesioned completed Z costs plus fixed margin do not bound changed lesion dynamics.'}


def worlds():
    from src.life import spec
    base = spec.world('catch_speck_blink20_20_l4', T=1024, t_fork=512, t_open=544)
    return {name: replace(base, fork_flags=0 if name == 'normal' else spec.V4.flags(*name.split('+')))
            for name in CONDITIONS}


def registration():
    item = read(STUDY / 'registration.json')
    if item.get('status') != 'registered' or item.get('labels') != LABELS or item.get('conditions') != CONDITIONS:
        raise ValueError('root registration of exact six roles and three conditions required')
    seeds = item['seeds']
    if (len(seeds) != 128 or len(set(seeds)) != 128 or 11 in seeds
            or any(type(x) is not int or x < 0 for x in seeds)):
        raise ValueError('128 fresh paired research seeds required')
    audit = read(STUDY / 'seed_audit.json')
    if audit.get('status') != 'passed' or audit.get('seeds') != seeds or sha(STUDY / 'seed_audit.json') != item['seed_audit_sha256']:
        raise ValueError('root-reviewed exact namespace required')
    dep = item['Z_complete']
    if sha(Z / 'protocol.json') != Z_PROTOCOL:
        raise ValueError('fixed Z protocol differs')
    for name, digest in dep['file_pins'].items():
        path = (Z / name).resolve()
        if not path.is_relative_to(Z.resolve()) or sha(path) != digest:
            raise ValueError('terminal Z dependency differs: ' + name)
    required = {'protocol.json', 'budget.json', 'confirmation/endpoints.json', 'confirmation/genotypes.npz',
                'confirmation/row_index.json', 'confirmation/report.json'}
    if not required.issubset(dep['file_pins']):
        raise ValueError('terminal Z evidence pins incomplete')
    summary_path = (ROOT / dep['summary_path']).resolve()
    if not summary_path.is_relative_to(ROOT) or sha(summary_path) != dep['summary_sha256']:
        raise ValueError('reviewed complete Z analysis required')
    summary, budget = read(summary_path), read(Z / 'budget.json')
    if (summary.get('status') != 'complete' or summary.get('protocol_sha256') != Z_PROTOCOL
            or budget.get('status') != 'complete' or budget.get('running') or budget.get('queued')
            or budget.get('cleanup_error') or budget.get('exit_code') != 0):
        raise ValueError('Z must be completely analyzed and cleanly terminal')
    return item, summary


def prepare():
    if any((STUDY / x).exists() for x in ('protocol.json', 'inputs', 'ready.json', 'attempt.json', 'budget.json',
                                         'measurement', 'startup_identity.json', 'logs', 'build-cache')):
        raise ValueError('first preparation refuses existing inputs or runtime work')
    reg, summary = registration()  # Do not inspect any Z runtime input before this root authorization.
    import numpy as np
    from numerical import check

    from src.genome import Layout

    zp = read(Z / 'protocol.json')
    for key, base in (('file_pins', Z), ('production_pins', ROOT)):
        for name, digest in zp[key].items():
            if sha(base / name) != digest:
                raise ValueError('frozen Z source or input differs: ' + name)
    check(zp['numerical_identity'])  # Runtime metadata only, no compile/goldens.
    endpoints = read(Z / 'confirmation/endpoints.json')
    if (endpoints['labels'] != LABELS or endpoints['protocol_sha256'] != Z_PROTOCOL
            or endpoints['numerical_identity'] != zp['expected_numerical_identity']):
        raise ValueError('exact final six-role Z binding required')
    with np.load(Z / 'confirmation/genotypes.npz', allow_pickle=False) as table:
        genomes, labels = table['genomes'], table['labels']
    if genomes.shape != (6, 875) or genomes.dtype != np.float32 or labels.tolist() != LABELS or not np.isfinite(genomes).all():
        raise ValueError('six exact unchanged ABI4 genotypes required')
    raw_pins = {label: hashlib.sha256(g.tobytes()).hexdigest() for label, g in zip(LABELS, genomes)}
    if raw_pins != endpoints['genotype_sha256']:
        raise ValueError('Z six-role array differs from terminal endpoint binding')
    index, rates, cost_pins = read(Z / 'confirmation/row_index.json'), {}, {}
    for i, label in enumerate(LABELS):
        relative = f'blink/row_{i:04d}.npz'
        path = Z / 'confirmation' / relative
        if sha(path) != index[relative]['sha256']:
            raise ValueError('terminal Z cost row changed')
        with np.load(path, allow_pickle=False) as row:
            identity = json.loads(str(row['identity']))
            if (row['ledger'].shape != (512, 58) or int(row['genome_index']) != i
                    or identity['role'] != label or identity['genome_sha256'] != raw_pins[label]
                    or identity['endpoints_sha256'] != sha(Z / 'confirmation/endpoints.json')
                    or row['seeds'].tolist() != zp['confirmation']['seeds']
                    or float(row['cpu_seconds']) != index[relative]['cpu_seconds']):
                raise ValueError('actual Z confirmation timing identity differs')
            rates[label] = float(row['cpu_seconds']) / 512
        cost_pins['confirmation/' + relative] = sha(path)
    projection = cost_projection(rates)
    if not projection['feasible']:
        raise ValueError('fixed AA scope fails conservative all-six-body cost check')
    reference = zp['reference_files'][0]
    _, original = Layout.load(Z / reference)
    if original.numpy().tobytes() != genomes[0].tobytes():
        raise ValueError('layout reference differs from original D90')
    copied = {name: name for name in ('protocol.json', 'budget.json', 'confirmation/endpoints.json',
                                     'confirmation/genotypes.npz', 'confirmation/row_index.json', 'confirmation/report.json')}
    copied.update({name: name for name in cost_pins})
    copied[reference] = 'layout_reference.json'
    cfg_path = zp['configs'][str(zp['runs'][0])]['path']
    copied[cfg_path] = 'evaluator.yaml'
    for source, target in copied.items():
        freeze(STUDY / 'inputs/Z' / target, (Z / source).read_bytes())
    freeze_json(STUDY / 'inputs/Z_summary.json', summary)
    freeze_json(STUDY / 'inputs/Z_cost_rows.json', {'source_pins': cost_pins, 'projection': projection})
    local = ['prepare.py', 'measure.py', 'run_budgeted.py', 'scoring.py', 'numerical.py', 'common.py',
             'test_preparation.py', 'README.md', 'PREREG.md', 'SCHEMA.md', 'registration.json', 'seed_audit.json']
    file_pins = {name: sha(STUDY / name) for name in local}
    file_pins.update({str(path.relative_to(STUDY)): sha(path) for path in sorted((STUDY / 'inputs').rglob('*')) if path.is_file()})
    settings = worlds()
    protocol = {'study': 'AA fixed-tissue blink lateral dependence', 'labels': LABELS, 'conditions': CONDITIONS,
        'seeds': reg['seeds'], 'T': 1024, 't_fork': 512, 't_open': 544, 'worlds': {k: asdict(v) for k, v in settings.items()},
        'unmodified_world': zp['world'], 'max_cpu_seconds': 1200, 'max_workers': 1, 'max_simulation_threads': 2,
        'planned_genome_lives': 2304, 'startup_validation_genome_lives': 2,
        'primary_pairs': [[4, 2], [5, 3]], 'start_pairs': [[2, 0], [3, 1]], 'cumulative_pairs': [[4, 0], [5, 1]],
        'genotypes_file': 'inputs/Z/confirmation/genotypes.npz', 'genotype_sha256': raw_pins,
        'layout_file': 'inputs/Z/layout_reference.json', 'config_file': 'inputs/Z/evaluator.yaml',
        'cost_projection': projection, 'numerical_identity': zp['numerical_identity'],
        'expected_numerical_identity': zp['expected_numerical_identity'],
        'file_pins': file_pins, 'production_pins': zp['production_pins'], 'registration_sha256': sha(STUDY / 'registration.json')}
    freeze_json(STUDY / 'protocol.json', protocol)
    print(json.dumps({'status': 'prepared_unreleased', 'protocol_sha256': sha(STUDY / 'protocol.json'),
                      'cost_projection': projection, 'simulations': 0, 'compilations': 0}, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--prepare', action='store_true')
    if parser.parse_args().prepare:
        prepare()
    else:
        print(json.dumps({'status': 'source_only_unregistered', 'genome_lives': 2304,
                          'startup_validation_genome_lives': 2, 'simulation_calls': 0}))
