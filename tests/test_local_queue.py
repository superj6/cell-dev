"""Process-only queue checks: tiny Python commands, never an engine, build or search."""
import hashlib
import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

import pytest

from scripts import run_local_queue as queue

SCRIPT = Path(queue.__file__).resolve()


def setup(tmp_path, commands, **limits):
    folder = tmp_path / 'outputs'
    folder.mkdir()
    jobs = [dict(id=f'j{i}', argv=[sys.executable, '-c', source], cwd=str(tmp_path),
                 output=str(folder / f'job{i}')) for i, source in enumerate(commands)]
    spec = folder / 'jobs.json'
    spec.write_text(json.dumps(dict(jobs=jobs, cpu_seconds=30, wall_seconds=20, **limits)))
    output = folder / 'queue'
    argv = [sys.executable, str(SCRIPT), '--jobs', str(spec), '--out', str(output)]
    return argv, output, jobs


def read(path):
    return json.loads(path.read_text())


def wait_for(fn, seconds=8):
    until = time.monotonic() + seconds
    while time.monotonic() < until:
        try:
            result = fn()
            if result:
                return result
        except (FileNotFoundError, KeyError):
            pass
        time.sleep(.03)
    raise AssertionError('tiny process did not reach its expected state')


def test_success_failure_threads_and_explicit_retry(tmp_path):
    source = "import os,json; print(json.dumps([os.environ['OMP_NUM_THREADS'],os.nice(0)]))"
    argv, output, _ = setup(tmp_path, [source, 'raise SystemExit(7)'], max_workers=2)
    first = subprocess.run(argv, capture_output=True, text=True, timeout=15)
    assert first.returncode == 1, first.stderr
    state = read(output / 'monitor.json')
    assert [j['status'] for j in state['jobs']] == ['complete', 'failed']
    paths = [Path(j['attempts'][0]['path']) for j in state['jobs']]
    assert read(paths[0] / 'exit.json')['exit_code'] == 0
    assert read(paths[1] / 'exit.json')['exit_code'] == 7
    assert json.loads((paths[0] / 'stdout.log').read_text()) == ['2', 10]
    old = (paths[1] / 'exit.json').read_bytes()
    assert subprocess.run(argv + ['--resume'], capture_output=True, timeout=15).returncode == 1
    assert all(len(j['attempts']) == 1 for j in read(output / 'monitor.json')['jobs'])
    assert subprocess.run(argv + ['--resume', '--retry', 'j1'], capture_output=True, timeout=15).returncode == 1
    assert [len(j['attempts']) for j in read(output / 'monitor.json')['jobs']] == [1, 2]
    assert (paths[1] / 'exit.json').read_bytes() == old


def test_monitor_restart_adopts_worker_without_rerun(tmp_path):
    source = ("import pathlib,time; p=pathlib.Path('started'); "
              "p.write_text(p.read_text()+'x' if p.exists() else 'x'); time.sleep(1.2)")
    argv, output, jobs = setup(tmp_path, [source])
    proc = subprocess.Popen(argv, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    try:
        wait_for(lambda: (Path(jobs[0]['output']) / 'queue_attempts/001/worker.json').exists())
        proc.kill()
        proc.wait(timeout=3)
        result = subprocess.run(argv + ['--resume'], capture_output=True, text=True, timeout=15)
        assert result.returncode == 0, result.stderr
        state = read(output / 'monitor.json')
        assert state['status'] == 'complete' and len(state['jobs'][0]['attempts']) == 1
        assert (tmp_path / 'started').read_text() == 'x'
    finally:
        if proc.poll() is None:
            proc.terminate()
            proc.wait(timeout=5)


def test_stop_kills_owned_child_tree_but_not_unrelated_process(tmp_path):
    source = ("import subprocess,sys,time; subprocess.Popen([sys.executable,'-c','import time; time.sleep(30)']); "
              "time.sleep(30)")
    argv, output, jobs = setup(tmp_path, [source])
    unrelated = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(30)'], start_new_session=True)
    proc = subprocess.Popen(argv, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    try:
        info = wait_for(lambda: (value if value.get('child') else None)
                        if (value := read(Path(jobs[0]['output']) / 'queue_attempts/001/worker.json')) else None)
        time.sleep(.15)
        result = subprocess.run([sys.executable, str(SCRIPT), '--out', str(output), '--stop'],
                                capture_output=True, text=True, timeout=5)
        assert result.returncode == 0, result.stderr
        assert proc.wait(timeout=8) == 1
        state = read(output / 'monitor.json')
        assert state['status'] == 'stopped' and state['stop_reason'] == 'signal'
        assert not queue.alive(info['child'], queue.table())
        assert not queue.owned(info['worker'], queue.table())
        assert unrelated.poll() is None
    finally:
        if proc.poll() is None:
            proc.terminate()
            proc.wait(timeout=8)
        unrelated.terminate()
        unrelated.wait(timeout=3)


@pytest.mark.parametrize('guard,value,reason', [('wall_seconds', .35, 'wall_limit'), ('rss_bytes', 1, 'rss_limit')])
def test_package_guards_stop_without_retry(tmp_path, guard, value, reason):
    argv, output, _ = setup(tmp_path, ['import time; time.sleep(30)'])
    spec = Path(argv[3])
    config = read(spec)
    config[guard] = value
    spec.write_text(json.dumps(config))
    result = subprocess.run(argv, capture_output=True, text=True, timeout=8)
    assert result.returncode == 1, result.stderr
    state = read(output / 'monitor.json')
    assert state['status'] == 'stopped' and state['stop_reason'] == reason
    assert all(len(j['attempts']) <= 1 for j in state['jobs'])
    assert all(not queue.alive(a['worker'], queue.table()) for j in state['jobs'] for a in j['attempts'])


def test_detached_monitor_and_immutable_resume_config(tmp_path):
    argv, output, _ = setup(tmp_path, ["print('ok')"])
    result = subprocess.run(argv + ['--detach'], capture_output=True, text=True, timeout=5)
    assert result.returncode == 0 and json.loads(result.stdout)['monitor_pid'] > 1
    wait_for(lambda: read(output / 'monitor.json')['status'] == 'complete')
    spec = Path(argv[3])
    config = read(spec)
    config['jobs'][0]['argv'][-1] = "print('changed')"
    spec.write_text(json.dumps(config))
    retry = subprocess.run(argv + ['--resume'], capture_output=True, text=True, timeout=5)
    assert retry.returncode != 0 and 'exact job list' in retry.stderr


def test_reused_pid_identity_cannot_signal_current_group():
    who = queue.identity(os.getpid())
    who['start_ticks'] -= 1
    queue.send(who, signal.SIGKILL)
    assert os.getpid() > 1


def test_resume_provisional_launch_before_parent_registration(tmp_path):
    argv, output, jobs = setup(tmp_path, ["from pathlib import Path; Path('accepted_once').write_text('yes')"])
    cfg = queue.load_jobs(Path(argv[3]))
    output.mkdir()
    attempt = Path(jobs[0]['output']) / 'queue_attempts/001'
    attempt.mkdir(parents=True)
    queue.save(attempt / 'job.json', cfg['jobs'][0])
    state = dict(version=1, jobs_sha256=hashlib.sha256(json.dumps(cfg, sort_keys=True).encode()).hexdigest(),
                 started_at=time.time(), monitor_cpu=0., peak_rss_bytes=0,
                 jobs=[dict(spec=cfg['jobs'][0], status='launching', attempts=[dict(
                     path=str(attempt), worker=None, cpu_seconds=0., launched_at=time.time())])])
    queue.save(output / 'monitor.json', state)
    child = subprocess.Popen([sys.executable, str(SCRIPT), '--worker', str(attempt / 'job.json'),
                              '--out', str(attempt)], start_new_session=True,
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    try:
        info = wait_for(lambda: read(attempt / 'worker.json'))
        assert info['child'] is None and not (tmp_path / 'accepted_once').exists()
        result = subprocess.run(argv + ['--resume'], capture_output=True, text=True, timeout=15)
        assert result.returncode == 0, result.stderr
        assert child.wait(timeout=3) == 0
        assert (tmp_path / 'accepted_once').read_text() == 'yes'
        assert len(read(output / 'monitor.json')['jobs'][0]['attempts']) == 1
    finally:
        if child.poll() is None:
            queue.send(queue.identity(child.pid), signal.SIGKILL)
            child.wait(timeout=3)


def test_exited_job_background_child_is_cleaned_before_success(tmp_path):
    source = ("import subprocess,sys; p=subprocess.Popen([sys.executable,'-c','import time; time.sleep(30)']); "
              "print(p.pid,flush=True)")
    argv, output, _ = setup(tmp_path, [source])
    result = subprocess.run(argv, capture_output=True, text=True, timeout=10)
    assert result.returncode == 0, result.stderr
    attempt = Path(read(output / 'monitor.json')['jobs'][0]['attempts'][0]['path'])
    assert read(attempt / 'exit.json')['cleanup_complete']
    pid = int((attempt / 'stdout.log').read_text())
    assert pid not in queue.table() or queue.table()[pid]['state'] == 'Z'
