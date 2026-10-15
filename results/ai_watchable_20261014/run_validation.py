"""Draft first-attempt wrapper for exactly three existing AI JS lives; no default replay."""
import argparse
import datetime
import hashlib
import json
import os
import resource
import signal
import subprocess
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--validate', action='store_true')
    args = parser.parse_args()
    if not args.validate:
        print(json.dumps({'status': 'source_only_unreleased', 'js_replay_lives': 0}))
        return
    export = json.loads((HERE / 'export_receipt.json').read_text())
    assert export['status'] == 'exported_without_simulation' and export['seed'] == 52360000
    for name, digest in export['draft_source_pins'].items():
        assert sha(HERE / name) == digest, name
    for name, digest in export['source_pins'].items():
        assert sha(Path(name)) == digest, name
    assert not any((HERE / n).exists() for n in ('validation_attempt.json', 'validation_budget.json', 'replay_stdout.json', 'replay_stderr.txt'))
    pins = {name: sha(HERE / name) for name in ('check_replay.js', 'bodies.json', 'truth.json', 'run_validation.py')}
    engine_sha = sha(ROOT / 'results/atlas/play/lifesim.js')
    attempt = {'scope': 'Three existing first-seed AI JS replays, not fresh research observations.',
               'status': 'authorized_export_bound', 'cpu_cap_seconds': 120, 'wall_cap_seconds': 180,
               'source_pins': pins, 'engine_sha256': engine_sha,
               'started_utc': datetime.datetime.now(datetime.timezone.utc).isoformat()}
    with (HERE / 'validation_attempt.json').open('x') as stream:
        stream.write(json.dumps(attempt, indent=2) + '\n')
    start = time.monotonic()
    before = resource.getrusage(resource.RUSAGE_CHILDREN)
    def limit():
        resource.setrlimit(resource.RLIMIT_CPU, (120, 120))
    with (HERE / 'replay_stdout.json').open('x') as out, (HERE / 'replay_stderr.txt').open('x') as err:
        proc = subprocess.Popen(['node', str(HERE / 'check_replay.js')], stdout=out, stderr=err,
                env={**os.environ, 'CELL_DEV_VIEWER_VALIDATION': 'AI_three_existing_lives'},
                preexec_fn=limit, start_new_session=True)
        identity = {'pid': proc.pid, 'pgid': proc.pid, 'ppid': os.getpid(), 'start_ticks': None}
        reason = None
        try:
            fields = Path(f'/proc/{proc.pid}/stat').read_text().rsplit(')', 1)[1].split()
            identity['start_ticks'] = int(fields[19])
            code = proc.wait(timeout=180)
        except BaseException as error:
            reason = type(error).__name__ + ': ' + str(error)
            code = -1
        finally:
            try:
                os.killpg(proc.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            proc.wait()
    after = resource.getrusage(resource.RUSAGE_CHILDREN)
    cpu = after.ru_utime + after.ru_stime - before.ru_utime - before.ru_stime
    survivors = []
    for path in Path('/proc').glob('[0-9]*/stat'):
        try:
            fields = path.read_text().rsplit(')', 1)[1].split()
            if int(fields[2]) == proc.pid:
                survivors.append(int(path.parent.name))
        except (FileNotFoundError, ProcessLookupError, PermissionError):
            pass
    complete = code == 0 and reason is None and not survivors and cpu <= 120
    receipt = {'status': 'complete' if complete else 'incomplete', 'exit_code': code, 'reason': reason,
               'cpu_seconds': cpu, 'wall_seconds': time.monotonic()-start, 'cap_cpu_seconds': 120,
               'processes': [identity], 'process_groups': [proc.pid], 'running': survivors, 'queued': [],
               'all_processes_exited': not survivors, 'cleanup_error': survivors or None,
               'source_pins': pins, 'engine_sha256': engine_sha,
               'stdout_sha256': sha(HERE / 'replay_stdout.json'), 'stderr_sha256': sha(HERE / 'replay_stderr.txt'),
               'js_replay_lives': 3 if complete else None, 'new_C_lives': 0, 'new_research_lives': 0}
    with (HERE / 'validation_budget.json').open('x') as stream:
        stream.write(json.dumps(receipt, indent=2) + '\n')
    print(json.dumps(receipt, indent=2))
    raise SystemExit(0 if complete else 1)


if __name__ == '__main__':
    main()
