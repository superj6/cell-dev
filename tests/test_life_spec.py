import math
import re
import struct
from pathlib import Path

import numpy as np
import pytest

from src import lattice
from src.life import spec
from tests.life_helpers import EDGE_WORLD_VALUES, INVALID_WORLD_VALUES

DOC = (Path(__file__).resolve().parents[1] / "docs/LIFE_ABI.md").read_text()
Y14 = [0.3, -2.7, 1.0, 0.5, -0.26, 0.0, 1e-9, 0.3, 0.75, 0.13, 0.0, -2.0, 1.1, 0.0, -1.0, 0.5, -9.0, 0.0, 2.2,
       -0.0624, 0.0625]
THETA14 = [0.25, -2.0, 1.0, 4.0, 1.5, 0.0, 1.0, 0.5, 0.5, 0.0078125, 0.5, 0.0, 1.0, 0.25, 0.13447071068499755, 0.875,
           -2.0, 8.0, 2.0, -0.0, 0.0]


def bits(x: float) -> int:
    return struct.unpack("<Q", struct.pack("<d", x))[0]


def _table_names(heading: str) -> list[str]:
    """Second-column names of the first markdown table after ``heading`` (cells like 'a, b' are split)."""
    lines = DOC.split(heading, 1)[1].splitlines()
    start = next(i for i, ln in enumerate(lines) if ln.startswith("|"))
    names = []
    for ln in lines[start:]:
        if not ln.startswith("|"):
            break
        cells = [c.strip() for c in ln.strip().strip("|").split("|")]
        if re.match(r"^\d", cells[0]):
            names += [n.strip() for n in cells[1].split(",")]
    return names


def test_hash_known_answers():
    assert spec.splitmix64(0) == 0xE220A8397B1DCDAF
    assert spec.splitmix64(1) == 0x910A2DEC89025CC1
    assert spec.hash64(0, 0) == 0xA706DD2F4D197E6F
    h = spec.hash64(1, 2, 3, 4)
    assert h == 0x89F838C6080F2B76 and spec.u01(h) == 0.5389438136554047
    assert spec.hash64(spec.MASK64, 7, -1) == 0x6BEEACB0A480F707
    assert spec.sitekey(-1, 2) == 0xFFFFFFFF00000002 and spec.sitekey(3, -4) == 0x00000003FFFFFFFC
    assert spec.normal(42, spec.S_CLK, spec.sitekey(0, 0), 0) == 0.25705196441331246
    assert spec.normal(42, spec.S_DC, spec.sitekey(0, 0), spec.sitekey(1, 0), 0) == 1.039345905501138
    assert spec.draw(42, spec.S_PHASE, spec.sitekey(0, 0), 0) == 0.5527679572439935
    z = spec.uid_initial(42, 0)
    assert z == 0x2791839B6C9CAF25 and spec.uid_daughter(42, z, 0) == 0x64F81C91D3FA48D1
    assert spec.draw(42, spec.S_JIT, z, 1, 3) == 0.549803149142197


def test_u01_is_an_odd_multiple_inside_the_open_interval():
    for h in [0, 1, 2047, 2048, spec.MASK64, spec.MASK64 - 2048] + [spec.hash64(5, 5, i) for i in range(200)]:
        u = spec.u01(h)
        assert 0.0 < u < 1.0
        n = u * 2.0 ** 53
        assert n == int(n) and int(n) % 2 == 1
    assert spec.u01(0) == 2.0 ** -53 and spec.u01(spec.MASK64) == 1.0 - 2.0 ** -53


def test_normal_is_bounded_exact_and_standard():
    z = np.array([spec.normal(9, spec.S_CLK, i) for i in range(4000)])
    assert np.all(np.abs(z) <= 6.0)
    assert abs(z.mean()) < 0.06 and 0.9 < z.var() < 1.1
    s = sum(spec.hash64(9, spec.S_CLK, 7, j) >> 11 for j in range(12))
    assert spec.normal(9, spec.S_CLK, 7) == float(s) * 2.0 ** -53 - 6.0


def test_uids_are_odd_and_distinct():
    uids = {spec.uid_initial(3, i) for i in range(64)} | {spec.uid_daughter(3, 12345, d) for d in range(500)}
    assert len(uids) == 564 and all(u & 1 for u in uids)


def test_rint_keeps_sign_and_ties_to_even():
    assert bits(spec.rint(-0.4)) == bits(-0.0) and bits(spec.rint(0.4)) == bits(0.0)
    assert [spec.rint(x) for x in (0.5, 1.5, 2.5, -2.5, 3.5)] == [0.0, 2.0, 2.0, -2.0, 4.0]
    assert spec.q10(0.99960) == 1.0 and spec.q10(-7.0) == -2.0 and spec.q10(0.3) == round(0.3 * 1024) / 1024


def test_decode_known_answer_bitwise():
    out = spec.decode_knobs(Y14)
    assert [bits(x) for x in out] == [bits(x) for x in THETA14]


def test_decode_lands_on_the_documented_grids():
    rng = np.random.default_rng(0)
    for scale in (0.3, 2.0, 50.0):
        for y in rng.normal(0, scale, (300, spec.P)):
            th = spec.decode_knobs(y)
            for name, v in zip(spec.KNOBS, th):
                if name in spec.GRIDS:
                    assert v in spec.GRIDS[name], (name, v)
                else:
                    lo, hi = spec.RANGES[name]
                    assert lo <= v <= hi


def test_decode_laws():
    d = lambda name, y: spec.decode_knobs([y if k == name else 0.0 for k in spec.KNOBS])[spec.K[name]]  # noqa: E731
    assert [d("tau_m", y) for y in (-9, -1.6, 0, 1.6, 9)] == [1.0, 1.0, 4.0, 16.0, 16.0]
    assert [d("t_ref", y) for y in (-9, -1.5, 0, 0.25, 0.3, 9)] == [0.5, 0.5, 2.0, 2.0, 2.5, 4.0]  # 4.5 -> 4
    assert [d("p_div", y) for y in (-1, 0.12, 0.13, 1.0, 2.0, 9)] == [0.0, 0.0, 2.0 ** -7, 2.0 ** -4, 1.0, 1.0]
    assert [d("emit0", y) for y in (-1e-12, 0.0, 1e-12)] == [0.0, 0.0, 1.0]
    for name, table in (("delta", spec.DELTA), ("kappa", spec.KAPPA), ("phi", spec.PHI)):
        assert [d(name, y) for y in (-3, 0.2, 0.3, 0.8, 1.3, 9)] == [table[i] for i in (0, 0, 1, 2, 3, 3)]
    assert [d("tau_tr", y) for y in (-9, -0.01, 0.0, 0.01, 9)] == [2.0, 4.0, 8.0, 8.0, 16.0]
    assert d("pol0", 9.0) == 2.0 and d("pol0", 0.5) == 0.875
    assert d("asym", 0.0) == 0.5 and d("sec0", 0.0) == 0.25


def test_gene_decodes():
    assert [spec.decode_lambda(x) for x in (-5, -2.5, -0.5, 0, 0.5, 3.4, 10)] == \
        [0.5, 0.5, 0.125, 0.0625, 0.03125, 2.0 ** -7, 2.0 ** -7]
    assert spec.decode_dm(0.0, 6) == 0.025 and spec.decode_km(0.0) == 0.155
    w = spec.world()  # longest tick interval under default physics keeps one tick's shipping below 90 %
    dt_max = w.P0 * math.exp(6 * w.clock_sd) * (1 + w.tick_jit)
    for kind in ("hex", "square8"):
        D = len(lattice.offsets(kind))
        assert dt_max < spec.P_MAX and D * spec.decode_dm(50.0, D) * dt_max < spec.CHEM_SHIP_MAX


def test_genome_layout():
    # ABI 2: inputs g[16], m/(1+m)[2], f/tau_tr, r/tau_tr[2], n_view/D; flank_best/2 was removed (LIFE_ABI.md 15.32)
    assert spec.ABI_VERSION == 2 and spec.GENOME_SIZE == 793 and spec.NIN == 22
    off = 0
    for f in spec.GENOME_FIELDS:
        a, b = spec.GENOME_SLICES[f.name]
        assert a == off and b - a == math.prod(f.shape)
        off = b
    assert spec.GENOME_SLICES["W"] == (0, 352) and spec.GENOME_SLICES["b"] == (352, 368)
    assert spec.GENOME_SLICES["A"] == (432, 768) and spec.GENOME_SLICES["km"] == (791, 793)


def _random_genome(rng, n_active=8):
    g = rng.normal(0, 1, spec.GENOME_SIZE).astype(np.float32)
    a, b = spec.GENOME_SLICES["act"]
    g[a:b] = 0.0
    g[a:a + n_active] = 1.0
    return g


def test_pack_genomes_decodes_and_masks_inactive_slots():
    rng = np.random.default_rng(1)
    raw = np.stack([_random_genome(rng), _random_genome(rng, 3)])
    gt = spec.pack_genomes(raw, "hex")
    assert gt.dtype == np.float64 and gt.flags.c_contiguous and gt.shape == (2, 793)
    assert not np.any(np.signbit(gt) & (gt == 0))  # no -0.0
    for r, n_act in ((0, 8), (1, 3)):
        act = spec.genome_view(gt[r], "act")
        assert act.tolist() == [1.0] * n_act + [0.0] * (16 - n_act)
        W, A = spec.genome_view(gt[r], "W"), spec.genome_view(gt[r], "A")
        assert not W[n_act:].any() and not W[:, n_act:16].any() and not A[:, n_act:].any()
        assert np.array_equal(W[:n_act, 16:], spec.genome_view(raw[r], "W")[:n_act, 16:].astype(np.float64))
        for name in ("b", "lam", "s0", "Q"):
            assert not spec.genome_view(gt[r], name)[n_act:].any()
        lam = spec.genome_view(gt[r], "lam")[:n_act]
        assert all(x in [2.0 ** -k for k in range(1, 8)] for x in lam)
        g0 = spec.genome_view(gt[r], "s0")[:n_act]
        assert np.array_equal(g0, [spec.sigmoid(float(x)) for x in spec.genome_view(raw[r], "s0")[:n_act]])
        assert np.all(spec.genome_view(gt[r], "Dm") < spec.CHEM_SHIP_MAX / (6 * spec.P_MAX))
        assert np.array_equal(spec.genome_view(gt[r], "a0"), spec.genome_view(raw[r], "a0").astype(np.float64))


def test_inactive_slots_are_neutral():
    rng = np.random.default_rng(2)
    raw = _random_genome(rng, 5)
    other = raw.copy()
    for name in ("W", "b", "lam", "s0", "Q", "A"):
        v = spec.genome_view(other, name)
        noise = rng.normal(0, 3, v.shape).astype(np.float32)
        if name == "W":
            v[5:] += noise[5:]
            v[:, 5:16] += noise[:, 5:16]
        elif name == "A":
            v[:, 5:] += noise[:, 5:]
        else:
            v[5:] += noise[5:]
    assert np.array_equal(spec.pack_genomes(raw), spec.pack_genomes(other))
    gt = spec.pack_genomes(raw)[0]
    g = np.concatenate([rng.random(5), np.zeros(11)])
    junk = np.concatenate([g[:5], rng.random(11)])  # zeroed columns: inactive gene values cannot reach theta
    assert [bits(y) for y in spec.readout(gt, g)] == [bits(y) for y in spec.readout(gt, junk)]
    assert spec.phenotype(gt, g) == spec.decode_knobs(spec.readout(gt, g))


def test_program_and_init_packing():
    r25 = spec.theta(b=1.125, tau_m=1, t_ref=2.5, w0=-1, emit0=1, delta=2, kappa=1, p_div=0.5, phi=2)
    alone = spec.theta(b=1.875, tau_m=8, t_ref=2, kappa=1, p_div=0.5, phi=2)
    juv = r25.copy()
    juv[spec.K["emit0"]] = 0.0
    prog = spec.pack_program(r25, alone=alone, juvenile=juv, juv_ticks=10, flank_gate=2, p_div_lo=1 / 16)
    assert prog.shape == (spec.PROGRAM_SIZE,) == (119,) and prog.dtype == np.float64
    rows = prog[:105].reshape(5, spec.P)
    assert np.array_equal(rows[spec.PROGRAM_ROW["alone"]], alone)
    assert np.array_equal(rows[spec.PROGRAM_ROW["juvenile"]], juv)
    assert np.array_equal(rows[spec.PROGRAM_ROW["rim"]], r25) and np.array_equal(rows[spec.PROGRAM_ROW["zygote"]], r25)
    assert prog[spec.PROGRAM_SCALAR["juv_ticks"]] == 10 and prog[spec.PROGRAM_SCALAR["p_div_lo"]] == 0.0625
    assert prog[spec.PROGRAM_SCALAR["k_grow"]] == 1e300 and prog[spec.PROGRAM_SCALAR["timer_step"]] == 2.0
    with pytest.raises(KeyError):
        spec.pack_program(r25, cap=91)
    with pytest.raises(KeyError):
        spec.theta(gain=1)
    body, n = spec.pack_init([(0, 0), (1, 0), (0, 1)], rows=[1, 1, -1])
    assert n == 3 and body.shape == (spec.MAX_INIT, 3) and body.dtype == np.int32
    assert body[:3].tolist() == [[0, 0, 1], [1, 0, 1], [0, 1, -1]] and not body[3:].any()
    with pytest.raises(ValueError):
        spec.pack_init([(0, 0), (0, 0)])


@pytest.mark.parametrize("kind", ["hex", "square4", "square8"])
def test_lattice_tables(kind):
    lat, unit = spec.lattice_tables(kind)
    D = len(lattice.offsets(kind))
    assert lat.dtype == np.int32 and lat.shape == (2 + 6 * D,) and lat[0] == spec.LATTICE_CODES[kind] and lat[1] == D
    oa, ob, back, prev, nxt, rot = (lat[2 + i * D: 2 + (i + 1) * D] for i in range(6))
    for d in range(D):
        assert (oa[back[d]], ob[back[d]]) == (-oa[d], -ob[d])
        assert nxt[prev[d]] == d and prev[nxt[d]] == d
    assert sorted(rot.tolist()) == list(range(D))
    assert unit.shape == (D, 2) and unit.dtype == np.float64 and unit.flags.c_contiguous
    assert np.allclose(np.hypot(unit[:, 0], unit[:, 1]), 1.0, atol=1e-15)


def test_bell_v1_preset_matches_the_design():
    w = spec.world("bell_v1")
    assert (w.T, w.d_min, w.d0, w.delay_sd, w.jit, w.tau_mis, w.P0, w.clock_sd, w.tick_jit) == \
        (1024.0, 0.5, 1.0, 0.1, 0.1, 0.05, 2.0, 0.05, 0.1)
    assert (w.tau_z, w.th, w.th_lo, w.tau_R, w.tau_e, w.h_inc) == (2.5, 0.6, 0.25, 6.0, 0.5, 1.0)
    assert (w.c_live, w.c_spike, w.c_tw, w.c_msg, w.c_div, w.c_sec) == tuple(spec.COSTS.values())
    assert (w.n_max, w.e_max, w.fabric_R, w.lattice, w.lives) == (1024, 5_000_000, 0, "hex", 3)
    v = spec.pack_world(w)
    assert v.shape == (spec.WORLD_SIZE,) == (41,) and v[spec.WORLD_INDEX["th"]] == 0.6
    many = spec.pack_world([w, spec.world(window_h=0.25, flags=spec.flags("lockstep"))])
    assert many.shape == (2, 41) and many[1, spec.WORLD_INDEX["flags"]] == spec.FLAGS["lockstep"]


@pytest.mark.parametrize("bad", [
    dict(window_h=0.3), dict(window_h=1.0), dict(window_h=0.25, oracle_cap=91), dict(T=100.5), dict(t0=0.5),
    dict(t_open=1024.0), dict(fork_flags=spec.flags("program_mode")), dict(flags=spec.flags("integer_twin")),
    dict(flags=1 << 20), dict(jit=1.0), dict(lattice="tri"), *INVALID_WORLD_VALUES,
], ids=str)
def test_invalid_worlds_are_rejected(bad):
    with pytest.raises(ValueError):
        spec.pack_world(spec.world(**bad))


@pytest.mark.parametrize("ok", EDGE_WORLD_VALUES, ids=str)
def test_the_edges_of_the_world_ranges_are_valid(ok):
    spec.validate_world(spec.world(**ok))
    assert spec.min_tick_period(spec.world(**ok)) >= spec.STEP_MIN


def test_packing_refuses_nan_and_infinity():
    # 4.4: the packed table holds no NaN or infinity, so no knob law can turn one into an out-of-range table index
    raw = np.zeros(spec.GENOME_SIZE, dtype=np.float32)
    assert np.all(np.isfinite(spec.pack_genomes(raw)))
    for field, idx, v in (("a0", spec.K["tau_m"], np.nan), ("a0", spec.K["delta"], np.nan), ("W", (0, 0), np.inf),
                          ("Q", 3, -np.inf)):
        bad = np.stack([raw, raw.copy()])
        spec.genome_view(bad[1], field)[idx] = v
        with pytest.raises(ValueError, match=r"rows \[1\] hold NaN or infinity"):
            spec.pack_genomes(bad)
    with pytest.raises(ValueError, match="NaN or infinity"):
        spec.pack_program(spec.theta(b=np.nan))
    with pytest.raises(ValueError, match="NaN or infinity"):
        spec.pack_program(spec.theta(), k_grow=np.inf)


def test_later_stages_are_stubs():
    for name in ("bell_v2", "bell_v3"):
        assert not spec.PRESETS[name].implemented
        with pytest.raises(NotImplementedError):
            spec.pack_world(spec.world(name))
    assert spec.pack_world(spec.world("bell_v1_5")).shape == (41,)
    for h in (0.5, 0.25, 0.125):
        spec.validate_world(spec.world(window_h=h))


def test_fitness_reprices_ledger_columns():
    led = np.zeros(spec.LEDGER_SIZE)
    vals = dict(income=60.0, live_time=1024.0, spikes=120, kappa_sum=120.0, contact_events=10, claims=2, sec_int=5.0)
    for k, v in vals.items():
        led[spec.L[k]] = v
    w = spec.world()
    cost = 0.02 * 1024 + 0.004 * 120 + 0.004 * 120 + 0.001 * 10 + 0.5 * 2 + 0.004 * 5
    assert spec.column_cost(led, w) == pytest.approx(cost, abs=1e-12)
    assert spec.fitness(led, w) == pytest.approx((60.0 - cost) / 1024, abs=1e-12)
    led[spec.L["status"]] = spec.STATUS["guard_cells"]
    led[spec.L["t_end"]] = 1000.0
    assert spec.guard_charge(led, w) == pytest.approx(0.02 * 1024 * 24)
    cheap = spec.world(c_live=0.01)
    assert spec.fitness(led, cheap) == pytest.approx((60.0 - spec.column_cost(led, cheap) - 0.01 * 1024 * 24) / 1024)
    assert spec.fitness(led, spec.world(t_open=512.0)) == pytest.approx(
        (60.0 - cost - 0.02 * 1024 * 24) / 512, abs=1e-12)


def test_document_tables_match_spec():
    # docs/LIFE_ABI.md is the ABI-3 contract (spec.V3); spec's module-level names are the ABI the kernel runs (V2)
    v3 = spec.V3
    assert _table_names("### 4.9 Ledger") == list(v3.LEDGER)
    assert _table_names("### 4.7 World vector") == list(v3.WORLD_KEYS)
    assert _table_names("## 8. Phenotype decode") == list(v3.KNOBS)
    flags = re.findall(r"^\| (\d+) \| (\w+) \|", DOC.split("## 12. Flags and forks", 1)[1], flags=re.M)
    assert {name: 1 << int(b) for b, name in flags} == v3.FLAGS
    streams = re.findall(r"^\| S_(\w+) \| (\d+) \|", DOC, flags=re.M)
    assert {name.lower(): int(i) for name, i in streams} == v3.STREAMS
    sizes = re.search(r"life_sizes\(int32_t out\[10\]\);\s+// abi, genome (\d+), program (\d+), world (\d+), "
                      r"ledger (\d+), hashes (\d+), knobs (\d+),\s+// max_init (\d+), fate_i (\d+), fate_f (\d+)", DOC)
    assert [int(x) for x in sizes.groups()] == list(v3.SIZES.values())[1:]
    assert list(v3.SIZES) == list(spec.SIZES) == ["abi", "genome", "program", "world", "ledger", "hashes", "knobs",
                                                  "max_init", "fate_i", "fate_f"]
    table = DOC.split("### 4.4 Genome table", 1)[1].split("###", 1)[0]  # the genome fields, shapes and offsets
    rows = re.findall(r"^\| (\w+) \| ([\[\]\d]+) \| (\d+) \|", table, flags=re.M)
    assert {n: int(o) for n, _, o in rows} == {n: a for n, (a, _) in v3.GENOME_SLICES.items()}
    assert {n: sh for n, sh, _ in rows} == {f.name: "".join(f"[{k}]" for k in f.shape) for f in v3.GENOME_FIELDS}
    # ABI 2 (what the kernel runs now) is the prefix of every ABI-3 table
    assert list(v3.LEDGER[:spec.LEDGER_SIZE]) == list(spec.LEDGER) and v3.WORLD_KEYS[:41] == spec.WORLD_KEYS
    assert v3.KNOBS[:spec.P] == spec.KNOBS and {k: v3.FLAGS[k] for k in spec.FLAGS} == spec.FLAGS
    assert {k: v3.STREAMS[k] for k in spec.STREAMS} == spec.STREAMS
