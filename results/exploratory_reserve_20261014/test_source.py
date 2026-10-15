"""AH synthetic selection/ownership checks; no real genotypes, kernel or life calls."""

import ast
import copy
import importlib.util
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest
import torch

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))


def load(name, filename):
    spec = importlib.util.spec_from_file_location(name, HERE / filename)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


A = load("reserve_adapter", "reserve_adapter.py")
P = load("ah_prepare", "prepare.py")
S = load("ah_search", "search.py")
B = load("run_budgeted", "run_budgeted.py")
M = load("ah_measure", "measure.py")


@dataclass
class Eval:
    fitness: torch.Tensor
    trial_scores: torch.Tensor


def native_fixture():
    """Execute only these four pure native functions; never import the engine."""
    names = {"rank_desc", "rows", "pooled", "recheck"}
    source = ROOT / "src/evolve.py"
    tree = ast.parse(source.read_text())
    selected = [node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name in names]
    space = {
        "torch": torch,
        "np": np,
        "time": time,
        "Eval": Eval,
        "recheck_draw": lambda ev, g, base, lives: SimpleNamespace(n=lives, generation=g),
    }
    exec(compile(ast.Module(body=selected, type_ignores=[]), str(source), "exec"), space)
    records = []

    class Lineage:
        def write(self, row):
            records.append(copy.deepcopy(row))

    native = SimpleNamespace(
        **{name: space[name] for name in names}, recheck_draw=space["recheck_draw"], Lineage=Lineage
    )
    # Extracted functions retain a globals dict; dispatch proxies mirror the real module's replacement semantics.
    originals = dict(space)
    for name in ("rank_desc", "recheck_draw", "rows", "pooled"):
        space[name] = lambda *args, _name=name, **kwargs: getattr(native, _name)(*args, **kwargs)
    native._originals, native.records = originals, records
    return native


def values(g, ties=False):
    base = torch.zeros(256, dtype=torch.float64) if ties else torch.arange(256, dtype=torch.float64).flip(0)
    # Values at different scales also exercise concatenation-mean versus reassociated means.
    scores = base[:, None] + torch.tensor([0.1, 0.0, -0.1], dtype=torch.float64)
    if ties:
        scores.zero_()
    return Eval(scores.mean(1), scores)


def generation(native, generator, g, parents, *, ties=False):
    everyone = torch.arange(256, dtype=torch.float64)[:, None]  # Synthetic row indices only, not genotypes.
    initial = values(g, ties)
    calls = []

    def ev(rows, draw):
        calls.append((len(rows), draw.n))
        f = initial.fitness[rows[:, 0].long()]
        trial = f[:, None].repeat(1, 4)
        return Eval(trial.mean(1), trial)

    native.rank_desc(initial.fitness, generator)  # Existing evolve_life diagnostic call.
    result = native.recheck(ev, everyone, initial, g, 32, 64, 4, "all", generator)
    child_ids = list(range(32 + 224 * g, 32 + 224 * (g + 1)))
    all_ids = parents + child_ids
    survivors = [all_ids[i] for i in result["order"].tolist()]
    native.Lineage().write({"gen": g, "children": [{"id": i} for i in child_ids], "survivors": survivors})
    assert calls == [(64, 4)]
    return survivors, result


@pytest.mark.parametrize("ties", [False, True])
def test_control_calls_original_with_identical_tie_rng(ties):
    plain, adapted = native_fixture(), native_fixture()
    ga, gb = (torch.Generator().manual_seed(123) for _ in range(2))
    parents = list(range(32))
    expected, a = generation(plain, ga, 0, parents, ties=ties)
    with A.installed(adapted, 0, "control"):
        actual, b = generation(adapted, gb, 0, parents, ties=ties)
    assert actual == expected and torch.equal(ga.get_state(), gb.get_state())
    for key in ("order", "shortlist", "pick"):
        assert torch.equal(a[key], b[key])
    assert torch.equal(a["chosen"].trial_scores, b["chosen"].trial_scores)
    meta = adapted.records[0]["exploratory_reserve"]
    assert not meta["active"] and meta["reserve_indices"] == []
    assert [x["size"] for x in meta["ranking_calls"]] == [256, 256, 64]
    expected_pool = plain._originals["pooled"](plain.rows(values(0, ties), a["shortlist"]), a["res"])
    assert meta["ranking_calls"][2]["fitness"] == expected_pool.fitness.tolist()


def test_uniform_domain_and_deterministic_fresh_indices():
    for g in range(4):
        indices = A.reserve_indices(0, g)
        assert indices == A.reserve_indices(0, g)
        assert len(set(indices)) == 2 and all(32 <= x < 256 for x in indices)
    with pytest.raises(ValueError):
        A.reserve_indices(-1, 0)


def test_rejection_sampling_rejects_biased_tail(monkeypatch):
    real = A.hashlib.sha256
    draws = iter([2**64 - 1, 0, 1])

    def sha(data):
        if data.startswith(b"cell-dev:AH:reserve:v1|"):
            return SimpleNamespace(digest=lambda: next(draws).to_bytes(8, "little") + bytes(24))
        return real(data)

    monkeypatch.setattr(A.hashlib, "sha256", sha)
    assert A.reserve_indices(0, 0) == [32, 34]


@pytest.mark.parametrize("ties", [False, True])
def test_reserve_exact_exclusions_order_and_final_ordinary(ties):
    native = native_fixture()
    generator = torch.Generator().manual_seed(55)
    parents = list(range(32))
    with A.installed(native, 0, "reserve"):
        for g in range(4):
            parents, result = generation(native, generator, g, parents, ties=ties)
            meta = native.records[-1]["exploratory_reserve"]
            full = meta["ranking_calls"][1]["order"]
            pooled = meta["ranking_calls"][2]["order"]
            protected = A.reserve_indices(0, g) if g < 3 else []
            normal = [i for i in full if i not in protected][: 64 - len(protected)]
            short = [i for i in full if i in set(protected + normal)]
            protected_pos = {j for j, i in enumerate(short) if i in protected}
            ordinary_pos = [i for i in pooled if i not in protected_pos][: 32 - len(protected)]
            picks = [i for i in pooled if i in protected_pos | set(ordinary_pos)]
            assert meta["shortlist_indices"] == short
            assert meta["pick_positions"] == picks
            assert len(set(meta["survivor_indices"])) == 32
            assert meta["reserve_indices"] == protected
            assert len(meta["candidate_ids"]) == len(meta["base_F"]) == 256
            assert meta["ranking_calls"][0]["fitness"] == meta["ranking_calls"][1]["fitness"] == meta["base_F"]
            pooled_fit = meta["ranking_calls"][2]["fitness"]
            assert result["chosen"].fitness.tolist() == [pooled_fit[i] for i in picks]
            assert meta["survivor_indices"][0] == short[pooled[0]]
            if g == 3:
                assert picks == pooled[:32] and short == full[:64]


def test_synthetic_restart_matches_uninterrupted_and_rng_state():
    full, split = native_fixture(), native_fixture()
    a, b = (torch.Generator().manual_seed(81) for _ in range(2))
    parents = list(range(32))
    with A.installed(full, 0, "reserve"):
        for g in range(4):
            parents, _ = generation(full, a, g, parents, ties=True)
    parents = list(range(32))
    with A.installed(split, 0, "reserve"):
        for g in range(2):
            parents, _ = generation(split, b, g, parents, ties=True)
    saved_rng = b.get_state().clone()
    saved_parents = list(parents)
    resumed = torch.Generator()
    resumed.set_state(saved_rng)
    with A.installed(split, 0, "reserve", parent_ids=saved_parents):
        for g in range(2, 4):
            parents, _ = generation(split, resumed, g, parents, ties=True)
    assert split.records == full.records
    assert torch.equal(a.get_state(), resumed.get_state())


def test_adapter_restore_on_exception():
    native = native_fixture()
    old = (native.rank_desc, native.recheck, native.Lineage.write)
    with pytest.raises(RuntimeError):
        with A.installed(native, 0, "reserve"):
            raise RuntimeError("synthetic failure")
    assert (native.rank_desc, native.recheck, native.Lineage.write) == old


def test_identity_calls_original_once_and_binds_config():
    calls = []
    base = {"golden": "synthetic", "sources": {}}
    configured = A.selection_identity("reserve")
    fn = S.one_identity(lambda: calls.append(1) or base, base, configured, "reserve")
    assert fn() == dict(base, external_selection=configured) and calls == [1]
    with pytest.raises(ValueError, match="exactly one"):
        fn()
    for field in ("mode", "policy_sha256", "source_pins"):
        wrong = copy.deepcopy(configured)
        wrong[field] = "changed"
        with pytest.raises(ValueError, match="adapter/config"):
            A.extended_identity(base, wrong, "reserve")


def test_checkpoint_config_identity_retains_adapter():
    from omegaconf import OmegaConf

    tree = ast.parse((ROOT / "src/checkpoint.py").read_text())
    fn = next(x for x in tree.body if isinstance(x, ast.FunctionDef) and x.name == "config_identity")
    space = {"OmegaConf": OmegaConf}
    exec(compile(ast.Module(body=[fn], type_ignores=[]), "config_identity", "exec"), space)
    cfg = P.search_config("reserve", 0, "synthetic.json")
    result = space["config_identity"](cfg)
    assert result["exploratory_reserve"] == A.selection_identity("reserve")
    changed = OmegaConf.create(OmegaConf.to_container(cfg, resolve=True))
    changed.exploratory_reserve.policy_sha256 = "different"
    assert result != space["config_identity"](changed)


def test_matched_configuration_scope_and_counts():
    from omegaconf import OmegaConf

    configs = [P.search_config(run, 0, "synthetic.json") for run in P.RUNS]
    a, b = [OmegaConf.to_container(c, resolve=True) for c in configs]
    for item in (a, b):
        item["logging"].pop("output_dir")
        item.pop("exploratory_reserve")
    assert a == b
    cfg = configs[0]
    assert (cfg.evolve.mu, cfg.evolve.lam, cfg.life.lives, cfg.evolve.recheck_k, cfg.evolve.recheck_lives) == (
        32,
        224,
        3,
        64,
        4,
    )
    assert cfg.life.abi == 3 and cfg.life.T == 1024 and cfg.life.T_choices is None
    assert cfg.evolve.random_ties and cfg.evolve.recheck_key == "all" and cfg.evolve.heldout_every == 4
    assert (cfg.life.final_top, cfg.life.final_lives, cfg.life.final_fork_lives, cfg.life.valid_lives) == (1, 2, 0, 16)
    assert not cfg.life.heldout and not cfg.life.size_curve and not cfg.clones.every and not cfg.clones.conditions
    assert cfg.evolve.dup_rate == cfg.evolve.del_rate == 0 and cfg.life.extinct_charge and cfg.life.fast_kernel
    assert 2 * (4 * (256 * 3 + 64 * 4) + 2 * 16 + 3 * 2) + 3 * 512 + 6 == 9810


def test_first_preparation_guard_and_no_unregistered_access(monkeypatch, tmp_path):
    monkeypatch.setattr(P, "STUDY", tmp_path)
    with pytest.raises(FileNotFoundError, match="registration"):
        P.prepare()
    assert not list(tmp_path.iterdir())
    (tmp_path / "generation_claim.json").write_text("{}")
    with pytest.raises(ValueError, match="first preparation"):
        P.prepare()


def test_cost_and_fixed_phase_caps():
    rates = [0.2] * 65
    p = P.cost_projection(rates)
    assert p["startup_search_projection"] == 180 + 1.5 * 8268 * 0.2
    assert p["confirmation_projection"] == 180 + 1.5 * 512 * 5 * 0.2
    assert p["feasible"] and not P.cost_projection([1.0] * 65)["feasible"]
    assert B.budget_reason("search", 3389) is None and B.budget_reason("search", 3390) == "search_reserve_limit"
    assert B.budget_reason("confirmation", 5390) == "cpu_budget_exhausted"


@pytest.mark.parametrize("bad", [0.0, -1.0, float("nan"), float("inf")])
def test_bad_historical_cost_rejected(bad):
    with pytest.raises(ValueError):
        P.cost_projection([0.1] * 64 + [bad])


def test_exact_unchanged_scorer_and_lifecycle_sources():
    old = ROOT / "results/prediction_continuation_20261014"
    for name in ("scoring.py", "numerical.py", "common.py", "world_contract.py"):
        assert (HERE / name).read_bytes() == (old / name).read_bytes()

    def funcs(path):
        return {
            n.name: ast.dump(n, include_attributes=False)
            for n in ast.parse(path.read_text()).body
            if isinstance(n, ast.FunctionDef)
        }

    a, b = funcs(HERE / "run_budgeted.py"), funcs(old / "run_budgeted.py")
    for name in (
        "proc_table",
        "consumed_cpu",
        "enable_subreaper",
        "child_limit",
        "send_signal",
        "cleanup_group",
        "cleanup",
        "interrupt",
        "process_identity",
        "phase_limit",
        "budget_reason",
        "resource_clearance",
    ):
        assert a[name] == b[name]


def test_search_health_retains_native_failure_rules():
    state = {
        "generation": 4,
        "curves": [{"gen": g, "pop_invalid": 0.0, "pop_mismatch": 0.0, "recheck_invalid": 0.0} for g in range(4)],
    }
    M.validate_search_state(state)
    state["curves"][1]["recheck_invalid"] = float("nan")
    with pytest.raises(ValueError):
        M.validate_search_state(state)


def test_source_only_has_no_runtime_or_engine_imports():
    assert not any(
        (HERE / n).exists() for n in ("protocol.json", "inputs", "initialization", "ready.json", "runs", "build-cache")
    )
    assert not {"src.life.build", "src.life.evaluate", "src.evolve", "src.run", "src.checkpoint"} & set(sys.modules)
