"""Local orchestration only: fixed preregistered cohort, four workers, two CPU-hours."""
import argparse
import json
import os
import resource
import signal
import subprocess
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
STUDY = Path(__file__).resolve().parent
CAP = 7200.0


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
    parser.add_argument('phase', choices=['screens', 'followup'])
    args = parser.parse_args()
    status_path = STUDY / f'budget_{args.phase}.json'
    if status_path.exists():
        raise SystemExit('Phase already has a budget record; inspect before any restart.')
    # Reserve the complete 32-life benchmark plus orchestration overhead.
    previous = 10.0 + sum(json.loads(p.read_text())['cpu_seconds'] for p in STUDY.glob('budget_*.json'))
    queue = []
    for body in (5, 7):
        for world in ('base', 'pool'):
            name = f's{body}_{world}_T1024_b80'
            if args.phase == 'screens':
                command = [str(ROOT / '.venv/bin/python'), '-m', 'scripts.taskvar_gradient',
                           '--body', str(body), '--world', world, '--mutants', '64', '--lives', '32',
                           '--duration', '1024', '--seed-block', '80', '--threads', '2',
                           '--out', str(STUDY / 'screens'), '--run']
            else:
                command = [str(ROOT / '.venv/bin/python'), '-m', 'scripts.taskvar_confirm',
                           '--screen', str(STUDY / 'screens' / name),
                           '--parent', str(ROOT / 'outputs/catch_pilot' /
                                           f'speck_lmax4_hexprism_sex_s{body}/best_genome.json'),
                           '--rescore-block', '81', '--confirm-block', '82', '--lesion-block', '83',
                           '--lesion-lives', '256', '--threads', '2', '--run']
            queue.append((name, command))
    env = dict(os.environ, ATEN_CPU_CAPABILITY='avx2', OMP_WAIT_POLICY='PASSIVE', OMP_NUM_THREADS='2',
               MKL_NUM_THREADS='2', CELL_DEV_CACHE=str(ROOT / 'outputs/e1_resume/kernel-cache'),
               PYTHONUNBUFFERED='1')
    running = {}
    completed = []
    start = time.monotonic()
    stopped = None
    while queue or running:
        consumed = child_cpu() + sum(active_cpu(pid) for pid in running)
        # Leave one polling interval of four-worker CPU so the hard cap is respected.
        if previous + consumed >= CAP - 10.0:
            stopped = 'cpu_budget_exhausted'
        if stopped:
            queue.clear()
            for pid in running:
                try:
                    os.killpg(pid, signal.SIGTERM)
                except ProcessLookupError:
                    pass
        while queue and len(running) < 2 and not stopped:
            name, command = queue.pop(0)
            log = (STUDY / 'logs' / f'{args.phase}_{name}.log').open('a')
            process = subprocess.Popen(command, cwd=ROOT, env=env, stdout=log, stderr=subprocess.STDOUT,
                                       start_new_session=True)
            running[process.pid] = (process, log, name)
            print(f'Started {name}: pid {process.pid}', flush=True)
        for pid, (process, log, name) in list(running.items()):
            code = process.poll()
            if code is not None:
                log.close()
                completed.append({'name': name, 'exit_code': code})
                del running[pid]
                print(f'Finished {name}: exit {code}', flush=True)
                if code and not stopped:
                    stopped = 'job_failed'
        consumed = child_cpu() + sum(active_cpu(pid) for pid in running)
        save(status_path, {'phase': args.phase, 'cpu_seconds': consumed, 'prior_cpu_seconds': previous,
                           'total_cpu_seconds': previous + consumed, 'cap_cpu_seconds': CAP,
                           'wall_seconds': time.monotonic() - start, 'running': list(running),
                           'completed': completed, 'queued': [entry[0] for entry in queue],
                           'status': stopped or ('running' if running or queue else 'complete')})
        if running or queue:
            time.sleep(2)
    raise SystemExit(1 if stopped else 0)


if __name__ == '__main__':
    main()
