"""Synthetic watchdog lifecycle tests: no cell engines, genomes, or simulated lives."""
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
STUDY = ROOT / 'outputs/autonomous_retention_frontier_20261015'


def run_case(tmp_path, child, *, fail_check=False, wall=10., cpu=10., margin=.3):
    case = tmp_path / 'case'
    case.mkdir()
    script = '''
import json, sys
from pathlib import Path
from monitor import run_worker
case = Path(sys.argv[1])
def complete():
    if FAIL_CHECK:
        raise ValueError('synthetic completion error')
result = run_worker(case, [sys.executable, '-c', CHILD],
    {'cpu_seconds': CPU, 'wall_seconds': WALL, 'threads': 2, 'workers': 1,
     'cleanup_margin_seconds': MARGIN}, 'protocol', 'release', complete, poll_seconds=.02)
print(json.dumps(result))
'''
    script = script.replace('FAIL_CHECK', repr(fail_check)).replace('CHILD', repr(child))
    script = script.replace('CPU', repr(cpu)).replace('WALL', repr(wall)).replace('MARGIN', repr(margin))
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1', PYTHONPATH=str(STUDY))
    result = subprocess.run([sys.executable, '-c', script, str(case)], env=env,
                            capture_output=True, text=True, timeout=15)
    (case / 'test_monitor.stdout.txt').write_text(result.stdout)
    (case / 'test_monitor.stderr.txt').write_text(result.stderr)
    return case, result, json.loads((case / 'budget.json').read_text())


def clean(budget):
    proof = budget['terminal_cleanup']
    assert proof['same_pid_namespace'] and proof['checked_in_monitor']
    assert proof['all_owned_groups_exited'] and proof['all_worker_identities_exited']
    assert not proof['remaining_descendants']
    assert not budget['running'] and not budget['queued'] and not budget['cleanup_error']
    assert budget['cpu_seconds'] >= sum(x['user_cpu_seconds'] + x['system_cpu_seconds']
                                        for x in budget['wait4_receipts'])


def test_complete_and_inherited_binding(tmp_path):
    _, result, budget = run_case(tmp_path, '''
import os
assert os.getppid() == int(os.environ['CELLDEV_MONITOR_PID'])
assert os.getpid() == os.getpgrp()
assert os.environ['CELLDEV_PROTOCOL_SHA256'] == 'protocol'
assert os.environ['OMP_NUM_THREADS'] == '2'
assert 'CELLDEV_THREADS_FILE' not in os.environ
print('synthetic worker complete')
''')
    assert result.returncode == 0
    assert budget['status'] == 'complete' and budget['exit_code'] == budget['worker_exit_code'] == 0
    assert len(budget['process_identities']) == 2 and len(budget['wait4_receipts']) == 1
    clean(budget)


def test_wall_timeout_reaps_owned_group(tmp_path):
    _, result, budget = run_case(tmp_path, 'import time; time.sleep(30)', wall=.8)
    assert result.returncode == 0  # wrapper returns the incomplete receipt
    assert budget['status'] == 'incomplete' and budget['reason'] == 'wall_budget_exhausted'
    assert budget['wall_seconds'] < .8
    clean(budget)


def test_cpu_timeout_counts_actual_work(tmp_path):
    _, _, budget = run_case(tmp_path, 'while True: pass', cpu=.6, margin=.2)
    assert budget['status'] == 'incomplete' and budget['reason'] == 'cpu_budget_exhausted'
    assert .4 <= budget['cpu_seconds'] < .6
    clean(budget)


def test_leader_exit_clears_surviving_descendant(tmp_path):
    _, result, budget = run_case(tmp_path, '''
import os, time
pid = os.fork()
if pid == 0:
    while True: time.sleep(.1)
os._exit(0)
''')
    assert result.returncode == 0 and budget['status'] == 'complete'
    assert len(budget['wait4_receipts']) == 2
    assert any(row['exit_code'] == -9 for row in budget['wait4_receipts'])
    clean(budget)


def test_completion_error_preserves_failed_receipt(tmp_path):
    _, result, budget = run_case(tmp_path, 'pass', fail_check=True)
    assert result.returncode != 0
    assert budget['status'] == 'monitor_failed'
    assert budget['error'] == 'ValueError: synthetic completion error'
    clean(budget)


def test_escaped_descendant_is_identity_checked_and_cleared(tmp_path):
    _, result, budget = run_case(tmp_path, '''
import os, time
read_fd, write_fd = os.pipe()
pid = os.fork()
if pid == 0:
    os.close(read_fd)
    os.setsid()
    os.write(write_fd, b'ready')
    while True: time.sleep(.1)
os.close(write_fd)
assert os.read(read_fd, 5) == b'ready'
os._exit(0)
''')
    assert result.returncode == 0 and budget['status'] == 'complete'
    assert len(budget['wait4_receipts']) == 2
    assert any(row['exit_code'] == -9 for row in budget['wait4_receipts'])
    clean(budget)


def test_refuses_repeated_attempt_before_launch(tmp_path, monkeypatch):
    monkeypatch.syspath_prepend(str(STUDY))
    import monitor
    (tmp_path / 'attempt.json').write_text('{}')
    with pytest.raises(ValueError, match='previous execution'):
        monitor.run_worker(tmp_path, ['never-executed'],
            {'cpu_seconds': 10, 'wall_seconds': 10, 'threads': 2, 'workers': 1,
             'cleanup_margin_seconds': 1}, 'p', 'r', lambda: None)
