"""Open-world search: allocation-aware draws, racing, behaviour grids, exact resume, and the unchanged legacy path.

All populations and life seeds are fixed engineering fixtures (T = 16 lives), not scientific results.
"""
import copy
import hashlib
import json
import os
import subprocess
import sys
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest
import torch
from omegaconf import OmegaConf

from src import checkpoint
from src.common import load_config
from src.evolve import evolve, recheck_draw, setup
from src.genome import LIFE_DIMS_ABI3, LifeLayout
from src.life import build
from src.life.evaluate import LifeEvaluator, life_seed, task_life_seed, task_objectives
from src.open_search import plan

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "tests" / "data"
TIMES = {"t_gen", "t_eval", "t_recheck", "wall_s", "final_s", "elapsed"}
TASKS = [dict(name="dim", world="catch_speck_flash5_dim25_l4", overrides=dict(visibility_low=.375)),
         dict(name="dark", world="catch_speck_flash5_dim25_l4", overrides=dict(visibility_low=0.0))]
LAYOUT = LifeLayout(LIFE_DIMS_ABI3)


def clean(value, omit=TIMES):
    if isinstance(value, dict):
        return {k: clean(v, omit) for k, v in value.items() if k not in omit}
    if isinstance(value, list):
        return [clean(v, omit) for v in value]
    return value


def same(a, b, path="state"):
    """Exact equality of nested checkpoint states (tensors by dtype, shape and bytes)."""
    if isinstance(a, torch.Tensor):
        assert isinstance(b, torch.Tensor) and a.dtype == b.dtype and a.shape == b.shape, path
        assert a.numpy().tobytes() == b.numpy().tobytes(), path
    elif isinstance(a, dict):
        assert isinstance(b, dict) and a.keys() == b.keys(), path
        for k in a.keys() - TIMES:
            same(a[k], b[k], f"{path}.{k}")
    elif isinstance(a, (list, tuple)):
        assert type(a) is type(b) and len(a) == len(b), path
        for i, (x, y) in enumerate(zip(a, b)):
            same(x, y, f"{path}[{i}]")
    else:
        assert a == b, path


def read_log(path):
    return [json.loads(line) for line in path.read_text().splitlines()]


def evaluator_config(**allocation):
    cfg = load_config("configs/life_speck.yaml", ["threads=1", "life.abi=4", "life.T=8", "life.T_choices=null",
                                                  "life.lives=6", "life.founder_lives=4", "life.founder_T=8",
                                                  "evolve.recheck_k=0", "evolve.batch=16"])
    cfg.life.training_tasks = TASKS
    if allocation:
        cfg.evolve.allocation = allocation
    return cfg


def open_config(mode="lp"):
    cfg = load_config("configs/life_speck.yaml", [
        "threads=1", "seed=45000123", "life.abi=4", "life.T=16", "life.T_choices=[16,32]",
        "life.lives=6", "life.founder_lives=2", "life.founder_T=16", "clones.every=0",
        "evolve.generations=6", "evolve.mu=4", "evolve.lam=6", "evolve.archive_size=2",
        "evolve.recheck_k=0", "evolve.recheck_lives=0", "evolve.batch=16", "evolve.selection=epsilon_lexicase",
        "evolve.breeding=sex", "evolve.dup_rate=0.4", "evolve.del_rate=0.2", "evolve.n_mut_scale=true",
        "evolve.race_k=6", "evolve.race_lives=6", "evolve.novel_k=2",
        "logging.checkpoint_every=1", "logging.lineage=all", "world.n_max=48"])
    cfg.life.training_tasks = TASKS
    cfg.evolve.allocation = dict(mode=mode, budget=6, floor=2, cap=4, period=2, window=6, probe_top=2,
                                 probe_lives=2, novelty_window=4)
    cfg.evolve.elites = dict(shape=[2, 2], descriptors=dict(dim=["n_end", "spikes"], dark=["spikes/window", "n_end"]),
                             bounds=dict(dim=[[0, 6], [0, 40]], dark=[[0, 3], [0, 6]]), confirm_lives=2,
                             parent_share=0.5)
    return cfg


@pytest.fixture
def seeded(tmp_path):
    # A single declared engineering draw supplies all four rows; no viability filtering.
    pop = LAYOUT.random(4, torch.Generator().manual_seed(45_000_001))
    path = tmp_path / "input_population.json"
    path.write_text(json.dumps(dict(dims=LAYOUT.dims.__dict__, genomes=[LAYOUT.to_dict(r) for r in pop],
                                    ids=[73, 10, 84, 6])))
    return path


@pytest.fixture
def native_calls(monkeypatch):
    original, calls = build.run, []

    def record(worlds, seeds, **kwargs):
        calls.append(len(seeds))
        return original(worlds, seeds, **kwargs)

    monkeypatch.setattr(build, "run", record)
    return calls


def search(cfg, out, **kwargs):
    out.mkdir(parents=True, exist_ok=True)
    states = []
    result = evolve(cfg, log=lambda row: None, out=out,
                    checkpoint=lambda state: states.append(copy.deepcopy(state)), **kwargs)
    return result, states


# ------------------------------------------------------------------------------------------- legacy path unchanged
GOLDEN_OVERRIDES = ["threads=1", "life.T=16", "life.founder_T=16", "evolve.mu=4", "evolve.lam=6",
                    "evolve.archive_size=4", "evolve.recheck_k=8", "evolve.generations=1", "evolve.batch=16",
                    "world.n_max=48", "life.capability_panel.lives=1", "life.capability_panel.top=2",
                    "logging.checkpoint_every=1"]


def multitask_first_generation(out):
    """configs/multitask.yaml scaled down (same tasks, selection, archive and recheck rules) for one generation."""
    cfg = load_config("configs/multitask.yaml", GOLDEN_OVERRIDES)
    _, layout, _, _ = setup(cfg)
    data = np.load(DATA / "multitask_legacy_inputs.npz")
    for name in ("population", "archive"):
        rows = torch.from_numpy(data[name])
        (out / f"{name}.json").write_text(json.dumps(dict(dims=layout.dims.__dict__, ids=list(range(len(rows))),
                                                          genomes=[layout.to_dict(r) for r in rows])))
    cfg.evolve.seed_population, cfg.evolve.seed_archive = str(out / "population.json"), str(out / "archive.json")
    run = out / "run"
    run.mkdir()
    states, curves = [], []
    evolve(cfg, log=lambda row: curves.append(row) if "gen" in row else None, out=run,
           checkpoint=lambda s: states.append(copy.deepcopy(s)))
    final = states[-1]
    omit = TIMES | {"population_file"}
    lineage = [clean(json.loads(line), omit) for line in (run / "lineage.jsonl").read_text().splitlines()]
    return {"generation": final["generation"], "search_lives": curves[-1]["search_lives"],
            "curves": json.loads(json.dumps(clean(curves, omit))),
            "tensors": {k: hashlib.sha256(v.numpy().tobytes()).hexdigest() for k, v in sorted(final.items())
                        if isinstance(v, torch.Tensor)},
            "lineage_sha256": hashlib.sha256(json.dumps(lineage, sort_keys=True).encode()).hexdigest(),
            "population_g1_sha256": hashlib.sha256((run / "populations/g000001.json").read_bytes()).hexdigest()}


def test_multitask_first_generation_is_bitwise_the_pre_allocation_code(tmp_path, monkeypatch):
    """The golden was produced by the code before allocation-aware search existed (commit 9cead4a)."""
    import src.open_search

    monkeypatch.setattr(src.open_search, "evolve_open", lambda *a, **k: pytest.fail("legacy config took new path"))
    golden = json.loads((DATA / "multitask_legacy_golden.json").read_text())
    assert json.loads(json.dumps(multitask_first_generation(tmp_path), sort_keys=True)) == golden


# ------------------------------------------------------------------------------------------- draws and seed keys
def test_seed_keys_follow_task_and_replicate_not_position():
    ev = LifeEvaluator(evaluator_config(mode="uniform"), LAYOUT)
    a = ev.draw_allocated("gen", 3, [2, 3])
    b = ev.draw_allocated("gen", 3, [5, 3])
    assert a.tasks == ("dim",) * 2 + ("dark",) * 3 and b.tasks == ("dim",) * 5 + ("dark",) * 3
    assert a.seeds[2:] == b.seeds[5:]  # dark's seeds do not move when dim's count changes
    assert a.seeds[:2] == b.seeds[:2]  # dim's first replicates are the same lives
    assert a.seeds == tuple(task_life_seed(ev.seed, "gen", 3, t, r) for t, n in (("dim", 2), ("dark", 3))
                            for r in range(n))
    # Seeds follow the task name, not its position in the list.
    swapped = evaluator_config(mode="uniform")
    swapped.life.training_tasks = list(reversed(TASKS))
    c = LifeEvaluator(swapped, LAYOUT).draw_allocated("gen", 3, [3, 2])
    assert c.tasks == ("dark",) * 3 + ("dim",) * 2 and c.seeds == a.seeds[2:] + a.seeds[:2]
    # Purposes never share lives: race, probe and confirmation lives are disjoint from the generation's.
    gen = set(ev.draw_allocated("gen", 3, [8, 8]).seeds)
    for purpose, index in (("race", 3), ("probe", 0), ("elite_confirm", 3), ("gen", 4), ("founders", 3)):
        assert not gen & set(ev.draw_allocated(purpose, index, [8, 8]).seeds), purpose
    assert not gen & {life_seed(ev.seed, "gen", 3, i) for i in range(16)}
    # A draw without a vector is an even keyed split; every task keeps at least one life.
    assert ev.draw("gen", 3) == ev.draw_allocated("gen", 3, [3, 3])
    assert ev.draw("founders", 2, lives=5).tasks == ("dim",) * 3 + ("dark",) * 2
    with pytest.raises(ValueError, match="at least one life per task"):
        ev.draw("gen", 3, lives=1)
    with pytest.raises(ValueError, match="every training task"):
        ev.draw_allocated("gen", 3, [0, 0])
    with pytest.raises(ValueError, match="every training task"):
        ev.draw_allocated("gen", 3, [1, 1, 1])


def test_keyed_envelope_physics_follow_the_life_not_its_position():
    cfg = evaluator_config(mode="uniform")
    cfg.envelope = dict(enabled=True, delay_sd=[0.0, 0.5], jit=[0.0, 0.3])
    ev = LifeEvaluator(cfg, LAYOUT)
    a, b = ev.draw_allocated("gen", 1, [1, 2]), ev.draw_allocated("gen", 1, [4, 2])
    assert a.worlds[1:] == b.worlds[4:] and a.worlds[0] == b.worlds[0]
    assert len({w.delay_sd for w in b.worlds}) == len(b.worlds)  # every life has its own physics
    assert ev.draw_allocated("race", 1, [1, 2], envelope=False).worlds[0].delay_sd == ev.world().delay_sd


def test_allocated_objectives_are_equal_weight_task_means_in_explicit_order():
    ev = LifeEvaluator(evaluator_config(mode="uniform"), LAYOUT)
    draw = ev.draw_allocated("gen", 0, [1, 3])
    scores = torch.tensor([[4., 1., 2., 3.], [0., 10., 10., 10.]], dtype=torch.float64)
    result = SimpleNamespace(trial_scores=scores)
    means = task_objectives(result, draw, ev.training_task_names)
    assert means.tolist() == [[4., 2.], [0., 10.]]
    assert means.mean(1).tolist() == [3., 5.]  # not the allocation-weighted 2.5 and 7.5
    assert task_objectives(result, draw, ("dark", "dim")).tolist() == [[2., 4.], [10., 0.]]
    only_dark = draw.select([1, 2, 3])
    with pytest.raises(ValueError, match="every task"):
        task_objectives(SimpleNamespace(trial_scores=scores[:, 1:]), only_dark, ev.training_task_names)
    with pytest.raises(ValueError, match="every task"):
        task_objectives(result, draw, ("dim",))


def test_every_draw_path_builds_worlds_from_its_own_life_seed():
    """``_life_world`` is the per-life world hook: a stub makes each world carry its seed, so any draw that
    replaced seeds after building worlds (or skipped the hook) would show a mismatch."""
    def stamp(ev):
        original = ev._life_world
        seen = []

        def hook(task, T, seed):
            seen.append(seed)
            return replace(original(task, T, seed), t0=float(seed % 997))
        ev._life_world = hook
        return seen

    def check(draw):
        assert [w.t0 for w in draw.worlds] == [float(s % 997) for s in draw.seeds]

    legacy = LifeEvaluator(evaluator_config(), LAYOUT)  # weighted cycle, flat seeds
    stamp(legacy)
    for draw in (legacy.draw("gen", 2), legacy.draw("founders", 1, lives=4), recheck_draw(legacy, 2, 6, 2),
                 legacy.draw_tasks("panel", 0, TASKS, 2, seed=61_017_000),
                 legacy.draw_tasks("confirm", 200, TASKS, 2, seed=61_018_900, keyed=True)):
        check(draw)
    assert legacy.draw_tasks("panel", 0, TASKS, 2, seed=5).seeds == tuple(life_seed(5, "panel", 0, i)
                                                                            for i in range(4))
    keyed = LifeEvaluator(evaluator_config(mode="lp", probe_lives=2), LAYOUT)
    seen = stamp(keyed)
    for draw in (keyed.draw("gen", 2), keyed.draw("founders", 1), keyed.draw_allocated("gen", 2, [3, 1]),
                 keyed.draw_allocated("race", 2, [0, 2]), keyed.draw_allocated("probe", 0, [2, 0], seed=9)):
        check(draw)
    assert len(seen) == 6 + 6 + 4 + 2 + 2  # an unsized founder draw has life.lives lives
    from scripts import confirm_multitask
    check(confirm_multitask.panel(legacy, TASKS, {"seed": 61_018_900}, 100, 2))


def test_per_life_columns_come_from_the_ledger(monkeypatch):
    ev = LifeEvaluator(evaluator_config(mode="uniform"), LAYOUT)
    with pytest.raises(ValueError, match="unknown ledger columns"):
        ev.request_columns(["captures", "no_such_column"])
    ev.request_columns(["captures", "window", "n_end"])
    genomes = LAYOUT.random(2, torch.Generator().manual_seed(4))
    draw = ev.draw_allocated("gen", 0, [1, 2])
    result = ev(genomes, draw)
    col = ev.columns(ev.run(genomes, draw), 2, draw)
    assert result.life_columns.shape == (2, 3, 3)
    for j, name in enumerate(("captures", "window", "n_end")):
        assert np.array_equal(result.life_columns[:, :, j].numpy(), col[name])
    ev.request_columns([])
    assert ev(genomes, draw).life_columns.shape == (2, 3, 0)


# ------------------------------------------------------------------------------------------- the open-world loop
def test_open_search_three_plus_resume_three_is_six_and_counts_actual_lives(tmp_path, seeded, native_calls):
    cfg = open_config("lp")
    cfg.evolve.seed_population = str(seeded)
    full, full_states = search(cfg, tmp_path / "full")
    part, split_states = search(cfg, tmp_path / "split", stop_after=3)
    assert not part["complete"] and split_states[-1]["generation"] == 3
    resumed, final_states = search(cfg, tmp_path / "split", resume=split_states[-1])
    assert full["complete"] and resumed["complete"]
    same(full_states[-1], final_states[-1])
    assert clean(read_log(tmp_path / "full/lineage.jsonl")) == clean(read_log(tmp_path / "split/lineage.jsonl"))
    for name in ("g000000.json", "g000006.json"):
        assert ((tmp_path / "full/populations" / name).read_bytes()
                == (tmp_path / "split/populations" / name).read_bytes())
    # Actual lives: the full run plus the split run (first half, then the rest) is every native life twice.
    assert sum(native_calls) == 2 * full["search_lives"]
    assert sum(full_states[-1]["lives"].values()) == full["search_lives"] and full_states[-1]["lives"]["founders"] == 0

    rows = [r for r in read_log(tmp_path / "full/lineage.jsonl") if "gen" in r]
    curves = full["curves"]
    elite_ids = set()
    for row, curve in zip(rows, curves):
        L = row["allocation"]
        assert sum(L) == 6 and min(L) >= 2 and max(L) <= 4 and curve["allocation"] == L
        assert row["tasks"] == ["dim"] * L[0] + ["dark"] * L[1]
        race = row["race"]
        assert race["allocation"] == L and len(race["seeds"]) == 6  # race_lives == budget: the same allocation
        assert not set(race["seeds"]) & set(row["seeds"])
        assert len(race["ids"]) <= 6 + 2 and set(race["novel_ids"]) <= set(race["ids"])
        assert set(row["survivors"]) | set(row["archive_ids"]) <= set(race["ids"])
        elite_children = [c for c in row["children"] if "pa_elite" in c]
        assert len(elite_children) == (3 if elite_ids else 0)  # parent_share 0.5 of 6 children
        assert {c["pa"] for c in elite_children} <= elite_ids
        assert curve["elite_parent_draws"] == len(elite_children)
        for a in row["elites"]["admissions"]:
            elite_ids.add(a["id"])
        for e in row["elites"]["events"]:
            assert e["median"] is not None and isinstance(e["confirmed"], bool)
        assert ("allocator" in curve) == (row["gen"] % 2 == 0)
        assert ("probe" in curve) == ((row["gen"] + 1) % 2 == 0)
        assert curve["mean_fitness"] == pytest.approx(np.mean(row["fitness"]))
        assert np.allclose(np.mean(row["task_F"], axis=1), row["fitness"], rtol=0, atol=1e-12)
    assert any(r["elites"]["admissions"] for r in rows)
    assert any(c["ops"].get("dup") for r in rows for c in r["children"])  # duplication composes with the rest
    probes = full_states[-1]["allocator"]["probes"]
    assert [p[0] for p in probes] == [2, 4, 6] and all(len(p[1]) == 2 for p in probes)
    saved = json.loads((tmp_path / "full/populations/g000006.json").read_text())
    assert set(saved["elites"]) == {"dim", "dark"} and saved["allocation"]["tasks"] == ["dim", "dark"]


def test_open_search_native_lives_equal_counted_lives(tmp_path, seeded, native_calls):
    cfg = open_config("uniform")
    cfg.evolve.seed_population = str(seeded)
    cfg.evolve.generations = 4
    cfg.life.capability_panel = dict(tasks=TASKS, every=2, top=2, lives=1, seed=61_017_000)
    result, states = search(cfg, tmp_path / "run")
    assert sum(native_calls) == result["search_lives"] + result["panel_lives"]
    lives = states[-1]["lives"]
    assert lives["gen"] > 0 and lives["race"] > 0 and lives["probe"] == 2 * 2 * 2 * 2
    assert all(c["allocation"] == [3, 3] for c in result["curves"])  # uniform: equal lives whatever is measured
    observations = [r for r in read_log(tmp_path / "run/lineage.jsonl") if r.get("event") == "capability_panel"]
    assert [r["generation"] for r in observations] == [0, 2, 4]


def test_open_search_cli_checkpoint_restores_logs_and_final_artifacts(tmp_path, seeded):
    cfg = open_config("lp")
    cfg.evolve.seed_population = str(seeded)
    cfg.evolve.generations = 4
    obj = OmegaConf.to_container(cfg, resolve=True)
    obj.pop("extends", None)
    config_path = tmp_path / "config.yaml"
    OmegaConf.save(OmegaConf.create(obj), config_path)
    full, split = tmp_path / "full/run", tmp_path / "split/run"

    def run(out, *flags):
        env = dict(os.environ, ATEN_CPU_CAPABILITY="avx2", OMP_WAIT_POLICY="PASSIVE",
                   OMP_NUM_THREADS="1", MKL_NUM_THREADS="1", OPENBLAS_NUM_THREADS="1")
        cmd = [sys.executable, "-m", "src.run", "--config", str(config_path), *flags, f"logging.output_dir={out}"]
        done = subprocess.run(cmd, cwd=ROOT, env=env, capture_output=True, text=True, timeout=120)
        assert done.returncode == 0, done.stdout + done.stderr

    run(full)
    run(split, "--stop-after", "1")  # stop inside an allocation block (period 2)
    middle = checkpoint.load(split / "checkpoint.pt")
    assert middle["state"]["generation"] == 1 and middle["state"]["family_search_version"] == 2
    assert middle["state"]["allocator"]["allocation"] == [3, 3] and middle["state"]["elites"]["grids"]
    for name in checkpoint.LOGS:
        with (split / name).open("a") as fh:
            fh.write('{"interrupted":')
    run(split, "--resume")
    for name in (*checkpoint.LOGS, "results.jsonl"):
        assert clean(read_log(full / name)) == clean(read_log(split / name)), name
    for name in ("population.json", "best_genome.json", "determinism.json"):
        assert (full / name).read_bytes() == (split / name).read_bytes(), name
    a, b = (checkpoint.load(p / "checkpoint.pt")["state"] for p in (full, split))
    same(a, b)
    result = read_log(full / "results.jsonl")[0]
    assert result["task_names"] == ["dim", "dark"] and result["search_lives"] == sum(a["lives"].values())


# ------------------------------------------------------------------------------------------- configuration
ARMS = {"U": ("uniform", 0.0, 0.0), "LP": ("lp", 0.0, 0.0), "LPD": ("lp", 0.02, 0.01)}


def test_pilot_arms_share_everything_but_allocation_mode_and_duplication():
    resolved = {}
    for arm, (mode, dup, dele) in ARMS.items():
        cfg = load_config(f"configs/open_worlds_pilot_{arm}.yaml")
        _, layout, _, ev = setup(cfg)
        alloc, elites, race_k, race_lives, novel_k = plan(cfg, ev, layout)
        assert alloc.mode == mode and (alloc.budget, alloc.floor, alloc.cap, alloc.period, alloc.window) == (
            24, 2, 8, 5, 30)
        assert (race_k, race_lives, novel_k) == (96, 24, 16)
        assert [g.shape for g in elites.grids] == [[4, 4]] * len(ev.training_task_names)
        assert elites.parent_share == 0.25 and elites.confirm_lives == 8
        e = cfg.evolve
        assert (e.mu, e.archive_size, e.lam, e.generations, cfg.logging.checkpoint_every) == (32, 64, 224, 100, 5)
        assert (e.dup_rate, e.del_rate, e.recheck_k) == (dup, dele, 0)
        assert ev.allocated and set(ev.ledger_names) == set(elites.columns)
        obj = OmegaConf.to_container(cfg, resolve=True)
        obj["evolve"]["allocation"].pop("mode")
        for key in ("dup_rate", "del_rate"):
            obj["evolve"].pop(key)
        obj["logging"].pop("output_dir")
        obj.pop("extends")
        resolved[arm] = obj
    assert resolved["U"] == resolved["LP"] == resolved["LPD"]


@pytest.mark.parametrize("changes,error", [
    ({"evolve.recheck_k": 8, "evolve.recheck_lives": 2}, "races instead of rechecking"),
    ({"evolve.race_k": 3}, "at least mu"),
    ({"evolve.race_lives": 0}, "both race_k and race_lives"),
    ({"evolve.allocation.budget": 3}, "floor"),
    ({"evolve.elites.descriptors.dim": ["captures", "no_such_column"]}, "unknown ledger columns"),
    ({"evolve.elites": None}, "novel_k needs"),
])
def test_invalid_open_settings_fail_before_native_calls(seeded, monkeypatch, changes, error):
    cfg = open_config()
    cfg.evolve.seed_population = str(seeded)
    for key, value in changes.items():
        OmegaConf.update(cfg, key, value, merge=False)
    monkeypatch.setattr(build, "run", lambda *a, **kw: pytest.fail("invalid config reached native evaluation"))
    with pytest.raises(ValueError, match=error):
        evolve(cfg, log=lambda row: None)


def test_open_settings_without_allocation_or_with_weights_are_refused(seeded, monkeypatch):
    monkeypatch.setattr(build, "run", lambda *a, **kw: pytest.fail("invalid config reached native evaluation"))
    cfg = open_config()
    cfg.evolve.seed_population = str(seeded)
    cfg.evolve.allocation = None
    with pytest.raises(ValueError, match="need evolve.allocation"):
        evolve(cfg, log=lambda row: None)
    weighted = open_config()
    weighted.life.training_tasks = [dict(TASKS[0], weight=2), TASKS[1]]
    with pytest.raises(ValueError, match="weights must be 1"):
        evolve(weighted, log=lambda row: None)


def test_one_generation_of_behaviour_grids_on_synthetic_scores():
    """Incumbent reuse and re-evaluation, running means, paired replacement, empty-cell fills, the median screen and
    a paired confirmation of a new ability, with a mocked evaluator (score = genome[0] + 0.1 * life)."""
    from src.elites import Elites
    from src.life.evaluate import LifeDraw
    from src.open_search import update_elites

    def labelled(tasks):
        return LifeDraw(tuple(range(len(tasks))), (None,) * len(tasks), tuple(tasks))

    calls = []

    def evaluate(genomes, draw, what, kind):
        calls.append((kind, len(genomes), draw.n))
        return SimpleNamespace(trial_scores=genomes[:, :1].double() + 0.1 * torch.arange(draw.n, dtype=torch.float64))

    def draw_allocated(purpose, index, vec, T=None, envelope=None):
        return labelled([t for t, n in zip(("a", "b"), vec) for _ in range(n)])

    ev = SimpleNamespace(training_task_names=("a", "b"), draw_allocated=draw_allocated)
    elites = Elites(dict(shape=[2, 2], descriptors=dict(a=["x", "y"]), bounds=dict(a=[[0, 2], [0, 2]]),
                         confirm_lives=2), ("a", "b"), size=3, genes=1)
    grid = elites.grids[0]
    e0, e1 = torch.tensor([1.0, 0, 0]), torch.tensor([3.0, 1, 0])
    grid.place(0, e0, 100, 7, torch.tensor([5]), [1.0, 1.0], 0, 64)
    grid.place(1, e1, 101, 8, torch.tensor([6]), [3.0, 3.0], 0, 64)
    everyone = torch.stack([e0, torch.tensor([1.5, 0, 0]), torch.tensor([5.0, 3, 0]), torch.tensor([0.5, 1, 0]),
                            torch.tensor([0.2, 2, 0])])
    shared = [[1.0, 1.1, 0.9], [1.5, 1.6, 1.4], [5.0, 5.0, 5.0], [0.5, 0.5, 0.5], [0.2, 0.2, 0.2]]
    cell_xy = {0: (0.5, 0.5), 1: (0.5, 1.5), 2: (1.5, 0.5), 3: (1.5, 1.5)}
    xy = [cell_xy[int(c)] for c in everyone[:, 1]]
    res = SimpleNamespace(trial_scores=torch.tensor([s + [0.0] for s in shared], dtype=torch.float64),
                          life_columns=torch.tensor([[p] * 4 for p in xy], dtype=torch.float64))
    draw = labelled(["a", "a", "a", "b"])
    eligible = torch.arange(5)
    task_lives = [np.array([0, 1, 2]), np.array([3])]
    desc = elites.describe(grid, res.life_columns.numpy()[:, :3, :])
    described = [(grid.cells(desc), res.trial_scores.numpy()[:, :3].mean(1))]
    assert described[0][0].tolist() == [0, 0, 3, 1, 2]
    ids = torch.arange(10, 15)
    log = update_elites(ev, elites, 4, 16.0, False, everyone, ids, ids + 100, torch.full((5, 1), 9), res, draw,
                        task_lives, eligible, described, None, None, None, evaluate)
    # Incumbent e0 is candidate row 0 (reused); e1 relives the task's three lives (score 3.0, 3.1, 3.2).
    assert calls == [("elite", 1, 3), ("confirm", 2, 2)]
    assert float(grid.value[1]) == pytest.approx((2 * 3.0 + 9.3) / 5) and int(grid.count[1]) == 5
    admitted = {a["cell"]: a for a in log["admissions"]}
    assert set(admitted) == {0, 2, 3}  # row 3 (cell 1) is far below e1; row 0 is e0 itself and never challenges
    assert admitted[0]["replaced"] == 100 and admitted[0]["id"] == 11 and admitted[0]["d"] == pytest.approx(0.5)
    assert admitted[2]["replaced"] is None and admitted[3]["replaced"] is None
    assert int(grid.ids[0]) == 11 and float(grid.value[0]) == pytest.approx(1.5) and int(grid.breeds[0]) == 111
    # Only the new cell at or above the median of the cells filled before (1.0 and 3.06) is checked, against the
    # lower-median elite e0 on two fresh paired lives (5.0, 5.1 against 1.0, 1.1).
    assert log["events"] == [dict(task="a", cell=3, id=12, reference=100, median=pytest.approx((1.0 + 3.06) / 2),
                                  d=pytest.approx(4.0), confirmed=True)]
    assert elites.events == [[4, 0, 3, 12]]
    assert float(grid.value[3]) == pytest.approx((15.0 + 10.1) / 5) and int(grid.count[3]) == 5
    assert elites.novelty_counts(5, 10) == [1, 0]
