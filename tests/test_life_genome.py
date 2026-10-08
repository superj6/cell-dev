"""The life genome layout (src/genome.py, kind life): agreement with the kernel's 793-slot table, crossover by whole
units with returned masks, the active-gene mask in mutation, exactly neutral duplication through the kernel,
deletion, neutral padding, save/load and decode ranges (docs/ONE_LIFE_DESIGN.md, Genome; LIFE_ABI.md 4.4)."""
import json

import numpy as np
import pytest
import torch

from src.genome import LIFE_DIMS_ABI3, Dims, Layout, LifeDims, LifeLayout, make_dims, make_layout
from src.life import build, spec
from src.life import handbuilt as hb
from tests.life_helpers import bits, same

LAY = LifeLayout(LifeDims())
G = spec.G_MAX
VIEW_COL = G + 5  # the W column fed by n_view / D (the last input: ABI 2 has no flank_best / 2)


def _gen(seed: int = 0) -> torch.Generator:
    return torch.Generator().manual_seed(seed)


def _unit_entries(lay: LifeLayout, u: int) -> torch.Tensor:
    return lay.unit_of == u


@pytest.fixture(scope="module")
def growers() -> torch.Tensor:
    """Random founders whose bodies grow and spike, with apoptosis switched on (p_die 2^-7 per tick), so lives
    exercise division, death, packets and messages."""
    x = LAY.random(256, _gen(1))
    res = build.run(spec.world(T=150.0, oracle_cap=30), [7] * 256, genomes=LAY.pack(x), genome_of=np.arange(256),
                    threads=4)
    pick = [i for i in range(256) if res["n_peak"][i] >= 10 and res["spikes"][i] > 50][:3]
    assert len(pick) == 3
    out = x[pick].clone()
    LAY.view(out, "a0")[:, spec.K["p_die"]] = 0.3  # rint(4 y) = 1: p_die = 2^-7
    return out


def _lives(params: torch.Tensor, seeds=(3, 4)) -> build.Lives:
    return build.run(spec.world(T=200.0, oracle_cap=40), list(seeds), genomes=LAY.pack(params.reshape(1, -1)),
                     threads=4, raster_cap=50_000, fate_cap=4096)


# ---------------------------------------------------------------------------------------------------- layout
def test_life_layout_is_the_kernel_table():
    assert LAY.size == spec.GENOME_SIZE == 793 and LAY.n_units == G + 1
    assert LAY.slices["W"][2] == (G, G + 6) and VIEW_COL == spec.NIN - 1
    assert {k: v[:2] for k, v in LAY.slices.items()} == spec.GENOME_SLICES
    assert [(f.name, tuple(f.shape), f.block, f.unit) for f in LAY.fields] == \
        [(f.name, tuple(f.shape), f.block, f.unit) for f in spec.GENOME_FIELDS]
    assert LifeDims().grn_inputs == spec.NIN and LifeDims().readout == spec.P
    x = LAY.random(3, _gen())
    for name in spec.GENOME_SLICES:  # the layout's named views are the spec's views of the same rows
        assert np.array_equal(LAY.view(x, name).numpy(), spec.genome_view(x.numpy(), name))
    with pytest.raises(ValueError):
        LifeLayout(LifeDims(genes_max=12))
    with pytest.raises(ValueError):
        LifeLayout(LifeDims(genes_init=17))


def test_kinds_dispatch_and_the_legacy_layout_is_untouched():
    assert isinstance(make_layout(make_dims({"kind": "life"})), LifeLayout)
    legacy = make_layout(make_dims({"genes": 8, "morph": 2, "types": 4, "channels": 2, "stim": 2}))
    assert type(legacy) is Layout and legacy.dims == Dims() and Dims().kind == "types"
    assert Dims().__dict__ == {"genes": 8, "morph": 2, "types": 4, "channels": 2, "stim": 2}  # saved payload unchanged
    assert make_dims({"kind": "types", "genes": 8}) == Dims()


def test_founders_start_homogeneous_with_eight_active_genes():
    x = LAY.random(64, _gen(2))
    act = LAY.active(x)
    assert act[:, :8].all() and not act[:, 8:].any()
    assert torch.equal(LAY.view(x, "act"), act.float())
    W, A = LAY.view(x, "W"), LAY.view(x, "A")
    assert (W[:, 8:, :] == 0).all() and (W[:, :, 8:G] == 0).all() and (A[:, :, 8:] == 0).all()
    for name in ("b", "lam", "s0", "Q"):
        assert (LAY.view(x, name)[:, 8:] == 0).all(), name
    assert (W[:, :, VIEW_COL] == 0).all()  # homogeneous founders
    # 14 inputs per active row (8 genes, 6 others): 337 mutable entries (345 in ABI 1, which had the flank input)
    assert (LAY.mutable(x).sum(1) == 8 * 14 + 4 * 8 + 21 * 8 + 21 + 4).all()
    assert W[:, :8, :8].abs().min() > 0 and W[:, :8, G:VIEW_COL].abs().min() > 0  # every other input weighs
    th = LAY.zygote_phenotype(x)
    for knob in ("p_die", "phi", "a0", "a1", "chi"):  # start exactly at their neutral value in every founder
        assert np.all(th[:, spec.K[knob]] == 0.0), knob
    assert 0.3 < np.mean(th[:, spec.K["b"]] > 1.0) < 0.7  # about half the zygotes are tonic


def test_decode_ranges():
    x = LAY.random(512, _gen(3), scale=1.5)
    th = LAY.zygote_phenotype(x)
    for knob, grid in spec.GRIDS.items():
        assert np.isin(th[:, spec.K[knob]], grid).all(), knob
    for knob, (lo, hi) in spec.RANGES.items():
        assert ((lo <= th[:, spec.K[knob]]) & (th[:, spec.K[knob]] <= hi)).all(), knob
    gt = LAY.pack(x)
    lam, g0 = spec.genome_view(gt, "lam"), spec.genome_view(gt, "s0")
    assert np.isin(lam[:, :8], [2.0 ** -k for k in range(1, 8)]).all() and (lam[:, 8:] == 0).all()
    assert ((g0[:, :8] > 0) & (g0[:, :8] < 1)).all() and (g0[:, 8:] == 0).all()
    Dm, km = spec.genome_view(gt, "Dm"), spec.genome_view(gt, "km")
    assert ((Dm > 0) & (6 * spec.P_MAX * Dm < spec.CHEM_SHIP_MAX)).all() and ((km > 0.005) & (km < 0.305)).all()
    for i in range(4):  # the kernel's readout and decode agree with the layout's zygote phenotype
        assert np.array_equal(build.decode(build.readout(gt[i], g0[i])), th[i])


# ------------------------------------------------------------------------------------------------- operators
def test_crossover_keeps_units_whole_and_returns_its_masks():
    g = _gen(4)
    a, b = LAY.random(32, g), LAY.random(32, g)
    child, masks = LAY.crossover(a, b, g, masks=True)
    assert masks.shape == (32, G + 1) and masks.dtype == torch.bool
    for u in range(LAY.n_units):
        sel = _unit_entries(LAY, u)
        from_a = (child[:, sel] == a[:, sel]).all(1)
        from_b = (child[:, sel] == b[:, sel]).all(1)
        assert (from_a | ~masks[:, u]).all() and (from_b | masks[:, u]).all()  # mask bit set = unit from a
    # a gene travels with its row, rate, maternal level, Q, act bit and readout column; a0, Dm and km are global
    unit = {f.name: f.unit for f in LAY.fields}
    assert unit == dict(W="row", b="elem", lam="elem", s0="elem", Q="elem", act="elem", A="col", a0="global",
                        Dm="global", km="global")
    assert torch.equal(LAY.crossover(a, a, _gen(5)), a)
    g1, g2 = _gen(6), _gen(6)
    assert torch.equal(LAY.crossover(a, b, g1), LAY.crossover(a, b, g2, masks=True)[0])  # same draws either way


def test_mutation_honours_the_active_mask_and_one_block():
    g = _gen(7)
    x = LAY.random(256, g)
    x[::2] = LAY.delete(x[0], 3).expand(128, -1)  # half the rows have gene 3 deleted
    ops = []
    m = LAY.mutate(x, g, n_mut=3, ops=ops)
    changed = m != x
    assert (changed.sum(1) <= 3).all() and (changed.sum(1) >= 1).all()
    assert all(LAY.block_of[row].unique().numel() == 1 for row in changed)
    assert not (changed & ~LAY.mutable(x)).any()
    assert not changed[:, LAY.is_act].any()
    W = LAY.view(changed, "W")
    assert not W[:, 8:, :].any() and not W[:, :, 8:G].any() and not LAY.view(changed, "A")[:, :, 8:].any()
    assert not W[::2, 3, :].any() and not W[::2, :, 3].any() and not LAY.view(changed, "A")[::2, :, 3].any()
    assert len(ops) == 256 and all(len(o["mut"]) == int(c.sum()) for o, c in zip(ops, changed))
    for o, row_x, row_m in zip(ops[:20], x[:20], m[:20]):  # the records name the entries and the steps
        for name, idx, delta in o["mut"]:
            step = float(LAY.view(row_m, name)[tuple(idx)] - LAY.view(row_x, name)[tuple(idx)])
            assert step == pytest.approx(delta, abs=1e-5)
    # n_mut scales with the active genes (2 at 8 active, 1 at 4)
    four = x[1:2].clone()
    for k in (4, 5, 6, 7):
        four = LAY.delete(four[0], k)[None]
    assert LAY.n_mut_of(x[1:2], 2).item() == 2 and LAY.n_mut_of(four, 2).item() == 1


def test_duplication_is_exactly_neutral_through_the_kernel(growers):
    for x in growers:
        base = _lives(x)
        assert base["n_peak"].max() >= 10 and base["deaths"].sum() > 0 and base["packets"].sum() > 0
        act = LAY.active(x).nonzero()[:, 0].tolist()
        for src, dst in ((act[0], 8), (act[5], 15), (act[7], 11)):
            d = LAY.duplicate(x, src, dst)
            assert LAY.active(d).sum() == 9 and float(LAY.view(d, "act")[dst]) == 1.0
            life = _lives(d)
            assert np.array_equal(bits(base.ledger), bits(life.ledger)) and np.array_equal(base.hashes, life.hashes)
            for i in range(2):
                assert np.array_equal(bits(base.spikes(i)[0]), bits(life.spikes(i)[0]))
                assert np.array_equal(base.fates(i)[0], life.fates(i)[0])
                fb, fd = base.fates(i)[1], life.fates(i)[1]
                keep = [c for c in range(fb.shape[1]) if c != 2 + dst]
                assert np.array_equal(bits(fb[:, keep]), bits(fd[:, keep]))
                assert np.array_equal(bits(fd[:, 2 + dst]), bits(fd[:, 2 + src]))  # the copy tracks the original
            split = _lives(LAY.duplicate(x, src, dst, split=True))  # the design's operator: neutral up to rounding
            assert np.array_equal(base.hashes[:, 1], split.hashes[:, 1])
            assert np.abs(split["F"] - base["F"]).max() < 1e-12


def test_duplicating_a_gene_of_the_r25_genome_leaves_its_life_unchanged():
    """R25-v1 written as a GRN genome (handbuilt.r25_genome, gate G9): copying its contact, juvenile or rate-gate gene
    into a spare slot changes no ledger column, hash, spike or fate record of its life."""
    x = torch.from_numpy(hb.r25_genome())
    base = _lives(x)
    assert base["n_end"].min() >= 30 and base["income"].min() > 0
    spare = (~LAY.active(x)).nonzero()[:, 0].tolist()
    for src, dst in ((hb.GENE_CONTACT, spare[0]), (hb.GENE_JUVENILE, spare[-1]), (hb.GENE_GATE, spare[3])):
        life = _lives(LAY.duplicate(x, src, dst))
        assert np.array_equal(bits(base.ledger), bits(life.ledger)) and np.array_equal(base.hashes, life.hashes)
        for i in range(2):
            assert np.array_equal(bits(base.spikes(i)[0]), bits(life.spikes(i)[0]))
            assert np.array_equal(base.fates(i)[0], life.fates(i)[0])


def test_duplicate_then_mutate_the_copy_diverges_only_through_the_copy():
    x = LAY.random(1, _gen(8))[0]
    d = LAY.duplicate(x, 2, 9)
    for name in ("b", "lam", "s0", "Q"):
        assert LAY.view(d, name)[9] == LAY.view(d, name)[2]
    W = LAY.view(d, "W")
    assert torch.equal(W[9, :9], LAY.view(x, "W")[2, :9]) and W[9, 9] == 0 and (W[:, 9] == 0).all()
    assert (LAY.view(d, "A")[:, 9] == 0).all()
    fed = (LAY.src_of < 0) | LAY.active(d)[LAY.src_of.clamp(min=0)]
    assert LAY.mutable(d[None])[0][(LAY.gene_of == 9) & ~LAY.is_act & fed].all()  # the copy is open to mutation
    assert LAY.mutable(d[None])[0][LAY.src_of == 9].sum() == 9  # and other active genes may now read it
    s = LAY.duplicate(x, 2, 9, split=True)
    assert torch.equal(LAY.view(s, "A")[:, 2], LAY.view(x, "A")[:, 2] * 0.5)
    assert torch.equal(LAY.view(s, "W")[:, 9], LAY.view(s, "W")[:, 2])
    with pytest.raises(ValueError):
        LAY.duplicate(x, 9, 10)  # the source must be active
    with pytest.raises(ValueError):
        LAY.duplicate(x, 2, 3)  # the destination must be spare


def test_deletion_masks_the_gene_and_undoes_a_duplication(growers):
    x = growers[0]
    k = 4
    deleted = LAY.delete(x, k)
    assert not LAY.active(deleted)[k] and LAY.active(deleted).sum() == 7
    zeroed = x.clone()  # the same genome with gene k's unit cleared by hand
    zeroed[(LAY.unit_of == k)] = 0.0
    W = LAY.view(zeroed, "W")
    W[:, k] = 0.0
    assert np.array_equal(bits(LAY.pack(deleted[None])), bits(LAY.pack(zeroed[None])))
    assert same(_lives(deleted), _lives(zeroed))
    assert not (LAY.mutable(deleted[None])[0] & ((LAY.gene_of == k) | (LAY.src_of == k))).any()
    back = LAY.delete(LAY.duplicate(x, 1, 12), 12)
    assert np.array_equal(bits(LAY.pack(back[None])), bits(LAY.pack(x[None])))
    with pytest.raises(ValueError):
        LAY.delete(x, 12)


def test_structural_mutation_rates_and_records():
    g = _gen(9)
    x = LAY.random(400, g)
    ops = []
    use = torch.zeros(G, dtype=torch.long)
    use[8:12] = 5  # slots 12-15 are least used in the population: duplicates go there
    m = LAY.mutate(x, g, dup_rate=0.25, del_rate=0.1, slot_use=use, ops=ops)
    dups = [o["dup"] for o in ops if "dup" in o]
    dels = [o["del"] for o in ops if "del" in o]
    assert 60 < len(dups) < 140 and 15 < len(dels) < 70
    assert all(src < 8 <= dst for src, dst in dups)
    # the registry is counted up after each duplication: the first 20 fill slots 12-15 up to slots 8-11's 5 carriers,
    # then the duplications spread evenly over all eight spare slots
    assert sorted(dst for _, dst in dups[:20]) == [d for d in range(12, 16) for _ in range(5)]
    final = use.clone()
    for _, dst in dups:
        final[dst] += 1
    assert int(final[8:].max() - final[8:].min()) <= 1
    assert use[8:12].tolist() == [5] * 4 and not use[12:].any()  # the caller's registry is not modified
    n_act = LAY.active(m).sum(1)
    expect = 8 + torch.tensor([("dup" in o) - ("del" in o) for o in ops])
    assert torch.equal(n_act, expect)
    assert torch.equal(LAY.active(LAY.mutate(x, _gen(10))), LAY.active(x))  # no structural ops at rate 0


def test_one_batch_of_duplications_spreads_over_distinct_slots():
    # review fix: the slot registry was read once per batch, so every duplicate of a generation went to one slot
    x = LAY.random(1, _gen(12)).expand(8, -1).clone()
    for k in range(1, 9):
        ops = []
        LAY.mutate(x[:k], _gen(k), dup_rate=1.0, slot_use=torch.zeros(G, dtype=torch.long), ops=ops)
        dst = [o["dup"][1] for o in ops]
        assert len(dst) == k and len(set(dst)) == k  # k <= 8 free slots: k distinct slots


def test_deleted_genes_leave_no_weights_for_a_later_gene_in_their_slot():
    # review fix: delete() kept the weights other genes read from the deleted gene (W[:, k]); crossing with a lineage
    # that holds a silent duplicate in slot k then attached those stale weights to it
    base, k = LAY.random(1, _gen(2))[0], 9
    a = LAY.duplicate(base, 2, k)
    LAY.view(a, "W")[0, k] = 3.0  # lineage A: gene 0 learns to read the copy, then the copy is lost
    a = LAY.delete(a, k)
    W = LAY.view(a, "W")
    assert not W[torch.arange(G) != k, k].any() and W[0, 1] == LAY.view(base, "W")[0, 1]
    b = LAY.duplicate(base, 5, k)  # lineage B: a silent copy of gene 5 in the same slot
    bits_ = torch.ones(1, LAY.n_units, dtype=torch.bool)
    bits_[0, k] = False  # every unit from A but unit k from B
    child = torch.where(bits_[:, LAY.unit_of], a[None], b[None])[0]
    assert LAY.active(child)[k]
    hybrid, ref = _lives(child), _lives(base)  # the copy is still silent: the hybrid lives exactly as the base
    assert np.array_equal(bits(hybrid.ledger), bits(ref.ledger)) and np.array_equal(hybrid.hashes, ref.hashes)
    for i in range(2):
        assert np.array_equal(bits(hybrid.spikes(i)[0]), bits(ref.spikes(i)[0]))
        assert np.array_equal(hybrid.fates(i)[0], ref.fates(i)[0])
        keep = [c for c in range(ref.fates(i)[1].shape[1]) if c != 2 + k]  # the log records the copy's own g too
        assert np.array_equal(bits(hybrid.fates(i)[1][:, keep]), bits(ref.fates(i)[1][:, keep]))
    # the same through crossover: a regulator row from a parent that carries gene k drops its weight from k when the
    # child does not inherit gene k
    c = LAY.duplicate(base, 3, k)
    LAY.view(c, "W")[0, k] = 3.0
    picks = torch.zeros(1, LAY.n_units, dtype=torch.bool)
    picks[0, 0] = True  # unit 0 (gene 0's row, reading k) from c, everything else (gene k off) from base
    kid = LAY.silence(torch.where(picks[:, LAY.unit_of], c[None], base[None]))[0]
    assert not LAY.active(kid)[k] and LAY.view(kid, "W")[0, k] == 0 and LAY.view(kid, "W")[0, 1] == LAY.view(c, "W")[0, 1]
    pa, pb = LAY.random(64, _gen(3)), LAY.random(64, _gen(4))
    pa = torch.stack([LAY.duplicate(x, 0, 8) for x in pa])
    LAY.view(pa, "W")[:, :, 8] = 1.0  # every gene of pa reads its gene 8; pb has no gene 8
    kids, masks = LAY.crossover(pa, pb, _gen(5), masks=True)
    off = ~LAY.active(kids)[:, 8]
    assert off.any() and not LAY.view(kids, "W")[off][:, :, 8].any()  # children without gene 8 keep no weight from it
    assert np.array_equal(bits(LAY.pack(kids)), bits(LAY.pack(torch.where(masks[:, LAY.unit_of], pa, pb))))


def test_pad_is_neutral():
    x = LAY.random(4, _gen(11))
    assert torch.equal(LAY.pad(x, LAY), x)
    v5 = LifeLayout(LifeDims(stim=1))
    assert not v5.runnable and v5.dims.grn_inputs == spec.NIN + 1 and v5.dims.readout == spec.P + 1
    p = LAY.pad(x, v5)
    assert p.shape == (4, v5.size) and v5.size == spec.GENOME_SIZE + G + G + 1
    for f in LAY.fields:  # every v1 entry keeps its (row, column) place; every new entry is 0
        new = v5.view(p, f.name)
        old = LAY.view(x, f.name)
        keep = (..., *[slice(0, n) for n in f.shape])
        assert torch.equal(new[keep], old), f.name
        rest = torch.ones_like(new, dtype=torch.bool)
        rest[keep] = False
        assert not new[rest].any(), f.name
    assert torch.equal(v5.active(p), LAY.active(x))
    assert torch.equal(v5.view(p, "W")[:, :, spec.NIN], torch.zeros(4, G))  # the receptor input has no weight
    assert torch.equal(v5.view(p, "a0")[:, spec.P], torch.zeros(4))  # its gain row decodes to 0
    assert (v5.view(v5.random(8, _gen(12)), "W")[:, :, spec.NIN] == 0).all()
    with pytest.raises(ValueError):
        v5.pad(p, LAY)  # padding never drops fields
    with pytest.raises(ValueError):
        v5.pack(p)  # the kernel cannot run receptor genomes yet


def test_the_abi3_layout_is_spec_v3_and_pads_neutrally():
    """LIFE_DIMS_ABI3 is BODY-1's 875-slot table (LIFE_ABI.md 4.4): fields, shapes, blocks, units and offsets equal
    spec.V3's, padding an ABI-2 genome equals spec.V3.pad_genomes, and it packs into spec.V3's kernel table (the
    kernel runs ABI 2 and ABI 3 tables; other padded layouts are not runnable)."""
    lay3 = LifeLayout(LIFE_DIMS_ABI3)
    assert lay3.abi is spec.V3 and LAY.abi is spec.V2 and LAY.runnable and lay3.runnable
    assert lay3.size == spec.V3.GENOME_SIZE == 875 and lay3.dims.grn_inputs == spec.V3.NIN
    assert lay3.knob_names == spec.V3.KNOBS
    x = LAY.mutate(LAY.random(6, _gen(21)), _gen(22), dup_rate=0.5)
    p = LAY.pad(x, lay3)
    assert np.array_equal(p.numpy(), spec.V3.pad_genomes(x.numpy(), spec.V2))
    assert torch.equal(lay3.active(p), LAY.active(x)) and torch.equal(lay3.pad(p, lay3), p)
    with pytest.raises(ValueError):
        lay3.pad(p, LAY)
    gt = lay3.pack(p, "hexprism")
    assert gt.shape == (6, 875) and np.array_equal(bits(gt), bits(spec.V3.pack_genomes(p.numpy(), "hexprism")))
    assert np.array_equal(bits(lay3.pack(p)), bits(spec.V3.pad_genomes(LAY.pack(x), spec.V2)))  # 2D: pad o pack
    assert lay3.zygote_phenotype(p).shape == (6, spec.V3.P)
    f = lay3.random(64, _gen(23))
    W = lay3.view(f, "W")
    assert (W[:, :, G + 5:G + 7] == 0).all()  # n_view and the receptor trace start silent
    assert (W[:, :8, G + 7:G + 9] != 0).any(dim=(1, 2)).all()  # plane cues start random (plane-specific founders)
    a0 = lay3.view(f, "a0")
    assert a0[:, spec.V3.K["g_r"]].std() > 0.5 and a0[:, spec.V3.K["zeta"]].std() > 0.5
    v5 = LifeLayout(LifeDims(stim=1))  # a receptor row without zeta cannot grow into ABI 3 in place
    with pytest.raises(ValueError):
        v5.pad(LAY.pad(x, v5), lay3)


LAY3 = LifeLayout(LIFE_DIMS_ABI3)
CATCH = spec.world("catch_v1_l4", T=300.0)


def _catch_lives(params: torch.Tensor, seeds=(3, 4)) -> build.Lives:
    return build.run(CATCH, list(seeds), genomes=LAY3.pack(params.reshape(1, -1), "hexprism"), threads=4,
                     raster_cap=50_000, fate_cap=4096, abi=spec.V3)


@pytest.fixture(scope="module")
def catch_growers() -> torch.Tensor:
    """ABI-3 founders whose CATCH bodies grow into the act plane, spike and receive receptor events."""
    x = LAY3.random(256, _gen(31))
    res = build.run(CATCH, [7] * 256, genomes=LAY3.pack(x, "hexprism"), genome_of=np.arange(256), threads=4,
                    abi=spec.V3)
    pick = [i for i in range(256) if 4 <= res["n_end"][i] <= 200 and res["n_M_end"][i] > 0 and res["spikes"][i] > 50
            and res["rec_events"][i] > 0][:3]
    assert len(pick) == 3
    return x[pick].clone()


def _same_but_the_copy(base: build.Lives, life: build.Lives, src: int, dst: int) -> bool:
    """``same`` except the copy's own gene in the fate log, which tracks the original's (silent duplicate)."""
    if not (np.array_equal(bits(base.ledger), bits(life.ledger)) and np.array_equal(base.hashes, life.hashes)):
        return False
    for i in range(len(base.ledger)):
        fb, fd = base.fates(i)[1], life.fates(i)[1]
        keep = [c for c in range(fb.shape[1]) if c != 2 + dst]
        if not (np.array_equal(bits(base.spikes(i)[0]), bits(life.spikes(i)[0]))
                and np.array_equal(base.fates(i)[0], life.fates(i)[0]) and np.array_equal(bits(fb[:, keep]),
                                                                                          bits(fd[:, keep]))
                and np.array_equal(bits(fd[:, 2 + dst]), bits(fd[:, 2 + src]))):
            return False
    return True


def test_abi3_operators_stay_exact_through_the_kernel_in_catch(catch_growers, tmp_path):
    """BODY-1 genomes keep the operators' guarantees in CATCH lives (3D bodies, receptors, the dot): a silent
    duplicate lives the same life (its own gene tracks the original's), deleting it again, crossing a genome with
    itself and a save/load round trip give bitwise the same life, and a deletion is the same life as zeroing the gene's
    outgoing weights."""
    for x in catch_growers:
        base = _catch_lives(x)
        act = LAY3.active(x)
        src, dst = int(act.nonzero()[0, 0]), int((~act).nonzero()[0, 0])
        dup = LAY3.duplicate(x, src, dst)
        assert _same_but_the_copy(base, _catch_lives(dup), src, dst)
        assert same(base, _catch_lives(LAY3.delete(dup, dst)))
        child = LAY3.crossover(x[None], x[None], _gen(5))[0]
        assert same(base, _catch_lives(child))
        k = int(act.nonzero()[1, 0])
        zeroed = x.clone()
        LAY3.view(zeroed, "W")[:, k] = 0.0
        LAY3.view(zeroed, "A")[:, k] = 0.0
        LAY3.view(zeroed, "act")[k] = 0.0
        assert same(_catch_lives(LAY3.delete(x, k)), _catch_lives(zeroed))
    LAY3.save(catch_growers[0], tmp_path / "g.json")
    lay, y = Layout.load(tmp_path / "g.json")
    assert lay.dims == LIFE_DIMS_ABI3 and lay.abi is spec.V3 and torch.equal(y, catch_growers[0])
    assert same(_catch_lives(catch_growers[0]), _catch_lives(y))


def test_input_init_sets_founder_weight_spreads_by_input_name():
    """genome.input_init: the founder std of every weight from a named non-gene input. The defaults are unchanged
    (n_view and the receptor trace silent, plane cues at the W std), so BELL and CATCH founders draw the same
    genomes as before; an override changes that column only, from the same random stream."""
    assert LAY3.input_names == spec.V3.INPUTS[G:] and LAY.input_names == spec.V2.INPUTS[G:]
    plain = LifeLayout(LIFE_DIMS_ABI3, input_init={})
    assert torch.equal(plain.random(8, _gen(41)), LAY3.random(8, _gen(41)))
    lay = LifeLayout(LIFE_DIMS_ABI3, input_init={"n_view": 1.0, "is_S": 2.0})
    a, b = LAY3.random(16, _gen(42)), lay.random(16, _gen(42))
    Wa, Wb = LAY3.view(a, "W"), lay.view(b, "W")
    col = {name: G + i for i, name in enumerate(LAY3.input_names)}
    other = [c for c in range(spec.V3.NIN) if c not in (col["n_view"], col["is_S"])]
    assert torch.equal(Wa[:, :, other], Wb[:, :, other])  # every other weight is the same draw
    assert (Wa[:, :8, col["n_view"]] == 0).all() and (Wb[:, :8, col["n_view"]] != 0).all()
    assert torch.allclose(Wb[:, :8, col["is_S"]], 2.0 * Wa[:, :8, col["is_S"]])
    assert (Wb[:, 8:, :] == 0).all()  # spare gene slots stay empty
    with pytest.raises(KeyError):
        LifeLayout(LIFE_DIMS_ABI3, input_init={"flank_best": 1.0})


def test_readout_std_sets_every_free_knob_spread_and_knob_init_still_wins():
    lay = LifeLayout(LIFE_DIMS_ABI3, readout_std=(0.5, 0.25), knob_init={"g_r": (0.5, 0.75, 1.0)})
    K = spec.V3.K
    a0, A = slice(*lay.slices["a0"][:2]), lay.slices["A"]
    std_a0 = lay.init_std[a0]
    std_A = lay.init_std[A[0]:A[1]].reshape(spec.V3.P, G)
    fixed = [K[k] for k in ("p_die", "phi", "a0", "a1", "chi")]  # LIFE_KNOB_INIT's fixed knobs stay fixed
    for k in range(spec.V3.P):
        want = (0.0, 0.0) if k in fixed else (0.75, 1.0) if k == K["g_r"] else (0.5, 0.25)
        assert (float(std_a0[k]), float(std_A[k, 0])) == want, spec.V3.KNOBS[k]
    assert lay.init_mean[a0][K["g_r"]] == 0.5 and lay.init_mean[a0][K["b"]] == 1.0  # means are knob_init's
    assert torch.equal(LifeLayout(LIFE_DIMS_ABI3, readout_std=None).init_std, LAY3.init_std)


def test_save_and_load_round_trip(tmp_path):
    g = _gen(13)
    x = LAY.mutate(LAY.random(1, g), g, dup_rate=1.0)[0]
    LAY.save(x, tmp_path / "g.json")
    payload = json.loads((tmp_path / "g.json").read_text())
    assert payload["dims"] == {**LifeDims().__dict__} and payload["dims"]["kind"] == "life"
    lay, y = Layout.load(tmp_path / "g.json")
    assert isinstance(lay, LifeLayout) and lay.dims == LifeDims()
    assert np.array_equal(bits(x.numpy().astype(np.float64)), bits(y.numpy().astype(np.float64)))
    assert np.array_equal(bits(LAY.pack(x[None])), bits(lay.pack(y[None])))


def test_an_abi1_genome_is_refused_on_load(tmp_path):
    """ABI 1 saved the same dims with a 23-column W (its last column read flank_best, removed in ABI 2): loading it
    must fail loudly, not shift every later field by 16 entries."""
    x = LAY.random(1, _gen(14))[0]
    LAY.save(x, tmp_path / "g.json")
    payload = json.loads((tmp_path / "g.json").read_text())
    payload["params"]["W"] = [row + [0.0] for row in payload["params"]["W"]]
    (tmp_path / "old.json").write_text(json.dumps(payload))
    with pytest.raises(ValueError, match="ABI 1"):
        Layout.load(tmp_path / "old.json")
    payload["params"]["A"] = payload["params"]["A"][:-1]  # any other misshapen field is refused too
    payload["params"]["W"] = [row[:-1] for row in payload["params"]["W"]]
    (tmp_path / "bad.json").write_text(json.dumps(payload))
    with pytest.raises(ValueError, match="saved field A"):
        Layout.load(tmp_path / "bad.json")
