"""Gates G1-G10 and S8 (docs/ONE_LIFE_DESIGN.md, PRE-REGISTERED GATES; docs/LIFE_GATES.md), pinned to
outputs/life_gates/gates.json. Lives are deterministic given their seeds and independent of the thread count, so
each test recomputes a cheap part of its gate and, when gates.json was written by the kernel library in use, asserts
the stored numbers exactly. Every test also re-judges the stored gate and checks the stored verdicts."""
import copy
import json
from pathlib import Path

import numpy as np
import pytest

from scripts import life_gates as lg
from src.life import analysis, build, spec
from src.life import handbuilt as hb

pytestmark = pytest.mark.slow

GATES_JSON = Path(__file__).resolve().parents[1] / "outputs" / "life_gates" / "gates.json"
PASSING = ("G1", "G2", "G3", "G4", "G5", "G6", "G7", "G8", "G9", "S8")  # pass in the stored run (G10 fails: D4)


def _roundtrip(x):
    return json.loads(json.dumps(lg._jsonable(x)))


def _stored(name: str):
    """The stored gate, or None when gates.json is missing or was written by another kernel library."""
    if not GATES_JSON.exists():
        return None
    data = json.loads(GATES_JSON.read_text())
    if data["meta"]["kernel"] != build.library_path().name:
        return None
    return data["gates"].get(name)


def _same(value, stored) -> None:
    assert _roundtrip(value) == stored


def _rejudge(name: str, stored: dict) -> None:
    """Re-applying the gate's criteria to its stored measurements gives the stored checks and verdict."""
    if name not in lg.JUDGES:
        return
    g = lg.JUDGES[name](copy.deepcopy(stored))
    assert g["checks"] == stored["checks"] and g["passed"] == stored["passed"], (g["checks"], stored["checks"])
    if name in PASSING:
        assert stored["passed"], (name, stored["checks"])


def test_gates_json_is_complete_and_its_verdicts_follow_from_its_numbers():
    if not GATES_JSON.exists():
        pytest.skip("gates.json not written yet")
    data = json.loads(GATES_JSON.read_text())
    assert set(data["gates"]) == set(lg.GATES)
    assert data["meta"]["fresh_seed0"] == analysis.FRESH_SEED0 and data["meta"]["threads"] <= 4
    for name, g in data["gates"].items():
        assert "registered" in g and "criteria" in g and set(g) >= {"checks", "passed"}, name
        _rejudge(name, g)
    assert data["passed"] == all(g["passed"] for g in data["gates"].values())


def test_g1_best_lone_cell_registration_screen_and_fresh_lives():
    g = lg.gate_g1(threads=4)
    assert g["passed"], g["checks"]
    assert g["best"]["phenotype"] == dict(b=1.625, tau_m=4.0, t_ref=4.0, kappa=1.0)  # flat top, same as the prototype
    pump = g["registered_phenotype"]
    assert abs(pump["F"] - 0.0326) < 5e-5 and pump["F"] > 0.99 * g["best"]["F"] and pump["rank"] <= 10
    rr = g["reregistered"]
    assert rr["lives"] >= 144 and abs(rr["best"]["F"] - 0.0326) < 0.02 * 0.0326
    assert 53.0 < rr["income_rate_best_e3"] <= rr["income_rate_max_life_e3"] < 55.0
    stored = _stored("G1")
    if stored is not None:
        for k in ("best", "registered_phenotype", "top", "inert", "port", "reregistered", "checks"):
            _same(g[k], stored[k])
        _rejudge("G1", stored)


def test_g2_messages_off_bodies_never_beat_a_lone_cell():
    cand = lg.g2_candidates()
    pts = lg.points(lg.curve(hb.L0, (2, 3, 7, 19), lg.LIVES))
    lone = lg.lone_reference()["F"]
    assert all(p["mean"] < lone for p in pts.values())
    assert pts[19]["income_per_cell_e3"] < lg.G2_ZERO_INCOME_E3
    stored = _stored("G2")
    if stored is not None:
        _same([o for o in cand["chosen"]], stored["screen"]["chosen"])
        for N, p in pts.items():
            _same(p, stored["bodies"][hb.L0.name][str(N)])
        assert all(v["mean"] <= stored["lone"]["F"] for v in stored["best_by_N"].values())
        _rejudge("G2", stored)


def test_g3_r25_v1_curve_is_reregistered_on_fresh_lives():
    pts = lg.points(lg.curve(hb.R25_V1, (37, 91, 169), lg.LIVES_R25))
    assert pts[37]["mean"] < pts[91]["mean"] and pts[169]["mean"] < pts[91]["mean"]
    assert pts[91]["mean"] < 0.928 - 2 * pts[91]["se"]  # the registered +0.928 was a high draw
    stored = _stored("G3")
    if stored is not None:
        for N, p in pts.items():
            rec = {k: v for k, v in stored["reregistered"]["curve"][str(N)].items() if k != "z_vs_registered"}
            _same(p, rec)
        rr = stored["reregistered"]
        assert rr["lives"] >= 144 and 37 <= rr["n_star"] <= 169 and rr["n_star"] in rr["flat_top"]
        _rejudge("G3", stored)


def test_g3_port_check_against_the_remeasured_prototype():
    """R25-v1/bell3 (the prototype's exact rule) on 144 of the port-check lives, within 2 SE of bell3.c with the
    kernel's Irwin-Hall normals (the pooled 4608-life reference); the stored check uses that reference too."""
    assert lg.G3_PORT_Z == lg.Z == 2.0 and lg.PROTOTYPE["G3_port"]["lives"] >= 3000
    ref = lg.PROTOTYPE["G3_port"]
    c = analysis.size_curve(hb.R25_V1_BELL3, lg.G3_SIZES, lives=144, seed0=lg.PROTOTYPE["G3"]["seed0"], threads=4)
    for N in lg.G3_SIZES:
        e = lg._curve_entry(c[N], ref["curve"][N], lg.G3_PORT_Z, ref["resolution"])
        assert e["ok"], (N, e)
    stored = _stored("G3")
    if stored is not None:
        pc = stored["port_check"]
        assert pc["prototype_lives"] == ref["lives"] and pc["ok"]
        for N in lg.G3_SIZES:
            assert pc["points"][str(N)]["reference"]["mean"] == ref["curve"][N][0]


def test_g4_ablation_ladder_points_are_pinned():
    stored = _stored("G4")
    for org in (hb.R25_NO_LBT, hb.L3):
        N = stored["organisms"][org.name]["n_star"] if stored else 61
        p = lg.points(lg.curve(org, (N,), lg.LIVES))[N]
        assert p["mean"] > 0.3
        if stored is not None:
            _same(p, stored["organisms"][org.name]["curve"][str(N)])
    if stored is not None:
        assert [r["pair"].split(" > ")[0] for r in stored["chain"]] == [o.name for o in lg.CHAIN[:-1]]
        _rejudge("G4", stored)


def test_g5_frozen_heterogeneity_sets_the_size_bound():
    nf = lg.points(lg.curve(hb.R25_V1, (91, 547), lg.LIVES_G5, **lg.g5_world("no_frozen")))
    assert nf[547]["mean"] > nf[91]["mean"] > 1.0
    stored = _stored("G5")
    if stored is not None:
        for N, p in nf.items():
            _same(p, stored["conditions"]["no_frozen"]["curve"][str(N)])
        assert stored["checks"]["no_frozen_unbounded"] and stored["checks"]["default_bounded"]
        _rejudge("G5", stored)


def test_g6_spikes_undelivered_from_half_life_collapse_income():
    g = lg.gate_g6(threads=4)
    assert g["passed"], g["checks"]
    assert g["organisms"]["R25-v1"]["fork"]["income_per_cell_e3"] < 3.0 < 25.0 < \
        g["organisms"]["R25-v1"]["twin"]["income_per_cell_e3"]
    stored = _stored("G6")
    if stored is not None:
        _same(g["organisms"], stored["organisms"])
        _rejudge("G6", stored)


def test_g7_income_per_cell_stays_below_the_lone_rate():
    ref = lg.lone_reference()
    pts = lg.points(lg.curve(hb.B, (37, 91), lg.LIVES_G5))
    assert all(p["income_per_cell_max_e3"] < 1e3 * ref["rate_max_life"] for p in pts.values())
    stored = _stored("G7")
    if stored is not None:
        _same(1e3 * ref["rate_max_life"], stored["lone"]["rate_max_life_e3"])
        assert stored["lives"] > 30_000 and stored["body_max_e3"] <= stored["lone"]["rate_max_life_e3"]
        _rejudge("G7", stored)


def test_g8_closed_form_lumen_matches_euler_and_lives_are_bitwise_invariant(tmp_path):
    out = tmp_path / "gates.json"
    assert lg.main(["--gates", "G8", "--threads", "4", "--out", str(out)]) == 0
    data = json.loads(out.read_text())
    g = data["gates"]["G8"]
    assert data["passed"] and g["passed"], g["checks"]
    assert g["max_abs_rel_err"] < 1e-3
    assert {x["cells"] for x in g["lives"]} == {1, 37, 91}
    assert all(0.3 <= x["halving_ratio"] <= 0.7 for x in g["lives"])
    stored = _stored("G8")
    if stored is not None:
        for k in ("lives", "window", "checks", "max_abs_rel_err"):
            assert g[k] == stored[k], k


def test_g9_r25_v1_genome_matches_the_program_at_91_cells():
    prog = lg.lives(hb.R25_V1, 91, lg.LIVES_R25)
    grn = lg.lives(hb.R25_V1_GRN, 91, lg.LIVES_R25)
    p, q = analysis.point(prog), analysis.point(grn)
    assert abs(analysis.z_diff(q, p)) <= lg.Z, (p, q)
    assert all(not v["mismatches"] for v in hb.r25_genome_states().values())
    stored = _stored("G9")
    if stored is not None:
        _same(q, stored["points"]["91"]["grn"])
        _same(p, stored["points"]["91"]["program"])
        assert stored["genome"]["slots"] == spec.GENOME_SIZE == 793 and stored["genome"]["genes"]["2"] == "rim gate"
        assert stored["abi1"]["gate"] == "flank_best = 2"  # the ABI-1 genome's numbers are kept for the record
        _rejudge("G9", stored)


def test_g10_d4_d5_and_the_grn_layer_are_pinned():
    stored = _stored("G10")
    grn = lg.d4_grn()
    assert list(grn) == ["n_view gate, flank placement", "n_view gate, random placement"]
    assert grn["n_view gate, flank placement"] is hb.R25_V1_GRN
    nv = grn["n_view gate, random placement"]
    p = lg.points(lg.curve(nv, (91,), lg.LIVES))[91]
    sweep2 = analysis.point(lg.lives(lg.tref_sweep()[2.0], 91, lg.LIVES))
    if stored is not None:
        _same(p, stored["d4_grn"]["rows"]["n_view gate, random placement"]["curve"]["91"])
        _same(sweep2, stored["d5"]["t_ref_sweep_91"]["2.0"])
        assert stored["grn_layer"]["lone_grn_bitwise_program"]
        _rejudge("G10", stored)


def test_abi2_grn_genomes_live_as_their_abi1_twins():
    """ABI 2 dropped the flank_best input (LIFE_ABI.md 15.32). R25-v1's genome now gates on n_view; it and its
    random-placement variant had zero flank weights under ABI 1 too, so on the same 144 fresh lives they reproduce
    the F* that G10 measured for them under ABI 1 (stored in ``life_gates.ABI1`` to 6 decimals)."""
    rec = lg.ABI1["G10"]["d4_grn"]
    for name, org in lg.d4_grn().items():
        F, se, n_star, _ = rec[name]
        p = lg.points(lg.curve(org, (n_star,), lg.LIVES))[n_star]
        assert abs(p["mean"] - F) < 1e-6 and abs(p["se"] - se) < 1e-6, (name, p["mean"], F)


def test_s8_square8_size_curve_is_measured_and_bounded():
    stored = _stored("S8")
    N = stored["r25_v1"]["n_star"] if stored else 81
    p = lg.points(lg.curve(hb.R25_V1, (N,), lg.LIVES, **lg.S8))[N]
    assert p["mean"] > 0.5
    if stored is not None:
        _same(p, stored["r25_v1"]["curve"][str(N)])
        _rejudge("S8", stored)


def test_square8_n_view_gate_against_the_abi1_flank_gate():
    """Review of ABI 2: G10 found the n_view gate as good as the removed flank_best gate on hex, but on square8 R25-v1's
    n_view-gated genome is lower at every size (results/flank_square8/). The ABI-1 side cannot be built any more, so
    its per-life F is stored; the ABI-2 side is re-measured at 81 cells (288 lives) and must match bitwise."""
    z = np.load(Path(__file__).resolve().parents[1] / "results" / "flank_square8" / "pair.npz")
    org = hb.GrnOrganism("R25-v1 genome, square8", hb.r25_genome(D=8))
    assert np.array_equal(lg.lives(org, 81, 288, lattice="square8")["F"], z["abi2/grn/81"])
    assert np.array_equal(z["abi1/prog/81"], z["abi2/prog/81"])  # the same lives in both trees
    diff = {}
    for N in (49, 81, 121, 169):
        d = z[f"abi2/grn/{N}"] - z[f"abi1/grn/{N}"]
        se = d.std(ddof=1) / np.sqrt(d.size)
        diff[N] = (round(float(d.mean()), 3), round(float(d.mean() / se), 1))
    assert diff == {49: (-0.013, -1.3), 81: (-0.051, -2.5), 121: (-0.081, -1.6), 169: (-0.165, -2.5)}
    f_star = [max(float(z[f"{abi}/grn/{N}"].mean()) for N in (49, 81, 121, 169)) for abi in ("abi1", "abi2")]
    assert [round(f, 3) for f in f_star] == [1.096, 1.015]
    for N in (61, 91, 127):  # on hex the two gates are equal (G10): |z| < 1
        d = z[f"abi2/grn_hex/{N}"] - z[f"abi1/grn_hex/{N}"]
        assert abs(d.mean()) < d.std(ddof=1) / np.sqrt(d.size)


# ---------------------------------------------------------------------------------------- BODY-1: the CATCH gates
CATCH_JSON = GATES_JSON.with_name("gates_catch.json")
CATCH_PASSING = ("GB3", "GB4", "GB5", "GB6", "GB7", "GB8", "GB9", "GB12", "GB13")  # pass in the stored run
L3 = spec.V3.L


def _stored_catch(name: str):
    """The stored CATCH gate, or None when gates_catch.json is missing or was written by another kernel library."""
    if not CATCH_JSON.exists():
        return None
    data = json.loads(CATCH_JSON.read_text())
    if data["meta"]["kernel"] != build.library_path().name:
        return None
    return data["gates"].get(name)


def _rejudge_catch(name: str, stored: dict) -> None:
    g = lg.CATCH_JUDGES[name](copy.deepcopy(stored))
    assert g["checks"] == stored["checks"] and g["passed"] == stored["passed"], (g["checks"], stored["checks"])
    if name in CATCH_PASSING:
        assert stored["passed"], (name, stored["checks"])


def test_catch_gates_json_is_complete_and_its_verdicts_follow_from_its_numbers():
    if not CATCH_JSON.exists():
        pytest.skip("gates_catch.json not written yet")
    data = json.loads(CATCH_JSON.read_text())
    assert set(data["gates"]) == set(lg.CATCH_GATES) and data["meta"]["world"] == "catch"
    assert data["meta"]["fresh_seed0"] == lg.CATCH_FRESH_SEED0 and data["meta"]["threads"] <= 4
    assert data["meta"]["abi"] == spec.V3.version
    for name, g in data["gates"].items():
        assert {"registered", "criteria", "checks", "passed"} <= set(g), name
        _rejudge_catch(name, g)
    assert data["passed"] == all(g["passed"] for g in data["gates"].values())


def test_catch_seed_ranges_are_disjoint():
    ranges = [lg.CATCH_FRESH_SEED0, lg.CATCH_SCREEN_SEED0, lg.CATCH_EXPLORE_SEED0, analysis.FRESH_SEED0,
              analysis.SCREEN_SEED0]
    assert len(set(r // 1_000_000 for r in ranges)) == len(ranges)
    assert lg.C_LIVES_SMALL >= 2048 and lg.C_LIVES >= 512 and lg.CATCH_PRESET == "catch_v1"


def test_gb3_the_clicker_beats_the_lone_zygote():
    g = lg.gate_gb3(threads=4)
    assert g["passed"], g["checks"]
    assert g["lone"]["income_rate"] == 0.0 and -0.021 < g["lone"]["mean"] < -0.020
    stored = _stored_catch("GB3")
    if stored is not None:
        for k in ("lone", "clicker", "step", "checks"):
            _same(g[k], stored[k])
        _rejudge_catch("GB3", stored)


def test_gb4_ring_curve_points_are_pinned():
    pts = {k: lg.cpoint(hb.ring_body(k), lg._n_for(hb.ring_body(k)), proto=f"ring{k}") for k in (0, 1, 3)}
    assert pts[0]["mean"] < pts[1]["mean"] < pts[3]["mean"] and pts[3]["mean"] > 20 * pts[0]["mean"]
    assert all(abs(p["z_prototype"]) <= lg.Z_PORT for p in pts.values())
    stored = _stored_catch("GB4")
    if stored is not None:
        for k, p in pts.items():
            _same(dict(p, cells=len(hb.ring_body(k).cells)), stored["rings"][str(k)])
        assert stored["best"]["n_star"] in (3, 4) and not stored["best"]["edge"]
        _rejudge_catch("GB4", stored)


def test_gb5_column_ladder_points_are_pinned():
    bodies = [hb.ladder_body("adjacent", m) for m in range(4)]
    steps = [lg._step(a, b, lg.C_LIVES_SMALL) for a, b in zip(bodies, bodies[1:])]
    assert all(s["z"] > 2 for s in steps), steps
    stored = _stored_catch("GB5")
    if stored is not None:
        for m in (1, 2, 3):
            _same(steps[m - 1], stored["orders"]["adjacent"]["steps"][f"{m - 1}->{m}"])
        _rejudge_catch("GB5", stored)


def test_gb6_the_wire_certificate_removes_second_half_income():
    org = hb.ring_body(1)
    row = lg._gb6_row(org, lg.C_LIVES_FORK)
    assert row["removed"] >= lg.GB6_REMOVED and row["removed_sense"] >= lg.GB6_REMOVED
    # review fix: a blind relay clicker passes the certificate alone; receptor_off shows it senses nothing
    blind = lg._gb6_row(hb.BLIND_RELAY_GRN, 64)
    assert blind["removed"] >= lg.GB6_REMOVED and blind["removed_sense"] < 0.05
    stored = _stored_catch("GB6")
    if stored is not None:
        _same(float(row["removed"]), stored["organisms"][org.name]["removed"])
        _same(float(row["removed_sense"]), stored["organisms"][org.name]["removed_sense"])
        _rejudge_catch("GB6", stored)


def test_gb7_cheats_lose():
    n = lg.C_LIVES_SMALL
    for cheat, ref in ((hb.BLIND_SPAM_RUNNER, hb.CLICKER), (hb.islands(), hb.ring_body(1))):
        s = lg._step(ref, cheat, n)
        assert s["z"] < -lg.Z, (cheat.name, s)
    # review fixes: slow blind clickers (a presser, or a tonic zygote relaying to a motor) lose to the lone zygote at
    # c_miss 2, and a clicker with two footless tonic drifters stays below the 4-cell column once their columns drag
    for cheat in (hb.BLIND_GRN, hb.BLIND_RELAY_GRN, hb.blind_presser(1.5, 16.0, 2.0, 1.0)):
        s = lg._step(hb.ZYGOTE, cheat, n)
        assert s["z"] < -lg.Z, (cheat.name, s)
    s = lg._step(hb.ladder_body("adjacent", 1), hb.runner(1.5, 8.0, 4.0, 1.0, drifters=2), n)
    assert s["z"] < lg.Z, s
    co = lg.clives(hb.ring_body(2), 128, flags=spec.V3.flags("contacts_off"))
    assert np.all(co[:, L3["income"]] == 0) and np.all(co[:, L3["clicks"]] == 0)
    stored = _stored_catch("GB7")
    if stored is not None:
        _same(lg._step(hb.CLICKER, hb.BLIND_SPAM_RUNNER, n), stored["cheats"]["blind_spam_runner"]["vs"])
        assert [stored["runner_screen"][d]["screened"] for d in ("1", "2", "3")] == [108] * 3
        assert stored["blind_screen"]["screened"] == len(hb.blind_presser_grid())
        _rejudge_catch("GB7", stored)


def test_gb8_the_centre_hold_pays_at_ring_1():
    n = lg._n_for(hb.ring_body(1))
    gain = lg._step(hb.ring_body(1), hb.hold_body(1), n)
    assert gain["z"] > lg.Z and 0.3 < gain["mean"] < 0.6
    stored = _stored_catch("GB8")
    if stored is not None:
        _same(gain, stored["rings"]["1"]["gain"])
        _rejudge_catch("GB8", stored)


def test_gb9_the_column_genome_grows_and_expresses_the_reflex():
    assert all(not v["mismatches"] for v in hb.column_genome_states().values())
    stored = _stored_catch("GB9")
    res, bodies = lg._grown(hb.COLUMN_GRN_RING1, 64)
    want = sorted((a, b, z) for a, b, z, _ in hb.ring_body(1).cells)
    assert all(sorted(b) == want for b in bodies) and res["rejects"].sum() == 0
    if stored is not None:
        assert all(v["exact"] == v["lives"] for v in stored["growth"].values())
        _same(lg.cpoint(hb.COLUMN_GRN_RING1, lg.C_LIVES_FORK, t_open=lg.GB9_T_OPEN), stored["after_growth"]["1"]["grn"])
        _rejudge_catch("GB9", stored)


def test_gb12_v1_sits_inside_the_good_start_region():
    b = lg.gb12_bodies()
    for a, c in (("lone", "ring0"), ("ring0", "adjacent_1"), ("adjacent_1", "adjacent_2")):
        s = lg._step(b[a], b[c], lg.C_LIVES_SMALL)
        assert s["z"] > lg.Z, (a, c, s)
    slow = lg.cpoint(hb.CLICKER, lg.C_LIVES_SMALL, proto="v_t_0.05/ring0", v_t=0.05)
    assert slow["mean"] < 2 * slow["se"]  # the clicker earns nothing when the target is slow (proposal 3.5)
    stored = _stored_catch("GB12")
    if stored is not None:
        _same(slow, stored["worlds"]["v_t_0.05"]["points"]["ring0"])
        _rejudge_catch("GB12", stored)


def test_gb13_hidden_planes_cost_exactly_c_live():
    g = lg.gate_gb13(threads=4)
    assert g["passed"], g["checks"]
    stored = _stored_catch("GB13")
    if stored is not None:
        _same(g["silent_hidden"], stored["silent_hidden"])
        _same(g["planes"], stored["planes"])
        _rejudge_catch("GB13", stored)


def test_main_runs_a_catch_gate(tmp_path):
    out = tmp_path / "c.json"
    assert lg.main(["--world", "catch", "--gates", "gb3", "--threads", "4", "--out", str(out)]) == 0
    data = json.loads(out.read_text())
    assert data["meta"]["world"] == "catch" and set(data["gates"]) == {"GB3"} and data["passed"]
    with pytest.raises(SystemExit):
        lg.main(["--world", "catch", "--gates", "G1", "--out", str(out)])


# ----------------------------------------------------------------------------- SPECK (S1 candidate): GS1-GS5
SPECK_JSON = GATES_JSON.with_name("gates_speck.json")
SPECK_TUNE_DIR = GATES_JSON.parent / "speck_tune"
SPECK_PASSING = ("GS1", "GS2", "GS3", "GS4", "GS5")  # pass in the stored run (GS6 fails: blind clicking pays)


def _stored_speck(name: str):
    """The stored SPECK gate, or None when gates_speck.json is missing or was written by another kernel library."""
    if not SPECK_JSON.exists():
        return None
    data = json.loads(SPECK_JSON.read_text())
    if data["meta"]["kernel"] != build.library_path().name:
        return None
    return data["gates"].get(name)


def _rejudge_speck(name: str, stored: dict) -> None:
    g = lg.SPECK_JUDGES[name](copy.deepcopy(stored))
    assert g["checks"] == stored["checks"] and g["passed"] == stored["passed"], (g["checks"], stored["checks"])
    assert g.get("reported_checks") == stored.get("reported_checks"), name  # reported, outside the verdict
    if name in SPECK_PASSING:
        assert stored["passed"], (name, stored["checks"])


def test_speck_gates_json_is_complete_and_its_verdicts_follow_from_its_numbers():
    if not SPECK_JSON.exists():
        pytest.skip("gates_speck.json not written yet")
    data = json.loads(SPECK_JSON.read_text())
    assert set(data["gates"]) == set(lg.SPECK_GATES) and data["meta"]["world"] == "speck"
    assert data["meta"]["fresh_seed0"] == lg.SPECK_FRESH_SEED0 and data["meta"]["threads"] <= 4
    assert data["meta"]["abi"] == spec.V3.version
    for name, g in data["gates"].items():
        assert {"registered", "criteria", "checks", "passed"} <= set(g), name
        _rejudge_speck(name, g)
    assert data["passed"] == all(g["passed"] for g in data["gates"].values())
    # the stored GS2 measured the knobs frozen in handbuilt
    assert data["gates"]["GS2"]["tuning"]["knobs"] == _roundtrip(hb.SPECK_TUNED)


def test_speck_seed_ranges_are_disjoint_and_the_tuned_bodies_are_frozen():
    ranges = [lg.SPECK_FRESH_SEED0, lg.SPECK_SCREEN_SEED0, lg.SPECK_HILL_SEED0, lg.CATCH_FRESH_SEED0,
              lg.CATCH_SCREEN_SEED0, lg.CATCH_EXPLORE_SEED0, analysis.FRESH_SEED0, analysis.SCREEN_SEED0]
    assert len(set(r // 1_000_000 for r in ranges)) == len(ranges)
    assert lg.S_LIVES >= 768 and lg.S_LIVES_PATH >= 768 and lg.SPECK_PRESET == "catch_speck"
    assert set(hb.SPECK_TUNED) == set(lg.SPECK_REFLEXES) | {lg.SPECK_ROUTER} | set(lg.SPECK_SIZE_CHECK)
    for name, knobs in hb.SPECK_TUNED.items():
        family = name.partition("@")[0]
        grid = lg.speck_family(family)[0]
        assert set(knobs) == set(grid) and hb.on_kernel_grid(knobs), name
        path = SPECK_TUNE_DIR / f"{name}.json"
        if path.exists():  # the tune's own output, when this tree has it
            rec = json.loads(path.read_text())
            assert rec["knobs"] == _roundtrip(knobs) and rec["F"] == hb.SPECK_TUNE_RECORD[name]["hill_F"], name


def test_speck_tune_is_reproducible():
    cfg = dict(n_rand=3, budget=6, screen_lives=4, hill_lives=4, top=2)
    a = lg.speck_tune("reflex", "ring2", threads=4, log=None, **cfg)
    b = lg.speck_tune("reflex", "ring2", threads=4, log=None, **cfg)
    assert a["knobs"] == b["knobs"] and a["trace"] == b["trace"] and a["hill_evaluations"] <= 6
    with pytest.raises(ValueError):
        lg.speck_family("polarised")


def test_gs1_the_s0_champion_earns_in_speck():
    g = lg.gate_gs1(threads=4)
    assert g["passed"], g["checks"]
    stored = _stored_speck("GS1")
    if stored is not None:
        for k in ("champion", "lone", "vs_lone", "checks"):
            _same(g[k], stored[k])
        _rejudge_speck("GS1", stored)


def test_gs2_the_router_beats_the_best_tuned_reflex():
    stored = _stored_speck("GS2")
    best = stored["best_reflex"] if stored is not None else "reflex@hollow3"
    router, reflex = hb.speck_body(lg.SPECK_ROUTER), hb.speck_body(best)
    d = analysis.paired(lg.sF(router, lg.S_LIVES), lg.sF(reflex, lg.S_LIVES))
    assert d["z"] > lg.Z_GS2, d
    if stored is not None:
        _same(d, stored["router_minus"][best])
        _same(lg.spoint(router, lg.S_LIVES), stored["points"][lg.SPECK_ROUTER])
        _rejudge_speck("GS2", stored)


def test_gs3_the_growth_path_starts_from_the_reflex():
    n = lg.S_LIVES_PATH
    start = hb.role_body(lg.path_knobs(0.0), "ring3+0", "path k0 g0.0")
    deaf = analysis.paired(lg.sF(start, n), lg.sF(hb.speck_body("reflex@ring3"), n))
    # at gain 0 the routing knobs are silent: the start lives bitwise as the reflex with deaf interior sensors
    silent = dict(hb.SPECK_TUNED["reflex@ring3"], **hb.REFLEX_FIXED, **{"J.g_r": 0.0})
    a, b = lg.slives(start, 64), lg.slives(hb.role_body(silent, "ring3"), 64)
    assert np.array_equal(a.view(np.uint64), b.view(np.uint64))
    stored = _stored_speck("GS3")
    if stored is not None:
        _same(deaf, stored["start_vs_reflex3"])
        _rejudge_speck("GS3", stored)


def test_gs3_reports_the_path_from_the_best_reflex():
    """Review 2026-10-08: the registered path starts at the ring-3 reflex with deaf interior sensors, which is below
    the best tuned reflex (the sense-hollow ring 3, GS2). GS3 reports that start and path against the best reflex,
    and the same grid with the best reflex's knobs starting at it (row 0: its shape with the routing knobs set,
    silent without interior sensors). The two reported rules are outside the verdict."""
    n = lg.S_LIVES_PATH
    stored = _stored_speck("GS3")
    best = stored["path_from_best_reflex"]["best_reflex"] if stored is not None else "reflex@hollow3"
    base = lg.path_knobs(0.25, best)
    assert all(base[k] == v for k, v in hb.SPECK_TUNED[best].items()) and base["J.g_r"] == 0.25
    assert lg.path_knobs(0.25)["S.tau_m"] == hb.SPECK_TUNED["reflex@ring3"]["S.tau_m"]
    start = hb.role_body(lg.path_knobs(0.0), "ring3+0", "path k0 g0.0")
    d = analysis.paired(lg.sF(start, n), lg.sF(hb.speck_body(best), n))
    if stored is not None:
        fb = stored["path_from_best_reflex"]
        _same(d, fb["start_vs_best_reflex"])
        assert fb["row0_lives_as_best_reflex"] and fb["first_fill_cells"] == 18
        assert fb["path"][0]["columns"] is None and fb["path"][0]["vs_start"]["mean"] == 0.0
        assert set(stored["reported_checks"]) == {"registered_start_not_below_best_reflex",
                                                  "path_uphill_from_best_reflex"}
        _rejudge_speck("GS3", stored)


def test_gs4_lateral_off_removes_the_routers_gain():
    g = lg.gate_gs4(threads=4)
    assert g["passed"], g["checks"]
    stored = _stored_speck("GS4")
    if stored is not None:
        for k in ("gain", "removed", "router_lateral_off", "checks"):
            _same(g[k], stored[k])
        _rejudge_speck("GS4", stored)


def test_gs5_the_router_genome_grows_columns_with_the_routers_roles():
    knobs = lg._router_knobs()
    assert all(not v["mismatches"] for v in hb.router_genome_states(hb.router_genome(knobs), knobs).values())
    stored = _stored_speck("GS5")
    win = stored["window"] if stored is not None else 0.2
    res, bodies = lg._grown(lg.router_grn(win), 16, seed0=lg.SPECK_FRESH_SEED0, preset=lg.SPECK_PRESET,
                            t_open=lg.GS5_T_OPEN)
    assert all(lg._columns_ok(b) for b in bodies) and np.all(res["n_H_end"] == 0)
    assert res["last_birth"].max() < lg.GS5_T_OPEN and res["n_end"].min() > 60
    if stored is not None:
        _rejudge_speck("GS5", stored)


def test_gs6_blind_clicking_paid_at_c_miss_2_and_loses_at_the_presets_10():
    """Rule N10 failed in SPECK at catch_v1's c_miss 2: with R_cap 500 a blind click breaks even at a 0.4% capture
    rate, so a slow blind presser beat the lone zygote (but not the sensing clicker). The SPECK presets price a miss at
    10, v1's break-even rate (LIFE_ABI.md 15.62), where it loses and GS6 passes. A price changes no life, so both come
    from the same lives."""
    n = lg.GS6_LIVES
    presser = hb.blind_presser(2.0, 16.0, 2.0, 1.0)
    at2, at10 = lg._sstep(hb.ZYGOTE, presser, n, 2.0), lg._sstep(hb.ZYGOTE, presser, n)
    assert at2["z"] > lg.Z and at10["z"] < -lg.Z and lg._sstep(hb.CLICKER, presser, n)["z"] < -lg.Z
    assert at10 == lg._sstep(hb.ZYGOTE, presser, n, lg.C_MISS_V1_RATIO)  # the preset's price is v1's ratio
    assert lg.C_MISS_V1_RATIO / (500.0 + lg.C_MISS_V1_RATIO) == 2.0 / 102.0
    stored = _stored_speck("GS6")
    if stored is not None:
        assert stored["checks"] == dict(blind_lose=True, islands_lose=True, runner_not_a_trap=True,
                                        contacts_off_no_income=True)
        assert all(stored["checks_at_c_miss_10"].values()) and stored["passed"]
        if stored["cheats"]["blind_presser_best"]["point"]["body"] == presser.name:
            _same(at10, stored["cheats"]["blind_presser_best"]["vs_lone"])
        _rejudge_speck("GS6", stored)


def test_main_runs_a_speck_gate(tmp_path):
    out = tmp_path / "s.json"
    assert lg.main(["--world", "speck", "--gates", "gs1", "--threads", "4", "--out", str(out)]) == 0
    data = json.loads(out.read_text())
    assert data["meta"]["world"] == "speck" and set(data["gates"]) == {"GS1"} and data["passed"]
    assert data["meta"]["hill_seed0"] == lg.SPECK_HILL_SEED0
    with pytest.raises(SystemExit):
        lg.main(["--world", "catch", "--tune", "reflex@ring2", "--out", str(out)])
