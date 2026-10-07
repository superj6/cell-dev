import math

import pytest
import torch

from src.lattice import build_lattice, hex_lattice


@pytest.mark.parametrize("r", [1, 2, 5])
def test_hex_site_count(r):
    assert hex_lattice(r).n == 3 * r * (r + 1) + 1


@pytest.mark.parametrize("kind", ["hex", "square4", "square8"])
def test_neighbours_symmetric_local_and_no_wraparound(kind):
    lat = build_lattice(kind, 4)
    for i in range(lat.n):
        for j in lat.nbr[i][lat.mask[i]].tolist():
            assert i in lat.nbr[j].tolist()
            dist = float((lat.pos[i] - lat.pos[j]).norm())
            assert dist == pytest.approx(1.0, abs=1e-5) or (kind == "square8" and dist == pytest.approx(math.sqrt(2), abs=1e-5))
    deg = lat.mask.sum(1)
    assert int(deg.max()) == lat.d and int(deg.min()) < lat.d  # edge sites have fewer neighbours
    assert float(lat.pos[lat.center].norm()) == pytest.approx(0.0)


def test_gather_reads_zero_in_empty_slots():
    lat = build_lattice("hex", 2)
    x = torch.arange(lat.n, dtype=torch.float32)[:, None] + 1
    g = lat.gather(x)[..., 0]
    assert torch.equal(g[lat.mask], (lat.nbr[lat.mask] + 1).float())
    assert (g[~lat.mask] == 0).all()
