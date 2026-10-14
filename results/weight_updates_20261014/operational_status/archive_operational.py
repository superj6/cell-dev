"""Archive R's unstarted dependency failure while preserving all prospective bytes; no lives."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import shutil
import subprocess
from pathlib import Path

ROOT = next(p for p in Path(__file__).resolve().parents if (p / 'src/genome.py').exists())
NAMES = {'R': 'weight_updates', 'Q': 's7_hidden', 'P': 'next_step'}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + '\n')


def verify(folder, records):
    for relative, record in records.items():
        path = folder / relative
        assert sha(path) == record['sha256'] and path.stat().st_size == record['bytes'], relative


def check(folder):
    record = read(folder / 'provenance.json')
    assert record['status'] == 'dependency_failed_before_measurement'
    verify(folder, record['artifacts'])
    verify(folder.parent, read(folder / 'preserved_files.json')['artifacts'])
    summary = read(folder / 'summary.json')
    assert summary['research_lives'] == summary['validation_lives'] == 0
    assert summary['scientific_outcome'] is None
    return record


def archive():
    work = {label: ROOT / f'outputs/autonomous_{name}_20261014' for label, name in NAMES.items()}
    budgets = {label: read(folder / 'budget.json') for label, folder in work.items()}
    for label, value in budgets.items():
        cap = 14400 if label == 'P' else 3600
        assert value['cap_cpu_seconds'] == cap and math.isfinite(value['cpu_seconds'])
        assert 0 < value['cpu_seconds'] < cap and not value['running'] and not value['queued']
    for label in ('R', 'Q'):
        assert budgets[label]['status'] == 'monitor_failed' and budgets[label]['error'] == 'ValueError'
    assert budgets['P']['status'] == 'incomplete' and budgets['P']['reason'] == 'cpu_budget_exhausted'
    assert budgets['P']['exit_code'] == 1
    absent = {name: not (work['R'] / name).exists() for name in ('measurement', 'run.log')}
    assert all(absent.values())
    host_dir = ROOT / 'outputs/wrapup_review_20261014'
    host, exits = read(host_dir / 'host_exit_review.json'), read(host_dir / 'session_exits.json')
    assert host['status'] == 'all_released_monitors_and_workers_exited'
    assert not host['remaining_owned_or_research_processes']
    assert host['session_exits_sha256'] == sha(host_dir / 'session_exits.json')
    for label, name in NAMES.items():
        assert exits[label]['exit_code'] == 1
        assert host['budgets'][name]['sha256'] == sha(work[label] / 'budget.json')
        assert host['budgets'][name]['record'] == budgets[label]
    assert 'dependency stopped abnormally; inspect before R launch' in exits['R']['output']
    assert 'dependency stopped abnormally; inspect before Q launch' in exits['Q']['output']
    for label, predecessor in (('R', 'Q'), ('Q', 'P')):
        ready, protocol = read(work[label] / 'ready.json'), read(work[label] / 'protocol.json')
        assert ready == budgets[label]['ready'] and ready['dependencies'] == protocol['dependencies']
        assert set(ready['files']) == {
            'protocol.json', 'prepare.py', 'measure.py', 'run_budgeted.py', 'test_measure.py', 'PREREG.md'}
        for name, expected in ready['files'].items():
            assert sha(work[label] / name) == expected
        dependency = str(work[predecessor].relative_to(ROOT))
        assert set(ready['dependencies']) == {dependency}
        for name, expected in ready['dependencies'][dependency].items():
            assert sha(work[predecessor] / name) == expected
        for name, expected in protocol['source_identity'].items():
            assert sha(ROOT / name) == expected
    public = ROOT / 'results/weight_updates_20261014'
    target, offline = public / 'operational_status', public / 'offline_analysis_preparation'
    assert not target.exists(), 'operational archive cannot overwrite existing evidence'
    expected = [(public, 109, '2512ae9c36f3775b18184deaa1d8a2721eed96d92c0da65231507af795c0a981'),
                (offline, 40, '926c02d5811b0727f7138c6e3cd2d5f4bb946f1895276baaa8863fa72f81f917')]
    preserved = {}
    for folder, count, digest in expected:
        assert sha(folder / 'provenance.json') == digest
        record = read(folder / 'provenance.json')
        assert len(record['artifacts']) == count
        verify(folder, record['artifacts'])
        for name, item in record['artifacts'].items():
            preserved[str((folder / name).relative_to(public))] = item
        path = folder / 'provenance.json'
        preserved[str(path.relative_to(public))] = {'sha256': sha(path), 'bytes': path.stat().st_size}
    assert len(preserved) == 151
    for name, item in preserved.items():
        path = str((public / name).relative_to(ROOT))
        blob = subprocess.check_output(['git', 'show', ':' + path], cwd=ROOT)
        assert hashlib.sha256(blob).hexdigest() == item['sha256']
    assert sha(work['R'] / 'analyze.py') == sha(offline / 'analyze.py')
    gate = json.loads(subprocess.check_output([str(ROOT / '.venv/bin/python'), str(work['R'] / 'analyze.py'),
                                              '--study', str(work['R'])], cwd=ROOT))
    assert gate == {'status': 'incomplete', 'budget_status': 'monitor_failed'}
    files = {'R/' + name: work['R'] / name for name in
             (*read(work['R'] / 'ready.json')['files'], 'ready.json', 'budget.json')}
    for label in ('Q', 'P'):
        files.update({label + '/' + name: work[label] / name for name in
                      ('protocol.json', 'run_budgeted.py', 'ready.json', 'budget.json')})
    files.update({'host/' + name: host_dir / name for name in ('host_exit_review.json', 'session_exits.json')})
    files['archive_operational.py'] = Path(__file__)
    files['review/analysis_review.json'] = Path(__file__).with_name('analysis_review.json')
    original = {name: sha(path) for name, path in files.items()}
    for name, source in files.items():
        destination = target / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, destination)
        assert sha(destination) == original[name]
    save(target / 'preserved_files.json', {'status': 'passed', 'preparation_artifacts': 109,
         'offline_artifacts': 40, 'git_index_blobs_verified': 151, 'artifacts': preserved})
    summary = {'status': 'dependency_failed_before_measurement', 'resource_status': 'monitor_failed',
        'monitor_error': 'ValueError', 'cause': 'Q dependency failed after P exhausted its fixed CPU budget',
        'planned_research_lives': 4608, 'research_lives': 0, 'validation_lives': 0,
        'measurement_worker_started': False, 'absent_working_artifacts': absent,
        'R_monitored_cpu_seconds': budgets['R']['cpu_seconds'], 'R_cap_cpu_seconds': 3600,
        'predecessor_monitored_cpu_seconds': {label: budgets[label]['cpu_seconds'] for label in ('Q', 'P')},
        'scientific_outcome': None, 'archival_simulated_lives': 0,
        'offline_analyzer_completion_gate': gate,
        'interpretation': 'R produced no biological measurements; '
                          'effective-weight-update dependence remains unmeasured.',
        'limits': ['The planned 4608 research lives and two startup golden lives were not executed.',
                   'Waiting/monitor CPU is operational overhead, not research simulation CPU.',
                   'No restart, rescue, cap extension or new release was performed.']}
    save(target / 'summary.json', summary)
    (target / 'README.md').write_text(
        '# R stopped before measurement\n\n'
        'P reached its fixed CPU limit with confirmation incomplete. Q then failed its prerequisite, and '
        'R stopped on its registered Q dependency. R exited with `monitor_failed` / `ValueError` before '
        'opening a worker log or starting measurement. **R ran zero research or validation lives and has '
        'no scientific outcome.** Effective-weight-update dependence remains unmeasured.\n\n'
        f"R used {budgets['R']['cpu_seconds']:.6f} CPU-seconds of waiting/monitor overhead under its 3600-second cap. "
        'The planned 4608 research lives were not executed. The existing offline analyzer correctly returns '
        '`incomplete` / `monitor_failed` before opening measurement outcomes.\n\n'
        'Exact terminal P/Q/R budgets, source/release pins and root host/session exit evidence are retained. '
        'Both working `measurement/` and `run.log` were absent. All 109 original preparation artifacts, their '
        'manifest, and all 40 offline-analysis artifacts plus their manifest remain byte-identical. All 151 '
        'preserved files also matched Git index blobs at archival time.\n\n'
        'This directory has a separate manifest. No simulation, scientific-source edit, restart, rescue, '
        'budget extension or new release occurred.\n\n'
        'Verify from the repository root:\n\n```sh\n'
        '.venv/bin/python results/weight_updates_20261014/operational_status/archive_operational.py '
        '--check results/weight_updates_20261014/operational_status\n```\n')
    verify(public, preserved)
    assert all(not (work['R'] / name).exists() for name in absent)
    for name, source in files.items():
        assert sha(source) == original[name]
    artifacts = {str(path.relative_to(target)): {'sha256': sha(path), 'bytes': path.stat().st_size}
                 for path in sorted(target.rglob('*')) if path.is_file()}
    save(target / 'provenance.json', {'status': summary['status'], 'research_lives': 0,
        'archival_simulated_lives': 0, 'original_preparation_provenance_sha256': expected[0][2],
        'offline_analysis_provenance_sha256': expected[1][2], 'artifacts': artifacts})
    check(target)
    return summary


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group()
    group.add_argument('--archive', action='store_true')
    group.add_argument('--check', type=Path)
    args = parser.parse_args()
    if args.archive:
        print(json.dumps(archive(), indent=2))
    elif args.check:
        print(json.dumps({'status': check(args.check)['status']}))
    else:
        print(json.dumps({'status': 'dry_run', 'simulated_lives': 0}))
