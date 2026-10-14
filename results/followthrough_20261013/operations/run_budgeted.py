"""Run registered experiments when their tested runner is marked ready; enforce a shared CPU cap."""
import argparse
import hashlib
import json
import os
import resource
import signal
import subprocess
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
STUDY = Path(__file__).resolve().parent


def save(path, value):
    temp = path.with_suffix('.tmp')
    temp.write_text(json.dumps(value, indent=2) + '\n')
    temp.replace(path)


def child_cpu():
    value = resource.getrusage(resource.RUSAGE_CHILDREN)
    return value.ru_utime + value.ru_stime


def active_cpu(pid):
    try:
        fields = Path(f'/proc/{pid}/stat').read_text().rsplit(')', 1)[1].split()
        return (int(fields[11]) + int(fields[12])) / os.sysconf('SC_CLK_TCK')
    except FileNotFoundError:
        return 0.0


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('phase', choices=['ab', 'factorial'])
    args = parser.parse_args()
    cap = 7200.0 if args.phase == 'ab' else 1800.0
    queue = ['transfer', 'second_step'] if args.phase == 'ab' else ['factorial']
    status_path = STUDY / f'budget_{args.phase}.json'
    if status_path.exists():
        raise SystemExit('Existing budget record: inspect resource use before any restart.')
    fast_cpus = os.sched_getaffinity(0).intersection(range(12))
    if not fast_cpus:
        raise SystemExit('Expected fast CPUs0-11 are unavailable; inspect host affinity.')
    os.sched_setaffinity(0, fast_cpus)
    env = dict(os.environ, ATEN_CPU_CAPABILITY='avx2', OMP_WAIT_POLICY='PASSIVE', OMP_NUM_THREADS='2',
               MKL_NUM_THREADS='2', CELL_DEV_CACHE=str(ROOT / 'outputs/e1_resume/kernel-cache'),
               PYTHONUNBUFFERED='1')
    running, completed = {}, []
    start = time.monotonic()
    stopped = None
    while queue or running:
        consumed = child_cpu() + sum(active_cpu(pid) for pid in running)
        # Four workers can consume at most eight CPU-seconds per two-second polling interval.
        if consumed >= cap - 10.0:
            stopped = 'cpu_budget_exhausted'
        if stopped:
            queue.clear()
            for pid in running:
                try:
                    os.killpg(pid, signal.SIGTERM)
                except ProcessLookupError:
                    pass
        for name in list(queue):
            ready = STUDY / f'{name}.ready.json'
            if len(running) >= 2 or stopped or not ready.exists():
                continue
            script = ROOT / 'scripts' / f'taskvar_{name}.py'
            digest = hashlib.sha256(script.read_bytes()).hexdigest()
            if json.loads(ready.read_text())['runner_sha256'] != digest:
                stopped = 'runner_changed_after_validation'
                break
            command = [str(ROOT / '.venv/bin/python'), '-m', f'scripts.taskvar_{name}',
                       '--out', str(STUDY / name), '--threads', '2', '--run']
            if name == 'transfer':
                command.extend(['--max-cpu-seconds', '7200'])
            log = (STUDY / 'logs' / f'{name}.log').open('a')
            process = subprocess.Popen(command, cwd=ROOT, env=env, stdout=log, stderr=subprocess.STDOUT,
                                       start_new_session=True)
            running[process.pid] = (process, log, name, digest)
            queue.remove(name)
            print(f'Started {name}: pid {process.pid}', flush=True)
        for pid, (process, log, name, digest) in list(running.items()):
            code = process.poll()
            if code is not None:
                log.close()
                completed.append({'name': name, 'exit_code': code, 'runner_sha256': digest})
                del running[pid]
                print(f'Finished {name}: exit {code}', flush=True)
                if code and not stopped:
                    stopped = 'job_failed'
        consumed = child_cpu() + sum(active_cpu(pid) for pid in running)
        save(status_path, {'phase': args.phase, 'cpu_seconds': consumed, 'cap_cpu_seconds': cap,
                           'wall_seconds': time.monotonic() - start, 'affinity': sorted(fast_cpus),
                           'running': {str(pid): entry[2] for pid, entry in running.items()},
                           'completed': completed, 'queued': queue,
                           'status': stopped or ('running' if running or queue else 'complete')})
        if running or queue:
            time.sleep(2)
    raise SystemExit(1 if stopped else 0)


if __name__ == '__main__':
    main()
