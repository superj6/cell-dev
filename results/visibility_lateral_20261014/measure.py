"""AA fixed six-role late-window lateral probe; dry-run default, no evolution or genotype generation."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from dataclasses import asdict
from pathlib import Path

os.environ.setdefault('ATEN_CPU_CAPABILITY', 'avx2')
sys.dont_write_bytecode = True
STUDY = Path(__file__).resolve().parent
ROOT = STUDY.parents[1]
sys.path.insert(0, str(ROOT))
LABELS = ['D90', 'L92', 'Y_D90', 'Y_L92', 'Z_D90', 'Z_L92']
CONDITIONS = ['normal', 'freeze', 'freeze+lateral_off']
PAIRS = [('primary', 4, 2), ('primary', 5, 3), ('start', 2, 0), ('start', 3, 1),
         ('cumulative', 4, 0), ('cumulative', 5, 1)]


def parent_check():
    from run_budgeted import process_identity, sha
    monitor = int(os.environ.get('CELLDEV_LATERAL_MONITOR_PID', '0'))
    if monitor <= 1 or os.getppid() != monitor:
        raise ValueError('measurement must be a direct child of its monitor')
    attempt = json.loads((STUDY / 'attempt.json').read_text())
    actual = process_identity(monitor)
    if (attempt['monitor']['pid'] != monitor or attempt['monitor']['start_ticks'] != actual['start_ticks']
            or attempt['ready_sha256'] != sha(STUDY / 'ready.json')):
        raise ValueError('monitor identity or release changed')
    budget = json.loads((STUDY / 'budget.json').read_text())
    if (budget.get('status') != 'running' or budget.get('phase') != 'measurement'
            or os.getpgrp() != os.getpid() or os.getsid(0) != os.getpid()
            or 'CELLDEV_THREADS_FILE' in os.environ):
        raise ValueError('measurement requires its active owned phase and fixed threads')


def contrasts(values):
    """Six fixed gain pairs, two interactions each, plus six within-genotype lesion losses."""
    import numpy as np
    arrays = {key: np.asarray(values[key], np.float64) for key in CONDITIONS}
    shape = arrays['normal'].shape
    if len(shape) != 2 or shape[0] != 6 or shape[1] < 2:
        raise ValueError('six paired genotype rows required')
    if any(value.shape != shape or not np.isfinite(value).all() for value in arrays.values()):
        raise ValueError('all eighteen finite paired arms required')
    raw = {}
    for family, i, j in PAIRS:
        prefix = family + '__' + LABELS[i] + '_minus_' + LABELS[j]
        gain = {key: value[i] - value[j] for key, value in arrays.items()}
        for key, value in gain.items():
            raw[prefix + '__gain__' + key] = value
        raw[prefix + '__added_lateral_dependence'] = gain['freeze'] - gain['freeze+lateral_off']
        raw[prefix + '__gain_lost_under_freeze'] = gain['normal'] - gain['freeze']
    for i, label in enumerate(LABELS):
        raw[label + '__frozen_lateral_loss'] = arrays['freeze'][i] - arrays['freeze+lateral_off'][i]
    return raw


def validate_frozen(rows):
    """E/H interval checks: no whole-life census equation; preserve every valid fitness row."""
    import numpy as np

    from src.life import spec
    terminal = spec.STATUS['extinct'] | spec.STATUS['guard_cells'] | spec.STATUS['guard_events']
    invalid = spec.STATUS['capacity'] | spec.STATUS['ledger_mismatch']
    coverage = []
    for i, label in enumerate(LABELS):
        arms = [rows[key][i] for key in CONDITIONS[1:]]
        for row in arms:
            if np.any(row['status'].astype(np.int64) & invalid):
                raise ValueError('invalid implementation status in frozen tissue')
            if (any(np.any(row[key] != 0) for key in ('births', 'deaths', 'kills', 'claims', 'rejects', 'rejects_wall'))
                    or np.any(row['last_birth'] >= 544)):
                raise ValueError('frozen structure changed in measured interval')
        complete = np.logical_and.reduce([(row['status'].astype(np.int64) & terminal) == 0 for row in arms])
        coverage.append({'label': label, 'complete_paired_lives': int(complete.sum()),
                         'excluded_from_structural_equality_only': int(len(complete) - complete.sum())})
        for row in arms:
            if np.any(row['t_end'][complete] != 1024):
                raise ValueError('unflagged complete frozen life ended early')
            for key in ('n_end', 'n_S_end', 'n_M_end', 'n_H_end'):
                if not np.array_equal(arms[0][key][complete], row[key][complete]):
                    raise ValueError('frozen pair has different terminal composition')
            for live, count in (('live_time', 'n_end'), ('live_S', 'n_S_end'),
                                ('live_M', 'n_M_end'), ('live_H', 'n_H_end')):
                if not np.allclose(row[live][complete], 480 * row[count][complete], rtol=1e-10, atol=1e-8):
                    raise ValueError('frozen cell-time does not match constant composition')
    return {'coverage': coverage, 'window': [544, 1024], 'all_fitness_rows_retained': True,
            'limitation': 'Within-genotype composition equality does not match architecture between genomes.'}


def report_values(rows):
    """Named fields plus additive terms; path and terminal body metrics are explicitly whole-life."""
    import numpy as np

    from src.life import spec
    metrics = ('F', 'F_kernel', 'captures', 'low_light_captures', 'clicks', 'misses', 'spikes', 'kappa_sum',
               'contact_events', 'rec_gain', 'income', 'cost', 'guard_charge', 'extinct_charge', 'live_time',
               'n_end', 'n_S_end', 'n_M_end', 'n_H_end', 'last_birth', 'path')
    output = {key: {c: np.stack([r[key] for r in rows[c]]) for c in CONDITIONS} for key in metrics}
    output['bright_captures'] = {c: output['captures'][c] - output['low_light_captures'][c] for c in CONDITIONS}
    for key in ('capture_income', 'ordinary_cost_saving', 'guard_charge_saving', 'extinction_charge_saving'):
        output[key] = {}
    from prepare import worlds
    settings = worlds()
    for condition in CONDITIONS:
        ledger = np.stack([np.stack([r[k] for k in spec.V4.LEDGER], axis=1) for r in rows[condition]])
        cost = spec.V4.column_cost(ledger, settings[condition])
        output['capture_income'][condition] = output['income'][condition] / 480
        output['ordinary_cost_saving'][condition] = -cost / 480
        output['guard_charge_saving'][condition] = -output['guard_charge'][condition] / 480
        output['extinction_charge_saving'][condition] = -output['extinct_charge'][condition]
        terms = sum(output[key][condition] for key in ('capture_income', 'ordinary_cost_saving',
                                                     'guard_charge_saving', 'extinction_charge_saving'))
        if not np.allclose(terms, output['F'][condition], rtol=0, atol=1e-9):
            raise ValueError('production fitness decomposition differs')
    return output


def measure():
    from run_budgeted import check_protocol, check_ready, save, sha
    protocol, ready = check_protocol(), check_ready()
    parent_check()
    from numerical import check
    check(protocol['numerical_identity'])
    if (STUDY / 'measurement').exists() or (STUDY / 'startup_identity.json').exists():
        raise ValueError('first attempt refuses existing measurement/startup artifacts')
    import numpy as np
    from omegaconf import OmegaConf
    from prepare import worlds
    from scoring import COLS, RowStore, atomic_npz

    from scripts.taskvar_gates import paired
    from src.checkpoint import numerical_identity
    from src.genome import Layout
    from src.life.evaluate import LifeEvaluator

    identity = numerical_identity()  # Exactly one full/fast ABI3 seed11 T200 pair in the entire worker.
    save(STUDY / 'startup_identity.json', {'identity': identity, 'protocol_sha256': sha(STUDY / 'protocol.json'),
        'startup_validation_genome_lives': 2, 'comparison': 'complete equality to pinned completed Z identity'})
    if identity != protocol['expected_numerical_identity']:
        raise ValueError('numerical identity differs from complete Z')
    with np.load(STUDY / protocol['genotypes_file'], allow_pickle=False) as data:
        genomes, labels = data['genomes'], data['labels'].tolist()
    if labels != LABELS or genomes.shape != (6, 875) or genomes.dtype != np.float32 or not np.isfinite(genomes).all():
        raise ValueError('six fixed ABI4 rows required')
    raw = {label: hashlib.sha256(g.tobytes()).hexdigest() for label, g in zip(LABELS, genomes)}
    if raw != protocol['genotype_sha256']:
        raise ValueError('fixed six-role raw genotype binding differs')
    layout, _ = Layout.load(STUDY / protocol['layout_file'])
    evaluator = LifeEvaluator(OmegaConf.load(STUDY / protocol['config_file']), layout)
    if (evaluator.abi.version != 4 or not evaluator.extinct_charge or evaluator.has_envelope
            or asdict(evaluator.world()) != protocol['unmodified_world']):
        raise ValueError('retained Z production scorer differs')
    settings = worlds()
    if {k: asdict(v) for k, v in settings.items()} != protocol['worlds']:
        raise ValueError('fixed intervention world differs')
    seed_list, out = protocol['seeds'], STUDY / 'measurement'
    store = RowStore(out, genomes, settings['normal'], evaluator,
                     {'protocol_sha256': sha(STUDY / 'protocol.json'),
                      'genotypes_sha256': sha(STUDY / protocol['genotypes_file'])})
    rows = {}
    startup_sha = sha(STUDY / 'startup_identity.json')
    for condition in CONDITIONS:
        store.world, rows[condition] = settings[condition], []
        for i, label in enumerate(LABELS):
            parent_check()
            if check_protocol() != protocol or check_ready() != ready or sha(STUDY / 'startup_identity.json') != startup_sha:
                raise ValueError('protocol, source, fixed input, startup or release changed')
            store.identity['role'], store.identity['condition'] = label, condition
            rows[condition].append(store.row(condition, i, seed_list))
        atomic_npz(out / condition / 'scores.npz', seeds=np.asarray(seed_list, np.uint64), genome_indices=np.arange(6),
                   **{key: np.stack([r[key] for r in rows[condition]]) for key in COLS})
    structure = validate_frozen(rows)
    values = report_values(rows)
    vectors = {metric: contrasts(value) for metric, value in values.items()}
    atomic_npz(out / 'paired.npz', **{metric + '___' + name: vector for metric, group in vectors.items()
                                    for name, vector in group.items()})
    result = {'status': 'complete', 'report_only': True, 'genome_lives': 2304, 'paired_seeds': 128,
        'startup_validation_genome_lives': 2, 'protocol_sha256': sha(STUDY / 'protocol.json'),
        'startup_identity_sha256': startup_sha, 'row_cpu_seconds': store.cpu_seconds,
        'labels': LABELS, 'conditions': CONDITIONS, 'frozen_checks': structure,
        'contrasts': {metric: {name: paired(v, np.zeros(128)) for name, v in group.items()}
                      for metric, group in vectors.items()},
        'absolute': {metric: {c: {LABELS[i]: paired(v[i], np.zeros(128)) for i in range(6)}
                             for c, v in group.items()} for metric, group in values.items()},
        'limitations': ['Within-genotype signaling contribution; architectures differ between evolved genomes.',
            'Freeze stops ongoing gene, phenotype and weight updates as well as new structural decisions.',
            'Path, last_birth and terminal census are whole-life diagnostics; interval costs/captures use544..1024.',
            'No memory, adult maturity, matched-architecture or improved-computation claim follows from a lesion deficit.',
            'Valid extinction/guards retain production penalties; unresolved effects are not equivalence.',
            'All six roles remain fixed regardless of prior outcome signs; life SE is not search-replicate uncertainty.']}
    save(out / 'report.json', result)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--measure-child', action='store_true')
    if parser.parse_args().measure_child:
        measure()
    else:
        print(json.dumps({'status': 'dry_run', 'labels': LABELS, 'conditions': CONDITIONS,
                          'genome_lives': 2304, 'startup_validation_genome_lives': 2, 'simulation_calls': 0}))
