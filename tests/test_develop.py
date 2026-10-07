import torch

from src.develop import D_SAFETY, develop, diffuse
from src.genome import Dims, Layout
from src.lattice import build_lattice


def _setup(kind="hex", n=16, seed=0):
    lat = build_lattice(kind, 5)
    lay = Layout(Dims())
    return lat, lay, lay.random(n, torch.Generator().manual_seed(seed))


def test_seed_stays_single_when_division_is_off():
    lat, lay, P = _setup()
    lay.view(P, "E")[:, 0] = 0.0  # divide logit = e0[0] only
    lay.view(P, "e0")[:, 0] = -5.0
    t = develop(lat, lay, P, steps=10)
    assert (t.n_cells == 1).all() and (t.divisions == 0).all()


def test_divisions_never_overwrite_cells():
    for kind in ("hex", "square4", "square8"):
        lat, lay, P = _setup(kind, n=64)
        t = develop(lat, lay, P, steps=12)
        assert torch.equal(t.n_cells, 1 + t.divisions)
        assert (t.types[~t.alive] == 0).all()


def test_development_is_deterministic_and_batch_invariant():
    lat, lay, P = _setup(n=32)
    full = develop(lat, lay, P, steps=12)
    again = develop(lat, lay, P, steps=12)
    alone = develop(lat, lay, P[7:8], steps=12)
    assert torch.equal(full.alive, again.alive) and torch.equal(full.types, again.types)
    assert torch.equal(full.alive[7:8], alone.alive) and torch.equal(full.types[7:8], alone.types)
    assert torch.allclose(full.g[7:8], alone.g, atol=1e-6)


def test_diffusion_is_stable_and_decays_at_max_rate():
    lat = build_lattice("hex", 5)
    morph = torch.zeros(1, lat.n, 1)
    morph[0, lat.center] = 10.0
    D = torch.full((1, 1), D_SAFETY / lat.full_contact)
    out = diffuse(lat, morph, D, torch.full((1, 1), 0.01), substeps=200)
    assert torch.isfinite(out).all() and (out >= 0).all()
    assert float(out.sum()) < 10.0 and float(out.max()) < 10.0
