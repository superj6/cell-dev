"""AL watchdog tests use only cheap synthetic processes and fabricated receipts."""
import ast
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[3]
SOURCE = ROOT / 'outputs/autonomous_retention_selection_20261015'


def module(monkeypatch):
    monkeypatch.syspath_prepend(str(SOURCE))
    spec = importlib.util.spec_from_file_location('al_test_monitor', SOURCE / 'monitor.py')
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


def run_case(tmp_path, child, *, cpu=10., wall=5., margin=.1, extra=None, injected=''):
    study = tmp_path / 'case'
    study.mkdir()
    budget = {'cpu_seconds': cpu, 'wall_seconds': wall, 'threads': 2,
              'workers': 1, 'cleanup_margin_seconds': margin, 'minimum_available_bytes': 0}
    budget.update(extra or {})
    script = f'''
import json, sys
from pathlib import Path
import monitor
case = Path(sys.argv[1])
{injected}
result = monitor.run_worker(case, [sys.executable, '-c', {child!r}], {budget!r},
    'protocol', 'release', lambda: None, poll_seconds=.02)
print(json.dumps(result))
'''
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1', PYTHONPATH=str(SOURCE))
    value = subprocess.run([sys.executable, '-c', script, str(study)], env=env,
                           capture_output=True, text=True, timeout=12)
    (study / 'test.stdout.txt').write_text(value.stdout)
    (study / 'test.stderr.txt').write_text(value.stderr)
    return study, value, json.loads((study / 'budget.json').read_text())


def clean(value):
    proof = value['terminal_cleanup']
    assert proof['same_pid_namespace'] and proof['checked_in_monitor']
    assert proof['all_owned_groups_exited'] and proof['all_worker_identities_exited']
    assert not proof['remaining_descendants']
    assert not value['running'] and not value['queued'] and not value['cleanup_error']
    assert value['cpu_seconds'] >= sum(row['user_cpu_seconds'] + row['system_cpu_seconds']
                                      for row in value['wait4_receipts'])


def test_real_child_binding_and_address_space_limit(tmp_path):
    _, result, value = run_case(tmp_path, '''
import os, resource
from pathlib import Path
assert os.getppid() == int(os.environ['CELLDEV_MONITOR_PID'])
assert os.getpid() == os.getpgrp()
assert Path(os.environ['CELLDEV_ATTEMPT_PATH']).parent == Path.cwd()
assert resource.getrlimit(resource.RLIMIT_AS) == (128*1024**2, 128*1024**2)
assert os.environ['OMP_NUM_THREADS'] == '2'
''', extra={'address_space_bytes':128*1024**2,'rss_bytes':64*1024**2})
    assert result.returncode == 0 and value['status'] == 'complete'
    clean(value)


def test_tiny_rss_bound_stops_without_large_allocation(tmp_path):
    _, result, value = run_case(tmp_path, 'import time; time.sleep(20)', extra={'rss_bytes':1})
    assert result.returncode == 0 and value['status'] == 'incomplete'
    assert value['reason'] == 'memory_budget_exhausted'
    assert value['peak_owned_rss_bytes'] >= value['cap_rss_bytes'] == 1
    clean(value)


def test_headroom_refuses_launch(tmp_path):
    _, result, value = run_case(tmp_path, "raise AssertionError('must not launch')",
                               extra={'minimum_available_bytes':2**62})
    assert result.returncode != 0 and value['status'] == 'monitor_failed'
    assert 'before worker launch' in value['error']
    assert len(value['process_identities']) == 1 and value['wait4_receipts'] == []
    clean(value)


def test_peak_record_sample_cannot_disappear(tmp_path):
    injected = '''
calls = 0
def fake_memory(group):
    global calls
    calls += 1
    # Prelaunch, first record, first loop, then record-only crossing.
    return (100 if calls == 4 else 0), 2**40
monitor.memory_usage = fake_memory
'''
    _, result, value = run_case(tmp_path, 'import time; time.sleep(20)',
        extra={'rss_bytes':100}, injected=injected)
    assert result.returncode == 0 and value['status'] == 'incomplete'
    assert value['reason'] == 'memory_budget_exhausted' and value['peak_owned_rss_bytes'] == 100
    clean(value)


def test_escaped_descendant_killed_after_leader_exit(tmp_path):
    _, result, value = run_case(tmp_path, '''
import os, time
r,w=os.pipe()
pid=os.fork()
if pid==0:
    os.close(r); os.setsid(); os.write(w,b'x')
    while True: time.sleep(.1)
os.close(w)
assert os.read(r,1)==b'x'
os._exit(0)
''')
    assert result.returncode == 0 and value['status'] == 'complete'
    assert len(value['wait4_receipts']) == 2
    assert any(row['exit_code'] == -9 for row in value['wait4_receipts'])
    clean(value)


def test_wall_stop_clears_group(tmp_path):
    _, result, value = run_case(tmp_path, 'import time; time.sleep(20)', wall=.5)
    assert result.returncode == 0 and value['reason'] == 'wall_budget_exhausted'
    assert value['wall_seconds'] < .5
    clean(value)


def test_cpu_stop_is_cumulative(tmp_path):
    _, result, value = run_case(tmp_path, 'while True: pass', cpu=.5)
    assert result.returncode == 0 and value['reason'] == 'cpu_budget_exhausted'
    assert .4 <= value['cpu_seconds'] < .5
    clean(value)


def test_sequential_main_uses_cumulative_not_summed_cpu(tmp_path, monkeypatch):
    monitor = module(monkeypatch)
    budget = {'cpu_seconds':5400,'wall_seconds':3600,'search_cpu_seconds':3600,
              'confirmation_cpu_seconds':1800,'threads':2,'workers':1,'cleanup_margin_seconds':10,
              'rss_bytes':4*1024**3,'minimum_available_bytes':4*1024**3,'address_space_bytes':8*1024**3}
    protocol = {'budget':budget}
    monitor.save(tmp_path/'protocol.json',protocol)
    monitor.save(tmp_path/'release.json',{'pid_namespace':monitor.pid_namespace()})
    monkeypatch.setattr(monitor,'STUDY',tmp_path)
    monkeypatch.setattr(monitor,'checked_release',lambda: protocol)
    state={'cpu':.5}; caps=[]
    monkeypatch.setattr(monitor,'consumed_cpu',lambda _:state['cpu'])
    def fake_phase(path, command, budget0, protocol_sha, release_sha, complete_check):
        # Main orchestration only; real owned process lifecycle is covered above.
        phase=path.name; caps.append(budget0['cpu_seconds'])
        state['cpu'] += 100
        row={'status':'complete','process_identities':[], 'wait4_receipts':[],
             'cpu_seconds':state['cpu']}
        monitor.save(path/'budget.json',row)
        if phase=='confirmation':
            monitor.save(tmp_path/'measurement_complete.json',{'synthetic':True})
        else:
            monitor.save(tmp_path/'runs'/phase/'search_complete.json',{'synthetic':True})
        return row
    monkeypatch.setattr(monitor,'run_worker',fake_phase)
    monkeypatch.setattr(sys,'argv',['monitor.py','--run'])
    monitor.main()
    value=monitor.read(tmp_path/'budget.json')
    assert caps == [3600,3600,2000.5]
    assert value['cpu_seconds']==300.5 and value['search_cpu_seconds']==200.5
    assert value['confirmation_cpu_seconds']==100
    assert len(value['phase_records'])==3
    assert value['status']=='complete'


def test_native_scope_matches_pure_68_id_schedule():
    from audit_namespace import derive_native_ids
    rows,values=derive_native_ids()
    assert len(rows)==len(values)==68
    assert sum(row['purpose']=='gen' for row in rows)==32
    assert sum(row['purpose']=='valid' for row in rows)==32
    assert sum(row['purpose']=='final' for row in rows)==4
    assert {row['index'] for row in rows if row['purpose']=='valid'}=={0,3}
    tree=ast.parse((SOURCE/'prepare.py').read_text())
    functions={node.name:node for node in tree.body if isinstance(node,ast.FunctionDef)}
    config=ast.unparse(functions['search_config'])
    assert 'cfg.evolve.recheck_k, cfg.evolve.recheck_lives, cfg.evolve.recheck_key = (64, 4' in config
    assert "cfg.life.abi, cfg.life.control, cfg.life.lives = (3, 'retention_selection_AL', 4)" in config
    assert 'cfg.evolve.generations, cfg.evolve.heldout_every = (4, 4)' in config


def test_three_real_owned_workers_preserve_cumulative_accounting(tmp_path):
    script=r'''
import json, sys
from pathlib import Path
from monitor import run_worker
base=Path(sys.argv[1])
receipts=[]
for name in ('persistent_control','balanced_mixture','confirmation'):
    folder=base/name; folder.mkdir()
    receipts.append(run_worker(folder,[sys.executable,'-c',
        'import time; start=time.process_time()\nwhile time.process_time()-start < .08: pass'],
        {'cpu_seconds':10,'wall_seconds':5,'threads':2,'workers':1,'cleanup_margin_seconds':.1,
         'minimum_available_bytes':0},'protocol','release',lambda:None,poll_seconds=.02))
print(json.dumps(receipts))
'''
    env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1',PYTHONPATH=str(SOURCE))
    result=subprocess.run([sys.executable,'-c',script,str(tmp_path)],env=env,
                          capture_output=True,text=True,timeout=10)
    (tmp_path/'sequential.stdout.json').write_text(result.stdout)
    (tmp_path/'sequential.stderr.txt').write_text(result.stderr)
    assert result.returncode==0
    rows=json.loads(result.stdout)
    assert all(row['status']=='complete' for row in rows)
    assert rows[0]['cpu_seconds'] < rows[1]['cpu_seconds'] < rows[2]['cpu_seconds']
    assert rows[-1]['cpu_seconds'] >= sum(receipt['user_cpu_seconds']+receipt['system_cpu_seconds']
        for row in rows for receipt in row['wait4_receipts'])
    assert len({row['process_identities'][1]['pid'] for row in rows})==3
    assert len({row['process_identities'][0]['pid'] for row in rows})==1
    for row in rows: clean(row)
