"""ABI 3 (BODY-1 v1) in src/life/spec.py: layout, padding, 3D lattices and site keys, CATCH worlds, ledger pricing and
the CATCH world's closed forms (docs/LIFE_ABI.md, sections 3, 4, 7.10, 9.7 and 14)."""
import math
import struct

import numpy as np
import pytest

from src import lattice
from src.life import spec

V2, V3 = spec.V2, spec.V3
Y14 = [0.3, -2.7, 1.0, 0.5, -0.26, 0.0, 1e-9, 0.3, 0.75, 0.13, 0.0, -2.0, 1.1, 0.0, -1.0, 0.5, -9.0, 0.0, 2.2,
       -0.0624, 0.0625]


def bits(x) -> np.ndarray:
    return np.asarray(x, dtype=np.float64).view(np.uint64)


def fbits(x: float) -> int:
    return struct.unpack("<Q", struct.pack("<d", x))[0]


def _raw2(rng, n=6):
    g = rng.normal(0, 1.5, (n, V2.GENOME_SIZE)).astype(np.float32)
    a, b = V2.GENOME_SLICES["act"]
    g[:, a:b] = (rng.random((n, 16)) < 0.6).astype(np.float32)
    return g


# ------------------------------------------------------------------------------------------------------- layout
def test_abi3_sizes_and_layout():
    assert spec.CURRENT is V2 and spec.ABI_VERSION == 2  # the kernel still implements ABI 2
    assert V3.SIZES == dict(abi=3, genome=875, program=129, world=66, ledger=57, hashes=5, knobs=23, max_init=1024,
                            fate_i=7, fate_f=18)
    assert (V3.NIN, V3.P, V3.S) == (25, 23, 1) and V3.KNOBS[21:] == ("zeta", "g_r")
    assert V3.INPUTS[22:] == ("rho", "is_S", "is_M") and len(V3.INPUTS) == V3.NIN
    assert V3.GENOME_SLICES == dict(W=(0, 400), b=(400, 416), lam=(416, 432), s0=(432, 448), Q=(448, 464),
                                    act=(464, 480), A=(480, 848), a0=(848, 871), Dm=(871, 873), km=(873, 875))
    assert V3.PROGRAM_SCALAR["juv_ticks"] == 115 and V3.PROGRAM_SIZE == 5 * 23 + 14
    assert V3.HASHES == ("all", "spikes", "fate", "chem", "world") and V3.FATE_I[-1] == "z"


def test_abi3_extends_every_abi2_table_in_place():
    for name in ("KNOBS", "INPUTS", "WORLD_KEYS", "LEDGER", "HASHES", "FATE_I"):
        old, new = getattr(V2, name), getattr(V3, name)
        assert new[:len(old)] == old, name
    for name in ("K", "WORLD_INDEX", "L", "FLAGS", "STREAMS", "LATTICE_CODES", "PROGRAM_ROW"):
        old, new = getattr(V2, name), getattr(V3, name)
        assert {k: new[k] for k in old} == old, name
    meta = [[(f.name, f.block, f.unit) for f in abi.GENOME_FIELDS] for abi in (V2, V3)]
    assert meta[0] == meta[1]
    for f2, f3 in zip(V2.GENOME_FIELDS, V3.GENOME_FIELDS):
        assert all(a <= b for a, b in zip(f2.shape, f3.shape)) and len(f2.shape) == len(f3.shape)
    assert V3.GRIDS["zeta"] == V3.GRIDS["g_r"] == spec.Q8_GRID and "zeta" not in V2.GRIDS


def test_decode_v3_keeps_rows_0_to_20_bitwise():
    assert V3.decode_knobs(Y14 + [0.3, -0.7])[21:] == [0.25, -0.75]  # LIFE_ABI.md 14
    rng = np.random.default_rng(0)
    for y in rng.normal(0, 3, (400, 23)):
        a, b = V2.decode_knobs(y[:21]), V3.decode_knobs(y)
        assert [fbits(x) for x in a] == [fbits(x) for x in b[:21]]
        assert b[21] == spec.q8(y[21]) and b[22] == spec.q8(y[22]) and b[21] in spec.Q8_GRID and b[22] in spec.Q8_GRID
    th = V3.theta(b=1.2, zeta=1.0, g_r=-0.5)
    assert th.shape == (23,) and th[V3.K["zeta"]] == 1.0 and th[V3.K["g_r"]] == -0.5
    assert np.array_equal(bits(V3.theta(b=1.2)[:21]), bits(V2.theta(b=1.2)))
    with pytest.raises(KeyError):
        V2.theta(zeta=1.0)


def test_pad_genomes_is_neutral_and_commutes_with_packing():
    rng = np.random.default_rng(1)
    raw = _raw2(rng)
    pad = V3.pad_genomes(raw, V2)
    assert pad.shape == (6, 875) and pad.dtype == np.float32
    for f2 in V2.GENOME_FIELDS:
        new, old = V3.genome_view(pad, f2.name), V2.genome_view(raw, f2.name)
        keep = (..., *[slice(0, n) for n in f2.shape])
        assert np.array_equal(new[keep], old), f2.name
        rest = np.ones(new.shape, dtype=bool)
        rest[keep] = False
        assert not new[rest].any(), f2.name
    for kind in ("hex", "square4", "square8"):  # BELL's lattices: packing a padded genome = padding the packed one
        assert np.array_equal(bits(V3.pack_genomes(pad, kind)), bits(V3.pad_genomes(V2.pack_genomes(raw, kind), V2)))
    gt2, gt3 = V2.pack_genomes(raw), V3.pack_genomes(pad)
    for r in range(6):
        g = rng.random(16)
        y2, y3 = V2.readout(gt2[r], g), V3.readout(gt3[r], g)
        assert [fbits(x) for x in y3] == [fbits(x) for x in y2] + [fbits(0.0)] * 2
        th = V3.phenotype(gt3[r], g)
        assert th[V3.K["zeta"]] == 0.0 and th[V3.K["g_r"]] == 0.0
    with pytest.raises(ValueError):
        V3.pad_genomes(raw[:, :-1], V2)
    with pytest.raises(ValueError):
        V2.pad_genomes(pad, V3)
    assert V3.pack_genomes(pad, "hexprism").shape == (6, 875)


def test_dm_decode_uses_the_prism_degree():
    raw = np.zeros((1, 875), dtype=np.float32)
    assert V3.genome_view(V3.pack_genomes(raw, "hexprism"), "Dm")[0].tolist() == [0.01875, 0.01875]
    assert V3.genome_view(V3.pack_genomes(raw, "hex"), "Dm")[0].tolist() == [0.025, 0.025]
    assert V3.lattice_degree("hexprism") == 8 and V3.lattice_degree("square8prism") == 10
    with pytest.raises(ValueError):
        V2.lattice_degree("hexprism")


def test_pad_program_and_v3_programs():
    contact = dict(b=1.125, tau_m=1, t_ref=2.5, w0=-1, emit0=1, delta=2, kappa=1, p_div=0.5, phi=2)
    alone = dict(b=1.875, tau_m=8, t_ref=2, kappa=1)
    p2 = V2.pack_program(V2.theta(**contact), alone=V2.theta(**alone), juv_ticks=10, flank_gate=2, p_div_lo=1 / 16)
    p3 = V3.pack_program(V3.theta(**contact), alone=V3.theta(**alone), juv_ticks=10, flank_gate=2, p_div_lo=1 / 16)
    assert p3.shape == (129,) and np.array_equal(bits(V3.pad_program(p2, V2)), bits(p3))
    with pytest.raises(ValueError):
        V3.pack_program(V2.theta(**contact))  # a 21-knob row is not an ABI-3 row
    clicker = V3.pack_program(V3.theta(g_r=0.55, emit0=1), rim=V3.theta(w0=1, kappa=1, t_ref=4))
    assert clicker[V3.K["g_r"]] == 0.55  # program rows keep off-grid values (LIFE_ABI.md 4.5)


def test_pack_init_v3():
    body, n = V3.pack_init([(0, 0), (0, 0, 1), (1, -1, 3)], rows=[2, 1, -1])
    assert n == 3 and body.shape == (1024, 4) and body.dtype == np.int32
    assert body[:3].tolist() == [[0, 0, 0, 2], [0, 0, 1, 1], [1, -1, 3, -1]] and not body[3:].any()
    big, n = V3.pack_init([(a, b, z) for a in range(16) for b in range(16) for z in range(4)])
    assert n == 1024
    for bad in ([(0, 0, 0), (0, 0)], [(2 ** 22 + 1, 0)], [(0, -2 ** 22 - 1, 0)], [(0, 0, 8)], [(0, 0, -1)],
                [(0, 0, 0, 0)], [(0,)]):
        with pytest.raises(ValueError):
            V3.pack_init(bad)
    with pytest.raises(ValueError):
        V3.pack_init([(a, 0) for a in range(1025)])
    with pytest.raises(ValueError):
        V2.pack_init([(0, 0, 1)])  # ABI 2 has no heights
    assert V3.pack_init([(2 ** 22, -2 ** 22)])[1] == 1


# ------------------------------------------------------------------------------------------------------ lattices
@pytest.mark.parametrize("kind", list(spec.LATTICE_CODES_V3))
def test_v3_lattice_tables(kind):
    lat, unit = V3.lattice_tables(kind)
    D = len(lattice.offsets3(kind))
    assert lat.dtype == np.int32 and lat.shape == (2 + 7 * D,) and lat[0] == V3.LATTICE_CODES[kind] and lat[1] == D
    oa, ob, oz, back, prev, nxt, rot = (lat[2 + i * D: 2 + (i + 1) * D] for i in range(7))
    for d in range(D):
        assert (oa[back[d]], ob[back[d]], oz[back[d]]) == (-oa[d], -ob[d], -oz[d])
        if oz[d] == 0:
            assert nxt[prev[d]] == d and prev[nxt[d]] == d and oz[prev[d]] == 0 and oz[nxt[d]] == 0
        else:
            assert prev[d] == nxt[d] == d and rot[d] == d and unit[d].tolist() == [0.0, 0.0, float(oz[d])]
    assert sorted(rot.tolist()) == list(range(D))
    assert unit.shape == (D, 3) and unit.dtype == np.float64 and unit.flags.c_contiguous
    if kind in V2.LATTICE_CODES:  # a 2D kind: every ABI-2 entry, bitwise, plus off_z = 0 and unit z = 0
        lat2, unit2 = V2.lattice_tables(kind)
        assert lat2[:2 + 2 * D].tolist() == lat[:2 + 2 * D].tolist() and not oz.any()
        assert lat2[2 + 2 * D:].tolist() == lat[2 + 3 * D:].tolist()
        assert np.array_equal(bits(unit2), bits(np.ascontiguousarray(unit[:, :2]))) and not unit[:, 2].any()


def test_hexprism_table_values():
    lat, unit = V3.lattice_tables("hexprism")
    D = 8
    assert lat[0] == 3 and lat[2 + 3 * D: 2 + 4 * D].tolist() == [3, 4, 5, 0, 1, 2, 7, 6]
    assert lat[2 + 2 * D: 2 + 3 * D].tolist() == [0] * 6 + [1, -1]
    with pytest.raises(ValueError):
        V2.lattice_tables("hexprism")


def test_sitekey_3d():
    rng = np.random.default_rng(2)
    for a, b in rng.integers(-2 ** 31, 2 ** 31, (200, 2)).tolist():
        assert spec.sitekey(a, b, 0) == spec.sitekey(a, b)
    assert spec.sitekey(-1, 2, 1) == 0xFEFFFFFF00000002 and spec.sitekey(3, -4, 3) == 0x03000003FFFFFFFC
    assert spec.sitekey(0, 0, 1) == 1 << 56
    sites = [(a, b, z) for a in (-2 ** 23, -5, -1, 0, 1, 7, 2 ** 23 - 1) for b in (-2 ** 31, -3, 0, 3, 2 ** 31 - 1)
             for z in range(8)]
    keys = [spec.sitekey(*s) for s in sites]
    assert len(set(keys)) == len(sites)
    for (a, b, z), k in zip(sites, keys):  # the XOR is reversible while |a| < 2^24
        z_dec = ((k >> 56) & 0xF) ^ (0xF if k >> 63 else 0)
        assert z_dec == z and k ^ (z_dec << 56) == spec.sitekey(a, b)


# -------------------------------------------------------------------------------------------------------- worlds
def test_catch_presets_match_the_proposal():
    for name, L_max in (("catch_v1", 4), ("catch_v1_l4", 4), ("catch_v1_l2", 2)):
        w = spec.world(name)
        assert (w.world_kind, w.lattice, w.L_max, w.T, w.lives) == (1, "hexprism", L_max, 1024.0, 3)
        assert (w.sigma, w.v_t, w.tau_turn, w.rho_c, w.R_cap, w.R_min, w.R_max, w.t_resp, w.c_miss) == \
            (1.5, 0.1, 20.0, 1.0, 100.0, 2.0, 6.0, 50.0, 2.0)  # BODY_DESIGN_PROPOSAL.md 3.1; c_miss 2 (15.60)
        assert (w.lam_s, w.lam_bg, w.g_n, w.drag_exp, w.th_click, w.th_rel, w.tau_z, w.c_rec) == \
            (2.0, 0.05, 1.0, 0.5, 0.6, 0.25, 2.5, 0.001)  # 2.2-2.4
        assert (w.c_live, w.c_spike, w.c_tw, w.c_msg, w.c_div, w.c_sec) == tuple(spec.COSTS.values())
        assert w.b2_amp == 0.0 and spec.lambda_max(w) == 2.05
        v = V3.pack_world(w)
        assert v.shape == (66,) and v[V3.WORLD_INDEX["world_kind"]] == 1 and v[V3.WORLD_INDEX["L_max"]] == L_max
        with pytest.raises(NotImplementedError):
            V2.pack_world(w)


def test_bell_worlds_pack_under_v3_with_the_abi2_vector_as_prefix():
    for name in ("bell_v1", "bell_v1_5"):
        w = spec.world(name)
        v2, v3 = V2.pack_world(w), V3.pack_world(w)
        assert np.array_equal(bits(v3[:41]), bits(v2)) and v3[41:44].tolist() == [0.0, 1.0, 0.0]
    for name in ("bell_v2", "bell_v3"):
        with pytest.raises(NotImplementedError):
            V3.pack_world(spec.world(name))
    with pytest.raises(NotImplementedError):
        V2.pack_world(spec.world(L_max=2))
    with pytest.raises(NotImplementedError):
        V2.pack_world(spec.world(lattice="hexprism"))
    assert V3.pack_world(spec.world(lattice="hexprism", L_max=3)).shape == (66,)  # BELL in 3D is allowed in ABI 3


@pytest.mark.parametrize("bad", [
    dict(world_kind=2), dict(world_kind=0.5), dict(L_max=0), dict(L_max=9), dict(L_max=2.5), dict(stuck_z=4),
    dict(stuck_z=-1), dict(sigma=0.0), dict(b2_sigma=-1.0), dict(sigma=2.0 ** 21), dict(lam_s=-1.0),
    dict(lam_bg=-0.1), dict(b2_amp=-0.5), dict(lam_s=1024.0), dict(g_n=-1.0), dict(g_n=2048.0), dict(v_t=-0.1),
    dict(drag_exp=-0.1), dict(drag_exp=2.5), dict(th_click=0.2), dict(th_rel=-0.1), dict(th_click=1.5),
    dict(rho_c=-1.0), dict(R_min=7.0), dict(R_max=2.0 ** 21), dict(tau_turn=-1.0), dict(t_resp=-1.0),
    dict(t_resp=1e-20), dict(tau_turn=2.0 ** -11), dict(t_resp=1e-5),
    dict(R_cap=-1.0), dict(c_miss=-1.0), dict(c_rec=-0.1), dict(b2_p=1.5), dict(b2_mode=2), dict(lattice="triprism"),
    dict(sigma=float("nan")), dict(b2_value=float("inf")),
], ids=str)
def test_invalid_abi3_worlds_are_rejected(bad):
    with pytest.raises(ValueError):
        V3.pack_world(spec.world("catch_v1", **bad))


@pytest.mark.parametrize("ok", [
    dict(tau_turn=0.0, t_resp=0.0), dict(tau_turn=2.0 ** -10, t_resp=2.0 ** -10), dict(v_t=0.0), dict(L_max=1),
    dict(L_max=8, stuck_z=7), dict(drag_exp=0.0),
    dict(th_rel=0.0, th_click=1.0), dict(rho_c=0.0, R_min=6.0), dict(lam_s=0.0, lam_bg=0.0), dict(b2_value=-25.0),
    dict(b2_amp=1.0, b2_sigma=1.6, b2_p=0.0, b2_mode=1), dict(lam_bg=0.0, lam_s=512.0, b2_amp=1.0),
    dict(lattice="hex"), dict(lattice="square8prism"), dict(world_kind=0),
], ids=str)
def test_the_edges_of_the_abi3_ranges_are_valid(ok):
    assert V3.pack_world(spec.world("catch_v1", **ok)).shape == (66,)


def test_abi3_flags():
    assert {k: V3.FLAGS[k] for k in ("lateral_off", "hidden_off", "receptor_off", "motor_off")} == \
        dict(lateral_off=1 << 11, hidden_off=1 << 12, receptor_off=1 << 13, motor_off=1 << 14)
    fork = V3.flags("lateral_off", "hidden_off", "receptor_off", "motor_off", "contacts_off")
    assert V3.pack_world(spec.world("catch_v1", t_fork=512.0, fork_flags=fork)).shape == (66,)
    with pytest.raises(ValueError):
        V2.pack_world(spec.world(flags=V3.flags("lateral_off")))
    with pytest.raises(KeyError):
        V2.flags("motor_off")
    with pytest.raises(ValueError):
        V3.pack_world(spec.world("catch_v1", fork_flags=V3.flags("program_mode")))
    with pytest.raises(ValueError):
        V3.pack_world(spec.world("catch_v1", flags=1 << 15))


def test_v3_pricing_extends_abi2_and_adds_the_catch_charges():
    rng = np.random.default_rng(3)
    led2 = rng.random((20, 35)) * 50
    led2[:, V2.L["status"]] = rng.integers(0, 8, 20)
    led3 = np.concatenate([led2, np.zeros((20, 22))], axis=1)
    for w in (spec.world(), spec.world(c_live=0.01, t_open=100.0)):  # a BELL ledger re-prices bitwise as before
        assert np.array_equal(bits(V3.column_cost(led3, w)), bits(V2.column_cost(led2, w)))
        assert np.array_equal(bits(V3.fitness(led3, w)), bits(V2.fitness(led2, w)))
    led = np.zeros(57)
    vals = dict(income=500.0, live_time=74 * 1024.0, spikes=1e4, kappa_sum=5e3, contact_events=3e4, claims=80,
                sec_int=10.0, misses=40, rec_gain=900.0, b2_clicks=3)
    for k, v in vals.items():
        led[V3.L[k]] = v
    w = spec.world("catch_v1", b2_value=-25.0)
    base = 0.02 * 74 * 1024 + 0.004 * 1e4 + 0.004 * 5e3 + 0.001 * 3e4 + 0.5 * 80 + 0.004 * 10
    assert V3.column_cost(led, w) == pytest.approx(base + 2.0 * 40 + 0.001 * 900 + 25.0 * 3, rel=1e-12)  # c_miss 2
    assert V3.fitness(led, w) == pytest.approx((500.0 - V3.column_cost(led, w)) / 1024, rel=1e-12)
    assert spec.b2_cost(spec.world(b2_value=100.0)) == 0.0 and spec.b2_cost(w) == 25.0


# ------------------------------------------------------------------------------------------- CATCH closed forms
def test_catch_known_answers():  # LIFE_ABI.md 14
    z = spec.uid_initial(42, 0)
    lam = spec.lambda_max(spec.world("catch_v1"))
    c0 = spec.receptor_next(42, z, 0, 0.0, lam)
    assert c0 == 0.9337337422296379 and spec.receptor_next(42, z, 1, c0, lam) == 1.3670951439075458
    assert spec.draw(42, spec.S_RACC, z, 0) * lam == 2.0035396181417187
    assert spec.halo(1.0, 0.5, 1.5) == 0.7574651283969664 and spec.halo(0.0, 0.0, 1.5) == 1.0
    rate = spec.receptor_rate(spec.world("catch_v1"), 1.0, 0.5, (0.0, 0.0))
    assert rate == 1.564930256793933 and not spec.receptor_accepts(42, z, 0, rate, lam)
    assert spec.blob_heading(42, 0, 0, 0.1) == (-0.09998754332570875, 0.0015783471384705633)
    assert spec.blob_heading(42, 1, 0, 0.1) == (-0.09050519768911242, 0.04253009747525491)
    assert spec.blob_place(42, 0, 0, 0.0, 0.0, 2.0, 6.0) == (0.9226993667863177, 3.7675546907873656)
    assert spec.blob_place(42, 1, 0, 0.0, 0.0, 2.0, 6.0) == (-3.133232594777813, 3.264525461412328)
    assert not spec.blob_present(42, 0, 0.5) and spec.draw(42, spec.S_PPRES, 1, 0) == 0.8467749902283425
    assert spec.poisson_next(42, spec.S_TURN, 0, 0, 0.0, 20.0) == 15.984882681203024
    assert spec.poisson_next(42, spec.S_RTIME, 0, 0, 0.0, 50.0) == 71.9336107410924
    assert spec.drag(37, 0.5) == 6.082762530298219
    assert spec.dot_gain(1.0, 2.5, spec.drag(37, 0.5)) == (0.13549762641654428, 0.6703200460356393)
    assert spec.dot_gain(0.0, 2.5, 3.0) == (0.0, 1.0)
    assert spec.exposed_face("hexprism", [0, 1]) == (1.5, -0.8660254037844386)


def test_the_dot_closed_form_is_the_integral_of_its_velocity():
    # V = F e^(-s / tau_z) / gamma; the closed form k must match a fine midpoint integration (cf. BELL's gate G8)
    for dt, tau, gam in ((0.3, 2.5, 1.0), (4.0, 2.5, math.sqrt(37)), (25.0, 1.0, 2.0)):
        k, e = spec.dot_gain(dt, tau, gam)
        n = 200_000
        s = (np.arange(n) + 0.5) * (dt / n)
        assert k == pytest.approx(float(np.exp(-s / tau).sum() * (dt / n) / gam), rel=1e-9)
        assert e == math.exp(-dt / tau)
    # anchoring at an intermediate time and continuing gives the same end point (up to rounding)
    k1, e1 = spec.dot_gain(1.5, 2.5, 3.0)
    k2, _ = spec.dot_gain(2.0, 2.5, 3.0)
    k12, _ = spec.dot_gain(3.5, 2.5, 3.0)
    assert k1 + e1 * k2 == pytest.approx(k12, rel=1e-14)


def test_receptor_streams_advance_and_thin_to_the_world_rate():
    z = spec.uid_initial(7, 0)
    t, times = 0.0, []
    for j in range(4000):
        t = spec.receptor_next(7, z, j, t, 2.05)
        times.append(t)
    gaps = np.diff([0.0] + times)
    assert (gaps > 0).all() and abs(gaps.mean() - 1 / 2.05) < 0.03
    assert spec.receptor_next(7, z, 0, 2.0 ** 40, 1e-30) > 2.0 ** 40  # always strictly later (nextup)
    w = spec.world("catch_v1")
    for d in (0.0, 1.0, 3.0):
        rate = spec.receptor_rate(w, d, 0.0, (0.0, 0.0))
        kept = np.mean([spec.receptor_accepts(7, z, j, rate, spec.lambda_max(w)) for j in range(20000)])
        assert abs(kept - rate / spec.lambda_max(w)) < 0.012
    w2 = spec.world("catch_v1", b2_amp=1.0, b2_sigma=1.6)
    both = spec.receptor_rate(w2, 0.0, 0.0, (0.0, 0.0), (0.0, 0.0))
    assert both == w2.lam_bg + w2.lam_s * 1.0 + w2.lam_s * (1.0 * 1.0) == spec.lambda_max(w2)


def test_blob_draws():
    for q in range(300):
        x, y = spec.blob_place(5, 0, q, 10.0, -4.0, 2.0, 6.0)
        assert 2.0 - 1e-12 <= math.hypot(x - 10.0, y + 4.0) <= 6.0 + 1e-12
        vx, vy = spec.blob_heading(5, 1, q, 0.1)
        assert math.hypot(vx, vy) == pytest.approx(0.1, abs=1e-15)
    assert spec.blob_place(5, 0, 3, 1.0, 2.0, 4.0, 4.0) != spec.blob_place(5, 1, 3, 1.0, 2.0, 4.0, 4.0)
    assert all(spec.blob_present(5, q, 1.0) for q in range(100)) and not any(spec.blob_present(5, q, 0.0)
                                                                            for q in range(100))
    gaps = [spec.poisson_next(5, spec.S_TURN, 0, k, 0.0, 20.0) for k in range(4000)]
    assert abs(np.mean(gaps) - 20.0) < 1.0 and min(gaps) > 0


def test_the_key_clicks_once_per_press():
    th_c, th_r = 0.6, 0.25
    assert spec.key_step(True, 0.0, 1.0, th_c, th_r) == (False, True)  # a full twitch from rest clicks
    assert spec.key_step(True, 0.0, 0.5, th_c, th_r) == (True, False)  # kappa 1/2 from rest does not
    assert spec.key_step(True, 0.3, 0.8, th_c, th_r) == (False, True)  # two halves in quick succession do
    assert spec.key_step(False, 0.7, 1.0, th_c, th_r) == (False, False)  # held down: no second click
    assert spec.key_step(False, 0.24, 0.49, th_c, th_r) == (True, False)  # released below th_rel: re-armed
    assert spec.key_step(False, 0.2, 0.7, th_c, th_r) == (False, True)  # released and pressed in one twitch


def test_exposed_faces_cancel_over_any_body():
    # the surface-normal law's key property (BODY_DESIGN_PROPOSAL.md 2.2): an isolated cell has n = 0 exactly, and the
    # faces of any body sum to 0, so tonic or synchronous firing never drifts it
    assert spec.exposed_face("hexprism", range(6)) == (0.0, 0.0)
    assert spec.exposed_face("hexprism", [6, 7]) == (0.0, 0.0)  # vertical slots never pull
    assert spec.exposed_face("hexprism", [0, 3]) == (0.0, 0.0) and spec.exposed_face("hex", [1, 3, 5]) == (0.0, 0.0)
    off = lattice.offsets("hex")
    two_x = [round(2 * u[0]) for u in lattice.unit_vectors("hex")]  # x in half units (exact)
    sgn_y = [0 if abs(u[1]) < 1e-12 else (1 if u[1] > 0 else -1) for u in lattice.unit_vectors("hex")]
    rng = np.random.default_rng(4)
    for _ in range(50):
        body = {tuple(c) for c in rng.integers(-3, 4, (int(rng.integers(1, 30)), 2)).tolist()}
        sx = sy = 0
        for a, b in body:
            for d, (da, db) in enumerate(off):
                if (a + da, b + db) not in body:
                    sx += two_x[d]
                    sy += sgn_y[d]
        assert sx == 0 and sy == 0
