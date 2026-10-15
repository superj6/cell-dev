"""Independent AD terminal raw recount, gated on explicit root process clearance.

NumPy and the pinned corrected static accountant only. Never runs an engine or
imports the released reader/worker. Default is a source-only dry run.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import math
from pathlib import Path

import numpy as np

PROTOCOL = 'ee041636fec03ab3dc8e468b0d3427d75a2ac2736436b4dd954e3ac1c96100fe'
ACCOUNTANT = 'd088d429791673906f9200f19d982046fb49fd0f713935767e7b4d62f6854316'
WORLD = 'flash5_dark'
ROLES = ['R0', 'R1', 'I', 'A', 'B', *[f'D{i}' for i in range(8)]]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


def check(condition, message):
    if not condition:
        raise ValueError(message)


def load_npz(path):
    with np.load(path, allow_pickle=False) as data:
        check(len(data.files) == len(set(data.files)), 'duplicate NPZ field')
        return {key: data[key].copy() for key in data.files}


def same(left, right):
    return left.dtype == right.dtype and left.shape == right.shape and left.tobytes() == right.tobytes()


def finite(value, name):
    value = float(value)
    check(math.isfinite(value) and value >= 0, 'invalid timing: ' + name)
    return value


def body_check(x, candidate, world, A):
    cells = np.asarray(candidate['cells'], dtype=np.int32)
    check(np.all(x[:, A.L['n_end']] == len(cells)), 'fixed final footprint differs')
    check(np.all(x[:, A.L['n_peak']] == len(cells)), 'fixed peak footprint differs')
    check(np.array_equal(len(cells) + x[:, 7] - x[:, 10] - x[:, 11], x[:, 16]),
          'initial cells are excluded from births')
    for name, mask in [('S', cells[:, 2] == 0), ('M', cells[:, 2] == 1), ('H', cells[:, 2] >= 2)]:
        count = int(mask.sum())
        check(np.all(x[:, A.L['n_' + name + '_end']] == count), 'plane footprint differs')
        check(np.allclose(x[:, A.L['live_' + name]], count * world['T'], rtol=1e-9, atol=1e-9),
              'fixed plane live time differs')


def summarize(rows, world, A):
    """Rebuild the reader's scientific payload from retained accountant definitions."""
    accounted = {role: A.reconcile(rows[role], world) for role in ROLES}
    f = {role: rows[role][:, A.L['F']] for role in ROLES}
    reference = max(['R0', 'R1'], key=lambda role: float(f[role].mean()))
    do_less = max(ROLES[5:], key=lambda role: float(f[role].mean()))
    contrasts, vectors = {}, {}
    for left, right in [('I', 'R0'), ('I', 'R1'), ('I', 'A'), ('I', 'B'),
                        *[(role, reference) for role in ROLES[5:]]]:
        label = left + '_minus_' + right
        summary, pieces = A.paired_contrast(rows[left], rows[right], world)
        contrasts[label] = summary
        vectors.update({WORLD + '__' + label + '__' + key: value for key, value in pieces.items()})
    gap = f['I'] - f[reference]
    margins = {}
    for role in ROLES[5:]:
        gain = f[role] - f[reference]
        margin = .25 * gap - gain
        margins[role] = {'quarter_gap_minus_gain': A.mean_se(margin),
                         'fraction_of_information_gap': A.ratio_of_paired_means(gain, gap)}
        vectors[WORLD + '__quarter_margin__' + role] = margin
    means = {}
    for role in ROLES:
        x, acc = rows[role], accounted[role]
        means[role] = {'raw_columns': {name: A.mean_se(x[:, i]) for i, name in enumerate(A.RAW_LEDGER)},
                      'low_light_captures': A.mean_se(acc['low_light_captures']),
                      'bright_captures': A.mean_se(acc['bright_captures']),
                      'costs': {key: A.mean_se(value) for key, value in acc['parts'].items()},
                      'low_light_share_of_captures': A.ratio_of_paired_means(
                          acc['low_light_captures'], x[:, A.L['captures']])}
    stats = A.mean_se(gap)
    return {'rows': means, 'reference_role': reference, 'do_less_role': do_less,
            'reference_selection': 'largest whole mean; ties retain first registered role',
            'contrasts': contrasts, 'information_gap': stats, 'do_less_quarter_margins': margins,
            'information_payoff_criterion': stats['mean'] >= 1. and stats['mean'] > 3 * stats['se'],
            'do_less_quarter_criterion': stats['mean'] > 0 and float((f[do_less] - f[reference]).mean()) < .25 * stats['mean'],
            'capability_specific_admission': 'incomplete', 'gradient': 'not measured by this study'}, vectors


def review(study, result, clearance_digest):
    study, result = study.resolve(), result.resolve()
    # No raw rows or scientific result are opened before this gate succeeds.
    check(len(clearance_digest) == 64, 'explicit root terminal-clearance SHA required')
    clearance_path = study / 'terminal_process_clearance.json'
    check(sha(clearance_path) == clearance_digest, 'root clearance receipt differs')
    clearance = read(clearance_path)
    budget_path = study / 'budget.json'
    check(clearance.get('status') == 'cleared' and clearance.get('all_processes_exited') is True,
          'all owned processes must have exited')
    check(clearance['budget_sha256'] == sha(budget_path), 'terminal budget pin differs')
    budget = read(budget_path)
    check(budget.get('status') == 'complete' and budget.get('exit_code') == 0
          and not budget.get('running') and not budget.get('queued')
          and not budget.get('cleanup_error') and not budget.get('reason'), 'successful terminal budget required')
    check(clearance['processes'] == budget['process_identities']
          and clearance['process_groups'] == budget['owned_process_groups'], 'terminal process coverage differs')
    total = finite(budget['cpu_seconds'], 'total')
    validation_cpu = finite(budget['validation_cpu_seconds'], 'validation')
    check(0 <= validation_cpu < 170 and validation_cpu <= total < 2390, 'fixed stop thresholds exceeded')
    check((budget['cap_cpu_seconds'], budget['validation_cap_cpu_seconds'], budget['phase']) ==
          (2400, 180, 'research'), 'resource scope differs')
    check(budget['completed'] == [{'name': 'validation', 'exit_code': 0}, {'name': WORLD, 'exit_code': 0}],
          'exact first-attempt worker completion required')
    leaders = budget['process_identities']
    check(len(leaders) == 3 and len({x['pid'] for x in leaders}) == 3, 'exact leader coverage required')
    check([x['name'] for x in leaders] == ['monitor', 'validation', WORLD], 'leader order differs')
    monitor, children = leaders[0], leaders[1:]
    check(all(x['ppid'] == monitor['pid'] and x['pgid'] == x['pid'] for x in children)
          and budget['owned_process_groups'] == [x['pgid'] for x in children], 'worker ownership differs')
    check(read(study / 'attempt.json')['monitor'] == {k: v for k, v in monitor.items() if k != 'name'},
          'attempt monitor identity differs')
    check(sha(study / 'protocol.json') == PROTOCOL, 'protocol differs')
    p = read(study / 'protocol.json')
    ready = read(study / 'ready.json')
    check(ready['status'] == 'released' and budget['ready'] == ready, 'release differs')
    check(read(study / 'attempt.json')['ready_sha256'] == sha(study / 'ready.json'), 'attempt release pin differs')
    for name, digest in ready['source_pins'].items():
        check(sha(study / name) == digest, 'released local artifact changed: ' + name)
    for name, digest in p['file_pins'].items():
        check(ready['source_pins'].get(name) == digest, 'protocol input missing from release')
    check(ready['production_pins'] == p['production_pins'], 'production release pins differ')
    for name, digest in p['production_pins'].items():
        check(sha(study.parents[1] / name) == digest, 'production source changed: ' + name)
    accountant_path = study / 'analysis/accounting.py'
    check(sha(accountant_path) == ACCOUNTANT, 'corrected static accountant differs')
    spec = importlib.util.spec_from_file_location('AD_terminal_accounting', accountant_path)
    A = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(A)
    candidates = {row['role']: row for row in p['worlds'][WORLD]['candidates']}
    world = p['worlds'][WORLD]['base_world']
    report = read(study / 'validation/report.json')
    vb = read(study / 'validation_budget.json')
    check(vb == {'status': 'complete', 'cpu_seconds': validation_cpu, 'cap_cpu_seconds': 180,
                 'report_sha256': sha(study / 'validation/report.json'), 'protocol_sha256': PROTOCOL},
          'validation CPU receipt differs')
    check(report['status'] == 'complete' and report['simulation_calls'] == 76
          and report['protocol_sha256'] == PROTOCOL, 'validation incomplete')
    for library in report['libraries'].values():
        check(sha(study / library['path']) == library['sha256'], 'validation library changed')
        if 'generated_source' in library:
            check(sha(study / library['generated_source']) == library['generated_source_sha256'],
                  'generated controller/kernel source changed')
    expected = {}
    seeds = p['validation_seeds']
    for role in ['R0', 'R1']:
        for i, seed in enumerate(seeds[:2]):
            for tag, lib in [('scratch', 'full'), ('production', 'production')]:
                expected[f'{WORLD}_{role}_{i}_{tag}'] = (role, 1, 128, [seed], lib)
    for role in ['I', 'A', 'B']:
        for tag in ['full', 'fast']:
            expected[f'{WORLD}_{role}_{tag}'] = (role, 2, 128, seeds[:2], tag)
        for tag, seed in [('record', seeds[0]), ('same_life', seeds[0]), ('other_life', seeds[1]),
                          ('other_world', seeds[1]), ('control', seeds[1])]:
            expected[f'{WORLD}_{role}_{tag}'] = (role, 1, 128, [seed], 'replay')
    for role in ROLES:
        expected[f'{WORLD}_{role}_calibration'] = (role, 3, 1024, seeds, 'fast')
    artifact_names = set(expected) | {f'{WORLD}_{role}_replay_logs' for role in ['I', 'A', 'B']} | {'startup_identity'}
    check(set(report['artifacts']) == artifact_names, 'exact validation coverage differs')
    loaded, validation_statuses, raw_validation_cpu = {}, [], 0.
    for label, item in report['artifacts'].items():
        path = study / item['path']
        check(sha(path) == item['sha256'], 'validation artifact changed: ' + label)
        loaded[label] = read(path) if label == 'startup_identity' else load_npz(path)
    identity = loaded['startup_identity']
    check(identity['identity'] == p['expected_numerical_identity'] and identity['simulation_calls'] == 2
          and identity['numerical_identity_invocations'] == 1 and identity['protocol_sha256'] == PROTOCOL,
          'single standard identity pair differs')
    check(set(identity['identity']['kernels'].values()).issubset(
        {sha(path) for path in (study / 'build-cache').rglob('*.so')}), 'standard kernel bytes absent')
    raw_validation_cpu += finite(identity['cpu_seconds'], 'identity')
    finite(identity['wall_seconds'], 'identity wall')
    for label, (role, n, duration, ids, lib) in expected.items():
        data, item = loaded[label], report['artifacts'][label]
        check([item[k] for k in ('simulation_calls','T','seeds','library')] == [n,duration,ids,lib],
              'validation row identity differs')
        x = data['ledger']
        check(x.dtype == np.float64 and x.shape == (n,58 if lib == 'production' else 57)
              and np.isfinite(x).all(), 'validation raw shape/type differs')
        check(data['hashes'].shape == (n,5) and data['hashes'].dtype == np.uint64, 'validation hash shape differs')
        validation_statuses.extend(x[:,19].tolist())
        raw_validation_cpu += finite(data['cpu_seconds'], label)
        finite(data['wall_seconds'], label + ' wall')
        if lib != 'production':
            w = dict(world, T=duration)
            A.reconcile(x, w, n)
            body_check(x, candidates[role], w, A)
    check(sum(item['simulation_calls'] for item in report['artifacts'].values()) == 76
          and len(validation_statuses) == 74, 'validation life recount differs')
    for role in ['R0','R1']:
        for i in range(2):
            left, right = (loaded[f'{WORLD}_{role}_{i}_{tag}'] for tag in ['scratch','production'])
            columns = [j for j in range(57) if j not in (21,22)]
            check(same(left['ledger'][:,columns], right['ledger'][:,columns])
                  and same(left['ledger'][:,21], right['ledger'][:,57])
                  and same(left['hashes'][:,1:4], right['hashes'][:,1:4]), 'physical bridge differs')
    for role in ['I','A','B']:
        prefix = WORLD + '_' + role
        full, fast, recorded = (loaded[prefix + '_' + tag] for tag in ['full','fast','record'])
        check(all(same(full[key], fast[key]) for key in ['ledger','diag','latency']), 'full/fast differs')
        check(all(same(full[key][:1], recorded[key]) for key in ['ledger','hashes','diag','latency']),
              'recording changes controller outputs')
        logs = loaded[prefix + '_replay_logs']
        for tag in ['same_life','other_life','other_world']:
            check(same(logs['actions'], logs[tag]) and same(logs['callbacks'], logs[tag + '_callbacks'])
                  and loaded[prefix + '_' + tag]['diag'][0,0] == 0, 'callback replay differs')
        check(not same(logs['actions'], logs['control'])
              and report['artifacts'][prefix + '_replay_logs']['truth_calls'] == 0, 'replay control/truth differs')
    calibration = {role: float(loaded[f'{WORLD}_{role}_calibration']['cpu_seconds']) for role in ROLES}
    rates = {role: max(calibration[role]/3, p['historical_cpu_per_life'][role]) for role in ROLES}
    projected = 180 + 1.5 * 512 * sum(rates.values())
    check(report['calibration_cpu_seconds'] == calibration and report['calibration_projection']['cpu_per_life'] == rates
          and report['calibration_projection']['projected_total_cpu_seconds'] == projected
          and report['calibration_projection']['feasible'] is True and projected <= 2390,
          'fixed all-role calibration gate differs')
    rows, raw_research_cpu, raw_pins, statuses = {}, 0., {}, []
    complete = read(study / 'rows' / WORLD / 'complete.json')
    check(complete['status'] == 'complete' and complete['simulation_calls'] == 6656
          and complete['roles'] == ROLES and complete['protocol_sha256'] == PROTOCOL, 'research coverage differs')
    for role in ROLES:
        folder = study / 'rows' / WORLD / role
        check(sha(folder / 'checkpoint.json') == complete['checkpoint_pins'][role + '/checkpoint.json'],
              'checkpoint pin differs')
        checkpoint = read(folder / 'checkpoint.json')
        path = folder / 'row.npz'
        check(sha(path) == checkpoint['row_sha256'], 'research raw bytes differ')
        data = load_npz(path)
        expected_identity = {'protocol_sha256': PROTOCOL, 'world': WORLD,
                             'candidate': candidates[role], 'seeds': p['seeds']}
        check(json.loads(str(data['identity'])) == checkpoint['identity'] == expected_identity,
              'research candidate or seed identity differs')
        A.reconcile(data['ledger'], world)
        body_check(data['ledger'], candidates[role], world, A)
        rows[role] = data['ledger']
        statuses.extend(data['ledger'][:,19].tolist())
        raw_research_cpu += finite(data['cpu_seconds'], role)
        finite(data['wall_seconds'], role + ' wall')
        raw_pins[str(path.relative_to(study))] = sha(path)
    check(raw_validation_cpu <= validation_cpu + 1e-6 and raw_research_cpu <= total-validation_cpu+1e-6,
          'raw row CPU exceeds owned monitored CPU')
    scientific, vectors = summarize(rows, world, A)
    saved = read(result / 'summary.json')
    check(saved['status'] == 'complete' and saved['simulation_calls'] == 6732
          and saved['protocol_sha256'] == PROTOCOL and saved['worlds'] == {WORLD: scientific},
          'reader scientific summary differs from raw reconstruction')
    check(saved['research_lives'] == 6656 and saved['seed_ids'] == p['seeds']
          and saved['ledger_aliases'] == A.ALIASES, 'reader coverage or ledger aliases differ')
    check(saved['resources'] == {'total_cpu_seconds':total, 'validation_cpu_seconds':validation_cpu,
          'research_cpu_seconds':total-validation_cpu, 'first_attempt_only':True,
          'monitor_accounting_includes_compilation':True, 'raw_research_row_cpu_seconds':raw_research_cpu},
          'reader resource summary differs')
    check(saved['validation']['simulation_calls'] == 76 and saved['validation']['standard_golden_lives'] == 2
          and saved['validation']['raw_row_cpu_seconds'] == raw_validation_cpu,
          'reader validation recount differs')
    stored = load_npz(result / 'paired_vectors.npz')
    check(set(stored) == set(vectors) and len(vectors) == 836, '836 paired arrays required')
    check(all(same(stored[name], value) for name, value in vectors.items()), 'paired array bytes differ')
    def histogram(values):
        keys, counts = np.unique(np.asarray(values, dtype=np.int64), return_counts=True)
        return {str(int(key)): int(count) for key,count in zip(keys,counts)}
    return {'status':'passed_independent_terminal_raw_review', 'protocol_sha256':PROTOCOL,
            'clearance_sha256':clearance_digest, 'budget_sha256':sha(budget_path),
            'review_source_sha256':sha(Path(__file__)), 'accountant_sha256':ACCOUNTANT,
            'summary_sha256':sha(result / 'summary.json'), 'paired_vectors_sha256':sha(result / 'paired_vectors.npz'),
            'research_lives':len(statuses), 'validation_raw_lives':len(validation_statuses),
            'validation_scratch_lives':70, 'validation_production_lives':4,
            'recorded_standard_identity_lives':2, 'total_calls':6732,
            'research_status_histogram':histogram(statuses), 'validation_status_histogram':histogram(validation_statuses),
            'paired_arrays_bitwise_equal':836, 'scientific_summary_exact':True,
            'monitor_cpu_seconds':total, 'validation_cpu_seconds':validation_cpu,
            'raw_validation_process_cpu_seconds':raw_validation_cpu, 'raw_research_cpu_seconds':raw_research_cpu,
            'raw_row_pins':raw_pins, 'simulations':0, 'compilations':0,
            'limits':['Reuses the independently reviewed static accounting definitions, not the released reader.',
                      'The standard identity pair is evidenced by its exact recorded golden/identity and library bytes; its full ledgers are not retained.',
                      'Process teardown is grounded in the explicit root clearance receipt; nested children are owned through worker groups.',
                      'No new independent scientific observations or capability-specific memory inference.']}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', action='store_true')
    parser.add_argument('--study', type=Path)
    parser.add_argument('--result', type=Path)
    parser.add_argument('--clearance-sha256')
    parser.add_argument('--out', type=Path)
    args = parser.parse_args()
    if not args.run:
        print(json.dumps({'status':'source_only_held_until_root_terminal_clearance','simulation_calls':0,
                          'opened_runtime_artifacts':0,'planned_research_lives':6656,'planned_validation_lives':76}))
    else:
        if any(value is None for value in [args.study,args.result,args.clearance_sha256,args.out]):
            parser.error('--run requires study, result, clearance-sha256 and a new output path')
        receipt = review(args.study,args.result,args.clearance_sha256)
        with args.out.open('x') as stream:
            stream.write(json.dumps(receipt,indent=2) + '\n')
        print(json.dumps({'status':receipt['status'],'receipt_sha256':sha(args.out)}))
