"""Offline AL complete recorded-genetics and logged ordinary-selection audit; no lives or RNG draws."""
from __future__ import annotations

import argparse
import copy
import hashlib
import importlib.util
import json
import os
import sys
from pathlib import Path

os.environ.setdefault('ATEN_CPU_CAPABILITY', 'avx2')
sys.dont_write_bytecode = True

import numpy as np  # noqa: E402
import torch  # noqa: E402

HERE = Path(__file__).resolve().parent


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


def audit(study):
    study = Path(study).resolve()
    protocol = read(study / 'protocol.json')
    for name, digest in protocol['source_pins'].items():
        if sha(study / name) != digest:
            raise ValueError('pinned study source changed: ' + name)
    replay = load('AL_full_recorded_replay', study / 'native_replay.py')
    selected = load('AL_ordinary_selection', HERE / 'selection_replay.py')
    operations = replay.operations()
    layout, initial = replay.initial_population(study, protocol)
    from src.life import spec

    first = replay.first_cohort(study, protocol)
    if (study / 'first_cohort_replay.json').exists() and read(study / 'first_cohort_replay.json') != first:
        raise ValueError('saved first-cohort proof differs')
    results, artifacts = {}, {}
    for arm in ('persistent_control', 'balanced_mixture'):
        folder = study / 'runs' / arm
        cfg_path = study / protocol['configs'][arm]['path']
        selected.equal(sha(cfg_path), protocol['configs'][arm]['sha256'], 'registered configuration')
        cfg = selected.config_identity(cfg_path)
        selected.equal(cfg['seed'], protocol['native_seed'], 'native seed')
        for key, value in {'generations': 4, 'mu': 32, 'lam': 224, 'breeding': 'sex', 'n_mut': 2,
                           'dup_rate': 0., 'del_rate': 0., 'dup_split': False, 'recheck_k': 64,
                           'recheck_lives': 4, 'recheck_key': 'all', 'heldout_every': 4}.items():
            selected.equal(cfg['evolve'][key], value, 'ordinary search ' + key)
        selected.equal(cfg['life']['lives'], 4, 'initial life budget')
        selected.equal(cfg['life']['T'], 1024, 'duration')
        selected.equal(cfg['life']['T_choices'], None, 'fixed duration')
        selected.equal(cfg['logging']['lineage'], 'all', 'complete child records')
        expected_population = {'version': 1, **protocol['population_start'], 'source_pins': {
            name: sha(study / name) for name in ('population_loader.py', 'search.py')}}
        expected_selection = {'version': 1, 'arm': arm, 'worlds': protocol['selection_worlds'],
            'rule': 'gen indices even=pool odd=persistent; control and diagnostics=persistent',
            'source_pins': {'selection.py': sha(study / 'selection.py')}}
        selected.equal(cfg['population_start'], expected_population, 'loader configuration')
        selected.equal(cfg['retention_selection'], expected_selection, 'world-allocation configuration')
        saved = torch.load(folder / 'checkpoint.pt', map_location='cpu', weights_only=True)
        selected.equal(saved['format'], 1, 'checkpoint format')
        selected.equal(saved['config'], cfg, 'checkpoint configuration')
        selected.equal(selected.config_identity(folder / 'config.yaml'), cfg, 'native saved configuration')
        expected_identity = {**protocol['expected_numerical_identity'], 'population_start': expected_population,
                             'retention_selection': expected_selection}
        selected.equal(saved['identity'], expected_identity, 'extended numerical identity')
        selected.equal(read(folder / 'determinism.json'), expected_identity, 'native identity file')
        state = saved['state']
        for key, value in {'generation': 4, 'evals': 1024, 'rc_lives': 1024}.items():
            selected.equal(state[key], value, 'native checkpoint ' + key)
        logs = {}
        for name, metadata in saved['logs'].items():
            data = (folder / name).read_bytes()
            selected.equal(len(data), metadata['bytes'], 'complete log length')
            selected.equal(hashlib.sha256(data).hexdigest(), metadata['sha256'], 'complete log hash')
            logs[name] = [json.loads(line) for line in data.splitlines() if line.strip()]
        selected.equal(set(logs), {'curves.jsonl', 'lineage.jsonl', 'clones.jsonl'}, 'native log set')
        selected.equal(logs['clones.jsonl'], [], 'disabled clone lives')
        curves, lines = logs['curves.jsonl'], logs['lineage.jsonl']
        selected.equal(curves, state['curves'], 'checkpoint curve history')
        selected.equal([row['gen'] for row in curves], list(range(4)), 'four generations')
        selected.equal([row['gen'] for row in curves if 'valid' in row], [0, 3], 'validation schedule')
        view_lines, view_curves = copy.deepcopy(lines), copy.deepcopy(curves)
        for row in [*view_lines[1:], *view_curves]:
            if 'T' in row:
                selected.equal(row['T'], 1024, 'optional duration')
            row['T'] = 1024
        selection = selected.audit_lineage(view_lines, view_curves, state, protocol['native_seed'], spec)
        genetics = operations.replay_genetics(lines, state, layout, initial[0], False, initial_population=initial)
        public = read(folder / 'population.json')
        final = torch.stack([layout.from_dict(row) for row in public['genomes']])
        if not operations.same(final.numpy(), state['population'].numpy()):
            raise ValueError('public final population differs from reconstructed checkpoint')
        for key in ('ids', 'breeds', 'origins', 'fitness'):
            selected.equal(public[key], state[key].tolist(), 'public population ' + key)
        _, best = type(layout).load(folder / 'best_genome.json')
        if not operations.same(best.numpy(), final[0].numpy()):
            raise ValueError('endpoint is not reconstructed final rank zero')
        if any(not np.isfinite(row[key]) or row[key] != 0 for row in curves
               for key in ('pop_invalid', 'pop_mismatch', 'recheck_invalid')):
            raise ValueError('invalid or mismatch in native search')
        guard_counts = [row['pop_guard'] * 1024 for row in curves]
        if any(not np.isfinite(x) or abs(x - round(x)) > 1e-8 for x in guard_counts):
            raise ValueError('invalid guard count aggregate')
        marker = read(folder / 'search_complete.json')
        for name, digest in marker['output_pins'].items():
            selected.equal(sha(folder / name), digest, 'completed native output ' + name)
            artifacts[str((folder / name).relative_to(study))] = digest
        results[arm] = {'status': 'passed', 'checkpoint_sha256': sha(folder / 'checkpoint.pt'),
            'selection': selection, 'genetic_replay': genetics, 'all_32_final_rows_bound': True,
            'final_rank_zero_id': int(state['ids'][0]), 'final_rank_zero_raw_sha256': replay.raw_sha(final[0].numpy()),
            'initial_evaluation_lives': 4096, 'recheck_lives': 1024,
            'initial_guard_counts_by_generation': [round(x) for x in guard_counts]}
    forbidden = [name for name in sys.modules if name in ('src.life.build', 'src.life.evaluate',
                  'src.checkpoint', 'src.evolve', 'src.run', 'src.life.reference')]
    if forbidden:
        raise ValueError('offline audit imported execution modules: ' + str(forbidden))
    return {'status': 'passed', 'protocol_sha256': sha(study / 'protocol.json'), 'runs': results,
        'first_cohort': first, 'input_artifact_pins': artifacts,
        'audit_source_sha256': sha(Path(__file__)), 'selection_helper_sha256': sha(HERE / 'selection_replay.py'),
        'simulated_lives': 0, 'random_draws': 0,
        'limits': ['Genetics reconstructs recorded operations; RNG draws are not repeated.',
                   'Selection verifies logged ordered shortlist and pooled top32 scores. Unrecorded parent base scores and exact tie permutations cannot be independently recovered.',
                   'Raw per-life selection ledgers are not retained; initial aggregate guards are reported without excluding those lives.',
                   'No ancestry statistic establishes functional circuitry or memory.']}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--study', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    if args.out.exists():
        raise ValueError('refuse to replace an audit receipt')
    result = audit(args.study)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2, allow_nan=False) + '\n')
    print(json.dumps({'status': result['status'], 'runs': list(result['runs']), 'simulated_lives': 0}))
