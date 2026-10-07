"""Life mode of the evolution harness (docs/ONE_LIFE_DESIGN.md, Code plan migration step 4): the LifeEvaluator, its
common random numbers, founder sampling, the smoke run's outputs and lineage, the control configs, two-stage selection
(evolve.recheck_*), the pilot arms and sweep, and the git revision in results rows."""
import json
import subprocess
from pathlib import Path

import numpy as np
import pytest
import torch

from src import evolve as evo
from src.common import load_config
from src.evolve import Eval, evolve_life, recheck, recheck_draw, recheck_plan, run_mode, sample_founders, setup
from src.genome import Layout, LifeDims, LifeLayout
from src.life import spec
from src.life.evaluate import LifeDraw, LifeEval, LifeEvaluator
from src.run import git_state, main

ROOT = Path(__file__).resolve().parents[1]
SMOKE = str(ROOT / "configs/life_smoke.yaml")
LAY = LifeLayout(LifeDims())


def _cfg(*overrides):
    return load_config(SMOKE, list(overrides))


def _pop(n: int = 24, seed: int = 0) -> torch.Tensor:
    """Random founders plus mutated ones, so some grow, some message and some trip the guard."""
    g = torch.Generator().manual_seed(seed)
    x = LAY.random(n, g)
    return LAY.mutate(x, g, n_mut=6)


def _fields(r: LifeEval) -> dict:
    return {f: getattr(r, f).numpy().copy() for f in LifeEval.__dataclass_fields__}


def _equal(a: dict, b: dict, idx=None) -> bool:
    """Bitwise equality of evaluation fields (``b`` indexed by ``idx`` first)."""
    for k, x in a.items():
        y = b[k] if idx is None else b[k][idx]
        if not np.array_equal(np.ascontiguousarray(x).view(np.uint8), np.ascontiguousarray(y).view(np.uint8)):
            return False
    return True


# ------------------------------------------------------------------------------------------------- evaluator
def test_setup_picks_the_evaluator_by_mode():
    assert run_mode(load_config(str(ROOT / "configs/local_smoke.yaml"))) == "trials"
    lattice, layout, task, ev = setup(_cfg())
    assert lattice is None and task is None and isinstance(layout, LifeLayout) and isinstance(ev, LifeEvaluator)
    with pytest.raises(ValueError):
        run_mode(_cfg("mode=tick"))


def test_eval_fields_follow_the_legacy_evaluator():
    ev = LifeEvaluator(_cfg(), LAY)
    x = _pop(12)
    draw = ev.draw("gen", 0)
    r = ev(x, draw)
    assert isinstance(r, Eval) and set(Eval.__dataclass_fields__) <= set(LifeEval.__dataclass_fields__)
    assert r.trial_scores.shape == (12, draw.n) == (12, 2)
    assert torch.equal(r.fitness, r.trial_scores.mean(1))
    assert torch.allclose(r.score - r.energy, r.fitness, atol=1e-12)  # F = income rate - cost rate
    lives = ev.run(x, draw)
    led = lives.ledger.reshape(12, 2, -1)
    assert np.allclose(r.n_cells.numpy(), led[:, :, spec.L["n_end"]].mean(1))
    assert np.allclose(r.divisions.numpy(), led[:, :, spec.L["births"]].mean(1))
    assert np.allclose(r.spikes.numpy(), led[:, :, spec.L["spikes"]].mean(1) / 128.0)
    assert set(r.take(0)) >= {"fitness", "score", "energy", "n_cells", "n_peak", "extinct", "guard"}
    assert (r.invalid == 0).all() and (r.guard > 0).any() and (r.n_peak > 1).any()


def test_evaluator_is_batch_composition_and_thread_independent():
    ev = LifeEvaluator(_cfg(), LAY)
    x = _pop(24, seed=1)
    draw = ev.draw("gen", 3)
    ref = _fields(ev(x, draw))
    perm = torch.randperm(24, generator=torch.Generator().manual_seed(2))
    assert _equal(_fields(ev(x[perm], draw)), ref, perm.numpy())
    ev.batch = 5  # other kernel batches
    assert _equal(_fields(ev(x, draw)), ref)
    for i in (0, 9, 23):  # alone
        assert _equal(_fields(ev(x[i:i + 1], draw)), ref, [i])
    mixed = torch.cat([x[:6], _pop(10, seed=3)])  # beside other genomes
    assert _equal({k: v[:6] for k, v in _fields(ev(mixed, draw)).items()}, ref, np.arange(6))
    ev.threads = 1
    assert _equal(_fields(ev(x, draw)), ref)


def test_life_seeds_are_shared_within_a_generation_and_fresh_across():
    ev = LifeEvaluator(_cfg(), LAY)
    a, b = ev.draw("gen", 4), ev.draw("gen", 4)
    assert a == b and len(set(a.seeds)) == a.n
    assert not set(a.seeds) & set(ev.draw("gen", 5).seeds)
    assert not set(a.seeds) & set(ev.draw("valid", 4).seeds)
    assert not set(a.seeds) & set(LifeEvaluator(_cfg("seed=1"), LAY).draw("gen", 4).seeds)
    lives = ev.run(_pop(3), a)
    assert lives.ledger.shape[0] == 6  # genome-major: every genome lives every seed of the draw
    f = ev.draw("founders", 0, lives=1, T=64.0)
    assert f.n == 1 and f.worlds[0].T == 64.0
    h = ev.draw("heldout", 0, lives=2, overrides=[{"th": 0.5}, {"tau_R": 12.0}])
    assert [w.th for w in h.worlds] == [0.5, 0.5, 0.6, 0.6] and h.worlds[3].tau_R == 12.0 and len(set(h.seeds)) == 4


def test_the_envelope_draws_noise_physics_per_life():
    ev = LifeEvaluator(_cfg("envelope.enabled=true"), LAY)
    a, b = ev.draw("gen", 0), ev.draw("gen", 1)
    assert a == ev.draw("gen", 0)  # common within a generation
    for w in a.worlds + b.worlds:
        assert 0.1 <= w.delay_sd <= 0.3 and 0.05 <= w.tau_mis <= 0.15 and 0.1 <= w.jit <= 0.3
        assert 0.05 <= w.clock_sd <= 0.2 and 0.0 <= w.drop_p <= 0.1 and 0.0 <= w.noise_rate <= 0.15
    assert len({w.delay_sd for w in a.worlds + b.worlds}) == 4  # fresh per life and generation
    assert LifeEvaluator(_cfg(), LAY).draw("gen", 0).worlds[0].delay_sd == 0.1
    assert ev(_pop(4), a).fitness.isfinite().all()


def test_the_envelope_changes_selection_lives_only():
    # review fix: valid and final lives used envelope physics in the envelope control and base physics elsewhere
    on, off = LifeEvaluator(_cfg("envelope.enabled=true"), LAY), LifeEvaluator(_cfg(), LAY)
    base = off.world()
    assert all(w != base for p in ("gen", "founders") for w in on.draw(p, 0).worlds)
    for purpose in ("valid", "final", "clones", "sizecurve", "census"):
        assert on.draw(purpose, 0, lives=3) == off.draw(purpose, 0, lives=3)  # same seeds, base physics
        assert all(w == base for w in on.draw(purpose, 0, lives=3).worlds)
    held = [{"th": 0.5}]
    assert on.draw("heldout", 0, lives=2, overrides=held) == off.draw("heldout", 0, lives=2, overrides=held)
    # the robustness column: the same lives under envelope physics, for every condition, enabled or not
    e_on, e_off = on.draw("final", 0, lives=3, envelope=True), off.draw("final", 0, lives=3, envelope=True)
    assert e_on == e_off and e_on.seeds == off.draw("final", 0, lives=3).seeds and all(w != base for w in e_on.worlds)
    assert on.draw("gen", 0, envelope=False) == off.draw("gen", 0)
    x = _pop(6)
    assert _equal(_fields(on(x, on.draw("final", 0, lives=3))), _fields(off(x, off.draw("final", 0, lives=3))))
    assert on.has_envelope and off.has_envelope  # life.yaml gives the ranges to every condition
    off.envelope = {"enabled": False}
    assert not off.has_envelope and off.draw("final", 0, lives=3, envelope=True) == on.draw("final", 0, lives=3)


def test_a_ledger_mismatch_makes_the_life_invalid_and_is_counted():
    # review fix: the kernel's ledger_mismatch bit was never read
    ev = LifeEvaluator(_cfg(), LAY)
    draw = ev.draw("gen", 0)
    x = _pop(3)
    res = ev.run(x, draw)
    col = ev.columns(res, 3, draw)
    assert not col["mismatch"].any() and not col["invalid"].any()
    st = spec.L["status"]
    res.ledger[1, st] = float(int(res.ledger[1, st]) | spec.STATUS["ledger_mismatch"])  # genome 0, life 1
    col = ev.columns(res, 3, draw)
    assert col["mismatch"][0, 1] and col["invalid"][0, 1] and col["mismatch"].sum() == 1
    assert col["F"][0, 1] == -draw.worlds[1].c_live * draw.worlds[1].n_max  # scored as the worst guard trip
    r = ev(x, draw)
    assert "mismatch" in LifeEval.KEYS and (r.mismatch == 0).all() and set(r.take(0)) == set(LifeEval.KEYS)


def test_death_income_replays_the_same_life_and_splits_its_income():
    # review fix: the design's monitor of cheat 8 ("income within 2 units of deaths is logged")
    from dataclasses import replace

    from src.life import build
    from src.life import handbuilt as hb
    from src.run import _merge, death_income

    assert _merge([5.0, 1.0, 2.5, 9.5], 2.0, 0.0, 10.0) == [(1.0, 4.5), (5.0, 7.0), (9.5, 10.0)]
    assert _merge([-3.0, -1.5], 2.0, 0.0, 10.0) == [(0.0, 0.5)]
    ev = LifeEvaluator(_cfg("life.T=320"), LAY)
    raw = hb.r25_genome(timer=1.125).astype(np.float32)
    spec.genome_view(raw, "a0")[spec.K["p_die"]] = 0.25  # p_die 2^-7: deaths
    g = torch.from_numpy(raw).reshape(1, -1)
    w, seeds = ev.world(), list(ev.draw("final", 0, lives=2).seeds)
    opens = [0.0, 17.25, 40.0, 63.5, 100.0]
    lives = build.run([replace(w, t_open=x) for x in opens for _ in seeds], seeds * len(opens), genomes=ev.table(g))
    inc = lives["income"].reshape(len(opens), len(seeds))
    assert (lives.hashes[:, 1:].reshape(len(opens), len(seeds), -1) == lives.hashes[:len(seeds), 1:]).all()  # one life
    parts = -np.diff(np.vstack([inc, np.zeros((1, len(seeds)))]), axis=0)  # income of [x_j, x_j+1)
    assert np.allclose(parts.sum(0), inc[0], rtol=1e-12, atol=0) and (parts >= 0).all() and lives["deaths"][0] > 0
    d = death_income(ev, g, seeds)
    assert d["death_lives"] == 2 and d["deaths_per_life"] > 0 and 0 < d["death_window_frac"] < 1
    assert 0 < d["death_income_share"] < 1 and d["death_lift"] > 0 and d["death_lift_rest"] > 0
    few = death_income(ev, g, seeds, max_windows=2)  # measured on a subset of the windows, extrapolated
    assert few["death_window_frac"] == d["death_window_frac"] and few["death_lift"] > 0
    spec.genome_view(raw, "a0")[spec.K["p_die"]] = -2.0
    none = death_income(ev, torch.from_numpy(raw).reshape(1, -1), seeds)
    assert none["deaths_per_life"] == 0 and none["death_lift"] is None and none["death_income_share"] == 0


@pytest.mark.parametrize("name, check", [
    ("messages_off", lambda w, c: w.flags == spec.FLAGS["contacts_off"]),
    ("freeze", lambda w, c: w.t_fork == 256.0 and w.fork_flags == spec.FLAGS["freeze"] and w.flags == 0),
    ("apoptosis_off", lambda w, c: w.flags == spec.FLAGS["apoptosis_off"]),
    ("genes_blind", lambda w, c: w.flags == spec.FLAGS["genes_blind"]),
    ("square8", lambda w, c: w.lattice == "square8"),
    ("envelope", lambda w, c: bool(c.envelope.enabled)),
    ("asex", lambda w, c: c.evolve.breeding == "asex"),
])
def test_control_configs(name, check):
    cfg = load_config(str(ROOT / f"configs/life_ctl_{name}.yaml"))
    assert run_mode(cfg) == "life" and cfg.life.control == name
    ev = LifeEvaluator(cfg, LAY)
    w = ev.world()
    assert check(w, cfg) and w.T == 1024.0
    assert cfg.evolve.generations == 500 and cfg.evolve.mu == 32 and cfg.evolve.lam == 224
    base = LifeEvaluator(load_config(str(ROOT / "configs/life_bell.yaml")), LAY).world()
    changed = {k for k in spec.WORLD_KEYS + ("lattice",) if getattr(w, k) != getattr(base, k)}
    assert changed <= {"flags", "t_fork", "fork_flags", "lattice"}  # one thing changes at a time


def test_the_messages_off_control_delivers_no_spikes():
    cfg = _cfg("life.flags=[contacts_off]")
    ev = LifeEvaluator(cfg, LAY)
    lives = ev.run(_pop(24, seed=4), ev.draw("gen", 0))
    assert lives["arrivals"].sum() == 0 and lives["contact_events"].sum() > 0


# ------------------------------------------------------------------------------------------- founder sampling
class _Stub:
    """Evaluator whose fitness and score are two genome entries, so the ranking can be checked exactly."""

    def __call__(self, cands, draw):
        f, s = cands[:, 0].double(), cands[:, 1].double()
        z = torch.zeros_like(f)
        return Eval(fitness=f, score=s, energy=z, n_cells=z, spikes=z, divisions=z, trial_scores=f[:, None])


@pytest.mark.parametrize("key", ["score", "fitness"])
def test_founder_sampling_ranks_scorers_first(key):
    cfg = _cfg("evolve.founders=32", "evolve.init_samples=64", "evolve.max_init_samples=64",
               "evolve.min_founder_score=1.2", f"evolve.founder_key={key}")
    founders, used, info = sample_founders(cfg, _Stub(), LAY, lambda g: None, torch.Generator().manual_seed(0))
    crit = founders[:, 0 if key == "fitness" else 1]
    n = info["scoring_founders"]
    assert used == 64 and 0 < n < 32
    assert (crit[:n] >= 1.2).all() and (crit[n:] < 1.2).all()  # scorers first
    assert (founders[:n, 0].diff() <= 0).all() and (founders[n:, 0].diff() <= 0).all()  # each group by fitness
    if key == "score":
        assert founders[n:, 0].max() > founders[:n, 0].min()  # a fitter non-scorer still ranks below every scorer


def test_founder_sampling_continues_until_a_genome_reaches_F():
    cfg = _cfg("evolve.init_samples=32", "evolve.max_init_samples=96", "evolve.min_founder_score=2.0")
    ev = LifeEvaluator(cfg, LAY)
    batches = iter(range(10))
    founders, used, info = sample_founders(cfg, ev, LAY, lambda g: ev.draw("founders", next(batches), 1, 64.0),
                                           torch.Generator().manual_seed(0))
    assert used == 96 and info["scoring_founders"] == 0 and info["founder_key"] == "fitness"


# -------------------------------------------------------------------------------------------------- smoke run
@pytest.fixture(scope="module")
def smoke(tmp_path_factory):
    out = tmp_path_factory.mktemp("life_smoke")
    results = main(_cfg(f"logging.output_dir={out}"))
    return out, json.loads(results.read_text().splitlines()[-1])


def test_smoke_run_writes_outputs(smoke):
    out, row = smoke
    for name in ("results.jsonl", "curves.jsonl", "lineage.jsonl", "best_genome.json", "population.json",
                 "clones.jsonl", "config.yaml"):
        assert (out / name).exists(), name
    assert row["mode"] == "life" and row["control"] == "full" and row["generations"] == 3
    assert {"F", "F_se", "n_cells", "income", "energy", "extinction_rate", "n_peak", "msg_reliance", "forks",
            "top_F", "final_seeds", "valid_score", "heldout_score", "evals", "size_curve", "size_curve_flat_top",
            "F_ci95", "kuramoto_R", "local_order", "beat_period", "trap_rate", "income_per_cell_late",
            "F_envelope", "F_envelope_se", "d_F_envelope", "mismatch_lives", "death_lives", "death_lift",
            "top_best_F_pick", "top_best_F_se"} <= set(row)
    assert row["selection_physics"] == "base" and row["mismatch_lives"] == 0
    # the best of the top is picked on the final lives and reported on separate ones
    assert row["top_best_F_pick"] == row["top_F"][row["top_best_rank"]] and row["top_best_F_se"] >= 0
    ev = LifeEvaluator(_cfg(), LAY)
    assert not set(ev.draw("final", 1, lives=len(row["final_seeds"])).seeds) & set(row["final_seeds"])
    assert row["evals"] == row["founders_sampled"] + 3 * (4 + 12)
    curves = [json.loads(line) for line in (out / "curves.jsonl").read_text().splitlines()]
    assert [c["gen"] for c in curves] == [0, 1, 2] and all("valid" in c and "clones" in c for c in curves)
    assert all(c["pop_mismatch"] == 0 and c["pop_invalid"] == 0 and c["mismatch"] == 0 for c in curves)
    layout, best = Layout.load(out / "best_genome.json")
    assert isinstance(layout, LifeLayout) and best.shape == (spec.GENOME_SIZE,)
    pop = json.loads((out / "population.json").read_text())
    assert len(pop["genomes"]) == 4 and pop["dims"]["kind"] == "life"
    assert torch.equal(layout.from_dict(pop["genomes"][0]), best)


def test_smoke_lineage_is_consistent(smoke):
    out, _ = smoke
    rows = [json.loads(line) for line in (out / "lineage.jsonl").read_text().splitlines()]
    head, gens = rows[0], rows[1:]
    assert head["event"] == "founders" and len(gens) == 3
    alive = set(head["ids"]) | {c["id"] for c in head["copies"]}
    assert all(c["parent"] in head["ids"] and "mut" in c["ops"] for c in head["copies"])
    for r in gens:
        kids = {c["id"]: c for c in r["children"]}
        assert all(c["kept"] for c in kids.values())  # logging.lineage = survivors
        for c in kids.values():
            assert c["pa"] in alive and c["pb"] in alive and 0 <= c["mask"] < 2 ** (spec.G_MAX + 1)
        assert set(r["survivors"]) <= alive | set(kids) and set(kids) <= set(r["survivors"])
        assert len(r["seeds"]) == 2 and sum(r["breeds"].values()) == 4
        assert all(sum(v.values()) <= 4 for v in r["registry"].values()) and r["n_active"] == 8.0
        alive = set(r["survivors"])
    clones = [json.loads(line) for line in (out / "clones.jsonl").read_text().splitlines()]
    assert {c["condition"] for c in clones} == set(_cfg().clones.conditions) and {c["frac"] for c in clones} == {0.5}


def test_asex_lineage_has_no_masks(tmp_path):
    main(_cfg(f"logging.output_dir={tmp_path}", "evolve.breeding=asex", "evolve.generations=2", "clones.every=0",
              "life.size_curve=[]", "logging.lineage=all"))
    gens = [json.loads(line) for line in (tmp_path / "lineage.jsonl").read_text().splitlines()][1:]
    assert all(len(r["children"]) == 12 for r in gens)  # logging.lineage = all
    assert all(c["pb"] is None and c["mask"] is None for r in gens for c in r["children"])
    assert not (tmp_path / "clones.jsonl").read_text()


def test_random_search_mode(tmp_path):
    row = json.loads(main(_cfg(f"logging.output_dir={tmp_path}", "evolve.generations=0",
                               "life.size_curve=[]")).read_text())
    assert row["evals"] == row["founders_sampled"] and row["generations"] == 0 and row["valid_score"] is None


def test_draws_are_frozen_dataclasses():
    d = LifeDraw((1, 2), (spec.world(), spec.world()))
    assert d.n == 2 and hash(d) == hash(LifeDraw((1, 2), (spec.world(), spec.world())))


def test_aggregate_reports_the_envelope_column_and_refuses_pre_fix_envelope_rows():
    import pandas as pd

    from scripts.aggregate import life_summary

    row = dict(sweep="s", world="bell_v1", lattice="hex", breeding="sex", seed=0, F=0.03, valid_score=0.03,
               heldout_score=0.02, n_cells=1.0, n_peak=1.0, income=0.05, energy=0.02, income_per_cell=0.05,
               extinction_rate=0.0, msg_reliance=0.0, evals_to_skill=None)
    new = [dict(row, control=c, selection_physics=p, F_envelope=0.01, death_lift=None)
           for c, p in (("full", "base"), ("envelope", "envelope"))]
    out = life_summary(pd.DataFrame(new))
    assert list(out["control"]) == ["envelope", "full"] and (out["F_envelope"] == 0.01).all()
    with pytest.raises(ValueError, match="envelope physics"):
        life_summary(pd.DataFrame([dict(row, control="envelope")]))  # written before the fix
    assert len(life_summary(pd.DataFrame([dict(row, control="full")]))) == 1  # older rows of other conditions are fine


# ------------------------------------------------------------------------------------------ two-stage selection
RECHECK = ("evolve.recheck_k=8", "evolve.recheck_lives=3")  # smoke scale: 16 genomes, 2 generation lives


def test_recheck_plan_reads_and_checks_the_settings():
    e = _cfg().evolve
    assert recheck_plan(e, 4, 16) == (0, 0, "all")  # life_smoke: off
    bell = load_config(str(ROOT / "configs/life_bell.yaml")).evolve
    assert recheck_plan(bell, 32, 256) == (64, 4, "all")  # the chosen scheme (B1 K64 L4)
    assert recheck_plan(_cfg(*RECHECK).evolve, 4, 16) == (8, 3, "all")
    assert recheck_plan(_cfg("evolve.recheck_k=8", "evolve.recheck_lives=0").evolve, 4, 16)[0] == 0
    assert recheck_plan(_cfg("evolve.recheck_k=99", "evolve.recheck_lives=2").evolve, 4, 16) == (16, 2, "all")
    assert recheck_plan(_cfg(*RECHECK, "evolve.recheck_key=recheck").evolve, 4, 16)[2] == "recheck"
    for bad in (["evolve.recheck_k=3", "evolve.recheck_lives=2"], [*RECHECK, "evolve.recheck_key=B1"],
                ["evolve.recheck_k=8", "evolve.recheck_lives=-1"]):
        with pytest.raises(ValueError):
            recheck_plan(_cfg(*bad).evolve, 4, 16)


def test_recheck_lives_are_fresh_shared_and_disjoint():
    for extra in ([], ["envelope.enabled=true"]):
        ev = LifeEvaluator(_cfg(*extra), LAY)
        L, L2 = ev.lives, 4
        r0, r1 = recheck_draw(ev, 0, L, L2), recheck_draw(ev, 1, L, L2)
        assert r0.n == L2 and len(set(r0.seeds)) == L2 and r0 == recheck_draw(ev, 0, L, L2)
        full = ev.draw("gen", 0, lives=L + L2)  # the generation's own draw continued
        assert r0.seeds == full.seeds[L:] and r0.worlds == full.worlds[L:] and full.seeds[:L] == ev.draw("gen", 0).seeds
        assert not set(r0.seeds) & set(r1.seeds)  # fresh every generation
        others = set()
        for g in range(3):
            others |= set(ev.draw("gen", g).seeds)
        for purpose in ("founders", "valid", "final", "clones", "sizecurve", "census"):
            for i in range(3):
                others |= set(ev.draw(purpose, i, lives=64).seeds)
        others |= set(ev.draw("heldout", 0, lives=4, overrides=list(_cfg().life.heldout)).seeds)
        assert not (set(r0.seeds) | set(r1.seeds)) & others
        if extra:  # selection lives: the envelope's noise physics, fresh per life
            assert all(w != ev.world() for w in r0.worlds) and len({w.delay_sd for w in r0.worlds}) == L2


class _Spy:
    """A LifeEvaluator that records (genomes, draw) of every call."""

    def __init__(self, ev):
        self.ev, self.calls, self.lives = ev, [], ev.lives

    def draw(self, *a, **k):
        return self.ev.draw(*a, **k)

    def __call__(self, params, draw):
        self.calls.append((params.clone(), draw))
        return self.ev(params, draw)


def test_recheck_ranks_the_shortlist_on_all_its_lives():
    ev = _Spy(LifeEvaluator(_cfg(), LAY))
    x = _pop(24, seed=5)
    g, mu, k, L2 = 7, 6, 12, 3
    res = ev(x, ev.draw("gen", g))
    ev.calls.clear()
    out = recheck(ev, x, res, g, mu, k, L2, "all")
    short = res.fitness.argsort(descending=True, stable=True)[:k]
    assert torch.equal(out["shortlist"], short)
    assert len(ev.calls) == 1  # one evaluation: the whole shortlist on one shared draw
    params, draw = ev.calls[0]
    assert torch.equal(params, x[short]) and draw == recheck_draw(ev, g, 2, L2) == out["draw"]
    # the key is the mean over all 2 + 3 lives: bitwise one evaluation of the shortlist on the generation's 5 lives
    whole = ev.ev(x[short], ev.draw("gen", g, lives=2 + L2))
    assert torch.equal(whole.fitness[out["pick"]], out["chosen"].fitness)
    assert torch.equal(whole.trial_scores[out["pick"]], out["chosen"].trial_scores)
    for f in ("score", "energy", "n_cells", "n_peak", "body", "guard"):
        assert torch.allclose(getattr(whole, f)[out["pick"]], getattr(out["chosen"], f), rtol=1e-12, atol=1e-15)
    expect = whole.fitness.argsort(descending=True, stable=True)[:mu]
    assert torch.equal(out["order"], short[expect]) and torch.equal(out["pick"], expect)
    assert out["changed"] == mu - len(set(out["order"].tolist()) & set(short[:mu].tolist()))
    alone = recheck(ev, x, res, g, mu, k, L2, "recheck")  # the recheck lives only
    assert torch.equal(alone["order"], short[alone["res"].fitness.argsort(descending=True, stable=True)[:mu]])
    assert torch.equal(alone["res"].fitness, out["res"].fitness)


class _Lives:
    """Stub evaluator: every genome scores its entry 0 on lives 0-2 of a generation and its entry 1 on later lives."""

    lives = 3

    def draw(self, purpose, index, lives=None):
        n = self.lives if lives is None else lives
        return LifeDraw(tuple(range(n)), (None,) * n)

    def __call__(self, params, draw):
        ts = torch.stack([params[:, 0 if s < 3 else 1].double() for s in draw.seeds], 1)
        z = torch.zeros(params.shape[0], dtype=torch.float64)
        return Eval(fitness=ts.mean(1), score=z, energy=z, n_cells=z, spikes=z, divisions=z, trial_scores=ts)


def test_recheck_picks_parents_by_the_chosen_key():
    # genome: (F on the generation's lives, F on the recheck lives)
    x = torch.tensor([[0.5, 5.0], [0.7, 0.1], [0.9, 0.4], [0.2, 9.0], [0.6, 0.45], [0.8, 0.7], [0.3, 0.0],
                      [0.4, 0.0]])
    ev = _Lives()
    res = ev(x, ev.draw("gen", 0))
    out = recheck(ev, x, res, 0, 2, 4, 4, "all")
    assert out["shortlist"].tolist() == [2, 5, 1, 4]  # genomes 0 and 3 recheck best but are not shortlisted
    assert out["order"].tolist() == [5, 2] and out["changed"] == 0  # (3 F + 4 F') / 7: 0.743, 0.614, 0.514, 0.357
    assert torch.allclose(out["chosen"].fitness, torch.tensor([2.4 + 2.8, 2.7 + 1.6], dtype=torch.float64) / 7)
    only = recheck(ev, x, res, 0, 2, 4, 4, "recheck")
    assert only["order"].tolist() == [5, 4] and only["changed"] == 1  # F' alone: 0.7, 0.45, 0.4, 0.1
    tied = x.clone()
    tied[:, 1] = 0.3
    t = recheck(ev, tied, ev(tied, ev.draw("gen", 0)), 0, 2, 4, 4, "recheck")
    assert t["order"].tolist() == [2, 5] and t["changed"] == 0  # ties keep the shortlist (generation-lives) order


def test_pooled_matches_one_evaluation_on_all_the_lives():
    ev = LifeEvaluator(_cfg(), LAY)
    x = _pop(10, seed=6)
    a, b = ev(x, ev.draw("gen", 3)), ev(x, recheck_draw(ev, 3, 2, 4))
    whole = ev(x, ev.draw("gen", 3, lives=6))
    p = evo.pooled(a, b)
    assert isinstance(p, LifeEval) and torch.equal(p.fitness, whole.fitness)
    assert torch.equal(p.trial_scores, whole.trial_scores)
    for f in LifeEval.KEYS:
        assert torch.allclose(getattr(p, f), getattr(whole, f), rtol=1e-12, atol=1e-15), f
    idx = torch.tensor([4, 0, 7])
    assert all(torch.equal(getattr(evo.rows(a, idx), f), getattr(a, f)[idx]) for f in LifeEval.__dataclass_fields__)


def _no_times(curves):
    return [{k: v for k, v in r.items() if k not in ("t_gen", "t_eval")} for r in curves]


def test_recheck_off_is_the_one_stage_loop(tmp_path, monkeypatch):
    def never(*a, **k):
        raise AssertionError("the recheck ran while off")

    monkeypatch.setattr(evo, "recheck", never)
    runs = []
    for name, extra in (("k0", []), ("lives0", ["evolve.recheck_k=8", "evolve.recheck_lives=0"])):
        out = tmp_path / name
        out.mkdir()
        log = []
        r = evolve_life(_cfg("clones.every=0", "evolve.generations=4", *extra), log=log.append, out=out)
        runs.append((r, _no_times(r["curves"]), (out / "lineage.jsonl").read_text(), log))
    (r, curves, lineage, log), other = runs[0], runs[1]
    assert curves == other[1] and lineage == other[2] and torch.equal(r["population"], other[0]["population"])
    assert torch.equal(r["fitness"], other[0]["fitness"]) and r["evals"] == other[0]["evals"]
    # the one-stage semantics: no recheck fields, integer evals (genomes x generations), and the survivors are the
    # generation's top 4 with their F on the generation's lives, as the children's rows give it
    founders = log[0]["sampled"]
    assert r["evals"] == founders + 4 * 16 and isinstance(r["evals"], int)
    gens = [json.loads(line) for line in lineage.splitlines()][1:]
    for g, (row, lrow) in enumerate(zip(curves, gens)):
        assert not [k for k in row if "recheck" in k] and "recheck" not in lrow
        assert row["evals"] == founders + (g + 1) * 16 and isinstance(row["evals"], int)
        fit = lrow["fitness"]
        assert fit == sorted(fit, reverse=True) and row["fitness"] == fit[0]
        assert row["mean_fitness"] == float(torch.tensor(fit, dtype=torch.float64).mean())
        kids = {c["id"]: c["fitness"] for c in lrow["children"]}
        assert all(kids[i] == f for i, f in zip(lrow["survivors"], fit) if i in kids)
    assert torch.equal(r["fitness"], torch.tensor(gens[-1]["fitness"], dtype=torch.float64))


@pytest.fixture(scope="module")
def smoke_recheck(tmp_path_factory):
    out = tmp_path_factory.mktemp("life_smoke_recheck")
    results = main(_cfg(f"logging.output_dir={out}", *RECHECK))
    return out, json.loads(results.read_text().splitlines()[-1])


def test_recheck_run_counts_its_lives_and_logs_them(smoke_recheck):
    out, row = smoke_recheck
    curves = [json.loads(line) for line in (out / "curves.jsonl").read_text().splitlines()]
    gens = [json.loads(line) for line in (out / "lineage.jsonl").read_text().splitlines()][1:]
    per_gen = 16 + 8 * 3 / 2  # 16 genomes on 2 lives, then 8 on 3 more: 12 genome evaluations of 2 lives
    assert row["evals"] == row["founders_sampled"] + 3 * per_gen
    assert [c["evals"] for c in curves] == [row["founders_sampled"] + (g + 1) * per_gen for g in range(3)]
    assert (row["recheck_k"], row["recheck_lives"], row["recheck_key"]) == (8, 3, "all")
    ev = LifeEvaluator(_cfg(), LAY)
    seen = set(row["final_seeds"])
    for g, (c, lrow) in enumerate(zip(curves, gens)):
        rc = lrow["recheck"]
        assert c["recheck_k"] == 8 == len(rc["ids"]) == len(rc["F_recheck"]) and 0 <= c["recheck_changed"] <= 4
        assert c["recheck_changed"] == rc["changed"] and c["recheck_invalid"] == 0 and c["t_recheck"] >= 0
        assert rc["F_base"] == sorted(rc["F_base"], reverse=True) and rc["key"] == "all"
        assert tuple(rc["seeds"]) == recheck_draw(ev, g, 2, 3).seeds and not set(rc["seeds"]) & set(lrow["seeds"])
        assert not set(rc["seeds"]) & seen  # fresh: no earlier generation or recheck life, no final life
        seen |= set(rc["seeds"]) | set(lrow["seeds"])
        # survivors: the shortlist's top 4 by the mean over all 5 lives, logged as that mean
        mean5 = {i: (2 * fb + 3 * fr) / 5 for i, fb, fr in zip(rc["ids"], rc["F_base"], rc["F_recheck"])}
        assert set(lrow["survivors"]) <= set(rc["ids"])
        assert lrow["survivors"] == sorted(rc["ids"], key=lambda i: -mean5[i])[:4]
        assert np.allclose(lrow["fitness"], [mean5[i] for i in lrow["survivors"]], rtol=0, atol=1e-15)
        assert c["fitness"] == lrow["fitness"][0] and abs(c["mean_fitness"] - np.mean(lrow["fitness"])) < 1e-15
        recheck_F = [rc["F_recheck"][rc["ids"].index(i)] for i in lrow["survivors"]]
        base_F = [rc["F_base"][rc["ids"].index(i)] for i in lrow["survivors"]]
        assert abs(c["recheck_F"] - np.mean(recheck_F)) < 1e-15 and abs(c["recheck_F_base"] - np.mean(base_F)) < 1e-15
        top4 = set(rc["ids"][:4])
        assert c["recheck_changed"] == 4 - len(top4 & set(lrow["survivors"]))


def test_recheck_rows_count_the_bodies_it_keeps_and_drops(monkeypatch):
    """Review fix (the recheck halves body escapes in the selection study): every two-stage row says how many bodies
    one-stage selection would have made parents and how many the recheck did, so a run stuck at 1-2 cells can be
    attributed. A seeded population grows bodies, so the counts are not trivially 0."""
    seen, real = [], evo.recheck

    def spy(ev, everyone, res, *a):
        rc = real(ev, everyone, res, *a)
        seen.append((res, rc))
        return rc

    monkeypatch.setattr(evo, "recheck", spy)
    r = evolve_life(_cfg(*RECHECK, "evolve.seed_genome=r25_v1_timer", "clones.every=0"), log=lambda row: None)
    assert len(seen) == len(r["curves"]) == 3
    total = 0
    for c, (res, rc) in zip(r["curves"], seen):
        body = res.n_cells >= evo.BODY_CELLS
        onestage = res.fitness.argsort(descending=True, stable=True)[:4]
        assert c["recheck_bodies"] == int(body[rc["order"]].sum()) and 0 <= c["recheck_bodies"] <= 4
        assert c["recheck_bodies_onestage"] == int(body[onestage].sum())
        total += c["recheck_bodies_onestage"]
    assert total > 0
    assert evo.recheck_bodies(r["curves"]) == dict(
        recheck_bodies=sum(c["recheck_bodies"] for c in r["curves"]), recheck_bodies_onestage=total,
        recheck_body_losses=sum(c["recheck_bodies_onestage"] > 0 and c["recheck_bodies"] == 0 for c in r["curves"]))
    # totals and losses: a loss is a generation where the recheck dropped every body one-stage selection kept
    rows = [dict(recheck_bodies=b, recheck_bodies_onestage=o) for b, o in ((0, 2), (1, 3), (0, 0), (2, 1), (0, 1))]
    assert evo.recheck_bodies(rows) == dict(recheck_bodies=3, recheck_bodies_onestage=7, recheck_body_losses=2)
    assert evo.recheck_bodies([{"gen": 0}]) == dict(recheck_bodies=None, recheck_bodies_onestage=None,
                                                    recheck_body_losses=None)


def test_results_rows_carry_the_git_revision(smoke, smoke_recheck):
    state = git_state()
    for _, row in (smoke, smoke_recheck):
        assert row["git_rev"] == state["git_rev"] and row["git_dirty"] == state["git_dirty"]
    if state["git_rev"] is not None:
        assert len(state["git_rev"]) == 40 and isinstance(state["git_dirty"], bool)
    assert smoke[1]["recheck_k"] == 0 and smoke[1]["recheck_key"] is None
    assert smoke[1]["recheck_bodies"] is None and smoke[1]["recheck_body_losses"] is None  # one-stage: nothing
    curves = [json.loads(line) for line in (smoke_recheck[0] / "curves.jsonl").read_text().splitlines()]
    assert {k: smoke_recheck[1][k] for k in evo.recheck_bodies(curves)} == evo.recheck_bodies(curves)
    assert git_state(Path("/")) == {"git_rev": None, "git_dirty": None}


# ------------------------------------------------------------------------------------------------ pilot arms
def test_pilot_arms_differ_only_in_the_lattice():
    hexa = load_config(str(ROOT / "configs/life_bell.yaml"))
    sq8 = load_config(str(ROOT / "configs/life_bell_square8.yaml"))
    assert (hexa.lattice.kind, sq8.lattice.kind) == ("hex", "square8")
    assert hexa.life.control == sq8.life.control == "full"  # a full arm, not a control
    a, b = load_config(str(ROOT / "configs/life_bell.yaml"), ["lattice.kind=square8"]), sq8
    a.logging.output_dir, a.extends = b.logging.output_dir, b.extends
    assert a == b
    assert (hexa.evolve.recheck_k, hexa.evolve.recheck_lives, hexa.evolve.recheck_key) == (64, 4, "all")
    assert hexa.evolve.generations == 500 and hexa.evolve.mu == 32 and hexa.evolve.lam == 224
    assert int(hexa.threads) <= 4


def test_sweep_interleaves_arms_and_the_pilot_script_runs_both():
    from scripts.sweep import matrix

    arms = [(c, load_config(str(ROOT / c))) for c in ("configs/life_bell.yaml", "configs/life_bell_square8.yaml")]
    runs = matrix(arms, None, None, ["0", "1"])
    assert [r["run"] for r in runs] == ["full_hex_sex_s0", "full_square8_sex_s0", "full_hex_sex_s1",
                                        "full_square8_sex_s1"]
    assert [r["config"] for r in runs[:2]] == ["configs/life_bell.yaml", "configs/life_bell_square8.yaml"]
    legacy = [("configs/local_smoke.yaml", load_config(str(ROOT / "configs/local_smoke.yaml")))]
    assert [r["run"] for r in matrix(legacy, "hex,square8", "sex", ["0", "1"])] == [
        "hex_sex_s0", "hex_sex_s1", "square8_sex_s0", "square8_sex_s1"]  # one arm: the order of before
    with pytest.raises(ValueError, match="share an output directory"):
        matrix([arms[0], arms[0]], None, None, ["0"])
    script = (ROOT / "scripts/run_life_pilot.sh").read_text()
    for part in ("--config configs/life_bell.yaml,configs/life_bell_square8.yaml", "PILOT_SEEDS:-0,1,2,3,4,5,6,7,8,9",
                 "--jobs 3 --threads 3", "PILOT_GENERATIONS:-500", "NAME=life_pilot", "scripts/sweep.py",
                 '--out "${ROOT}outputs" --logs "${ROOT}logs"', 'evolve.generations="$GENERATIONS"'):
        assert part in script, part  # defaults: 10 seeds x 500 generations into outputs/, logs/ and results/
    assert subprocess.run(["bash", "-n", str(ROOT / "scripts/run_life_pilot.sh")]).returncode == 0


def test_aggregate_groups_by_selection_and_reports_git():
    import pandas as pd

    from scripts.aggregate import life_summary

    row = dict(sweep="s", world="bell_v1", lattice="hex", breeding="sex", seed=0, F=0.03, valid_score=0.03,
               heldout_score=0.02, n_cells=1.0, n_peak=1.0, income=0.05, energy=0.02, income_per_cell=0.05,
               extinction_rate=0.0, msg_reliance=0.0, evals_to_skill=None, control="full", selection_physics="base")
    two = dict(recheck_k=64, recheck_lives=4, recheck_key="all")
    out = life_summary(pd.DataFrame([dict(row, git_rev="a" * 40, git_dirty=False, **two),
                                     dict(row, seed=1, git_rev="b" * 40, git_dirty=True, **two),
                                     dict(row, seed=2)]))  # a row from before the fields: one-stage, git unknown
    assert list(out["selection"]) == ["one-stage", "recheck K64 L4 all"] and list(out["runs"]) == [1, 2]
    assert list(out["git"]) == ["?", "aaaaaaa,bbbbbbb+dirty"]
    assert np.isnan(out["bodies_kept"][0]) and np.isnan(out["body_losses"][0])  # rows without the body fields
    bodies = [dict(recheck_bodies=3, recheck_bodies_onestage=10, recheck_body_losses=2),
              dict(recheck_bodies=2, recheck_bodies_onestage=0, recheck_body_losses=0)]
    out = life_summary(pd.DataFrame([dict(row, **two, **bodies[0]), dict(row, seed=1, **two, **bodies[1]),
                                     dict(row, seed=2, recheck_k=0, recheck_bodies=None)]))
    assert list(out["bodies_kept"])[1] == 0.5 and list(out["body_losses"])[1] == 2  # (3 + 2) / (10 + 0), 2 + 0
    assert np.isnan(out["bodies_kept"][0]) and np.isnan(out["body_losses"][0])  # one-stage
