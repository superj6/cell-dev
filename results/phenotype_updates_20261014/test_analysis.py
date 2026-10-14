"""Synthetic transition-chain, cohort, age and reversibility checks; no simulation."""
import importlib.util
from copy import deepcopy
from pathlib import Path

import numpy as np
import pytest

path = Path(__file__).with_name('analyze.py')
spec = importlib.util.spec_from_file_location('phenotype_changes_audit', path)
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


def fixture():
    names = ['w0', 'emit0', 'asym']
    arrays = {'cells__cid': np.arange(4), 'cells__t_birth': np.array([0., 790., 810., 0.]),
              'cells__t_death': np.array([np.inf, 900., np.inf, 800.]),
              'knobs_birth__w0': np.zeros(4), 'knobs_birth__emit0': np.ones(4),
              'knobs_end__w0': np.array([0., .125, .5, 0.]), 'knobs_end__emit0': np.array([0., 1., 1., 1.]),
              'pheno_changes__t': np.array([800., 805., 806., 820., 830., 900.]),
              'pheno_changes__cid': np.array([0, 0, 0, 2, 0, 1]),
              'pheno_changes__knob': np.array(['w0', 'w0', 'w0', 'w0', 'emit0', 'w0']),
              'pheno_changes__old': np.array([0., .125, .25, 0., 1., 0.]),
              'pheno_changes__new': np.array([.125, .25, 0., .5, 0., .125])}
    return arrays, {'tables': {'knobs_birth': names}}


def test_alive_cohort_births_deaths_and_boundary():
    a, metadata = fixture()
    r = m.analyze_arrays(a, metadata)
    assert r['alive_at800_cells'] == 2 and r['later_born_cells'] == 1 and r['cohort_died_after800'] == 1
    assert r['gridded_events'] == 4 and r['gridded_changed_cells'] == 2
    assert r['emission_switches'] == 1 and r['emission_switched_fraction'] == .5
    assert r['per_knob']['w0']['later_born_events'] == 1
    assert r['per_knob']['w0']['events'] == 3
    assert r['age_bins'][0]['cells'] == 1 and r['age_bins'][2]['cells'] == 1
    assert r['time_bins'][0]['gridded_events'] == 4 and r['time_bins'][-1]['gridded_events'] == 0
    assert 'asym' not in r['per_knob']


def test_reversible_changes_remain_counted_when_endpoint_matches():
    a, metadata = fixture()
    a['pheno_changes__new'][2] = .125
    a['knobs_end__w0'][0] = .125
    r = m.analyze_arrays(a, metadata)
    assert r['per_knob']['w0']['changed_cells'] == 2
    assert r['per_knob']['w0']['terminal_differs_cells'] == 1


@pytest.mark.parametrize('field,index,value', [('pheno_changes__old', 1, 0.),
                                               ('pheno_changes__cid', 0, 99),
                                               ('pheno_changes__t', 3, 799.),
                                               ('pheno_changes__t', 5, 999.),
                                               ('knobs_end__w0', 0, .75)])
def test_corruption_is_rejected(field, index, value):
    a, metadata = fixture()
    a = deepcopy(a)
    a[field][index] = value
    with pytest.raises(ValueError):
        m.analyze_arrays(a, metadata)


def test_empty_cohort_has_no_invented_zero_fraction():
    a, metadata = fixture()
    a['cells__t_death'][:] = 700
    a['cells__t_birth'][:] = 0
    for key in ('t', 'cid', 'knob', 'old', 'new'):
        a['pheno_changes__' + key] = a['pheno_changes__' + key][:0]
    a['knobs_end__w0'][:] = 0
    a['knobs_end__emit0'][:] = 1
    r = m.analyze_arrays(a, metadata)
    assert r['alive_at800_cells'] == 0 and r['neural_changed_fraction'] is None


def test_exact_fixed_label_seed_set():
    m.validate_pairs([{'label': label, 'seed': seed} for label in m.LABELS for seed in m.SEEDS])


@pytest.mark.parametrize('bad', ['duplicate', 'seed'])
def test_wrong_fixed_label_seed_set_rejected(bad):
    rows = [{'label': label, 'seed': seed} for label in m.LABELS for seed in m.SEEDS]
    rows[0] = dict(rows[1]) if bad == 'duplicate' else {'label': m.LABELS[0], 'seed': 999}
    with pytest.raises(ValueError, match='label/seed'):
        m.validate_pairs(rows)
