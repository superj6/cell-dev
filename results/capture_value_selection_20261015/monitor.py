"""One-attempt owned-worker watchdog; importing or describing it runs no lives."""
from __future__ import annotations

import argparse
import ctypes
import json
import math
import os
import resource
import signal
import subprocess
import sys
import time
from pathlib import Path

sys.dont_write_bytecode = True
from common import ROOT, STUDY, checked_release, read, save, sha  # noqa: E402


def pid_namespace():
    return os.readlink('/proc/self/ns/pid')


def proc_table():
    table = {}
    for path in Path('/proc').iterdir():
        if not path.name.isdecimal():
            continue
        try:
            fields = (path / 'stat').read_text().rsplit(')', 1)[1].split()
            table[int(path.name)] = {
                'ppid': int(fields[1]), 'pgid': int(fields[2]), 'start_ticks': int(fields[19]),
                'cpu_ticks': sum(int(fields[i]) for i in (11, 12, 13, 14)),
                'rss_bytes': int(fields[21]) * os.sysconf('SC_PAGE_SIZE')}
        except (FileNotFoundError, ProcessLookupError, PermissionError):
            continue
    return table


def identity(pid):
    row = proc_table()[pid]
    return {'pid': pid, **{key: row[key] for key in ('ppid', 'pgid', 'start_ticks')}}


def owned_live(table, group):
    # Include adopted descendants and the child tree even if a child leaves its group.
    owned = {pid for pid, row in table.items() if row['pgid'] == group or row['ppid'] == os.getpid()}
    while True:
        expanded = owned | {pid for pid, row in table.items() if row['ppid'] in owned}
        if expanded == owned:
            return owned
        owned = expanded


def consumed_cpu(group):
    own = resource.getrusage(resource.RUSAGE_SELF)
    reaped = resource.getrusage(resource.RUSAGE_CHILDREN)
    table = proc_table()
    active = sum(table[pid]['cpu_ticks'] for pid in owned_live(table, group)) / os.sysconf('SC_CLK_TCK')
    return own.ru_utime + own.ru_stime + reaped.ru_utime + reaped.ru_stime + active


def memory_usage(group):
    table = proc_table()
    rss = sum(table[pid]['rss_bytes'] for pid in owned_live(table, group))
    available = next(int(line.split()[1]) * 1024 for line in Path('/proc/meminfo').read_text().splitlines()
                     if line.startswith('MemAvailable:'))
    return rss, available


def child_limits(seconds, expected_parent, address_space_bytes):
    libc = ctypes.CDLL(None, use_errno=True)
    if libc.prctl(1, signal.SIGKILL, 0, 0, 0) != 0:  # PR_SET_PDEATHSIG
        raise OSError(ctypes.get_errno(), 'cannot bind worker to monitor')
    if os.getppid() != expected_parent:
        os._exit(1)
    hard = max(2, math.ceil(seconds))
    resource.setrlimit(resource.RLIMIT_CPU, (hard - 1, hard))
    resource.setrlimit(resource.RLIMIT_AS, (address_space_bytes, address_space_bytes))


def enable_subreaper():
    libc = ctypes.CDLL(None, use_errno=True)
    if libc.prctl(36, 1, 0, 0, 0) != 0:  # PR_SET_CHILD_SUBREAPER
        raise OSError(ctypes.get_errno(), 'cannot account for adopted descendants')


def signal_owned(group, signum):
    if group <= 1 or group == os.getpgrp():
        raise ValueError('refuse signaling an unowned process group')
    try:
        os.killpg(group, signum)
    except ProcessLookupError:
        pass


def signal_descendant(pid, start_ticks, signum):
    """A pidfd plus a fresh start-tick check prevents signaling a recycled PID."""
    if pid <= 1 or pid == os.getpid():
        raise ValueError('refuse signaling monitor or namespace init')
    try:
        handle = os.pidfd_open(pid)
    except ProcessLookupError:
        return
    try:
        row = proc_table().get(pid)
        if row is not None and row['start_ticks'] == start_ticks:
            try:
                signal.pidfd_send_signal(handle, signum)
            except ProcessLookupError:
                pass
    finally:
        os.close(handle)


def reap(process, receipts):
    # wait4 retains exact CPU evidence for the leader and adopted compiler children.
    while True:
        try:
            pid, status, usage = os.wait4(-1, os.WNOHANG)
        except ChildProcessError:
            return
        if pid == 0:
            return
        code = os.waitstatus_to_exitcode(status)
        receipts.append({'pid': pid, 'wait_status': status, 'exit_code': code,
                         'user_cpu_seconds': usage.ru_utime, 'system_cpu_seconds': usage.ru_stime})
        if pid == process.pid:
            process.returncode = code


def cleanup(process, receipts, namespace):
    if pid_namespace() != namespace:
        raise ValueError('cleanup namespace changed')
    deadline = time.monotonic() + 3
    while True:
        signal_owned(process.pid, signal.SIGKILL)
        table = proc_table()
        for pid in owned_live(table, process.pid):
            signal_descendant(pid, table[pid]['start_ticks'], signal.SIGKILL)
        reap(process, receipts)
        table = proc_table()
        remaining = owned_live(table, process.pid)
        if not remaining and process.returncode is not None:
            return
        if time.monotonic() >= deadline:
            raise RuntimeError('owned descendants remain after group cleanup: ' + str(sorted(remaining)))
        time.sleep(.05)


def cleanup_evidence(worker, namespace):
    table = proc_table()
    group = [] if worker is None else [pid for pid, row in table.items() if row['pgid'] == worker['pgid']]
    same = [] if worker is None else [worker['pid']] if (
        worker['pid'] in table and table[worker['pid']]['start_ticks'] == worker['start_ticks']) else []
    descendants = [] if worker is None else sorted(owned_live(table, worker['pgid']))
    return {'pid_namespace': pid_namespace(), 'checked_in_monitor': True,
            'same_pid_namespace': pid_namespace() == namespace,
            'remaining_group_members': group, 'remaining_worker_identities': same,
            'remaining_descendants': descendants,
            'all_owned_groups_exited': not group, 'all_worker_identities_exited': not same}


def run_worker(study, command, budget, protocol_sha256, release_sha256,
               complete_check, *, environment=None, poll_seconds=.2):
    """Used by the CLI and synthetic subprocess tests; no engine imports."""
    study = Path(study)
    cpu_cap, wall_cap = float(budget['cpu_seconds']), float(budget['wall_seconds'])
    margin = float(budget['cleanup_margin_seconds'])
    rss_cap = int(budget.get('rss_bytes', 4 * 1024**3))
    free_floor = int(budget.get('minimum_available_bytes', 4 * 1024**3))
    address_cap = int(budget.get('address_space_bytes', 8 * 1024**3))
    if (not all(math.isfinite(v) for v in (cpu_cap, wall_cap, margin))
            or not 0 < margin < min(cpu_cap, wall_cap) or budget['threads'] != 2 or budget['workers'] != 1
            or not 0 < rss_cap <= address_cap or free_floor < 0):
        raise ValueError('invalid fixed worker/resource scope')
    for name in ('attempt.json', 'budget.json', 'worker.stdout.log', 'worker.stderr.log',
                 'startup.json', 'raw', 'row_index.json', 'measurement_complete.json', 'build-cache'):
        if (study / name).exists():
            raise ValueError('first attempt refuses previous execution: ' + name)
    namespace, start = pid_namespace(), time.monotonic()
    monitor = identity(os.getpid())
    attempt = {'monitor': monitor, 'pid_namespace': namespace, 'protocol_sha256': protocol_sha256,
               'release_sha256': release_sha256, 'command': command, 'budget': budget}
    save(study / 'attempt.json', attempt, exclusive=True)
    attempt_sha = sha(study / 'attempt.json')
    process, worker, error, reason, stop_time, cleanup_error = None, None, None, None, None, None
    receipts, cpu_peak, rss_peak = [], 0., 0
    interrupted = []
    handlers = {sig: signal.signal(sig, lambda signum, frame: interrupted.append(signum))
                for sig in (signal.SIGINT, signal.SIGTERM)}

    def record(status):
        nonlocal cpu_peak, rss_peak
        cpu_peak = max(cpu_peak, consumed_cpu(process.pid if process is not None else -1))
        rss, available = memory_usage(process.pid if process is not None else -1)
        rss_peak = max(rss_peak, rss)
        proof = cleanup_evidence(worker, namespace)
        terminal = status != 'running'
        if status == 'complete' and (cpu_peak >= cpu_cap or time.monotonic() - start >= wall_cap
                or rss_peak >= rss_cap or available < free_floor
                or not proof['same_pid_namespace'] or not proof['all_owned_groups_exited']
                or not proof['all_worker_identities_exited'] or proof['remaining_descendants']):
            raise ValueError('complete status requires bounded, cleared owned execution')
        item = {'status': status, 'exit_code': 0 if status == 'complete' else 1 if terminal else None,
                'worker_exit_code': None if process is None else process.returncode,
                'cpu_seconds': cpu_peak, 'wall_seconds': time.monotonic() - start,
                'cap_cpu_seconds': cpu_cap, 'cap_wall_seconds': wall_cap,
                'peak_owned_rss_bytes': rss_peak, 'available_memory_bytes': available,
                'cap_rss_bytes': rss_cap, 'minimum_available_bytes': free_floor,
                'worker_address_space_bytes': address_cap,
                'protocol_sha256': protocol_sha256, 'release_sha256': release_sha256,
                'attempt_sha256': attempt_sha, 'pid_namespace': namespace,
                'process_identities': [dict(monitor, name='monitor')] + ([] if worker is None else [dict(worker, name='worker')]),
                'owned_process_groups': [] if worker is None else [worker['pgid']],
                'running': {} if terminal else ({} if worker is None else {str(worker['pid']): 'measurement'}),
                'queued': [], 'reason': reason, 'error': error, 'cleanup_error': cleanup_error,
                'terminal_cleanup': proof if terminal else None, 'wait4_receipts': receipts}
        save(study / 'budget.json', item)
        return item

    try:
        enable_subreaper()
        env = dict(os.environ if environment is None else environment,
                   PYTHONDONTWRITEBYTECODE='1', PYTHONUNBUFFERED='1', ATEN_CPU_CAPABILITY='avx2',
                   OMP_NUM_THREADS='2', OMP_THREAD_LIMIT='2', OMP_WAIT_POLICY='PASSIVE',
                   MKL_NUM_THREADS='1', OPENBLAS_NUM_THREADS='1',
                   CELLDEV_MONITOR_PID=str(monitor['pid']), CELLDEV_MONITOR_START_TICKS=str(monitor['start_ticks']),
                   CELLDEV_PID_NAMESPACE=namespace, CELLDEV_ATTEMPT_SHA256=attempt_sha,
                   CELLDEV_PROTOCOL_SHA256=protocol_sha256, CELLDEV_ATTEMPT_PATH=str(study / 'attempt.json'),
                   CELL_DEV_CACHE=str(STUDY / 'build-cache'))
        env.pop('CELLDEV_THREADS_FILE', None)
        if memory_usage(-1)[1] < free_floor:
            raise ValueError('insufficient available host memory before worker launch')
        record('running')
        with (study / 'worker.stdout.log').open('x') as out, (study / 'worker.stderr.log').open('x') as err:
            parent_pid = os.getpid()
            process = subprocess.Popen(command, cwd=study, env=env, stdout=out, stderr=err,
                start_new_session=True, preexec_fn=lambda: child_limits(cpu_cap, parent_pid, address_cap))
            worker = identity(process.pid)
            if worker['ppid'] != parent_pid or worker['pid'] != worker['pgid']:
                raise ValueError('worker ownership differs')
            while True:
                cpu_peak = max(cpu_peak, consumed_cpu(process.pid))
                rss, available = memory_usage(process.pid)
                rss_peak = max(rss_peak, rss)
                elapsed = time.monotonic() - start
                if rss_peak >= rss_cap or available < free_floor:
                    reason = reason or 'memory_budget_exhausted'
                    signal_owned(process.pid, signal.SIGKILL)
                if interrupted:
                    reason = reason or 'monitor_interrupted'
                if cpu_peak >= cpu_cap - margin:
                    reason = reason or 'cpu_budget_exhausted'
                if elapsed >= wall_cap - margin:
                    reason = reason or 'wall_budget_exhausted'
                if reason and stop_time is None:
                    stop_time = time.monotonic()
                    signal_owned(process.pid, signal.SIGTERM)
                if stop_time is not None and time.monotonic() - stop_time >= 2:
                    signal_owned(process.pid, signal.SIGKILL)
                reap(process, receipts)
                if process.returncode is not None:
                    # A leader may exit while compiler/worker descendants still run.
                    cleanup(process, receipts, namespace)
                    break
                record('running')
                time.sleep(poll_seconds)
        if process.returncode != 0:
            reason = reason or 'worker_failed'
        cpu_peak = max(cpu_peak, consumed_cpu(process.pid))
        if cpu_peak >= cpu_cap or time.monotonic() - start >= wall_cap:
            reason = reason or 'final_resource_cap_exceeded'
        rss, available = memory_usage(process.pid)
        rss_peak = max(rss_peak, rss)
        if rss_peak >= rss_cap or available < free_floor:
            reason = reason or 'memory_budget_exhausted'
        if not reason:
            complete_check()
        return record('incomplete' if reason else 'complete')
    except BaseException as failure:
        error = type(failure).__name__ + ': ' + str(failure)
        if process is not None:
            try:
                cleanup(process, receipts, namespace)
            except BaseException as failure2:
                cleanup_error = type(failure2).__name__ + ': ' + str(failure2)
        record('monitor_failed')
        raise
    finally:
        for sig, handler in handlers.items():
            signal.signal(sig, handler)


def main():
    parser = argparse.ArgumentParser(description='AM capture-value selection and confirmation under one cumulative cap')
    parser.add_argument('--run', action='store_true')
    args = parser.parse_args()
    if not args.run:
        print(json.dumps({'status': 'source_only', 'simulation_calls': 0}))
        return
    protocol = checked_release()
    release = read(STUDY / 'release.json')
    namespace = pid_namespace()
    if namespace != release['pid_namespace']:
        raise ValueError('run must use cleared release namespace')
    for name in ('attempt.json', 'budget.json', 'execution', 'runs', 'raw', 'endpoints.json', 'build-cache'):
        if (STUDY / name).exists():
            raise ValueError('first attempt refuses runtime artifacts: ' + name)
    protocol_sha, release_sha = sha(STUDY / 'protocol.json'), sha(STUDY / 'release.json')
    executable = str(ROOT / '.venv/bin/python')
    phases = ['current_value', 'high_value', 'confirmation']
    commands = {arm: [executable, '-u', str(STUDY / 'search.py'), '--arm', arm] for arm in phases[:2]}
    commands['confirmation'] = [executable, '-u', str(STUDY / 'measure.py'), '--run-child']
    monitor = identity(os.getpid())
    attempt = {'monitor': monitor, 'pid_namespace': namespace, 'protocol_sha256': protocol_sha,
               'release_sha256': release_sha, 'commands': commands, 'budget': protocol['budget']}
    save(STUDY / 'attempt.json', attempt, exclusive=True)
    start = time.monotonic()
    records, workers, receipts = {}, [], []
    search_cpu = None
    current = phases[0]

    def record(status, reason=None):
        cpu = consumed_cpu(-1)
        table = proc_table()
        groups = [worker['pgid'] for worker in workers]
        members = [pid for pid, row in table.items() if row['pgid'] in groups]
        same = [worker['pid'] for worker in workers if worker['pid'] in table
                and table[worker['pid']]['start_ticks'] == worker['start_ticks']]
        descendants = sorted(owned_live(table, -1))
        cleanup = {'pid_namespace': pid_namespace(), 'checked_in_monitor': True,
            'same_pid_namespace': pid_namespace() == namespace, 'remaining_group_members': members,
            'remaining_worker_identities': same, 'remaining_descendants': descendants,
            'all_owned_groups_exited': not members, 'all_worker_identities_exited': not same}
        if status == 'complete' and (members or same or descendants or cpu >= 10800
                or time.monotonic() - start >= 5400 or search_cpu is None
                or search_cpu >= 7200 or cpu - search_cpu >= 3600):
            raise ValueError('complete requires bounded cleared entire run')
        item = {'status': status, 'phase': current, 'exit_code': 0 if status == 'complete' else
                None if status == 'running' else 1,
                'worker_exit_code': 0 if status == 'complete' else None,
                'cpu_seconds': cpu, 'wall_seconds': time.monotonic() - start,
                'cap_cpu_seconds': 10800, 'cap_wall_seconds': 5400,
                'search_cpu_seconds': search_cpu,
                'confirmation_cpu_seconds': None if search_cpu is None else cpu - search_cpu,
                'search_cpu_cap': 7200, 'confirmation_cpu_cap': 3600,
                'protocol_sha256': protocol_sha, 'release_sha256': release_sha,
                'attempt_sha256': sha(STUDY / 'attempt.json'), 'pid_namespace': namespace,
                'process_identities': [dict(monitor, name='monitor')] + workers,
                'owned_process_groups': groups, 'phase_records': records,
                'wait4_receipts': receipts, 'running': {current: True} if status == 'running' else {},
                'queued': phases[phases.index(current) + 1:] if status == 'running' else [],
                'reason': reason, 'error': None, 'cleanup_error': None if not descendants else descendants,
                'terminal_cleanup': cleanup if status != 'running' else None}
        save(STUDY / 'budget.json', item)
        return item

    try:
        for phase in phases:
            current = phase
            if checked_release() != protocol or sha(STUDY / 'release.json') != release_sha:
                raise ValueError('protocol/release changed during execution')
            phase_dir = STUDY / 'execution' / phase
            phase_dir.mkdir(parents=True)
            cpu_cap = 7200 if phase != 'confirmation' else min(10800, search_cpu + 3600)
            phase_budget = {'cpu_seconds': cpu_cap, 'wall_seconds': 5400 - (time.monotonic() - start),
                            'threads': 2, 'workers': 1, 'cleanup_margin_seconds': 10,
                            **{key: protocol['budget'][key] for key in
                               ('rss_bytes', 'minimum_available_bytes', 'address_space_bytes')}}

            def complete_check(phase=phase):
                if phase != 'confirmation':
                    marker = read(STUDY / 'runs' / phase / 'search_complete.json')
                    if (marker['status'] != 'complete' or marker['research_lives'] != 10278
                            or marker['startup_lives'] != 2 or marker['protocol_sha256'] != protocol_sha):
                        raise ValueError('native search completion differs')
                else:
                    marker = read(STUDY / 'measurement_complete.json')
                    if (marker['status'] != 'complete' or marker['research_lives'] != 8192
                            or marker['startup_lives'] != 4 or marker['rows'] != 16
                            or marker['protocol_sha256'] != protocol_sha
                            or marker['row_index_sha256'] != sha(STUDY / 'row_index.json')
                            or marker['endpoints_sha256'] != sha(STUDY / 'endpoints.json')):
                        raise ValueError('confirmation marker differs')
                    index = read(STUDY / 'row_index.json')
                    expected = {f'raw/{world}/row_{i:02d}.npz' for world in protocol['worlds'] for i in range(4)}
                    if set(index) != expected:
                        raise ValueError('confirmation coverage differs')
                    for name, entry in index.items():
                        if entry['sha256'] != sha(STUDY / name) or entry['lives'] != 512:
                            raise ValueError('confirmation row differs')

            record('running')
            result = run_worker(phase_dir, commands[phase], phase_budget, protocol_sha, release_sha, complete_check)
            records[phase] = {'path': str((phase_dir / 'budget.json').relative_to(STUDY)),
                              'sha256': sha(phase_dir / 'budget.json')}
            workers.extend(dict(worker, name=phase) for worker in result['process_identities'] if worker['name'] == 'worker')
            receipts.extend(result['wait4_receipts'])
            if result['status'] != 'complete':
                record('incomplete', phase + ': ' + str(result.get('reason')))
                raise SystemExit(1)
            if phase == 'high_value':
                search_cpu = consumed_cpu(-1)
        save(STUDY / 'study_complete.json', {'status': 'complete', 'research_lives': 28748,
            'startup_lives': 8, 'total_calls': 28756, 'protocol_sha256': protocol_sha,
            'measurement_complete_sha256': sha(STUDY / 'measurement_complete.json'),
            'search_complete_pins': {arm: sha(STUDY / 'runs' / arm / 'search_complete.json') for arm in phases[:2]}},
            exclusive=True)
        final = record('complete')
        print(json.dumps({key: final[key] for key in ('status', 'cpu_seconds', 'wall_seconds')}))
    except BaseException as error:
        # A phase watchdog already cleans its owned child tree before propagating an error.
        path = STUDY / 'execution' / current / 'budget.json'
        if path.exists() and current not in records:
            result = read(path)
            records[current] = {'path': str(path.relative_to(STUDY)), 'sha256': sha(path)}
            workers.extend(dict(worker, name=current) for worker in result['process_identities'] if worker['name'] == 'worker')
            receipts.extend(result['wait4_receipts'])
        record('incomplete', type(error).__name__ + ': ' + str(error))
        raise


if __name__ == '__main__':
    main()
