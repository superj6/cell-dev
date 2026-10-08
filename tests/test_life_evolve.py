"""Life mode of the evolution harness (docs/ONE_LIFE_DESIGN.md, Code plan migration step 4): the LifeEvaluator, its
common random numbers, founder sampling, the smoke run's outputs and lineage, the control configs, two-stage selection
(evolve.recheck_*), the pilot arms and sweep, and the git revision in results rows."""
import json
import subprocess
from dataclasses import replace
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
    assert "growing" not in out and list(out["world"]) == ["bell_v1"] * 2  # BELL rows: as before
    # CATCH rows: a world with overrides (SPECK) is its own group, and GB11's readout is the median share growing
    catch = dict(row, world="catch_v1_l4", control="lmax4", **two)
    out = life_summary(pd.DataFrame([dict(catch, growing=0.9), dict(catch, seed=1, growing=0.5),
                                     dict(catch, control="speck_lmax4", world_over="R_cap=500,sigma=0.6",
                                          growing=0.25)]))
    assert list(out["world"]) == ["catch_v1_l4", "catch_v1_l4[R_cap=500,sigma=0.6]"]
    assert list(out["runs"]) == [2, 1] and list(out["growing"]) == [0.7, 0.25]


# ------------------------------------------------------------------------------------------- BODY-1: CATCH
CATCH_CFG = str(ROOT / "configs/life_catch.yaml")
CATCH_TINY = ["life.T=192", "life.founder_T=96", "life.valid_lives=2", "life.heldout_lives=1",
              "life.heldout=[{v_t: 0.2}]", "life.final_lives=4", "life.final_top=2", "life.final_fork_lives=2",
              "life.size_curve=[2,14]", "life.size_curve_lives=2", "clones.every=1", "clones.top=2",
              "clones.times=[0.5]", "clones.lives=1", "evolve.mu=4", "evolve.lam=12", "evolve.generations=3",
              "evolve.founders=2", "evolve.init_samples=48", "evolve.max_init_samples=96", "evolve.heldout_every=1",
              "evolve.batch=16", "evolve.recheck_k=8", "evolve.recheck_lives=2", "threads=2",
              "life.T_choices=[144,192,288]"]  # the configs' GB11 draw (768, 1024, 1536) scaled to T 192


def _catch(*overrides, path=CATCH_CFG):
    return load_config(path, CATCH_TINY + list(overrides))


def test_the_catch_evaluator_runs_abi3_genomes_and_reports_the_planes():
    from src.genome import LIFE_DIMS_ABI3

    _, layout, _, ev = setup(_catch())
    assert layout.dims == LIFE_DIMS_ABI3 and layout.abi is spec.V3 and ev.abi is spec.V3 and ev.catch
    assert ev.kind == "hexprism" and ev.world().L_max == 4 and ev.extinct_charge
    x = layout.random(16, torch.Generator().manual_seed(3))
    draw = ev.draw("gen", 0)
    r = ev(x, draw)
    led = ev.run(x, draw).ledger.reshape(16, draw.n, -1)
    L3 = spec.V3.L
    for k, c in (("captures", "captures"), ("misses", "misses"), ("clicks", "clicks"), ("n_S", "n_S_end"),
                 ("n_M", "n_M_end"), ("n_H", "n_H_end")):
        assert np.array_equal(getattr(r, k).numpy(), led[:, :, L3[c]].mean(1)), k
    assert np.allclose((r.n_S + r.n_M + r.n_H).numpy(), r.n_cells.numpy(), rtol=1e-12, atol=0)
    assert set(r.take(0, catch=True)) == set(LifeEval.KEYS + LifeEval.CATCH_KEYS)
    assert set(r.take(0)) == set(LifeEval.KEYS)  # the BELL row keys are unchanged
    bell = LifeEvaluator(_cfg(), LAY)
    assert bell.abi is spec.V2 and not bell.catch and not bell.extinct_charge
    rb = bell(_pop(4), bell.draw("gen", 0))
    assert all((getattr(rb, k) == 0).all() for k in LifeEval.CATCH_KEYS)
    with pytest.raises(ValueError, match="ABI-3 genome"):  # a CATCH world with BELL's 793-slot genome
        setup(_catch("genome.life.stim=0", "genome.life.cues=0", "genome.life.pheno=21", "genome.input_init=null",
                     "genome.knob_init=null", "genome.readout_std=null"))


def test_the_extinction_charge_scores_an_extinct_life_as_a_silent_cell_living_on():
    """Tweak (evaluate.py): in CATCH a zygote that dies at once has F about 0 and would beat the silent lone cell
    (-c_live) and every losing body. Under life.extinct_charge an extinct life pays c_live for every counted unit
    after its extinction; the kernel's F stays in F_kernel, and lives that do not go extinct are untouched."""
    _, layout, _, ev = setup(_catch())
    g = torch.zeros(2, layout.size)  # no active gene: a decode of a0 alone
    a0 = layout.view(g, "a0")
    a0[0, spec.V3.K["p_die"]] = 2.0  # p_die = 1: the zygote dies at its first tick
    a0[:, spec.V3.K["tau_m"]] = 0.0
    draw = ev.draw("gen", 0)
    col = ev.columns(ev.run(g, draw), 2, draw)
    w = draw.worlds[0]
    assert col["extinct"][0].all() and not col["extinct"][1].any()
    assert (col["F_kernel"][0] > -1e-3).all()  # the kernel's F of the dead zygote is about 0 ...
    rest = w.t0 + w.T - col["t_ext"][0]
    assert np.allclose(col["F"][0], col["F_kernel"][0] - w.c_live * rest / w.T, rtol=0, atol=1e-15)
    assert (np.abs(col["F"][0] + w.c_live) < 1e-3).all()  # ... and is charged like a silent cell
    assert np.array_equal(col["F"][1], col["F_kernel"][1]) and (col["F"][1] < -w.c_live).all()  # lives on: unchanged
    assert np.array_equal(col["extinct_charge"][0], col["F_kernel"][0] - col["F"][0])
    r = ev(g, draw)  # the charge is a cost: F = income rate - cost rate still holds
    assert torch.allclose(r.score - r.energy, r.fitness, atol=1e-12)
    ev.extinct_charge = False
    assert np.array_equal(ev.columns(ev.run(g, draw), 2, draw)["F"][0], col["F_kernel"][0])


@pytest.fixture(scope="module")
def catch_smoke(tmp_path_factory):
    out = tmp_path_factory.mktemp("catch_smoke")
    results = main(_catch(f"logging.output_dir={out}"))
    return out, json.loads(results.read_text().splitlines()[-1])


def test_a_catch_run_writes_its_outputs_with_the_body_columns(catch_smoke):
    out, row = catch_smoke
    for name in ("results.jsonl", "curves.jsonl", "lineage.jsonl", "best_genome.json", "population.json",
                 "clones.jsonl", "config.yaml"):
        assert (out / name).exists(), name
    assert row["world"] == "catch_v1_l4" and row["lattice"] == "hexprism" and row["L_max"] == 4 and row["abi"] == 3
    assert row["control"] == "lmax4" and row["recheck_k"] == 8 and row["generations"] == 3
    assert {"captures", "misses", "clicks", "n_S", "n_M", "n_H", "path", "mean_distance", "msg_reliance",
            "sense_reliance", "size_curve", "forks", "F_envelope", "git_rev"} <= set(row)
    assert "receptor_off" in _catch().clones.conditions  # review fix: a blind relay clicker passes the certificate
    assert "kuramoto_R" not in row  # BELL's beat statistics are not computed in CATCH
    assert set(row["forks"]) == {f"{c}@0.5" for c in _catch().clones.conditions}
    assert row["n_S"] + row["n_M"] + row["n_H"] == pytest.approx(row["n_cells"])
    curves = [json.loads(line) for line in (out / "curves.jsonl").read_text().splitlines()]
    assert all(set(LifeEval.CATCH_KEYS) <= set(c) for c in curves) and all("clones" in c for c in curves)
    clones_rows = [json.loads(line) for line in (out / "clones.jsonl").read_text().splitlines()]
    assert {c["condition"] for c in clones_rows} == set(_catch().clones.conditions)
    layout, best = Layout.load(out / "best_genome.json")
    assert layout.abi is spec.V3 and best.shape == (875,)


def test_a_catch_run_records_its_drawn_lengths_and_judges_at_the_nominal_one(catch_smoke):
    """GB11's draw in a run: every curves and lineage row records its generation's length (the evaluator's draw for
    the run seed), evals still counts genome evaluations whatever the length, the valid score is the best genome on
    lives of the nominal T, and the row adds T_choices, T_sel_mean and GB11's readout (n_half, growing)."""
    out, row = catch_smoke
    ev = setup(_catch())[3]
    curves = [json.loads(line) for line in (out / "curves.jsonl").read_text().splitlines()]
    gens = [json.loads(line) for line in (out / "lineage.jsonl").read_text().splitlines()][1:]
    Ts = [ev.draw("gen", g).worlds[0].T for g in range(3)]
    assert [c["T"] for c in curves] == [lrow["T"] for lrow in gens] == Ts and set(Ts) <= {144.0, 192.0, 288.0}
    assert row["T_choices"] == [144.0, 192.0, 288.0] and row["T_sel_mean"] == pytest.approx(np.mean(Ts))
    per_gen = 16 + 8 * 2 / 3  # 16 genomes on 3 lives, then the shortlist of 8 on 2 more, whatever the length
    expected = [row["founders_sampled"] + (g + 1) * per_gen for g in range(3)]
    assert [c["evals"] for c in curves] == pytest.approx(expected)
    _, best = Layout.load(out / "best_genome.json")
    valid = ev(best.reshape(1, -1), ev.draw("valid", 2, lives=2))  # judged lives: T = 192 whatever generation 2 drew
    assert curves[-1]["valid"] == float(valid.fitness[0]) and ev.draw("valid", 2, lives=2).worlds[0].T == 192.0
    assert 0.0 <= row["growing"] <= 1.0 and row["n_half"] > 0 and "world_over" not in row


def test_catch_arms_differ_only_in_the_stack_height():
    l4, l2 = load_config(CATCH_CFG), load_config(str(ROOT / "configs/life_catch_l2.yaml"))
    assert (spec.world(l4.life.world).L_max, spec.world(l2.life.world).L_max) == (4, 2)
    assert l4.lattice.kind == l2.lattice.kind == "hexprism" and l4.life.T == 1024 and l4.evolve.generations == 500
    assert (l4.evolve.recheck_k, l4.evolve.recheck_lives, l4.evolve.recheck_key) == (64, 4, "all")
    assert "hidden_off" in l4.clones.conditions and "hidden_off" not in l2.clones.conditions
    assert l4.clones.conditions[0] == l2.clones.conditions[0] == "contacts_off+chem_off+division_off"
    a = load_config(CATCH_CFG, ["life.world=catch_v1_l2", "life.control=lmax2",
                                f"clones.conditions={list(l2.clones.conditions)}"])
    a.logging.output_dir, a.extends = l2.logging.output_dir, l2.extends
    assert a == l2
    seeded = load_config(str(ROOT / "configs/life_catch_seeded.yaml"))
    assert seeded.evolve.seed_genome == evo.CATCH_SEED and seeded.life.control == "seeded"
    from src.life import handbuilt as hb
    layout = setup(seeded)[1]
    if hasattr(hb, "catch_reflex_genome"):
        assert torch.equal(evo.seed_genome(seeded, layout)[0], torch.as_tensor(hb.catch_reflex_genome()))
    elif hasattr(hb, "column_genome"):  # gate GB9's genome that grows the 2-cell clicker
        assert torch.equal(evo.seed_genome(seeded, layout)[0], torch.from_numpy(hb.column_genome(0)))
    else:  # the stub until the gates work provides the hand GRN seed
        with pytest.raises(NotImplementedError):
            evo.seed_genome(seeded, layout)
    from scripts.sweep import matrix

    arms = [(c, load_config(str(ROOT / c))) for c in ("configs/life_catch.yaml", "configs/life_catch_l2.yaml")]
    assert [r["run"] for r in matrix(arms, None, None, ["0"])] == ["lmax4_hexprism_sex_s0", "lmax2_hexprism_sex_s0"]


def _pilot(arms: str | None = None):
    """The pilot script in plan mode (it prints the runs and starts nothing)."""
    import os

    env = {k: v for k, v in os.environ.items() if not k.startswith("PILOT_")}
    env.update(PILOT_PLAN="1", **({"PILOT_ARMS": arms} if arms is not None else {}))
    return subprocess.run(["bash", str(ROOT / "scripts/run_catch_pilot.sh")], env=env, capture_output=True, text=True,
                          timeout=120)


def test_the_catch_pilot_matrix_is_set_per_arm():
    """scripts/run_catch_pilot.sh: arms with seed counts (PILOT_ARMS), interleaved by seed; the default runs the v1
    arms and the SPECK arms (29 runs on 4 jobs x 3 threads); bad arms are refused before anything runs."""
    script = (ROOT / "scripts/run_catch_pilot.sh").read_text()
    for part in ('ARMS=${PILOT_ARMS:-v1_l4:10 v1_l2:3 v1_seeded:3:300 speck_l4:10 speck_seeded:3:300}',
                 "v1_l4) echo configs/life_catch.yaml",
                 "v1_l2) echo configs/life_catch_l2.yaml", "v1_seeded) echo configs/life_catch_seeded.yaml",
                 "speck_l4) echo configs/life_speck.yaml", "speck_seeded) echo configs/life_speck_seeded.yaml",
                 "PILOT_GENERATIONS:-500", "PILOT_JOBS:-4", "PILOT_THREADS:-3", "NAME=catch_pilot", "scripts/sweep.py",
                 'evolve.generations="$GENERATIONS"', "scripts/aggregate.py", '--out "${ROOT}outputs"'):
        assert part in script, part
    assert subprocess.run(["bash", "-n", str(ROOT / "scripts/run_catch_pilot.sh")]).returncode == 0

    def runs(out):  # the plan's numbered rows (the last line is the count per config)
        return [line.split()[1] for line in out.splitlines() if line[:3].strip().isdigit() and "runs:" not in line]

    default = _pilot()
    assert default.returncode == 0, default.stderr
    got = runs(default.stdout)
    assert len(got) == 29 and got[:5] == ["lmax4_hexprism_sex_s0", "lmax2_hexprism_sex_s0", "seeded_hexprism_sex_s0",
                                          "speck_lmax4_hexprism_sex_s0", "speck_seeded_hexprism_sex_s0"]
    assert sum(r.startswith("lmax4_") for r in got) == 10 and sum(r.startswith("lmax2_") for r in got) == 3
    assert sum(r.startswith("seeded_") for r in got) == 3 and sum(r.startswith("speck_lmax4_") for r in got) == 10
    assert sum(r.startswith("speck_seeded_") for r in got) == 3
    tail = [f"{c}_hexprism_sex_s{s}" for s in range(3, 10) for c in ("lmax4", "speck_lmax4")]
    assert got[15:] == tail  # the two 10-seed arms finish alone
    for arm in (" seeded_hexprism", " speck_seeded_hexprism"):
        seeded = [line for line in default.stdout.splitlines() if arm in line]
        assert len(seeded) == 3 and all(line.endswith("generations=300") for line in seeded)  # the hedges run 300
    full = _pilot("v1_l4:2 speck_seeded:1:300 v1_l2:2 speck_l4:1")
    assert runs(full.stdout) == ["lmax4_hexprism_sex_s0", "speck_seeded_hexprism_sex_s0", "lmax2_hexprism_sex_s0",
                                 "speck_lmax4_hexprism_sex_s0", "lmax4_hexprism_sex_s1", "lmax2_hexprism_sex_s1"]
    gens = [line.endswith("generations=300") for line in full.stdout.splitlines()[:6]]
    assert gens == [False, True, False, False, False, False]  # name:seeds:generations sets that arm's length only
    for bad in ("v1_l4", "v1_l4:0", "v1_l4:x", "nope:2", " ", "v1_l4:2:", "v1_l4:2:0", "v1_l4:2:3:4"):
        r = _pilot(bad)  # refused before the sweep starts (the check comes before the plan)
        assert r.returncode == 2 and r.stdout == "" and r.stderr, bad


def test_the_sweep_runs_the_first_n_seeds_of_an_arm():
    from scripts.sweep import arm_spec, matrix

    assert arm_spec("configs/life_catch.yaml") == ("configs/life_catch.yaml", None, None)
    assert arm_spec("configs/life_catch.yaml:3") == ("configs/life_catch.yaml", 3, None)
    assert arm_spec("configs/life_catch.yaml:3:250") == ("configs/life_catch.yaml", 3, 250)
    assert arm_spec("/abs/a:b.yaml") == ("/abs/a:b.yaml", None, None)  # not a count
    for bad in ("configs/life_catch.yaml:0", "configs/life_catch.yaml:2:0"):
        with pytest.raises(ValueError):
            arm_spec(bad)
    l4, sd = (load_config(str(ROOT / c)) for c in ("configs/life_catch.yaml", "configs/life_catch_seeded.yaml"))
    runs = matrix([("a", l4, 3), ("b", sd, 1, 250)], None, None, ["0", "1", "2"])
    assert [r["run"] for r in runs] == ["lmax4_hexprism_sex_s0", "seeded_hexprism_sex_s0", "lmax4_hexprism_sex_s1",
                                        "lmax4_hexprism_sex_s2"]
    assert [r["generations"] for r in runs] == [None, 250, None, None]
    from scripts.sweep import command

    cmd = command(runs[1], 4, "o/x/seeded", ["evolve.generations=500", "evolve.mu=4"])
    assert cmd[-3:] == ["evolve.generations=500", "evolve.mu=4", "evolve.generations=250"]  # the arm's wins
    assert "evolve.generations=250" not in command(runs[0], 4, "o/x/l4", ["evolve.generations=500"])
    assert matrix([("a", l4, None), ("b", sd)], None, None, ["4", "7"]) == matrix([("a", l4), ("b", sd)], None, None,
                                                                                    ["4", "7"])
    with pytest.raises(ValueError, match="3 seeds asked"):
        matrix([("a", l4, 3)], None, None, ["0", "1"])
    plan = subprocess.run([str(ROOT / ".venv/bin/python"), "scripts/sweep.py", "--config",
                           "configs/life_catch.yaml:2,configs/life_catch_seeded.yaml:1", "--seeds", "5,6", "--name",
                           "x", "--plan"], cwd=ROOT, capture_output=True, text=True, timeout=120)
    assert plan.returncode == 0 and [line.split()[1] for line in plan.stdout.splitlines()[:3]] == [
        "lmax4_hexprism_sex_s5", "seeded_hexprism_sex_s5", "lmax4_hexprism_sex_s6"]
    assert not (ROOT / "logs" / "x").exists()  # a plan writes nothing


SPECK_CFG = str(ROOT / "configs/life_speck.yaml")


def test_the_speck_arms_are_v1_in_the_speck_world():
    """configs/life_speck.yaml is life_catch.yaml in the speck-gates preset catch_speck_l4 (catch_v1_l4 with sigma
    0.6 and R_cap 500), with its own label, held-out worlds and skill threshold; the SPECK seeded arm adds the same
    labelled seed genome as v1's. Both keep the T draw."""
    sp = load_config(SPECK_CFG)
    assert sp.life.world == "catch_speck_l4" and sp.life.control == "speck_lmax4" and not sp.world
    assert spec.world("catch_speck_l4") == replace(spec.world("catch_v1_l4"), name="catch_speck_l4", stage="body-s1",
                                                   sigma=0.6, R_cap=500.0, c_miss=10.0)
    a = load_config(CATCH_CFG, ["life.world=catch_speck_l4", "life.control=speck_lmax4", "life.skill_at=4.0"])
    a.life.heldout = sp.life.heldout
    a.logging.output_dir, a.extends = sp.logging.output_dir, sp.extends
    assert a == sp
    sps, v1s = load_config(str(ROOT / "configs/life_speck_seeded.yaml")), load_config(
        str(ROOT / "configs/life_catch_seeded.yaml"))
    b = load_config(SPECK_CFG, ["life.control=speck_seeded", "evolve.seed_genome=catch_reflex"])
    b.logging.output_dir, b.extends = sps.logging.output_dir, sps.extends
    assert b == sps and sps.evolve.seed_genome == v1s.evolve.seed_genome == evo.CATCH_SEED
    _, layout, _, ev = setup(load_config(SPECK_CFG, ["threads=1"]))
    w = ev.world()
    assert (w.sigma, w.R_cap, w.L_max, w.c_miss, ev.T_choices) == (0.6, 500.0, 4, 10.0, (768.0, 1024.0, 1536.0))
    held = ev.draw("heldout", 0, lives=1, overrides=list(sp.life.heldout))  # every held-out world is valid
    assert [(x.sigma, x.R_cap, x.v_t) for x in held.worlds] == [(0.6, 500.0, 0.05), (0.6, 500.0, 0.2),
                                                               (0.6, 250.0, 0.1), (0.6, 1000.0, 0.1),
                                                               (0.4, 500.0, 0.1), (1.5, 500.0, 0.1)]
    try:
        assert torch.equal(evo.seed_genome(sps, layout), evo.seed_genome(v1s, layout))
    except NotImplementedError:  # no hand GRN seed yet: both arms fail alike
        pass


def test_results_rows_name_world_overrides_and_the_length_draw():
    from src.run import life_settings

    sp, v1 = load_config(SPECK_CFG), load_config(CATCH_CFG)
    assert life_settings(sp, [{"T": 768.0}, {"T": 1536.0}]) == dict(T_choices=[768.0, 1024.0, 1536.0],
                                                                     T_sel_mean=1152.0)
    over = load_config(CATCH_CFG, ["world.sigma=0.6", "world.R_cap=500.0", "costs_life.c_miss=10.0"])
    assert life_settings(over, [])["world_over"] == "R_cap=500,c_miss=10,sigma=0.6"
    assert life_settings(v1, []) == dict(T_choices=[768.0, 1024.0, 1536.0], T_sel_mean=None)
    assert life_settings(_cfg(), [{"gen": 0}]) == {}  # BELL rows gain nothing


def test_the_per_generation_life_length_draw_is_shared_and_selection_only():
    """life.T_choices (gate GB11's switch; on in the CATCH configs): a generation's lives and its recheck lives share
    one length drawn uniformly from the list, keyed by the run seed and the generation only; the life seeds do not
    depend on it; every judged life keeps life.T, and evolution refuses a nominal T outside the choices."""
    ev = LifeEvaluator(_catch("life.T_choices=[96,192,288]"), setup(_catch())[1])
    Ts = [ev.draw("gen", g).worlds[0].T for g in range(300)]
    assert set(Ts) == {96.0, 192.0, 288.0} and Ts == [ev.draw("gen", g).worlds[0].T for g in range(300)]
    assert all(60 <= Ts.count(T) <= 140 for T in (96.0, 192.0, 288.0))  # uniform: 100 each, SD 8.2
    other = LifeEvaluator(_catch("life.T_choices=[96,192,288]", "seed=1"), setup(_catch())[1])
    assert [other.draw("gen", g).worlds[0].T for g in range(300)] != Ts  # fresh across runs
    off = LifeEvaluator(_catch("life.T_choices=null"), setup(_catch())[1])
    for g in range(6):
        d, rc = ev.draw("gen", g), recheck_draw(ev, g, 3, 2)
        assert {w.T for w in d.worlds + rc.worlds} == {Ts[g]}
        assert d.seeds == off.draw("gen", g).seeds and rc.seeds == recheck_draw(off, g, 3, 2).seeds
    for purpose in ("valid", "final", "clones", "heldout"):
        assert ev.draw(purpose, 0, lives=2).worlds[0].T == 192.0
    assert ev.world().T == 192.0 and ev.draw("founders", 0, lives=1, T=96.0).worlds[0].T == 96.0
    assert off.draw("gen", 0).worlds[0].T == 192.0 and off.T_choices == ()  # off: life.T
    with pytest.raises(ValueError):
        LifeEvaluator(_catch("life.T_choices=[96.5]"), setup(_catch())[1])  # T must be an integer
    with pytest.raises(ValueError, match="not one of life.T_choices"):
        evolve_life(_catch("life.T_choices=[96,288]"), log=lambda row: None)


def test_drawn_lengths_cut_the_same_lives_and_fitness_stays_per_unit():
    """No cell reads T, so a generation's lives at a shorter length are the first part of the same lives at a longer
    one (fate logs agree up to the cut). F is per unit of each life's own length: the window is its T and the
    extinction charge runs to its own end, so a zygote that dies at once scores about -c_live at every length."""
    _, layout, _, ev = setup(_catch())
    x = layout.random(6, torch.Generator().manual_seed(11))
    short, long = ev.draw("gen", 0, T=144.0), ev.draw("gen", 0, T=288.0)
    assert short.seeds == long.seeds
    a, b = ev.run(x, short, fate_cap=1 << 12), ev.run(x, long, fate_cap=1 << 12)
    grew = 0
    for i in range(6 * short.n):
        (ka, fa), (kb, fb) = a.fates(i), b.fates(i)
        cut = fb[:, 0] < short.worlds[0].t0 + 144.0
        assert np.array_equal(ka, kb[cut]) and np.array_equal(fa, fb[cut])
        grew += int((ka[:, 0] == 1).sum() > 1)
    assert grew > 0  # some of these lives divide before the cut
    g = torch.zeros(2, layout.size)
    a0 = layout.view(g, "a0")
    a0[0, spec.V3.K["p_die"]] = 2.0  # dies at its first tick
    a0[:, spec.V3.K["tau_m"]] = 0.0
    for T in ev.T_choices:
        d = ev.draw("gen", 0, T=T)
        col = ev.columns(ev.run(g, d), 2, d)
        w = d.worlds[0]
        assert (col["window"] == T).all() and w.T == T
        assert np.allclose(col["F"][0], col["F_kernel"][0] - w.c_live * (w.t0 + T - col["t_ext"][0]) / T, rtol=0,
                           atol=1e-15)
        assert (np.abs(col["F"][0] + w.c_live) < 1e-3).all()


def test_the_growth_readout_counts_lives_still_growing_after_half_time():
    """GB11's readout (src/run.py growth_at_half): the size at T/2 is the same life's size at T/2, read from the full
    life's fate log, and a life is growing if its size at T exceeds that by more than 10%."""
    from src.run import GROWING, growth_at_half

    _, layout, _, ev = setup(_catch())
    x = layout.random(12, torch.Generator().manual_seed(4))
    lives = 4
    for i in range(12):
        d = ev.draw("final", 0, lives=lives)
        full = ev.run(x[i: i + 1], d, fate_cap=1 << 12)
        n_end = full["n_end"]
        at_half = []
        for j in range(lives):
            k, f = full.fates(j)
            m = f[:, 0] < d.worlds[0].t0 + ev.T / 2
            at_half.append(int((k[m][:, 0] == 1).sum() - (k[m][:, 0] == 2).sum()))
        got = growth_at_half(ev, x[i: i + 1], n_end, lives)
        assert got["n_half"] == np.mean(at_half)
        assert got["growing"] == np.mean(n_end > (1 + GROWING) * np.maximum(at_half, 1))


def test_founder_sampling_can_use_its_whole_budget():
    """evolve.founder_all: sampling draws all max_init_samples even after a genome clears the bar, and the founders
    are the fittest of the whole pool (scorers first); without it sampling stops at the first batch with a scorer."""
    base = ["evolve.init_samples=32", "evolve.max_init_samples=96", "evolve.min_founder_score=-1000.0"]
    for full, used_expected in ((False, 32), (True, 96)):
        cfg = _cfg(*base, f"evolve.founder_all={str(full).lower()}")
        ev = LifeEvaluator(cfg, LAY)

        def sample(g, ev=ev, batches=iter(range(10))):
            return ev.draw("founders", next(batches), 1, 64.0)

        founders, used, info = sample_founders(cfg, ev, LAY, sample, torch.Generator().manual_seed(0),
                                               collect=(seen := []))
        assert used == used_expected == sum(len(r.fitness) for r in seen)
        best = torch.cat([r.fitness for r in seen]).max()
        assert info["best_fitness"] == float(best) and info["scoring_founders"] == founders.shape[0]
    with pytest.raises(ValueError):
        sample_founders(_cfg("evolve.founder_all=true", "evolve.max_init_samples=null"), ev, LAY, None,
                        torch.Generator().manual_seed(0))


def test_the_catch_founder_settings_are_the_recorded_tweaks():
    cfg = load_config(CATCH_CFG)
    assert list(cfg.genome.readout_std) == [0.5, 0.5] and dict(cfg.genome.input_init) == dict(is_S=2.0, is_M=2.0,
                                                                                              n_view=8.0)
    assert cfg.evolve.founder_all and cfg.evolve.max_init_samples == 16384 and cfg.life.founder_lives == 2
    assert cfg.life.extinct_charge and list(cfg.life.T_choices) == [768, 1024, 1536] and cfg.life.T == 1024  # GB11
    _, layout, _, _ = setup(cfg)
    K = spec.V3.K
    a0 = slice(*layout.slices["a0"][:2])
    mean, std = layout.init_mean[a0], layout.init_std[a0]
    assert (mean[K["b"]], mean[K["g_r"]], mean[K["kappa"]], mean[K["w0"]], mean[K["emit0"]]) == (0.0, 0.5, 1.5,
                                                                                                    0.5, 0.5)
    # review fix: the means decode as the config says (kappa 1, not 1/2; b 0 as in proposal 7)
    theta = spec.V3.decode_knobs([float(x) for x in mean])
    assert theta[K["kappa"]] == 1.0 and theta[K["b"]] == 0.0 and theta[K["g_r"]] == 0.5 and theta[K["w0"]] == 0.5
    fixed = [K[k] for k in ("p_die", "phi", "a0", "a1", "chi")]
    assert all(std[i] == 0 for i in fixed) and all(std[i] == 0.5 for i in range(spec.V3.P) if i not in fixed)
    bell = setup(_cfg())[1]  # BELL's founders are untouched
    assert torch.equal(bell.init_std, LifeLayout(LifeDims()).init_std)
