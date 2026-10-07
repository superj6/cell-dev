import math

import pytest
import torch

from src import lattice
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


# sparse-fabric helpers for the one-life kernel
KINDS = ["hex", "square4", "square8"]


@pytest.mark.parametrize("kind", KINDS)
def test_offsets_match_dense_neighbour_table(kind):
    off = lattice.offsets(kind)
    lat = build_lattice(kind, 3)
    pos = lat.pos.double()
    for d, (da, db) in enumerate(off):
        x, y = lattice.to_xy(kind, da, db)
        j = int(lat.nbr[lat.center, d])
        assert torch.allclose(pos[j] - pos[lat.center], torch.tensor([x, y], dtype=torch.float64), atol=1e-6)


@pytest.mark.parametrize("kind", KINDS)
def test_back_slots_by_lookup(kind):
    off = lattice.offsets(kind)
    back = lattice.back_slots(kind)
    for d, (da, db) in enumerate(off):
        assert off[back[d]] == (-da, -db)
        assert back[back[d]] == d


def test_square8_back_is_not_half_turn_index():
    assert lattice.back_slots("square8") == [2, 3, 0, 1, 6, 7, 4, 5]
    assert lattice.back_slots("square8") != [(d + 4) % 8 for d in range(8)]
    assert lattice.back_slots("hex") == [3, 4, 5, 0, 1, 2]


@pytest.mark.parametrize("kind", KINDS)
def test_unit_vectors_and_cyclic_order(kind):
    units = lattice.unit_vectors(kind)
    for x, y in units:
        assert math.hypot(x, y) == pytest.approx(1.0, abs=1e-12)
    cyc = lattice.cyclic_order(kind)
    assert sorted(cyc) == list(range(len(units)))
    ang = [math.atan2(units[d][1], units[d][0]) % (2 * math.pi) for d in cyc]
    assert all(a < b for a, b in zip(ang, ang[1:]))
    step = 2 * math.pi / len(units)
    for d, (p, n) in enumerate(lattice.cyclic_neighbours(kind)):
        assert lattice.cyclic_neighbours(kind)[n][0] == d and lattice.cyclic_neighbours(kind)[p][1] == d
        for e in (p, n):  # cyclic neighbours are one angular step apart
            cos = units[d][0] * units[e][0] + units[d][1] * units[e][1]
            assert cos == pytest.approx(math.cos(step), abs=1e-12)


def test_cyclic_orders():
    assert lattice.cyclic_order("hex") == [0, 5, 4, 3, 2, 1]
    assert lattice.cyclic_order("square4") == [0, 1, 2, 3]
    assert lattice.cyclic_order("square8") == [0, 4, 1, 5, 2, 6, 3, 7]


@pytest.mark.parametrize("kind", KINDS)
def test_rotate_and_mirror(kind):
    k = lattice.rotation_steps(kind)
    units = lattice.unit_vectors(kind)
    rot = lattice.slot_map(kind, lambda a, b: lattice.rotate(kind, a, b))
    mir = lattice.slot_map(kind, lambda a, b: lattice.mirror(kind, a, b))
    assert sorted(rot) == list(range(len(units))) and sorted(mir) == list(range(len(units)))
    c, s = math.cos(2 * math.pi / k), math.sin(2 * math.pi / k)
    for d, (x, y) in enumerate(units):
        assert units[rot[d]] == pytest.approx((c * x - s * y, s * x + c * y), abs=1e-12)  # counter-clockwise
        assert units[mir[d]] == pytest.approx((x, -y), abs=1e-12)
    for a, b in [(2, -1), (0, 3), (-4, 1)]:
        assert lattice.rotate(kind, a, b, k) == (a, b)
        assert lattice.mirror(kind, *lattice.mirror(kind, a, b)) == (a, b)
        x0, y0 = lattice.to_xy(kind, a, b)
        x1, y1 = lattice.to_xy(kind, *lattice.rotate(kind, a, b))
        assert math.hypot(x1, y1) == pytest.approx(math.hypot(x0, y0), abs=1e-12)


@pytest.mark.parametrize("kind", KINDS)
@pytest.mark.parametrize("r", [1, 4])
def test_in_disk_matches_dense_fabric(kind, r):
    lat = build_lattice(kind, r)
    span = range(-r - 1, r + 2)
    inside = [(a, b) for a in span for b in span if lattice.in_disk(kind, a, b, r)]
    assert len(inside) == lat.n
    pos = sorted(tuple(round(v, 6) for v in lattice.to_xy(kind, a, b)) for a, b in inside)
    assert pos == sorted(tuple(round(float(v), 6) for v in p) for p in lat.pos.tolist())
