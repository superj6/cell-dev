"""Independent saved-array recount. Never imports a simulator or the frozen reader."""
from pathlib import Path
import hashlib
import json
import math
import os
import resource
import sys
import time
import traceback

HERE = Path(__file__).resolve().parent
STUDY = HERE.parent / 'prelaunch'
EXPECTED_PROTOCOL = 'da37b12819a8377832e97561eebc9e1a04e1e0847e45bdf157b2fa58ff6ef78a'
ROLES = ('I', 'E', 'P', 'N', 'B', 'R0', 'R1', 'D0', 'D1', 'D2', 'D3')
METRICS = ('choice_opportunities', 'choice_carry_in', 'correct_choices',
           'wrong_choices', 'choice_timeouts', 'unfinished_choices')
CLASSES = ('narrow', 'broad')
PRICE_TERMS = (('maintenance', 'c_live', 'live_time'), ('spikes', 'c_spike', 'spikes'),
               ('twitch', 'c_tw', 'kappa_sum'), ('messages', 'c_msg', 'contact_events'),
               ('division', 'c_div', 'claims'), ('secretion', 'c_sec', 'sec_int'),
               ('misses', 'c_miss', 'misses'), ('receptors', 'c_rec', 'rec_gain'))


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


def save(name, value):
    with (HERE / name).open('x') as stream:
        json.dump(value, stream, indent=2, allow_nan=False)
        stream.write('\n')


def require(condition, message):
    if not condition:
        raise AssertionError(message)


def close(actual, expected, name, tolerance=1e-11):
    require(math.isfinite(actual) and math.isfinite(expected), 'nonfinite ' + name)
    require(abs(actual - expected) <= tolerance * max(1., abs(expected)),
            f'{name}: actual={actual!r}, expected={expected!r}')


def bits(a, b, name):
    require(a.shape == b.shape and a.dtype == b.dtype and a.tobytes() == b.tobytes(), name)


def compare(actual, expected, label):
    """Compare independently reconstructed numeric fields, allowing roundoff only."""
    if isinstance(expected, dict):
        for key, value in expected.items():
            require(key in actual, label + ': missing ' + key)
            compare(actual[key], value, label + '.' + key)
    elif isinstance(expected, bool) or expected is None or isinstance(expected, str):
        require(actual == expected, label)
    elif isinstance(expected, (int, float)):
        close(float(actual), float(expected), label)
    else:
        require(actual == expected, label)


def stats(values):
    values = [float(v) for v in values]
    n = len(values)
    mean = math.fsum(values) / n
    se = math.sqrt(math.fsum((x - mean)**2 for x in values) / (n * (n - 1)))
    return {'n': n, 'mean': mean, 'se': se}


def available():
    return next(int(line.split()[1]) * 1024 for line in Path('/proc/meminfo').read_text().splitlines()
                if line.startswith('MemAvailable:'))


def recount(receipt, started):
    # Completion gate precedes all outcome reads, including selection and row index.
    budget = read(STUDY / 'budget.json')
    marker = read(STUDY / 'measurement_complete.json')
    require(budget['status'] == marker['status'] == 'complete', 'study is not complete')
    require(not (STUDY / 'measurement_incomplete.json').exists(), 'incomplete marker present')
    require(budget['worker_exit_code'] == 0 and budget['exit_code'] == 0, 'worker exit')
    proof = budget['terminal_cleanup']
    require(proof['same_pid_namespace'] and proof['all_owned_groups_exited']
            and proof['all_worker_identities_exited'] and not proof['remaining_descendants'], 'cleanup')
    require(not budget['running'] and not budget['queued'], 'ongoing work')
    require(budget['cpu_seconds'] < budget['cap_cpu_seconds']
            and budget['wall_seconds'] < budget['cap_wall_seconds']
            and budget['peak_owned_rss_bytes'] < budget['cap_rss_bytes']
            and budget['available_memory_bytes'] >= budget['minimum_available_bytes'], 'run bounds')
    require(sha(STUDY / 'protocol.json') == EXPECTED_PROTOCOL, 'protocol pin')
    protocol = read(STUDY / 'protocol.json')
    require(protocol['cumulative_budget']['prior_allocated_cpu_seconds'] + budget['cpu_seconds'] + 60. < 3600.,
            'insufficient cumulative CPU headroom for bounded audit')
    receipt['completion_pins_at_start'] = {name: sha(STUDY / name) for name in
        ('protocol.json', 'budget.json', 'measurement_complete.json', 'row_index.json', 'summary.json')}
    for name, key in (('protocol.json', 'protocol_sha256'), ('row_index.json', 'row_index_sha256'),
                      ('summary.json', 'summary_sha256'), ('selected_arms.json', 'selected_arms_sha256')):
        require(sha(STUDY / name) == marker[key], 'completion pin ' + name)
    require(marker['backend_calls'] == 6656 and marker['development_calls'] == 1024
            and marker['confirmation_calls'] == 5632 and marker['total_package_calls'] == 6696,
            'call inventory')
    for group, base in (('input_pins', STUDY), ('source_pins', STUDY),
                        ('production_pins', STUDY.parents[2])):
        for name, digest in protocol[group].items():
            require(sha(base / name) == digest, 'changed ' + name)
    inputs = read(STUDY / 'inputs.json')
    index = read(STUDY / 'row_index.json')
    published = read(STUDY / 'summary.json')
    selection = read(STUDY / 'selection.json')
    arms = read(STUDY / 'selected_arms.json')
    names = protocol['ledger_columns']
    require(len(names) == 70 and len(set(names)) == 70, 'ledger names')
    col = {name: i for i, name in enumerate(names)}
    world = protocol['world']
    devseeds = list(range(52440000, 52440064))
    confseeds = list(range(52450000, 52450512))
    require(protocol['development_seeds'] == devseeds and protocol['confirmation_seeds'] == confseeds,
            'seed arrays')
    candidates = inputs['reflex_panel'] + inputs['instrument_panel']
    require(len(candidates) == 16 and tuple(protocol['roles']) == ROLES, 'panels')
    schedule = [('development', seed, entry['id'], 'tissue' if j < 12 else 'instrument')
                for seed in devseeds for j, entry in enumerate(candidates)]
    schedule += [('confirmation', seed, role, 'instrument' if role in ROLES[:5] else 'tissue')
                 for seed in confseeds for role in ROLES]
    require(len(index) == len(schedule) == 6656, 'row count')
    require(len({r['path'] for r in index}) == 6656, 'duplicate paths')
    require({p.name for p in (STUDY / 'raw').glob('*.npz')} ==
            {Path(r['path']).name for r in index}, 'raw file inventory')
    import numpy as np
    dev = np.empty((16, 64))
    ledgers = {role: [] for role in ROLES}
    diagnostics = {role: [] for role in ROLES}
    manifests = []
    maxima = {'cost': 0., 'guard_charge': 0., 'F': 0., 'net': 0.}
    pair = {}
    ep_pairs = ie_prefixes = 0
    statuses = {}
    backends = {'tissue': 0, 'instrument': 0}
    for n, (row, expected) in enumerate(zip(index, schedule)):
        receipt['current_row'] = {'index': n, 'path': row.get('path')}
        if n % 128 == 0:
            require(available() >= 4 * 1024**3, 'audit host headroom')
            require(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss < 512 * 1024, 'audit RSS')
            require(time.monotonic() - started < 120., 'audit wall limit')
        stage, seed, role, backend = expected
        require(row['index'] == n and row['status'] == 'complete'
                and (row['stage'], row['seed'], row['role'], row['backend']) == expected,
                f'schedule row {n}')
        relative = f'raw/{stage}_{seed}_{role}.npz'
        require(row['path'] == relative, 'raw path')
        path = STUDY / relative
        digest = sha(path)
        require(digest == row['sha256'], 'raw digest ' + relative)
        manifests.append({'path': relative, 'sha256': digest})
        with np.load(path, allow_pickle=False) as saved:
            require(set(saved.files) == {'ledger', 'hashes', 'diag', 'raster_t', 'raster_uid', 'raster_n',
                                         'fate_i', 'fate_f', 'fate_n', 'seed'}, 'raw schema')
            x = {key: saved[key] for key in saved.files}
        require(x['seed'].shape == () and x['seed'].dtype == np.dtype('uint64')
                and int(x['seed']) == seed, 'saved seed')
        require(x['ledger'].shape == (1, 70) and x['ledger'].dtype == np.dtype('float64'), 'ledger shape')
        require(x['hashes'].shape == (1, 5) and x['hashes'].dtype == np.dtype('uint64'), 'hash shape')
        require(x['diag'].shape == (1, 16) and np.isfinite(x['diag']).all(), 'diagnostics')
        require(np.isfinite(x['ledger']).all(), 'nonfinite ledger')
        a = x['ledger'][0]
        get = lambda key: float(a[col[key]])
        status = get('status')
        require(status == int(status) and 0 <= status < 512 and not (int(status) & (8 | 16 | 64 | 128)),
                'invalid native status')
        statuses[str(int(status))] = statuses.get(str(int(status)), 0) + 1
        backends[backend] += 1
        require(world['t0'] <= get('t_end') <= world['t0'] + world['T'], 'terminal time')
        for cls in CLASSES:
            counts = [get(metric + '_' + cls) for metric in METRICS]
            require(all(v >= 0 and v == int(v) for v in counts), 'noninteger class counter')
            require(sum(counts[:2]) == sum(counts[2:]), 'class conservation')
        correct = sum(get('correct_choices_' + cls) for cls in CLASSES)
        wrong = sum(get('wrong_choices_' + cls) for cls in CLASSES)
        require(get('income') == 500 * correct, 'correct-choice income')
        cost = math.fsum(world[price] * get(key) for _, price, key in PRICE_TERMS) + 50 * wrong
        guard = world['c_live'] * world['n_max'] * (world['t0'] + world['T'] - get('t_end')) \
            if int(status) & (2 | 4) else 0.
        net = get('income') - cost - guard
        for key, expected_value in (('cost', cost), ('guard_charge', guard), ('net', net),
                                    ('F', net / world['T'])):
            maxima[key] = max(maxima[key], abs(get(key) - expected_value))
            close(get(key), expected_value, relative + ':' + key, 1e-9)
        for prefix in ('raster', 'fate'):
            count = x[prefix + '_n']
            require(count.shape == (1,) and count.dtype == np.dtype('int64') and count[0] >= 0,
                    prefix + ' count')
        nr, nf = int(x['raster_n'][0]), int(x['fate_n'][0])
        require(x['raster_t'].shape == x['raster_uid'].shape == (nr,), 'raster count/shape')
        require(x['fate_i'].shape == (nf, 7) and x['fate_f'].shape == (nf, 18), 'fate count/shape')
        require(np.isfinite(x['raster_t']).all() and np.isfinite(x['fate_f']).all(), 'nonfinite logs')
        require(np.all(np.diff(x['raster_t']) >= 0) and np.all(x['raster_t'] >= world['t0'])
                and np.all(x['raster_t'] <= get('t_end')), 'raster chronology')
        if backend == 'instrument':
            require(x['diag'][0, 15] == 0., 'instrument numeric failure')
        if stage == 'development':
            dev[n % 16, n // 16] = get('F')
        else:
            ledgers[role].append(a)
            diagnostics[role].append(x['diag'][0])
            if role in ('I', 'E', 'P'):
                pair[role] = x
            if role == 'P':
                e, p, i = pair['E'], pair['P'], pair['I']
                for key in ('ledger', 'hashes', 'raster_t', 'raster_uid', 'raster_n', 'fate_i', 'fate_f', 'fate_n'):
                    bits(e[key], p[key], f'E/P {seed}: {key}')
                bits(e['diag'][:, 6:], p['diag'][:, 6:], f'E/P {seed}: diagnostics')
                bits(i['diag'][:, 5:6], e['diag'][:, 5:6], f'I/E {seed}: sample statistic')
                im, em = i['raster_t'] < 65.5, e['raster_t'] < 65.5
                for key in ('raster_t', 'raster_uid'):
                    bits(i[key][im], e[key][em], f'I/E {seed}: prefix {key}')
                ep_pairs += 1
                ie_prefixes += 1
                pair.clear()
    require(backends == {'tissue': 3840, 'instrument': 2816}, 'backend totals')
    means = dev.mean(axis=1)
    for n, value in enumerate(means):
        close(selection['development_mean_F'][n], float(value), 'selection mean')
    # Match the declared native-array mean operation, then Python first-maximum tie order.
    ri = max(range(12), key=lambda j: means[j])
    ii = max(range(4), key=lambda j: means[12 + j])
    require(selection['reflex_index'] == ri and selection['instrument_index'] == ii
            and selection['tie_rule'] == 'first table row' and selection['no_confirmation_observed'] is True,
            'selection/tie policy')
    expected_arms = {role: {'controller': 10 + n, 'parameters': inputs['instrument_panel'][ii]['parameters']}
                     for n, role in enumerate(ROLES[:5])}
    expected_arms.update(R0={'body': inputs['R0']}, R1={'body': inputs['reflex_panel'][ri]['body']})
    expected_arms.update({role: {'body': body} for role, body in inputs['do_less_by_reflex'][ri].items()})
    require(arms == expected_arms, 'selected actual arm definitions')
    ledgers = {role: np.asarray(rows) for role, rows in ledgers.items()}
    diagnostics = {role: np.asarray(rows) for role, rows in diagnostics.items()}
    get = lambda role, key: ledgers[role][:, col[key]]
    fs = {role: get(role, 'F') for role in ROLES}
    contrasts = {}
    for ref in ('R0', 'R1', 'E', 'N', 'B'):
        value = stats(fs['I'] - fs[ref])
        value['pass_1F_3SE'] = value['mean'] >= 1. and value['mean'] > 3 * value['se']
        contrasts['I-' + ref] = value
    margins = {}
    for ref in ('R0', 'R1'):
        for d in ('D0', 'D1', 'D2', 'D3'):
            value = stats(.25 * fs['I'] + .75 * fs[ref] - fs[d])
            value.update(point_pass=value['mean'] > 0, lower_three_se=value['mean'] - 3 * value['se'],
                         do_less_gain=stats(fs[d] - fs[ref]))
            margins[ref + '/' + d] = value
    roles = {}
    for role in ROLES:
        status_values = [int(s) for s in get(role, 'status')]
        entry = {'F': stats(fs[role]), 'status_counts': {str(s): status_values.count(s) for s in set(status_values)},
                 'ledger_means': {name: math.fsum(get(role, name)) / 512 for name in names}, 'classes': {}}
        components = {name: world[price] * math.fsum(get(role, key)) / 512 for name, price, key in PRICE_TERMS}
        components['wrong_choices'] = 50 * math.fsum(get(role, 'wrong_choices_' + cls).sum() for cls in CLASSES) / 512
        components['guard'] = math.fsum(get(role, 'guard_charge')) / 512
        entry['physical_cost_component_means'] = components
        for cls in CLASSES:
            c = {metric: int(sum(get(role, metric + '_' + cls))) for metric in METRICS}
            opportunities = c['choice_opportunities'] + c['choice_carry_in']
            completed = c['correct_choices'] + c['wrong_choices']
            c.update(correct_per_opportunity=c['correct_choices'] / opportunities if opportunities else None,
                     completion_coverage=completed / opportunities if opportunities else None,
                     accuracy_among_completed=c['correct_choices'] / completed if completed else None,
                     gross_reward_per_opportunity=(500 * c['correct_choices'] - 50 * c['wrong_choices']) /
                     opportunities if opportunities else None,
                     narrow_hits=c['correct_choices'] if cls == 'narrow' else c['wrong_choices'],
                     broad_hits=c['wrong_choices'] if cls == 'narrow' else c['correct_choices'])
            entry['classes'][cls] = c
        if role in ROLES[:5]:
            require(np.all(get(role, 'choice_opportunities_narrow') + get(role, 'choice_opportunities_broad') <= 1),
                    'multiple instrument opportunities')
            attempts = [float(x) for x in diagnostics[role][:, 10] if x > 0.]
            entry['attempted_tap_callback_count'] = len(attempts)
            entry['attempted_tap_callback_mean'] = math.fsum(attempts) / len(attempts) if attempts else None
        roles[role] = entry
    labeled = [(int(n), float(logit)) for n, b, logit in zip(get('I', 'choice_opportunities_narrow'),
               get('I', 'choice_opportunities_broad'), diagnostics['I'][:, 5]) if n + b == 1]
    losses, errors, right = [], [], []
    for y, logit in labeled:
        prob = 1 / (1 + math.exp(-logit)) if logit >= 0 else math.exp(logit) / (1 + math.exp(logit))
        z = -(2 * y - 1) * logit
        losses.append(max(z, 0) + math.log1p(math.exp(-abs(z))))
        errors.append((prob - y)**2)
        right.append(int((logit >= 0) == y))
    count = len(labeled)
    calibration = {'n': count, 'missing': 512 - count,
                   'class_counts': {'narrow': sum(y for y, _ in labeled), 'broad': sum(1 - y for y, _ in labeled)},
                   'brier': math.fsum(errors) / count if count else None,
                   'log_loss': math.fsum(losses) / count if count else None,
                   'sample_class_accuracy': sum(right) / count if count else None}
    passed = all(contrasts['I-' + role]['pass_1F_3SE'] for role in ('R0', 'R1', 'E')) \
        and all(value['point_pass'] for value in margins.values())
    reconstructed = {'status': 'complete', 'paired_life_clusters': 512, 'contrasts': contrasts,
                     'do_less_margins': margins, 'roles': roles, 'sample_calibration': calibration,
                     'E_P_full_bitwise_identity': True, 'section_0_4_thresholds_met': passed}
    compare(published, reconstructed, 'summary')
    require(ep_pairs == ie_prefixes == 512, 'paired audit coverage')
    for name, digest in receipt['completion_pins_at_start'].items():
        require(sha(STUDY / name) == digest, 'terminal input changed during audit: ' + name)
    save('raw_manifest.json', manifests)
    save('reconstructed.json', reconstructed)
    pin_names = ('protocol.json', 'release.json', 'attempt.json', 'budget.json', 'measurement_complete.json',
                 'row_index.json', 'summary.json', 'selection.json', 'selected_arms.json', 'inputs.json', 'seeds.json')
    receipt.update(status='passed', completed_rows=6656, development_rows=1024, confirmation_rows=5632,
                   confirmation_seed_clusters=512, E_P_bitwise_pairs=ep_pairs, I_E_prefix_pairs=ie_prefixes,
                   backends=backends, status_counts=statuses, accounting_max_absolute_error=maxima,
                   selection={'reflex_index': ri, 'instrument_index': ii,
                              'reflex_tied_max_indices': [j for j in range(12) if means[j] == means[ri]],
                              'instrument_tied_max_indices': [j for j in range(4) if means[12+j] == means[12+ii]]},
                   exact_pins={name: sha(STUDY / name) for name in pin_names},
                   raw_manifest_sha256=sha(HERE / 'raw_manifest.json'),
                   reconstructed_sha256=sha(HERE / 'reconstructed.json'),
                   scientific_worker_cpu_seconds=budget['cpu_seconds'],
                   prior_allocated_cpu_seconds=protocol['cumulative_budget']['prior_allocated_cpu_seconds'],
                   section_0_4_thresholds_met=passed)


def main():
    os.environ['OPENBLAS_NUM_THREADS'] = '1'
    os.environ['OMP_NUM_THREADS'] = '1'
    resource.setrlimit(resource.RLIMIT_CPU, (60, 60))
    resource.setrlimit(resource.RLIMIT_AS, (2 * 1024**3, 2 * 1024**3))
    started = time.monotonic()
    receipt = {'status': 'started', 'audit_source_sha256': sha(__file__), 'new_simulator_calls': 0,
               'new_builds': 0, 'new_random_draws': 0}
    require(not (HERE / 'audit_receipt.json').exists(), 'audit already attempted; no automatic retry')
    try:
        recount(receipt, started)
    except BaseException as error:
        receipt.update(status='failed', error=repr(error), traceback=traceback.format_exc())
    usage = resource.getrusage(resource.RUSAGE_SELF)
    receipt.update(cpu_seconds=usage.ru_utime + usage.ru_stime, wall_seconds=time.monotonic() - started,
                   peak_rss_kib=usage.ru_maxrss)
    if receipt['status'] == 'passed':
        receipt['cumulative_package_cpu_including_audit'] = receipt['prior_allocated_cpu_seconds'] \
            + receipt['scientific_worker_cpu_seconds'] + receipt['cpu_seconds']
        if receipt['cumulative_package_cpu_including_audit'] >= 3600.:
            receipt.update(status='failed', error='cumulative package CPU exceeded')
    save('audit_receipt.json', receipt)
    print(json.dumps(receipt, indent=2))
    return 0 if receipt['status'] == 'passed' else 1


if __name__ == '__main__':
    sys.exit(main())
