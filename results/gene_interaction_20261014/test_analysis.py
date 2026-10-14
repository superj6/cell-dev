"""Independent M raw-ledger, genetic replay and export tests; never simulate a life."""
import importlib.util
import shutil
import sys
from pathlib import Path

import numpy as np
import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
loader = importlib.util.spec_from_file_location("M_independent_analysis_tests", HERE / "analyze.py")
a = importlib.util.module_from_spec(loader)
loader.loader.exec_module(a)
loader = importlib.util.spec_from_file_location("M_scientific_arithmetic_tests", HERE / "measure.py")
production = importlib.util.module_from_spec(loader)
loader.loader.exec_module(production)


def world():
    return a.expected_world(a.source(HERE, "src/life/spec.py"))


def row(captures=10, status=None):
    w = world()
    value = {key: np.zeros(512) for key in a.COLS}
    value.update(cpu_seconds=np.asarray(1.), wall_seconds=np.asarray(1.))
    for name, v in {"captures": captures, "income": captures * 500, "n_end": 100, "n_S_end": 30,
                    "n_M_end": 40, "n_H_end": 30, "live_time": 102400, "t_end": 1024, "window": 1024,
                    "last_birth": 300, "spikes": 10, "clicks": captures + 2, "misses": 2, "path": 5}.items():
        value[name][:] = v
    if status is not None:
        value["status"][:] = status
        ended = np.asarray(status, dtype=np.int64) & 7 != 0
        value["t_end"][ended], value["t_ext"][ended] = 700, 700
    value["cost"] = sum(price * value[column] for _, column, price in a.prices(w))
    states = value["status"].astype(np.int64)
    value["guard_charge"] = np.where(states & 6 != 0, w["c_live"] * w["n_max"] * (1024-value["t_end"]), 0)
    value["net"] = value["income"] - value["cost"] - value["guard_charge"]
    value["F_kernel"] = value["net"] / 1024
    value["extinct_charge"] = w["c_live"] * np.where(states & 1 != 0, 1024-value["t_ext"], 0) / 1024
    value["F"] = value["F_kernel"] - value["extinct_charge"]
    value["ledger"] = np.stack([value["F_kernel" if key == "F" else key] for key in a.LEDGER], axis=1)
    return value


@pytest.fixture
def workflow(monkeypatch, tmp_path):
    def create(captures=(10, 8, 7, 6)):
        protocol = {"limitations": ["Synthetic fixture"]}
        manifest = {"world": world(), "seeds": list(range(52_000_000, 52_000_512)), "ready": {}}
        branch = {"rows": {role: {"row": i} for i, role in enumerate(a.ROLES)}}
        monkeypatch.setattr(a, "audit_inputs", lambda base: (protocol, manifest))
        monkeypatch.setattr(a, "audit_candidates", lambda base, man: (branch, {"fixture": "synthetic"}))
        a.save(tmp_path / "budget.json", {"status": "complete", "cap_cpu_seconds": 1800,
            "cpu_seconds": 30., "exit_code": 0, "running": {}, "queued": [], "ready": {}})
        folder = tmp_path / "measurement"
        (folder / "rows").mkdir(parents=True, exist_ok=True)
        rows, index = {}, {}
        for i, n in enumerate(captures):
            rows[i] = row(n)
            name = f"rows/row_{i:04d}.npz"
            np.savez_compressed(folder / name, **rows[i], seeds=np.asarray(manifest["seeds"], dtype=np.uint64),
                                genome_index=np.asarray(i))
            index[name] = {"sha256": a.sha(folder / name), "cpu_seconds": 1.}
        a.save(folder / "row_index.json", index)
        data = {key: np.stack([rows[i][key] for i in range(4)]) for key in a.COLS}
        np.savez_compressed(folder / "scores.npz", **data, seeds=np.asarray(manifest["seeds"], dtype=np.uint64),
                            genome_indices=np.arange(4))
        effects, contrasts = production.factorial(rows, branch, production.world())
        a.save(folder / "report.json", {"status": "complete", "research_genome_lives": 2048,
               "row_cpu_seconds": 4., "limitations": protocol["limitations"], "endpoints": {"51090": effects}})
        np.savez_compressed(folder / "contrasts.npz", seeds=np.asarray(manifest["seeds"], dtype=np.uint64),
                            **{"s51090_" + key: value for key, value in contrasts.items()})
        return tmp_path, data
    return create


@pytest.mark.parametrize("captures,sign", [((10, 8, 7, 6), 1), ((10, 9, 8, 6), -1), ((10, 8, 7, 5), 0)])
def test_whole_mock_data_preserves_both_interaction_signs_and_zero(workflow, captures, sign):
    base, _ = workflow(captures)
    summary, vectors = a.analyze(base)
    f = summary["interaction"]["F"]
    assert f["mean"] == sign * 500 / 1024 and f["se"] == 0
    assert summary["research_genome_lives"] == 2048 and summary["audit"]["raw_rows"] == 4
    assert summary["interaction"]["abs_above_3se"] == bool(sign)
    assert not summary["interaction"]["abs_at_least_0p5"]
    assert set(summary["losses"]) == set(a.ROLES[1:])
    assert set(vectors) == {"seeds", "s51090_interaction", *["s51090_" + r + "_loss" for r in a.ROLES[1:]]}


def test_within_seed_covariance_and_inclusive_half_point_flag(workflow):
    _, data = workflow()
    shared = np.arange(512, dtype=np.float64)
    data["F"] += shared
    data["F_kernel"] += shared
    data["income"] += 1024 * shared
    result, values = a.interaction(data, world())
    assert result["F"]["se"] < 1e-12 and np.allclose(values, 500 / 1024, rtol=0, atol=1e-12)
    data["F"][:] = np.asarray([2., 1., 1., .5])[:, None]
    data["F_kernel"][:] = data["F"]
    data["income"][:] = 1024 * data["F"] + data["cost"]
    result, _ = a.interaction(data, world())
    assert result["F"]["mean"] == .5 and result["abs_at_least_0p5"]


def test_guard_and_extinction_penalties_remain_in_complete_rows():
    status = np.zeros(512)
    status[1:4] = (1, 2, 4)
    value = row(status=status)
    assert a.validate_row(value, world()) == {"guarded": 2, "extinct": 1, "valid_other_status": 0}
    assert value["extinct_charge"][1] > 0 and value["guard_charge"][2] > 0


@pytest.mark.parametrize("key,change", [("F", 1), ("cost", 1), ("net", 1), ("extinct_charge", 1),
                                        ("window", 1), ("status", 64), ("status", 128), ("t_end", -1)])
def test_corrupt_accounting_is_rejected(key, change):
    value = row()
    value[key][0] += change
    if key in a.LEDGER and key != "F":
        value["ledger"][0, a.LEDGER.index(key)] += change
    with pytest.raises(ValueError):
        a.validate_row(value, world())


@pytest.mark.parametrize("fault", ["raw_hash", "aggregate", "seeds", "report", "flags", "contrast", "count",
                                   "cpu", "old_cap", "exact_cap"])
def test_raw_and_report_corruption_cannot_become_a_conclusion(workflow, fault):
    base, _ = workflow()
    if fault in ("aggregate", "seeds", "contrast"):
        file = base / "measurement" / ("contrasts.npz" if fault == "contrast" else "scores.npz")
        data = a.arrays(file)
        key = {"aggregate": "F", "seeds": "seeds", "contrast": "s51090_interaction"}[fault]
        data[key].reshape(-1)[0] += 1
        np.savez_compressed(file, **data)
    else:
        file = base / ("budget.json" if fault in ("cpu", "old_cap", "exact_cap") else
                       "measurement/row_index.json" if fault == "raw_hash" else "measurement/report.json")
        value = a.read(file)
        if fault == "raw_hash":
            value["rows/row_0000.npz"]["sha256"] = "changed"
        elif fault == "report":
            value["endpoints"]["51090"]["interaction"]["F"]["mean"] += 1
        elif fault == "flags":
            value["endpoints"]["51090"]["interaction"]["abs_at_least_0p5"] = True
        elif fault == "count":
            value["research_genome_lives"] = 4096
        elif fault == "cpu":
            value["cpu_seconds"] = 2.
        elif fault == "old_cap":
            value["cap_cpu_seconds"] = 3600
        else:
            value["cpu_seconds"] = 1800
        a.save(file, value)
    with pytest.raises(ValueError):
        a.analyze(base)


def test_completion_gate_precedes_all_input_and_outcome_reads(monkeypatch, tmp_path):
    monkeypatch.setattr(a, "audit_inputs", lambda base: pytest.fail("read scientific data before completion"))
    assert a.analyze(tmp_path)[0]["budget_status"] == "not_started"
    a.save(tmp_path / "budget.json", {"status": "running"})
    assert a.analyze(tmp_path)[0]["budget_status"] == "running"
    a.save(tmp_path / "budget.json", {"status": "complete", "running": {"123": "work"}, "queued": []})
    with pytest.raises(ValueError, match="active or queued"):
        a.analyze(tmp_path)


@pytest.fixture
def frozen_genomes(tmp_path):
    # Completed G genetics and the prospective M table only; no measured M or active L outcomes are read.
    for name in ("inputs",):
        shutil.copytree(HERE / name, tmp_path / name)
    for name in ("genomes.json", "genotypes.npy"):
        shutil.copyfile(HERE / name, tmp_path / name)
    frozen = a.read(tmp_path / "genomes.json")
    (tmp_path / "measurement").mkdir()
    np.savez_compressed(tmp_path / "measurement/genotypes.npz", genomes=np.load(tmp_path / "genotypes.npy"),
                        labels=np.asarray(frozen["labels"]))
    return tmp_path, {"frozen_genomes": frozen}


def test_independent_genetic_replay_and_all_four_canonical_tables(frozen_genomes):
    base, manifest = frozen_genomes
    branch, replay = a.audit_candidates(base, manifest)
    actual = tuple(branch[k] for k in ("copy_slot", "copy_origin_id", "source_slot", "source_origin_id"))
    assert actual == (9, 21, 0, 0)
    assert replay["duplication_events"] == 71 and replay["deletion_events"] == 45
    assert branch["duplication_event"]["source_origin_id"] == 0


@pytest.mark.parametrize("fault", ["source_origin", "raw_genome", "runtime_hash", "lineage"])
def test_frozen_candidate_or_source_mutations_are_rejected(frozen_genomes, fault):
    base, manifest = frozen_genomes
    frozen = manifest["frozen_genomes"]
    if fault == "source_origin":
        frozen["branches"]["51090"]["source_origin_id"] = 1
    elif fault == "runtime_hash":
        frozen["branches"]["51090"]["rows"]["double_KO"]["runtime_table_sha256"] = "wrong"
    elif fault == "raw_genome":
        genome = np.load(base / "genotypes.npy")
        genome[3, 0] += .125
        np.save(base / "genotypes.npy", genome)
    else:
        file = base / "inputs/G/runs/s51090/lineage.jsonl"
        file.write_text(file.read_text() + "\n")
    with pytest.raises(ValueError):
        a.audit_candidates(base, manifest)


@pytest.fixture
def input_receipt(tmp_path):
    protocol = a.read(HERE / "protocol.json")
    ready = a.read(HERE / "ready.template.json")
    ready.pop("status", None)
    names = {*protocol["inputs"], *protocol["preparation_pins"], "protocol.json", "measure.py", "run_budgeted.py"}
    for name in names:
        target = tmp_path / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(HERE / name, target)
    a.save(tmp_path / "ready.json", ready)
    dep = tmp_path / "dependency/L"
    dep.mkdir(parents=True)
    for name in ("protocol.json", "run_budgeted.py"):
        source = HERE / "dependency/L" / name
        if not source.exists():
            source = a.ROOT / a.L_DEPENDENCY / name
        shutil.copyfile(source, dep / name)
    a.save(dep / "budget.json", {"status": "complete", "cpu_seconds": 100., "cap_cpu_seconds": 14400,
                                "exit_code": 0, "running": {}, "queued": []})
    manifest = {"protocol_sha256": a.sha(tmp_path / "protocol.json"), "ready": ready,
                "numerical_identity": protocol["numerical_identity"], "world": protocol["world"],
                "seeds": protocol["seeds"], "seed_block": 100, "genome_lives": 2048,
                "frozen_genomes": a.read(tmp_path / "genomes.json")}
    a.save(tmp_path / "measurement/manifest.json", manifest)
    return tmp_path


def test_all_preparation_release_source_and_dependency_pins_are_checked(input_receipt):
    protocol, manifest = a.audit_inputs(input_receipt)
    assert protocol["runs"] == [51090] and manifest["genome_lives"] == 2048


@pytest.mark.parametrize("fault", ["old_scope", "release_source", "frozen_proof", "L_pending", "seed_order"])
def test_input_pin_and_scope_corruption_is_rejected(input_receipt, fault):
    base = input_receipt
    if fault == "old_scope":
        p = a.read(base / "protocol.json")
        p["runs"] = [51089, 51090]
        a.save(base / "protocol.json", p)
    elif fault == "release_source":
        (base / "measure.py").write_text("changed\n")
    elif fault == "frozen_proof":
        (base / "analytical_proof/PROOF.md").write_text("changed\n")
    elif fault == "L_pending":
        p = a.read(base / "dependency/L/budget.json")
        p["queued"] = ["uncompleted"]
        a.save(base / "dependency/L/budget.json", p)
    else:
        p = a.read(base / "measurement/manifest.json")
        p["seeds"].reverse()
        a.save(base / "measurement/manifest.json", p)
    with pytest.raises(ValueError):
        a.audit_inputs(base)


def test_export_preserves_prelaunch_raw_rows_and_reaudits_copy(workflow, tmp_path):
    base, _ = workflow()
    summary, vectors = a.analyze(base)
    target = tmp_path / "public"
    target.mkdir()
    for name in ("inputs", "analytical_proof", "dependency/L"):
        (base / name).mkdir(parents=True, exist_ok=True)
    protocol = {"preparation_pins": {}, "source_identity": {}, "helpers": {}}
    a.save(base / "protocol.json", protocol)
    a.save(base / "genomes.json", {"synthetic": True})
    np.save(base / "genotypes.npy", np.zeros((4, 875), dtype=np.float32))
    a.save(base / "ready.json", {})
    for name in ("measure.py", "run_budgeted.py", "run.log"):
        (base / name).write_text("synthetic receipt\n")
    for name in ("protocol.json", "run_budgeted.py", "budget.json"):
        (base / "dependency/L" / name).write_text("synthetic dependency\n")
    (target / "README.md").write_text("Original amended preparation\n")
    initial = {"status": "prospective_preparation_not_released", "artifacts": {
        "README.md": {"sha256": a.sha(target / "README.md"), "bytes": (target / "README.md").stat().st_size}}}
    a.save(target / "provenance.json", initial)
    original = (target / "provenance.json").read_bytes()
    a.export(base, target, summary, vectors)
    assert (target / "prelaunch/provenance.json").read_bytes() == original
    assert (target / "prelaunch/README.md").read_text() == "Original amended preparation\n"
    for path in (base / "measurement").rglob("row_*.npz"):
        assert path.read_bytes() == (target / path.relative_to(base)).read_bytes()
    for name, item in a.read(target / "provenance.json")["artifacts"].items():
        assert a.sha(target / name) == item["sha256"]
    assert a.read(target / "summary.json") == summary
