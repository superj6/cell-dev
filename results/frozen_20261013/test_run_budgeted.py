"""Mock-only launch, budget and dependency checks; no scientific processes are started."""
import importlib.util
import json
import signal
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

HERE = Path(__file__).resolve().parent


@pytest.fixture
def monitor(monkeypatch, tmp_path):
    spec = importlib.util.spec_from_file_location('frozen_monitor_test', HERE / 'run_budgeted.py')
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    root = tmp_path / 'repo'
    study, dependency = root / 'outputs/autonomous_frozen_20261013', root / 'outputs/autonomous_continuation_20261013'
    study.mkdir(parents=True)
    dependency.mkdir(parents=True)
    monkeypatch.setattr(mod, 'ROOT', root)
    monkeypatch.setattr(mod, 'STUDY', study)
    monkeypatch.setattr(mod, 'DEPENDENCY', dependency)
    monkeypatch.setattr(sys, 'argv', ['run_budgeted.py', '--run'])
    for name in ('taskvar_frozen_gain.py', *mod.HELPERS):
        path = root / 'scripts' / name
        path.parent.mkdir(exist_ok=True)
        path.write_text(name)
    (root / 'src').mkdir()
    (root / 'src/kernel.c').write_text('unchanged')
    for name in ('run_budgeted.py', 'protocol.json'):
        (dependency / name).write_text(name)
    ready = {'monitor_sha256': mod.sha(Path(mod.__file__)),
             'runner_sha256': mod.sha(root / 'scripts/taskvar_frozen_gain.py'),
             'helpers': {name: mod.sha(root / 'scripts' / name) for name in mod.HELPERS},
             'source_identity': {'src/kernel.c': mod.sha(root / 'src/kernel.c')},
             'dependency': {'monitor_sha256': mod.sha(dependency / 'run_budgeted.py'),
                            'protocol_sha256': mod.sha(dependency / 'protocol.json')}}
    mod.save(study / 'ready.json', ready)
    mod.save(dependency / 'budget.json', {'status': 'running', 'running': {'1': 'evolve_s90'}, 'queued': []})
    monkeypatch.setattr(mod.os, 'sched_getaffinity', lambda pid: {0, 1, 15})
    monkeypatch.setattr(mod.os, 'sched_setaffinity', lambda pid, values: None)
    monkeypatch.setattr(mod.time, 'sleep', lambda seconds: None)
    mod.real_cpu = mod.cpu
    monkeypatch.setattr(mod, 'cpu', lambda pid: 0.)
    monkeypatch.setattr(mod.signal, 'signal', lambda *args: None)
    return mod


class Process:
    def __init__(self, code=0, alive=False, ignore_term=False):
        self.pid, self.returncode = 98765, None if alive else code
        self.ignore_term = ignore_term

    def poll(self):
        return self.returncode

    def wait(self, timeout=None):
        if timeout is not None and self.ignore_term:
            raise subprocess.TimeoutExpired('mock', timeout)
        self.returncode = -signal.SIGKILL if self.ignore_term else -signal.SIGTERM
        return self.returncode


def test_dryrun_never_starts_process_or_requires_readiness(monitor, monkeypatch, capsys):
    (monitor.STUDY / 'ready.json').unlink()
    monkeypatch.setattr(sys, 'argv', ['run_budgeted.py'])
    monkeypatch.setattr(monitor.subprocess, 'Popen', lambda *a, **k: pytest.fail('launched in dry-run'))
    monitor.main()
    result = json.loads(capsys.readouterr().out)
    assert result['status'] == 'dry_run' and result['max_cpu_seconds'] == 3600
    assert not (monitor.STUDY / 'budget.json').exists()


@pytest.mark.parametrize('kind', ['monitor', 'runner', 'helper', 'source', 'dependency'])
def test_changed_pins_refuse_before_launch(monitor, monkeypatch, kind):
    if kind == 'monitor':
        value = json.loads((monitor.STUDY / 'ready.json').read_text())
        value['monitor_sha256'] = 'changed'
        monitor.save(monitor.STUDY / 'ready.json', value)
    else:
        path = {'runner': monitor.ROOT / 'scripts/taskvar_frozen_gain.py',
                'helper': monitor.ROOT / 'scripts/taskvar_confirm.py',
                'source': monitor.ROOT / 'src/kernel.c',
                'dependency': monitor.DEPENDENCY / 'run_budgeted.py'}[kind]
        path.write_text('changed')
    monkeypatch.setattr(monitor.subprocess, 'Popen', lambda *a, **k: pytest.fail('launched altered source'))
    with pytest.raises(ValueError, match='differs'):
        monitor.main()


def test_dependency_waits_for_empty_queue_and_at_most_one_job(monitor):
    for running, queued, expected in [({'1':'a','2':'b'}, [], False), ({'1':'a'}, ['later'], False),
                                     ({'1':'a'}, [], True), ({}, [], True)]:
        monitor.save(monitor.DEPENDENCY / 'budget.json', {'status':'running','running':running,'queued':queued})
        assert monitor.dependency_available() is expected
    monitor.save(monitor.DEPENDENCY / 'budget.json', {'status':'job_failed','running':{},'queued':[]})
    with pytest.raises(ValueError, match='abnormally'):
        monitor.dependency_available()


@pytest.mark.parametrize('exit_code,report_status,expected', [(0,'complete',0),(3,'complete',1),(0,'incomplete',1)])
def test_completion_requires_good_exit_and_complete_report(monitor, monkeypatch, exit_code, report_status, expected):
    process = Process(code=exit_code)
    def popen(command, **kwargs):
        assert command[-4:] == ['--threads','2','--max-cpu-seconds','3600']
        assert kwargs['preexec_fn'] is monitor.child_limit
        assert kwargs['start_new_session'] is True
        assert kwargs['env']['OMP_NUM_THREADS'] == '2'
        assert kwargs['env']['MKL_NUM_THREADS'] == '2'
        assert 'CELLDEV_THREADS_FILE' not in kwargs['env']
        monitor.save(monitor.STUDY / 'measurement/report.json', {'status':report_status})
        return process
    monkeypatch.setenv('CELLDEV_THREADS_FILE', 'unexpected')
    monkeypatch.setattr(monitor.subprocess, 'Popen', popen)
    with pytest.raises(SystemExit) as error:
        monitor.main()
    assert error.value.code == expected
    assert json.loads((monitor.STUDY / 'budget.json').read_text())['status'] == ('complete' if expected == 0 else 'incomplete')


def test_cpu_stop_uses_term_then_kill_and_retains_failure(monitor, monkeypatch):
    process, signals = Process(alive=True, ignore_term=True), []
    monkeypatch.setattr(monitor.subprocess, 'Popen', lambda *a, **k: process)
    monkeypatch.setattr(monitor.os, 'killpg', lambda pid, sig: signals.append(sig))
    monkeypatch.setattr(monitor, 'cpu', lambda pid: 3592.)
    with pytest.raises(SystemExit) as error:
        monitor.main()
    assert error.value.code == 1
    assert signals == [signal.SIGTERM, signal.SIGKILL]
    result = json.loads((monitor.STUDY / 'budget.json').read_text())
    assert result['cpu_budget_exhausted'] is True and result['status'] == 'incomplete'


def test_exit_race_and_hard_cpu_limit(monitor, monkeypatch):
    process = Process()
    def gone(pid, sig):
        raise ProcessLookupError()
    monkeypatch.setattr(monitor.os, 'killpg', gone)
    monitor.terminate(process)
    limits = []
    monkeypatch.setattr(monitor.resource, 'setrlimit', lambda key, value: limits.append((key,value)))
    monitor.child_limit()
    assert limits == [(monitor.resource.RLIMIT_CPU,(3599,3600))]


def test_existing_budget_or_unaccounted_cache_cannot_restart(monitor, monkeypatch):
    monkeypatch.setattr(monitor.subprocess, 'Popen', lambda *a, **k: pytest.fail('restarted'))
    monitor.save(monitor.STUDY / 'budget.json', {'cpu_seconds':10})
    with pytest.raises(ValueError, match='budget record exists'):
        monitor.main()
    (monitor.STUDY / 'budget.json').unlink()
    path = monitor.STUDY / 'measurement/normal/row_0000.npz'
    path.parent.mkdir(parents=True)
    path.write_bytes(b'previous scientific work')
    with pytest.raises(ValueError, match='without a budget'):
        monitor.main()


def test_proc_cpu_indices_sum_user_and_system(monitor, monkeypatch):
    monkeypatch.setattr(monitor.resource, 'getrusage', lambda kind: SimpleNamespace(ru_utime=2.,ru_stime=3.))
    original = Path.read_text
    fields = ['S'] + ['0'] * 25
    fields[11], fields[12] = '700', '900'
    monkeypatch.setattr(Path, 'read_text', lambda path, *a, **k: ('123 (command with ) paren) ' + ' '.join(fields))
                        if str(path) == '/proc/123/stat' else original(path,*a,**k))
    monkeypatch.setattr(monitor.os, 'sysconf', lambda name: 100)
    assert monitor.real_cpu(123) == 21.


def test_sources_checked_again_after_waiting(monitor, monkeypatch):
    monitor.save(monitor.DEPENDENCY / 'budget.json', {'status':'running','running':{'1':'a','2':'b'},'queued':[]})
    def change_during_wait(seconds):
        (monitor.ROOT / 'scripts/taskvar_confirm.py').write_text('changed while queued')
        monitor.save(monitor.DEPENDENCY / 'budget.json', {'status':'running','running':{'1':'a'},'queued':[]})
    monkeypatch.setattr(monitor.time, 'sleep', change_during_wait)
    monkeypatch.setattr(monitor.subprocess, 'Popen', lambda *a, **k: pytest.fail('launched changed helper'))
    with pytest.raises(ValueError, match='helper differs'):
        monitor.main()


def test_monitor_interruption_terminates_child_and_records_failure(monitor, monkeypatch):
    process, signals = Process(alive=True), []
    monkeypatch.setattr(monitor.subprocess, 'Popen', lambda *a, **k: process)
    monkeypatch.setattr(monitor.os, 'killpg', lambda pid, sig: signals.append(sig))
    def interrupt(seconds):
        raise KeyboardInterrupt()
    monkeypatch.setattr(monitor.time, 'sleep', interrupt)
    with pytest.raises(KeyboardInterrupt):
        monitor.main()
    assert process.returncode == -signal.SIGTERM and signals == [signal.SIGTERM]
    assert json.loads((monitor.STUDY / 'budget.json').read_text())['status'] == 'monitor_failed'
