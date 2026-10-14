"""Scientific synthetic U checks, with no engine imports or simulated lives."""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[2]
STUDY = ROOT / "outputs/autonomous_decoy_evolution_20261014"


@pytest.fixture
def module():
    loader = importlib.util.spec_from_file_location("U_analysis_independent_test", STUDY / "analyze.py")
    value = importlib.util.module_from_spec(loader)
    loader.loader.exec_module(value)
    return value


def paired(values):
    values = np.asarray(values, dtype=float)
    return {"n": len(values), "mean": float(np.mean(values)),
            "se": float(np.sqrt(np.sum((values - values.mean()) ** 2) / (len(values) - 1) / len(values)))}


def test_interactions_preserve_pairing_and_founder_identity(module):
    noise = np.asarray([1000., -1000., 500., -500.])
    deltas = {"trained": np.asarray([2., 4., 6., 8.]), "width_swapped": np.asarray([1., 3., 5., 7.]),
              "frozen": np.asarray([3., 5., 7., 9.]), "frozen_lateral_off": np.asarray([2., 4., 6., 8.])}
    rows = {name: {0: {"F": noise}, 1: {"F": -noise}, 2: {"F": noise + delta},
                   3: {"F": -noise - 2 * delta}} for name, delta in deltas.items()}
    result = module.contrasts(rows)
    assert result[module.LABELS[2]]["width_cue_interaction"]["mean"] == 1
    assert result[module.LABELS[2]]["width_cue_interaction"]["se"] == 0
    assert result[module.LABELS[3]]["added_frozen_lateral_dependence"]["mean"] == -2
    assert result[module.LABELS[3]]["added_frozen_lateral_dependence"]["se"] == 0
    assert result[module.LABELS[2]]["trained_gain"]["se"] == pytest.approx(np.sqrt(5 / 3))


def test_decomposition_separates_poison_miss_guard_and_extinction(module):
    world = {"T": 1024., "t_open": 544., "R_cap": 500., "b2_value": -50., "c_miss": 10.}
    base = {key: np.zeros(3) for key in ("captures", "b2_clicks", "misses", "guard_charge",
                                       "extinct_charge", "cost", "F")}
    candidate, reference = copy.deepcopy(base), copy.deepcopy(base)
    candidate["captures"][:] = 2
    reference["b2_clicks"][:] = 3
    reference["misses"][:] = 4
    reference["guard_charge"][:] = 96
    reference["extinct_charge"][:] = .25
    reference["cost"][:] = 3 * 50 + 4 * 10 + 48
    candidate["F"][:] = 1000 / 480
    reference["F"][:] = -(238 + 96) / 480 - .25
    result = module.components(candidate, reference, world)
    expected = {"capture_income": 1000 / 480, "poison_cost_saving": 150 / 480,
                "miss_cost_saving": 40 / 480, "guard_charge_saving": .2,
                "extinction_charge_saving": .25, "other_cost_saving": .1}
    for key, value in expected.items():
        assert result[key]["mean"] == pytest.approx(value)
        assert result[key]["se"] == pytest.approx(0)
    candidate["F"][0] += .01
    with pytest.raises(ValueError, match="reconcile"):
        module.components(candidate, reference, world)


def frozen_rows(module):
    def row():
        return {"status": np.zeros(3), "births": np.zeros(3), "deaths": np.zeros(3),
                "last_birth": np.full(3, 511.), "n_end": np.full(3, 12.), "n_S_end": np.full(3, 4.),
                "n_M_end": np.full(3, 4.), "n_H_end": np.full(3, 4.), "live_time": np.full(3, 5760.)}
    return {condition: {i: row() for i in range(4)} for condition in module.CONDITIONS[2:]}


@pytest.mark.parametrize("key,value", [("births", 1), ("deaths", 1), ("last_birth", 544),
                                       ("n_H_end", 3), ("n_end", 11), ("live_time", 5761)])
def test_frozen_checks_reject_changes(module, key, value):
    rows = frozen_rows(module)
    assert all(item["complete_pairs"] == 3 for item in module.frozen_structure(rows))
    rows["frozen_lateral_off"][1][key][0] = value
    with pytest.raises(ValueError, match="frozen"):
        module.frozen_structure(rows)


def test_guarded_pairs_excluded_only_from_structure(module):
    rows = frozen_rows(module)
    rows["frozen_lateral_off"][0]["status"][0] = 2
    rows["frozen_lateral_off"][0]["n_end"][0] = 1
    rows["frozen_lateral_off"][0]["live_time"][0] = 100
    report = module.frozen_structure(rows)[0]
    assert report == {"label": module.LABELS[0], "complete_pairs": 2, "guard_or_extinct_pairs": 1,
                      "all_fitness_rows_retained": True}


@pytest.mark.parametrize("status", ["incomplete", "monitor_failed", "running"])
def test_incomplete_gate_does_not_read_partial_outcomes(module, tmp_path, status):
    (tmp_path / "budget.json").write_text(json.dumps({"status": status}))
    assert module.analyze(tmp_path) == {"status": status, "confirmation": None,
                                      "partial_outcomes_compared": False}


def test_not_started_does_not_require_scientific_artifacts(module, tmp_path):
    assert module.analyze(tmp_path) == {"status": "not_started", "confirmation": None,
                                      "partial_outcomes_compared": False}


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + "\n")


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


@pytest.fixture
def synthetic_archive(module, tmp_path):
    """A complete artificial raw archive exercises analysis against worker report schema, not real outcomes."""
    base = tmp_path / "U_synthetic"
    base.mkdir()
    world = json.loads((ROOT / "results/decoy_gradient_20261014/protocol.json").read_text())["world"]
    condition_worlds = module.worlds(world)
    genomes = np.zeros((4, 875), dtype=np.float32)
    genomes[:, 0] = np.arange(4)
    raw_hashes = {label: hashlib.sha256(genomes[i].tobytes()).hexdigest()
                  for i, label in enumerate(module.LABELS)}
    protocol = {"planned_genome_lives": 16460, "world": world, "inputs": {},
                "expected_numerical_identity": {"synthetic": True},
                "confirmation": {"labels": module.LABELS, "conditions": module.CONDITIONS,
                                 "seeds": module.SEEDS.tolist()},
                "founder_mapping": {str(seed): {"raw_sha256": raw_hashes[module.LABELS[i]]}
                                    for i, seed in enumerate((53091, 53092))}}
    write_json(base / "protocol.json", protocol)
    for name in ("run_budgeted.py", "measure.py"):
        (base / name).write_text("synthetic archived source, never executed\n")
    ready = {"protocol_sha256": sha(base / "protocol.json"), "runner_sha256": sha(base / "run_budgeted.py"),
             "measurement_sha256": sha(base / "measure.py")}
    write_json(base / "ready.json", ready)
    write_json(base / "budget.json", {"status": "complete", "running": {}, "queued": [], "cpu_seconds": 100.,
                                     "exit_code": 0, "ready": ready,
                                     "completed": [{"name": name, "exit_code": 0} for name in
                                                   ("evolve_s53091", "evolve_s53092", "confirmation")]})
    endpoint_records = {}
    for i, seed in enumerate((53091, 53092)):
        directory = base / f"runs/s{seed}"
        directory.mkdir(parents=True)
        (directory / "checkpoint.pt").write_bytes(b"synthetic checkpoint bytes; never deserialized")
        (directory / "best_genome.json").write_text("synthetic endpoint\n")
        endpoint_records[str(seed)] = {"generation": 4, "rank": 0,
            "checkpoint_sha256": sha(directory / "checkpoint.pt"),
            "genome_file_sha256": sha(directory / "best_genome.json"),
            "genome_raw_sha256": raw_hashes[module.LABELS[i+2]],
            "search_health": {"pop_invalid": 0., "pop_mismatch": 0., "recheck_invalid": 0.}}
    manifest = {"protocol_sha256": sha(base / "protocol.json"), "worlds": condition_worlds,
                "labels": module.LABELS, "seeds": module.SEEDS.tolist(), "ready": ready,
                "numerical_identity": protocol["expected_numerical_identity"],
                "genotype_sha256": raw_hashes, "endpoints": endpoint_records}
    write_json(base / "confirmation/endpoints.json", manifest)
    np.savez(base / "confirmation/genotypes.npz", genomes=genomes, labels=np.asarray(module.LABELS))
    rows, index = {}, {}
    report = {"status": "complete", "genome_lives": 8192, "primary": {}, "secondary": {}, "conditions": {}}
    sequence = np.arange(512)
    for condition_index, (condition, w) in enumerate(condition_worlds.items()):
        rows[condition] = {}
        span = w["T"] - w["t_open"]
        directory = base / "confirmation" / condition
        directory.mkdir()
        for i in range(4):
            row = {name: np.zeros(512, dtype=np.float64) for name in module.A.COLS}
            row.update(seeds=module.SEEDS.copy(), genome_index=np.asarray(i),
                       cpu_seconds=np.asarray(1.), wall_seconds=np.asarray(1.))
            row["captures"][:] = 4 + i + sequence % 3 - int(condition_index > 0 and i >= 2)
            row["b2_clicks"][:] = 7 - i
            row["misses"][:] = 5 + sequence % 2
            row["clicks"][:] = row["captures"] + row["b2_clicks"] + row["misses"]
            row["n_end"][:] = 8 + i
            row["n_S_end"][:] = 3
            row["n_M_end"][:] = 3
            row["n_H_end"][:] = 2 + i
            row["n_peak"][:] = row["n_end"]
            row["live_time"][:] = span * row["n_end"]
            row["live_S"][:] = span * row["n_S_end"]
            row["live_M"][:] = span * row["n_M_end"]
            row["live_H"][:] = span * row["n_H_end"]
            row["t_end"][:] = w["T"]
            row["last_birth"][:] = 100
            row["window"][:] = span
            row["income"][:] = w["R_cap"] * row["captures"]
            row["cost"][:] = w["c_live"] * row["live_time"] + w["c_miss"] * row["misses"] + 50 * row["b2_clicks"]
            row["net"][:] = row["income"] - row["cost"]
            row["F_kernel"][:] = row["net"] / span
            row["F"][:] = row["F_kernel"]
            row["ledger"] = np.stack([row["F_kernel" if name == "F" else name] for name in module.A.LEDGER], axis=1)
            rows[condition][i] = row
            path = directory / f"row_{i:04d}.npz"
            np.savez(path, **row)
            index[str(path.relative_to(base / "confirmation"))] = sha(path)
        np.savez(directory / "scores.npz", seeds=module.SEEDS, genome_indices=np.arange(4),
                 **{key: np.stack([rows[condition][i][key] for i in range(4)]) for key in module.A.COLS})
        comparisons = {}
        for i in (2, 3):
            candidate, reference = rows[condition][i], rows[condition][i-2]
            values = {key: paired(candidate[key] - reference[key]) for key in module.COUNTS}
            # Independent term construction, preserving the real worker's field names and absent flag keys.
            terms = {"capture_income": w["R_cap"] * (candidate["captures"] - reference["captures"]) / span,
                     "poison_cost_saving": 50 * (reference["b2_clicks"] - candidate["b2_clicks"]) / span,
                     "miss_cost_saving": w["c_miss"] * (reference["misses"] - candidate["misses"]) / span,
                     "guard_charge_saving": np.zeros(512), "extinction_charge_saving": np.zeros(512)}
            terms["other_cost_saving"] = ((reference["cost"] - candidate["cost"]) / span -
                                          terms["poison_cost_saving"] - terms["miss_cost_saving"])
            values["decoy_fitness_contributions"] = {name: paired(value) for name, value in terms.items()}
            comparisons[module.LABELS[i]] = values
        report["conditions"][condition] = {"own_founder_contrasts": comparisons}
    for i in (2, 3):
        gain = {condition: rows[condition][i]["F"] - rows[condition][i-2]["F"] for condition in module.CONDITIONS}
        primary = paired(gain["trained"])
        report["primary"][module.LABELS[i]] = {**primary, "above_3se": primary["mean"] > 3 * primary["se"],
                                              "at_least_0p5": primary["mean"] >= .5}
        report["secondary"][module.LABELS[i]] = {
            "width_association_gain": {"F": paired(gain["trained"] - gain["width_swapped"])},
            "added_lateral_dependence": {"F": paired(gain["frozen"] - gain["frozen_lateral_off"])}}
    write_json(base / "confirmation/report.json", report)
    write_json(base / "confirmation/row_index.json", index)
    return base


def test_complete_archive_matches_actual_worker_report_schema(module, synthetic_archive):
    result = module.analyze(synthetic_archive)
    assert result["status"] == "complete" and result["confirmation_genome_lives"] == 8192
    assert result["raw_confirmation_cpu_seconds"] == 16
    assert all(item["complete_pairs"] == 512 for item in result["frozen_structure"])


def test_wrong_primary_descriptive_flag_rejected(module, synthetic_archive):
    path = synthetic_archive / "confirmation/report.json"
    report = json.loads(path.read_text())
    label = module.LABELS[2]
    report["primary"][label]["above_3se"] = not report["primary"][label]["above_3se"]
    write_json(path, report)
    with pytest.raises(ValueError, match="flag|3se|3.SE|above"):
        module.analyze(synthetic_archive)


def test_corrupted_raw_row_hash_rejected(module, synthetic_archive):
    path = synthetic_archive / "confirmation/trained/row_0000.npz"
    path.write_bytes(path.read_bytes() + b"corrupted")
    with pytest.raises(ValueError, match="raw row"):
        module.analyze(synthetic_archive)


def test_terminal_completed_cpu_above_cap_rejected(module, synthetic_archive):
    path = synthetic_archive / "budget.json"
    budget = json.loads(path.read_text())
    budget["cpu_seconds"] = 7200.
    write_json(path, budget)
    with pytest.raises(ValueError, match="resource"):
        module.analyze(synthetic_archive)


def test_raw_guard_and_extinction_charges_are_retained(module, synthetic_archive):
    world = json.loads((synthetic_archive / "protocol.json").read_text())["world"]
    row = module.A.arrays(synthetic_archive / "confirmation/trained/row_0000.npz")
    row["status"][:2] = [2, 1]
    row["t_end"][:2] = [256, 128]
    row["t_ext"][1] = 128
    row["live_time"][:2] = [256 * 8, 128 * 8]
    row["n_end"][1] = 0
    for name in ("n_S_end", "n_M_end", "n_H_end"):
        row[name][1] = 0
    row["deaths"][1] = 8
    row["cost"][:] = world["c_live"] * row["live_time"] + 10 * row["misses"] + 50 * row["b2_clicks"]
    row["guard_charge"][0] = world["c_live"] * world["n_max"] * (1024 - 256)
    row["extinct_charge"][1] = world["c_live"] * (1024 - 128) / 1024
    row["net"][:] = row["income"] - row["cost"] - row["guard_charge"]
    row["F_kernel"][:] = row["net"] / 1024
    row["F"][:] = row["F_kernel"] - row["extinct_charge"]
    row["ledger"] = np.stack([row["F_kernel" if name == "F" else name] for name in module.A.LEDGER], axis=1)
    assert module.A.validate_row(row, world) == {"guarded": 1, "extinct": 1, "valid_other_status": 0}
    row["F"][1] += row["extinct_charge"][1]
    with pytest.raises(ValueError, match="production fitness"):
        module.A.validate_row(row, world)


def test_invalid_status_cannot_be_dropped_from_evidence(module, synthetic_archive):
    world = json.loads((synthetic_archive / "protocol.json").read_text())["world"]
    row = module.A.arrays(synthetic_archive / "confirmation/trained/row_0000.npz")
    row["status"][0] = 128
    row["ledger"][0, module.A.L["status"]] = 128
    with pytest.raises(ValueError, match="invalid implementation status"):
        module.A.validate_row(row, world)
