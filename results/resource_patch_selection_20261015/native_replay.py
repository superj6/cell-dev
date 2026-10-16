"""Offline ABI6 two-arm genetics and recorded selection replay from saved parents and recorded operations only."""
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
    spec = importlib.util.spec_from_file_location('patch_recorded_ops', path)
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
    for arm in ('mean', 'pareto'):
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
                       'First-cohort identity alone does not establish functional behavior.']}


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


def recorded_selection(base, folder, arm, protocol, layout, initial, lines, state):
    """Rederive rankings from logged lives; replay operations bind all candidate row bytes.

    This deliberately reuses the reviewed pure selector. An independent accounting audit
    must still check its ranking mathematics separately; no simulator or RNG is invoked.
    """
    import pareto
    from selection import endpoint_from_arrays

    from src.life import spec

    parents = {i: row.clone() for i, row in enumerate(initial)}
    ops = operations()
    world_rows = np.stack([spec.V6.pack_world(spec.World(**protocol['selection_worlds'][name]))
                          for name in ('patch', 'pool', 'patch', 'persistent') * 2])
    files = {}
    final_arrays = None
    for g, row in enumerate(lines[1:]):
        record = row['selection']
        name = f'selection/g{g:03d}.npz'
        if record['path'] != name or record['arm'] != arm or sha(folder / name) != record['sha256']:
            raise ValueError('selection array provenance differs')
        with np.load(folder / name, allow_pickle=False) as file:
            arrays = {key: file[key] for key in file.files}
        candidates = dict(parents)
        for child in row['children']:
            units = torch.tensor([(child['mask'] >> i) & 1 for i in range(layout.n_units)], dtype=torch.bool)
            mixed = layout.silence(torch.where(units[layout.unit_of], parents[child['pa']], parents[child['pb']]))
            candidates[child['id']] = ops.point_mutation(layout, mixed, child['ops'])
        matrix = torch.stack(list(candidates.values())).numpy()
        ids = np.asarray(list(candidates), dtype=np.int64)
        if (not ops.same(matrix, arrays['base_genomes']) or not ops.same(ids, arrays['candidate_ids'])
                or raw_sha(matrix) != record['candidate_raw_sha256']
                or arrays['base_seeds'].tolist() != row['seeds']
                or arrays['recheck_seeds'].tolist() != row['recheck']['seeds']):
            raise ValueError('recorded genetics/IDs/seeds differ from scored candidate rows')
        for stage, shape in (('base', (256, 8)), ('recheck', (64, 8))):
            if not ops.same(arrays[stage + '_worlds'], world_rows):
                raise ValueError('recorded fixed selection worlds differ')
            for key in ('captures', 'production_F', 'native_F', 'status', 'extinct_charge', 'invalid', 'mismatch'):
                values = arrays[f'{stage}_{key}']
                if values.shape != shape or not np.isfinite(values).all():
                    raise ValueError('selection raw life matrix shape/finiteness differs')
            if (arrays[stage + '_invalid'].any() or arrays[stage + '_mismatch'].any()
                    or not ops.same(arrays[stage + '_production_F'],
                                    arrays[stage + '_native_F'] - arrays[stage + '_extinct_charge'])):
                raise ValueError('selection ordinary F/health differs')
        if not np.array_equal(np.sort(arrays['pre_permutation']), np.arange(256)):
            raise ValueError('diagnostic tie permutation differs')
        base_cap, base_fit = arrays['base_captures'], arrays['base_production_F']
        new_cap, new_fit = arrays['recheck_captures'], arrays['recheck_production_F']
        first = pareto.select_shortlist(base_cap, base_fit, arrays['shortlist_permutation'])
        order0 = (pareto.rank_mean(base_fit.mean(axis=1), arrays['shortlist_permutation'])
                  if arm == 'mean' else first.ranking.order)
        short = order0[:64]
        second = pareto.select_survivors(base_cap, base_fit, short, new_cap, new_fit,
                                         arrays['survivor_permutation'])
        order1 = (pareto.rank_mean(second.ranking.objectives[:, 3], arrays['survivor_permutation'])
                  if arm == 'mean' else second.ranking.order)
        pick = order1[:32]
        for actual, expected in ((arrays['shortlist'], short), (arrays['pick'], pick),
                                 (arrays['shortlist_order'], order0), (arrays['survivor_order'], order1),
                                 (arrays['base_objectives'], first.ranking.objectives),
                                 (arrays['pooled_objectives'], second.ranking.objectives),
                                 (arrays['recheck_genomes'], matrix[short])):
            if not ops.same(actual, expected):
                raise ValueError('recorded selection order/objectives differ from rederivation')
        if (first.ranking.audit() != record['stage0_pareto']
                or second.ranking.audit() != record['stage1_pareto']
                or short[pick].tolist() != record['selection_order']
                or ids[short].tolist() != row['recheck']['ids']
                or ids[short[pick]].tolist() != row['survivors']
                or second.ranking.objectives[pick, 3].tolist() != row['fitness']
                or base_fit[short].mean(axis=1).tolist() != row['recheck']['F_base']
                or new_fit.mean(axis=1).tolist() != row['recheck']['F_recheck']):
            raise ValueError('lineage scoring/retention differs from captured lives')
        parents = {key: candidates[key] for key in row['survivors']}
        files[name] = record['sha256']
        final_arrays = arrays
    if not ops.same(torch.stack(list(parents.values())).numpy(), state['population'].numpy()):
        raise ValueError('selected final population rows differ')
    endpoint = endpoint_from_arrays(final_arrays, state['ids'].numpy())
    receipt = json.loads((folder / 'endpoint_selection.json').read_text())
    _, genome = type(layout).load(folder / 'joint_genome.json')
    rank = endpoint.selected
    if (receipt['selection'] != endpoint.audit() or receipt['rank'] != rank
            or receipt['id'] != int(state['ids'][rank])
            or receipt['selection_path'] != 'selection/g003.npz'
            or receipt['selection_sha256'] != files['selection/g003.npz']
            or receipt['checkpoint_sha256'] != sha(folder / 'checkpoint.pt')
            or receipt['genome_file_sha256'] != sha(folder / 'joint_genome.json')
            or receipt['genome_raw_sha256'] != raw_sha(genome.numpy())
            or receipt['population_raw_sha256'] != raw_sha(state['population'].numpy())
            or not ops.same(genome.numpy(), state['population'][rank].numpy())
            or receipt['protocol_sha256'] != sha(base / 'protocol.json')
            or receipt['added_lives'] != 0 or receipt['random_draws'] != 0):
        raise ValueError('common joint endpoint differs from cached final16 selection')
    return {'files': files, 'generations': 4, 'scored_base_lives': 8192, 'scored_recheck_lives': 2048,
            'candidate_rows_genetically_replayed': 1024, 'endpoint_rank': rank,
            'endpoint_id': int(state['ids'][rank]), 'endpoint_sha256': sha(folder / 'endpoint_selection.json'),
            'selector_reused_not_independent': True}


def complete_replay(study, protocol=None):
    """Bind two complete searches and reconstruct every recorded candidate and final row."""
    from omegaconf import OmegaConf

    base = Path(study).resolve()
    actual = json.loads((base / 'protocol.json').read_text())
    if protocol is not None and protocol != actual:
        raise ValueError('supplied protocol differs from saved protocol')
    protocol = actual
    expected_search = {'arms': ['mean', 'pareto'], 'generations': 4, 'research_lives_per_arm': 10278,
                       'startup_lives_per_arm': 4, 'initial_lives': 8, 'recheck_lives': 8,
                       'parents': 32, 'offspring': 224,
                       'growth_diagnostic_T': 512, 'growth_diagnostic_lives': 2}
    if protocol['search'] != expected_search:
        raise ValueError('registered paired selection scope differs')
    for name in ('native_replay.py', 'replay_ops.py', 'population_loader.py', 'selection.py', 'pareto.py', 'search.py'):
        if sha(base / name) != protocol['source_pins'][name]:
            raise ValueError('recorded replay/adapter helper source changed')
    layout, initial = initial_population(base, protocol)
    sys.path.insert(0, str(base))
    import selection

    runs = {}
    first = {}
    for arm in ('mean', 'pareto'):
        folder = base / 'runs' / arm
        marker = json.loads((folder / 'search_complete.json').read_text())
        for key, value in {'status': 'complete', 'arm': arm, 'research_lives': 10278,
                           'startup_lives': 4, 'protocol_sha256': sha(base / 'protocol.json'),
                           'release_sha256': sha(base / 'release.json')}.items():
            if marker[key] != value:
                raise ValueError('completed search marker differs: ' + key)
        required = {'checkpoint.pt', 'config.yaml', 'determinism.json', 'curves.jsonl', 'lineage.jsonl',
                    'population.json', 'best_genome.json', 'results.jsonl', 'search_startup.json',
                    'joint_genome.json', 'endpoint_selection.json',
                    *(f'selection/g{g:03d}.npz' for g in range(4))}
        if set(marker['output_pins']) != required:
            raise ValueError('completed search output coverage differs')
        for name, digest in marker['output_pins'].items():
            if sha(folder / name) != digest:
                raise ValueError('completed search output changed: ' + name)
        cfg_path = base / protocol['configs'][arm]['path']
        if sha(cfg_path) != protocol['configs'][arm]['sha256']:
            raise ValueError('registered configuration changed')
        cfg = config_identity(cfg_path)
        if config_identity(folder / 'config.yaml') != cfg:
            raise ValueError('native configuration differs')
        for key, value in {'generations': 4, 'mu': 32, 'lam': 224, 'breeding': 'sex', 'n_mut': 2,
                           'dup_rate': 0., 'del_rate': 0., 'dup_split': False, 'recheck_k': 64,
                           'recheck_lives': 8, 'recheck_key': 'all', 'heldout_every': 4}.items():
            if cfg['evolve'][key] != value:
                raise ValueError('ordinary search setting differs: ' + key)
        if (cfg['seed'] != protocol['native_seed'] or cfg['life']['abi'] != 6 or cfg['life']['T'] != 1024.
                or cfg['life']['lives'] != 8 or cfg['life']['T_choices'] is not None
                or not cfg['life']['extinct_charge'] or cfg['logging']['lineage'] != 'all'):
            raise ValueError('search seed/base evaluator differs')
        expected_population = {'version': 1, **protocol['population_start'], 'source_pins': {
            name: sha(base / name) for name in ('population_loader.py', 'search.py')}}
        expected_selection = selection.selection_identity(arm, protocol['selection_worlds'])
        if cfg['population_start'] != expected_population or cfg['retention_selection'] != expected_selection:
            raise ValueError('pinned population/selection identity differs')
        identity = {**protocol['expected_numerical_identity'],
                    'population_start': cfg['population_start'], 'retention_selection': cfg['retention_selection']}
        if json.loads((folder / 'determinism.json').read_text()) != identity:
            raise ValueError('native extended identity differs')
        saved = torch.load(folder / 'checkpoint.pt', map_location='cpu', weights_only=True)
        state = saved['state']
        if (saved['format'] != 1 or saved['config'] != cfg or saved['identity'] != identity
                or state['generation'] != 4 or state['evals'] != 1024 or state['rc_lives'] != 2048):
            raise ValueError('checkpoint configuration/identity/count differs')
        logs = bound_logs(folder, saved)
        lines, curves = logs['lineage.jsonl'], logs['curves.jsonl']
        if (state['curves'] != curves or [row['gen'] for row in curves] != list(range(4))
                or [row['gen'] for row in curves if 'valid' in row] != [0, 3]):
            raise ValueError('native curve history differs')
        full = recorded_population(layout, initial, lines, state, 4)
        selected = recorded_selection(base, folder, arm, protocol, layout, initial, lines, state)
        first[arm] = replay_first(layout, initial, lines)
        public = json.loads((folder / 'population.json').read_text())
        rows = torch.stack([layout.from_dict(row) for row in public['genomes']])
        if public['dims'] != layout.dims.__dict__ or not operations().same(rows.numpy(), state['population'].numpy()):
            raise ValueError('public final population differs from reconstructed rows')
        for key in ('ids', 'breeds', 'origins', 'fitness'):
            if public[key] != state[key].tolist():
                raise ValueError('public final population metadata differs: ' + key)
        _, best = type(layout).load(folder / 'best_genome.json')
        if not operations().same(best.numpy(), state['population'][0].numpy()):
            raise ValueError('native best export is not reconstructed rank zero')
        from search import verify_endpoint

        endpoint = verify_endpoint(folder, OmegaConf.load(cfg_path), identity)
        if endpoint != marker['endpoint']:
            raise ValueError('completed marker endpoint differs')
        runs[arm] = {'final': full, 'selection': selected, 'endpoint': endpoint}
    if first['mean'] != first['pareto']:
        raise ValueError('common-seed initial cohorts differ before selection')
    return {'status': 'passed', 'protocol_sha256': sha(base / 'protocol.json'),
            'initial_population_raw_sha256': raw_sha(initial.numpy()), 'runs': runs,
            'first_cohort': first, 'first_cohort_bitwise_equal': True,
            'offspring_replayed': 1792, 'point_additions_replayed': 3584,
            'all_32_final_rows_bound_per_arm': True, 'all_scored_candidate_rows_bound': True,
            'source_sha256': {name: sha(HERE / name) for name in ('native_replay.py', 'replay_ops.py')},
            'simulated_lives': 0, 'random_draws': 0,
            'limits': ['Recorded operations are replayed; genetic RNG draws are not resampled.',
                       'Selection is rederived using the registered pure selector, not an independent implementation.',
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
        print(json.dumps({'status': 'passed', 'offspring_replayed': result['offspring_replayed'], 'simulated_lives': 0}))
