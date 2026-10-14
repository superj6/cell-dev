"""Pure fixtures for tie-aware selection diagnostics; no engine imports or lives."""
import copy
import importlib.util
import json
from pathlib import Path

import numpy as np
import pytest

SPEC = importlib.util.spec_from_file_location('selection_diagnostic', Path(__file__).with_name('analyze.py'))
m = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(m)


def fixture(base=None, repeat=None, forced_order=None):
    a = np.arange(64., 0., -1) if base is None else np.asarray(base, dtype=float)
    b = a.copy() if repeat is None else np.asarray(repeat, dtype=float)
    pooled = (3 * a + 4 * b) / 7
    order = np.argsort(-pooled, kind='stable')[:32] if forced_order is None else np.array(forced_order)
    ids = list(range(64))
    survivors = order.tolist()
    changed = 32 - len(set(ids[:32]) & set(survivors))
    row = dict(gen=0, T=1024, seeds=[1, 2, 3], survivors=survivors, fitness=pooled[order].tolist(),
               recheck=dict(ids=ids, F_base=a.tolist(), F_recheck=b.tolist(), key='all',
                            seeds=[4, 5, 6, 7], changed=changed))
    curve = dict(gen=0, T=1024, recheck_changed=changed, best_id=survivors[0], fitness=pooled[order][0],
                 recheck_F_base=a[order].mean(), recheck_F=b[order].mean(), mean_fitness=pooled[order].mean(),
                 recheck_k=64, t_eval=3., t_recheck=1., pop_guard=0., pop_invalid=0., recheck_invalid=0.)
    return row, curve


def test_strict_reversal_uses_recorded_survivors():
    b = np.arange(64., 0., -1)
    b[40] = 150
    row, curve = fixture(repeat=b)
    result, candidates = m.generation('X', 1, row, curve)
    assert result['changed_parents'] == 1
    assert result['top_relation'] == 'strict_displacement'
    assert result['final_first_base_rank_min'] == result['final_first_base_rank_max'] == 41
    assert candidates[40]['selected_rank'] == 1
    assert len(candidates) == 64


def test_exact_base_and_pooled_tie_changes_identity_without_strict_reversal():
    a = np.arange(64., 0., -1)
    a[1] = a[0]
    row, curve = fixture(base=a, forced_order=[1, 0] + list(range(2, 32)))
    result, _ = m.generation('X', 1, row, curve)
    assert result['leader_identity_changed']
    assert result['base_top_ids'] == [0, 1]
    assert result['top_sets_overlap_ids'] == [0, 1]
    assert result['top_relation'] == 'overlap_with_exact_recorded_top_set'
    assert (result['final_first_base_rank_min'], result['final_first_base_rank_max']) == (1, 2)


def test_pooled_tie_alone_is_not_strict_displacement():
    a = np.arange(64., 0., -1)
    b = a.copy()
    b[1] = 64.75
    row, curve = fixture(base=a, repeat=b, forced_order=[1, 0] + list(range(2, 32)))
    result, _ = m.generation('X', 1, row, curve)
    assert result['leader_identity_changed'] and result['base_top_ids'] == [0]
    assert result['recorded_pooled_top_ids'] == [1, 0]
    assert result['top_relation'] == 'overlap_with_exact_recorded_top_set'


def test_full_tied_plateau_retains_actual_parent_changes_and_cutoff_ambiguity():
    row, curve = fixture(base=np.ones(64), forced_order=list(range(32, 64)))
    result, _ = m.generation('X', 1, row, curve)
    assert result['changed_parents'] == 32
    assert result['base_parent_cutoff_tied']
    assert result['pooled_parent_cutoff_ambiguous']
    assert not result['pooled_top_set_complete']
    assert result['base_top_set_may_extend_past_shortlist']
    assert result['rank']['spearman_average_ties'] is None
    assert result['top_relation'] != 'strict_displacement'


def test_near_recorded_scores_use_actual_order_not_reconstructed_ties():
    a = np.arange(64., 0., -1)
    b = a.copy()
    b[1] = 64.75 + 1e-13
    row, curve = fixture(base=a, repeat=b)
    result, _ = m.generation('X', 1, row, curve)
    assert result['leader_identity_changed']
    assert result['top_relation'] == 'strict_displacement'
    assert result['strict_displacement_recorded_margin_lower_bound'] > 0


@pytest.mark.parametrize('kind', ['changed', 'seeds', 'curve', 'pooled', 'ordering'])
def test_corruption_fails_closed(kind):
    row, curve = fixture()
    if kind == 'changed':
        row['recheck']['changed'] = 1
    elif kind == 'seeds':
        row['recheck']['seeds'][0] = 1
    elif kind == 'curve':
        curve['best_id'] = 1
    elif kind == 'pooled':
        row['fitness'][0] += .01
    else:
        row['recheck']['F_base'][1] = 100
    with pytest.raises(ValueError):
        m.generation('X', 1, row, curve)


def test_rank_pair_ties_are_excluded_and_average_ranks_used():
    result = m.rank_diagnostics([1, 1, 3], [3, 3, 1])
    assert result['spearman_average_ties'] == pytest.approx(-1)
    assert result['strict_comparable_pairs'] == result['strict_reversed_pairs'] == 2
    assert result['tied_base_pairs'] == result['tied_recheck_pairs'] == 1


def test_signed_disagreement_preserved_in_aggregate():
    first, second = fixture(repeat=np.arange(64., 0., -1) - 2)
    third, fourth = fixture(repeat=np.arange(64., 0., -1) + 3)
    r1, c1 = m.generation('X', 1, first, second)
    r2, c2 = m.generation('X', 1, third, fourth)
    stats = m.aggregate([r1, r2], c1 + c2)
    assert stats['recheck_minus_base']['mean'] == .5
    assert stats['recheck_minus_base']['minimum'] == -2
    assert stats['recheck_minus_base']['maximum'] == 3
    assert stats['recheck_elapsed_fraction'] == .25
    assert stats['parent_slots'] == 64


def test_archive_gate_precedes_outcome_or_manifest_reads(tmp_path):
    (tmp_path / 'operations').mkdir()
    (tmp_path / 'operations/budget.json').write_text(json.dumps(dict(status='running')))
    with pytest.raises(ValueError, match='completed empty-budget'):
        m.verify_archive(tmp_path)


def test_archive_corruption_rejected(tmp_path):
    (tmp_path / 'operations').mkdir()
    budget = tmp_path / 'operations/budget.json'
    budget.write_text(json.dumps(dict(status='complete', running={}, queued=[])))
    (tmp_path / 'data').write_text('original')
    manifest = dict(artifacts={'data': dict(sha256=m.sha(tmp_path / 'data'), bytes=8)})
    (tmp_path / 'provenance.json').write_text(json.dumps(manifest))
    (tmp_path / 'data').write_text('corrupt!')
    with pytest.raises(ValueError, match='artifact changed'):
        m.verify_archive(tmp_path)


def test_logged_identity_count_separate_from_top_set_overlap():
    a = np.arange(64., 0., -1)
    a[1] = a[0]
    row, curve = fixture(base=a, forced_order=[1, 0] + list(range(2, 32)))
    r, c = m.generation('X', 1, row, curve)
    stats = m.aggregate([r], c)
    assert stats['leader_identity_changes'] == stats['identity_changes_with_top_set_overlap'] == 1
    assert stats['strict_top_displacements'] == 0
    copied = copy.deepcopy(r)
    assert copied == r


def test_incomplete_pooled_top_set_without_overlap_remains_ambiguous():
    a = np.arange(64., 0., -1)
    b = (7 * 80 - 3 * a) / 4
    b[0] -= 7 / 4
    row, curve = fixture(base=a, repeat=b)
    result, _ = m.generation('X', 1, row, curve)
    assert not result['pooled_top_set_complete']
    assert result['top_sets_overlap_ids'] == []
    assert result['top_relation'] == 'cutoff_incomplete_top_set'
    assert result['strict_displacement_recorded_margin_lower_bound'] is None
