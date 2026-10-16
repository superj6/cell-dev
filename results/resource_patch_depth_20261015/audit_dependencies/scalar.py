"""Independent scalar accounting of completed saved rows; no lives, builds or random draws.

The measurement/analyzer modules are never imported. Recorded genetic replay uses the
separately root-reviewed helper; this is not a second genetic implementation.
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
from pathlib import Path

os.environ['OMP_NUM_THREADS'] = '1'
os.environ['OPENBLAS_NUM_THREADS'] = '1'
os.environ['MKL_NUM_THREADS'] = '1'
os.environ['ATEN_CPU_CAPABILITY'] = 'avx2'
sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
STUDY = HERE.parent
EXPECTED_PROTOCOL = '529d65718fce28b8b9a521ab5edabca81390d190514e71bde79903d57431d8dd'
ROLES = ('AO_start', 'patch8_start', 'mean4', 'pareto4')
PHASES = ('mean', 'pareto', 'confirmation')
PAIRS = (('pareto4', 'mean4'), ('mean4', 'patch8_start'), ('pareto4', 'patch8_start'),
         ('mean4', 'AO_start'), ('pareto4', 'AO_start'), ('patch8_start', 'AO_start'))
WORLDS = ('patch', 'pool', 'persistent', 'blink80_20', 'transfer')
COSTS = (('maintenance', 'c_live', 'live_time'), ('spikes', 'c_spike', 'spikes'),
         ('twitch', 'c_tw', 'kappa_sum'), ('messages', 'c_msg', 'contact_events'),
         ('division', 'c_div', 'claims'), ('secretion', 'c_sec', 'sec_int'),
         ('misses', 'c_miss', 'misses'), ('receptors', 'c_rec', 'rec_gain'))
PATCH_STEMS = ('stock_open', 'source', 'supply', 'spill', 'harvest', 'empty', 'stock_end',
               'initial_harvest', 'refill_harvest')
COUNTS = ('spikes contact_events claims births rejects rejects_wall deaths kills n_end n_peak events beats '
          'arrivals arrivals_dropped packets chem_clamps ticks captures misses clicks b2_clicks respawns nudges '
          'rec_cand rec_accept rec_events samples zone_samples n_S_end n_M_end n_H_end low_light_captures').split()
SIGNED = {'net', 'F', 't_end', 'last_birth', 't_ext', 'X_end', 'Y_end'}


def read(path):
    return json.loads(Path(path).read_text())


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def equal(a, b, where):
    if a != b:
        raise ValueError(f'{where}: {a!r} != {b!r}')


def close(a, b, where):
    if not (math.isfinite(a) and math.isfinite(b)) or abs(a-b) > 1e-9*max(1., abs(b)):
        raise ValueError(f'{where}: {a!r} != {b!r}')


def scalar_statistics(values):
    n = len(values)
    if n != 512 or not all(math.isfinite(x) for x in values):
        raise ValueError('512 finite paired scalar values required')
    mean = math.fsum(values)/n
    se = math.sqrt(math.fsum((x-mean)**2 for x in values)/(n-1)/n)
    return dict(n=n, mean=mean, se=se, lower_3se=mean-3*se, upper_3se=mean+3*se,
                positive_above_3se=mean > 3*se, bounds_are_descriptive=True)


def verify_tree(actual, expected, where='summary'):
    """Count and compare every reconstructed numerical summary leaf; no NumPy reducers."""
    if isinstance(expected, dict):
        equal(set(actual), set(expected), where+' keys')
        return sum(verify_tree(actual[k], v, where+'.'+k) for k, v in expected.items())
    if isinstance(expected, list):
        equal(len(actual), len(expected), where+' length')
        return sum(verify_tree(a, b, where) for a, b in zip(actual, expected))
    if isinstance(expected, bool) or expected is None or isinstance(expected, str):
        equal(actual, expected, where)
        return 0
    close(float(actual), float(expected), where)
    return 1


def terminal_proof(study, protocol, artifacts):
    """Bind the original owned execution, cumulative caps and phase receipts."""
    digest = sha(study/'protocol.json')
    release = read(study/'release.json')
    equal(release['status'], 'released', 'release')
    equal(release['protocol_sha256'], digest, 'released protocol')
    budget, attempt = read(study/'budget.json'), read(study/'attempt.json')
    equal(budget['status'], 'complete', 'terminal overall budget')
    equal(budget['protocol_sha256'], digest, 'budget protocol')
    equal(budget['attempt_sha256'], sha(study/'attempt.json'), 'attempt binding')
    equal(budget['release_sha256'], sha(study/'release.json'), 'budget release')
    equal(attempt['budget'], protocol['budget'], 'attempt budget')
    equal(attempt['protocol_sha256'], digest, 'attempt protocol')
    equal(attempt['release_sha256'], sha(study/'release.json'), 'attempt release')
    equal(budget['pid_namespace'], attempt['pid_namespace'], 'overall PID namespace')
    equal(attempt['pid_namespace'], release['pid_namespace'], 'released PID namespace')
    equal(release['actual_input_review_sha256'], sha(study/'reviews/actual_input_review.json'),
          'released actual-input review')
    equal(release['launch_source_sha256'], sha(study/'release_and_run.py'), 'launcher source')
    equal(release['launch_source_sha256'], protocol['source_pins']['release_and_run.py'], 'frozen launcher')
    review = read(study/'reviews/actual_input_review.json')
    equal(review['status'], 'passed', 'actual-input review')
    equal(review['protocol_sha256'], digest, 'actual-input review protocol')
    amendment = read(study/'reviews/actual_input_review_amendment.json')
    equal(amendment['status'], 'passed_source_review_metadata_correction', 'review metadata correction')
    equal(amendment['protocol_sha256'], digest, 'review correction protocol')
    equal(amendment['scientific_retry'], False, 'no scientific retry')
    for key in ('new_lives', 'new_builds', 'new_genetic_draws'):
        equal(amendment[key], 0, 'metadata correction '+key)
    for name, pin in amendment['pins'].items():
        equal(sha(study/name), pin, 'preserved metadata-review history '+name)
        artifacts[name] = pin
    # This study has a reviewed launcher from the outset, not the preceding study's
    # namespace-omission launch failure. Preserve only its actual metadata-review history.
    source_review = read(study/'reviews/preparation_source_review.json')
    for key in ('review_amendment', 'launcher_amendment', 'rankzero_clarification_amendment'):
        earlier = source_review[key]
        equal(sha(study/earlier['prior_receipt']), earlier['prior_receipt_sha256'], 'prior source-review receipt')
        artifacts[earlier['prior_receipt']] = earlier['prior_receipt_sha256']
    for name in ('reviews/actual_input_review.json', 'reviews/actual_input_review_amendment.json',
                 'reviews/preparation_source_review.json', 'release_and_run.py'):
        artifacts[name] = sha(study/name)
    equal(budget['exit_code'], 0, 'overall exit')
    for used, cap in ((budget['cpu_seconds'], 5280), (budget['wall_seconds'], 3480),
                      (budget['search_cpu_seconds'], 4080), (budget['confirmation_cpu_seconds'], 1200)):
        if not 0 <= used < cap:
            raise ValueError('terminal resource cap exceeded')
    close(budget['search_cpu_seconds']+budget['confirmation_cpu_seconds'], budget['cpu_seconds'], 'phase CPU sum')
    monitor = attempt['monitor']
    equal(budget['process_identities'][0], dict(monitor, name='monitor'), 'overall monitor')
    workers = {row['name']: row for row in budget['process_identities'][1:]}
    equal(set(workers), set(PHASES), 'owned worker phases')
    equal(set(budget['phase_records']), set(PHASES), 'phase coverage')
    recorded_ppids = [monitor['ppid']]
    for phase in PHASES:
        record = budget['phase_records'][phase]
        equal(record['path'], f'execution/{phase}/budget.json', 'phase budget location')
        equal(sha(study/record['path']), record['sha256'], 'phase budget pin')
        phase_budget = read(study/record['path'])
        attempt_path = study/f'execution/{phase}/attempt.json'
        phase_attempt = read(attempt_path)
        equal(phase_budget['status'], 'complete', 'phase completion')
        equal(phase_budget['worker_exit_code'], 0, 'phase worker exit')
        equal(phase_budget['protocol_sha256'], digest, 'phase protocol')
        equal(phase_budget['release_sha256'], sha(study/'release.json'), 'phase release')
        equal(phase_budget['attempt_sha256'], sha(attempt_path), 'phase attempt')
        equal(phase_budget['pid_namespace'], attempt['pid_namespace'], 'phase PID namespace')
        equal(phase_attempt['pid_namespace'], attempt['pid_namespace'], 'phase attempt namespace')
        equal(phase_attempt['command'], attempt['commands'][phase], 'owned phase command')
        equal(phase_budget['process_identities'][0], dict(phase_attempt['monitor'], name='monitor'), 'phase monitor')
        for field in ('pid', 'pgid', 'start_ticks'):
            equal(phase_attempt['monitor'][field], monitor[field], 'stable monitor '+field)
        recorded_ppids.append(phase_attempt['monitor']['ppid'])
        observed = phase_budget['process_identities'][1]
        equal(observed, dict(workers[phase], name='worker'), 'phase worker identity')
        equal(observed['ppid'], monitor['pid'], 'worker parent')
        equal(observed['pid'], observed['pgid'], 'owned worker session')
        equal(phase_budget['owned_process_groups'], [observed['pgid']], 'phase owned group')
        if not any(row['pid'] == observed['pid'] and row['exit_code'] == 0
                   for row in phase_budget['wait4_receipts']):
            raise ValueError('worker terminal wait4 receipt missing')
        if not (phase_budget['cpu_seconds'] < phase_budget['cap_cpu_seconds']
                and phase_budget['wall_seconds'] < phase_budget['cap_wall_seconds']
                and phase_budget['peak_owned_rss_bytes'] < 4*1024**3
                and phase_budget['available_memory_bytes'] >= 4*1024**3):
            raise ValueError('phase resource proof differs')
        artifacts[record['path']] = record['sha256']
        artifacts[str(attempt_path.relative_to(study))] = sha(attempt_path)
    for evidence in (budget, *(read(study/budget['phase_records'][phase]['path'])
                               for phase in PHASES)):
        proof = evidence['terminal_cleanup']
        for key in ('same_pid_namespace', 'all_owned_groups_exited', 'all_worker_identities_exited'):
            equal(proof[key], True, 'cleanup '+key)
        for key in ('remaining_group_members', 'remaining_worker_identities', 'remaining_descendants'):
            equal(proof[key], [], 'cleanup '+key)
        equal(evidence['running'], {}, 'terminal running workers')
        equal(evidence['queued'], [], 'terminal queued workers')
        if evidence.get('error') or evidence.get('cleanup_error') or evidence.get('reason'):
            raise ValueError('terminal execution error retained')
    complete = read(study/'study_complete.json')
    equal(complete['status'], 'complete', 'study marker')
    equal(complete['research_lives'], 30796, 'study research calls')
    equal(complete['startup_lives'], 12, 'study startup calls')
    equal(complete['total_calls'], 30808, 'study total calls')
    equal(complete['protocol_sha256'], digest, 'study protocol')
    equal(complete['measurement_complete_sha256'], sha(study/'measurement_complete.json'), 'measurement marker')
    equal(complete['search_complete_pins'],
          {arm: sha(study/f'runs/{arm}/search_complete.json') for arm in PHASES[:2]}, 'search marker')
    for arm in PHASES[:2]:
        folder = study/'runs'/arm
        marker = read(folder/'search_complete.json')
        equal(marker['status'], 'complete', 'search completion')
        equal(marker['research_lives'], 10278, 'search research calls')
        equal(marker['startup_lives'], 4, 'search startup calls')
        equal(marker['count_proof'], {'selection': 10240, 'valid': 32, 'final': 6, 'growth_half': 2,
                                     'native_evals': 1280, 'generations': 4, 'children_per_generation': 224},
              'search native call inventory')
        equal(marker['protocol_sha256'], digest, 'search protocol')
        equal(marker['release_sha256'], sha(study/'release.json'), 'search release')
        for name, pin in marker['output_pins'].items():
            equal(sha(folder/name), pin, 'search artifact '+name)
            artifacts[str((folder/name).relative_to(study))] = pin
        artifacts[str((folder/'search_complete.json').relative_to(study))] = sha(folder/'search_complete.json')
    for name in ('protocol.json', 'release.json', 'attempt.json', 'budget.json', 'study_complete.json',
                 'measurement_complete.json', 'row_index.json', 'endpoints.json', 'startup.json'):
        artifacts[name] = sha(study/name)
    return {'original_execution_complete': True, 'cpu_seconds': budget['cpu_seconds'],
            'wall_seconds': budget['wall_seconds'], 'recorded_monitor_ppids': recorded_ppids,
            'stable_monitor_identity_verified': True, 'owned_terminal_cleanup_verified': True}


def one_life(values, world, labels, sources):
    """Independently reconcile one complete scalar physical ledger and derive summary columns."""
    d = dict(zip(labels, (float(x) for x in values)))
    if len(d) != 107 or not all(math.isfinite(x) for x in d.values()):
        raise ValueError('finite complete scalar ledger required')
    for key, value in d.items():
        if key not in SIGNED and value < 0:
            raise ValueError('negative physical scalar '+key)
    integral = set(COUNTS) | {key for key in labels[58:]} | {'status'}
    if any(not d[key].is_integer() for key in integral):
        raise ValueError('fractional count')
    status = int(d['status'])
    if status & ~511 or status & (8|16|64|128):
        raise ValueError('invalid status cannot support inference')
    guard, extinct = bool(status & 6), bool(status & 1)
    start, stop, span = world['t0'], world['t0']+world['T'], world['T']-world['t_open']
    equal(world['t_open'], 0, 'full accounting window')
    if not start <= d['t_end'] <= stop or (not guard and d['t_end'] != stop):
        raise ValueError('unexplained early endpoint')
    if extinct:
        if not start <= d['t_ext'] <= d['t_end'] or d['n_end'] != 0:
            raise ValueError('extinction ledger disagreement')
    else:
        equal(d['t_ext'], -1, 'nonextinct time sentinel')
    if not start <= d['last_birth'] <= d['t_end']:
        raise ValueError('birth outside life')
    for lo, hi in (('n_end','n_peak'), ('zone_samples','samples'), ('rec_accept','rec_cand'),
                   ('rec_events','rec_accept'), ('low_light_captures','captures')):
        if d[lo] > d[hi]:
            raise ValueError(lo+' exceeds '+hi)
    equal(d['n_end'], 1+d['births']-d['deaths']-d['kills'], 'zygote census')
    equal(d['n_end'], d['n_S_end']+d['n_M_end']+d['n_H_end'], 'plane census')
    close(d['live_time'], math.fsum(d[k] for k in ('live_S','live_M','live_H')), 'plane integrated time')
    close(d['morph_secreted'], math.fsum(d[k] for k in ('morph_decayed','morph_lost',
          'morph_content_end','morph_inflight_end')), 'morphogen balance')
    equal(d['captures']+d['misses']+d['b2_clicks'], d['clicks'], 'click partition')
    equal(world['task_mode'], 0, 'task mode')
    equal(world['b2_amp'], 0, 'second blob amplitude')
    equal(world['b2_value'], 0, 'second blob price')
    equal(d['b2_clicks'], 0, 'second blob hits')
    if any(d[key] for key in labels[58:70]):
        raise ValueError('nonneutral matching counters')
    totals = {stem: math.fsum(d[f'patch_{stem}_{slot}'] for slot in range(4)) for stem in PATCH_STEMS}
    if world['patch_count']:
        capacity = world['patch_capacity']
        for slot in range(4):
            q = {stem: d[f'patch_{stem}_{slot}'] for stem in PATCH_STEMS}
            if slot >= world['patch_count'] or d['t_end'] <= start:
                if any(q.values()):
                    raise ValueError('nonzero disabled/empty-window patch')
                continue
            equal(q['stock_open'], capacity, 'opening stock')
            equal(q['source'], sources[slot], 'exact exogenous arrival count')
            if q['stock_end'] > capacity:
                raise ValueError('stock exceeds capacity')
            equal(q['source'], q['supply']+q['spill'], 'source partition')
            equal(q['stock_open']+q['supply'], q['harvest']+q['stock_end'], 'stock conservation')
            equal(q['harvest'], q['initial_harvest']+q['refill_harvest'], 'food origin partition')
            equal(q['initial_harvest'], min(capacity,q['harvest']), 'initial FIFO')
            if q['refill_harvest'] > q['supply']:
                raise ValueError('refill consumed before supply')
        equal(totals['harvest'], d['captures'], 'patch food')
        equal(totals['empty']+d['patch_geometric_misses'], d['misses'], 'empty/geometric miss partition')
        equal(d['respawns'], 0, 'persistent patch locations')
    elif any(d[key] for key in labels[70:]):
        raise ValueError('nonneutral old-world patch counters')
    if not world['visibility_mode']:
        equal(d['low_light_captures'], 0, 'neutral visibility')
    income = d['captures']*world['R_cap']
    parts = {name: world[price]*d[counter] for name,price,counter in COSTS}
    cost = math.fsum(parts.values())
    guard_cost = world['c_live']*world['n_max']*(stop-d['t_end']) if guard else 0.
    extinction = world['c_live']*(stop-max(d['t_ext'],start))/span if extinct else 0.
    close(d['income'], income, 'native income')
    close(d['cost'], cost, 'native ordinary cost')
    close(d['guard_charge'], guard_cost, 'native guard charge')
    close(d['net'], income-cost-guard_cost, 'native net')
    close(d['F'], (income-cost-guard_cost)/span, 'native F')
    metrics = dict(d)
    metrics.update(F=d['F']-extinction, native_F=d['F'], extinct_charge=extinction,
        income_contribution=income/span, ordinary_cost_contribution=-cost/span,
        guard_contribution=-guard_cost/span, extinction_contribution=-extinction)
    metrics.update({'cost__'+key: value for key,value in parts.items()})
    metrics.update({'total_patch_'+key: value for key,value in totals.items()})
    metrics.update(initial_income=world['R_cap']*totals['initial_harvest'],
        refill_income=world['R_cap']*totals['refill_harvest'],
        initial_income_contribution=world['R_cap']*totals['initial_harvest']/span,
        refill_income_contribution=world['R_cap']*totals['refill_harvest']/span,
        physical_cost=cost, guard_energy=guard_cost, extinction_energy=extinction*span,
        guarded=float(guard), extinct=float(extinct))
    return metrics


def verify_startup(study, p, spec, np, artifacts):
    fixture = read(study/'inputs/patch_truth.json')['cases'][0]
    expected_ledger = np.asarray(fixture['ledger'], dtype=np.float64)[None, :]
    expected_hashes = np.asarray([int(x,16) for x in fixture['hashes']],dtype=np.uint64)[None,:]
    for phase, name in (*((arm, f'runs/{arm}/search_startup.json') for arm in PHASES[:2]),
                        ('confirmation', 'startup.json')):
        startup = read(study/name)
        equal(startup['identity'], p['expected_numerical_identity'], 'startup numerical identity')
        equal(startup['startup_lives'],4,'startup call inventory')
        equal(startup['protocol_sha256'],EXPECTED_PROTOCOL,'startup protocol')
        patches = startup['patches']
        equal(patches['lives'],2,'ABI6 startup calls')
        equal(patches['name'],fixture['name'],'ABI6 startup fixture')
        equal(patches['seed'],fixture['seed'],'ABI6 startup seed')
        equal(patches['fixture_sha256'],sha(study/'inputs/patch_truth.json'),'ABI6 truth pin')
        folder = f'execution/{phase}/patch_truth'
        equal(patches['calls_path'],folder+'/calls.json','startup calls location')
        equal(patches['calls_sha256'],sha(study/patches['calls_path']),'startup calls pin')
        calls = read(study/patches['calls_path'])
        equal(len(calls),2,'startup raw call count')
        for i, variant in enumerate(('full','fast')):
            raw_path = folder+'/'+variant+'.npz'
            equal(calls[i]['status'],'validated','startup call status')
            equal(calls[i]['backend'],('C_full','C_fast')[i],'startup backend')
            equal(calls[i]['seed'],fixture['seed'],'startup seed')
            equal(calls[i]['raw_sha256'],sha(study/raw_path),'startup raw pin')
            with np.load(study/raw_path,allow_pickle=False) as saved:
                equal(saved['ledger'].dtype,expected_ledger.dtype,'startup ledger dtype')
                equal(saved['ledger'].shape,expected_ledger.shape,'startup ledger shape')
                equal(saved['ledger'].tobytes(),expected_ledger.tobytes(),'retained truth all107 values')
                wanted_hashes = expected_hashes if variant=='full' else np.full((1,5),spec.HASH_INIT,dtype=np.uint64)
                equal(saved['hashes'].dtype,wanted_hashes.dtype,'startup hash dtype')
                equal(saved['hashes'].shape,wanted_hashes.shape,'startup hash shape')
                equal(saved['hashes'].tobytes(),wanted_hashes.tobytes(),'startup all5 hashes')
            artifacts[raw_path] = sha(study/raw_path)
        artifacts[name] = sha(study/name)
        artifacts[patches['calls_path']] = sha(study/patches['calls_path'])


def source_counts(spec, world, seed, endpoint):
    result = []
    for slot in range(int(world['patch_count'])):
        period, first = spec.patch_source(seed,slot,world['patch_refill_fast'],world['patch_refill_slow'],world['t0'])
        n = max(0, math.ceil((endpoint-first)/period))
        while n and first+(n-1)*period >= endpoint:
            n -= 1
        while first+n*period < endpoint:
            n += 1
        result.append(n)
    return result


def run(study):
    begin_cpu, begin_wall = time.process_time(), time.perf_counter()
    import numpy as np
    import torch

    torch.set_num_threads(1)
    equal(sha(study/'protocol.json'), EXPECTED_PROTOCOL, 'frozen protocol')
    p = read(study/'protocol.json')
    equal(p['total_calls'], 30808, 'registered total calls')
    equal(p['research_lives'], 30796, 'registered research calls')
    equal(p['startup_lives'], 12, 'registered startup calls')
    equal(p['extinct_charge'], True, 'registered ordinary extinction surcharge')
    source_root = study/'production' if (study/'production/src/genome.py').exists() else study.parents[1]
    sys.path.insert(0, str(source_root))
    from src.genome import Layout
    from src.life import spec

    for name, pin in p['production_pins'].items():
        equal(sha(source_root/name), pin, 'production source '+name)
    for section in ('source_pins','input_pins'):
        for name, pin in p[section].items():
            equal(sha(study/name), pin, section+' '+name)
    artifacts = {'terminal_audit/audit_accounting.py': sha(Path(__file__))}
    terminal = terminal_proof(study,p,artifacts)
    verify_startup(study,p,spec,np,artifacts)
    equal(p['roles'], list(ROLES), 'roles')
    equal(list(p['worlds']), list(WORLDS), 'worlds')
    equal(p['seeds'], list(range(52500000,52500512)), 'fresh paired IDs')
    labels = tuple(spec.V6.LEDGER)
    equal(len(labels),107,'ABI6 size')
    endpoints = read(study/'endpoints.json')
    equal(endpoints['roles'],list(ROLES),'endpoint roles')
    equal(endpoints['protocol_sha256'],EXPECTED_PROTOCOL,'endpoint protocol')
    for i, item in enumerate(endpoints['genomes']):
        equal(item['role'],ROLES[i],'endpoint role order')
        equal(sha(study/item['path']),item['file_sha256'],'genome file')
        _, genome = Layout.load(study/item['path'])
        equal(hashlib.sha256(genome.numpy().tobytes()).hexdigest(),item['raw_sha256'],'genome raw bytes')
        artifacts[item['path']] = item['file_sha256']
    for i, reference in enumerate(p['references']):
        equal(endpoints['genomes'][i]['role'], reference['role'], 'fixed ancestor role')
        equal(endpoints['genomes'][i]['raw_sha256'], reference['raw_sha256'], 'exact ancestral endpoint')
        equal(endpoints['genomes'][i]['file_sha256'], reference['file_sha256'], 'fixed ancestor file')
    equal(endpoints['genomes'][1]['raw_sha256'],p['population_start']['row_sha256'][0], 'imported G8 rank zero')
    marker = read(study/'measurement_complete.json')
    equal(marker['status'],'complete','measurement complete')
    equal(marker['research_lives'],10240,'confirmation calls')
    equal(marker['startup_lives'],4,'confirmation startup')
    equal(marker['rows'],20,'confirmation rows')
    equal(marker['row_index_sha256'],sha(study/'row_index.json'),'row index binding')
    equal(marker['endpoints_sha256'],sha(study/'endpoints.json'),'endpoint binding')
    index = read(study/'row_index.json')
    expected_paths = {f'raw/{world}/row_{i:02d}.npz' for world in WORLDS for i in range(4)}
    equal(set(index),expected_paths,'exact raw row coverage')
    equal({str(path.relative_to(study)) for path in (study/'raw').rglob('*.npz')},expected_paths,'raw files')
    equal({str(path.relative_to(study)) for path in (study/'scored').rglob('*.npz')},
          {name.replace('raw/','scored/',1) for name in expected_paths},'scored files')
    absolute, health, all_rows = {}, {}, {}
    for world in WORLDS:
        definition = p['worlds'][world]
        equal(definition['abi'],6,'world ABI')
        equal(definition['ledger_columns'],list(labels),'world ledger schema')
        equal(spec.V6.pack_world(spec.World(**definition['world'])).tolist(),definition['world_vector'],'world vector')
        absolute[world], health[world], all_rows[world] = {}, {}, {}
        for i, role in enumerate(ROLES):
            path = f'raw/{world}/row_{i:02d}.npz'
            scored_path = path.replace('raw/','scored/',1)
            entry = index[path]
            for key, expected in (('status','validated'),('lives',512),('abi',6),('role',role),
                                  ('world',world),('sha256',sha(study/path)),('scored_path',scored_path),
                                  ('scored_sha256',sha(study/scored_path))):
                equal(entry[key],expected,'row index '+key)
            with np.load(study/path,allow_pickle=False) as data:
                native = {key:data[key].copy() for key in data.files}
            with np.load(study/scored_path,allow_pickle=False) as data:
                scored = {key:data[key].copy() for key in data.files}
            equal(native['ledger'].shape,(512,107),'ledger shape')
            equal(str(native['ledger'].dtype),'float64','ledger dtype')
            equal(native['hashes'].shape,(512,5),'hash shape')
            equal(str(native['hashes'].dtype),'uint64','hash dtype')
            if not np.all(native['hashes'] == spec.HASH_INIT):
                raise ValueError('fast hashes are not declared constants')
            equal(str(native['seeds'].dtype),'uint64','seed dtype')
            equal(native['seeds'].tolist(),p['seeds'],'row seed order')
            for key, expected in (('world_name',world),('role',role),('raw_path',path),
                  ('genome_raw_sha256',endpoints['genomes'][i]['raw_sha256']),
                  ('protocol_sha256',EXPECTED_PROTOCOL),('endpoints_sha256',sha(study/'endpoints.json'))):
                equal(native[key].shape,(),'scalar metadata')
                equal(native[key].item(),expected,'row metadata '+key)
            for key in ('cpu_seconds','wall_seconds'):
                equal(native[key].shape,(),'scalar timing')
                if not math.isfinite(float(native[key])) or float(native[key]) < 0:
                    raise ValueError('invalid row timing')
                close(float(native[key]),entry[key],'indexed row timing')
            equal(scored['raw_sha256'].item(),entry['sha256'],'scored/native binding')
            rows = [one_life(row,definition['world'],labels,
                    source_counts(spec,definition['world'],int(seed),float(row[labels.index('t_end')])))
                    for row,seed in zip(native['ledger'],native['seeds'])]
            vectors = {key:[row[key] for row in rows] for key in rows[0]}
            for key, source in (('production_F','F'),('native_F','native_F'),('extinct_charge','extinct_charge')):
                expected = np.asarray(vectors[source],dtype=np.float64)
                equal(scored[key].dtype,expected.dtype,'scored dtype')
                equal(scored[key].shape,expected.shape,'scored shape')
                equal(scored[key].tobytes(),expected.tobytes(),'bitwise scored '+key)
            counts = {}
            for row in rows:
                code = str(int(row['status']))
                counts[code] = counts.get(code,0)+1
            health[world][role] = dict(status_counts=counts, guarded=sum(int(row['guarded']) for row in rows),
                extinct=sum(int(row['extinct']) for row in rows),all_fitness_rows_retained=512,
                hashes_are_fast_constants_not_trajectory_evidence=True)
            equal(entry['health'],health[world][role],'row health')
            absolute[world][role] = {key:scalar_statistics(value) for key,value in vectors.items()}
            all_rows[world][role] = vectors
            artifacts[path], artifacts[scored_path] = sha(study/path),sha(study/scored_path)
    paired = {world:{new+'_minus_'+old:{key:scalar_statistics([a-b for a,b in zip(
              all_rows[world][new][key],all_rows[world][old][key])]) for key in all_rows[world][new]}
              for new,old in PAIRS} for world in WORLDS}
    retention = {}
    for world in ('pool','persistent','blink80_20'):
        retention[world] = {}
        old = all_rows[world]['AO_start']['captures']
        for role in ('mean4','pareto4'):
            new = all_rows[world][role]['captures']
            margin = scalar_statistics([a-.9*b for a,b in zip(new,old)])
            retention[world][role+'_vs_AO_start'] = dict(
                captures_difference=scalar_statistics([a-b for a,b in zip(new,old)]),
                retained_90_percent_margin=margin,
                mean_capture_ratio=None if math.fsum(old)==0 else math.fsum(new)/math.fsum(old),
                lower_3se_positive=margin['lower_3se']>0,diagnostic_only_not_a_gate=True)
    summary = read(study/'summary.json')
    equal(set(summary),{'status','research_lives','startup_lives','paired_life_clusters','absolute','paired','health',
                       'old_world_retention','primary_contrast','protocol_sha256','row_index_sha256',
                       'endpoints_sha256','limitations'},
          'complete summary schema')
    expected = dict(status='complete',research_lives=10240,startup_lives=4,paired_life_clusters=512,
                    absolute=absolute,paired=paired,health=health,old_world_retention=retention,
                    primary_contrast='pareto4_minus_mean4',
                    protocol_sha256=EXPECTED_PROTOCOL,row_index_sha256=sha(study/'row_index.json'),
                    endpoints_sha256=sha(study/'endpoints.json'))
    numeric = verify_tree({key:summary[key] for key in expected},expected)
    if not isinstance(summary['limitations'],list) or not all(isinstance(x,str) for x in summary['limitations']):
        raise ValueError('summary limitations missing')
    artifacts['summary.json'] = sha(study/'summary.json')

    # Existing source-reviewed recorded-operation replay, explicitly separate from scalar accounting above.
    module_spec = importlib.util.spec_from_file_location('resource_recorded_replay',study/'native_replay.py')
    module = importlib.util.module_from_spec(module_spec)
    module_spec.loader.exec_module(module)
    replay = module.complete_replay(study,p)
    equal(replay['offspring_replayed'],1792,'recorded offspring')
    equal(replay['point_additions_replayed'],3584,'recorded additions')
    equal(replay['all_32_final_rows_bound_per_arm'],True,'recorded final populations')
    equal(replay['all_scored_candidate_rows_bound'],True,'all scored genotype rows')
    equal(replay['first_cohort_bitwise_equal'],True,'common initial candidates')
    target = study/'native_replay_result.json'
    if target.exists():
        equal(read(target),replay,'existing genetic replay receipt')
    else:
        with target.open('x') as stream:
            json.dump(replay,stream,indent=2,allow_nan=False)
            stream.write('\n')
    artifacts['native_replay_result.json'] = sha(target)
    return dict(status='passed',protocol_sha256=EXPECTED_PROTOCOL,row_index_sha256=sha(study/'row_index.json'),
        summary_sha256=sha(study/'summary.json'),raw_batches=20,scored_batches=20,confirmation_lives=10240,
        native_ledger_values=10240*107,hash_values=10240*5,scored_values_checked_bitwise=10240*3,
        summary_numeric_values_checked=numeric,all_native_ledger_and_hash_bytes_bound=True,
        comparison='Independent scalar math.fsum means/sample variances/paired differences; relative1e-9 numerical tolerance.',
        terminal_execution=terminal,genetics={'implementation':'Reused root-reviewed native_replay.py/replay_ops.py; not independently reimplemented.',
        'offspring_replayed':1792,'point_additions_replayed':3584,'all32_final_rows_per_arm':True,
        'first_cohort_bitwise_equal':replay['first_cohort_bitwise_equal'],
        'selection_replay_reuses_registered_selector':True},
        artifacts=artifacts,new_lives=0,new_builds=0,new_genetic_draws=0,
        resources=dict(cpu_seconds=time.process_time()-begin_cpu,wall_seconds=time.perf_counter()-begin_wall,
                       max_rss_KiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,threads=1))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run',action='store_true')
    parser.add_argument('--study',type=Path,default=STUDY)
    args = parser.parse_args()
    if not args.run:
        print('source only: independent completed saved-data accounting; no lives/builds/draws')
    else:
        result = run(args.study.resolve())
        output = args.study/'reviews/independent_accounting.json'
        with output.open('x') as stream:
            json.dump(result,stream,indent=2,allow_nan=False)
            stream.write('\n')
        print(json.dumps({key:result[key] for key in ('status','confirmation_lives','summary_numeric_values_checked','resources')}))
