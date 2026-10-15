"""AI matched control/reserve searches with a fixed confirmation CPU reserve."""
from __future__ import annotations

import argparse
import ctypes
import hashlib
import json
import math
import os
import resource
import signal
import subprocess
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
STUDY = Path(__file__).resolve().parent
LABELS = ("AE_L92", "AI_control", "AI_reserve")
CAP, SEARCH_CAP, MARGIN, POLL = 5400, 3400, 10, 1


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + '.tmp')
    temporary.write_text(json.dumps(value, indent=2, allow_nan=False) + '\n')
    temporary.replace(path)


def check_protocol():
    protocol = json.loads((STUDY / 'protocol.json').read_text())
    expected = {'study': 'AI fresh-offspring exploratory reserve replication', 'generations': 4,
                'max_cpu_seconds': CAP, 'search_cpu_seconds': SEARCH_CAP, 'max_simulation_threads': 4,
                'search_genome_lives': 8268, 'confirmation_genome_lives': 1536,
                'planned_genome_lives': 9804, 'startup_validation_genome_lives': 6, 'abi': 3}
    if any(protocol.get(key) != value for key, value in expected.items()):
        raise ValueError('registered scientific/resource scope differs')
    runs, confirmation = protocol['runs'], protocol['confirmation']
    if (runs != ['control', 'reserve'] or type(protocol.get('paired_native_seed')) is not int
            or not 0 <= protocol['paired_native_seed'] < 2**64):
        raise ValueError('exact matched search arms and shared native seed required')
    if (confirmation['labels'] != list(LABELS) or confirmation['threads'] != 2
            or len(confirmation['seeds']) != 512 or len(set(confirmation['seeds'])) != 512
            or confirmation['primary_pairs'] != [[2, 1]] or confirmation['gain_pairs'] != [[1, 0], [2, 0]]):
        raise ValueError('registered three-role confirmation differs')
    for key, base in (('file_pins', STUDY), ('production_pins', ROOT)):
        if not protocol[key]:
            raise ValueError('empty required source/config pin map')
        for name, digest in protocol[key].items():
            path = (base / name).resolve()
            if not path.is_relative_to(base.resolve()) or sha(path) != digest:
                raise ValueError('changed pinned input: ' + name)
    required_sources = {str(p.relative_to(ROOT)) for p in (ROOT / 'src').rglob('*.py')}
    required_sources.update({'src/life/kernel.c', 'scripts/taskvar_confirm.py',
                             'scripts/taskvar_gradient.py', 'scripts/taskvar_gates.py'})
    if not required_sources.issubset(protocol['production_pins']):
        raise ValueError('incomplete imported source closure')
    if set(protocol['configs']) != {str(seed) for seed in runs}:
        raise ValueError('configuration set differs')
    for record in protocol['configs'].values():
        if sha(STUDY / record['path']) != record['sha256']:
            raise ValueError('configuration differs')
    from prepare import cost_projection
    if protocol['cost_projection'] != cost_projection(protocol['cost_projection']['rates_cpu_per_life']):
        raise ValueError('measured-cost projection differs')
    if protocol['cost_projection']['feasible'] is not True:
        raise ValueError('fixed scope does not fit developed-founder cost estimate')
    from reserve_adapter import POLICY
    if protocol['reserve_policy'] != POLICY:
        raise ValueError('selection policy changed')
    return protocol


def check_ready():
    protocol = check_protocol()
    ready = json.loads((STUDY / 'ready.json').read_text())
    if ready.get('status') != 'released' or ready.get('production_pins') != protocol['production_pins']:
        raise ValueError('study is not released with exact source pins')
    required = dict(protocol['file_pins'])
    for name in ('protocol.json', 'run_budgeted.py', 'measure.py', 'resource_clearance.json'):
        required[name] = sha(STUDY / name)
    if any(ready.get('source_pins', {}).get(k) != v for k, v in required.items()):
        raise ValueError('release identity differs')
    for name, digest in ready['source_pins'].items():
        path = (STUDY / name).resolve()
        if not path.is_relative_to(STUDY.resolve()) or sha(path) != digest:
            raise ValueError('reviewed file differs: ' + name)
    return ready


def resource_clearance():
    item = json.loads((STUDY / 'resource_clearance.json').read_text())
    if item.get('status') != 'cleared' or item.get('all_processes_exited') is not True:
        raise ValueError('previous work is not cleared')
    if not item.get('processes') or not item.get('process_groups') or not item.get('budget_pins'):
        raise ValueError('clearance requires process and budget evidence')
    table = proc_table()
    for process in item['processes']:
        row = table.get(process['pid'])
        if row is not None and row['start_ticks'] == process['start_ticks']:
            raise ValueError('prior recorded process is still alive')
    if any(row['pgrp'] in item['process_groups'] for row in table.values()):
        raise ValueError('prior owned process group is still alive')
    for name, digest in item['budget_pins'].items():
        if sha(ROOT / name) != digest:
            raise ValueError('prior terminal budget changed')
        old = json.loads((ROOT / name).read_text())
        if old.get('running') or old.get('queued') or old.get('cleanup_error') or old.get('status') == 'running':
            raise ValueError('prior budget is not cleanly terminal')
    return item


def own_cpu():
    usage = resource.getrusage(resource.RUSAGE_SELF)
    return usage.ru_utime + usage.ru_stime


def child_cpu():
    usage = resource.getrusage(resource.RUSAGE_CHILDREN)
    return usage.ru_utime + usage.ru_stime


def proc_table():
    processes = {}
    for directory in Path('/proc').iterdir():
        if not directory.name.isdigit():
            continue
        try:
            fields = (directory / 'stat').read_text().rsplit(')', 1)[1].split()
            processes[int(directory.name)] = {'ppid': int(fields[1]), 'pgrp': int(fields[2]),
                'start_ticks': int(fields[19]), 'cpu_ticks': sum(int(fields[i]) for i in (11, 12, 13, 14))}
        except (FileNotFoundError, ProcessLookupError, PermissionError):
            continue
    return processes


def active_cpu(group):
    # Group membership survives leader exit and descendant adoption by the subreaper.
    return sum(row['cpu_ticks'] for row in proc_table().values()
               if row['pgrp'] == group) / os.sysconf('SC_CLK_TCK')


def consumed_cpu(running):
    return own_cpu() + child_cpu() + sum(active_cpu(pid) for pid in running)


def child_limit(seconds, parent_pid):
    if ctypes.CDLL(None).prctl(1, signal.SIGKILL, 0, 0, 0) != 0:
        raise OSError('cannot bind worker lifetime to monitor')
    if os.getppid() != parent_pid:
        os._exit(1)
    hard = max(2, int(math.floor(seconds)))
    resource.setrlimit(resource.RLIMIT_CPU, (hard - 1, hard))


def send_signal(process, signum):
    try:
        os.killpg(process.pid, signum)
    except ProcessLookupError:
        pass


def enable_subreaper():
    if ctypes.CDLL(None).prctl(36, 1, 0, 0, 0) != 0:  # Linux PR_SET_CHILD_SUBREAPER
        raise OSError('cannot enable complete descendant CPU accounting')


def cleanup_group(process):
    """Terminate/reap the owned group even after its leader has exited; charge adopted descendants."""
    deadline = time.monotonic() + 3
    while True:
        send_signal(process, signal.SIGKILL)
        if process.poll() is not None:
            while True:
                try:
                    pid, _ = os.waitpid(-process.pid, os.WNOHANG)
                except ChildProcessError:
                    break
                if pid == 0:
                    break
            if not any(row['pgrp'] == process.pid for row in proc_table().values()):
                return
        if time.monotonic() >= deadline:
            raise RuntimeError('owned process group did not exit after SIGKILL')
        time.sleep(.05)


def cleanup(running):
    for process, _, _ in running.values():
        send_signal(process, signal.SIGTERM)
    deadline = time.monotonic() + 2
    errors = []
    for pid, (process, log, _) in list(running.items()):
        try:
            try:
                process.wait(timeout=max(0, deadline - time.monotonic()))
            except subprocess.TimeoutExpired:
                send_signal(process, signal.SIGKILL)
            cleanup_group(process)
            del running[pid]
        except BaseException as error:
            errors.append(f'{pid}: {type(error).__name__}: {error}')
        finally:
            log.close()
    if errors:
        raise RuntimeError('owned group cleanup failed: ' + '; '.join(errors))


def interrupt(signum, frame):
    raise KeyboardInterrupt(f'monitor interrupted by signal {signum}')


def process_identity(pid):
    fields = (Path('/proc') / str(pid) / 'stat').read_text().rsplit(')', 1)[1].split()
    return {'pid': pid, 'ppid': int(fields[1]), 'pgid': int(fields[2]), 'start_ticks': int(fields[19])}


def phase_limit(phase):
    if phase not in ('search', 'confirmation'):
        raise ValueError('invalid phase')
    return SEARCH_CAP if phase == 'search' else CAP


def budget_reason(phase, consumed):
    if consumed >= phase_limit(phase) - MARGIN:
        return 'search_reserve_limit' if phase == 'search' else 'cpu_budget_exhausted'
    return None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', action='store_true')
    args = parser.parse_args()
    if not args.run and not (STUDY / 'protocol.json').exists():
        print(json.dumps({'status': 'source_only_unregistered', 'planned_genome_lives': 9804,
                          'startup_validation_genome_lives': 6, 'simulation_calls': 0}))
        return
    protocol = check_protocol()
    commands = {f'evolve_{run}': [str(ROOT / '.venv/bin/python'), str(STUDY / 'search.py'), '--run-id', run]
                for run in protocol['runs']}
    commands['confirmation'] = [str(ROOT / '.venv/bin/python'), str(STUDY / 'measure.py'), '--confirm-child']
    if not args.run:
        print(json.dumps({'status': 'dry_run', 'commands': commands, 'max_cpu_seconds': CAP,
                          'search_cpu_seconds': SEARCH_CAP, 'confirmation_reserved_cpu_seconds': CAP - SEARCH_CAP,
                          'planned_genome_lives': 9804, 'max_simulation_threads': 4,
                          'confirmation_threads': 2, 'simulated_lives': 0}, indent=2))
        return
    ready = check_ready()
    status_path = STUDY / 'budget.json'
    if status_path.exists():
        raise ValueError('budget exists: no automatic reset or restart')
    if any((STUDY / name).exists() for name in ('runs', 'confirmation', 'logs', 'attempt.json', 'build-cache')):
        raise ValueError('run artifacts exist before launch')
    resource_clearance()
    running, completed, queue = {}, [], [f'evolve_{run}' for run in protocol['runs']]
    with (STUDY / 'attempt.json').open('x') as stream:
        json.dump({'monitor': process_identity(os.getpid()), 'ready_sha256': sha(STUDY / 'ready.json')}, stream)
        stream.flush()
        os.fsync(stream.fileno())
    phase, reason, stop_time = 'search', None, None
    search_stage_cpu_seconds = None
    start, affinity = time.monotonic(), set()
    identities = [dict(process_identity(os.getpid()), name='monitor')]
    handlers = {sig: signal.signal(sig, interrupt) for sig in (signal.SIGTERM, signal.SIGINT)}

    def record(status, **extra):
        save(status_path, {'status': status, 'cpu_seconds': consumed_cpu(running), 'cap_cpu_seconds': CAP,
                          'search_cpu_seconds': SEARCH_CAP, 'confirmation_reserved_cpu_seconds': CAP - SEARCH_CAP,
                          'search_stage_cpu_seconds': search_stage_cpu_seconds,
                          'wall_seconds': time.monotonic() - start, 'phase': phase,
                          'running': {str(pid): item[2] for pid, item in running.items()},
                          'queued': list(queue), 'completed': completed, 'affinity': sorted(affinity),
                          'ready': ready, 'process_identities': identities,
                          'owned_process_groups': [item['pgid'] for item in identities if item['name'] != 'monitor'],
                          **extra})

    def unchanged():
        if check_protocol() != protocol or check_ready() != ready:
            raise ValueError('protocol or release changed')

    try:
        enable_subreaper()
        from numerical import check
        check(protocol['numerical_identity'])  # No builds or golden lives; charged monitor CPU.
        affinity = os.sched_getaffinity(0).intersection(range(12))
        if not affinity:
            raise ValueError('fast CPU set unavailable')
        os.sched_setaffinity(0, affinity)
        env = dict(os.environ, ATEN_CPU_CAPABILITY='avx2', OMP_WAIT_POLICY='PASSIVE', OMP_NUM_THREADS='2',
                   OMP_THREAD_LIMIT='2', MKL_NUM_THREADS='1', OPENBLAS_NUM_THREADS='1', PYTHONUNBUFFERED='1',
                   CELL_DEV_CACHE=str(STUDY / 'build-cache'), PYTHONDONTWRITEBYTECODE='1',
                   CELLDEV_CONTINUATION_MONITOR_PID=str(os.getpid()))
        env.pop('CELLDEV_THREADS_FILE', None)
        record('running')
        while queue or running:
            reason = reason or budget_reason(phase, consumed_cpu(running))
            if reason:
                queue.clear()
                if stop_time is None:
                    stop_time = time.monotonic()
                    for process, _, _ in running.values():
                        send_signal(process, signal.SIGTERM)
                if time.monotonic() - stop_time >= 2:
                    for process, _, _ in running.values():
                        send_signal(process, signal.SIGKILL)
            while queue and len(running) < (2 if phase == 'search' else 1) and not reason:
                unchanged()
                consumed = consumed_cpu(running)
                reason = budget_reason(phase, consumed)
                if reason:
                    break
                name = queue.pop(0)
                log_path = STUDY / 'logs' / f'{name}.log'
                log_path.parent.mkdir(parents=True, exist_ok=True)
                log = log_path.open('x')
                remaining, parent_pid = phase_limit(phase) - consumed, os.getpid()
                try:
                    process = subprocess.Popen(commands[name], cwd=ROOT, env=env, stdout=log,
                        stderr=subprocess.STDOUT, start_new_session=True,
                        preexec_fn=lambda limit=remaining, parent=parent_pid: child_limit(limit, parent))
                except BaseException:
                    log.close()
                    raise
                running[process.pid] = (process, log, name)
                identities.append(dict(process_identity(process.pid), name=name))
                print(f'Started {name}: pid {process.pid}', flush=True)
            for pid, (process, log, name) in list(running.items()):
                code = process.poll()
                if code is not None:
                    cleanup_group(process)
                    log.close()
                    completed.append({'name': name, 'exit_code': code})
                    del running[pid]
                    if code:
                        reason = reason or ('search_reserve_limit' if phase == 'search' and
                            code in (-signal.SIGXCPU, -signal.SIGKILL) else 'job_failed')
            reason = reason or budget_reason(phase, consumed_cpu(running))
            if reason:
                queue.clear()
            if not running and not queue and not reason:
                if phase == 'search':
                    search_stage_cpu_seconds = consumed_cpu(running)
                    queue, phase = ['confirmation'], 'confirmation'
                else:
                    unchanged()
                    result = json.loads((STUDY / 'confirmation/report.json').read_text())
                    if result.get('status') != 'complete' or result.get('genome_lives') != 1536:
                        raise ValueError('confirmation did not complete the registered measurement')
            record('running' if running or queue else ('incomplete' if reason else 'complete'),
                   reason=reason, exit_code=1 if reason else (None if running or queue else 0))
            if running or queue:
                time.sleep(POLL)
    except BaseException as error:
        cleanup_error = None
        try:
            cleanup(running)
        except BaseException as failure:
            cleanup_error = type(failure).__name__ + ': ' + str(failure)
        queue.clear()
        record('monitor_failed', reason=reason, error=type(error).__name__, exit_code=1,
               cleanup_error=cleanup_error)
        raise
    finally:
        for sig, handler in handlers.items():
            signal.signal(sig, handler)
    raise SystemExit(1 if reason else 0)


if __name__ == '__main__':
    main()
