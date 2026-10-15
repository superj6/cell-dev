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
                'cpu_ticks': sum(int(fields[i]) for i in (11, 12, 13, 14))}
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


def child_limits(seconds, expected_parent):
    libc = ctypes.CDLL(None, use_errno=True)
    if libc.prctl(1, signal.SIGKILL, 0, 0, 0) != 0:  # PR_SET_PDEATHSIG
        raise OSError(ctypes.get_errno(), 'cannot bind worker to monitor')
    if os.getppid() != expected_parent:
        os._exit(1)
    hard = max(2, math.ceil(seconds))
    resource.setrlimit(resource.RLIMIT_CPU, (hard - 1, hard))


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
    if (not all(math.isfinite(v) for v in (cpu_cap, wall_cap, margin))
            or not 0 < margin < min(cpu_cap, wall_cap) or budget['threads'] != 2 or budget['workers'] != 1):
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
    receipts, cpu_peak = [], 0.
    interrupted = []
    handlers = {sig: signal.signal(sig, lambda signum, frame: interrupted.append(signum))
                for sig in (signal.SIGINT, signal.SIGTERM)}

    def record(status):
        nonlocal cpu_peak
        cpu_peak = max(cpu_peak, consumed_cpu(process.pid if process is not None else -1))
        proof = cleanup_evidence(worker, namespace)
        terminal = status != 'running'
        if status == 'complete' and (cpu_peak >= cpu_cap or time.monotonic() - start >= wall_cap
                or not proof['same_pid_namespace'] or not proof['all_owned_groups_exited']
                or not proof['all_worker_identities_exited'] or proof['remaining_descendants']):
            raise ValueError('complete status requires bounded, cleared owned execution')
        item = {'status': status, 'exit_code': 0 if status == 'complete' else 1 if terminal else None,
                'worker_exit_code': None if process is None else process.returncode,
                'cpu_seconds': cpu_peak, 'wall_seconds': time.monotonic() - start,
                'cap_cpu_seconds': cpu_cap, 'cap_wall_seconds': wall_cap,
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
                   CELLDEV_PROTOCOL_SHA256=protocol_sha256, CELL_DEV_CACHE=str(study / 'build-cache'))
        env.pop('CELLDEV_THREADS_FILE', None)
        record('running')
        with (study / 'worker.stdout.log').open('x') as out, (study / 'worker.stderr.log').open('x') as err:
            parent_pid = os.getpid()
            process = subprocess.Popen(command, cwd=study, env=env, stdout=out, stderr=err,
                start_new_session=True, preexec_fn=lambda: child_limits(cpu_cap, parent_pid))
            worker = identity(process.pid)
            if worker['ppid'] != parent_pid or worker['pid'] != worker['pgid']:
                raise ValueError('worker ownership differs')
            while True:
                cpu_peak = max(cpu_peak, consumed_cpu(process.pid))
                elapsed = time.monotonic() - start
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
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', action='store_true')
    args = parser.parse_args()
    if not args.run:
        print(json.dumps({'status': 'source_only_no_run', 'simulation_calls': 0}))
        return
    protocol = checked_release()
    release = read(STUDY / 'release.json')
    if release.get('pid_namespace') != pid_namespace():
        raise ValueError('release clearance was issued in a different PID namespace')
    protocol_sha, release_sha = sha(STUDY / 'protocol.json'), sha(STUDY / 'release.json')

    def complete_check():
        if (checked_release() != protocol or sha(STUDY / 'release.json') != release_sha
                or sha(STUDY / 'protocol.json') != protocol_sha):
            raise ValueError('protocol/release changed during execution')
        marker = read(STUDY / 'measurement_complete.json')
        expected = {'status': 'complete', 'research_lives': 3072, 'startup_lives': 4,
                    'rows': 12, 'protocol_sha256': protocol_sha,
                    'row_index_sha256': sha(STUDY / 'row_index.json')}
        if marker != expected:
            raise ValueError('measurement completion marker differs')
        index = read(STUDY / 'row_index.json')
        paths = {f'raw/{world}/row_{i:02d}.npz' for world in protocol['worlds'] for i in range(3)}
        if set(index) != paths or len(paths) != 12:
            raise ValueError('measurement row coverage differs')
        for name, item in index.items():
            if sha(STUDY / name) != item['sha256'] or item['lives'] != 256:
                raise ValueError('measurement row changed: ' + name)

    result = run_worker(STUDY, [str(ROOT / '.venv/bin/python'), '-u', str(STUDY / 'measure.py'), '--run-child'],
                        protocol['budget'], protocol_sha, release_sha, complete_check)
    raise SystemExit(result['exit_code'])


if __name__ == '__main__':
    main()
