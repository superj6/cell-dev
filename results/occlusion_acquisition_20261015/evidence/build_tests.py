from pathlib import Path
import ast
old=Path('outputs/audit_capture_value_selection_20261015/test_confirmation_reader.py').read_text()
nodes={n.name:n for n in ast.parse(old).body if isinstance(n,ast.FunctionDef)}
def body(name):
 n=nodes[name];return '\n'.join(old.splitlines()[n.lineno-1:n.end_lineno])
text='''"""AN focused changes only: checkpoint prefixes, 8+4+4 calls and fixed 3×5 matrix."""
import ast
import copy
import hashlib
import importlib.util
import json
import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = next(p for p in Path(__file__).resolve().parents if (p / 'src/life/spec.py').is_file())
STUDY = ROOT / 'outputs/autonomous_occlusion_acquisition_20261015'
AM = ROOT / 'outputs/autonomous_capture_value_selection_20261015'
'''
text+='\n\n'+body('load')+'\n\nM = load("an_reader", STUDY / "analyze.py")\n\n'+body('functions')+'\n\n'+body('rows')+'\n\n'+body('flat_captures')+'\n\n'
text+='''def test_physics_truth_genetic_core_unchanged():
    for filename, names in (
            ('analyze.py', ('identical', 'stats', 'prices', 'physical_costs', 'validate_row', 'reconstruct', 'json_genome')),
            ('measure.py', ('parent_check', 'check_visibility_truth')),
            ('native_replay.py', ('sha', 'raw_sha', 'definitions', 'initial_population', 'replay_first'))):
        old, new = functions(AM / filename), functions(STUDY / filename)
        assert all(ast.dump(old[name]) == ast.dump(new[name]) for name in names)
    assert (AM / 'replay_ops.py').read_bytes() == (STUDY / 'replay_ops.py').read_bytes()
    old = functions(ROOT / 'outputs/audit_capture_value_selection_20261015/terminal_review/accuracy_supplement.py')
    assert ast.dump(old['describe_counts']) == ast.dump(functions(STUDY / 'analyze.py')['describe_counts'])


def test_39_groups_8_retention_vectors_covariance_duplicates():
    data = rows()
    noise = np.arange(512, dtype=float)
    data['persistent'][M.ROLES[2]]['captures'] += noise
    data['turn100_blink80_20'][M.ROLES[2]]['captures'] += noise + 2
    reports, arrays = M.contrasts(data)
    retention, extra = M.retention_diagnostics(data)
    assert (len(reports), len(arrays), len(retention), len(extra)) == (39, 2925, 4, 8)
    assert len(set(arrays) | set(extra)) == 2933
    key = 'interaction__turn100_blink80_20_minus_persistent__generation8_minus_AM_current_start'
    np.testing.assert_array_equal(arrays[key+'__captures'], np.full(512, 2.))
    assert reports[key]['captures']['se'] == 0
    np.testing.assert_array_equal(arrays['within__pool__generation4_minus_AM_current_start__captures'], np.zeros(512))


def test_fixed_final_primary_is_not_best_midpoint_and_strict_3se():
    data = rows(); flat_captures(data)
    data['blink80_20'][M.ROLES[1]]['captures'][:] = 100
    assert not M.verdicts(data)['primary_capture_gain_above_3se']
    values = np.tile([-1., 1.], 256)
    boundary = 3 * M.stats(values)['se']
    data['blink80_20'][M.ROLES[2]]['captures'] = 10 + values + boundary + 1e-10
    assert M.verdicts(data)['primary_capture_gain_above_3se']
    data['blink80_20'][M.ROLES[2]]['captures'] -= 2e-10
    assert not M.verdicts(data)['primary_capture_gain_above_3se']


def test_four_retention_pairs_strict_margin():
    assert M.RETENTION == ((1,0,'pool'), (1,0,'persistent'), (2,0,'pool'), (2,0,'persistent'))
    data=rows(); flat_captures(data, 100.)
    for world in ('pool','persistent'):
        for role in M.ROLES[1:]: data[world][role]['captures'][:] = 90
    report, arrays=M.retention_diagnostics(data)
    assert all(not value['passes_conventional_10_percent_diagnostic'] for value in report.values())
    assert all(np.all(value == 0) for key,value in arrays.items() if key.endswith('ninety_percent_reference'))


def test_aggregate_accuracy_zero_and_weighting():
    assert M.describe_counts(np.zeros(2), np.zeros(2), np.zeros(2))['aggregate_capture_fraction'] is None
    result=M.describe_counts(np.array([1.,1.]), np.array([0.,8.]), np.array([1.,9.]))
    assert result['aggregate_capture_fraction'] == .2
    with pytest.raises(ValueError): M.describe_counts(np.array([1.]), np.array([1.]), np.array([1.]))


def test_fixed_checkpoint_scope_and_one_confirmation_identity(monkeypatch):
    monkeypatch.syspath_prepend(str(STUDY))
    worker=load('an_measure', STUDY/'measure.py')
    assert worker.ROLES==M.ROLES and worker.ARMS==M.ARMS
    for generation in (4,8):
        state={'generation':generation, 'curves':[{'gen':g,'pop_invalid':0,'pop_mismatch':0,'recheck_invalid':0} for g in range(generation)]}
        assert worker.validate_search_state(state,generation)==dict(pop_invalid=0.,pop_mismatch=0.,recheck_invalid=0.)
        with pytest.raises(ValueError): worker.validate_search_state(state,6)
    tree=ast.parse((STUDY/'measure.py').read_text())
    assert sum(isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute) and n.func.attr=='numerical_identity' for n in ast.walk(tree))==1
    fn=functions(STUDY/'measure.py')['measure']
    freeze=next(n.lineno for n in ast.walk(fn) if isinstance(n,ast.Call) and isinstance(n.func,ast.Name) and n.func.id=='freeze_endpoints')
    assert freeze < min(n.lineno for n in ast.walk(fn) if isinstance(n,ast.For))
    assert not any(n.startswith(('src.life.build','src.run','src.evolve')) for n in sys.modules)
'''
terminal=body('terminal_fixture').replace('/synthetic_AM','/synthetic_AN').replace('7200 if i < 2 else 3810','7200 if i == 0 else 3710').replace('310.', '210.').replace('300.', '200.').replace('"search_cpu_seconds": 210.', '"search_cpu_seconds": 110.').replace('28748','28214').replace('28756','28222')
text+='\n\n'+terminal+'''\n\ndef test_two_phase_cumulative_cpu():
    with pytest.MonkeyPatch.context() as mp:
        base, protocol, docs, digest=terminal_fixture(mp)
        assert M.verify_terminal(base,protocol)['cpu_seconds']==210
        docs[str(base/'budget.json')]['confirmation_cpu_seconds']=3600
        with pytest.raises(ValueError): M.verify_terminal(base,protocol)
'''
raw=body('test_actual_four_role_raw_coverage_in_memory').replace('test_actual_four_role_raw_coverage_in_memory','test_five_world_three_role_coverage').replace('missing_fourth_role','missing_final').replace('range(4)','range(3)').replace('8192','7680').replace('16','15').replace('row_03','row_02').replace('four','three')
text+='\n\n@pytest.mark.parametrize("missing_final", [False,True])\n'+raw+'\n'
Path('outputs/audit_occlusion_acquisition_20261015/test_confirmation_reader.py').write_text(text)
