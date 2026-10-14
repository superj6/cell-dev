"""Synthetic accounting/statistics and checkpoint audit checks; no simulation."""
import importlib.util
import shutil
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

PATH = Path(__file__).with_name("analyze.py")
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
    data = {key: np.zeros((6, 3)) for key in keys}
    data.update(seeds=np.array([1, 2, 3]), genome_indices=np.arange(6))
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
    data["extinct_charge"] = np.zeros((6, 3))
    data["extinct_charge"][2, 1] = 0.06
    data["window"] = np.full((6, 3), 10)
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
    row = {"gen": 0, "T": 1024, "seeds": [mod.life_seed(spec, 52091, 1, 0, i) for i in range(3)],
           "children": [{"id": i, "pa": 0, "pb": 1, "ops": {"mut": [["b", [0], 0.1]]},
                         "kept": i in survivors} for i in range(32, 256)],
           "survivors": survivors, "fitness": fitness,
           "recheck": {"seeds": [mod.life_seed(spec, 52091, 1, 0, i) for i in range(3, 7)], "key": "all",
                       "ids": list(range(32, 96)), "F_base": list(range(128, 64, -1)),
                       "F_recheck": list(range(128, 64, -1))}}
    state = {"ids": mod.torch.tensor(survivors), "fitness": mod.torch.tensor(fitness, dtype=mod.torch.float64)}
    curves = [{"gen": 0, "T": 1024, "best_id": 32, "fitness": 128.0}]
    return [initial, row], curves, state, spec


def test_lineage_reconstructs_ordinary_top32_from_seven_life_scores():
    lines, curves, state, spec = lineage_example()
    value = mod.audit_lineage(lines, curves, state, 52091, spec)
    assert value["sexual_offspring"] == 224
    assert value["initial_mutated_copies"] == 31
    assert value["logged_point_mutations_including_initial_copies"] == 255


def test_lineage_rejects_retention_of_lower_ranked_shortlist_member():
    lines, curves, state, spec = lineage_example()
    lines[1]["survivors"][-1] = 95
    lines[1]["fitness"][-1] = 65
    with pytest.raises(ValueError, match="top32 pooled shortlist"):
        mod.audit_lineage(lines, curves, state, 52091, spec)


def test_lineage_rejects_overlapping_initial_and_recheck_seed_roles():
    lines, curves, state, spec = lineage_example()
    lines[1]["recheck"]["seeds"][0] = lines[1]["seeds"][0]
    with pytest.raises(ValueError, match="recheck seeds"):
        mod.audit_lineage(lines, curves, state, 52091, spec)


def test_P_scope_mapping_and_unresolved_signs_are_fixed():
    assert mod.RUNS == (52091, 52092)
    assert mod.LABELS == ("pilot_s5", "founder_row38", "D51089", "D51090", "s52091_final_rank0", "s52092_final_rank0")
    assert mod.DURATIONS == (768, 1024, 1536)
    assert mod.stats(np.array([-1., 1.]))["mean"] == 0


def test_actual_preparation_sources_and_seed_mapping_without_outcome_reads(tmp_path):
    here = Path(__file__).resolve().parent
    prepared = here / "prelaunch"
    if not prepared.exists():
        prepared = mod.ROOT / "results/next_step_20261014"
        if (prepared / "prelaunch").exists():
            prepared = prepared / "prelaunch"
    base = tmp_path / "archived_preparation"
    shutil.copytree(prepared, base)
    shutil.copyfile(here / "sources/G_audit_search.py", base / "sources/G_audit_search.py")
    ready = mod.read_json(base / "ready.template.json")
    mod.write_json(base / "ready.json", ready)
    for relative in mod.DEPENDENCIES:
        mod.write_json(base / "dependencies" / Path(relative).name / "budget.json",
                       {"status": "complete", "running": {}, "queued": []})
    # These synthetic scheduling receipts let the input audit run without consulting any live study outcome.
    protocol, checked, inputs, _ = mod.frozen_inputs(base)
    assert checked == ready and protocol["runs"] == list(mod.RUNS)
    assert protocol["max_cpu_seconds"] == 14400 and len(inputs["D51089"]) == 875
    assert mod.raw_digest(inputs["D51089"]) == "a4f43384b1a82ca2929d556250bbd4b3b8a471773e765bb5095cc1e2ab11d3b8"
    assert mod.raw_digest(inputs["D51090"]) == "1287ee4421f88fc108c073eae282f625bd0e340a5e4b12d590cd27cbc046bfac"


@pytest.mark.parametrize("status", ["not_started", "waiting_for_workers", "running", "incomplete", "monitor_failed"])
def test_incomplete_budget_never_reads_search_outcomes(tmp_path, monkeypatch, status):
    if status != "not_started":
        mod.write_json(tmp_path / "budget.json", {"status": status})
    monkeypatch.setattr(mod, "frozen_inputs", lambda *a: pytest.fail("incomplete study inspected"))
    summary, vectors = mod.analyze(tmp_path)
    assert summary["status"] == status and summary["confirmation"] is None and vectors == {}


@pytest.mark.parametrize("seed", mod.RUNS)
def test_prospective_initial_population_matches_all_32_recorded_genomes(seed):
    study = Path(__file__).resolve().parent
    receipt = mod.read_json(study / "initialization.json")["runs"][str(seed)]
    population = np.load(study / receipt["population_file"], allow_pickle=False)
    origins = np.tile(np.r_[np.arange(8), np.full(8, -1)], (32, 1))
    state = {"ids": mod.torch.arange(32), "population": mod.torch.from_numpy(population.copy()),
             "origins": mod.torch.from_numpy(origins), "next_innov": 16, "next_id": 32}
    lines = [{"ids": [0], "copies": receipt["copies"]}]
    result = mod.initialization_audit(study, seed, lines, state, population[0])
    assert result["prospective_population_bitwise"]
    assert result["genetic_replay"]["raw_population_replay_bitwise"]
    assert result["genetic_replay"]["point_mutations_including_initial_copies"] == 62
    state["population"][1, 0] += .25
    with pytest.raises(ValueError, match="raw final population"):
        mod.initialization_audit(study, seed, lines, state, population[0])


def estimate(values):
    return {"mean": float(np.mean(values)), "se": float(np.std(values, ddof=1) / np.sqrt(len(values))),
            "n": len(values)}


@pytest.fixture
def confirmation_fixture(tmp_path):
    from dataclasses import asdict

    from src.life import spec

    base = tmp_path / "P"
    folder = base / "confirmation"
    folder.mkdir(parents=True)
    seeds = list(range(52_020_000, 52_020_256))
    ready = {"release": "synthetic"}
    protocol = {"expected_numerical_identity": {"synthetic": True}}
    mod.write_json(base / "protocol.json", protocol)
    endpoints = np.zeros((6, 875), dtype=np.float32)
    endpoints[:, 0] = np.arange(6)
    searches = {str(seed): {"search_health": {"pop_invalid": 0, "pop_mismatch": 0, "recheck_invalid": 0},
                           "checkpoint_sha256": str(seed)} for seed in mod.RUNS}
    manifest = {"labels": list(mod.LABELS), "seeds": seeds, "seed_block": 102, "ready": ready,
                "protocol_sha256": mod.digest(base / "protocol.json"),
                "numerical_identity": protocol["expected_numerical_identity"],
                "search_health": {seed: row["search_health"] for seed, row in searches.items()},
                "checkpoint_sha256": {seed: row["checkpoint_sha256"] for seed, row in searches.items()},
                "genotype_sha256": {label: mod.raw_digest(row) for label, row in zip(mod.LABELS, endpoints)},
                "worlds": {}}
    report = {"status": "complete", "genome_lives": 4608, "worlds": {}, "primary": {}, "secondary": {}}
    row_index, all_data = {}, {}
    np.savez_compressed(folder / "genotypes.npz", genomes=endpoints, labels=np.array(mod.LABELS))
    for duration in mod.DURATIONS:
        world = spec.world("catch_speck_l4", T=duration, d0=.5, d_min=.25, sigma=.4, lam_s=4)
        manifest["worlds"][str(duration)] = asdict(world)
        data = {key: np.zeros((6, 256), dtype=np.float64)
                for key in (*spec.V3.LEDGER, "F_kernel", "extinct_charge", "window")}
        data["window"][:] = duration
        data["t_end"][:] = duration
        data["n_end"][:] = data["n_peak"][:] = 1
        data["live_time"][:] = duration
        data["captures"][0] = 20
        data["captures"][1] = 40
        data["captures"][2] = 100
        data["captures"][3] = 50
        data["captures"][4] = 80 + np.arange(256) % 2
        data["captures"][5] = 70 + np.arange(256) % 2
        data["income"] = world.R_cap * data["captures"]
        data["cost"] = world.c_live * data["live_time"]
        data["net"] = data["income"] - data["cost"]
        data["F"] = data["F_kernel"] = data["net"] / duration
        out = folder / str(duration)
        out.mkdir()
        np.savez_compressed(out / "scores.npz", seeds=np.array(seeds, dtype=np.uint64),
                            genome_indices=np.arange(6), **data)
        for i in range(6):
            raw = {key: row[i] for key, row in data.items()}
            ledger = np.stack([raw["F_kernel" if key == "F" else key] for key in spec.V3.LEDGER], axis=1)
            path = out / f"row_{i:04d}.npz"
            np.savez_compressed(path, seeds=np.array(seeds, dtype=np.uint64), genome_index=np.array(i), ledger=ledger,
                                wall_seconds=np.array(1.), cpu_seconds=np.array(1.), **raw)
            row_index[str(path.relative_to(folder))] = mod.digest(path)
        report["worlds"][str(duration)] = {}
        for i in (4, 5):
            report["worlds"][str(duration)][mod.LABELS[i]] = {}
            for j, name in ((i - 2, "vs_own_founder"), (1, "vs_row38"), (0, "vs_pilot")):
                income = (data["income"][i] - data["income"][j]) / duration
                value = {"F": estimate(data["F"][i] - data["F"][j]),
                         "fitness_contributions": {"income": estimate(income)}}
                for key in ("cost_saving", "guard_charge_saving", "extinction_charge_saving", "accounting_residual"):
                    value["fitness_contributions"][key] = estimate(np.zeros(256))
                report["worlds"][str(duration)][mod.LABELS[i]][name] = value
        all_data[duration] = data
    for i in (4, 5):
        value = estimate(sum(all_data[t]["F"][i] - all_data[t]["F"][i - 2] for t in mod.DURATIONS) / 3)
        report["primary"][mod.LABELS[i]] = {**value, "above_3se": value["mean"] > 3 * value["se"],
                                           "at_least_0p5": value["mean"] >= .5}
        report["secondary"][mod.LABELS[i]] = {
            name: estimate(sum(all_data[t]["F"][i] - all_data[t]["F"][j] for t in mod.DURATIONS) / 3)
            for name, j in (("vs_row38", 1), ("vs_pilot", 0))}
    mod.write_json(folder / "manifest.json", manifest)
    mod.write_json(folder / "report.json", report)
    mod.write_json(folder / "row_index.json", row_index)
    return base, protocol, ready, endpoints, spec, searches


def test_P_confirmation_retains_all_six_contrasts_and_both_signs(confirmation_fixture):
    result, contrasts = mod.confirmation(*confirmation_fixture)
    assert result["genome_lives"] == 4608 and result["paired_seed_clusters"] == 256
    assert len(result["duration_average"]) == 6 and len(contrasts) == 25
    first, second = [result["primary"][label] for label in mod.LABELS[4:]]
    assert first["mean"] < 0 and not first["above_3se"] and not first["at_least_0p5"]
    assert second["mean"] > 0 and second["above_3se"] and second["at_least_0p5"]
    np.testing.assert_array_equal(contrasts["seeds"], np.arange(52_020_000, 52_020_256))


@pytest.mark.parametrize("change", ["block", "labels", "life_count"])
def test_original_D_mapping_cannot_silently_reenter_P_confirmation(confirmation_fixture, change):
    base = confirmation_fixture[0]
    name = "report.json" if change == "life_count" else "manifest.json"
    path = base / "confirmation" / name
    value = mod.read_json(path)
    if change == "block":
        value["seed_block"] = 91
    elif change == "labels":
        value["labels"][0] = "pilot_s7"
    else:
        value["genome_lives"] = 4607
    mod.write_json(path, value)
    with pytest.raises(ValueError, match="differs"):
        mod.confirmation(*confirmation_fixture)


def test_complete_raw_ledger_is_checked_independently_of_scored_columns(confirmation_fixture):
    base = confirmation_fixture[0]
    path = base / "confirmation/768/row_0000.npz"
    raw = mod.npz(path)
    raw["ledger"][0, 0] += 1
    np.savez_compressed(path, **raw)
    index = mod.read_json(base / "confirmation/row_index.json")
    index["768/row_0000.npz"] = mod.digest(path)
    mod.write_json(base / "confirmation/row_index.json", index)
    with pytest.raises(ValueError, match="raw ledger differs"):
        mod.confirmation(*confirmation_fixture)


def mocked_completed_study(fixture, monkeypatch):
    base, protocol, ready, endpoints, spec, searches = fixture
    protocol.update(planned_genome_lives=37548, max_cpu_seconds=14400,
                    selection_T1024_equivalent_lives=34816, source_identity={}, reference_sources={},
                    template_pins={}, wait_for_studies=[])
    ready["helpers"] = {}
    for seed in mod.RUNS:
        searches[str(seed)].update(initial_evaluation_genome_lives=12288, recheck_genome_lives=4096,
                                  selection_T1024_equivalent_lives=17408,
                                  periodic_validation=[{"generation": g, "F": 0, "n_lives": 16, "T": 1024}
                                                       for g in (0, 4, 8, 12, 15)])
    mod.write_json(base / "protocol.json", protocol)
    mod.write_json(base / "ready.json", ready)
    manifest = mod.read_json(base / "confirmation/manifest.json")
    manifest.update(protocol_sha256=mod.digest(base / "protocol.json"), ready=ready)
    mod.write_json(base / "confirmation/manifest.json", manifest)
    budget = {"status": "complete", "running": {}, "queued": [], "cpu_seconds": 1000,
              "cap_cpu_seconds": 14400, "exit_code": 0, "ready": ready,
              "completed": [{"name": name, "exit_code": 0} for name in
                            ("evolve_s52091", "evolve_s52092", "confirmation")]}
    mod.write_json(base / "budget.json", budget)
    monkeypatch.setattr(mod, "frozen_inputs", lambda folder: (
        protocol, ready, {label: endpoints[i] for i, label in enumerate(mod.LABELS[:4])}, spec))
    monkeypatch.setattr(mod, "search_audit", lambda folder, seed, *args: (
        searches[str(seed)], endpoints[4 + mod.RUNS.index(seed)]))
    return base, protocol


def test_duration_adjusted_search_count_comes_from_P_protocol(confirmation_fixture, monkeypatch):
    base, _ = mocked_completed_study(confirmation_fixture, monkeypatch)
    summary, _ = mod.analyze(base)
    assert summary["completed_genome_lives"] == 37548
    assert summary["audited_checkpoint_selection_lives"] == 32768
    assert sum(row["selection_T1024_equivalent_lives"] for row in summary["searches"].values()) == 34816


def test_export_preserves_prelaunch_and_all_raw_rows_then_reaudits(confirmation_fixture, monkeypatch, tmp_path):
    base, protocol = mocked_completed_study(confirmation_fixture, monkeypatch)
    for name in ("seed_audit.json", "initialization.json", "search_health.json", "inputs/D/provenance.json"):
        mod.write_json(base / name, {"synthetic": True})
    for name in ("sources/G_audit_search.py", "run_budgeted.py", "measure.py", "prepare.py"):
        path = base / name
        path.parent.mkdir(exist_ok=True)
        path.write_text("# synthetic archived source\n")
    target = tmp_path / "public"
    target.mkdir()
    (target / "README.md").write_text("Original prospective preparation\n")
    old = {"status": "prepared_not_released", "artifacts": {"README.md": {
        "sha256": mod.digest(target / "README.md"), "bytes": (target / "README.md").stat().st_size}}}
    mod.write_json(target / "provenance.json", old)
    summary, contrasts = mod.analyze(base)
    out = base / "analysis"
    mod.write_json(out / "summary.json", summary)
    np.savez_compressed(out / "contrasts.npz", **contrasts)
    (out / "continuation_summary.png").write_bytes(b"synthetic plot")
    mod.export(base, target, summary, out)
    assert (target / "prelaunch/README.md").read_text() == "Original prospective preparation\n"
    assert mod.read_json(target / "prelaunch/provenance.json") == old
    assert len(list((target / "confirmation").rglob("row_*.npz"))) == 18
    assert mod.read_json(target / "provenance.json")["status"] == "complete"
    mod.provenance_check(target)
    rebuilt, vectors = mod.analyze(target)
    assert rebuilt == summary and set(vectors) == set(contrasts)
    assert all(mod.identical(vectors[key], value) for key, value in contrasts.items())


@pytest.mark.parametrize('cpu', [14400, 14401, float('nan')])
def test_at_or_over_cap_or_nonfinite_usage_cannot_be_complete(confirmation_fixture, monkeypatch, cpu):
    import json

    base, _ = mocked_completed_study(confirmation_fixture, monkeypatch)
    budget = mod.read_json(base / 'budget.json')
    budget['cpu_seconds'] = cpu
    (base / 'budget.json').write_text(json.dumps(budget))
    with pytest.raises(ValueError, match='resource'):
        mod.analyze(base)


def test_missing_second_endpoint_cannot_reduce_scope(tmp_path):
    with pytest.raises(ValueError, match='checkpoint is missing'):
        mod.search_audit(tmp_path, 52092, {}, {}, None, True)


def test_assigned_D_founders_cannot_be_swapped_without_outcome_reads():
    from copy import deepcopy

    here = Path(__file__).resolve().parent
    protocol = deepcopy(mod.read_json(here / 'protocol.json'))
    protocol['founder_mapping']['52091']['D_run'] = 51090
    with pytest.raises(ValueError, match='prospective founder mapping'):
        mod.founder_inputs(here, protocol)


def test_secondary_mixture_is_recomputed_independently(confirmation_fixture):
    base = confirmation_fixture[0]
    report = mod.read_json(base / 'confirmation/report.json')
    report['secondary'][mod.LABELS[4]]['vs_row38']['mean'] += .5
    mod.write_json(base / 'confirmation/report.json', report)
    with pytest.raises(ValueError, match='secondary mixture'):
        mod.confirmation(*confirmation_fixture)


def test_missing_last_raw_arm_cannot_publish_a_subset(confirmation_fixture):
    (confirmation_fixture[0] / 'confirmation/1536/row_0005.npz').unlink()
    with pytest.raises(ValueError, match='missing local raw'):
        mod.confirmation(*confirmation_fixture)


def test_frozen_endpoint_order_must_match_both_searches(confirmation_fixture):
    base = confirmation_fixture[0]
    path = base / 'confirmation/genotypes.npz'
    saved = mod.npz(path)
    saved['genomes'][[4, 5]] = saved['genomes'][[5, 4]]
    np.savez_compressed(path, **saved)
    with pytest.raises(ValueError, match='fixed inputs/final rank-zero endpoints'):
        mod.confirmation(*confirmation_fixture)


def test_export_retry_rejects_changed_preserved_preparation(confirmation_fixture, monkeypatch, tmp_path):
    original_inputs = mod.frozen_inputs
    base, _ = mocked_completed_study(confirmation_fixture, monkeypatch)
    summary, _ = mod.analyze(base)
    target = tmp_path / 'public_retry'
    historical = target / 'prelaunch'
    historical.mkdir(parents=True)
    (historical / 'README.md').write_text('original preparation\n')
    mod.write_json(historical / 'provenance.json', {'status': 'prepared_not_released', 'artifacts': {
        'README.md': {'sha256': mod.digest(historical / 'README.md'),
                      'bytes': (historical / 'README.md').stat().st_size}}})
    (historical / 'README.md').write_text('changed preparation\n')
    with pytest.raises(ValueError, match='archived artifact'):
        mod.export(base, target, summary, base / 'analysis')
    with pytest.raises(ValueError, match='archived artifact'):
        original_inputs(target)
    assert not (target / 'measurement').exists()


@pytest.mark.parametrize('name,value', [('cpu_seconds', -1.), ('wall_seconds', float('nan'))])
def test_corrupt_raw_timing_is_rejected(confirmation_fixture, name, value):
    base = confirmation_fixture[0]
    path = base / 'confirmation/768/row_0000.npz'
    row = mod.npz(path)
    row[name] = np.asarray(value)
    np.savez_compressed(path, **row)
    index = mod.read_json(base / 'confirmation/row_index.json')
    index['768/row_0000.npz'] = mod.digest(path)
    mod.write_json(base / 'confirmation/row_index.json', index)
    with pytest.raises(ValueError, match='raw confirmation timing'):
        mod.confirmation(*confirmation_fixture)


def test_raw_confirmation_cpu_cannot_exceed_cumulative_monitor(confirmation_fixture, monkeypatch):
    base, _ = mocked_completed_study(confirmation_fixture, monkeypatch)
    budget = mod.read_json(base / 'budget.json')
    budget['cpu_seconds'] = 17  # eighteen synthetic rows each record one CPU-second
    mod.write_json(base / 'budget.json', budget)
    with pytest.raises(ValueError, match='CPU exceeds cumulative'):
        mod.analyze(base)
