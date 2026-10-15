"""Create focused source-only AO tests from compact retained fixture definitions."""
import ast
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
AN=ROOT/'outputs/audit_occlusion_acquisition_20261015/test_confirmation_reader.py'
AM=ROOT/'outputs/audit_capture_value_selection_20261015/test_confirmation_reader.py'
def function(path,name):
 s=path.read_text();n=next(n for n in ast.parse(s).body if isinstance(n,ast.FunctionDef) and n.name==name)
 return '\n'.join(s.splitlines()[n.lineno-1:n.end_lineno])
s='''"""AO changed coverage/decision rules; no inputs, draws, engines or file fixture tree."""
import ast
import copy
import hashlib
import importlib.util
import json
import sys
from pathlib import Path
import numpy as np
import pytest
ROOT=next(p for p in Path(__file__).resolve().parents if (p/'src/life/spec.py').is_file())
STUDY=ROOT/'outputs/autonomous_retained_depth_20261015'
AN=ROOT/'outputs/autonomous_occlusion_acquisition_20261015'
'''
s+='\n\n'+function(AN,'load')+'\n\nM=load("ao_reader",STUDY/"analyze.py")\n\n'+function(AN,'functions')+'\n\n'+function(AN,'rows')+'\n\n'+function(AN,'flat_captures')+'\n\n'
s+='''def test_unchanged_physics_and_truth():
    for filename,names in [('analyze.py',('identical','stats','prices','physical_costs','validate_row','reconstruct','json_genome','describe_counts','contrasts','retention_diagnostics')),
                          ('measure.py',('parent_check','check_visibility_truth'))]:
        old,new=functions(AN/filename),functions(STUDY/filename)
        assert all(ast.dump(old[k])==ast.dump(new[k]) for k in names)


def test_all11967_vectors_covariance_and_duplicates():
    data=rows()
    assert len(M.PAIRS)==15 and len(set(M.PAIRS))==15
    noise=np.arange(512,dtype=np.float64)
    data['persistent']['balanced24']['captures']+=noise
    data['turn100_blink80_20']['balanced24']['captures']+=noise+2
    report,arrays=M.contrasts(data)
    margins,retention=M.retention_diagnostics(data)
    assert (len(report),len(arrays),len(margins),len(retention))==(159,11925,21,42)
    assert len(set(arrays)|set(retention))==11967
    key='interaction__turn100_blink80_20_minus_persistent__balanced24_minus_AN_start'
    np.testing.assert_array_equal(arrays[key+'__captures'],np.full(512,2.))
    assert report[key]['captures']['se']==0
    np.testing.assert_array_equal(arrays['within__pool__unchanged8_minus_AM_reference__captures'],np.zeros(512))
    expected={(i,1,w) for i in range(2,6) for w in ('pool','persistent','blink80_20')}
    expected|={(i,0,w) for i in range(2,6) for w in ('pool','persistent')}
    expected.add((5,3,'blink80_20'))
    assert set(M.RETENTION)==expected


def test_joint_claim_requires_both_and_discloses_actual_blink_loss():
    data=rows()
    flat_captures(data,10.)
    data['pool']['balanced24']['captures'][:]=11
    data['blink80_20']['balanced24']['captures'][:]=9.5
    result=M.verdicts(data)
    assert result['joint_primary_passes']
    assert result['primary_blink80_20_actual_capture_difference']['mean']==-.5
    assert result['primary_blink80_20_ninety_percent_noninferiority']['mean']==.5
    data['blink80_20']['balanced24']['captures'][:]=9
    assert not M.verdicts(data)['joint_primary_passes']
    data['blink80_20']['balanced24']['captures'][:]=10
    data['pool']['balanced24']['captures'][:]=10
    assert not M.verdicts(data)['joint_primary_passes']


def test_unrounded_three_se_blink_margin():
    data=rows()
    flat_captures(data,10.)
    data['pool']['balanced24']['captures'][:]=11
    noise=np.tile([-1.,1.],256)
    boundary=3*M.stats(noise)['se']
    data['blink80_20']['balanced24']['captures']=9+noise+boundary+1e-10
    assert M.verdicts(data)['joint_primary_passes']
    data['blink80_20']['balanced24']['captures']-=2e-10
    assert not M.verdicts(data)['joint_primary_passes']


def test_fixed_reference_checkpoint_order_and_single_confirmation_identity(monkeypatch):
    monkeypatch.syspath_prepend(str(STUDY))
    worker=load('ao_measure',STUDY/'measure.py')
    assert worker.ROLES==M.ROLES and worker.ARMS==M.ARMS
    for generation in (8,24):
        state={'generation':generation,'curves':[dict(gen=g,pop_invalid=0,pop_mismatch=0,recheck_invalid=0) for g in range(generation)]}
        worker.validate_search_state(state,generation)
        with pytest.raises(ValueError): worker.validate_search_state(state,4)
    f=functions(STUDY/'measure.py')['freeze_endpoints']
    refs=next(n.value for n in f.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='references' for t in n.targets))
    assert [x.slice.value for x in refs.elts]==['ancestral_reference','reference']
    t=ast.parse((STUDY/'measure.py').read_text())
    assert sum(isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute) and n.func.attr=='numerical_identity' for n in ast.walk(t))==1
    assert not any(n.startswith(('src.life.build','src.run','src.evolve')) for n in sys.modules)
'''
f=function(AM,'terminal_fixture').replace('/synthetic_AM','/synthetic_AO').replace('10800','28800').replace('5400','14400').replace('7200','24000').replace('3600','4800').replace('3810','5010').replace('28748','138476').replace('28756','138488').replace('"startup_lives": 8','"startup_lives": 12')
s+='\n\n'+f+'''\n\ndef test_three_phase_inclusive_caps(monkeypatch):
    base,protocol,docs,digest=terminal_fixture(monkeypatch)
    assert M.verify_terminal(base,protocol)['cpu_seconds']==310
    docs[str(base/'budget.json')]['confirmation_cpu_seconds']=4800
    with pytest.raises(ValueError): M.verify_terminal(base,protocol)
'''
f=function(AM,'test_actual_four_role_raw_coverage_in_memory').replace('test_actual_four_role_raw_coverage_in_memory','test_exact_thirty_rows').replace('missing_fourth_role','missing_last_role').replace('range(4)','range(6)').replace('8192','15360').replace('"rows": 16','"rows": 30').replace("'rows': 16","'rows': 30").replace('row_03','row_05').replace('16-row','30-row').replace('cpu == 16','cpu == 30')
s+='\n\n@pytest.mark.parametrize("missing_last_role",[False,True])\n'+f+'\n'
# A directly adapted pure startup fixture now checks three four-life receipts.
f=function(AN,'test_two_startup_pairs_and_two_visibility_pairs').replace('test_two_startup_pairs_and_two_visibility_pairs','test_three_startup_receipts')
f=f.replace('"runs/acquisition/search_startup.json": copy.deepcopy(expected),','"runs/unchanged/search_startup.json": copy.deepcopy(expected),\n        "runs/balanced/search_startup.json": copy.deepcopy(expected),')
f=f.replace('runs/acquisition/search_startup.json','runs/balanced/search_startup.json').replace('== 8','== 12')
s+='\n\n@pytest.mark.parametrize("corruption",[None,"missing_search_truth","extra_search_calls"])\n'+f+'\n'
Path(__file__).with_name('test_confirmation_reader.py').write_text(s)
