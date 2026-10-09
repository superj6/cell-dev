"""scripts/catch_pilot_analysis.py: the knockout surgery decodes to the neutral knob in every gene state and touches
nothing else, and the footprint laws reproduce finding 2's slit numbers (RESULTS.md, Pre-pilot part 6)."""
import numpy as np
import pytest

from scripts import catch_pilot_analysis as pa
from src.genome import LIFE_DIMS_ABI3, LifeLayout
from src.life import handbuilt as hb
from src.life import spec

V3 = spec.V3
NEUTRAL = dict(chi=0.0, tau_tr=8.0, delta=0.0, phi=0.0, zeta=0.0, asym=0.0, a0=0.0, a1=0.0, pol0=0.0, pol1=0.0,
               sec0=0.0, sec1=0.0, p_die=0.0, emit1=0.0)


def _genome(seed: int = 0) -> np.ndarray:
    import torch
    lay = LifeLayout(LIFE_DIMS_ABI3)
    g = lay.random(1, torch.Generator().manual_seed(seed))
    return np.asarray(g, dtype=np.float32).reshape(-1)


@pytest.mark.parametrize("family", sorted(pa.KNOB_KO))
def test_knob_knockouts_decode_to_the_neutral_value_in_every_gene_state(family):
    g = _genome()
    ko = pa.knock(g, knobs=pa.KNOB_KO[family])
    row = V3.pack_genomes(ko[None], "hexprism")[0]
    rng = np.random.default_rng(1)
    for _ in range(50):
        theta = dict(zip(V3.KNOBS, V3.phenotype(row, rng.random(16))))
        for knob in pa.KNOB_KO[family]:
            assert theta[knob] == NEUTRAL[knob]
    changed = np.flatnonzero(ko != g)
    sl = V3.GENOME_SLICES
    rows = {V3.K[k] for k in pa.KNOB_KO[family]}
    for i in changed:  # only the knocked rows of A and a0 differ
        if sl["A"][0] <= i < sl["A"][1]:
            assert (i - sl["A"][0]) // 16 in rows
        else:
            assert sl["a0"][0] <= i < sl["a0"][1] and i - sl["a0"][0] in rows


def test_input_knockouts_zero_exactly_their_columns():
    g = _genome(2)
    for name, cols in pa.INPUT_KO.items():
        ko = pa.knock(g, inputs=cols)
        sl = V3.GENOME_SLICES
        W0, W1 = (x[sl["W"][0]:sl["W"][1]].reshape(16, V3.NIN) for x in (g, ko))
        idx = [V3.INPUTS.index(c) for c in cols]
        assert (W1[:, idx] == 0).all(), name
        keep = [j for j in range(V3.NIN) if j not in idx]
        assert np.array_equal(W1[:, keep], W0[:, keep]) and np.array_equal(ko[sl["W"][1]:], g[sl["W"][1]:])


def test_footprints_reproduce_finding_2():
    ring = [s for s in hb.disk(3) if hb.hex_ring(*s) == 3]
    thick = [(0, 0)] + [s for s in hb.disk(3) if hb.hex_ring(*s) >= 2]
    slit = [s for s in thick if s not in ((2, 0), (3, 0))]
    assert pa.footprints(thick)[:3] == (len(thick), 37, 37)
    cols, fill, close, hull = pa.footprints(slit)
    assert (cols, fill, close, hull) == (29, 29, 36, 36)
    assert pa.footprints(hb.disk(3)) == (37, 37, 37, 37)
    assert pa.footprints([(0, 0)] + ring)[1] == 37  # the closed 1-wide hollow ring fills to the disk
