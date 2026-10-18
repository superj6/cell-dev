"""Small persistent local process queue (Linux); never retries a failed job implicitly.

    python scripts/run_local_queue.py --jobs jobs.json --out outputs/queue --detach
    python scripts/run_local_queue.py --jobs jobs.json --out outputs/queue --resume --detach
    python scripts/run_local_queue.py --out outputs/queue --stop

JSON: {jobs:[{id,argv:[...],cwd,output}], max_workers:4, cpu_seconds:..., wall_seconds:...}.
Commands are exact argv, without a shell. Each worker has two computational threads and niceness10.
An interrupted monitor may adopt surviving workers; their durable exit receipts retain exit codes.
Explicit --retry ID preserves the failed attempt and starts its exact argv again (checkpoint handling is the job's).
"""
from __future__ import annotations

import argparse
import ctypes
import fcntl
import hashlib
import json
import math
import os
import resource
import signal
import subprocess
import sys
import time
from pathlib import Path

GIB = 1024 ** 3
SCRIPT = Path(__file__).resolve()


def save(path, value):
    path = Path(path)
    temporary = path.with_name(path.name + f'.{os.getpid()}.tmp')
    with temporary.open('w') as stream:
        json.dump(value, stream, indent=2, allow_nan=False)
        stream.write('\n')
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)


def table():
    rows = {}
    for path in Path('/proc').iterdir():
        if not path.name.isdecimal():
            continue
        try:
            fields = (path / 'stat').read_text().rsplit(')', 1)[1].split()
            rows[int(path.name)] = dict(pid=int(path.name), ppid=int(fields[1]), pgid=int(fields[2]),
                start_ticks=int(fields[19]),
                cpu=sum(int(fields[i]) for i in (11, 12, 13, 14)) / os.sysconf('SC_CLK_TCK'),
                rss=int(fields[21]) * os.sysconf('SC_PAGE_SIZE'), state=fields[0])
        except (FileNotFoundError, ProcessLookupError, PermissionError):
            pass
    return rows


def identity(pid, rows=None):
    row = (table() if rows is None else rows)[pid]
    return {key: row[key] for key in ('pid', 'pgid', 'start_ticks')}


def alive(who, rows):
    return (who['pid'] in rows and rows[who['pid']]['start_ticks'] == who['start_ticks']
            and rows[who['pid']]['state'] != 'Z')


def owned(who, rows):
    if not alive(who, rows):
        return set()
    found = {pid for pid, row in rows.items() if row['pgid'] == who['pgid']}
    while True:
        more = found | {pid for pid, row in rows.items() if row['ppid'] in found}
        if more == found:
            return found
        found = more


def send(who, signum):
    """Signal every verified group member/descendant through its pinned pidfd."""
    rows = table()
    if not alive(who, rows) or who['pgid'] <= 1 or who['pgid'] == os.getpgrp():
        return
    for pid in owned(who, rows):
        signal_identity(identity(pid, rows), signum)


def signal_identity(who, signum):
    if who['pid'] <= 1 or who['pid'] == os.getpid():
        return
    try:
        fd = os.pidfd_open(who['pid'])
    except ProcessLookupError:
        return
    try:
        if alive(who, table()):
            signal.pidfd_send_signal(fd, signum)
    except ProcessLookupError:
        pass
    finally:
        os.close(fd)


def available():
    return next(int(line.split()[1]) * 1024 for line in Path('/proc/meminfo').read_text().splitlines()
                if line.startswith('MemAvailable:'))


def load_jobs(path):
    config = json.loads(Path(path).read_text())
    config.setdefault('max_workers', 4)
    config.setdefault('cpu_seconds', 8 * 7 * 86400)
    config.setdefault('wall_seconds', 7 * 86400)
    config.setdefault('rss_bytes', 8 * GIB)
    config.setdefault('minimum_available_bytes', 4 * GIB)
    if (type(config['max_workers']) is not int or not 1 <= config['max_workers'] <= 4 or
            not 0 < config['rss_bytes'] <= 8 * GIB or config['minimum_available_bytes'] < 4 * GIB or
            any(not math.isfinite(config[k]) or config[k] <= 0 for k in ('cpu_seconds', 'wall_seconds'))):
        raise ValueError('queue limits require1..4 workers, <=8GiB RSS, >=4GiB host reserve and finite positive times')
    jobs = config['jobs']
    if not isinstance(jobs, list) or not jobs:
        raise ValueError('nonempty jobs list required')
    for job in jobs:
        if (not isinstance(job.get('id'), str) or not job['id'] or
                any(c not in 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-' for c in job['id']) or
                not isinstance(job.get('argv'), list) or not job['argv'] or
                any(not isinstance(x, str) or not x or '\0' in x for x in job['argv'])):
            raise ValueError('each job needs a safe unique id and nonempty string argv')
        job['cwd'] = str(Path(job['cwd']).resolve())
        job['output'] = str(Path(job['output']).resolve())
        if not Path(job['cwd']).is_dir():
            raise ValueError('job cwd does not exist')
    if len({j['id'] for j in jobs}) != len(jobs) or len({j['output'] for j in jobs}) != len(jobs):
        raise ValueError('job IDs and output directories must be distinct')
    return config


def worker(job_path, attempt):
    """Stay alive until descendants exit, so a replacement monitor can safely adopt this group."""
    attempt = Path(attempt)
    job = json.loads(Path(job_path).read_text())
    os.nice(10)
    libc = ctypes.CDLL(None, use_errno=True)
    if libc.prctl(36, 1, 0, 0, 0):  # become subreaper for job grandchildren
        raise OSError(ctypes.get_errno(), 'subreaper failed')
    stopped = []
    signal.signal(signal.SIGTERM, lambda signum, frame: stopped.append(signum))
    signal.signal(signal.SIGINT, lambda signum, frame: stopped.append(signum))
    env = dict(os.environ, OMP_NUM_THREADS='2', OMP_THREAD_LIMIT='2', MKL_NUM_THREADS='1',
               OPENBLAS_NUM_THREADS='1', NUMEXPR_NUM_THREADS='1', OMP_WAIT_POLICY='PASSIVE',
               CELLDEV_JOB_OUTPUT=job['output'])
    env.pop('CELLDEV_THREADS_FILE', None)
    start = time.time()
    code, error, child = None, None, None
    try:
        own_identity = identity(os.getpid())
        save(attempt / 'worker.json', dict(worker=own_identity, child=None, started_at=start))
        while not (attempt / 'accepted.json').exists() and time.time() - start < 10 and not stopped:
            time.sleep(.05)
        if (not (attempt / 'accepted.json').exists() or
                json.loads((attempt / 'accepted.json').read_text()) != own_identity or stopped):
            raise RuntimeError('launch was not durably accepted; no job started')
        child = subprocess.Popen(job['argv'], cwd=job['cwd'], env=env)
        save(attempt / 'worker.json', dict(worker=identity(os.getpid()), child=identity(child.pid), started_at=start))
        while child.poll() is None:
            if stopped:
                child.terminate()
            time.sleep(.1)
        code = child.returncode
    except BaseException as failure:
        error = repr(failure)
    finally:
        # The wrapper is the only group member that must survive long enough to write the exit receipt.
        for _ in range(30):
            rows = table()
            descendants = {p for p in owned(identity(os.getpid(), rows), rows)
                           if p != os.getpid() and rows[p]['state'] != 'Z'}
            for pid in descendants:
                signal_identity(identity(pid, rows), signal.SIGKILL)
            while True:
                try:
                    if os.waitpid(-1, os.WNOHANG)[0] == 0:
                        break
                except ChildProcessError:
                    break
            if not descendants:
                break
            time.sleep(.05)
        rows = table()
        remaining = [identity(p, rows) for p in owned(identity(os.getpid(), rows), rows)
                     if p != os.getpid() and rows[p]['state'] != 'Z']
        if remaining:
            error = (error or '') + ' owned descendants did not exit'
        own = resource.getrusage(resource.RUSAGE_SELF)
        children = resource.getrusage(resource.RUSAGE_CHILDREN)
        save(attempt / 'exit.json', dict(exit_code=code, error=error, stopped=bool(stopped),
             cleanup_complete=not remaining, remaining_owned=remaining,
             cpu_seconds=own.ru_utime + own.ru_stime + children.ru_utime + children.ru_stime,
             wall_seconds=time.time() - start, finished_at=time.time()))
    return 0 if code == 0 and error is None else 1


def monitor(config, output, resume=False, retry=()):
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    with (output / 'monitor.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        return run_monitor(config, output, resume, retry)


def run_monitor(config, output, resume, retry):
    digest = hashlib.sha256(json.dumps(config, sort_keys=True).encode()).hexdigest()
    path = output / 'monitor.json'
    if path.exists():
        if not resume:
            raise ValueError('queue exists; use --resume (failed jobs are not retried automatically)')
        state = json.loads(path.read_text())
        if state['jobs_sha256'] != digest:
            raise ValueError('resume requires the exact job list and limits')
    else:
        state = dict(version=1, jobs_sha256=digest, started_at=time.time(), monitor_cpu=0.,
                     jobs=[dict(spec=j, status='pending', attempts=[]) for j in config['jobs']], peak_rss_bytes=0)
        save(output / 'jobs.json', config)
    for name in retry:
        row = next((j for j in state['jobs'] if j['spec']['id'] == name), None)
        if row is None or row['status'] not in ('failed', 'interrupted', 'stopped'):
            raise ValueError('explicit retry requires a recorded failed/interrupted/stopped job')
        row['status'] = 'pending'
    state['monitor'] = identity(os.getpid())
    state['status'] = 'running'
    state['stop_reason'] = None
    state['limits'] = {k: v for k, v in config.items() if k != 'jobs'} | {'threads_per_job': 2, 'nice': 10}
    cpu_start, prior_cpu = time.process_time(), state['monitor_cpu']
    stopped, processes, stop_at = [], {}, None
    old = {sig: signal.signal(sig, lambda signum, frame: stopped.append(signum))
           for sig in (signal.SIGTERM, signal.SIGINT)}
    try:
        while True:
            rows = table()
            rss = rows.get(os.getpid(), {}).get('rss', 0)
            running = []
            for row in state['jobs']:
                if row['status'] not in ('launching', 'running'):
                    continue
                attempt = row['attempts'][-1]
                info = Path(attempt['path']) / 'worker.json'
                if attempt['worker'] is None:
                    if info.exists():
                        attempt['worker'] = json.loads(info.read_text())['worker']
                        row['status'] = 'running'
                        save(path, state)
                    elif time.time() - attempt['launched_at'] < 12:
                        running.append(row)
                        continue
                    else:
                        row['status'] = 'interrupted'
                        attempt['error'] = 'provisional worker never registered; no job was accepted'
                        continue
                accepted = Path(attempt['path']) / 'accepted.json'
                if not accepted.exists() and alive(attempt['worker'], rows):
                    save(accepted, attempt['worker'])
                receipt = Path(attempt['path']) / 'exit.json'
                members = owned(attempt['worker'], rows)
                if members:
                    attempt['owned'] = [identity(p, rows) for p in members]
                attempt['cpu_seconds'] = max(attempt['cpu_seconds'], sum(rows[p]['cpu'] for p in members))
                rss += sum(rows[p]['rss'] for p in members)
                known = attempt.get('owned', [])
                if info.exists() and json.loads(info.read_text()).get('child'):
                    known = known + [json.loads(info.read_text())['child']]
                if receipt.exists():
                    known += json.loads(receipt.read_text()).get('remaining_owned', [])
                survivors = [who for who in known if who != attempt['worker'] and alive(who, rows)]
                if not alive(attempt['worker'], rows) and survivors:
                    orphaned = set().union(*(owned(who, rows) for who in survivors))
                    rss += sum(rows[p]['rss'] for p in orphaned)
                    attempt['cpu_seconds'] = max(attempt['cpu_seconds'], sum(rows[p]['cpu'] for p in orphaned))
                    for who in survivors:
                        send(who, signal.SIGKILL)
                    attempt['error'] = 'owned cleanup still pending'
                    running.append(row)
                    continue
                if receipt.exists() and not alive(attempt['worker'], rows):
                    result = json.loads(receipt.read_text())
                    result['cpu_seconds'] = max(result['cpu_seconds'], attempt['cpu_seconds'])
                    attempt.update(result)
                    row['status'] = ('stopped' if result['stopped'] else 'complete' if result['exit_code'] == 0
                                     and result['error'] is None and result['cleanup_complete'] else 'failed')
                elif not alive(attempt['worker'], rows):
                    row['status'] = 'interrupted'
                    attempt['error'] = 'worker vanished without an exit receipt; no automatic retry'
                else:
                    running.append(row)
                process = processes.get(row['spec']['id'])
                if process is not None:
                    process.poll()
            state['monitor_cpu'] = prior_cpu + time.process_time() - cpu_start
            state['cpu_seconds'] = state['monitor_cpu'] + sum(a['cpu_seconds'] for j in state['jobs']
                                                             for a in j['attempts'])
            state['wall_seconds'] = time.time() - state['started_at']
            state['rss_bytes'] = rss
            state['peak_rss_bytes'] = max(state['peak_rss_bytes'], rss)
            state['available_bytes'] = available()
            reason = ('signal' if stopped else 'rss_limit' if rss >= config['rss_bytes'] else
                      'host_memory_floor' if state['available_bytes'] < config['minimum_available_bytes'] else
                      'cpu_limit' if state['cpu_seconds'] >= config['cpu_seconds'] else
                      'wall_limit' if state['wall_seconds'] >= config['wall_seconds'] else None)
            if reason and stop_at is None:
                stop_at = time.monotonic()
                state['stop_reason'] = reason
            if stop_at is not None:
                for row in running:
                    if row['attempts'][-1]['worker'] is not None:
                        send(row['attempts'][-1]['worker'], signal.SIGTERM if time.monotonic() - stop_at < 2
                             else signal.SIGKILL)
            else:
                for row in state['jobs']:
                    if row['status'] != 'pending' or len(running) >= config['max_workers']:
                        continue
                    job_output = Path(row['spec']['output'])
                    attempt_path = job_output / 'queue_attempts' / f'{len(row["attempts"]) + 1:03d}'
                    attempt_path.mkdir(parents=True)  # refuse to overwrite any previous attempt
                    save(attempt_path / 'job.json', row['spec'])
                    attempt = dict(path=str(attempt_path), worker=None, cpu_seconds=0., launched_at=time.time())
                    row['attempts'].append(attempt)
                    row['status'] = 'launching'
                    save(path, state)  # crash before/after Popen cannot lose the provisional attempt
                    with (attempt_path / 'stdout.log').open('x') as out, (attempt_path / 'stderr.log').open('x') as err:
                        process = subprocess.Popen([sys.executable, str(SCRIPT), '--worker',
                            str(attempt_path / 'job.json'), '--out', str(attempt_path)],
                            stdout=out, stderr=err, start_new_session=True)
                    who = identity(process.pid)
                    attempt['worker'] = who
                    row['status'] = 'running'
                    running.append(row)
                    processes[row['spec']['id']] = process
                    save(path, state)  # persist ownership before launching another worker
                    save(attempt_path / 'accepted.json', who)
            state['updated_at'] = time.time()
            if stop_at is not None and time.monotonic() - stop_at > 10 and running:
                state['status'] = 'cleanup_failed'
                save(path, state)
                return 2  # retain live identities visibly; never report successful cleanup
            if not running and (stop_at is not None or not any(j['status'] == 'pending' for j in state['jobs'])):
                state['status'] = 'stopped' if stop_at is not None else 'complete'
                if stop_at is None and any(j['status'] != 'complete' for j in state['jobs']):
                    state['status'] = 'failed'
                save(path, state)
                return 0 if state['status'] == 'complete' else 1
            save(path, state)
            time.sleep(.2)
    finally:
        for sig, handler in old.items():
            signal.signal(sig, handler)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--jobs', type=Path)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--detach', action='store_true')
    parser.add_argument('--resume', action='store_true')
    parser.add_argument('--retry', action='append', default=[])
    parser.add_argument('--stop', action='store_true')
    parser.add_argument('--worker', type=Path, help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.worker:
        return worker(args.worker, args.out)
    if args.stop:
        state = json.loads((args.out / 'monitor.json').read_text())
        if alive(state['monitor'], table()):
            signal_identity(state['monitor'], signal.SIGTERM)
        else:
            raise ValueError('monitor is absent; resume it to adopt surviving workers before stopping')
        return 0
    if args.jobs is None:
        parser.error('--jobs is required')
    config = load_jobs(args.jobs)
    if args.detach:
        args.out.mkdir(parents=True, exist_ok=True)
        argv = [sys.executable, str(SCRIPT), '--jobs', str(args.jobs.resolve()), '--out', str(args.out.resolve())]
        argv += ['--resume'] if args.resume else []
        for name in args.retry:
            argv += ['--retry', name]
        with (args.out / 'monitor.stdout.log').open('a') as out, (args.out / 'monitor.stderr.log').open('a') as err:
            process = subprocess.Popen(argv, stdout=out, stderr=err, start_new_session=True)
        print(json.dumps({'monitor_pid': process.pid, 'output': str(args.out.resolve())}))
        return 0
    return monitor(config, args.out.resolve(), args.resume, args.retry)


if __name__ == '__main__':
    raise SystemExit(main())
