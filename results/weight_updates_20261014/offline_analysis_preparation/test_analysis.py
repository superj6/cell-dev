"""Synthetic tests for independent R accounting, paired covariance and frozen-tissue audits; no lives."""
import importlib.util
import json
from pathlib import Path

import numpy as np
import pytest


def module():
    path = Path(__file__).with_name("analyze.py")
    spec = importlib.util.spec_from_file_location("weight_updates_independent", path)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


def world():
    manifest = json.loads((Path(__file__).parent / "inputs/D/confirmation/manifest.json").read_text())
    return dict(manifest["worlds"]["1536"], t_fork=768, t_open=800, fork_flags=16)


def synthetic(run, w, status=(0, 0, 0, 0), ends=(1536, 1536, 1536, 1536), extinct=(0, 0, 0, 0)):
    n = len(status)
    row = {key: np.zeros(n, dtype=np.float64) for key in run.COLS}
    row.update(cpu_seconds=np.asarray(1.25), wall_seconds=np.asarray(1.0))
    for name, value in dict(status=status, t_end=ends, t_ext=extinct, captures=5, income=2500,
                             n_end=100, n_S_end=30, n_M_end=40, n_H_end=30, live_time=73600,
                             window=736, last_birth=768.2, misses=2, spikes=500).items():
        row[name][:] = value
    costs = sum(price * row[column] for _, column, price in run.prices(w))
    status = np.asarray(status, dtype=np.int64)
    row["cost"] = costs
    row["guard_charge"] = np.where((status & 6) != 0, w["c_live"] * w["n_max"] * (1536 - row["t_end"]), 0)
    row["net"] = row["income"] - costs - row["guard_charge"]
    row["F_kernel"] = row["net"] / 736
    row["extinct_charge"] = w["c_live"] * np.where((status & 1) != 0,
                                                    1536 - np.maximum(row["t_ext"], 800), 0) / 736
    row["F"] = row["F_kernel"] - row["extinct_charge"]
    row["ledger"] = np.stack([row["F_kernel" if name == "F" else name] for name in run.LEDGER], axis=1)
    return row


def test_guard_and_extinction_penalties_are_retained_with_window_clamping():
    run = module()
    w = world()
    row = synthetic(run, w, status=(0, 4, 1, 1), ends=(1536, 1000, 500, 1000), extinct=(0, 0, 500, 1000))
    health = run.validate_row(row, w, n=4)
    assert health == {"guarded": 1, "extinct": 2, "valid_other_status": 0}
    assert row["guard_charge"][1] == .02 * 1024 * 536
    assert row["extinct_charge"][2] == .02
    assert row["extinct_charge"][3] == .02 * 536 / 736
    assert np.array_equal(row["F"], row["F_kernel"] - row["extinct_charge"])


@pytest.mark.parametrize("column,delta,message", [
    ("status", 64, "invalid implementation"), ("status", 128, "invalid implementation"),
    ("status", 0.1, "invalid implementation"), ("F", 0.01, "production fitness"),
    ("window", 1, "accounting window"), ("cost", 1, "independent accounting"),
    ("net", 1, "independent accounting"),
    ("t_end", -1, "incomplete life"), ("extinct_charge", 1, "independent accounting")])
def test_corrupted_or_invalid_row_rejected(column, delta, message):
    run = module()
    w = world()
    row = synthetic(run, w)
    row[column][1] += delta
    if column in run.LEDGER and column != "F":
        row["ledger"][1, run.L[column]] += delta
    with pytest.raises(ValueError, match=message):
        run.validate_row(row, w, n=4)


def test_raw_ledger_columns_cannot_disagree_with_saved_columns():
    run = module()
    w = world()
    row = synthetic(run, w)
    row["ledger"][0, run.L["path"]] += 1
    with pytest.raises(ValueError, match="saved production column"):
        run.validate_row(row, w, n=4)


def fixture_frozen(run):
    row = synthetic(run, world())
    return {condition: {key: np.stack([row[key]] * 3) for key in run.COLS} for condition in run.CONDITIONS}


def test_structure_accepts_benign_flags_and_counts_guard_exclusions_without_censoring():
    run = module()
    data = fixture_frozen(run)
    data["S"]["status"][0, 0] = 256
    data["F"]["status"][0, 1] = 4
    data["F"]["n_end"][0, 1] = 10
    data["F"]["live_time"][0, 1] = 10
    result = run.constant_structure(data)
    assert result[0]["complete_triplets"] == 3 and result[0]["excluded_guard_or_extinct_triplets"] == 1
    assert all(row["all_fitness_rows_retained"] for row in result)
    assert data["F"]["F"].shape == (3, 4)


@pytest.mark.parametrize("key", ["births", "deaths", "last_birth", "n_end", "n_S_end", "n_M_end", "n_H_end",
                                "live_time", "t_end"])
def test_constant_structure_detects_each_constraint(key):
    run = module()
    data = fixture_frozen(run)
    data["F"][key][2, 1] += 100
    with pytest.raises(ValueError):
        run.constant_structure(data)


def test_three_arm_interactions_keep_seed_covariance_both_endpoints_and_signs():
    run = module()
    shared = np.asarray([100., -200., 300., -400.])
    data = {condition: np.stack([shared] * 3) for condition in run.CONDITIONS}
    data["C"][1] += [1, 2, 3, 4]
    data["F"][1] += [-1, 0, 1, 2]
    data["F"][2] += 3
    raw = run.effects(data)
    positive = run.stats(raw[run.LABELS[1] + "__added_C_minus_F"], flags=True)
    negative = run.stats(raw[run.LABELS[2] + "__added_C_minus_F"], flags=True)
    assert positive == {"mean": 2, "se": 0, "n": 4, "positive_above_3se": True, "negative_below_minus_3se": False}
    assert negative["mean"] == -3 and negative["negative_below_minus_3se"]
    assert len(raw) == 16


def test_income_cost_guard_extinction_terms_reconcile_per_seed():
    run = module()
    w = world()
    left = synthetic(run, w, status=(0, 4, 1, 0), ends=(1536, 1000, 500, 1536), extinct=(0, 0, 500, 0))
    right = synthetic(run, w)
    data = {key: np.stack([left[key], right[key]]) for key in run.COLS}
    terms = run.pair_terms(data, 1, w)
    assert np.allclose(terms["accounting_residual"], 0, atol=1e-12)
    assert terms["guard_charge_saving"][1] > 0 and terms["extinction_charge_saving"][2] == .02


def test_prelaunch_and_running_studies_cannot_be_reported_complete(tmp_path):
    run = module()
    assert run.analyze(tmp_path)[0]["budget_status"] == "not_started"
    (tmp_path / "budget.json").write_text('{"status":"waiting_for_workers"}')
    assert run.analyze(tmp_path)[0] == {"status": "incomplete", "budget_status": "waiting_for_workers"}


@pytest.mark.parametrize("cpu", [0, -1, 3600, 3601, float("nan"), float("inf")])
def test_claimed_completion_requires_finite_cpu_strictly_inside_cap(tmp_path, cpu):
    run = module()
    (tmp_path / "budget.json").write_text(json.dumps({"status": "complete", "exit_code": 0,
        "cpu_seconds": cpu, "running": {}, "queued": []}))
    with pytest.raises(ValueError, match="fixed worker budget"):
        run.analyze(tmp_path)


@pytest.mark.parametrize("status", ["running", "waiting_for_workers", "incomplete", "cpu_budget_exhausted"])
def test_no_result_read_before_terminal_completion(tmp_path, monkeypatch, status):
    run = module()
    (tmp_path / "budget.json").write_text(json.dumps({"status": status}))
    monkeypatch.setattr(run, "audit_inputs", lambda *args: pytest.fail("read scientific inputs before completion"))
    monkeypatch.setattr(run, "arrays", lambda *args: pytest.fail("read raw outcomes before completion"))
    assert run.analyze(tmp_path)[0] == {"status": "incomplete", "budget_status": status}


def test_all_three_arms_enter_structure_audit():
    run = module()
    data = fixture_frozen(run)
    data["C"]["births"][0, 0] = 1
    with pytest.raises(ValueError, match="tissue changed"):
        run.constant_structure(data)


def test_all_sixteen_contrast_accounting_retains_covariance_and_penalties():
    run, w = module(), world()
    data = {}
    for j, condition in enumerate(run.CONDITIONS):
        records = [synthetic(run, w, status=(0, 4, 1, 0), ends=(1536, 1000, 500, 1536),
                             extinct=(0, 0, 500, 0)) for _ in range(3)]
        for i, row in enumerate(records):
            delta = np.array([2., -1., 4., 3.]) * (j + 1) * (i + 1)
            row["captures"] += delta
            row["income"] += 500 * delta
            row["net"] += 500 * delta
            row["F_kernel"] += 500 * delta / 736
            row["F"] += 500 * delta / 736
        data[condition] = {key: np.stack([row[key] for row in records]) for key in run.COLS}
    vectors = run.effects({key: row["F"] for key, row in data.items()})
    result = run.contrast_accounting(data, {key: w for key in run.CONDITIONS}, vectors)
    assert set(result) == set(vectors) and len(result) == 16
    for key, pieces in result.items():
        assert abs(pieces["fitness_contributions"]["accounting_residual"]["mean"]) < 1e-12
        assert pieces["fitness_contributions"]["income"]["mean"] == pytest.approx(run.stats(vectors[key])["mean"])
        assert pieces["fitness_contributions"]["income"]["se"] == pytest.approx(run.stats(vectors[key])["se"])
        assert len(pieces["cost_savings"]) == 9


def test_unreconciled_contrast_accounting_is_rejected():
    run, w = module(), world()
    data = fixture_frozen(run)
    vectors = run.effects({key: row["F"] for key, row in data.items()})
    vectors[run.LABELS[1] + "__added_C_minus_F"][0] += .01
    with pytest.raises(ValueError, match="full contrast accounting"):
        run.contrast_accounting(data, {key: w for key in run.CONDITIONS}, vectors)


def test_invalid_life_cannot_be_excluded_only_from_structure():
    run = module()
    data = fixture_frozen(run)
    data["C"]["status"][0, 0] = 64
    with pytest.raises(ValueError, match="invalid life"):
        run.constant_structure(data)


def test_prelaunch_preservation_checks_original_bytes_and_sizes(tmp_path):
    run = module()
    raw = tmp_path / "protocol.json"
    raw.write_text("original preparation\n")
    receipt = {"status": "prospective_preparation_not_released", "artifacts": {
        "protocol.json": {"sha256": run.sha(raw), "bytes": raw.stat().st_size}}}
    run.save(tmp_path / "provenance.json", receipt)
    assert run.check_prelaunch(tmp_path) == receipt
    raw.write_text("changed preparation\n")
    with pytest.raises(ValueError, match="preserved preparation bytes"):
        run.check_prelaunch(tmp_path)


@pytest.mark.parametrize("key,value", [("cpu_seconds", -1), ("cpu_seconds", float("nan")),
                                       ("wall_seconds", -1), ("wall_seconds", float("inf"))])
def test_invalid_raw_timings_are_rejected(key, value):
    run, w = module(), world()
    row = synthetic(run, w)
    row[key] = np.asarray(value)
    with pytest.raises(ValueError, match="saved row timing"):
        run.validate_row(row, w, n=4)


def test_telescope_is_per_seed_with_shared_covariance():
    run = module()
    rng = np.random.default_rng(51)
    values = {key: rng.normal(size=(3, 17)) for key in run.CONDITIONS}
    result = run.effects(values)
    for label in run.LABELS[1:]:
        direct = result[label + "__gain__S"] - result[label + "__gain__F"]
        first, second = result[label + "__added_S_minus_C"], result[label + "__added_C_minus_F"]
        np.testing.assert_allclose(first + second, direct, rtol=0, atol=1e-14)
        assert run.stats(direct)["se"] != pytest.approx(run.stats(first)["se"] + run.stats(second)["se"])


@pytest.fixture
def fixed_inputs(tmp_path):
    """Actual frozen preparation plus synthetic completed dependency/manifest; no active outcome reads."""
    import shutil

    run = module()
    here = Path(__file__).parent
    protocol = run.read(here / "protocol.json")
    for relative in set(protocol["inputs"]) | set(protocol["preparation_pins"]) | run.READY_FILES:
        target = tmp_path / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(here / relative, target)
    ready = {"files": {name: run.sha(tmp_path / name) for name in run.READY_FILES},
             "dependencies": protocol["dependencies"]}
    run.save(tmp_path / "ready.json", ready)
    for name in ("protocol.json", "run_budgeted.py"):
        target = tmp_path / "dependency/Q" / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(run.ROOT / run.DEPENDENCY / name, target)
    run.save(tmp_path / "dependency/Q/budget.json", {"status": "complete", "running": {}, "queued": [],
             "cpu_seconds": 1000, "cap_cpu_seconds": 3600, "exit_code": 0})
    manifest = {key: protocol[key] for key in
                ("labels", "conditions", "seeds", "seed_block", "genome_raw_sha256", "numerical_identity", "worlds")}
    manifest.update(protocol_sha256=run.sha(tmp_path / "protocol.json"), ready=ready, planned_genome_lives=4608)
    run.save(tmp_path / "measurement/manifest.json", manifest)
    genomes = [run.genes.from_json(run.read(tmp_path / "inputs" / (label + ".json"))) for label in run.LABELS]
    np.savez_compressed(tmp_path / "measurement/genotypes.npz", genomes=np.stack(genomes),
                        labels=np.asarray(run.LABELS))
    return run, tmp_path, protocol


def test_complete_fixed_input_audit_replays_both_D_endpoints(fixed_inputs):
    run, base, expected = fixed_inputs
    protocol, manifest = run.audit_inputs(base)
    assert protocol == expected and manifest["labels"] == list(run.LABELS)


def test_frozen_inputs_are_auditable_without_repository_fallback(fixed_inputs, monkeypatch):
    import shutil

    run, base, protocol = fixed_inputs
    for relative in list(protocol["source_identity"]) + ["scripts/" + name for name in protocol["helpers"]]:
        target = base / "sources" / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(run.ROOT / relative, target)
    monkeypatch.setattr(run, "ROOT", None)
    assert run.audit_inputs(base)[0] == protocol


@pytest.mark.parametrize("change", ["ready", "input", "proof", "dependency", "raw_genome", "manifest_seed"])
def test_frozen_input_and_manifest_corruption_is_rejected(fixed_inputs, change):
    run, base, _ = fixed_inputs
    if change == "ready":
        value = run.read(base / "ready.json")
        value["files"].pop("test_measure.py")
        run.save(base / "ready.json", value)
    elif change == "input":
        (base / "inputs/d_s51089_final_rank0.json").write_text("tampered input")
    elif change == "proof":
        (base / "semantic_proof/COMBINED_CLAMP_SOURCE_AUDIT.md").write_text("tampered proof")
    elif change == "dependency":
        value = run.read(base / "dependency/Q/budget.json")
        value["status"] = "incomplete"
        run.save(base / "dependency/Q/budget.json", value)
    elif change == "raw_genome":
        path = base / "measurement/genotypes.npz"
        values = run.arrays(path)
        values["genomes"][1, 0] += 1
        np.savez_compressed(path, **values)
    else:
        path = base / "measurement/manifest.json"
        value = run.read(path)
        value["seeds"][0] += 1
        run.save(path, value)
    with pytest.raises(ValueError):
        run.audit_inputs(base)
