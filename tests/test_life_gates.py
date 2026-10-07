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
