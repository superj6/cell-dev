"""Synthetic and source-only safety checks. No kernel compilation or simulation."""
import copy
import ctypes
import json
import os
from pathlib import Path
import subprocess
import sys
import numpy as np
import pytest

sys.path.insert(0,str(Path(__file__).resolve().parent))
import common
import frozen
import raw
import prepare


@pytest.fixture(scope='module')
def value():
    return common.read(common.STUDY/'protocol.json')


def test_exact_scope_and_unchanged_inputs(value):
    assert value['monitor_scope']['research_lives']==2*13*512
    assert value['monitor_scope']['validation_lives']==16+24+30+12
    assert value['monitor_scope']['total_cpu_seconds']==3599
    assert value['monitor_scope']['validation_cpu_seconds']==179
    assert value['seeds']==list(range(52130000,52130512))
    assert value['validation_seeds']==[52160000,52160001]
    assert set(value['seeds']).isdisjoint(value['validation_seeds'])
    inputs=common.read(common.STUDY/'inputs/recovered_inputs.json')
    H=frozen.load_harness()
    for name,world in value['worlds'].items():
        assert world['candidates']==[prepare.candidate_arrays(H,x) for x in prepare.descriptions(inputs['worlds'][name])]
        full=next(x for x in world['candidates'] if x['role']=='I')
        assert full['params']==inputs['worlds'][name]['full_parameters']
        assert full['cell_count']==56
        assert len(full['sense_sites'])==19 and len(full['act_sites'])==37
        for role,indexes in [('A',[9,10,21]),('B',[26])]:
            candidate=next(x for x in world['candidates'] if x['role']==role)
            assert candidate['changed_parameter_indices']==indexes
            assert candidate['cells']==full['cells'] and candidate['program']==full['program']
            assert candidate['isolates_capability'] is False
    assert common.sha(common.STUDY/'original/controllers/mem_ctl.c')==inputs['controller_sha256']


def test_fresh_process_frozen_imports_compile_disabled():
    code="""import frozen,sys
H=frozen.load_harness()
assert H.build.KERNEL.version==3
assert H.KERNEL is H.spec.V3
assert list(H.spec.V3.SIZES.values())==[3,875,129,66,57,5,23,1024,7,18]
frozen.modules_pinned()
for f in (H.load,H.build.load,H.build.build):
 try:f()
 except ValueError:pass
 else:raise AssertionError('implicit compilation allowed')
assert 't8_score' not in sys.modules
print('frozen no simulation')
"""
    result=subprocess.run([sys.executable,'-c',code],cwd=common.STUDY,capture_output=True,text=True)
    assert result.returncode==0,result.stderr
    assert result.stdout.strip()=='frozen no simulation'


def test_loaded_main_engine_rejected():
    code="""import sys
sys.path.insert(0,sys.argv[1])
import src.life.spec
import frozen
try:frozen.load_harness()
except ValueError as e:assert 'unfrozen engine' in str(e)
else:raise AssertionError('accepted main ABI4 import')
"""
    result=subprocess.run([sys.executable,'-c',code,str(common.ROOT)],cwd=common.STUDY,capture_output=True,text=True)
    assert result.returncode==0,result.stderr


@pytest.mark.parametrize('world',common.WORLDS)
@pytest.mark.parametrize('role',common.ROLES)
def test_all_fixed_arrays_match_archived_packing(value,world,role):
    H=frozen.load_harness()
    entry=value['worlds'][world];candidate=next(x for x in entry['candidates'] if x['role']==role)
    arrays,base=raw.prepare_arrays(candidate,entry,[1,2])
    ws=H.WorldSpec(world,over={'T':1024},x=entry['scratch_slots'])
    expected,_=H.world_vectors(ws,H.build._seeds([1,2]),flags=H.V3.flags('program_mode')|candidate['body_flags'])
    assert arrays['world'].tobytes()==expected.tobytes()
    assert arrays['world'][0].tolist()==entry['packed_world']
    assert arrays['cells'].shape==(2,1024,4)
    if 'params' in candidate:
        assert arrays['params'].shape==(2,30)
        assert np.all(arrays['flags']==6)
        assert np.all(arrays['latency']==base.d0)


@pytest.mark.parametrize('field,dtype,shape',[('world','float64',(2,70)),('ledger','float64',(2,58)),
    ('hashes','uint64',(2,4)),('program','float64',(1,119)),('cells','int32',(2,4096,4)),
    ('params','float64',(2,29)),('seeds','int64',(2,4)),('world','float32',(2,66))])
def test_boundary_rejects_abi_stride_and_dtype(value,field,dtype,shape):
    world=value['worlds']['blink20'];candidate=world['candidates'][2]
    arrays,_=raw.prepare_arrays(candidate,world,[1,2])
    arrays[field]=np.zeros(shape,dtype=dtype)
    with pytest.raises(ValueError):raw.validate_boundary(arrays,2,True)


def test_boundary_rejects_strided_array(value):
    world=value['worlds']['blink20'];arrays,_=raw.prepare_arrays(world['candidates'][2],world,[1,2])
    arrays['world']=np.zeros((2,132))[:,::2]
    with pytest.raises(ValueError):raw.validate_boundary(arrays,2,True)


@pytest.mark.parametrize('field,value_',[('flags',7),('cids',1101),('latency',.5),('tref',1)])
def test_boundary_rejects_action_drift(value,field,value_):
    world=value['worlds']['blink20'];arrays,_=raw.prepare_arrays(world['candidates'][2],world,[1,2])
    arrays[field][:]=value_
    with pytest.raises(ValueError):raw.validate_boundary(arrays,2,True)


def test_missing_library_never_autobuilds(tmp_path):
    with pytest.raises(ValueError,match='no implicit build'):
        frozen.checked_library(tmp_path/'absent.so','0'*64)
    assert not list(tmp_path.iterdir())


class Function:
    def __init__(self,callback):self.callback=callback
    def __call__(self,*args):return self.callback(*args)


@pytest.mark.parametrize('version,sizes',[(4,[4,875,129,70,58,5,23,1024,7,18]),(3,[3,875,129,66,58,5,23,1024,7,18])])
def test_wrong_library_abi_rejected_before_simulation(monkeypatch,tmp_path,version,sizes):
    path=tmp_path/'fake.so';path.write_bytes(b'fake, never dynamically loaded')
    class Fake:
        def __init__(self):
            self.life_abi_version=Function(lambda:version)
            self.life_sizes=Function(lambda out:[out.__setitem__(i,v) for i,v in enumerate(sizes)])
        def __getattr__(self,key):
            if key in ('life_run','ctl_life_run'):
                return Function(lambda *args:pytest.fail('simulation called'))
            return Function(lambda *args:None)
    monkeypatch.setattr(ctypes,'CDLL',lambda p:Fake())
    with pytest.raises(ValueError,match='ABI/stride'):
        frozen.checked_library(path,common.sha(path))


def test_numerical_identity_is_enforced(value,monkeypatch):
    import numerical
    assert numerical.identity()==value['numerical_identity']
    changed=copy.deepcopy(value['numerical_identity']);changed['compiler_sha256']='0'*64
    with pytest.raises(ValueError,match='numerical'):
        numerical.check(changed)


def synthetic_ledger(base):
    H=frozen.load_harness();ledger=np.zeros((1,57))
    ledger[0,H.V3.L['t_end']]=base.t0+base.T
    return ledger


@pytest.mark.parametrize('status',['extinct','guard_cells','guard_events','capacity','ledger_mismatch','fate_overflow','raster_overflow'])
def test_invalid_static_life_rejected(value,status):
    H=frozen.load_harness();base=H.spec.World(**value['worlds']['blink20']['base_world'])
    ledger=synthetic_ledger(base);ledger[0,H.V3.L['status']]=H.spec.STATUS[status]
    with pytest.raises(ValueError):raw.validate_ledger(ledger,base)


def test_scratch_capture_aliases_not_priced(value):
    H=frozen.load_harness();base=H.spec.World(**value['worlds']['blink20']['base_world'])
    ledger=synthetic_ledger(base)
    ledger[0,H.V3.L['captures']]=2
    ledger[0,21:23]=[1,2]
    raw.validate_ledger(ledger,base)
    ledger[0,21]=3
    with pytest.raises(ValueError,match='capture aliases'):raw.validate_ledger(ledger,base)


@pytest.mark.parametrize('name',['prepare.py','measure.py','validate.py','production_run.py'])
def test_default_commands_are_dry_runs(name):
    result=subprocess.run([sys.executable,str(common.STUDY/name)],capture_output=True,text=True)
    assert result.returncode==0,result.stderr
    assert json.loads(result.stdout)['status']=='dry_run'
    assert not (common.STUDY/'validation').exists()
    assert not (common.STUDY/'rows').exists()


def test_no_release_or_build_artifacts():
    assert not (common.STUDY/'ready.json').exists()
    assert not (common.STUDY/'budget.json').exists()
    assert not list((common.STUDY/'original').rglob('*.so'))


def ownership_fixture(monkeypatch,tmp_path,nested=False):
    monkeypatch.setattr(common,'STUDY',tmp_path)
    common.save(tmp_path/'ready.json',{'status':'released'})
    common.save(tmp_path/'attempt.json',{'monitor':{'pid':100,'start_ticks':777},'ready_sha256':common.sha(tmp_path/'ready.json')})
    common.save(tmp_path/'budget.json',{'status':'running','phase':'validation','running':{}})
    monkeypatch.setenv('CELLDEV_VISIBILITY_MONITOR_PID','100')
    monkeypatch.setattr(os,'getpid',lambda:300 if nested else 200)
    monkeypatch.setattr(os,'getppid',lambda:200 if nested else 100)
    monkeypatch.setattr(os,'getpgrp',lambda:200)
    monkeypatch.setattr(os,'getsid',lambda pid:200)
    identities={100:{'pid':100,'start_ticks':777,'ppid':50,'pgid':50,'sid':50},
                200:{'pid':200,'start_ticks':888,'ppid':100,'pgid':200,'sid':200}}
    monkeypatch.setattr(common,'process_identity',lambda pid:identities[pid])
    return identities


@pytest.mark.parametrize('nested',[False,True])
def test_owned_startup_before_running_map_publication(monkeypatch,tmp_path,nested):
    ownership_fixture(monkeypatch,tmp_path,nested)
    common.parent_check(200 if nested else 100,nested=nested,phase='validation')


@pytest.mark.parametrize('change',['env','start','phase','terminal','ready','parent','pgrp','sid'])
def test_owned_worker_rejects_bypass_or_stale_attempt(monkeypatch,tmp_path,change):
    identities=ownership_fixture(monkeypatch,tmp_path)
    expected=100
    if change=='env':monkeypatch.setenv('CELLDEV_VISIBILITY_MONITOR_PID','200')
    elif change=='start':identities[100]['start_ticks']=1
    elif change=='phase':common.save(tmp_path/'budget.json',{'status':'running','phase':'research'})
    elif change=='terminal':common.save(tmp_path/'budget.json',{'status':'complete','phase':'validation'})
    elif change=='ready':common.save(tmp_path/'ready.json',{'status':'different'})
    elif change=='parent':
        expected=50;monkeypatch.setattr(os,'getppid',lambda:50)
    elif change=='pgrp':monkeypatch.setattr(os,'getpgrp',lambda:99)
    elif change=='sid':monkeypatch.setattr(os,'getsid',lambda _:99)
    with pytest.raises(ValueError):common.parent_check(expected,phase='validation')


@pytest.mark.parametrize('field',['ppid','pgid','sid'])
def test_production_nested_parent_chain_checked(monkeypatch,tmp_path,field):
    identities=ownership_fixture(monkeypatch,tmp_path,nested=True)
    identities[200][field]=55
    with pytest.raises(ValueError):common.parent_check(200,nested=True,phase='validation')


@pytest.mark.parametrize('order',['fresh','frozen_first','production_first','system_first'])
def test_consistent_openmp_initialization_fresh_worker_process(order):
    code='''import ctypes,json,sys
from pathlib import Path
order=sys.argv[1]
if order=='system_first':ctypes.CDLL('/usr/lib/x86_64-linux-gnu/libgomp.so.1')
if order=='frozen_first':
 import frozen
 frozen.load_harness()
if order=='production_first':
 sys.path.insert(0,sys.argv[2])
 from src.life import spec,build
 assert build.KERNEL is spec.V4
import numerical
expected=json.loads(Path('protocol.json').read_text())['numerical_identity']
try:numerical.check(expected)
except ValueError:
 assert order=='system_first'
else:assert order!='system_first'
print('checked')
'''
    env=dict(os.environ,ATEN_CPU_CAPABILITY='avx2',OMP_WAIT_POLICY='PASSIVE',OMP_NUM_THREADS='1',OMP_THREAD_LIMIT='1',
             MKL_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',NUMEXPR_NUM_THREADS='1',PYTHONUNBUFFERED='1',
             PYTHONDONTWRITEBYTECODE='1',CELL_DEV_CACHE=str(common.STUDY/'unused-test-cache'))
    env.pop('CELLDEV_THREADS_FILE',None)
    result=subprocess.run([sys.executable,'-c',code,order,str(common.ROOT)],cwd=common.STUDY,env=env,
                          capture_output=True,text=True)
    assert result.returncode==0,result.stderr
    assert result.stdout.strip()=='checked'
    assert not (common.STUDY/'unused-test-cache').exists()


def test_prior_failed_cpu_is_retained_and_total_caps_reduce(value):
    prior=value['prior_attempt']
    budget=common.read(common.STUDY/prior['budget_path'])
    assert common.sha(common.STUDY/prior['budget_path'])==prior['budget_sha256']
    assert budget['status']=='incomplete' and budget['phase']=='validation'
    assert budget['cpu_seconds']==prior['cpu_seconds']==0.716548
    assert prior['simulation_calls']==prior['compiled_libraries']==0
    assert value['monitor_scope']['total_cpu_seconds']+prior['cpu_seconds']<3600
    assert value['monitor_scope']['validation_cpu_seconds']+prior['cpu_seconds']<180
    import monitor
    assert monitor.CAP==3599 and monitor.VALIDATION_CAP==179
    assert monitor.SCOPE==value['monitor_scope']
