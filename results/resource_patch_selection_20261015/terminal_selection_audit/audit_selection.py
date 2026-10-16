"""Independent saved-selection mathematics; no selector, simulator or RNG imports/calls."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import resource
import time
from pathlib import Path

import numpy as np

PROTOCOL_SHA = '529d65718fce28b8b9a521ab5edabca81390d190514e71bde79903d57431d8dd'
PATTERN = ('patch', 'pool', 'patch', 'persistent') * 2
NAMES = ('patch', 'pool', 'persistent', 'production_F')
FIELDS = ('W', 'b', 'lam', 's0', 'Q', 'act', 'A', 'a0', 'Dm', 'km')


def require(condition, message):
    if not condition:
        raise ValueError(message)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


def raw_sha(value):
    return hashlib.sha256(np.asarray(value).tobytes()).hexdigest()


def same(actual, expected, label):
    actual, expected = np.asarray(actual), np.asarray(expected)
    require(actual.shape == expected.shape and actual.dtype == expected.dtype
            and actual.tobytes() == expected.tobytes(), label)


def permutation(value, n):
    value = np.asarray(value)
    require(value.shape == (n,) and value.dtype.kind in 'iu'
            and sorted(value.tolist()) == list(range(n)), 'invalid supplied tie permutation')
    return [int(i) for i in value]


def objectives(captures, fitness):
    """Recompute registered float64 means, separately cross-checking F with scalar fsum."""
    captures, fitness = np.asarray(captures), np.asarray(fitness)
    require(captures.shape == fitness.shape and fitness.ndim == 2 and fitness.shape[1] in (8, 16)
            and captures.dtype == fitness.dtype == np.float64 and np.isfinite(fitness).all()
            and np.isfinite(captures).all() and (captures >= 0).all()
            and np.equal(captures, np.floor(captures)).all(), 'invalid objective source matrices')
    labels = PATTERN * (fitness.shape[1] // 8)
    parts = [captures[:, [i for i, label in enumerate(labels) if label == name]].mean(axis=1)
             for name in NAMES[:3]]
    means = fitness.mean(axis=1)
    for row, mean in zip(fitness, means, strict=True):
        reference = math.fsum(float(x) for x in row) / len(row)
        error_bound = 8 * np.finfo(np.float64).eps * math.fsum(abs(float(x)) for x in row) / len(row)
        require(abs(float(mean) - reference) <= error_bound, 'F mean differs from fsum bound')
    return np.column_stack([*parts, means])


def ranking(values, ties):
    """Lexicographic DAG traversal gives front depth; scalar value groups give crowding.

    This does not use the production selector's dominance matrix, front peeling,
    np.unique grouping or lexsort ordering. Shared NumPy mean rounding is explicit.
    """
    rows = np.asarray(values, dtype=np.float64).tolist()
    require(rows and all(len(row) == 4 and all(math.isfinite(x) for x in row) for row in rows),
            'finite four-objective rows required')
    ties = permutation(ties, len(rows))
    ranks = [-1] * len(rows)
    previous = []
    for j in sorted(range(len(rows)), key=lambda i: tuple(rows[i]), reverse=True):
        dominators = [i for i in previous if all(a >= b for a, b in zip(rows[i], rows[j], strict=True))
                      and any(a > b for a, b in zip(rows[i], rows[j], strict=True))]
        ranks[j] = 1 + max((ranks[i] for i in dominators), default=-1)
        previous.append(j)
    crowd = [0.] * len(rows)
    for front in range(max(ranks) + 1):
        members = [i for i, rank in enumerate(ranks) if rank == front]
        for dimension in range(4):
            groups = {}
            for i in members:
                groups.setdefault(rows[i][dimension], []).append(i)
            levels = sorted(groups)
            if len(levels) < 2:
                continue
            scale = max(abs(levels[0]), abs(levels[-1]))
            scaled = [value / scale for value in levels]
            span = scaled[-1] - scaled[0]
            for k, level in enumerate(levels):
                delta = (math.inf if k in (0, len(levels) - 1)
                         else (scaled[k + 1] - scaled[k - 1]) / span)
                for i in groups[level]:
                    crowd[i] += delta
    priority = {i: rank for rank, i in enumerate(ties)}
    order = sorted(range(len(rows)), key=lambda i: (ranks[i], -crowd[i], priority[i]))
    return {'objective_names': list(NAMES), 'objectives': rows, 'ranks': ranks,
            'crowding': [None if math.isinf(x) else x for x in crowd],
            'crowding_infinite': [math.isinf(x) for x in crowd], 'order': order, 'tie_order': ties}


def mean_order(values, ties):
    return sorted(permutation(ties, len(values)), key=lambda i: -float(values[i]))


def endpoint(values, ids, references):
    values = np.asarray(values, dtype=np.float64)
    ids = [int(i) for i in ids]
    require(values.shape == (32, 4) and len(set(ids)) == 32 and min(ids) >= 0, 'endpoint dimensions/IDs')
    fractions = [[float(row[d]) / references[d] for d in range(3)] for row in values]
    worst = [min(row) for row in fractions]
    order = sorted(range(32), key=lambda i: (-worst[i], -float(values[i, 3]), ids[i]))
    return {'objective_names': list(NAMES), 'objectives': values.tolist(), 'ao_reference': references,
            'fractions': fractions, 'worst_fraction': worst, 'order': order,
            'tie_order': sorted(range(32), key=lambda i: ids[i]), 'candidate_ids': ids,
            'selected': order[0], 'selected_id': ids[order[0]]}


def packed_genome(params):
    require(set(params) == set(FIELDS), 'genome field schema differs')
    result = np.concatenate([np.asarray(params[name], dtype=np.float32).reshape(-1) for name in FIELDS])
    require(result.shape == (875,) and np.isfinite(result).all(), 'genome packed dimensions/finiteness')
    return result


def stage_arrays(arrays, record, arm):
    for prefix, size in (('base', 256), ('recheck', 64)):
        for field in ('captures', 'production_F', 'native_F', 'status', 'extinct_charge', 'invalid', 'mismatch'):
            a = arrays[f'{prefix}_{field}']
            require(a.shape == (size, 8) and np.isfinite(a).all(), 'scored row shape/finiteness')
        require(not arrays[prefix + '_invalid'].any() and not arrays[prefix + '_mismatch'].any(),
                'invalid/mismatch source rows')
        same(arrays[prefix + '_production_F'], arrays[prefix + '_native_F'] - arrays[prefix + '_extinct_charge'],
             'ordinary production F differs')
    permutation(arrays['pre_permutation'], 256)
    base = objectives(arrays['base_captures'], arrays['base_production_F'])
    first = ranking(base, arrays['shortlist_permutation'])
    require(record['stage0_pareto'] == first, 'base front/crowding/order audit differs')
    order0 = mean_order(base[:, 3], arrays['shortlist_permutation']) if arm == 'mean' else first['order']
    short = np.asarray(order0[:64], dtype=np.int64)
    joined = [np.concatenate((arrays['base_' + name][short], arrays['recheck_' + name]), axis=1)
              for name in ('captures', 'production_F')]
    pooled = objectives(*joined)
    second = ranking(pooled, arrays['survivor_permutation'])
    require(record['stage1_pareto'] == second, 'pooled16 front/crowding/order audit differs')
    order1 = mean_order(pooled[:, 3], arrays['survivor_permutation']) if arm == 'mean' else second['order']
    pick = np.asarray(order1[:32], dtype=np.int64)
    for key, value in (('base_objectives', base), ('pooled_objectives', pooled), ('shortlist', short),
                       ('pick', pick), ('shortlist_order', np.asarray(order0, dtype=np.int64)),
                       ('survivor_order', np.asarray(order1, dtype=np.int64))):
        same(arrays[key], value, key + ' differs')
    same(arrays['recheck_genomes'], arrays['base_genomes'][short], 'recheck genotype row order')
    require(record['selection_order'] == short[pick].tolist(), 'selected candidate order differs')
    return short, pick, pooled[pick]


def audit(study):
    # The completion guard precedes all search/outcome reads. Execution still needs the parent's terminal signal.
    require(sha(study / 'protocol.json') == PROTOCOL_SHA, 'registered protocol changed')
    protocol = read(study / 'protocol.json')
    terminal = {name: read(study / name) for name in ('study_complete.json', 'budget.json')}
    for name, value in terminal.items():
        require(value['status'] == 'complete' and value['protocol_sha256'] == PROTOCOL_SHA,
                name + ' is not complete for this protocol')
    require(terminal['study_complete.json']['total_calls'] == 30808, 'terminal call inventory')
    budget = terminal['budget.json']
    require(not budget['running'] and not budget['queued'] and not budget['cleanup_error'], 'owned execution uncleared')
    for name, digest in protocol['source_pins'].items():
        require(sha(study / name) == digest, 'registered source changed: ' + name)
    for name, digest in protocol['input_pins'].items():
        require(sha(study / name) == digest, 'registered input changed: ' + name)
    require(protocol['endpoint']['reference_captures'] == [19.046875, 16.029296875, 5.919921875]
            and protocol['endpoint']['worlds'] == list(NAMES[:3]), 'registered endpoint references')
    imported = read(study / protocol['population_start']['population_file'])
    initial = np.stack([packed_genome(row) for row in imported['genomes']])
    require(raw_sha(initial) == protocol['population_start']['population_raw_sha256'], 'initial population pin')
    pins = {name: sha(study / name) for name in (*terminal, 'measurement_complete.json')}
    result, first, paired_draws = {}, {}, {}
    import torch  # Checkpoint decoding only; no repository module, simulator or random API is imported.

    for arm in ('mean', 'pareto'):
        folder = study / 'runs' / arm
        marker = read(folder / 'search_complete.json')
        require(marker['status'] == 'complete' and marker['protocol_sha256'] == PROTOCOL_SHA
                and marker['arm'] == arm, 'search marker identity')
        require(sha(folder / 'search_complete.json') == terminal['study_complete.json']['search_complete_pins'][arm],
                'terminal search marker pin')
        pins[f'runs/{arm}/search_complete.json'] = sha(folder / 'search_complete.json')
        for name, digest in marker['output_pins'].items():
            require(sha(folder / name) == digest, 'search output pin: ' + name)
            pins[f'runs/{arm}/{name}'] = digest
        saved = torch.load(folder / 'checkpoint.pt', map_location='cpu', weights_only=True)
        state = saved['state']
        require(state['generation'] == 4 and state['evals'] == 1024 and state['rc_lives'] == 2048,
                'final checkpoint counts')
        line_bytes = (folder / 'lineage.jsonl').read_bytes()
        lp = saved['logs']['lineage.jsonl']
        require(len(line_bytes) == lp['bytes'] and hashlib.sha256(line_bytes).hexdigest() == lp['sha256'],
                'checkpoint lineage pin')
        lines = [json.loads(line) for line in line_bytes.splitlines()]
        require(lines[0]['ids'] == list(range(32)) and lines[0]['copies'] == []
                and [row.get('gen') for row in lines[1:]] == list(range(4)), 'lineage generation scope')
        parents, parent_genomes = list(range(32)), initial
        stages = []
        for g, row in enumerate(lines[1:]):
            rec = row['selection']
            filename = f'selection/g{g:03d}.npz'
            require(rec['path'] == filename and rec['sha256'] == sha(folder / filename)
                    and rec['arm'] == arm and rec['extra_lives'] == rec['extra_rng_draws'] == 0,
                    'selection file/call provenance')
            with np.load(folder / filename, allow_pickle=False) as file:
                a = {name: file[name] for name in file.files}
            children = [child['id'] for child in row['children']]
            require(children == list(range(32 + g * 224, 32 + (g + 1) * 224)), 'child ID sequence')
            ids = np.asarray(parents + children, dtype=np.int64)
            same(a['candidate_ids'], ids, 'candidate IDs')
            require(a['base_genomes'].shape == (256, 875) and a['base_genomes'].dtype == np.float32,
                    'candidate genotype matrix')
            same(a['base_genomes'][:32], parent_genomes, 'retained parent genotype order')
            require(raw_sha(a['base_genomes']) == rec['candidate_raw_sha256'], 'candidate genotype pin')
            if g == 0:
                first[arm] = a['base_genomes'].copy()
            expected_worlds = np.asarray([protocol['worlds'][name]['world_vector'] for name in PATTERN])
            for prefix, seeds in (('base', row['seeds']), ('recheck', row['recheck']['seeds'])):
                same(a[prefix + '_seeds'], np.asarray(seeds, dtype=np.uint64), 'native seed rows')
                same(a[prefix + '_worlds'], expected_worlds, 'native selection world rows')
            for key in ('base_seeds', 'recheck_seeds', 'pre_permutation',
                        'shortlist_permutation', 'survivor_permutation'):
                if arm == 'mean':
                    paired_draws[g, key] = a[key].copy()
                else:
                    same(a[key], paired_draws[g, key], 'paired native seed/tie schedule: ' + key)
            short, pick, final_objectives = stage_arrays(a, rec, arm)
            require(ids[short].tolist() == row['recheck']['ids']
                    and ids[short[pick]].tolist() == row['survivors']
                    and final_objectives[:, 3].tolist() == row['fitness'], 'lineage retention/F differs')
            parents = ids[short[pick]].tolist()
            parent_genomes = a['base_genomes'][short[pick]]
            stages.append({'generation': g, 'selection_sha256': rec['sha256'], 'rankings_checked': 2,
                           'tie_permutations_checked': 3, 'base_rows': 256, 'pooled_rows': 64})
        same(state['population'].numpy(), parent_genomes, 'checkpoint selected genotypes')
        same(state['ids'].numpy(), np.asarray(parents, dtype=np.int64), 'checkpoint selected IDs')
        public = read(folder / 'population.json')
        same(np.stack([packed_genome(row) for row in public['genomes']]), parent_genomes, 'public genotypes')
        require(public['ids'] == parents, 'public survivor IDs')
        expected = endpoint(final_objectives, parents, protocol['endpoint']['reference_captures'])
        receipt = read(folder / 'endpoint_selection.json')
        rank = expected['selected']
        joint = packed_genome(read(folder / 'joint_genome.json')['params'])
        same(joint, parent_genomes[rank], 'joint endpoint genotype')
        require(receipt['selection'] == expected and receipt == marker['endpoint']
                and receipt['rank'] == rank and receipt['id'] == parents[rank]
                and receipt['protocol_sha256'] == PROTOCOL_SHA
                and receipt['checkpoint_sha256'] == sha(folder / 'checkpoint.pt')
                and receipt['genome_file_sha256'] == sha(folder / 'joint_genome.json')
                and receipt['genome_raw_sha256'] == raw_sha(joint)
                and receipt['population_raw_sha256'] == raw_sha(parent_genomes)
                and receipt['selection_path'] == 'selection/g003.npz'
                and receipt['selection_sha256'] == stages[-1]['selection_sha256']
                and receipt['added_lives'] == receipt['random_draws'] == 0, 'endpoint receipt differs')
        result[arm] = {'stages': stages, 'endpoint_rank': rank, 'endpoint_id': parents[rank],
                       'joint_raw_sha256': raw_sha(joint)}
    same(first['mean'], first['pareto'], 'first-generation candidate genotypes differ between arms')
    return {'status': 'passed', 'protocol_sha256': PROTOCOL_SHA, 'source_sha256': sha(__file__),
            'runs': result, 'artifact_pins': pins, 'source_pins_verified': protocol['source_pins'],
            'rankings_checked': 16, 'tie_permutations_checked': 24,
            'selection_lives_checked': 20480, 'first_candidate_rows_equal': 256,
            'initial_candidate_raw_sha256': raw_sha(first['mean']),
            'calls': {'simulator': 0, 'builds': 0, 'random_draws': 0},
            'limits': ['Saved selection mathematics and row identity only; no trajectory or genetic RNG replay.',
                       'NumPy float64 mean rounding is shared; scalar fsum independently bounds F arithmetic.',
                       'No selection.py, pareto.py, native_replay.py or repository module is imported.',
                       'Independent accounting and recorded genetic replay are separate receipts.']}


def self_test():
    # Literal fixtures only. This branch never reads the study, checkpoints or outcomes.
    r = ranking([[4, 4, 4, 4], [3, 3, 3, 3], [3, 3, 3, 3], [4, 0, 4, 4], [0, 0, 0, 0]], [4, 3, 2, 1, 0])
    require(r['ranks'] == [0, 1, 1, 1, 2], 'fabricated front depth')
    r = ranking([[0, 3, 0, 0], [1, 2, 0, 0], [1, 2, 0, 0], [3, 0, 0, 0]], [2, 1, 3, 0])
    require(r['ranks'] == [0] * 4 and r['crowding'] == [None, 2., 2., None]
            and r['order'] == [3, 0, 2, 1], 'fabricated crowding/duplicate/ties')
    r = ranking([[0, 0, 0, 0]] * 4, [2, 1, 3, 0])
    require(r['crowding'] == [0.] * 4 and r['order'] == [2, 1, 3, 0], 'constant front')
    require(mean_order([2., 3., 3., -1.], [2, 0, 3, 1]) == [2, 1, 0, 3], 'mean stable order')
    cap = np.tile(np.asarray([8., 4., 8., 2.] * 4), (2, 1))
    fit = np.tile(np.asarray([1., 2., 3., 4.] * 4), (2, 1))
    same(objectives(cap, fit), np.asarray([[8., 4., 2., 2.5]] * 2), 'pooled16 objectives')
    v = np.zeros((32, 4))
    v[:, :3] = [8., 4., 2.]
    v[2:4, 3] = 3.
    e = endpoint(v, list(range(100, 68, -1)), [8., 4., 2.])
    require(e['selected'] == 3 and e['selected_id'] == 97, 'common endpoint F then ID tie')
    try:
        permutation([0, 0], 2)
    except ValueError:
        pass
    else:
        raise AssertionError('duplicate tie permutation accepted')
    return {'status': 'passed', 'literal_cases': 7, 'outcome_reads': 0, 'simulator_calls': 0, 'random_draws': 0}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument('--run', action='store_true')
    mode.add_argument('--self-test', action='store_true')
    parser.add_argument('--study', type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument('--out', type=Path)
    args = parser.parse_args()
    start, cpu = time.monotonic(), time.process_time()
    if args.self_test:
        print(json.dumps(self_test(), allow_nan=False))
    elif args.run:
        require(args.out is not None and not args.out.exists(), 'absent output path required')
        result = audit(args.study.resolve())
        result['resources'] = {'cpu_seconds': time.process_time() - cpu,
                               'wall_seconds': time.monotonic() - start,
                               'peak_rss_bytes': resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024}
        with args.out.open('x') as stream:
            json.dump(result, stream, indent=2, allow_nan=False)
            stream.write('\n')
        print(json.dumps({'status': 'passed', 'rankings_checked': 16, 'simulator_calls': 0}))
    else:
        print(json.dumps({'status': 'source_only', 'outcome_reads': 0, 'simulator_calls': 0}))
