"""Independent completed-data accounting; no analyzer, engine, Torch or RNG imports.

The prior independent scalar ledger routine and fixed-source recount are SHA-pinned.
Each NPZ is decompressed once. Checkpoint internals/genetic replay are a separate review.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import math
import os
import resource
import sys
import time
from collections import Counter
from pathlib import Path

os.environ['OPENBLAS_NUM_THREADS'] = '1'
os.environ['OMP_NUM_THREADS'] = '1'
os.environ['MKL_NUM_THREADS'] = '1'
sys.dont_write_bytecode = True
STUDY = Path(__file__).resolve().parent.parent
ROOT = STUDY.parents[1]
PROTOCOL = '86593f759c5c17823d4eaff19800728229f757eb2ffc82b2f54660e9b32653bb'
BORROWED = {
    'scalar': ('results/resource_patch_selection_20261015/terminal_audit/audit_accounting.py',
               'dbc493e5752e9703c80063ebfb28b7119bc52cbf567af85dcc5c5bc20be02a75'),
    'schedule': ('results/resource_patch_population_20261015/terminal_review/independent_review.py',
                 'ea97a0abbd384cf3015423df04b4f1bb0233f057aa92029ecfa60c1d1da52d35'),
}
ROLES = ('AO', 'G8_joint', 'Pareto4_joint', 'depth8_joint')
TRAIN = ('patch', 'pool', 'persistent')
WORLDS = (*TRAIN, 'blink80_20', 'transfer', 'reserved_capacity3')
SCALES = (19.046875, 16.029296875, 5.919921875)
ENDPOINT_METRICS = ('captures', 'F', 'cost', 'total_patch_initial_harvest', 'total_patch_refill_harvest',
                    'total_patch_empty', 'misses', 'path', 'n_end', 'guarded', 'extinct')
HASH_INIT = 0x243F6A8885A308D3


def read(path):
    return json.loads(Path(path).read_text())


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def raw_sha(array):
    return hashlib.sha256(array.tobytes()).hexdigest()


def require(condition, label):
    if not condition:
        raise ValueError(label)


def close(a, b, label):
    require(math.isfinite(a) and math.isfinite(b) and abs(a-b) <= 1e-9*max(1., abs(b)), label)


def average(values):
    return math.fsum(values)/len(values)


def stats(actual, values, label):
    n = len(values)
    require(n in (32, 512) and actual['n'] == n and all(math.isfinite(x) for x in values), label+' n')
    mean = average(values)
    se = math.sqrt(math.fsum((x-mean)**2 for x in values)/(n-1)/n)
    for key, value in (('mean', mean), ('se', se), ('lower_3se', mean-3*se), ('upper_3se', mean+3*se)):
        close(actual[key], value, label+' '+key)
    require(actual['positive_above_3se'] == (mean > 3*se) and actual['bounds_are_descriptive'] is True,
            label+' descriptive flags')


def load_npz(path, np):
    with np.load(path, allow_pickle=False) as file:
        return {key: file[key].copy() for key in file.files}


def retained_module(name):
    relative, pin = BORROWED[name]
    require(sha(ROOT/relative) == pin, 'retained independent helper '+name)
    spec = importlib.util.spec_from_file_location('depth_independent_'+name, ROOT/relative)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def cleared(record):
    proof = record['terminal_cleanup']
    require(all(proof[k] for k in ('same_pid_namespace', 'all_owned_groups_exited', 'all_worker_identities_exited'))
            and not any(proof[k] for k in
                        ('remaining_group_members', 'remaining_worker_identities', 'remaining_descendants')),
            'owned terminal cleanup')
    require(record['status'] == 'complete' and not record['error'] and not record['running']
            and not record['queued'], 'complete resource receipt')


def terminal(study, p, digest, artifacts):
    """Gate all outcome reads on completed, bounded, cleared execution and exact phase inventory."""
    complete, budget, release = (read(study/name) for name in
                                ('study_complete.json', 'budget.json', 'release.json'))
    require(complete['status'] == budget['status'] == 'complete'
            and complete['protocol_sha256'] == budget['protocol_sha256'] == release['protocol_sha256'] == digest
            and release['status'] == 'released' and budget['release_sha256'] == sha(study/'release.json'),
            'completed released protocol')
    require((p['research_lives'], p['startup_lives'], p['total_calls']) == (97334, 8, 97342)
            and (complete['research_lives'], complete['startup_lives'], complete['total_calls']) == (97334, 8, 97342),
            'overall call inventory')
    for key, name in (('search_complete_sha256', 'runs/pareto/search_complete.json'),
                      ('measurement_complete_sha256', 'measurement_complete.json'),
                      ('summary_sha256', 'summary.json'), ('budget_sha256', 'budget.json')):
        require(complete[key] == sha(study/name), 'terminal marker pin '+name)
        artifacts[name] = sha(study/name)
    cleared(budget)
    require(set(budget['phases']) == set(budget['phase_cpu_seconds']) == {'pareto', 'measurement'}, 'both phases')
    close(sum(budget['phase_cpu_seconds'].values()), budget['cpu_seconds'], 'cumulative phase CPU')
    for key in ('cpu_seconds', 'wall_seconds'):
        require(0 <= budget[key] < p['runtime_budget'][key], 'runtime '+key)
        used = budget[key]+p['package_budget']['preparation_terminal_'+key.replace('_seconds', '')+'_reserve']
        close(complete['package_'+key+'_with_full_reserve'], used, 'conservative package '+key)
        require(used < p['package_budget'][key], 'package '+key)
    for phase in ('pareto', 'measurement'):
        path = f'execution/{phase}/budget.json'
        record, attempt = read(study/path), read(study/f'execution/{phase}/attempt.json')
        require(record == budget['phases'][phase] and sha(study/path) == complete['phase_budget_pins'][phase],
                'phase receipt binding')
        cleared(record)
        require(record['worker_exit_code'] == 0 and not record['reason'] and not record['cleanup_error']
                and record['protocol_sha256'] == attempt['protocol_sha256'] == digest
                and record['release_sha256'] == attempt['release_sha256'] == sha(study/'release.json')
                and record['attempt_sha256'] == sha(study/f'execution/{phase}/attempt.json')
                and record['pid_namespace'] == attempt['pid_namespace'] == release['pid_namespace'],
                'phase ownership')
        require(0 <= budget['phase_cpu_seconds'][phase] < p['phase_budgets'][phase]['cpu_seconds']
                and record['cpu_seconds'] < record['cap_cpu_seconds']
                and record['wall_seconds'] < record['cap_wall_seconds'] <= p['phase_budgets'][phase]['wall_seconds']
                and record['peak_owned_rss_bytes'] < p['runtime_budget']['rss_bytes']
                and record['available_memory_bytes'] >= p['runtime_budget']['minimum_available_bytes'],
                'phase resource limits')
        expected_cap = min(p['runtime_budget']['cpu_seconds'], p['phase_budgets']['pareto']['cpu_seconds']
                           if phase == 'pareto' else budget['phase_cpu_seconds']['pareto']
                           +p['phase_budgets']['measurement']['cpu_seconds'])
        close(record['cap_cpu_seconds'], expected_cap, 'absolute cumulative CPU threshold')
        worker = record['process_identities'][1]
        require(worker['pid'] == worker['pgid'] and worker['ppid'] == attempt['monitor']['pid']
                and any(row['pid'] == worker['pid'] and row['exit_code'] == 0 for row in record['wait4_receipts']),
                'owned child and reaped exit')
        artifacts[path] = sha(study/path)
        artifacts[f'execution/{phase}/attempt.json'] = sha(study/f'execution/{phase}/attempt.json')
    marker = read(study/'runs/pareto/search_complete.json')
    require(marker['status'] == 'complete' and marker['arm'] == 'pareto' and marker['research_lives'] == 81974
            and marker['startup_lives'] == 4 and marker['protocol_sha256'] == digest
            and marker['release_sha256'] == sha(study/'release.json')
            and marker['reporting_endpoint_selected'] is False and marker['native_rank0_only'] is True
            and marker['count_proof'] == dict(selection=81920, valid=48, final=6, growth_half=2,
                                             native_evals=2560, generations=8, children_per_generation=224),
            'search inventory and separate reporting endpoint')
    required = {'checkpoint.pt', 'config.yaml', 'determinism.json', 'curves.jsonl', 'lineage.jsonl',
                'population.json', 'best_genome.json', 'results.jsonl', 'search_startup.json',
                *(f'selection/g{g:03d}.npz' for g in range(8))}
    require(set(marker['output_pins']) == required, 'complete search artifacts')
    for name, pin in marker['output_pins'].items():
        relative = 'runs/pareto/'+name
        require(sha(study/relative) == pin, 'search output '+name)
        artifacts[relative] = pin
    for name, meta in marker['checkpoint_log_pins'].items():
        path = study/'runs/pareto'/name
        require(path.stat().st_size == meta['bytes'] and sha(path) == meta['sha256'], 'checkpoint log binding')
    artifacts.update({name: sha(study/name) for name in ('protocol.json', 'study_complete.json', 'release.json')})


def startup(study, p, digest, artifacts, np):
    fixture = read(study/'inputs/patch_truth.json')['cases'][0]
    for phase, name in (('pareto', 'runs/pareto/search_startup.json'), ('measurement', 'startup.json')):
        record = read(study/name)
        require(record['identity'] == p['expected_numerical_identity'] and record['startup_lives'] == 4
                and record['protocol_sha256'] == digest, 'retained startup identity')
        patch = record['patches']
        folder = f'execution/{phase}/patch_truth'
        require(patch['name'] == fixture['name'] and patch['seed'] == fixture['seed'] and patch['lives'] == 2
                and patch['calls_path'] == folder+'/calls.json'
                and patch['calls_sha256'] == sha(study/patch['calls_path'])
                and patch['fixture_sha256'] == sha(study/'inputs/patch_truth.json'), 'ABI6 startup binding')
        calls = read(study/patch['calls_path'])
        require(len(calls) == 2, 'two ABI6 calls per phase')
        for i, variant in enumerate(('full', 'fast')):
            path = folder+'/'+variant+'.npz'
            require(calls[i]['status'] == 'validated' and calls[i]['backend'] == ('C_full', 'C_fast')[i]
                    and calls[i]['seed'] == fixture['seed'] and calls[i]['raw_sha256'] == sha(study/path),
                    'startup call receipt')
            raw = load_npz(study/path, np)
            require(raw['ledger'].dtype == np.float64 and raw['ledger'].shape == (1, 107)
                    and raw['ledger'].tobytes() == np.asarray(fixture['ledger'], dtype=np.float64).tobytes(),
                    'startup107 ledger bits')
            hashes = [int(x, 16) for x in fixture['hashes']] if i == 0 else [HASH_INIT]*5
            require(raw['hashes'].dtype == np.uint64 and raw['hashes'].shape == (1, 5)
                    and raw['hashes'].tobytes() == np.asarray(hashes, dtype=np.uint64).tobytes(), 'startup5 hashes')
            artifacts[path] = sha(study/path)
        artifacts[name], artifacts[patch['calls_path']] = sha(study/name), patch['calls_sha256']


def batch(study, p, digest, world, stage, ids, hashes, binding, index, scalar, schedule, artifacts, np):
    prefix = 'endpoint_' if stage == 'endpoint' else ''
    path, scored_path = f'{prefix}raw/{world}.npz', f'{prefix}scored/{world}.npz'
    seeds = p['endpoint_seeds' if stage == 'endpoint' else 'confirmation_seeds']
    entry = index[path]
    for key, expected in (('status', 'validated'), ('stage', stage), ('world', world), ('row_ids', ids), ('abi', 6),
                          ('requested_lives', len(ids)*len(seeds)), ('lives', len(ids)*len(seeds)),
                          ('sha256', sha(study/path)), ('scored_path', scored_path),
                          ('scored_sha256', sha(study/scored_path))):
        require(entry[key] == expected, 'cohort index '+key)
    raw, scored = load_npz(study/path, np), load_npz(study/scored_path, np)
    B, n = len(ids), len(seeds)
    require(raw['ledger'].dtype == np.float64 and raw['ledger'].shape == (B*n, 107)
            and raw['hashes'].dtype == np.uint64 and raw['hashes'].shape == (B*n, 5)
            and (raw['hashes'] == HASH_INIT).all() and raw['seeds'].dtype == np.uint64
            and raw['seeds'].tolist() == seeds and raw['row_ids'].dtype == np.int64
            and raw['row_ids'].tolist() == ids and raw['genome_raw_sha256'].tolist() == hashes,
            'genotype-major cohort bytes/seeds/hash schema')
    for key, expected in (('protocol_sha256', digest), ('world_name', world), ('stage', stage),
                          ('raw_path', path), ('binding_sha256', binding)):
        require(raw[key].shape == () and raw[key].item() == expected, 'cohort metadata '+key)
    for key in ('cpu_seconds', 'wall_seconds'):
        require(raw[key].shape == () and math.isfinite(float(raw[key])) and float(raw[key]) >= 0, 'cohort timing')
    require(scored['raw_sha256'].item() == entry['sha256'], 'scored raw file binding')
    for key in ('production_F', 'native_F', 'extinct_charge'):
        require(scored[key].dtype == np.float64 and scored[key].shape == (B, n), 'scored cohort schema')
    labels, world_fields = p['worlds'][world]['ledger_columns'], p['worlds'][world]['world']
    require(p['worlds'][world]['abi'] == 6 and len(labels) == len(set(labels)) == 107, 'complete ABI6 schema')
    values, health, source_cache = [], [], {}
    for row in range(B):
        lives, status = [], []
        for life, seed in enumerate(seeds):
            ledger = raw['ledger'][row*n+life]
            endpoint = float(ledger[labels.index('t_end')])
            key = (seed, endpoint)
            if key not in source_cache:
                source_cache[key] = schedule.source_counts(world_fields, seed, endpoint)
            metric = scalar.one_life(ledger, world_fields, labels, source_cache[key])
            for name, value in (('production_F', metric['F']), ('native_F', metric['native_F']),
                                ('extinct_charge', metric['extinct_charge'])):
                require(float(scored[name][row, life]) == value, 'exact production/native/surcharge scoring')
            lives.append(metric)
            status.append(int(metric['status']))
        values.append({key: [item[key] for item in lives] for key in lives[0]})
        health.append(dict(status_counts={str(k): v for k, v in sorted(Counter(status).items())},
                           guarded=sum(bool(x & 6) for x in status), extinct=sum(bool(x & 1) for x in status),
                           all_fitness_rows_retained=n, hashes_are_fast_constants_not_trajectory_evidence=True))
    require(health == entry['health'], 'retained status counts')
    artifacts[path], artifacts[scored_path] = entry['sha256'], entry['scored_sha256']
    return values, health


def endpoint(study, p, digest, scalar, schedule, artifacts, np):
    meta = read(study/'endpoint_population.json')
    saved = load_npz(study/'endpoint_population.npz', np)
    genomes, ids = saved['genomes'], saved['ids']
    require(meta['status'] == 'complete' and meta['protocol_sha256'] == digest
            and meta['reporting_endpoint_selected'] is False and genomes.dtype == np.float32
            and genomes.shape == (32, 875) and np.isfinite(genomes).all() and ids.dtype == np.int64
            and ids.shape == (32,) and len(set(ids.tolist())) == 32 and (ids >= 0).all()
            and meta['population_raw_sha256'] == raw_sha(genomes) and meta['ids'] == ids.tolist()
            and meta['array_sha256'] == sha(study/'endpoint_population.npz'), 'all32 endpoint founder rows')
    require(set(meta['source_pins']) == {f'runs/pareto/{name}' for name in
            ('checkpoint.pt', 'population.json', 'determinism.json', 'search_complete.json')}, 'population source set')
    for name, pin in meta['source_pins'].items():
        require(sha(study/name) == pin == artifacts[name], 'population source pin '+name)
    final = load_npz(study/'runs/pareto/selection/g007.npz', np)
    selected = final['shortlist'][final['pick']]
    require(final['base_genomes'][selected].dtype == np.float32
            and final['base_genomes'][selected].tobytes() == genomes.tobytes()
            and final['candidate_ids'][selected].tolist() == ids.tolist(), 'final selection genotype/ID binding')
    index = read(study/'endpoint_index.json')
    require(set(index) == {f'endpoint_raw/{w}.npz' for w in TRAIN}, 'three endpoint cohorts')
    hashes = [raw_sha(row) for row in genomes]
    values = {w: batch(study, p, digest, w, 'endpoint', ids.tolist(), hashes, sha(study/'endpoint_population.json'),
                        index, scalar, schedule, artifacts, np)[0] for w in TRAIN}
    receipt = read(study/'endpoint_selection.json')
    require(receipt['status'] == 'complete' and receipt['protocol_sha256'] == digest
            and receipt['population_manifest_sha256'] == sha(study/'endpoint_population.json')
            and receipt['endpoint_index_sha256'] == sha(study/'endpoint_index.json')
            and receipt['genome_file_sha256'] == sha(study/'joint_genome.json'), 'frozen endpoint receipt')
    actual = receipt['selection']
    require(actual['capture_scales'] == list(SCALES) and actual['fitness_weights'] == [.5, .25, .25]
            and actual['development_only'] is True and actual['minimum_has_no_linear_SE'] is True
            and actual['endpoint_lives'] == 3072 and actual['random_draws'] == 0 and len(actual['rows']) == 32,
            'endpoint rule scope')
    keys = []
    for row, detail in enumerate(actual['rows']):
        capture = [average(values[w][row]['captures']) for w in TRAIN]
        weighted = [.5*a+.25*b+.25*c for a, b, c in
                    zip(values['patch'][row]['F'], values['pool'][row]['F'], values['persistent'][row]['F'])]
        fractions = [a/b for a, b in zip(capture, SCALES)]
        require(detail['row'] == row and detail['native_id'] == int(ids[row])
                and detail['raw_sha256'] == hashes[row] and len(detail['objectives']) == 4
                and len(detail['capture_fractions']) == 3, 'endpoint row identity')
        for observed, expected in zip(detail['objectives'], [*capture, average(weighted)]):
            close(observed, expected, 'endpoint objective')
        for observed, expected in zip(detail['capture_fractions'], fractions):
            close(observed, expected, 'endpoint fixed AO fraction')
        close(detail['joint_minimum'], min(fractions), 'endpoint minimum')
        stats(detail['weighted_F'], weighted, 'weighted endpoint F')
        require(set(detail['worlds']) == set(TRAIN), 'endpoint descriptive worlds')
        for world in TRAIN:
            require(set(detail['worlds'][world]) == set(ENDPOINT_METRICS), 'endpoint descriptive metrics')
            for metric in ENDPOINT_METRICS:
                stats(detail['worlds'][world][metric], values[world][row][metric], 'endpoint '+metric)
        keys.append((-min(fractions), -average(weighted), int(ids[row]), row))
    order = [key[3] for key in sorted(keys)]
    chosen = order[0]
    require(actual['order'] == order and actual['selected_row'] == chosen
            and actual['selected_id'] == int(ids[chosen]) and actual['selected_raw_sha256'] == hashes[chosen],
            'fresh endpoint rank and selected genotype')
    for name in ('endpoint_population.npz', 'endpoint_population.json', 'endpoint_index.json',
                 'endpoint_selection.json', 'joint_genome.json'):
        artifacts[name] = sha(study/name)
    return receipt, genomes[chosen], int(ids[chosen])


def audit(study, expected_protocol):
    start_cpu, start_wall = time.process_time(), time.perf_counter()
    import numpy as np

    require(expected_protocol == PROTOCOL == sha(study/'protocol.json'), 'explicit frozen protocol')
    digest, p = expected_protocol, read(study/'protocol.json')
    artifacts = {'terminal_accounting/check.py': sha(Path(__file__))}
    terminal(study, p, digest, artifacts)  # No partial outcomes are inspected before this gate.
    require(tuple(p['worlds']) == WORLDS and tuple(p['selection_worlds']) == TRAIN
            and p['endpoint_seeds'] == list(range(52520000, 52520032))
            and p['confirmation_seeds'] == list(range(52530000, 52530512)) and p['extinct_charge'], 'fixed panels')
    for section in ('source_pins', 'input_pins'):
        for name, pin in p[section].items():
            require(sha(study/name) == pin, 'frozen source/input '+name)
            artifacts[name] = pin
    scalar, schedule = retained_module('scalar'), retained_module('schedule')
    startup(study, p, digest, artifacts, np)
    selected, chosen, chosen_id = endpoint(study, p, digest, scalar, schedule, artifacts, np)
    references = read(study/p['references_manifest'])
    reference_genomes = np.load(study/p['reference_input'], allow_pickle=False)
    require(references['roles'] == list(ROLES[:3]) == p['reference_roles']
            and references['rows'] == p['references'] and references['shape'] == [3, 875]
            and references['dtype'] == 'float32' and reference_genomes.dtype == np.float32
            and reference_genomes.shape == (3, 875) and np.isfinite(reference_genomes).all()
            and references['raw_sha256'] == raw_sha(reference_genomes), 'fixed three references')
    genomes = np.concatenate((reference_genomes, chosen[None, :]), axis=0)
    endpoints = read(study/'endpoints.json')
    require(endpoints['roles'] == list(ROLES) and endpoints['protocol_sha256'] == digest
            and endpoints['references_manifest_sha256'] == sha(study/p['references_manifest'])
            and endpoints['endpoint_selection_sha256'] == sha(study/'endpoint_selection.json')
            and len(endpoints['genomes']) == 4, 'frozen confirmation roles')
    for row, item in enumerate(endpoints['genomes']):
        require(item['role'] == ROLES[row] and item['raw_sha256'] == raw_sha(genomes[row])
                and item['file_sha256'] == sha(study/item['path']), 'fixed confirmation genome bytes')
        if row < 3:
            require(all(item[k] == references['rows'][row][k] for k in
                        ('role', 'path', 'file_sha256', 'raw_sha256', 'native_id')), 'reference source binding')
        else:
            require(item['path'] == 'joint_genome.json' and item['native_id'] == chosen_id
                    and item['native_row'] == selected['selection']['selected_row'], 'fresh selected endpoint binding')
    expected = dict(status='complete', research_lives=15360, startup_lives=4, total_calls=15364,
        endpoint_lives=3072, confirmation_lives=12288, endpoint_batches=3, confirmation_batches=6,
        protocol_sha256=digest, endpoint_index_sha256=sha(study/'endpoint_index.json'),
        row_index_sha256=sha(study/'row_index.json'), endpoint_selection_sha256=sha(study/'endpoint_selection.json'),
        endpoints_sha256=sha(study/'endpoints.json'), startup_sha256=sha(study/'startup.json'))
    require(read(study/'measurement_complete.json') == expected, 'complete measurement marker')
    index, summary = read(study/'row_index.json'), read(study/'summary.json')
    require(set(index) == {f'raw/{w}.npz' for w in WORLDS}, 'six confirmation cohorts')
    for directory, worlds in (('endpoint_raw', TRAIN), ('endpoint_scored', TRAIN), ('raw', WORLDS), ('scored', WORLDS)):
        require({str(f.relative_to(study)) for f in (study/directory).rglob('*.npz')}
                == {f'{directory}/{w}.npz' for w in worlds}, 'exact cohort file set')
    for key, value in (('status', 'complete'), ('research_lives', 15360), ('endpoint_lives', 3072),
                       ('confirmation_lives', 12288), ('startup_lives', 4), ('paired_life_clusters', 512),
                       ('endpoint_batches', 3), ('confirmation_batches', 6), ('protocol_sha256', digest),
                       ('primary_contrast', 'depth8_joint_minus_Pareto4_joint')):
        require(summary[key] == value, 'summary scope '+key)
    for key, name in (('row_index_sha256', 'row_index.json'), ('endpoint_index_sha256', 'endpoint_index.json'),
                      ('endpoints_sha256', 'endpoints.json'), ('endpoint_selection_sha256', 'endpoint_selection.json')):
        require(summary[key] == sha(study/name), 'summary provenance')
    require(summary['endpoint_development'] == selected['selection']
            and summary['fixed_references'] == references['rows'], 'summary endpoint and references')
    require(all(set(summary[name]) == set(WORLDS) for name in ('absolute', 'paired', 'health'))
            and set(summary['old_world_retention']) == {'pool', 'persistent', 'blink80_20'}, 'summary world coverage')
    counters, groups, health = 0, 0, Counter()
    for world in WORLDS:
        values, checked = batch(study, p, digest, world, 'confirmation', list(range(4)),
            [raw_sha(row) for row in genomes], sha(study/'endpoints.json'), index, scalar, schedule, artifacts, np)
        require(summary['health'][world] == dict(zip(ROLES, checked)), 'summary status retention')
        require(set(summary['absolute'][world]) == set(ROLES)
                and set(summary['paired'][world]) == {f'depth8_joint_minus_{r}' for r in ROLES[:3]},
                'summary contrasts')
        for row, role in enumerate(ROLES):
            require(set(summary['absolute'][world][role]) == set(values[row]), 'all absolute physical metrics')
            health.update({int(k): v for k, v in checked[row]['status_counts'].items()})
            counters += 512
            for metric, panel in values[row].items():
                stats(summary['absolute'][world][role][metric], panel, 'absolute '+metric)
                groups += 1
                if row < 3:
                    pair = summary['paired'][world]['depth8_joint_minus_'+role]
                    require(set(pair) == set(values[row]), 'all paired physical metrics')
                    stats(pair[metric], [a-b for a, b in zip(values[3][metric], panel)], 'paired '+metric)
                    groups += 1
        if world in ('pool', 'persistent', 'blink80_20'):
            require(set(summary['old_world_retention'][world]) == {f'depth8_joint_vs_{r}' for r in ROLES[:3]},
                    'retention reference coverage')
            for row, role in enumerate(ROLES[:3]):
                result = summary['old_world_retention'][world]['depth8_joint_vs_'+role]
                new, old = values[3]['captures'], values[row]['captures']
                stats(result['captures_difference'], [a-b for a, b in zip(new, old)], 'retention delta')
                margin = [a-.9*b for a, b in zip(new, old)]
                stats(result['retained_90_percent_margin'], margin, 'retention90 margin')
                if average(old):
                    close(result['mean_capture_ratio'], average(new)/average(old), 'retention ratio')
                else:
                    require(result['mean_capture_ratio'] is None, 'undefined reference ratio')
                require(result['lower_3se_positive'] == (result['retained_90_percent_margin']['lower_3se'] > 0)
                        and result['diagnostic_only_not_a_gate'] is True, 'retention interpretation')
                groups += 2
    require(counters == 12288, 'all confirmation lives retained')
    artifacts.update({name: sha(study/name) for name in ('endpoints.json', 'row_index.json', 'startup.json')})
    return dict(status='passed', protocol_sha256=digest, source_sha256=sha(Path(__file__)),
        summary_sha256=sha(study/'summary.json'), search_complete_sha256=sha(study/'runs/pareto/search_complete.json'),
        checkpoint_sha256=sha(study/'runs/pareto/checkpoint.pt'), artifact_pins=artifacts,
        borrowed_sources={key: dict(path=value[0], sha256=value[1]) for key, value in BORROWED.items()},
        endpoint_ledgers_checked=3072, confirmation_ledgers_checked=counters, raw_batches=9, scored_batches=9,
        startup_calls_verified=8, original_search_research=81974, original_total_calls=97342,
        endpoint_statistic_groups=32*(1+3*len(ENDPOINT_METRICS)), confirmation_statistic_groups=groups,
        status_counts_confirmation={str(k): v for k, v in sorted(health.items())},
        selected_row=selected['selection']['selected_row'],
        selected_id=chosen_id, new_lives=0, new_builds=0, new_random_draws=0,
        resources=dict(cpu_seconds=time.process_time()-start_cpu, wall_seconds=time.perf_counter()-start_wall,
                       peak_rss_bytes=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024),
        limitations=['Reuses the prior independent scalar physical checker and existing-seed source recount.',
                     'Checkpoint files and final selection rows are bound; internals/genetics are separately audited.',
                     'Source/marker ordering establishes frozen endpoint provenance; no trajectory is replayed.',
                     'Full startup hashes are checked; research fast hashes are constants, not trajectory evidence.',
                     'Scalar fsum moments reconcile at1e-9 relative tolerance; exact native/scored F is also checked.'])


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--write', action='store_true')
    parser.add_argument('--protocol-sha256')
    args = parser.parse_args()
    if not args.write:
        print('Source only: terminal accounting requires --write and the explicit frozen protocol SHA.')
    else:
        require(args.protocol_sha256 is not None, 'explicit reviewed protocol SHA required')
        target = STUDY/'reviews/independent_accounting.json'
        require(not target.exists(), 'preserve original audit receipt; no automatic retry')
        result = audit(STUDY, args.protocol_sha256)
        with target.open('x') as file:
            json.dump(result, file, indent=2, allow_nan=False)
            file.write('\n')
        print(json.dumps({key: result[key] for key in ('status', 'selected_row', 'selected_id', 'resources')}))
