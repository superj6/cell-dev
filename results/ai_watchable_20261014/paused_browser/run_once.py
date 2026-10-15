"""One separately authorized paused Firefox attempt; no retry and no simulator playback."""
from pathlib import Path
import ctypes
import datetime
import hashlib
import json
import os
import resource
import signal
import subprocess
import time

HERE = Path(__file__).resolve().parent
FIREFOX = Path('/snap/firefox/current/usr/lib/firefox/firefox')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(name, value):
    with (HERE / name).open('x') as stream:
        stream.write(json.dumps(value, indent=2, allow_nan=False) + '\n')


def table():
    rows = {}
    for path in Path('/proc').glob('[0-9]*/stat'):
        try:
            f = path.read_text().rsplit(')', 1)[1].split()
            rows[int(path.parent.name)] = {'ppid': int(f[1]), 'pgid': int(f[2]), 'start_ticks': int(f[19]),
                'cpu_ticks': sum(int(f[i]) for i in (11, 12, 13, 14))}
        except (FileNotFoundError, ProcessLookupError, PermissionError):
            pass
    return rows


def main():
    assert not any((HERE / n).exists() for n in ('attempt.json', 'execution.json', 'stdout.txt', 'stderr.txt', 'paused_firefox.png'))
    prep = json.loads((HERE / 'preparation.json').read_text())
    assert sha(HERE / 'diagnostic.html') == prep['diagnostic_html_sha256']
    assert sha(HERE / 'guard.js') == prep['guard_sha256']
    assert sha(HERE.parent / 'exploratory_reserve_replication.html') == prep['original_html_sha256']
    assert FIREFOX.is_file() and os.access(FIREFOX, os.X_OK)
    argv = [str(FIREFOX), '--headless', '--no-remote', '--profile', str(HERE / 'profile'),
            '--screenshot', str(HERE / 'paused_firefox.png'), '--window-size', '1440,1300',
            (HERE / 'diagnostic.html').as_uri()]
    env = {**os.environ, 'MOZ_HEADLESS': '1', 'MOZ_NO_REMOTE': '1', 'MOZ_CRASHREPORTER_DISABLE': '1',
           'XDG_CACHE_HOME': str(HERE / 'cache'), 'TMPDIR': str(HERE / 'tmp'), 'GSETTINGS_BACKEND': 'memory'}
    namespace = os.readlink('/proc/self/ns/pid')
    save('attempt.json', {'status': 'one_authorized_attempt', 'argv': argv, 'cwd': str(HERE),
        'started_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(), 'script_sha256': sha(Path(__file__)),
        'preparation_sha256': sha(HERE / 'preparation.json'), 'firefox_executable_sha256': sha(FIREFOX),
        'child_cpu_cap_seconds': 30, 'wall_cap_seconds': 45, 'screenshots': 1,
        'permitted_initializations': 3, 'permitted_advance_or_run_calls': 0,
        'pid_namespace': namespace, 'identity_scope': 'This execution PID namespace only, not host-global identities.'})
    lib = ctypes.CDLL(None, use_errno=True)
    if lib.prctl(36, 1, 0, 0, 0) != 0:
        raise OSError(ctypes.get_errno(), 'cannot establish child subreaper')
    before = resource.getrusage(resource.RUSAGE_CHILDREN)
    ticks = os.sysconf('SC_CLK_TCK')
    started = time.monotonic()
    proc = None
    reason = None
    identity = None
    groups = set()
    seen = {}
    def consumed(rows):
        use = resource.getrusage(resource.RUSAGE_CHILDREN)
        return (use.ru_utime + use.ru_stime - before.ru_utime - before.ru_stime
                + sum(x['cpu_ticks'] / ticks for x in rows.values() if x['pgid'] in groups))
    def limits():
        resource.setrlimit(resource.RLIMIT_CPU, (30, 30))
    with (HERE / 'stdout.txt').open('x') as out, (HERE / 'stderr.txt').open('x') as err:
        try:
            proc = subprocess.Popen(argv, cwd=HERE, env=env, stdout=out, stderr=err,
                                    start_new_session=True, preexec_fn=limits)
            groups.add(proc.pid)
            first = table().get(proc.pid)
            if first is None:
                raise RuntimeError('browser exited before identity was observed')
            identity = {'pid': proc.pid, **{k: first[k] for k in ('ppid', 'pgid', 'start_ticks')}}
            while proc.poll() is None:
                rows = table()
                for pid, row in rows.items():
                    if row['pgid'] in groups:
                        seen[pid] = {k: row[k] for k in ('ppid', 'pgid', 'start_ticks')}
                if consumed(rows) >= 29:
                    reason = 'CPU cleanup threshold reached'
                    break
                if time.monotonic() - started >= 43:
                    reason = 'wall cleanup threshold reached'
                    break
                time.sleep(.05)
        except BaseException as error:
            reason = type(error).__name__ + ': ' + str(error)
        finally:
            for group in groups:
                try:
                    os.killpg(group, signal.SIGKILL)
                except ProcessLookupError:
                    pass
            deadline = started + 45
            while time.monotonic() < deadline:
                if proc is not None:
                    proc.poll()
                while groups:
                    try:
                        pid, _ = os.waitpid(-next(iter(groups)), os.WNOHANG)
                    except ChildProcessError:
                        break
                    if pid == 0:
                        break
                if not any(x['pgid'] in groups for x in table().values()):
                    break
                time.sleep(.02)
    rows = table()
    remaining = [pid for pid, x in rows.items() if x['pgid'] in groups]
    cpu = consumed(rows)
    guard_records = [json.loads(line[len('AI_PAUSED_GUARD '):]) for line in (HERE / 'stdout.txt').read_text().splitlines()
                     if line.startswith('AI_PAUSED_GUARD ')]
    guard = guard_records[0] if len(guard_records) == 1 else None
    screenshot = HERE / 'paused_firefox.png'
    success = (proc is not None and proc.returncode == 0 and reason is None and not remaining and cpu <= 30
               and time.monotonic() - started <= 45 and screenshot.is_file() and guard is not None
               and guard['status'] == 'passed' and guard['initializations'] == 3
               and guard['times'] == [0, 0, 0] and guard['advance_calls'] == guard['run_calls'] == 0)
    save('execution.json', {'status': 'complete' if success else 'incomplete_no_retry',
        'exit_code': None if proc is None else proc.returncode, 'reason': reason,
        'cpu_seconds': cpu, 'wall_seconds': time.monotonic() - started,
        'child_cpu_cap_seconds': 30, 'wall_cap_seconds': 45, 'pid_namespace': namespace,
        'process_identity': identity, 'observed_group_members': seen, 'process_groups': sorted(groups),
        'all_processes_exited': not remaining, 'remaining': remaining, 'guard': guard,
        'screenshot_sha256': sha(screenshot) if screenshot.is_file() else None,
        'stdout_sha256': sha(HERE / 'stdout.txt'), 'stderr_sha256': sha(HERE / 'stderr.txt'),
        'completed_simulated_lives': 0, 'retry': False, 'source_changes': False,
        'identity_scope': 'Process IDs and group IDs are local to the recorded execution PID namespace.'})
    print((HERE / 'execution.json').read_text())
    raise SystemExit(0 if success else 1)


if __name__ == '__main__':
    main()
