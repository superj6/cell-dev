"""Focused source-only AE regressions; one shared numeric fixture, no engine calls."""

import ast
import copy
import hashlib
import importlib.util
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("AE_reader_test", HERE / "analyze.py")
M = importlib.util.module_from_spec(spec)
spec.loader.exec_module(M)
ROOT = next((p for p in HERE.parents if (p / "src/life/spec.py").is_file()), None)
SOURCE = (
    HERE.parent if (HERE.parent / "measure.py").is_file() else ROOT / "outputs/autonomous_prediction_gradient_20261014"
)


def world():
    return dict(
        t0=0,
        T=1024,
        t_open=0,
        world_kind=1,
        b2_amp=0,
        b2_value=0,
        c_live=0.001,
        c_spike=0.02,
        c_tw=0.03,
        c_msg=0.04,
        c_div=0.05,
        c_sec=0.06,
        c_miss=0.07,
        c_rec=0.08,
        R_cap=500,
        n_max=128,
    )


def row(captures, seeds=None):
    captures = np.broadcast_to(captures, (512,)).astype(np.float64).copy()
    w = world()
    r = {key: np.zeros(512, dtype=np.float64) for key in M.A.COLS}
    for key, value in {
        "captures": captures,
        "clicks": captures,
        "n_end": 1,
        "n_peak": 1,
        "n_S_end": 1,
        "live_time": 1024,
        "live_S": 1024,
        "t_end": 1024,
        "t_ext": -1,
        "window": 1024,
        "spikes": 2,
    }.items():
        r[key][:] = value
    r["income"] = w["R_cap"] * r["captures"]
    r["cost"], _ = M.A.physical_costs(r, w)
    r["net"] = r["income"] - r["cost"] - r["guard_charge"]
    r["F_kernel"] = r["net"] / w["T"]
    r["F"] = r["F_kernel"] - r["extinct_charge"]
    r["ledger"] = np.stack([r["F_kernel" if name == "F" else name] for name in M.A.LEDGER], axis=1)
    r.update(
        seeds=np.arange(512, dtype=np.uint64) if seeds is None else seeds,
        cpu_seconds=np.asarray(0.01),
        wall_seconds=np.asarray(0.02),
    )
    return r


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(M.json_bytes(value))


def synthetic_complete(base):
    """Pure numeric fixtures, deliberately not valid genetic programs; no engine imports."""
    p = {
        "world": world(),
        "seeds": {stage: list(range(1000 * j, 1000 * j + n)) for j, (stage, n) in enumerate(M.N.items(), 1)},
        "historical_blink_cpu_per_life": {b: [0.01] * 65 for b in M.PARENTS},
    }
    panels = {b: np.broadcast_to(np.arange(65, dtype=np.float32)[:, None], (65, 875)).copy() for b in M.PARENTS}
    p["panel_genotype_sha256"] = {b: [M.raw_sha(x) for x in table] for b, table in panels.items()}
    selection = {b: {"genome_row": 64, "raw_sha256": p["panel_genotype_sha256"][b][64]} for b in M.PARENTS}
    save(base / "selection.json", selection)
    role_rows = {f"{a}_{b}": i for b in M.PARENTS for a, i in (("P", 0), ("H", 64))}
    np.savez_compressed(
        base / "confirmation_genotypes.npz",
        roles=np.asarray(M.LABELS),
        genomes=np.stack([panels[label.split("_")[1]][role_rows[label]] for label in M.LABELS]),
    )
    roles = {
        "roles": list(M.LABELS),
        "panel_rows": role_rows,
        "genotype_sha256": {
            label: p["panel_genotype_sha256"][label.split("_")[1]][role_rows[label]] for label in M.LABELS
        },
        "selection_sha256": M.sha(base / "selection.json"),
        "protocol_sha256": M.PROTOCOL_SHA,
        "genotypes_sha256": M.sha(base / "confirmation_genotypes.npz"),
    }
    save(base / "confirmation_roles.json", roles)
    indexes, data = {}, {}
    for key in ("screen/D90", "screen/L92", "confirm/persistent"):
        folder = base / "measurement" / key
        index, data[key] = {}, {}
        stages = (
            {"calibration": [0, 1], "screen": list(range(65))}
            if key.startswith("screen/")
            else {"confirm": list(range(4))}
        )
        for stage, indices in stages.items():
            data[key][stage] = {}
            for i in indices:
                n = M.N[stage]
                r = {k: v[:n] if isinstance(v, np.ndarray) and v.ndim else v for k, v in row(10 + i).items()}
                r["seeds"] = np.asarray(p["seeds"][stage], dtype=np.uint64)
                r["genome_index"] = np.asarray(i)
                if key.startswith("screen/"):
                    b = key.split("/")[1]
                    identity = {
                        "protocol_sha256": M.PROTOCOL_SHA,
                        "background": b,
                        "world": "persistent",
                        "genome_sha256": p["panel_genotype_sha256"][b][i],
                    }
                else:
                    identity = {
                        "protocol_sha256": M.PROTOCOL_SHA,
                        "world": key.split("/")[1],
                        "roles": list(M.LABELS),
                        "confirmation_roles_sha256": M.sha(base / "confirmation_roles.json"),
                        "genome_sha256": roles["genotype_sha256"][M.LABELS[i]],
                    }
                identity.update(stage=stage, genome_index=i, seeds=p["seeds"][stage])
                r["identity"] = np.asarray(M.canonical(identity))
                path = folder / stage / f"row_{i:04d}.npz"
                path.parent.mkdir(parents=True, exist_ok=True)
                np.savez_compressed(path, **r)
                index[f"{stage}/row_{i:04d}.npz"] = {"sha256": M.sha(path), "cpu_seconds": float(r["cpu_seconds"])}
                data[key][stage][i] = r
            np.savez_compressed(
                folder / stage / "scores.npz",
                seeds=np.asarray(p["seeds"][stage], dtype=np.uint64),
                genome_indices=np.asarray(indices),
                **{k: np.stack([data[key][stage][i][k] for i in indices]) for k in M.A.COLS},
            )
        save(folder / "row_index.json", index)
        indexes[key] = index
    return p, panels, selection, roles, indexes, data


def phase_fixture(base, p, selection, roles, indexes):
    save(base / "attempt.json", {"synthetic": True})
    save(base / "startup_identity.json", {"synthetic": True})
    # Execute the actual producer's pure cost functions to check persisted schema.
    funcs = pure_functions("measure.py", ["calibration_projection", "selected_projection"])
    calibration = {b: {i: {"cpu_seconds": 0.01} for i in (0, 1)} for b in M.PARENTS}
    screens = {b: {i: {"cpu_seconds": 0.01} for i in range(65)} for b in M.PARENTS}
    initial = funcs["calibration_projection"](calibration, 5.0, p["historical_blink_cpu_per_life"])
    selected = funcs["selected_projection"](screens, selection, p["historical_blink_cpu_per_life"])
    save(base / "calibration_projection.json", initial)
    save(base / "confirmation_projection.json", selected)
    receipts = {}
    for name, charged in (("calibration_complete", 5.0), ("screens_complete", 15.0)):
        snapshot = {}
        for b in M.PARENTS:
            names = [f"calibration/row_{i:04d}.npz" for i in (0, 1)]
            if name == "screens_complete":
                names += [f"screen/row_{i:04d}.npz" for i in range(65)]
            snapshot["screen/" + b] = {k: indexes["screen/" + b][k] for k in names}
        request = {
            "protocol_sha256": M.PROTOCOL_SHA,
            "row_index_sha256": {k: hashlib.sha256(M.json_bytes(v)).hexdigest() for k, v in snapshot.items()},
        }
        if name == "calibration_complete":
            artifacts = {"startup_identity.json": M.sha(base / "startup_identity.json")}
            request.update(validation_lives=10, startup_identity_sha256=artifacts["startup_identity.json"])
        else:
            artifacts = {
                k: M.sha(base / k)
                for k in (
                    "selection.json",
                    "calibration_projection.json",
                    "confirmation_projection.json",
                    "confirmation_roles.json",
                    "confirmation_genotypes.npz",
                )
            }
            request.update(
                scientific_genome_lives=4160,
                selection_sha256=artifacts["selection.json"],
                confirmation_roles_sha256=artifacts["confirmation_roles.json"],
                confirmation_genotypes_sha256=artifacts["confirmation_genotypes.npz"],
            )
        request_path = base / "requests" / (name + ".json")
        save(request_path, request)
        receipts[name] = {
            "status": "allowed",
            "protocol_sha256": M.PROTOCOL_SHA,
            "attempt_sha256": M.sha(base / "attempt.json"),
            "request_sha256": M.sha(request_path),
            "cpu_seconds": charged,
            "row_snapshot": snapshot,
            "artifact_pins": artifacts,
        }
        save(base / "monitor_receipts" / (name + ".json"), receipts[name])
    report = {
        "status": "complete",
        "scope": M.SCOPE,
        "research_genome_lives": 6208,
        "validation_lives": 10,
        "total_genome_lives": 6218,
        "row_index_sha256": {k: M.sha(base / "measurement" / k / "row_index.json") for k in indexes},
        "row_cpu_seconds": 1.38,
        "screen": {},
        "confirmation": {},
    }
    for b in M.PARENTS:
        report["screen"][b] = {
            "selected": selection[b],
            "complete_rows": 65,
            "row_index_sha256": report["row_index_sha256"]["screen/" + b],
        }
    for w in M.WORLDS:
        report["confirmation"][w] = {
            "complete_roles": list(M.LABELS),
            "row_index_sha256": report["row_index_sha256"]["confirm/" + w],
        }
    save(base / "report.json", report)
    return {"phase_receipts": receipts, "startup_screen_cpu_seconds": 15.0, "cpu_seconds": 25.0}


def pure_functions(filename, names, extra=None):
    tree = ast.parse((SOURCE / filename).read_text())
    definitions = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name in names]
    for definition in definitions:
        definition.body = [n for n in definition.body if not isinstance(n, (ast.Import, ast.ImportFrom))]
    env = {
        "np": np,
        "PARENTS": M.PARENTS,
        "ROLES": list(M.LABELS),
        "COLS": M.A.COLS,
        "paired": lambda a, b: M.A.stats(a - b),
    }
    env.update(extra or {})
    exec(compile(ast.Module(body=definitions, type_ignores=[]), "actual_pure_producer", "exec"), env)
    return env


@pytest.fixture(scope="module")
def complete(tmp_path_factory):
    previous = M.PROTOCOL_SHA
    M.PROTOCOL_SHA = "synthetic-protocol"
    base = tmp_path_factory.mktemp("one_138_row_fixture")
    p, panels, selected, roles, indexes, data = synthetic_complete(base)
    budget = phase_fixture(base, p, selected, roles, indexes)
    yield base, p, panels, selected, roles, indexes, data, budget
    M.PROTOCOL_SHA = previous


def test_complete138_rows_actual_phase_cost_report_schema(complete):
    base, p, panels, selected, roles, indexes, data, budget = complete
    sel, actual_roles, screens, confirmation, idx, cpu, pins = M.load_rows(base, p, panels)
    assert sel == selected and actual_roles == roles and idx == indexes
    assert len([k for k in pins if "/row_" in k and k.endswith(".npz")]) == 138
    assert sum(len(r["F"]) for group in data.values() for stage in group.values() for r in stage.values()) == 6216
    report, projections = M.phases(base, p, budget, indexes, selected, roles, cpu)
    summary, vectors = M.contrasts(confirmation, {"persistent": p["world"]})
    assert len(summary) == 2 and len(vectors) == 128 and all(len(v) == 512 for v in vectors.values())
    # Actual producer builds its 64 metrics independently; use only its pure function AST.
    abi = SimpleNamespace(
        LEDGER=M.A.LEDGER,
        column_cost=lambda ledger, w: M.A.physical_costs({k: ledger[:, i] for i, k in enumerate(M.A.LEDGER)}, vars(w))[
            0
        ],
    )
    producer = pure_functions("measure.py", ["contrast_reports"], {"ABI": abi})
    report["contrasts"] = producer["contrast_reports"](confirmation, {"persistent": SimpleNamespace(**p["world"])})
    M.compare_report(report, vectors, {"persistent": p["world"]})
    report["contrasts"]["H_D90_minus_P_D90"]["captures"]["mean"] += 1
    with pytest.raises(ValueError, match="independent estimate"):
        M.compare_report(report, vectors, {"persistent": p["world"]})


@pytest.mark.parametrize("bad", ["missing", "aggregate", "selection", "role_table", "index_cpu"])
def test_shared_fixture_coverage_corruption(complete, bad):
    base, p, panels, selection, roles, indexes, data, budget = complete
    target = {
        "missing": "measurement/confirm/persistent/confirm/row_0003.npz",
        "aggregate": "measurement/confirm/persistent/confirm/scores.npz",
        "selection": "selection.json",
        "role_table": "confirmation_genotypes.npz",
        "index_cpu": "measurement/confirm/persistent/row_index.json",
    }[bad]
    path = base / target
    original = path.read_bytes()
    try:
        if bad == "missing":
            path.unlink()
        elif bad in ("aggregate", "role_table"):
            value = M.npz(path)
            value["F" if bad == "aggregate" else "genomes"][0, 0] += 1
            np.savez_compressed(path, **value)
        else:
            value = M.read(path)
            if bad == "selection":
                value["D90"] = {"genome_row": 63, "raw_sha256": p["panel_genotype_sha256"]["D90"][63]}
            else:
                value["confirm/row_0000.npz"]["cpu_seconds"] += 1
            save(path, value)
        with pytest.raises((ValueError, FileNotFoundError)):
            M.load_rows(base, p, panels)
    finally:
        path.write_bytes(original)


@pytest.mark.parametrize("bad", ["phase_cpu", "snapshot", "selection_pin", "selected_rate", "report_count"])
def test_phase_corruption(complete, bad):
    base, p, panels, selection, roles, indexes, data, budget0 = complete
    budget = copy.deepcopy(budget0)
    path = None
    if bad == "phase_cpu":
        budget["startup_screen_cpu_seconds"] = 14
    elif bad == "snapshot":
        budget["phase_receipts"]["screens_complete"]["row_snapshot"]["screen/D90"].pop("screen/row_0064.npz")
    else:
        path = (
            base
            / {
                "selection_pin": "selection.json",
                "selected_rate": "confirmation_projection.json",
                "report_count": "report.json",
            }[bad]
        )
        old = path.read_bytes()
        if bad == "selection_pin":
            path.write_bytes(old + b" ")
        else:
            value = M.read(path)
            if bad == "selected_rate":
                value["confirmation_role_rates"]["H_D90"] += 0.1
            else:
                value["research_genome_lives"] = 6207
            save(path, value)
    try:
        with pytest.raises(ValueError):
            M.phases(base, p, budget, indexes, selection, roles, {"calibration": 0.04, "screen": 1.3, "confirm": 0.04})
    finally:
        if path is not None:
            path.write_bytes(old)


def rescore(r, w):
    r["income"] = w["R_cap"] * r["captures"]
    r["cost"], _ = M.A.physical_costs(r, w)
    r["net"] = r["income"] - r["cost"] - r["guard_charge"]
    r["F_kernel"] = r["net"] / w["T"]
    r["F"] = r["F_kernel"] - r["extinct_charge"]
    r["ledger"] = np.stack([r["F_kernel" if k == "F" else k] for k in M.A.LEDGER], axis=1)


def test_abi3_ordinary_growth_guard_extinction_and_disjoint_counters():
    assert len(M.A.LEDGER) == 57 and len(M.A.COLS) == 60 and "low_light_captures" not in M.A.LEDGER
    r = row(10)
    w = world()
    # Three legitimate states including growth, paid guard, and natural extinction.
    r["births"][0] = 2
    r["n_end"][0] = 3
    r["n_peak"][0] = 3
    r["n_S_end"][0] = 3
    r["status"][1] = 2
    r["t_end"][1] = 500
    r["guard_charge"][1] = w["c_live"] * w["n_max"] * 524
    r["status"][2] = 1
    r["t_end"][2] = 500
    r["t_ext"][2] = 500
    r["deaths"][2] = 1
    r["n_end"][2] = 0
    r["n_S_end"][2] = 0
    r["extinct_charge"][2] = w["c_live"] * 524 / 1024
    r["arrivals_dropped"][3] = 10
    r["rejects_wall"][3] = 10
    rescore(r, w)
    result = M.A.validate_row(r, w)
    assert result["guarded"] == result["extinct"] == 1 and result["all_fitness_rows_retained"] == 512
    r["births"][4] = 1
    rescore(r, w)
    with pytest.raises(ValueError, match="census"):
        M.A.validate_row(r, w)


@pytest.mark.parametrize("field", ["income", "cost", "F", "captures", "guard_charge", "extinct_charge"])
def test_corrupt_physical_or_scored_column_rejected(field):
    r = row(10)
    r[field][0] += 1
    with pytest.raises(ValueError):
        M.A.validate_row(r, world())


def test_selected_loser_and_tie_no_parent_fallback():
    rows = {i: {"F": np.full(32, 100 if i == 0 else -10.0)} for i in range(65)}
    assert M.selected_mutant(rows) == 1
    rows[64]["F"][:] = -9
    assert M.selected_mutant(rows) == 64
    rows[63]["F"][:] = -9
    assert M.selected_mutant(rows) == 63


@pytest.mark.parametrize("bad", ["missing", "short", "nan"])
def test_selection_needs_whole32_all65(bad):
    rows = {i: {"F": np.zeros(32)} for i in range(65)}
    if bad == "missing":
        del rows[64]
    elif bad == "short":
        rows[1]["F"] = np.zeros(31)
    else:
        rows[1]["F"][0] = np.nan
    with pytest.raises(ValueError):
        M.selected_mutant(rows)


def test_pairing_keeps_negative_null_and_duplicate_roles():
    data = {"persistent": {0: row(10), 1: row(10), 2: row(9), 3: row(10)}}
    result, vectors = M.contrasts(data, {"persistent": world()})
    assert result["H_D90_minus_P_D90"]["captures"]["mean"] == -1
    assert all(np.all(v == 0) for k, v in vectors.items() if k.startswith("H_L92"))
    data["persistent"][2]["seeds"] = data["persistent"][2]["seeds"][::-1]
    with pytest.raises(ValueError, match="ordered seeds"):
        M.contrasts(data, {"persistent": world()})


def test_actual_four_field_receipts_and_monitor_ast():
    old = ROOT / "results/visibility_flash_gradient_20261014/analysis/fixtures" if ROOT else None
    if old is not None:
        attempt, budget = M.read(old / "Y_attempt.json"), M.read(old / "Y_budget.json")
    else:
        budget = M.read(SOURCE / "inputs/Y/budget.json")
        attempt = {"monitor": {k: budget["process_identities"][0][k] for k in ("pid", "ppid", "pgid", "start_ticks")}}
    M.owned_processes(attempt, budget, ["gradient"])
    tree = ast.parse((SOURCE / "monitor.py").read_text())
    f = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "process_identity")
    value = next(n.value for n in ast.walk(f) if isinstance(n, ast.Return))
    assert [ast.literal_eval(k) for k in value.keys] == ["pid", "ppid", "pgid", "start_ticks"]
    budget["process_identities"][1]["ppid"] = 1
    with pytest.raises(ValueError):
        M.owned_processes(attempt, budget, ["gradient"])


def test_exact_V_packing_with_no_engine_imports(monkeypatch):
    vp = ROOT / "results/prediction_information_20261014/protocol.json" if ROOT else SOURCE / "inputs/V/protocol.json"
    assert M.sha(vp) == M.V_PROTOCOL
    w = M.read(vp)["world"]
    tree = ast.parse((ROOT / "src/life/spec.py" if ROOT else M.external(SOURCE, "src/life/spec.py")).read_text())
    cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "World")
    fields = [n.target.id for n in cls.body if isinstance(n, ast.AnnAssign)]
    keys = [
        k
        for k in fields[: fields.index("visibility_mode")]
        if k not in ("name", "stage", "implemented", "lattice", "lives")
    ]
    packed = np.asarray([w[k] for k in keys], dtype=np.float64)
    p = {
        "world": w,
        "V_protocol_sha256": M.V_PROTOCOL,
        "world_packing": {"abi": 3, "keys": keys, "values": packed.tolist(), "raw_sha256": M.raw_sha(packed)},
        "configuration_changes": {
            "life.world": "catch_speck_l4",
            "life.abi": 3,
            "world": {"v_t": 0.3, "tau_turn": 200},
        },
    }
    original_sha, original_read = M.sha, M.read
    monkeypatch.setattr(
        M, "sha", lambda path: original_sha(vp if str(path).endswith("inputs/V/protocol.json") else path)
    )
    monkeypatch.setattr(
        M,
        "read",
        lambda path: original_read(vp) if str(path).endswith("inputs/V/protocol.json") else {"status": "complete"},
    )
    M.check_worlds(Path("/synthetic"), p, tree)
    p["world_packing"]["values"][0] += 1
    with pytest.raises(ValueError, match="packing"):
        M.check_worlds(Path("/synthetic"), p, tree)


def test_cost_gate_covers_unselected_historical_max():
    f = pure_functions("measure.py", ["calibration_projection", "selected_projection"])
    rates = {b: [0.1] * 65 for b in M.PARENTS}
    rates["D90"][45] = 1.13
    calibration = {b: {i: {"cpu_seconds": 0.2} for i in (0, 1)} for b in M.PARENTS}
    value = f["calibration_projection"](calibration, 30, rates)
    assert value["confirmation_role_rates"]["H_D90"] == 1.13
    assert value["screen_row_rate_floors"]["D90"][44] == 0.1
    assert value["screen_row_rate_floors"]["D90"][45] == 1.13
    assert value["confirmation_role_rates"]["P_D90"] == 0.1
    assert value["feasible"]


def test_unregistered_emits_no_outcomes(tmp_path, monkeypatch):
    monkeypatch.setattr(M, "PROTOCOL_SHA", None)
    summary, vectors = M.analyze(tmp_path)
    assert summary["status"] == "incomplete" and summary["scientific_outcomes_emitted"] is False and vectors == {}


def test_exactly_one_standard_identity_and_explicit_abi3_source():
    tree = ast.parse((SOURCE / "measure.py").read_text())
    calls = [
        n
        for n in ast.walk(tree)
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id == "numerical_identity"
    ]
    assert len(calls) == 1
    prep = ast.parse((SOURCE / "prepare.py").read_text())
    assert not any(
        isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id == "numerical_identity"
        for n in ast.walk(prep)
    )
    score = (SOURCE / "scoring.py").read_text()
    assert "ABI = spec.V3" in score and "threads=THREADS" in score and "THREADS = 2" in score
    assert "evaluator.abi.version != 3" in score


@pytest.mark.parametrize("failure", [None, "total_cap", "screen_cap", "failed", "phase", "raw_fits_wrong_scope"])
def test_actual_complete_resource_contract(monkeypatch, failure):
    old = ROOT / "results/visibility_flash_gradient_20261014/analysis/fixtures" if ROOT else None
    if old is not None:
        attempt, budget = M.read(old / "Y_attempt.json"), M.read(old / "Y_budget.json")
    else:
        budget = M.read(SOURCE / "inputs/Y/budget.json")
        attempt = {"monitor": {k: budget["process_identities"][0][k] for k in ("pid", "ppid", "pgid", "start_ticks")}}
    digest = "a" * 64
    p = {"file_pins": {"measure.py": digest}, "production_pins": {"src/life/spec.py": digest}}
    required = dict(p["file_pins"])
    for name in (
        "protocol.json",
        "monitor.py",
        "resource_clearance.json",
        "analysis/analyze.py",
        "analysis/offline_accounting.py",
        "analysis/panel_replay.py",
        "analysis/helpers/genetics.py",
    ):
        required[name] = digest
    ready = {"status": "released", "source_pins": required, "production_pins": p["production_pins"]}
    attempt["ready_sha256"] = digest
    budget.update(
        status="complete",
        exit_code=0,
        phase="confirmation",
        cap_cpu_seconds=5400,
        startup_screen_cap_cpu_seconds=3400,
        startup_calibration_cap_cpu_seconds=180,
        confirmation_reserve_cpu_seconds=2000,
        running={},
        queued=[],
        completed=[{"name": "gradient", "exit_code": 0}],
        ready=ready,
        cpu_seconds=100,
        startup_screen_cpu_seconds=50,
        wall_seconds=60,
        affinity=[0, 1],
        reason=None,
    )
    clearance = {
        "status": "cleared",
        "all_processes_exited": True,
        "budget_pins": {"old_budget.json": digest},
        "processes": [{"pid": 1, "start_ticks": 1}],
        "process_groups": [1],
    }
    values = {
        "ready.json": ready,
        "resource_clearance.json": clearance,
        "attempt.json": attempt,
        "budget.json": budget,
        "old_budget.json": {"status": "incomplete", "running": {}, "queued": []},
    }
    if failure == "total_cap":
        budget["cpu_seconds"] = 5390
    elif failure == "screen_cap":
        budget["startup_screen_cpu_seconds"] = 3390
    elif failure == "failed":
        budget["cleanup_error"] = "survivor"
    elif failure == "phase":
        budget["phase"] = "startup_screen"
    elif failure == "raw_fits_wrong_scope":
        budget["confirmation_reserve_cpu_seconds"] = 3800
    monkeypatch.setattr(M, "read", lambda path: values[Path(path).name])
    monkeypatch.setattr(M, "sha", lambda path: digest)
    monkeypatch.setattr(M, "operation", lambda base, name: Path(name))
    monkeypatch.setattr(M, "external", lambda base, name: Path(name))
    monkeypatch.setattr(M, "pins", lambda *a, **kw: None)
    if failure is None:
        _, _, resource = M.resources(Path("/synthetic"), p)
        assert resource["total_cpu_seconds"] == 100
    else:
        with pytest.raises(ValueError):
            M.resources(Path("/synthetic"), p)


@pytest.mark.parametrize("failure", [None, "extra_invocation", "missing_library", "golden"])
def test_exact_startup_identity_scope(monkeypatch, failure):
    identity = {"golden": dict(M.GOLDEN), "kernels": {"False": "f" * 64, "True": "e" * 64}, "metadata": "frozen"}
    p = {"expected_numerical_identity": copy.deepcopy(identity)}
    record = {
        "identity": identity,
        "preexpected_fields": sorted(identity),
        "newly_captured_fields": [],
        "numerical_identity_invocations": 1,
        "golden_lives": dict(M.GOLDEN_SCOPE),
    }
    binaries = [Path("/synthetic/full"), Path("/synthetic/fast")]
    if failure == "extra_invocation":
        record["numerical_identity_invocations"] = 2
    elif failure == "missing_library":
        binaries = binaries[:1]
    elif failure == "golden":
        record["identity"]["golden"]["all"] = "bad"
    monkeypatch.setattr(M, "read", lambda path: record)
    monkeypatch.setattr(Path, "rglob", lambda self, pattern: iter(binaries))
    monkeypatch.setattr(M, "sha", lambda path: "f" * 64 if path.name == "full" else "e" * 64)
    if failure is None:
        M.check_startup(Path("/synthetic"), p)
    else:
        with pytest.raises(ValueError):
            M.check_startup(Path("/synthetic"), p)
