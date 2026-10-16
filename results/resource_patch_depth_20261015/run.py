"""Release the fixed depth study, then own its search and measurement under one resource cap."""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

sys.dont_write_bytecode = True
from common import ROOT, STUDY, checked_protocol, read, save, sha  # noqa: E402


def search_complete(protocol):
    out = STUDY / 'runs/pareto'
    marker = read(out / 'search_complete.json')
    if (marker['status'] != 'complete' or marker['research_lives'] != 81974 or marker['startup_lives'] != 4
            or marker['protocol_sha256'] != sha(STUDY / 'protocol.json')
            or marker['release_sha256'] != sha(STUDY / 'release.json')):
        raise ValueError('complete eight-generation search inventory required')
    for name, digest in marker['output_pins'].items():
        if sha(out / name) != digest:
            raise ValueError('search output changed: ' + name)


def measurement_complete(protocol):
    marker = read(STUDY / 'measurement_complete.json')
    expected = dict(status='complete', research_lives=15360, startup_lives=4, total_calls=15364,
                    endpoint_lives=3072, confirmation_lives=12288, endpoint_batches=3, confirmation_batches=6,
                    protocol_sha256=sha(STUDY / 'protocol.json'))
    if any(marker[key] != value for key, value in expected.items()):
        raise ValueError('complete endpoint and confirmation inventory required')
    for name, count in (('endpoint_index.json', 3), ('row_index.json', 6)):
        index = read(STUDY / name)
        if len(index) != count:
            raise ValueError('complete measurement batch index required: ' + name)
        for path, entry in index.items():
            if (entry['status'] != 'validated' or sha(STUDY / path) != entry['sha256']
                    or sha(STUDY / entry['scored_path']) != entry['scored_sha256']):
                raise ValueError('returned raw/scored batch changed: ' + path)
    summary = read(STUDY / 'summary.json')
    if summary['status'] != 'complete' or summary['protocol_sha256'] != sha(STUDY / 'protocol.json'):
        raise ValueError('complete protocol-bound summary required')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', action='store_true')
    parser.add_argument('--public-commit')
    args = parser.parse_args()
    if not args.run:
        print('source only: no release, build or life')
        return
    start = time.monotonic()
    if args.public_commit is None or len(args.public_commit) != 40:
        raise ValueError('exact prospective publication commit required')
    protocol = checked_protocol()
    public = ROOT / 'results/resource_patch_depth_20261015'
    review = read(STUDY / 'reviews/actual_input_review.json')
    if (review['status'] != 'passed' or review['protocol_sha256'] != sha(STUDY / 'protocol.json')
            or sha(public / 'protocol.json') != sha(STUDY / 'protocol.json')
            or sha(public / 'reviews/actual_input_review.json') != sha(STUDY / 'reviews/actual_input_review.json')
            or sha(public / 'run.py') != sha(Path(__file__))):
        raise ValueError('reviewed prospective protocol, input review or launcher differs')
    manifest = read(public / 'manifest.json')
    if (manifest['status'] != 'prospective' or manifest['scientific_calls'] != 0
            or manifest['planned_calls'] != 97342 or manifest['protocol_sha256'] != sha(STUDY / 'protocol.json')):
        raise ValueError('prospective call inventory differs')
    for name, pin in manifest['files'].items():
        if sha(public / name) != pin['sha256']:
            raise ValueError('published artifact differs: ' + name)
    for ref in ('HEAD', 'origin/master'):
        if subprocess.check_output(['git', 'rev-parse', ref], cwd=ROOT, text=True).strip() != args.public_commit:
            raise ValueError('prospective commit must be HEAD and origin/master')
    if subprocess.check_output(['git', 'status', '--porcelain'], cwd=ROOT):
        raise ValueError('clean tracked publication required')
    if any((STUDY / name).exists() for name in ('release.json', 'execution', 'runs', 'raw', 'scored',
            'endpoint_raw', 'endpoint_scored', 'startup.json', 'row_index.json', 'measurement_complete.json',
            'study_complete.json', 'budget.json', 'build-cache', 'joint_genome.json', 'summary.json')):
        raise ValueError('first release refuses previous runtime artifacts')
    available = next(int(line.split()[1])*1024 for line in Path('/proc/meminfo').read_text().splitlines()
                     if line.startswith('MemAvailable:'))
    limits = protocol['runtime_budget']
    if available < limits['minimum_available_bytes']:
        raise ValueError('host memory reserve unavailable')
    save(STUDY / 'release.json', dict(status='released', protocol_sha256=sha(STUDY / 'protocol.json'),
        prospective_commit=args.public_commit, prospective_manifest_sha256=sha(public / 'manifest.json'),
        actual_input_review_sha256=sha(STUDY / 'reviews/actual_input_review.json'),
        pid_namespace=os.readlink('/proc/self/ns/pid'), available_memory_bytes=available,
        launch_source_sha256=sha(Path(__file__)),
        authorization='Standing user authorization for bounded safe local experiments; budget reported before launch.'),
        exclusive=True)
    import monitor_core as monitor
    execution = STUDY / 'execution'
    execution.mkdir(exist_ok=False)
    phases, search_cpu, current = {}, None, 'pareto'
    executable = str(ROOT / '.venv/bin/python')
    commands = dict(pareto=[executable, '-u', str(STUDY / 'search.py'), '--arm', 'pareto'],
                    measurement=[executable, '-u', str(STUDY / 'measure.py'), '--run-child'])

    def record(status, error=None):
        cpu, elapsed = monitor.consumed_cpu(-1), time.monotonic()-start
        table = monitor.proc_table()
        workers = [identity for phase in phases.values() for identity in phase['process_identities']
                   if identity['name'] == 'worker']
        groups = {worker['pgid'] for worker in workers}
        members = [pid for pid, row in table.items() if row['pgid'] in groups]
        identities = [worker['pid'] for worker in workers if worker['pid'] in table
                      and table[worker['pid']]['start_ticks'] == worker['start_ticks']]
        descendants = sorted(monitor.owned_live(table, -1))
        cleanup = dict(pid_namespace=monitor.pid_namespace(), checked_in_monitor=True,
            same_pid_namespace=monitor.pid_namespace() == read(STUDY / 'release.json')['pid_namespace'],
            all_owned_groups_exited=not members, all_worker_identities_exited=not identities,
            remaining_group_members=members, remaining_worker_identities=identities, remaining_descendants=descendants)
        phase_cpu = dict(pareto=search_cpu, measurement=None if search_cpu is None else cpu-search_cpu)
        if status == 'complete' and (members or identities or descendants or not cleanup['same_pid_namespace']
                or set(phases) != {'pareto', 'measurement'} or any(r['status'] != 'complete' for r in phases.values())
                or cpu >= limits['cpu_seconds'] or elapsed >= limits['wall_seconds'] or search_cpu is None
                or search_cpu >= protocol['phase_budgets']['pareto']['cpu_seconds']
                or cpu-search_cpu >= protocol['phase_budgets']['measurement']['cpu_seconds']):
            raise ValueError('complete requires bounded cleared execution of both phases')
        result = dict(status=status, phase=current, cpu_seconds=cpu, wall_seconds=elapsed,
            cap_cpu_seconds=limits['cpu_seconds'], cap_wall_seconds=limits['wall_seconds'],
            phase_cpu_seconds=phase_cpu, phases=phases,
            peak_owned_rss_bytes=max((p['peak_owned_rss_bytes'] for p in phases.values()), default=0),
            protocol_sha256=sha(STUDY / 'protocol.json'), release_sha256=sha(STUDY / 'release.json'),
            terminal_cleanup=cleanup if status != 'running' else None, error=error,
            running=[current] if status == 'running' else [], queued=['measurement']
            if status == 'running' and current == 'pareto' else [])
        save(STUDY / 'budget.json', result)
        return result

    try:
        for current in ('pareto', 'measurement'):
            folder = execution / current
            folder.mkdir()
            phase = protocol['phase_budgets'][current]
            budget = dict(limits)
            budget['cpu_seconds'] = min(limits['cpu_seconds'], phase['cpu_seconds']
                                        if search_cpu is None else search_cpu+phase['cpu_seconds'])
            budget['wall_seconds'] = min(phase['wall_seconds'], limits['wall_seconds']-(time.monotonic()-start))
            record('running')
            check = search_complete if current == 'pareto' else measurement_complete
            phases[current] = monitor.run_worker(folder, commands[current], budget,
                sha(STUDY / 'protocol.json'), sha(STUDY / 'release.json'), lambda check=check: check(protocol))
            if phases[current]['status'] != 'complete':
                record('incomplete', current + ' did not complete')
                raise SystemExit(1)
            if current == 'pareto':
                search_cpu = monitor.consumed_cpu(-1)
        result = record('complete')
    except BaseException as error:
        record('incomplete', type(error).__name__ + ': ' + str(error))
        raise
    reserve = protocol['package_budget']['preparation_terminal_cpu_reserve']
    save(STUDY / 'study_complete.json', dict(status='complete', research_lives=97334, startup_lives=8,
        total_calls=97342, protocol_sha256=sha(STUDY / 'protocol.json'), summary_sha256=sha(STUDY / 'summary.json'),
        search_complete_sha256=sha(STUDY / 'runs/pareto/search_complete.json'),
        measurement_complete_sha256=sha(STUDY / 'measurement_complete.json'), budget_sha256=sha(STUDY / 'budget.json'),
        phase_budget_pins={name: sha(execution / name / 'budget.json') for name in phases},
        package_cpu_seconds_with_full_reserve=result['cpu_seconds']+reserve,
        package_wall_seconds_with_full_reserve=result['wall_seconds']
            +protocol['package_budget']['preparation_terminal_wall_reserve']), exclusive=True)
    print(json.dumps({key: result[key] for key in ('status', 'cpu_seconds', 'wall_seconds', 'phase_cpu_seconds')}))


if __name__ == '__main__':
    main()
