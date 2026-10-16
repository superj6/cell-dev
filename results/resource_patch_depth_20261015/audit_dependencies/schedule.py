"""Saved-data checks only: scalar physical recount, seed-cluster summaries and descriptive ranks.

Reuses the previously reviewed independent scalar ledger checker by exact SHA. Neither
population analyzer nor its borrowed accounting module is imported. No engine is loaded.
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
PROTOCOL = '6fb2a4f9744ff15377346bde4b2d7af42a7e12087e5f9d2d9cc622af7a5ee33f'
BORROWED = 'results/resource_patch_selection_20261015/terminal_audit/audit_accounting.py'
BORROWED_SHA = 'dbc493e5752e9703c80063ebfb28b7119bc52cbf567af85dcc5c5bc20be02a75'
GROUPS = {'G8': range(32), 'mean4': range(32, 64), 'pareto4': range(64, 96), 'AO': range(96, 97)}
WORLDS = ('patch', 'pool', 'persistent', 'blink80_20', 'transfer')
SCALES = (19.046875, 16.029296875, 5.919921875)
HASH_INIT = 0x243F6A8885A308D3
# Check the acquisition and complete energy decomposition, rather than rebuild every descriptive output.
METRICS = ('captures', 'F', 'native_F', 'income', 'cost', 'guard_charge', 'extinct_charge',
           'total_patch_initial_harvest', 'total_patch_refill_harvest', 'total_patch_empty',
           'patch_geometric_misses', 'total_patch_source', 'total_patch_supply', 'total_patch_spill',
           'total_patch_stock_end', 'initial_income', 'refill_income')
METRICS += tuple('cost__'+name for name in
                 ('maintenance', 'spikes', 'twitch', 'messages', 'division', 'secretion', 'misses', 'receptors'))


def read(path):
    return json.loads(Path(path).read_text())


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def raw_sha(array):
    return hashlib.sha256(array.tobytes()).hexdigest()


def require(condition, where):
    if not condition:
        raise ValueError(where)


def close(a, b, where):
    require(math.isfinite(a) and math.isfinite(b) and abs(a-b) <= 1e-9*max(1., abs(b)), where)


def mean(values):
    return math.fsum(values)/len(values)


def check_stats(actual, values, where):
    require(len(values) == 32 and actual['n'] == 32, where+' shared-seed clusters')
    avg = mean(values)
    se = math.sqrt(math.fsum((x-avg)**2 for x in values)/31/32)
    for key, value in (('mean', avg), ('se', se), ('lower_3se', avg-3*se), ('upper_3se', avg+3*se)):
        close(actual[key], value, where+' '+key)
    require(actual['positive_above_3se'] == (avg > 3*se)
            and actual['bounds_are_descriptive'] is True, where+' descriptive flags')


def source_counts(world, seed, endpoint):
    """Recount the existing fixed source schedule; no new seed, RNG state or life is generated."""
    mask = (1 << 64)-1

    def mix(x):
        x = (x+0x9E3779B97F4A7C15) & mask
        x = ((x ^ (x >> 30))*0xBF58476D1CE4E5B9) & mask
        x = ((x ^ (x >> 27))*0x94D049BB133111EB) & mask
        return x ^ (x >> 31)

    def fixed_uniform(stream, slot):
        h = mix(seed ^ mix(stream))
        h = mix(h ^ slot)
        h = mix(h)  # final existing key is zero
        return float((h >> 11) | 1)*2.0**-53

    counts = []
    for slot in range(world['patch_count']):
        period = world['patch_refill_fast'] if fixed_uniform(32, slot) < .5 else world['patch_refill_slow']
        first = world['t0']+period*fixed_uniform(33, slot)
        if first <= world['t0']:
            first = math.nextafter(world['t0'], math.inf)
        n = max(0, math.ceil((endpoint-first)/period))
        while n and first+(n-1)*period >= endpoint:
            n -= 1
        while first+n*period < endpoint:
            n += 1
        counts.append(n)
    return counts


def terminal(study, protocol, artifacts):
    marker, complete, budget = (read(study/name) for name in
                               ('measurement_complete.json', 'study_complete.json', 'budget.json'))
    require(marker == dict(status='complete', research_lives=15520, startup_lives=4, total_calls=15524,
                          batches=20, genomes=97, genome_world_rows=485, lives_per_genome_world=32,
                          protocol_sha256=PROTOCOL, row_index_sha256=sha(study/'row_index.json'),
                          rows_manifest_sha256=sha(study/protocol['rows_input']),
                          startup_sha256=sha(study/'startup.json')), 'complete measurement matrix')
    require(complete['status'] == budget['status'] == 'complete'
            and complete['protocol_sha256'] == budget['protocol_sha256'] == PROTOCOL
            and complete['research_lives'] == 15520 and complete['startup_lives'] == 4
            and complete['total_calls'] == 15524, 'terminal call ownership')
    for key, name in (('measurement_complete_sha256', 'measurement_complete.json'),
                      ('summary_sha256', 'summary.json'), ('budget_sha256', 'budget.json'),
                      ('execution_budget_sha256', 'execution/budget.json')):
        require(complete[key] == sha(study/name), 'terminal pin '+name)
    require(sha(study/'budget.json') == sha(study/'execution/budget.json'), 'owned budget copy')
    require(budget['worker_exit_code'] == 0 and not budget['error'] and not budget['cleanup_error']
            and not budget['reason'] and not budget['queued'] and not budget['running'], 'owned worker complete')
    proof = budget['terminal_cleanup']
    require(all(proof[k] for k in ('same_pid_namespace', 'all_owned_groups_exited', 'all_worker_identities_exited'))
            and not any(proof[k] for k in
                        ('remaining_group_members', 'remaining_worker_identities', 'remaining_descendants')),
            'owned processes clear')
    for used, cap in (('cpu_seconds', 'cpu_seconds'), ('wall_seconds', 'wall_seconds'),
                      ('peak_owned_rss_bytes', 'rss_bytes')):
        require(0 <= budget[used] < protocol['runtime_budget'][cap], 'execution cap '+used)
    require(budget['available_memory_bytes'] >= protocol['runtime_budget']['minimum_available_bytes'],
            'terminal host memory reserve')
    for name in ('protocol.json', 'summary.json', 'measurement_complete.json', 'study_complete.json',
                 'budget.json', 'execution/budget.json', 'execution/attempt.json', 'release.json', 'row_index.json'):
        artifacts[name] = sha(study/name)


def check_startup(study, protocol, np, artifacts):
    startup = read(study/'startup.json')
    fixture = read(study/'inputs/patch_truth.json')['cases'][0]
    require(startup['identity'] == protocol['expected_numerical_identity'] and startup['startup_lives'] == 4
            and startup['protocol_sha256'] == PROTOCOL, 'retained startup identity and calls')
    patch = startup['patches']
    require(patch['lives'] == 2 and patch['name'] == fixture['name'] and patch['seed'] == fixture['seed']
            and patch['fixture_sha256'] == sha(study/'inputs/patch_truth.json')
            and patch['calls_path'] == 'startup_truth/calls.json'
            and patch['calls_sha256'] == sha(study/patch['calls_path']), 'startup ABI6 binding')
    calls = read(study/patch['calls_path'])
    require(len(calls) == 2, 'startup full/fast inventory')
    for i, backend in enumerate(('full', 'fast')):
        name = 'startup_truth/'+backend+'.npz'
        require(calls[i]['status'] == 'validated' and calls[i]['backend'] == ('C_full', 'C_fast')[i]
                and calls[i]['seed'] == fixture['seed'] and calls[i]['raw_sha256'] == sha(study/name),
                'retained startup result')
        with np.load(study/name, allow_pickle=False) as raw:
            require(raw['ledger'].dtype == np.float64 and raw['ledger'].shape == (1, 107)
                    and raw['ledger'].tobytes() == np.asarray(fixture['ledger'], dtype=np.float64).tobytes(),
                    'retained startup ledger bits')
            wanted = [int(x, 16) for x in fixture['hashes']] if i == 0 else [HASH_INIT]*5
            require(raw['hashes'].dtype == np.uint64 and raw['hashes'].shape == (1, 5)
                    and raw['hashes'].tobytes() == np.asarray(wanted, dtype=np.uint64).tobytes(),
                    'retained startup hashes')
        artifacts[name] = sha(study/name)
    for name in ('startup.json', patch['calls_path']):
        artifacts[name] = sha(study/name)


def check_ranks(study, rows, values, summary, np):
    for group, indices in GROUPS.items():
        actual = summary['descriptive_orders'][group]
        fresh, cached = [], None
        ids = [rows[i]['native_id'] for i in indices]
        for i in indices:
            weighted = [.5*a+.25*b+.25*c for a, b, c in
                        zip(values['patch'][i]['F'], values['pool'][i]['F'], values['persistent'][i]['F'])]
            fresh.append([mean(values[w][i]['captures']) for w in WORLDS[:3]]+[mean(weighted)])
            detail = actual['rows'][i-indices.start]
            check_stats(detail['training_weighted_F'], weighted, 'training weighted F')
            require(detail['index'] == i and detail['label'] == rows[i]['label']
                    and detail['native_id'] == ids[i-indices.start]
                    and detail['reported_endpoint'] == rows[i]['reported_endpoint'], 'fixed row annotation')

        def order(table, ids=tuple(ids)):
            keys = [(-min(row[k]/SCALES[k] for k in range(3)), -row[3], ids[local], local)
                    for local, row in enumerate(table)]
            return [item[3] for item in sorted(keys)]

        fresh_order = order(fresh)
        require(actual['fresh_order_local_rows'] == fresh_order and not actual['replaces_reporting_endpoint'],
                'fresh descriptive order')
        if group in ('mean4', 'pareto4'):
            folder = study/'inputs/cached'/group
            last = json.loads((folder/'lineage.jsonl').read_text().splitlines()[-1])
            endpoint = read(folder/'endpoint_selection.json')
            require(last['gen'] == 3 and last['survivors'] == ids
                    and last['selection']['sha256'] == endpoint['selection_sha256'] == sha(folder/'g003.npz'),
                    'cached survivor order and selection pin')
            with np.load(folder/'g003.npz', allow_pickle=False) as saved:
                cached = []
                for local, i in enumerate(indices):
                    short_row = int(saved['pick'][local])
                    candidate = int(saved['shortlist'][short_row])
                    require(int(saved['candidate_ids'][candidate]) == rows[i]['native_id']
                            and raw_sha(saved['base_genomes'][candidate]) == rows[i]['raw_sha256'],
                            'cached genotype/ID row binding')
                    cap = saved['base_captures'][candidate].tolist()+saved['recheck_captures'][short_row].tolist()
                    fit = saved['base_production_F'][candidate].tolist()
                    fit += saved['recheck_production_F'][short_row].tolist()
                    require(len(cap) == len(fit) == 16, 'pooled16 rows')
                    cached.append([mean([cap[j] for j in range(16) if (0, 1, 0, 2)[j % 4] == w])
                                   for w in range(3)]+[mean(fit)])
            require(actual['cached16_order_local_rows'] == order(cached) == endpoint['selection']['order']
                    and rows[indices.start+endpoint['rank']]['reported_endpoint'], 'cached order/endpoint')
            for a, b in zip(endpoint['selection']['objectives'], cached):
                for x, y in zip(a, b):
                    close(x, y, 'cached16 endpoint objectives')
            require(actual['cached_source_pins'] == {str(p.relative_to(study)): sha(p) for p in
                    (folder/'g003.npz', folder/'lineage.jsonl', folder/'endpoint_selection.json')}, 'cache pins')
        require(actual['cached_capture_table_available'] == (cached is not None), 'cache availability')
        if cached is None:
            require(actual['cached16_order_local_rows'] is None, 'no invented G8/AO cache')
        for local, detail in enumerate(actual['rows']):
            for observed, expected in zip(detail['fresh_objectives'], fresh[local]):
                close(observed, expected, 'fresh objectives')
            for k in range(3):
                close(detail['fresh_capture_fractions'][k], fresh[local][k]/SCALES[k], 'fixed AO fractions')
            close(detail['fresh_joint_minimum'], min(fresh[local][k]/SCALES[k] for k in range(3)), 'joint minimum')
            require(detail['fresh_descriptive_rank'] == fresh_order.index(local), 'fresh rank')
            if cached is not None:
                for observed, expected in zip(detail['cached16_objectives'], cached[local]):
                    close(observed, expected, 'cached16 objectives')
                rank = order(cached).index(local)
                require(detail['cached16_rank'] == rank and detail['rank_change'] == fresh_order.index(local)-rank,
                        'descriptive cached/fresh rank change')


def review(study):
    started_cpu, started_wall = time.process_time(), time.perf_counter()
    import numpy as np

    require(sha(study/'protocol.json') == PROTOCOL, 'registered protocol pin')
    p = read(study/'protocol.json')
    require(p['groups'] == list(GROUPS) and tuple(p['worlds']) == WORLDS
            and p['seeds'] == list(range(52510000, 52510032)) and p['extinct_charge'], 'fixed panel')
    artifacts = {'terminal_review/independent_review.py': sha(Path(__file__))}
    terminal(study, p, artifacts)  # Refuse all interim outcomes before reading any raw/summary data.
    for section in ('input_pins', 'source_pins'):
        for name, pin in p[section].items():
            require(sha(study/name) == pin, 'frozen input/source '+name)
            artifacts[name] = pin
    require(sha(ROOT/BORROWED) == BORROWED_SHA, 'previous independent scalar checker pin')
    descriptor = importlib.util.spec_from_file_location('retained_independent_scalar_audit', ROOT/BORROWED)
    scalar = importlib.util.module_from_spec(descriptor)
    descriptor.loader.exec_module(scalar)
    check_startup(study, p, np, artifacts)
    manifest, summary, index = (read(study/name) for name in (p['rows_input'], 'summary.json', 'row_index.json'))
    rows = manifest['rows']
    require(summary['row_manifest'] == rows and len(rows) == 97 and summary['status'] == 'complete'
            and summary['protocol_sha256'] == PROTOCOL, 'summary fixed manifest')
    genomes = np.load(study/p['genome_input'], allow_pickle=False)
    require(genomes.dtype == np.float32 and genomes.shape == (97, 875)
            and raw_sha(genomes) == manifest['raw_sha256'], 'complete genotype table')
    expected_paths = {f'raw/{world}/{group}.npz' for world in WORLDS for group in GROUPS}
    require(set(index) == expected_paths
            and {str(f.relative_to(study)) for f in (study/'raw').rglob('*.npz')} == expected_paths,
            'exact20 raw cohort files')
    require({str(f.relative_to(study)) for f in (study/'scored').rglob('*.npz')}
            == {x.replace('raw/', 'scored/', 1) for x in expected_paths}, 'exact20 scored cohort files')
    values, statuses, checked = {}, Counter(), 0
    for world in WORLDS:
        values[world] = {}
        definition = p['worlds'][world]
        labels, physics = definition['ledger_columns'], definition['world']
        require(definition['abi'] == 6 and len(labels) == 107, 'ABI6 schema')
        for group, indices in GROUPS.items():
            path, scored_path = f'raw/{world}/{group}.npz', f'scored/{world}/{group}.npz'
            entry = index[path]
            for key, expected in (('status', 'validated'), ('requested_lives', len(indices)*32), ('abi', 6),
                                  ('group', group), ('world', world), ('row_indices', list(indices)),
                                  ('lives', len(indices)*32), ('sha256', sha(study/path)),
                                  ('scored_path', scored_path), ('scored_sha256', sha(study/scored_path))):
                require(entry[key] == expected, 'cohort index '+key)
            with np.load(study/path, allow_pickle=False) as raw_file, \
                    np.load(study/scored_path, allow_pickle=False) as scored_file:
                raw = {key: raw_file[key] for key in raw_file.files}
                s = {key: scored_file[key] for key in scored_file.files}
                require(raw['ledger'].dtype == np.float64 and raw['ledger'].shape == (len(indices)*32, 107)
                        and raw['hashes'].dtype == np.uint64 and raw['hashes'].shape == (len(indices)*32, 5)
                        and (raw['hashes'] == HASH_INIT).all(), 'native cohort schema/fast constants')
                require(raw['seeds'].dtype == np.uint64 and raw['seeds'].tolist() == p['seeds']
                        and raw['row_indices'].dtype == np.int64 and raw['row_indices'].tolist() == list(indices)
                        and raw['genome_raw_sha256'].tolist() == [rows[i]['raw_sha256'] for i in indices]
                        and s['raw_sha256'].item() == entry['sha256'], 'cohort seed/genotype/scoring bindings')
                for key, expected in (('raw_path', path), ('world_name', world), ('group', group),
                                      ('protocol_sha256', PROTOCOL),
                                      ('rows_manifest_sha256', sha(study/p['rows_input']))):
                    require(raw[key].shape == () and raw[key].item() == expected, 'raw metadata '+key)
                for key in ('production_F', 'native_F', 'extinct_charge'):
                    require(s[key].dtype == np.float64 and s[key].shape == (len(indices), 32), 'scored schema')
                for local, i in enumerate(indices):
                    row = rows[i]
                    require(row['index'] == i and row['group'] == group and row['row'] == local
                            and row['raw_sha256'] == raw_sha(genomes[i]), 'genome-major manifest order')
                    lives, status = [], []
                    for j, seed in enumerate(p['seeds']):
                        ledger = raw['ledger'][local*32+j]
                        sources = source_counts(physics, seed, float(ledger[labels.index('t_end')]))
                        metric = scalar.one_life(ledger, physics, labels, sources)
                        for key, value in (('production_F', metric['F']), ('native_F', metric['native_F']),
                                           ('extinct_charge', metric['extinct_charge'])):
                            require(float(s[key][local, j]) == value, 'native/scored exact F and surcharge')
                        lives.append(metric)
                        status.append(int(metric['status']))
                    values[world][i] = {key: [life[key] for life in lives] for key in METRICS}
                    statuses.update(status)
                    health = dict(status_counts={str(k): v for k, v in sorted(Counter(status).items())},
                                  guarded=sum(bool(x & 6) for x in status), extinct=sum(bool(x & 1) for x in status),
                                  all_fitness_rows_retained=32, hashes_are_fast_constants_not_trajectory_evidence=True)
                    require(entry['health'][local] == summary['health'][world][row['label']] == health,
                            'native status/retention counts')
                    checked += 32
            artifacts[path], artifacts[scored_path] = entry['sha256'], entry['scored_sha256']
    stats_checked = 0
    for world in WORLDS:
        population = {}
        for i, row in enumerate(rows):
            for key in METRICS:
                panel = values[world][i][key]
                check_stats(summary['absolute'][world][row['label']][key], panel, 'individual '+key)
                stats_checked += 1
                if i < 96:
                    delta = [a-b for a, b in zip(panel, values[world][96][key])]
                    check_stats(summary['paired_minus_AO'][world][row['label']][key], delta, 'paired AO '+key)
                    stats_checked += 1
        for group, indices in GROUPS.items():
            population[group] = {}
            for key in METRICS:
                panel = [mean([values[world][i][key][seed] for i in indices]) for seed in range(32)]
                population[group][key] = panel
                check_stats(summary['population_means'][world][group][key], panel, 'seed-cluster population '+key)
                stats_checked += 1
        for new, old in (('mean4', 'G8'), ('pareto4', 'G8'), ('pareto4', 'mean4')):
            for key in METRICS:
                delta = [a-b for a, b in zip(population[new][key], population[old][key])]
                check_stats(summary['population_paired'][world][new+'_minus_'+old][key], delta,
                            'paired seed-cluster populations '+key)
                stats_checked += 1
        if world in ('pool', 'persistent', 'blink80_20'):
            reference = values[world][96]['captures']
            for i in range(96):
                actual = summary['old_world_retention'][world][rows[i]['label']]
                panel = values[world][i]['captures']
                require(actual['diagnostic_only_not_a_gate'], 'retention remains descriptive')
                if mean(reference):
                    close(actual['mean_capture_ratio'], mean(panel)/mean(reference), 'descriptive retention ratio')
                else:
                    require(actual['mean_capture_ratio'] is None, 'undefined zero-reference ratio')
                check_stats(actual['paired_90_percent_margin'], [a-.9*b for a, b in zip(panel, reference)],
                            'paired retention margin')
                stats_checked += 1
    check_ranks(study, rows, values, summary, np)
    require(checked == 15520, 'all scientific rows retained')
    return dict(status='passed', protocol_sha256=PROTOCOL, summary_sha256=sha(study/'summary.json'),
                source_sha256=sha(Path(__file__)), borrowed_scalar_source=dict(path=BORROWED, sha256=BORROWED_SHA),
                artifact_pins=artifacts, raw_batches=20, scored_batches=20, genome_world_rows=485,
                research_rows_checked=checked, retained_startup_calls=4, total_original_calls=15524,
                native_status_counts={str(k): v for k, v in sorted(statuses.items())},
                summary_metrics_checked=list(METRICS), statistics_checked=stats_checked,
                ranking_rows_checked=97, cached_rows_checked=64, shared_seed_clusters=32,
                new_lives=0, new_builds=0, new_seed_or_genetic_draws=0,
                resources=dict(cpu_seconds=time.process_time()-started_cpu,
                               wall_seconds=time.perf_counter()-started_wall,
                               peak_rss_bytes=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024),
                limitations=['Reuses the retained independent scalar checker; not a second implementation of it.',
                             'Hash-keyed schedules are recounted on existing seeds; no new random sample is drawn.',
                             'Checks 25 acquisition/energy summaries, statuses and ranks; other metrics are omitted.',
                             'Fast hashes are constants, not trajectory replay evidence.',
                             'All ordering remains development-only; no endpoint replacement or winner certification.'])


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--write', action='store_true')
    args = parser.parse_args()
    if not args.write:
        print('source only: --write requires the completed owned study')
    else:
        target = STUDY/'reviews/independent_review.json'
        require(not target.exists(), 'one saved-data audit attempt; preserve previous receipts')
        result = review(STUDY)
        with target.open('x') as stream:
            json.dump(result, stream, indent=2, allow_nan=False)
            stream.write('\n')
        keys = ('status', 'research_rows_checked', 'statistics_checked', 'resources')
        print(json.dumps({k: result[k] for k in keys}))
