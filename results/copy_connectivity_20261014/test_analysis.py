"""Graph semantics for copied-gene coefficient paths, without lives or engine imports."""
import importlib.util
from pathlib import Path

import numpy as np
import pytest

SPEC = importlib.util.spec_from_file_location('copy_connectivity_analysis', Path(__file__).with_name('analyze.py'))
ANALYSIS = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(ANALYSIS)


def graph():
    active = np.ones(16, dtype=bool)
    return active, np.zeros((16, 16)), np.zeros((23, 16))


def test_incoming_edge_does_not_give_source_an_outgoing_path():
    active, w, a = graph()
    w[9, 0], a[3, 0] = 1, 1
    assert not ANALYSIS.connectivity(active, w, a, 9)['has_readout_path']


def test_signed_direct_readout_is_retained():
    active, w, a = graph()
    a[6, 9] = -.25
    result = ANALYSIS.connectivity(active, w, a, 9)
    assert result['has_readout_path'] and result['direct_readout_rows'] == [6]


def test_multihop_route_and_cycle_terminate():
    active, w, a = graph()
    w[10, 9], w[11, 10], w[9, 11], a[22, 11] = 1, -2, 3, .5
    result = ANALYSIS.connectivity(active, w, a, 9)
    assert result['direct_readout_rows'] == []
    assert result['other_gene_targets'] == [10]
    assert result['reachable_active_genes'] == [9, 10, 11]
    assert result['reachable_readout_rows'] == [22]


def test_inactive_intermediary_cannot_relay():
    active, w, a = graph()
    w[10, 9], w[11, 10], a[2, 11] = 1, 1, 1
    active[10] = False
    assert not ANALYSIS.connectivity(active, w, a, 9)['has_readout_path']


def test_private_loop_without_readout_stays_disconnected():
    active, w, a = graph()
    w[9, 9] = 4
    result = ANALYSIS.connectivity(active, w, a, 9)
    assert result['reachable_active_genes'] == [9]
    assert result['other_gene_targets'] == [] and not result['has_readout_path']


def test_exact_zero_only_no_arbitrary_small_weight_threshold():
    active, w, a = graph()
    a[1, 9] = np.nextafter(np.float32(0), np.float32(1))
    assert ANALYSIS.connectivity(active, w, a, 9)['has_readout_path']
    a[1, 9] = -0.0
    assert not ANALYSIS.connectivity(active, w, a, 9)['has_readout_path']


def test_inactive_copy_rejected():
    active, w, a = graph()
    active[9] = False
    with pytest.raises(ValueError, match='must be active'):
        ANALYSIS.connectivity(active, w, a, 9)
