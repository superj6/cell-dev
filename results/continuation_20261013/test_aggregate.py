"""Synthetic accounting/statistics and checkpoint audit checks; no simulation."""
import importlib.util
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

PATH = Path(__file__).with_name("aggregate.py")
if not PATH.exists():
    PATH = Path(__file__).with_name("analyze.py")
SPEC = importlib.util.spec_from_file_location("continuation_aggregate", PATH)
mod = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(mod)


def example():
    world = SimpleNamespace(T=10.0, t0=0.0, t_open=0.0, c_live=0.1, c_spike=0.2, c_tw=0.3,
                            c_msg=0.4, c_div=0.5, c_sec=0.6, c_miss=0.7, c_rec=0.8,
                            b2_value=-0.9, n_max=100)
    keys = ("F", "income", "cost", "guard_charge", "t_end", "t_ext", "status", "captures", "clicks",
            "n_end", "path", "packets") + tuple(key for key, _ in mod.prices(world).values())
    data = {key: np.zeros((4, 3)) for key in keys}
    data.update(seeds=np.array([1, 2, 3]), genome_indices=np.arange(4))
    data["t_end"][:] = 10
    data["income"][:] = [100, 120, 130]
    data["live_time"][:] = [10, 20, 30]
    data["cost"] = world.c_live * data["live_time"]
    data["status"][1, 0] = 2  # legitimate guard, charged the unobserved remainder
    data["t_end"][1, 0] = 6
    data["guard_charge"][1, 0] = 40
    data["status"][2, 1] = 1
    data["t_end"][2, 1] = 4
    data["t_ext"][2, 1] = 4
    data["extinct_charge"] = np.zeros((4, 3))
    data["extinct_charge"][2, 1] = 0.06
    data["window"] = np.full((4, 3), 10)
    data["F_kernel"] = (data["income"] - data["cost"] - data["guard_charge"]) / 10
    data["F"] = data["F_kernel"] - data["extinct_charge"]
    return data, world, keys


def test_mixture_preserves_cross_duration_covariance():
    values = {768: np.array([0., 1., 4., 5.]), 1024: np.array([0., 1., 4., 5.]),
              1536: np.array([0., 1., 4., 5.])}
    result = mod.stats(mod.mixture(values))
    assert result == mod.stats(values[768])
    assert result["se"] > mod.stats(np.concatenate(list(values.values())))["se"]


def test_mixture_keeps_negative_effect_and_requires_all_durations():
    values = {t: np.array([-2., -1., -3.]) for t in mod.DURATIONS}
    assert mod.stats(mod.mixture(values))["mean"] == -2
    with pytest.raises(ValueError, match="all three"):
        mod.mixture({768: values[768]})


def test_ordinary_guards_and_extinction_keep_production_accounting():
    data, world, keys = example()
    mod.check_scores(data, [1, 2, 3], world, keys)
    assert data["F"][1, 0] == 5.9
    assert data["F"][2, 1] == pytest.approx(11.74)
    values = mod.pair_arrays(data, 2, 1, world)
    assert np.max(np.abs(values["accounting_residual"])) < 1e-14


@pytest.mark.parametrize("key", ["cost", "guard_charge", "extinct_charge", "F_kernel", "F"])
def test_corrupt_accounting_is_rejected(key):
    data, world, keys = example()
    data[key][0, 0] += 0.125
    with pytest.raises(ValueError, match="accounting"):
        mod.check_scores(data, [1, 2, 3], world, keys)


@pytest.mark.parametrize("flag", [64, 128])
def test_invalid_engine_status_blocks_inference(flag):
    data, world, keys = example()
    data["status"][0, 0] = flag
    with pytest.raises(ValueError, match="capacity or ledger mismatch"):
        mod.check_scores(data, [1, 2, 3], world, keys)


def test_seed_reordering_is_rejected():
    data, world, keys = example()
    with pytest.raises(ValueError, match="order"):
        mod.check_scores(data, [3, 2, 1], world, keys)


def test_incomplete_study_cannot_export(tmp_path):
    with pytest.raises(ValueError, match="requires all runs"):
        mod.export(tmp_path, tmp_path / "export", {"status": "cpu_budget_exhausted"}, tmp_path)
    assert not (tmp_path / "export").exists()


def test_summary_rejects_wrong_standard_error():
    value = mod.stats(np.arange(5))
    with pytest.raises(ValueError, match="independently recomputed"):
        mod.check_stats(value, {**value, "se": value["se"] / np.sqrt(3)}, "cluster SE")


def test_genome_field_order_is_explicit_and_float32():
    fields = {key: [i + 0.1] for i, key in enumerate(mod.FIELDS)}
    assert np.array_equal(mod.genome(dict(reversed(list(fields.items())))),
                          np.arange(len(fields), dtype=np.float32) + np.float32(0.1))
    with pytest.raises(ValueError, match="field names"):
        mod.genome({**fields, "extra": [0]})


def lineage_example():
    spec = SimpleNamespace(hash64=lambda seed, stream, generation, life: seed + stream + generation * 100 + life)
    initial = {"event": "founders", "sampled": 0, "ids": [0],
               "copies": [{"id": i, "parent": 0, "ops": {"mut": [["b", [0], 0.1]]}} for i in range(1, 32)]}
    survivors = list(range(32, 64))
    fitness = list(map(float, range(128, 96, -1)))
    row = {"gen": 0, "T": 1024, "seeds": [mod.life_seed(spec, 51089, 1, 0, i) for i in range(3)],
           "children": [{"id": i, "pa": 0, "pb": 1, "ops": {"mut": [["b", [0], 0.1]]},
                         "kept": i in survivors} for i in range(32, 256)],
           "survivors": survivors, "fitness": fitness,
           "recheck": {"seeds": [mod.life_seed(spec, 51089, 1, 0, i) for i in range(3, 7)], "key": "all",
                       "ids": list(range(32, 96)), "F_base": list(range(128, 64, -1)),
                       "F_recheck": list(range(128, 64, -1))}}
    state = {"ids": mod.torch.tensor(survivors), "fitness": mod.torch.tensor(fitness, dtype=mod.torch.float64)}
    curves = [{"gen": 0, "T": 1024, "best_id": 32, "fitness": 128.0}]
    return [initial, row], curves, state, spec


def test_lineage_reconstructs_ordinary_top32_from_seven_life_scores():
    lines, curves, state, spec = lineage_example()
    value = mod.audit_lineage(lines, curves, state, 51089, spec)
    assert value["sexual_offspring"] == 224
    assert value["initial_mutated_copies"] == 31
    assert value["logged_point_mutations_including_initial_copies"] == 255


def test_lineage_rejects_retention_of_lower_ranked_shortlist_member():
    lines, curves, state, spec = lineage_example()
    lines[1]["survivors"][-1] = 95
    lines[1]["fitness"][-1] = 65
    with pytest.raises(ValueError, match="top32 pooled shortlist"):
        mod.audit_lineage(lines, curves, state, 51089, spec)


def test_lineage_rejects_overlapping_initial_and_recheck_seed_roles():
    lines, curves, state, spec = lineage_example()
    lines[1]["recheck"]["seeds"][0] = lines[1]["seeds"][0]
    with pytest.raises(ValueError, match="recheck seeds"):
        mod.audit_lineage(lines, curves, state, 51089, spec)
