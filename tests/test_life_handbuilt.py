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
    assert g.dtype == np.float32 and g.size == spec.GENOME_SIZE == 793
    gt = hb.R25_V1_GRN.table("hex")[0]
    assert list(np.nonzero(spec.genome_view(gt, "act"))[0]) == [0, 1, 2, 3, 4]
    lam = spec.genome_view(gt, "lam")
    assert lam[hb.GENE_JUVENILE] == 1 / 16 and lam[hb.GENE_CONTACT] == lam[hb.GENE_GATE] == lam[hb.GENE_ECHO] == 0.5
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
    for gate in ("n_view", None):
        gt = spec.pack_genomes(hb.r25_genome(gate=gate)[None])[0]
        assert np.all(np.isfinite(gt))
    assert np.array_equal(hb.r25_genome(), hb.r25_genome(gate="n_view"))
    assert hb.R25_V1_GRN.genome.size == spec.GENOME_SIZE
    for gate in ("flank", "rim"):  # ABI 2: the gene network has no flank_best input (LIFE_ABI.md 15.32)
        with pytest.raises(ValueError):
            hb.r25_genome(gate=gate)
    # the gate opens at n_view >= D - 1: input n_view / D (the last GRN input) through W = 20 D, b = 30 - 20 D
    for D in (6, 8):
        W = spec.genome_view(hb.r25_genome(D=D), "W")
        b = spec.genome_view(hb.r25_genome(D=D), "b")
        assert np.count_nonzero(W[hb.GENE_GATE]) == 1 and W[hb.GENE_GATE, spec.NIN - 1] == 20.0 * D
        p = [b[hb.GENE_GATE] + W[hb.GENE_GATE, spec.NIN - 1] * n / D for n in range(D + 1)]
        assert [x > 0 for x in p] == [False] * (D - 1) + [True] * 2
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


# ------------------------------------------------------------------------------------------- BODY-1: CATCH bodies
V3 = spec.V3
K3, ROW3 = V3.K, V3.PROGRAM_ROW


def _row3(prog, name):
    i = ROW3[name]
    return prog[i * V3.P:(i + 1) * V3.P]


def test_catch_rows_are_the_prototype_rows():
    """common.rows_A of the prototype (cur.row defaults: b 0, tau_m 2, t_ref 1): sensor g_r 1 emitting on ch0, motor
    w0 1 kappa 1 t_ref 4, centre coincidence sensor g_r 0.55, and the cheats' tonic rows."""
    for row, want in ((hb.SENSE, dict(g_r=1.0, emit0=1, b=0, tau_m=2, t_ref=1, w0=0, kappa=0)),
                      (hb.MOTOR, dict(w0=1, kappa=1, t_ref=4, tau_m=2, b=0, emit0=0, g_r=0)),
                      (hb.CLICK_SENSE, dict(g_r=0.55, emit0=1, tau_m=2, t_ref=1, emit1=0)),
                      (hb.SENSE_HOLD, dict(g_r=1.0, emit0=1, w1=-1)), (hb.CLICK_HOLD, dict(g_r=0.55, emit0=1, emit1=1)),
                      (hb.TONIC_MOTOR, dict(b=1.2, tau_m=2, t_ref=2, kappa=1)),
                      (hb.PRESSER, dict(b=2.0, tau_m=2, t_ref=2, kappa=0.6)),
                      (hb.SPAM_DRIFTER, dict(b=2.0, tau_m=2, t_ref=0.5, kappa=1))):
        assert all(row[K3[k]] == v for k, v in want.items()), (row, want)
    assert hb.CLICK_SENSE_Q8[K3["g_r"]] == 0.5 and spec.q8(0.5) == 0.5 and spec.q8(0.55) != 0.55


def test_column_bodies_are_the_time_tests_bodies():
    from tests.life_helpers import COLUMN3, columns, hexdisk
    assert np.array_equal(hb.COLUMN_PROGRAM, COLUMN3)
    for k in range(4):
        assert sorted(hb.ring_body(k).cells) == sorted(columns(hexdisk(k)))
        assert sorted(hb.ring_body(k, hidden=2).cells) == sorted(columns(hexdisk(k), hidden=2))
    assert [len(hb.ring_body(k).cells) for k in range(7)] == [2, 14, 38, 74, 122, 182, 254]
    assert hb.ring_body(3, hidden=2).plane_counts() == (37, 37, 74)
    # the prototype's cur.hexdisk order: by ring, then by angle from -pi
    assert hb.disk(1) == [(0, 0), (0, -1), (1, -1), (1, 0), (0, 1), (-1, 1), (-1, 0)]
    assert len(hb.disk(3)) == 37 and [hb.hex_ring(*s) for s in hb.disk(2)] == [0] + [1] * 6 + [2] * 12
    cells = hb.ring_body(1).cells
    assert cells[0] == (0, 0, 0, ROW3["juvenile"]) and all(c[3] == ROW3["alone"] for c in cells[1:7])
    assert all(c[2] == 1 and c[3] == ROW3["contact"] for c in cells[7:])
    with pytest.raises(ValueError):
        hb.column_body([(1, 0)])


def test_column_ladders_and_cheats_have_the_registered_shapes():
    sizes = {o: [len(hb.ladder_body(o, m).cells) for m in range(7)] for o in hb.COLUMN_ORDERS}
    assert all(s == [2, 4, 6, 8, 10, 12, 14] for s in sizes.values())
    assert hb.ladder_body("adjacent", 6).cells == hb.ring_body(1).cells == hb.ladder_body("opposite", 6).cells
    assert hb.ladder_body("alternating", 5).cells == hb.ladder_body("adjacent", 5).cells  # the same five columns
    opp = {(a, b) for a, b, z, _ in hb.ladder_body("opposite", 2).cells if z == 0}
    assert opp == {(0, 0), (0, -1), (0, 1)}  # an opposite pair
    assert hb.ring1_plus(0).cells == hb.ring_body(1).cells and len(hb.ring1_plus(12).cells) == 38
    assert sorted(hb.ring1_plus(12).cells) == sorted(hb.ring_body(2).cells)
    isl = {(a, b) for a, b, z, _ in hb.islands().cells}
    assert len(hb.islands().cells) == 14 and all(hb.hex_ring(*s) in (0, 3) for s in isl)
    assert hb.BLIND_SPAM_RUNNER.flags == V3.flags("contacts_off") and len(hb.BLIND_SPAM_RUNNER.cells) == 3
    assert len(hb.runner_grid()) == 108 and len(hb.runner(1.1, 2.0, 1.0, 1.0, 1).cells) == 4
    drift = _row3(hb.runner(*hb.RUNNER_PROTOTYPE).program, "zygote")
    assert (drift[K3["b"]], drift[K3["t_ref"]], drift[K3["kappa"]]) == (1.1, 1.0, 1.0)
    assert _row3(hb.tonic_ring(2).program, "alone")[K3["g_r"]] == 0  # blind: the sensors have no receptor
    # review cheats (GB7): runners with 2 and 3 adjacent drifters, and the blind presser grid
    two, three = hb.runner(1.5, 8.0, 4.0, 1.0, drifters=2), hb.runner(1.5, 8.0, 4.0, 1.0, foot=1, drifters=3)
    assert len(two.cells) == 4 and len(three.cells) == 8 and len(hb.runner_grid(3)) == 108
    assert {(a, b) for a, b, z, _ in three.cells if z == 1} == {(0, 0), *hb.RUNNER_SITES}
    assert hb.runner(*hb.RUNNER_PROTOTYPE).cells == hb.runner(*hb.RUNNER_PROTOTYPE, drifters=1).cells
    assert len(hb.blind_presser_grid()) == 480 and all(b.cells == hb.BLIND_CLICKER.cells for b in
                                                        hb.blind_presser_grid()[:3])


def test_blind_genomes_never_sense_and_click_slowly():
    """Review cheats (GB6, GB7): grown from one zygote into 2 cells, no receptor event ever lands; the presser
    clicks with no message, the relay with one message per click."""
    for org, relayed in ((hb.BLIND_GRN, False), (hb.BLIND_RELAY_GRN, True)):
        res = org.run([5, 6], T=400.0)
        assert np.all(res["n_end"] == 2) and np.all(res["rec_events"] == 0) and np.all(res["clicks"] > 5)
        assert np.all(res["arrivals"] > 0) == relayed and np.all(res["n_M_end"] == 1)
    from tests.life_helpers import kernel3, mismatch, reference3
    w = hb.BLIND_RELAY_GRN.world(T=120.0)
    k = kernel3(w, [21], genome=hb.BLIND_RELAY_GRN.genome)
    assert mismatch(k, 0, reference3(w, 21, genome=hb.BLIND_RELAY_GRN.genome)) == []


def test_catch_bodies_live_cleanly():
    bad = spec.STATUS["capacity"] | spec.STATUS["ledger_mismatch"] | spec.STATUS["guard_cells"] | spec.STATUS["wall"]
    for name, org in hb.CATCH_BODIES.items():
        res = org.run([1, 2], T=200.0)
        assert not np.any(res["status"].astype(np.int64) & bad), name
        assert np.all(res["n_end"] == len(org.cells)) and np.all(res["births"] == 0), name
        if org.flags & V3.flags("contacts_off"):
            assert np.all(res["arrivals"] == 0), name
    # blind bodies never sense; every click of the blind clicker is a miss or a lucky capture
    res = hb.BLIND_CLICKER.run([3, 4], T=200.0)
    assert np.all(res["rec_events"] == 0) and np.all(res["clicks"] > 30)


def test_silent_hidden_cells_cost_exactly_c_live():
    """Proposal 4.1: a silent hidden cell receives nothing (motors do not emit) and changes no other cell's draws."""
    seeds = [11, 12, 13]
    base = hb.ring_body(1).run(seeds)
    for h in (1, 2):
        res = hb.ring_body(1, hidden=h).run(seeds)
        assert np.allclose(res["F"], base["F"] - spec.COSTS["c_live"] * 7 * h, rtol=0, atol=1e-12)
        assert np.array_equal(res["captures"], base["captures"]) and np.array_equal(res["path"], base["path"])


def test_column_genome_decodes_the_program_rows_in_every_settled_state():
    states = hb.column_genome_states()
    assert all(not v["mismatches"] for v in states.values()), states
    assert {k: v["p_div"] for k, v in states.items()} == dict(sense_fresh=0.5, sense=0.0, sense_growing=0.5, zygote=0.5,
                                                              motor=0.0, motor_fresh=0.0, act_newborn=0.0,
                                                              sense_newborn=0.0)
    g = hb.column_genome(1)
    assert g.dtype == np.float32 and g.size == V3.GENOME_SIZE == 875
    assert list(np.nonzero(V3.genome_view(g, "act"))[0]) == [0, 1, 2, 3, 4]
    assert list(np.nonzero(V3.genome_view(hb.column_genome(1, window=0.16), "act"))[0]) == [0, 1, 2, 3, 4, 5, 6]
    assert np.count_nonzero(hb.column_genome(0) != hb.column_genome(1)) == 3  # a0 and the kin weight of p_div, s0
    for bad in (dict(rings=2), dict(click_g_r=0.55), dict(window=0.5)):
        with pytest.raises(ValueError):
            hb.column_genome(**bad)


@pytest.mark.parametrize("rings", [0, 1])
def test_column_genome_grows_its_ring_exactly(rings):
    want = sorted((a, b, z) for a, b, z, _ in hb.ring_body(rings).cells)
    org = (hb.COLUMN_GRN_RING0, hb.COLUMN_GRN_RING1)[rings]
    res = org.run(list(range(8)), T=160.0, fate_cap=256, threads=4)
    for i in range(8):
        assert sorted(analysis.final_cells(res.fates(i)[0])) == want, i
    assert np.all(res["rejects"] == 0) and np.all(res["claims"] == len(want) - 1) and np.all(res["n_H_end"] == 0)


def test_column_genome_lives_match_the_reference_bitwise():
    from tests.life_helpers import kernel3, mismatch, reference3
    for org in (hb.COLUMN_GRN_RING1, hb.column_grower(0.1)):
        w = org.world(T=120.0)
        k = kernel3(w, [21], genome=org.genome)
        assert k["n_end"][0] >= 14 and k["captures"][0] + k["misses"][0] > 0
        assert mismatch(k, 0, reference3(w, 21, genome=org.genome)) == [], org.name


def test_hand_bodies_live_as_the_reference():
    from tests.life_helpers import kernel3, mismatch, reference3
    for org in (hb.hold_body(1), hb.runner(*hb.RUNNER_PROTOTYPE), hb.BLIND_SPAM_RUNNER, hb.islands(),
                hb.runner(1.5, 8.0, 4.0, 1.0, drifters=2), hb.blind_presser(1.5, 16.0, 2.0, 1.0)):
        w = org.world(T=128.0)
        k = kernel3(w, [31], program=org.program, init=list(org.cells))
        assert mismatch(k, 0, reference3(w, 31, program=org.program, init=list(org.cells))) == [], org.name
