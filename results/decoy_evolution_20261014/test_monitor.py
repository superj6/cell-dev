"""Synthetic budget and scheduling checks; never launch a scientific worker."""
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
def m(monkeypatch, tmp_path):
    loader = importlib.util.spec_from_file_location('U_monitor_review', HERE / 'run_budgeted.py')
    mod = importlib.util.module_from_spec(loader)
    loader.loader.exec_module(mod)
    mod.ROOT, mod.STUDY = tmp_path, tmp_path / 'U'
    mod.STUDY.mkdir()
    def source(relative):
        path = tmp_path / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text('synthetic pinned source ' + relative)
        return mod.sha(path)
    protocol = {'study': 'decoy_ordinary_evolution', 'max_cpu_seconds':7200, 'search_cpu_seconds':3600,
        'max_simulation_threads':4, 'runs':[53091,53092], 'generations':4,
        'planned_genome_lives':16460, 'confirmation_genome_lives':8192, 'search_genome_lives':8268,
        'startup_validation_genome_lives':6,
        'confirmation':{'labels':['I_s5_row32','I_s7_row1','s53091_final_rank0','s53092_final_rank0'],
            'seeds':list(range(52060000,52060512)), 'seed_block':106,
            'conditions':['trained','width_swapped','frozen','frozen_lateral_off'], 'threads':2},
        'seed_audit_sha256':source('U/seed_audit.json'), 'prepare_sha256':source('U/prepare.py'),
        'configs':{str(seed):{'path':f'U/configs/s{seed}.yaml','sha256':source(f'U/configs/s{seed}.yaml')}
                   for seed in mod.RUNS},
        'source_identity':{'src/engine.py':source('src/engine.py')},
        'inputs':{'inputs/founder.json':source('U/inputs/founder.json')},
        'helpers':{name:source('scripts/'+name) for name in
                   ('taskvar_confirm.py','taskvar_gradient.py','taskvar_gates.py')}}
    initial={str(seed):{'population_file':f'initialization/s{seed}.npy',
                       'file_sha256':source(f'U/initialization/s{seed}.npy')} for seed in mod.RUNS}
    mod.save(mod.STUDY/'initialization.json',{'runs':initial})
    protocol['initialization_audit_sha256']=mod.sha(mod.STUDY/'initialization.json')
    mod.save(mod.STUDY/'protocol.json',protocol)
    ready={'status':'released', 'protocol_sha256':mod.sha(mod.STUDY/'protocol.json'),
           'runner_sha256':source('U/run_budgeted.py'), 'measurement_sha256':source('U/measure.py'),
           'helpers':protocol['helpers']}
    mod.save(mod.STUDY/'ready.json',ready)
    mod.protocol,mod.ready=protocol,ready
    monkeypatch.setattr(mod,'own_cpu',lambda:0)
    monkeypatch.setattr(mod,'child_cpu',lambda:10)
    monkeypatch.setattr(mod,'active_cpu',lambda pid:0)
    monkeypatch.setattr(mod,'process_identity',lambda pid:{'pid':pid,'ppid':1,'pgid':pid,'start_ticks':42})
    monkeypatch.setattr(mod,'proc_table',lambda:{})
    monkeypatch.setattr(mod,'enable_subreaper',lambda:None)
    monkeypatch.setattr(mod.os,'waitpid',lambda *args:(_ for _ in ()).throw(ChildProcessError()))
    monkeypatch.setattr(mod.os,'killpg',lambda *args:None)
    monkeypatch.setattr(mod.os,'sched_getaffinity',lambda pid:{0,1,12})
    monkeypatch.setattr(mod.os,'sched_setaffinity',lambda *args:None)
    monkeypatch.setattr(mod.signal,'signal',lambda *args:None)
    monkeypatch.setattr(mod.time,'sleep',lambda seconds:None)
    monkeypatch.setattr(sys,'argv',['run_budgeted.py','--run'])
    return mod

class Process:
    def __init__(self, pid, code=0):
        self.pid, self.returncode = pid, code

    def poll(self):
        return self.returncode

    def wait(self, timeout=None):
        if self.returncode is None:
            raise subprocess.TimeoutExpired("mock", timeout)
        return self.returncode

def launch_mock(m, monkeypatch, codes=(0, 0, 0), report="complete", lives=8192):
    calls, processes = [], []

    def spawn(command, **kwargs):
        record = json.loads((m.STUDY / "budget.json").read_text())
        assert record["ready"] == m.ready
        assert kwargs["env"]["OMP_NUM_THREADS"] == kwargs["env"]["MKL_NUM_THREADS"] == "2"
        assert kwargs["env"]["OPENBLAS_NUM_THREADS"] == "2" and "CELLDEV_THREADS_FILE" not in kwargs["env"]
        assert kwargs["start_new_session"]
        if "--confirm-child" in command:
            assert len(processes) == 2 and all(p.returncode is not None for p in processes)
            if report is not None:
                m.save(m.STUDY / "confirmation/report.json", {"status": report, "genome_lives": lives})
        process = Process(100 + len(calls), codes[len(calls)])
        calls.append((command, kwargs))
        processes.append(process)
        return process

    monkeypatch.setattr(m.subprocess, "Popen", spawn)
    return calls, processes

def run(m, expected=0):
    with pytest.raises(SystemExit) as error:
        m.main()
    assert error.value.code == expected
    return json.loads((m.STUDY / "budget.json").read_text())

def test_dryrun_has_no_worker_or_resource_record(m, monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["run_budgeted.py"])
    monkeypatch.setattr(m.subprocess, "Popen", lambda *a, **kw: pytest.fail("launched"))
    m.main()
    result = json.loads(capsys.readouterr().out)
    assert result["simulated_lives"] == 0 and result["planned_genome_lives"] == 16460
    assert not (m.STUDY / "budget.json").exists()

def test_two_searches_precede_the_single_confirmation(m, monkeypatch):
    calls, _ = launch_mock(m, monkeypatch)
    record = run(m)
    assert len(calls) == 3 and "--confirm-child" in calls[2][0]
    assert record["status"] == "complete" and record["phase"] == "confirmation"
    assert record["running"] == {} and record["queued"] == []
    assert record["completed"] == [{"name": name, "exit_code": 0} for name in
                                    ("evolve_s53091", "evolve_s53092", "confirmation")]
    assert record["ready"] == m.ready and record["cpu_seconds"] == 10

def test_failed_search_never_launches_confirmation(m, monkeypatch):
    calls, _ = launch_mock(m, monkeypatch, codes=(1, 0))
    record = run(m, 1)
    assert len(calls) == 2 and record["status"] == "incomplete" and record["reason"] == "job_failed"

def test_final_confirmation_cpu_race_cannot_report_complete(m, monkeypatch):
    calls, _ = launch_mock(m, monkeypatch)
    monkeypatch.setattr(m, "child_cpu", lambda: m.CAP + 1 if len(calls) == 3 else 10)
    record = run(m, 1)
    assert record["status"] == "incomplete" and record["reason"] == "cpu_budget_exhausted"

def test_changed_source_before_final_report_cannot_be_complete(m, monkeypatch):
    calls, _ = launch_mock(m, monkeypatch)
    original = m.subprocess.Popen

    def change_on_confirmation(*args, **kwargs):
        process = original(*args, **kwargs)
        if len(calls) == 3:
            (m.ROOT / "src/engine.py").write_text("changed while scoring")
        return process

    monkeypatch.setattr(m.subprocess, "Popen", change_on_confirmation)
    with pytest.raises(ValueError, match="differs"):
        m.main()
    assert json.loads((m.STUDY / "budget.json").read_text())["status"] == "monitor_failed"

def test_parent_computes_remaining_limit_before_fork(m, monkeypatch):
    calls, _ = launch_mock(m, monkeypatch)
    monkeypatch.setattr(m, "active_cpu", lambda pid: 100)
    run(m)
    limits = []
    monkeypatch.setattr(m, "child_cpu", lambda: pytest.fail("child sampled parent CPU"))
    monkeypatch.setattr(m, "child_limit", lambda remaining, parent: limits.append((remaining, parent)))
    for _, kwargs in calls:
        kwargs["preexec_fn"]()
    assert [value[0] for value in limits] == [3590, 3490, 7190]
    assert all(parent == m.os.getpid() for _, parent in limits)

def test_rlimit_and_exact_parent_death_binding(m, monkeypatch):
    calls, limits = [], []
    monkeypatch.setattr(m.ctypes, "CDLL", lambda *a: SimpleNamespace(prctl=lambda *args: calls.append(args) or 0))
    monkeypatch.setattr(m.os, "getppid", lambda: 321)
    monkeypatch.setattr(m.resource, "setrlimit", lambda *args: limits.append(args))
    m.child_limit(123.75, 321)
    assert calls == [(1, signal.SIGKILL, 0, 0, 0)]
    assert limits == [(m.resource.RLIMIT_CPU, (122, 123))]

def test_lost_parent_exits_before_setting_resource_limit(m, monkeypatch):
    monkeypatch.setattr(m.ctypes, "CDLL", lambda *a: SimpleNamespace(prctl=lambda *args: 0))
    monkeypatch.setattr(m.os, "getppid", lambda: 999)
    monkeypatch.setattr(m.os, "_exit", lambda code: (_ for _ in ()).throw(SystemExit(code)))
    monkeypatch.setattr(m.resource, "setrlimit", lambda *a: pytest.fail("lost parent continued"))
    with pytest.raises(SystemExit) as error:
        m.child_limit(100, 321)
    assert error.value.code == 1

@pytest.mark.parametrize('relative',['seed_audit.json','prepare.py','initialization.json',
    'configs/s53091.yaml','inputs/founder.json','initialization/s53092.npy'])
def test_mutated_inputs_rejected(m, relative):
    (m.STUDY/relative).write_text('changed')
    with pytest.raises(ValueError,match='differs'):m.check_protocol()

@pytest.mark.parametrize('relative',['src/engine.py','scripts/taskvar_confirm.py'])
def test_mutated_source_rejected(m,relative):
    (m.ROOT/relative).write_text('changed')
    with pytest.raises(ValueError,match='differs'):m.check_protocol()

@pytest.mark.parametrize('relative',['run_budgeted.py','measure.py','protocol.json'])
def test_mutated_release_rejected(m,relative):
    (m.STUDY/relative).write_text('{}')
    with pytest.raises((ValueError,KeyError)):m.check_ready()

@pytest.mark.parametrize('report,lives',[(None,8192),('incomplete',8192),('complete',8191)])
def test_incomplete_measurement_not_success(m,monkeypatch,report,lives):
    launch_mock(m,monkeypatch,report=report,lives=lives)
    with pytest.raises((ValueError,FileNotFoundError)):m.main()
    assert json.loads((m.STUDY/'budget.json').read_text())['status']=='monitor_failed'

@pytest.mark.parametrize('name',['runs','confirmation','logs','budget.json'])
def test_no_restart_or_budget_reset(m,monkeypatch,name):
    p=m.STUDY/name
    if name=='budget.json':p.write_text('{}')
    else:p.mkdir()
    monkeypatch.setattr(m.subprocess,'Popen',lambda *a,**kw:pytest.fail('launched'))
    with pytest.raises(ValueError):m.main()


def test_search_cannot_consume_confirmation_reserve(m,monkeypatch):
    calls,_=launch_mock(m,monkeypatch)
    monkeypatch.setattr(m,'child_cpu',lambda:m.SEARCH_CAP-10 if len(calls)==2 else 10)
    record=run(m,1)
    assert len(calls)==2 and record['reason']=='search_reserve_limit'
    assert record['cpu_seconds']==3590 and not record['running'] and not record['queued']


def test_cpu_is_cumulative_across_phases(m,monkeypatch):
    calls,_=launch_mock(m,monkeypatch)
    monkeypatch.setattr(m,'child_cpu',lambda:3000 if len(calls)>=2 else 10)
    record=run(m)
    assert record['cpu_seconds']==3000
    limits=[]
    monkeypatch.setattr(m,'child_limit',lambda seconds,parent:limits.append(seconds))
    calls[-1][1]['preexec_fn']()
    assert limits==[4200]


def test_search_limit_terminates_all_live_workers(m,monkeypatch):
    calls,processes=launch_mock(m,monkeypatch,codes=(None,None))
    monkeypatch.setattr(m,'active_cpu',lambda pid:1800 if len(calls)==2 else 0)
    clock=[0.0]
    monkeypatch.setattr(m.time,'monotonic',lambda:clock[0])
    monkeypatch.setattr(m.time,'sleep',lambda seconds:clock.__setitem__(0,clock[0]+seconds))
    signals=[]
    def send(pid,signum):
        signals.append((pid,signum,clock[0]))
        if signum==signal.SIGKILL:next(p for p in processes if p.pid==pid).returncode=-signum
    monkeypatch.setattr(m.os,'killpg',send)
    record=run(m,1)
    assert len(calls)==2 and record['reason']=='search_reserve_limit'
    assert [s[1] for s in signals[:4]]==[signal.SIGTERM,signal.SIGTERM,signal.SIGKILL,signal.SIGKILL]
    assert signals[2][2]-signals[0][2]==2
    assert not record['running'] and not record['queued']


def test_spawn_failure_reaps_existing_worker(m,monkeypatch):
    calls,processes=launch_mock(m,monkeypatch,codes=(None,None))
    spawn=m.subprocess.Popen
    def fail_second(*args,**kwargs):
        if calls:raise OSError('synthetic spawn failure')
        return spawn(*args,**kwargs)
    monkeypatch.setattr(m.subprocess,'Popen',fail_second)
    def send(pid,signum):processes[0].returncode=-signum
    monkeypatch.setattr(m.os,'killpg',send)
    with pytest.raises(OSError,match='spawn failure'):m.main()
    record=json.loads((m.STUDY/'budget.json').read_text())
    assert record['status']=='monitor_failed' and not record['running'] and not record['queued']


def test_own_monitor_cpu_counts_toward_cap(m,monkeypatch):
    monkeypatch.setattr(m,'own_cpu',lambda:3580)
    monkeypatch.setattr(m.subprocess,'Popen',lambda *a,**kw:pytest.fail('launched'))
    assert run(m,1)['reason']=='search_reserve_limit'


def test_subreaper_enabled_before_any_worker(m,monkeypatch):
    events=[]
    monkeypatch.setattr(m,'enable_subreaper',lambda:events.append('subreaper'))
    launch_mock(m,monkeypatch)
    original=m.subprocess.Popen
    def spawn(*args,**kwargs):
        assert events==['subreaper']
        return original(*args,**kwargs)
    monkeypatch.setattr(m.subprocess,'Popen',spawn)
    assert run(m)['status']=='complete'


def test_subreaper_failure_prevents_launch(m,monkeypatch):
    monkeypatch.setattr(m,'enable_subreaper',lambda:(_ for _ in ()).throw(OSError('subreaper unavailable')))
    monkeypatch.setattr(m.subprocess,'Popen',lambda *args,**kwargs:pytest.fail('launched without subreaper'))
    with pytest.raises(OSError,match='subreaper'):m.main()
    record=json.loads((m.STUDY/'budget.json').read_text())
    assert record['status']=='monitor_failed' and not record['running'] and not record['queued']


def test_actual_subreaper_prctl_contract(monkeypatch):
    loader=importlib.util.spec_from_file_location('U_subreaper_contract',HERE/'run_budgeted.py')
    module=importlib.util.module_from_spec(loader);loader.loader.exec_module(module)
    calls=[]
    monkeypatch.setattr(module.ctypes,'CDLL',lambda *args:SimpleNamespace(prctl=lambda *args:calls.append(args) or 0))
    module.enable_subreaper()
    assert calls==[(36,1,0,0,0)]


def test_group_cpu_counts_reparented_descendants_after_leader_exit(monkeypatch):
    loader=importlib.util.spec_from_file_location('U_group_cpu_contract',HERE/'run_budgeted.py')
    module=importlib.util.module_from_spec(loader);loader.loader.exec_module(module)
    monkeypatch.setattr(module,'proc_table',lambda:{101:{'ppid':1,'pgrp':100,'cpu_ticks':250},
        102:{'ppid':101,'pgrp':100,'cpu_ticks':125},999:{'ppid':1,'pgrp':999,'cpu_ticks':50000}})
    monkeypatch.setattr(module.os,'sysconf',lambda key:100)
    assert module.active_cpu(100)==3.75


@pytest.mark.parametrize('descendant_cpu,expected_reason',[(13,None),(3580,'search_reserve_limit')])
def test_exited_leader_descendants_reaped_and_charged_before_transition(m,monkeypatch,descendant_cpu,expected_reason):
    calls,_=launch_mock(m,monkeypatch)
    orphans={201:{'ppid':m.os.getpid(),'pgrp':100,'cpu_ticks':100}}
    charged=[10.]
    signals=[]
    monkeypatch.setattr(m,'proc_table',lambda:dict(orphans))
    monkeypatch.setattr(m,'child_cpu',lambda:charged[0])
    monkeypatch.setattr(m.os,'killpg',lambda group,sig:signals.append((group,sig)))
    def reap(group,options):
        assert options==m.os.WNOHANG
        if group==-100 and 201 in orphans:
            orphans.pop(201);charged[0]+=descendant_cpu
            return 201,0
        raise ChildProcessError()
    monkeypatch.setattr(m.os,'waitpid',reap)
    record=run(m,1 if expected_reason else 0)
    assert record['cpu_seconds']==10+descendant_cpu and record['reason']==expected_reason
    assert not orphans and not record['running'] and not record['queued']
    assert (100,signal.SIGKILL) in signals
    assert len(calls)==(2 if expected_reason else 3)
    assert record['owned_process_groups']==list(range(100,100+len(calls)))


def test_group_teardown_timeout_is_bounded(m,monkeypatch):
    clock=[0.]
    monkeypatch.setattr(m.time,'monotonic',lambda:clock[0])
    monkeypatch.setattr(m.time,'sleep',lambda seconds:clock.__setitem__(0,clock[0]+seconds))
    monkeypatch.setattr(m,'proc_table',lambda:{201:{'pgrp':100}})
    monkeypatch.setattr(m.os,'waitpid',lambda *args:(0,0))
    with pytest.raises(RuntimeError,match='owned process group'):
        m.cleanup_group(Process(100,0))
    assert 3<=clock[0]<3.1


def test_group_teardown_failure_is_recorded_and_blocks_confirmation(m,monkeypatch):
    calls,_=launch_mock(m,monkeypatch)
    def teardown(process):
        if process.pid==100:raise RuntimeError('synthetic owned process group persists')
    monkeypatch.setattr(m,'cleanup_group',teardown)
    with pytest.raises(RuntimeError,match='persists'):m.main()
    record=json.loads((m.STUDY/'budget.json').read_text())
    assert record['status']=='monitor_failed' and record['cleanup_error']
    assert record['running']=={'100':'evolve_s53091'} and record['queued']==[]
    assert len(calls)==2


def test_exception_cleanup_kills_group_even_if_leader_already_exited(m,monkeypatch):
    calls,_=launch_mock(m,monkeypatch)
    original=m.subprocess.Popen
    def fail_second(*args,**kwargs):
        if calls:raise OSError('second spawn failed')
        return original(*args,**kwargs)
    monkeypatch.setattr(m.subprocess,'Popen',fail_second)
    orphans={201:{'pgrp':100}}
    signals=[]
    monkeypatch.setattr(m,'proc_table',lambda:dict(orphans))
    monkeypatch.setattr(m.os,'killpg',lambda group,sig:signals.append((group,sig)))
    def reap(group,options):
        if orphans:orphans.clear();return 201,0
        raise ChildProcessError()
    monkeypatch.setattr(m.os,'waitpid',reap)
    with pytest.raises(OSError,match='second spawn'):m.main()
    record=json.loads((m.STUDY/'budget.json').read_text())
    assert (100,signal.SIGKILL) in signals and not orphans
    assert not record['running'] and record['cleanup_error'] is None
