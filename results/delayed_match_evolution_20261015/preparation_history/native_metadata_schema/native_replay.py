"""Offline ABI5 mixed-run genetics replay from saved parents and recorded operations only."""
from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
from pathlib import Path

import numpy as np
import torch

HERE = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def raw_sha(value):
    return hashlib.sha256(np.asarray(value).tobytes()).hexdigest()


def operations():
    path = HERE / 'replay_ops.py'
    spec = importlib.util.spec_from_file_location('matching_recorded_ops', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def definitions(base, protocol):
    """Use packaged definitions when present; bind the exact actually imported source bytes."""
    root = base / 'production' if (base / 'production/src/genome.py').exists() else base.parents[1]
    sys.path.insert(0, str(root))
    from src.genome import Layout

    for name, module in tuple(sys.modules.items()):
        if name in ('src', 'src.genome', 'src.lattice', 'src.life', 'src.life.spec'):
            path = Path(module.__file__).resolve()
            if not path.is_relative_to(root.resolve()):
                raise ValueError('loaded genome definition is outside the pinned source root')
            if sha(path) != protocol['production_pins'][str(path.relative_to(root.resolve()))]:
                raise ValueError('loaded genome definition source changed')
    return Layout


def initial_population(base, protocol):
    Layout = definitions(base, protocol)
    record = protocol['population_start']
    path = base / record['population_file']
    if sha(path) != record['file_sha256']:
        raise ValueError('imported population file changed')
    saved = json.loads(path.read_text())
    layout, reference = Layout.load(base / protocol['reference']['path'])
    table = torch.stack([layout.from_dict(row) for row in saved['genomes']])
    hashes = [raw_sha(row.numpy()) for row in table]
    if (saved['dims'] != layout.dims.__dict__ or table.shape != (32, 875)
            or table.dtype != torch.float32 or not bool(torch.isfinite(table).all())
            or saved['ids'] != record['old_ids'] or len(set(saved['ids'])) != 32
            or record['new_ids'] != list(range(32)) or record['shape'] != [32, 875]
            or raw_sha(table.numpy()) != record['population_raw_sha256'] or hashes != record['row_sha256']
            or raw_sha(reference.numpy()) != hashes[0]
            or record['old_to_new'] != [{'old_id': old, 'new_id': i, 'row': i, 'raw_sha256': hashes[i]}
                                        for i, old in enumerate(saved['ids'])]):
        raise ValueError('imported ordered population/reference/crosswalk differs')
    return layout, table


def replay_first(layout, initial, lines):
    """Reconstruct the original 32 parents plus all 224 recorded first-generation children."""
    ops = operations()
    if (lines[0]['event'] != 'founders' or lines[0]['sampled'] != 0
            or lines[0]['ids'] != list(range(32)) or lines[0]['copies'] != []
            or lines[1]['gen'] != 0):
        raise ValueError('exact imported founders and first generation required')
    children = lines[1]['children']
    if [child['id'] for child in children] != list(range(32, 256)):
        raise ValueError('all 224 ordered first offspring required')
    reconstructed, signature = [row.clone() for row in initial], []
    for child in children:
        pa, pb, mask = child['pa'], child['pb'], child['mask']
        if (pa not in range(32) or pb not in range(32)
                or not isinstance(mask, int) or mask < 0 or mask >= 1 << layout.n_units
                or set(child['ops']) != {'mut'}):
            raise ValueError('invalid recorded first-cohort parent/crossover/operator')
        units = torch.tensor([(mask >> i) & 1 for i in range(layout.n_units)], dtype=torch.bool)
        mixed = layout.silence(torch.where(units[layout.unit_of], initial[pa], initial[pb]))
        reconstructed.append(ops.point_mutation(layout, mixed, child['ops']))
        signature.append({key: child[key] for key in ('id', 'pa', 'pb', 'mask', 'ops')})
    table = torch.stack(reconstructed).numpy()
    return {'candidate_raw_sha256': raw_sha(table),
            'candidate_row_sha256': [raw_sha(row) for row in table],
            'genetic_signature_sha256': hashlib.sha256(json.dumps(signature, sort_keys=True,
                separators=(',', ':'), allow_nan=False).encode()).hexdigest()}


def first_cohort(study, protocol):
    base = Path(study).resolve()
    for name in ('native_replay.py', 'replay_ops.py'):
        if sha(HERE / name) != protocol['source_pins'][name]:
            raise ValueError('recorded replay helper source changed')
    layout, initial = initial_population(base, protocol)
    runs = {}
    for arm in ('mixed',):
        folder = base / 'runs' / arm
        marker = json.loads((folder / 'search_complete.json').read_text())
        if (marker['status'] != 'complete' or marker['arm'] != arm
                or marker['protocol_sha256'] != sha(base / 'protocol.json')
                or sha(folder / 'lineage.jsonl') != marker['output_pins']['lineage.jsonl']):
            raise ValueError('completed native lineage binding differs')
        lines = [json.loads(line) for line in (folder / 'lineage.jsonl').read_text().splitlines()]
        runs[arm] = {**replay_first(layout, initial, lines), 'lineage_sha256': sha(folder / 'lineage.jsonl')}
    return {'status': 'passed', 'protocol_sha256': sha(base / 'protocol.json'),
            'initial_population_raw_sha256': raw_sha(initial.numpy()),
            'initial_row_sha256': [raw_sha(row.numpy()) for row in initial],
            'runs': runs, 'initial_rows': 32, 'offspring_per_arm': 224,
            'simulated_lives': 0, 'random_draws': 0,
            'limits': ['Reconstructs recorded operations; it does not repeat genetic RNG draws.',
                       'This one-run first-cohort check does not establish fitness or selection correctness.']}


def recorded_population(layout, initial, lines, state, generations):
    """Replay a complete recorded prefix, checking offspring IDs and retained row order."""
    if (lines[0].get('event') != 'founders' or lines[0].get('sampled') != 0
            or lines[0].get('ids') != list(range(32)) or lines[0].get('copies') != []
            or [row.get('gen') for row in lines[1:]] != list(range(generations))):
        raise ValueError('recorded founder/generation sequence differs')
    parents = list(range(32))
    for g, row in enumerate(lines[1:]):
        children = row['children']
        expected_ids = list(range(32 + 224*g, 32 + 224*(g+1)))
        if [c['id'] for c in children] != expected_ids:
            raise ValueError('recorded offspring IDs/order differ')
        candidates = set(parents) | set(expected_ids)
        survivors = row['survivors']
        if len(survivors) != 32 or len(set(survivors)) != 32 or not set(survivors) <= candidates:
            raise ValueError('recorded survivor IDs/order invalid')
        for child in children:
            if (child['pa'] not in parents or child['pb'] not in parents
                    or set(child['ops']) != {'mut'} or len(child['ops']['mut']) != 2
                    or child['kept'] != (child['id'] in survivors)):
                raise ValueError('recorded parent/operator/retention contract differs')
        parents = survivors
    if parents != state['ids'].tolist():
        raise ValueError('recorded terminal survivor order differs')
    result = operations().replay_genetics(lines, state, layout, initial[0], False,
                                          initial_population=initial)
    if (result['point_mutations_including_initial_copies'] != generations*224*2
            or result['duplication_events'] or result['deletion_events']):
        raise ValueError('recorded genetic operation counts differ')
    return {**result, 'offspring_replayed': generations*224,
            'all_32_rows_bound': True, 'population_raw_sha256': raw_sha(state['population'].numpy()),
            'row_sha256': [raw_sha(row.numpy()) for row in state['population']]}


def config_identity(path):
    """The native checkpoint's config projection, without importing execution code."""
    from omegaconf import OmegaConf

    value = OmegaConf.to_container(OmegaConf.load(path), resolve=True)
    value.pop('extends', None)
    value['logging'].pop('output_dir', None)
    value['logging'].pop('checkpoint_every', None)
    return value


def bound_logs(folder, saved, *, prefix=False):
    expected = {'curves.jsonl', 'lineage.jsonl', 'clones.jsonl'}
    if set(saved['logs']) != expected:
        raise ValueError('checkpoint log coverage differs')
    result = {}
    for name, pin in saved['logs'].items():
        if type(pin['bytes']) is not int or pin['bytes'] < 0:
            raise ValueError('invalid checkpoint log length')
        with (folder / name).open('rb') as stream:
            data = stream.read(pin['bytes']) if prefix else stream.read()
        if len(data) != pin['bytes'] or hashlib.sha256(data).hexdigest() != pin['sha256']:
            raise ValueError('checkpoint log bytes differ: ' + name)
        result[name] = [json.loads(row) for row in data.splitlines() if row.strip()]
    if result['clones.jsonl']:
        raise ValueError('unexpected clone evaluations')
    return result


def complete_replay(study, protocol=None):
    """Bind one complete search and reconstruct every final and generation-eight row."""
    base = Path(study).resolve()
    actual = json.loads((base / 'protocol.json').read_text())
    if protocol is not None and protocol != actual:
        raise ValueError('supplied protocol differs from saved protocol')
    protocol = actual
    expected_search = {'arms': ['mixed'], 'generations': 24, 'research_lives_per_arm': 61558,
                       'startup_lives_per_arm': 4, 'initial_lives': 8, 'recheck_lives': 8,
                       'parents': 32, 'offspring': 224}
    if protocol['search'] != expected_search:
        raise ValueError('registered single mixed search scope differs')
    for name in ('native_replay.py', 'replay_ops.py'):
        if sha(HERE / name) != protocol['source_pins'][name]:
            raise ValueError('recorded replay helper source changed')
    layout, initial = initial_population(base, protocol)
    folder = base / 'runs/mixed'
    marker = json.loads((folder / 'search_complete.json').read_text())
    for key, value in {'status': 'complete', 'arm': 'mixed', 'research_lives': 61558,
                       'startup_lives': 4, 'protocol_sha256': sha(base / 'protocol.json'),
                       'release_sha256': sha(base / 'release.json')}.items():
        if marker[key] != value:
            raise ValueError('completed search marker differs: ' + key)
    required = {'checkpoint.pt', 'config.yaml', 'determinism.json', 'curves.jsonl', 'lineage.jsonl',
                'population.json', 'best_genome.json', 'results.jsonl', 'search_startup.json',
                'generation8/checkpoint.pt', 'generation8/best_genome.json', 'generation8/snapshot.json'}
    if set(marker['output_pins']) != required:
        raise ValueError('completed search output coverage differs')
    for name, digest in marker['output_pins'].items():
        if sha(folder / name) != digest:
            raise ValueError('completed search output changed: ' + name)
    cfg_path = base / protocol['configs']['mixed']['path']
    if sha(cfg_path) != protocol['configs']['mixed']['sha256']:
        raise ValueError('registered configuration changed')
    cfg = config_identity(cfg_path)
    if config_identity(folder / 'config.yaml') != cfg:
        raise ValueError('native configuration differs')
    for key, value in {'generations': 24, 'mu': 32, 'lam': 224, 'breeding': 'sex', 'n_mut': 2,
                       'dup_rate': 0., 'del_rate': 0., 'dup_split': False, 'recheck_k': 64,
                       'recheck_lives': 8, 'recheck_key': 'all', 'heldout_every': 4}.items():
        if cfg['evolve'][key] != value:
            raise ValueError('ordinary search setting differs: ' + key)
    if (cfg['seed'] != protocol['native_seed'] or cfg['life']['abi'] != 5 or cfg['life']['T'] != 85.
            or cfg['life']['lives'] != 8 or cfg['life']['T_choices'] is not None
            or not cfg['life']['extinct_charge'] or cfg['logging']['lineage'] != 'all'):
        raise ValueError('mixed search seed/base evaluator differs')
    for name in ('population_loader.py', 'selection.py', 'search.py'):
        if sha(base / name) != protocol['source_pins'][name]:
            raise ValueError('pinned native adapter changed: ' + name)
    expected_population = {'version': 1, **protocol['population_start'], 'source_pins': {
        name: sha(base / name) for name in ('population_loader.py', 'search.py')}}
    selection_spec = importlib.util.spec_from_file_location('matching_replay_selection', base / 'selection.py')
    selection_module = importlib.util.module_from_spec(selection_spec)
    selection_spec.loader.exec_module(selection_module)
    expected_selection = selection_module.selection_identity('mixed', protocol['selection_worlds'])
    if cfg['population_start'] != expected_population or cfg['retention_selection'] != expected_selection:
        raise ValueError('pinned population/selection identity differs')
    expected_identity = {**protocol['expected_numerical_identity'],
                         'population_start': cfg['population_start'],
                         'retention_selection': cfg['retention_selection']}
    if json.loads((folder / 'determinism.json').read_text()) != expected_identity:
        raise ValueError('native extended identity differs')
    saved = torch.load(folder / 'checkpoint.pt', map_location='cpu', weights_only=True)
    middle = torch.load(folder / 'generation8/checkpoint.pt', map_location='cpu', weights_only=True)
    for payload, generation in ((saved, 24), (middle, 8)):
        state = payload['state']
        if (payload['format'] != 1 or payload['config'] != cfg or payload['identity'] != expected_identity
                or state['generation'] != generation or state['evals'] != 256*generation
                or state['rc_lives'] != 512*generation):
            raise ValueError('checkpoint configuration/identity/count differs')
    logs = bound_logs(folder, saved)
    prefixes = bound_logs(folder, middle, prefix=True)
    lines, curves = logs['lineage.jsonl'], logs['curves.jsonl']
    if (saved['state']['curves'] != curves or middle['state']['curves'] != curves[:8]
            or prefixes['curves.jsonl'] != curves[:8] or prefixes['lineage.jsonl'] != lines[:9]
            or [row['gen'] for row in curves] != list(range(24))
            or [row['gen'] for row in curves if 'valid' in row] != [0, 4, 8, 12, 16, 20, 23]):
        raise ValueError('native curve history or passive midpoint prefix differs')
    full = recorded_population(layout, initial, lines, saved['state'], 24)
    mid = recorded_population(layout, initial, prefixes['lineage.jsonl'], middle['state'], 8)
    public = json.loads((folder / 'population.json').read_text())
    if public['dims'] != layout.dims.__dict__:
        raise ValueError('public population dimensions differ')
    rows = torch.stack([layout.from_dict(row) for row in public['genomes']])
    if not operations().same(rows.numpy(), saved['state']['population'].numpy()):
        raise ValueError('public final population differs from reconstructed rows')
    for key in ('ids', 'breeds', 'origins', 'fitness'):
        if public[key] != saved['state'][key].tolist():
            raise ValueError('public final population metadata differs: ' + key)
    for prefix, state in (('', saved['state']), ('generation8/', middle['state'])):
        _, best = type(layout).load(folder / (prefix + 'best_genome.json'))
        if not operations().same(best.numpy(), state['population'][0].numpy()):
            raise ValueError('fixed endpoint is not reconstructed rank zero')
    snapshot = json.loads((folder / 'generation8/snapshot.json').read_text())
    if snapshot != marker['midpoint'] or snapshot != {
            'status': 'complete', 'generation': 8, 'rank': 0,
            'rank_zero_id': int(middle['state']['ids'][0]),
            'checkpoint_sha256': sha(folder / 'generation8/checkpoint.pt'),
            'genome_file_sha256': sha(folder / 'generation8/best_genome.json'),
            'genome_raw_sha256': mid['row_sha256'][0],
            'population_raw_sha256': mid['population_raw_sha256'], 'identity': expected_identity,
            'log_prefix_pins': middle['logs'], 'protocol_sha256': sha(base / 'protocol.json'),
            'release_sha256': sha(base / 'release.json'), 'added_lives': 0, 'random_draws': 0}:
        raise ValueError('passive midpoint snapshot differs')
    return {'status': 'passed', 'protocol_sha256': sha(base / 'protocol.json'),
            'initial_population_raw_sha256': raw_sha(initial.numpy()),
            'runs': {'mixed': {'final': full, 'midpoint': mid}},
            'offspring_replayed': 5376, 'point_additions_replayed': 10752,
            'all_32_midpoint_rows_bound': True, 'all_32_final_rows_bound': True,
            'source_sha256': {name: sha(HERE / name) for name in ('native_replay.py', 'replay_ops.py')},
            'simulated_lives': 0, 'random_draws': 0,
            'limits': ['Recorded operations are replayed; genetic RNG draws are not resampled.',
                       'Survival follows the recorded survivor IDs. This helper does not independently prove ranking or unlogged parent scores.',
                       'Ancestry and byte identity do not establish functional circuitry or memory.']}


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', action='store_true')
    parser.add_argument('--study', type=Path, default=HERE)
    parser.add_argument('--out', type=Path)
    args = parser.parse_args()
    if not args.run:
        print(json.dumps({'status': 'source_only', 'simulated_lives': 0, 'random_draws': 0}))
    else:
        if args.out is None or args.out.exists():
            raise ValueError('an absent output file is required')
        result = complete_replay(args.study)
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(result, indent=2, allow_nan=False) + '\n')
        print(json.dumps({'status': 'passed', 'offspring_replayed': 5376, 'simulated_lives': 0}))
