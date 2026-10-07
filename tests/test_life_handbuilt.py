"""Hand-built organisms (src/life/handbuilt.py): their programs say what the design says, they live without
implementation faults, and the cheap reference points hold; R25-v1 written as a GRN genome (gate G9) decodes the
program's rows, and a constant-readout genome is bitwise its program twin in the kernel and the reference."""
import math

import numpy as np
import pytest

from src.life import analysis, spec
from src.life import handbuilt as hb
from src.life import reference as ref
from tests.life_helpers import bits, kernel, mismatch, r25

K, ROW, SC = spec.K, spec.PROGRAM_ROW, spec.PROGRAM_SCALAR


def _row(org, name):
    i = ROW[name]
    return org.program[i * spec.P:(i + 1) * spec.P]


def test_r25_v1_is_the_design_program():
    p = hb.R25_V1
    assert np.array_equal(p.program, r25())  # the program the time-model tests use
    contact, alone, juv = _row(p, "contact"), _row(p, "alone"), _row(p, "juvenile")
    for k, v in dict(b=1.125, tau_m=1, t_ref=2.5, w0=-1, emit0=1, emit1=0, delta=2, kappa=1, p_div=0.5, phi=2).items():
        assert contact[K[k]] == v, k
    for k, v in dict(b=1.875, tau_m=8, t_ref=2, kappa=1, emit0=0, w0=0, p_div=0.5, phi=2).items():
        assert alone[K[k]] == v, k
    assert juv[K["emit0"]] == 0 and np.array_equal(np.delete(juv, K["emit0"]), np.delete(contact, K["emit0"]))
    sc = {k: p.program[i] for k, i in SC.items()}
    assert sc["juv_ticks"] == 10 and sc["flank_gate"] == 2 and sc["p_div_lo"] == 1 / 16 and sc["zyg_row"] == 0
    assert hb.R25_V1_BELL3.program[SC["p_div_lo"]] == 0.05
    assert np.array_equal(np.delete(hb.R25_V1_BELL3.program, SC["p_div_lo"]), np.delete(p.program, SC["p_div_lo"]))
    naive = hb.R25_NAIVE.program
    assert naive[SC["flank_gate"]] == 0 and naive[SC["juv_ticks"]] == 0
    assert _row(hb.R25_NAIVE, "contact")[K["phi"]] == 0 and _row(hb.R25_NAIVE, "contact")[K["p_div"]] == 0.25


def test_ladder_programs_follow_the_prototype():
    assert hb.L0.flags == spec.FLAGS["contacts_off"] and _row(hb.L0, "contact")[K["emit0"]] == 0
    assert hb.L1.program[SC["zyg_row"]] == 1 and _row(hb.L1, "zygote")[K["b"]] == _row(hb.L1, "alone")[K["b"]]
    assert math.isclose(hb.tonic_period(_row(hb.L1, "zygote")[K["b"]], 4.0, 3.5), 8.0, rel_tol=1e-12)
    assert _row(hb.L1, "contact")[K["w0"]] == 1.5 and _row(hb.L1, "contact")[K["b"]] == 0
    for org in (hb.L2, hb.L3, hb.L4):
        c = _row(org, "contact")
        assert (c[K["b"]], c[K["t_ref"]], c[K["w0"]], c[K["delta"]]) == (1.2, 2.6, -1.0, 2.0)  # AOFF, off-grid
    assert hb.L2.program[SC["flank_gate"]] == 0 and _row(hb.L2, "contact")[K["p_div"]] == 0.25
    assert hb.L3.program[SC["juv_ticks"]] == 0 and hb.L4.program[SC["juv_ticks"]] == 10
    assert all(o.program[SC["p_div_lo"]] == hb.BELL3_P_DIV_LO for o in (hb.L0, hb.L1, hb.L3, hb.L4, hb.B))
    b = _row(hb.B, "contact")
    assert (b[K["b"]], b[K["tau_m"]], b[K["t_ref"]]) == (2.0, 2.0, 0.5)


def test_every_organism_lives_cleanly():
    bad = spec.STATUS["capacity"] | spec.STATUS["ledger_mismatch"] | spec.STATUS["guard_cells"]
    for name, org in hb.ORGANISMS.items():
        assert org.program.shape == (spec.PROGRAM_SIZE,) and np.all(np.isfinite(org.program)), name
        res = org.run(list(range(3)), cap=20, T=256.0)
        assert not np.any(res["status"].astype(np.int64) & bad), name
        grows = name not in ("silent", "lone-pump", "lone-best")
        assert np.all((res["n_end"] > 1) == grows), name
        if org.flags & spec.FLAGS["contacts_off"]:
            assert np.all(res["arrivals"] == 0) and np.all(res["contact_events"] == 0), name
    assert np.all(hb.SILENT_ZYGOTE.run([0, 1])["F"] == -spec.COSTS["c_live"])


def test_lone_grid_and_the_lone_cell_reference_points():
    combos, progs = hb.lone_grid()
    assert len(combos) == 33 * 5 * 8 * 4 == len(progs)
    assert (1.875, 8.0, 2.0, 1.0) in combos and (1.625, 4.0, 4.0, 1.0) in combos
    for p, period in ((hb.LONE_PUMP, 8.097), (hb.LONE_BEST, 7.822)):
        assert abs(hb.tonic_period(p[K["b"]], p[K["tau_m"]], p[K["t_ref"]]) - period) < 1e-3
    assert math.isclose(hb.tonic_drive(hb.tonic_period(1.625, 4.0, 4.0), 4.0, 4.0), 1.625, rel_tol=1e-12)
    pump = analysis.summary(hb.LONE_PUMP_CELL.run(list(range(16)))["F"])
    best = analysis.summary(hb.LONE_BEST_CELL.run(list(range(16)))["F"])
    assert abs(pump["mean"] - 0.0326) < 1e-4 and best["mean"] > pump["mean"] + 3 * math.hypot(pump["se"], best["se"])


def test_messages_off_bodies_never_beat_a_lone_cell():
    """G2's registered points (-0.004, -0.035, -0.137 at 2, 3 and 7 cells) for the messages-off ladder rung L0."""
    lone = hb.LONE_PUMP_CELL.run(list(range(16)))["F"].mean()
    for N, F in ((2, -0.004), (3, -0.035), (7, -0.137)):
        s = analysis.summary(hb.L0.run(analysis.curve_seeds(N, 36), cap=N, threads=4)["F"])
        assert s["mean"] < lone and abs(s["mean"] - F) < 0.006, (N, s)


@pytest.mark.slow
def test_ladder_reproduces_the_prototype_away_from_the_91_cell_seeds():
    """task_bell e7 points (36 lives each; values rounded to 1e-3) against 144 kernel lives, within 3 SE."""
    for org, N, (F, se) in ((hb.L1, 3, (0.046, 0.001)), (hb.L2, 37, (0.434, 0.044)), (hb.L3, 37, (0.513, 0.015)),
                            (hb.L4, 37, (0.534, 0.014)), (hb.L4, 61, (0.681, 0.060)), (hb.B, 37, (0.150, 0.036))):
        s = analysis.summary(org.run(analysis.curve_seeds(N, 144, seed0=10 ** 6), cap=N, threads=4)["F"])
        z = analysis.z_diff(s, dict(mean=F, se=math.hypot(se, 1e-3 / math.sqrt(12))))
        assert abs(z) <= 3, (org.name, N, s, z)


def test_grower_options_are_additive():
    """The D4 switches default to ``layered``: the existing programs are unchanged, bit for bit."""
    assert np.array_equal(hb.r25_v1(placement=True, gate=True).program, hb.R25_V1.program)
    assert np.array_equal(hb.r25_v1(contact=hb.COUPLED).program, hb.R25_V1.program)
    po, go = hb.r25_v1(gate=False), hb.r25_v1(placement=False)
    assert po.program[SC["flank_gate"]] == 0 and _row(po, "contact")[K["phi"]] == 2
    assert go.program[SC["flank_gate"]] == 2 and _row(go, "contact")[K["phi"]] == 0 and _row(go, "alone")[K["phi"]] == 0


def test_r25_genome_decodes_the_program_rows_in_every_settled_state():
    states = hb.r25_genome_states()
    assert set(states) >= {"alone", "juvenile_closed", "juvenile_open", "contact_closed", "contact_open"}
    assert all(not v["mismatches"] for v in states.values()), states
    g = hb.R25_V1_GRN.genome
    assert g.dtype == np.float32 and g.size == spec.GENOME_SIZE == 809
    gt = hb.R25_V1_GRN.table("hex")[0]
    assert list(np.nonzero(spec.genome_view(gt, "act"))[0]) == [0, 1, 2, 3, 4]
    lam = spec.genome_view(gt, "lam")
    assert lam[hb.GENE_JUVENILE] == 1 / 16 and lam[hb.GENE_CONTACT] == lam[hb.GENE_FLANK] == lam[hb.GENE_ECHO] == 0.5
    assert lam[hb.GENE_RESET] == 0.5 and spec.genome_view(gt, "Q")[hb.GENE_RESET] == -1.0
    assert "mother_after_claim" in states
    # the design's minimal form (no echo) is exact only once settled: its first contact tick is still mid-switch
    mini = hb.r25_genome_states(hb.GrnOrganism("m", hb.r25_genome(echo=False)))
    assert mini["first_contact_tick"]["mismatches"] and not mini["contact_open"]["mismatches"]


def test_r25_genome_keeps_a_newborn_silent_for_exactly_ten_ticks():
    """Juvenile gene: daughter starts at min(1, g + asym), decays by 15/16 per own tick; emission needs g1 < 0.508."""
    gt = hb.R25_V1_GRN.table("hex")[0]
    asym = spec.phenotype(gt, np.zeros(16))[K["asym"]]
    emits = []
    for n in range(14):
        g = np.zeros(16)
        g[hb.GENE_CONTACT] = g[hb.GENE_ECHO] = 1.0
        g[hb.GENE_JUVENILE] = asym * (15 / 16) ** (n + 1) + (1 - (15 / 16) ** (n + 1)) * spec.sigmoid(-12.0)
        emits.append(spec.phenotype(gt, g)[K["emit0"]])
    assert emits == [0.0] * 10 + [1.0] * 4  # ticks 0..9 silent, as the program's juv_ticks = 10


def test_r25_genome_gates_and_timer_variants():
    for gate in ("flank", "n_view", None):
        gt = spec.pack_genomes(hb.r25_genome(gate=gate)[None])[0]
        assert np.all(np.isfinite(gt))
    with pytest.raises(ValueError):
        hb.r25_genome(gate="rim")
    # the n_view gate opens at n_view >= D - 1: input n_view / D through W = 20 D, b = 30 - 20 D
    W = spec.genome_view(hb.r25_genome(gate="n_view", D=8), "W")
    b = spec.genome_view(hb.r25_genome(gate="n_view", D=8), "b")
    p = [b[hb.GENE_FLANK] + W[hb.GENE_FLANK, spec.G_MAX + 5] * n / 8 for n in range(9)]
    assert [x > 0 for x in p] == [False] * 7 + [True] * 2
    timed = spec.genome_view(hb.r25_genome(timer=2.0), "A")[K["p_div"], hb.GENE_TIMER]
    assert timed == -2.0
    assert spec.genome_view(hb.r25_genome(placement=False), "a0")[K["phi"]] == 0.0


def test_r25_genome_lives_match_the_reference_bitwise():
    w = spec.world(T=120.0, oracle_cap=7)
    k = kernel(w, [3], genome=hb.R25_V1_GRN.genome)
    r = ref.run(w, genome=hb.R25_V1_GRN.genome, seed=3)
    assert k["n_end"][0] > 1 and k["spikes"][0] > 0
    assert mismatch(k, 0, r) == []


def test_constant_genome_is_bitwise_its_program_twin():
    """GRN mode with a constant readout adds nothing to a fixed phenotype (G10, grn_layer); sec readouts of -800
    decode to exactly 0 because sigma(-800) underflows to 0 in C and in spec.sigmoid."""
    assert spec.sigmoid(-800.0) == 0.0 and spec.sigmoid(800.0) == 1.0
    for row in (hb.LONE_BEST, hb.LONE_PUMP, hb.SILENT):
        g = hb.constant_genome(row)
        a, b = hb.lone(row).run(list(range(8))), hb.GrnOrganism("c", g).run(list(range(8)))
        assert np.array_equal(bits(a.ledger), bits(b.ledger)) and np.array_equal(a.hashes, b.hashes)
    w = spec.world(T=200.0)
    r = ref.run(w, genome=hb.constant_genome(hb.LONE_BEST), seed=5)
    k = kernel(w, [5], genome=hb.constant_genome(hb.LONE_BEST))
    assert mismatch(k, 0, r) == []
    with pytest.raises(ValueError):
        hb.constant_genome(hb.with_knobs(hb.LONE_BEST, sec0=0.1))


@pytest.mark.slow
def test_r25_genome_scores_like_the_program():
    """G9 in miniature on screen seeds: 64 lives at 37 cells, GRN within 3 combined SE of the program."""
    seeds = analysis.fresh_seeds(64, analysis.SCREEN_SEED0)
    p = analysis.summary(hb.R25_V1.run(seeds, cap=37, threads=4)["F"])
    g = analysis.summary(hb.R25_V1_GRN.run(seeds, cap=37, threads=4)["F"])
    assert abs(analysis.z_diff(g, p)) <= 3, (g, p)
