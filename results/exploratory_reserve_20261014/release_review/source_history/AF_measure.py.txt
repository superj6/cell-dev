"""AF four-role ABI3 confirmation after two complete native searches; dry-run default."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import sys
from dataclasses import asdict
from pathlib import Path

os.environ.setdefault('ATEN_CPU_CAPABILITY', 'avx2')
sys.dont_write_bytecode = True
STUDY = Path(__file__).resolve().parent
ROOT = STUDY.parents[1]
sys.path.insert(0, str(ROOT))
LABELS = ['AE_D90', 'AE_L92', 'AF_D90', 'AF_L92']


def validate_search_state(state, generations=4):
    """Retain U's complete-generation and production invalid/mismatch checks."""
    if state['generation'] != generations:
        raise ValueError('refuse incomplete search endpoint')
    curves = state['curves']
    if [row['gen'] for row in curves] != list(range(generations)):
        raise ValueError('checkpoint lacks complete ordered search history')
    keys = ('pop_invalid', 'pop_mismatch', 'recheck_invalid')
    if any(not math.isfinite(float(row[key])) or float(row[key]) != 0 for row in curves for key in keys):
        raise ValueError('invalid or mismatched search lives block inference')
    return {key: max(float(row[key]) for row in curves) for key in keys}


def parent_check():
    """Confirmation is a live child in this first attempt's owned process group."""
    from run_budgeted import process_identity, sha
    monitor = int(os.environ.get('CELLDEV_CONTINUATION_MONITOR_PID', '0'))
    if monitor <= 1 or os.getppid() != monitor:
        raise ValueError('confirmation must be a child of its monitor')
    attempt = json.loads((STUDY / 'attempt.json').read_text())
    actual = process_identity(monitor)
    if (attempt['monitor']['pid'] != monitor or attempt['monitor']['start_ticks'] != actual['start_ticks']
            or attempt['ready_sha256'] != sha(STUDY / 'ready.json')):
        raise ValueError('monitor identity or release changed')
    budget = json.loads((STUDY / 'budget.json').read_text())
    if (budget.get('status') != 'running' or budget.get('phase') != 'confirmation'
            or os.getpgrp() != os.getpid() or os.getsid(0) != os.getpid()
            or 'CELLDEV_THREADS_FILE' in os.environ):
        raise ValueError('confirmation requires its active owned phase and fixed threads')


def confirm_endpoints():
    from run_budgeted import check_protocol, check_ready, save, sha
    protocol, ready = check_protocol(), check_ready()
    parent_check()
    from numerical import check
    check(protocol['numerical_identity'])
    out = STUDY / 'confirmation'
    if out.exists():
        raise ValueError('first attempt refuses previous confirmation artifacts')

    import numpy as np
    from omegaconf import OmegaConf
    from scoring import COLS, atomic_npz, comparison, score_row

    from scripts.taskvar_gates import paired
    from src import checkpoint
    from src.genome import Layout
    from src.life import spec
    from src.life.evaluate import LifeEvaluator

    identity = checkpoint.numerical_identity()  # Exactly one full/fast ABI3 T200 golden pair here.
    if identity != protocol['expected_numerical_identity']:
        raise ValueError('confirmation numerical identity differs from completed AE')
    seeds, runs = protocol['confirmation']['seeds'], protocol['runs']
    paths = [STUDY / name for name in protocol['reference_files']]
    if len(paths) != 2 or protocol['confirmation']['labels'] != LABELS:
        raise ValueError('exact AE starts and final endpoints required')
    endpoint_records = {}
    for seed in runs:
        folder = STUDY / f'runs/s{seed}'
        cfg = OmegaConf.load(STUDY / protocol['configs'][str(seed)]['path'])
        path = folder / 'checkpoint.pt'
        saved = checkpoint.load(path)
        checkpoint.validate(saved, cfg, identity)  # Reuse the already captured identity; no extra goldens.
        health = validate_search_state(saved['state'])
        log_pins = {}
        for name, metadata in saved['logs'].items():
            data = (folder / name).read_bytes()
            if len(data) < metadata['bytes'] or hashlib.sha256(data[:metadata['bytes']]).hexdigest() != metadata['sha256']:
                raise ValueError('native checkpoint log prefix differs')
            log_pins[name] = sha(folder / name)
        selected = folder / 'best_genome.json'
        _, genome = Layout.load(selected)
        if genome.numpy().tobytes() != saved['state']['population'][0].numpy().tobytes():
            raise ValueError('endpoint differs from final production population rank0')
        paths.append(selected)
        endpoint_records[str(seed)] = {'checkpoint_sha256': sha(path), 'genome_file_sha256': sha(selected),
            'genome_raw_sha256': hashlib.sha256(genome.numpy().tobytes()).hexdigest(),
            'determinism_sha256': sha(folder / 'determinism.json'), 'log_pins': log_pins,
            'generation': 4, 'rank': 0, 'search_health': health}
        if json.loads((folder / 'determinism.json').read_text()) != identity:
            raise ValueError('search startup numerical identity differs')
    loaded = [Layout.load(path) for path in paths]
    layout = loaded[0][0]
    if any(other.dims != layout.dims for other, _ in loaded):
        raise ValueError('genotype layouts differ')
    genomes = np.stack([genome.numpy() for _, genome in loaded])
    if genomes.dtype != np.float32 or genomes.shape != (4, 875) or not np.isfinite(genomes).all():
        raise ValueError('four fixed ABI3 genotypes required')
    for i, seed in enumerate(runs):
        if hashlib.sha256(genomes[i].tobytes()).hexdigest() != protocol['founder_mapping'][str(seed)]['raw_sha256']:
            raise ValueError('fixed AE start differs')
    world = spec.World(**protocol['world'])
    from world_contract import check_world
    check_world(asdict(world), protocol['world'])
    cfg = OmegaConf.load(STUDY / protocol['configs'][str(runs[0])]['path'])
    evaluator = LifeEvaluator(cfg, layout)
    if evaluator.abi.version != 3 or asdict(evaluator.world()) != asdict(world) or evaluator.has_envelope:
        raise ValueError('explicit ABI3 production scorer/world required')
    manifest = {'format': 1, 'labels': LABELS, 'seeds': seeds,
        'genotype_sha256': {label: hashlib.sha256(genome.tobytes()).hexdigest() for label, genome in zip(LABELS, genomes)},
        'endpoints': endpoint_records, 'protocol_sha256': sha(STUDY / 'protocol.json'),
        'numerical_identity': identity, 'ready': ready, 'world': protocol['world'],
        'selection': 'Both complete generation4 final population rank0 endpoints fixed together before confirmation.'}
    save(out / 'endpoints.json', manifest)
    atomic_npz(out / 'genotypes.npz', genomes=genomes, labels=np.asarray(LABELS))
    manifest_sha = sha(out / 'endpoints.json')
    genome_file_sha = sha(out / 'genotypes.npz')
    rows, index = {}, {}
    for i in range(4):
        parent_check()
        if check_protocol() != protocol or check_ready() != ready:
            raise ValueError('release or protocol changed during confirmation')
        if sha(out / 'endpoints.json') != manifest_sha or sha(out / 'genotypes.npz') != genome_file_sha:
            raise ValueError('frozen four-role endpoint identity changed')
        rows[i] = score_row(out / 'persistent', i, genomes, world, seeds, evaluator,
                            identity={'protocol_sha256': manifest['protocol_sha256'], 'stage': 'confirmation',
                                      'endpoints_sha256': manifest_sha, 'role': LABELS[i]})
        path = out / 'persistent' / f'row_{i:04d}.npz'
        index[str(path.relative_to(out))] = {'sha256': sha(path), 'cpu_seconds': float(rows[i]['cpu_seconds'])}
        save(out / 'row_index.json', index)
    atomic_npz(out / 'persistent/scores.npz', seeds=np.asarray(seeds, dtype=np.uint64), genome_indices=np.arange(4),
               **{key: np.stack([rows[i][key] for i in range(4)]) for key in COLS})
    metrics = ('F', 'F_kernel', 'captures', 'clicks', 'misses', 'n_end', 'n_H_end',
               'live_time', 'path', 'spikes', 'packets', 'income', 'cost', 'guard_charge', 'extinct_charge')
    report = {'status': 'complete', 'report_only': True, 'genome_lives': 2048, 'paired_seeds': 512,
        'confirmation_startup_validation_lives': 2, 'protocol_sha256': manifest['protocol_sha256'],
        'endpoints_sha256': manifest_sha, 'genotypes_sha256': genome_file_sha,
        'row_cpu_seconds': sum(float(row['cpu_seconds']) for row in rows.values()),
        'absolute': {LABELS[i]: {key: paired(rows[i][key], np.zeros(len(seeds))) for key in metrics} for i in range(4)},
        'limitations': ['Life-level paired uncertainty concerns fixed genotypes, not reliability across evolutionary runs.',
            'Lower costs can improve production fitness without better capture behavior; retain the full decomposition.',
            'Capture gains do not isolate prediction, temporal memory or a distributed mechanism.',
            'Both fixed AE starts are retained regardless of their previous fresh confirmation sign.',
            'No partial search, missing arm or stopped confirmation supports a complete-study inference.']}
    for name in ('primary',):
        report[name] = {LABELS[a]: comparison(rows[a], rows[b], world) for a, b in protocol['confirmation'][name + '_pairs']}
    save(out / 'report.json', report)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--confirm-child', action='store_true')
    args = parser.parse_args()
    if args.confirm_child:
        confirm_endpoints()
    else:
        print(json.dumps({'status': 'dry_run', 'genome_lives': 2048, 'startup_validation_lives': 2,
                          'roles': LABELS, 'simulation_calls': 0}))


if __name__ == '__main__':
    main()
