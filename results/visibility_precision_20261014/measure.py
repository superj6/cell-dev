"""AB six-role ABI4 confirmation after four complete native policy searches; dry-run default."""
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
LABELS = ['Z_D90', 'Z_L92', 'depth_D90', 'precision_D90', 'depth_L92', 'precision_L92']


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


def first_cohort(path):
    """Recorded genetic instructions only; exclude fitness, shortlist and survivor outcomes."""
    rows = [json.loads(line) for line in path.read_text().splitlines()]
    founders = [row for row in rows if row.get('event') == 'founders']
    generations = [row for row in rows if row.get('gen') == 0]
    if len(founders) != 1 or len(generations) != 1:
        raise ValueError('unique native founders and first generation required')
    row = generations[0]
    children = [{key: child[key] for key in ('id', 'pa', 'pb', 'mask', 'ops')} for child in row['children']]
    if [child['id'] for child in children] != list(range(32, 256)):
        raise ValueError('complete ordered first 224 offspring required')
    return {'founder_ids': founders[0]['ids'], 'copies': founders[0]['copies'], 'children': children}


def check_matched_first_cohorts(protocol):
    """Fail before confirmation if actual genetic instructions differ within a fixed policy pair."""
    initial = json.loads((STUDY / 'initialization.json').read_text())
    evidence = {}
    for parent in ('D90', 'L92'):
        pair = [first_cohort(STUDY / 'runs' / (parent + '_' + policy) / 'lineage.jsonl')
                for policy in ('depth', 'precision')]
        if pair[0] != pair[1] or pair[0]['founder_ids'] != [0]:
            raise ValueError('paired policies did not share the first genetic cohort')
        prepared = initial['backgrounds'][parent]
        if pair[0]['copies'] != prepared['copies']:
            raise ValueError('actual native fill differs from prepared matched population')
        for policy in ('depth', 'precision'):
            run = parent + '_' + policy
            if (initial['runs'][run] != parent
                    or protocol['run_settings'][run]['seed'] != protocol['paired_native_seeds'][parent]):
                raise ValueError('paired initialization/RNG mapping differs')
        evidence[parent] = {'population_raw_sha256': prepared['population_raw_sha256'],
            'recorded_genetics_sha256': hashlib.sha256(json.dumps(pair[0], sort_keys=True).encode()).hexdigest(),
            'candidate_count': 256, 'offspring_count': 224,
            'limitation': 'Independent final audit also reconstructs raw child bytes from the pinned genetic operations.'}
    return evidence


def parent_check():
    """Confirmation is a live child in this first attempt's owned process group."""
    from run_budgeted import process_identity, sha
    monitor = int(os.environ.get('CELLDEV_PRECISION_MONITOR_PID', '0'))
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
        raise ValueError('confirmation numerical identity differs from completed Z')
    seeds, runs = protocol['confirmation']['seeds'], protocol['runs']
    paths = [STUDY / name for name in protocol['reference_files']]
    if len(paths) != 2 or protocol['confirmation']['labels'] != LABELS:
        raise ValueError('exact two Z starts and four fixed endpoints required')
    endpoint_records = {}
    for seed in runs:
        folder = STUDY / 'runs' / seed
        cfg = OmegaConf.load(STUDY / protocol['configs'][str(seed)]['path'])
        path = folder / 'checkpoint.pt'
        saved = checkpoint.load(path)
        checkpoint.validate(saved, cfg, identity)  # Reuse the already captured identity; no extra goldens.
        health = validate_search_state(saved['state'], protocol['run_settings'][seed]['generations'])
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
            'generation': protocol['run_settings'][seed]['generations'], 'rank': 0, 'search_health': health}
        if json.loads((folder / 'determinism.json').read_text()) != identity:
            raise ValueError('search startup numerical identity differs')
    cohort_proof = check_matched_first_cohorts(protocol)
    loaded = [Layout.load(path) for path in paths]
    layout = loaded[0][0]
    if any(other.dims != layout.dims for other, _ in loaded):
        raise ValueError('genotype layouts differ')
    genomes = np.stack([genome.numpy() for _, genome in loaded])
    if genomes.dtype != np.float32 or genomes.shape != (6, 875) or not np.isfinite(genomes).all():
        raise ValueError('six fixed ABI4 genotypes required')
    for i, parent in enumerate(('D90', 'L92')):
        if hashlib.sha256(genomes[i].tobytes()).hexdigest() != protocol['founder_mapping'][parent]['raw_sha256']:
            raise ValueError('fixed Z start differs')
    world = spec.world('catch_speck_blink20_20_l4', T=1024)
    if asdict(world) != protocol['world']:
        raise ValueError('exact approved irregular blink world required')
    cfg = OmegaConf.load(STUDY / protocol['configs'][str(runs[0])]['path'])
    evaluator = LifeEvaluator(cfg, layout)
    if evaluator.abi.version != 4 or asdict(evaluator.world()) != protocol['world'] or evaluator.has_envelope:
        raise ValueError('explicit ABI4 production scorer/world required')
    manifest = {'format': 1, 'labels': LABELS, 'seeds': seeds,
        'genotype_sha256': {label: hashlib.sha256(genome.tobytes()).hexdigest() for label, genome in zip(LABELS, genomes)},
        'endpoints': endpoint_records, 'protocol_sha256': sha(STUDY / 'protocol.json'),
        'numerical_identity': identity, 'ready': ready, 'world': asdict(world),
        'matched_first_cohort': cohort_proof,
        'selection': 'All four complete final population rank0 endpoints fixed together before confirmation.'}
    save(out / 'endpoints.json', manifest)
    atomic_npz(out / 'genotypes.npz', genomes=genomes, labels=np.asarray(LABELS))
    manifest_sha = sha(out / 'endpoints.json')
    genome_file_sha = sha(out / 'genotypes.npz')
    rows, index = {}, {}
    for i in range(6):
        parent_check()
        if check_protocol() != protocol or check_ready() != ready:
            raise ValueError('release or protocol changed during confirmation')
        if sha(out / 'endpoints.json') != manifest_sha or sha(out / 'genotypes.npz') != genome_file_sha:
            raise ValueError('frozen six-role endpoint identity changed')
        rows[i] = score_row(out / 'blink', i, genomes, world, seeds, evaluator,
                            identity={'protocol_sha256': manifest['protocol_sha256'], 'stage': 'confirmation',
                                      'endpoints_sha256': manifest_sha, 'role': LABELS[i]})
        path = out / 'blink' / f'row_{i:04d}.npz'
        index[str(path.relative_to(out))] = {'sha256': sha(path), 'cpu_seconds': float(rows[i]['cpu_seconds'])}
        save(out / 'row_index.json', index)
    atomic_npz(out / 'blink/scores.npz', seeds=np.asarray(seeds, dtype=np.uint64), genome_indices=np.arange(6),
               **{key: np.stack([rows[i][key] for i in range(6)]) for key in COLS})
    metrics = ('F', 'F_kernel', 'captures', 'low_light_captures', 'clicks', 'misses', 'n_end', 'n_H_end',
               'live_time', 'path', 'spikes', 'packets', 'income', 'cost', 'guard_charge', 'extinct_charge')
    report = {'status': 'complete', 'report_only': True, 'genome_lives': 3072, 'paired_seeds': 512,
        'confirmation_startup_validation_lives': 2, 'protocol_sha256': manifest['protocol_sha256'],
        'endpoints_sha256': manifest_sha, 'genotypes_sha256': genome_file_sha,
        'row_cpu_seconds': sum(float(row['cpu_seconds']) for row in rows.values()),
        'absolute': {LABELS[i]: {key: paired(rows[i][key], np.zeros(len(seeds))) for key in metrics} for i in range(6)},
        'limitations': ['Life-level paired uncertainty concerns fixed genotypes, not reliability across evolutionary runs.',
            'Lower costs can improve production fitness without better capture behavior; retain the full decomposition.',
            'Low-light captures do not isolate retained information from delayed cues, coasting or other dynamics.',
            'Both fixed Z starts are retained regardless of AA or earlier confirmation signs.',
            'Policies match selection-life counts, not CPU or evolutionary depth; only two background/run pairs.',
            'No partial search, missing arm or stopped confirmation supports a complete-study inference.']}
    for name in ('primary', 'gain'):
        report[name] = {LABELS[a]: comparison(rows[a], rows[b], world) for a, b in protocol['confirmation'][name + '_pairs']}
    save(out / 'report.json', report)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--confirm-child', action='store_true')
    args = parser.parse_args()
    if args.confirm_child:
        confirm_endpoints()
    else:
        print(json.dumps({'status': 'dry_run', 'genome_lives': 3072, 'startup_validation_lives': 2,
                          'roles': LABELS, 'simulation_calls': 0}))


if __name__ == '__main__':
    main()
