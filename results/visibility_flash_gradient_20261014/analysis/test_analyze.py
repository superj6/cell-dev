"""Focused synthetic AC accounting/selection/covariance checks; zero lives."""

import ast
import hashlib
import importlib.util
from pathlib import Path

import numpy as np
import pytest

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("AC_test_reader", HERE / "analyze.py")
M = importlib.util.module_from_spec(spec)
spec.loader.exec_module(M)
SOURCE = (
    HERE.parent
    if (HERE.parent / "measure.py").is_file()
    else HERE.parent / "autonomous_visibility_flash_gradient_20261014"
)
ROOT = next((p for p in HERE.parents if (p / "src/life/spec.py").is_file()), None)


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


def rows():
    variable = np.arange(512) % 5
    return {
        "flash": {i: row(10 + i + (variable if i >= 4 else 0)) for i in range(6)},
        "blink": {i: row(10 + i + (variable - 2 if i >= 4 else 0)) for i in range(6)},
    }


def test_complete_paired_world_interactions_keep_covariance():
    data = rows()
    summary, vectors = M.contrasts(data, {name: world() for name in M.WORLDS})
    assert len(vectors) == 16 * 75
    key = "H_D90_minus_P_D90"
    f = summary["within"]["flash"][key]["columns"]["captures"]
    b = summary["within"]["blink"][key]["columns"]["captures"]
    interaction = summary["interactions"][key]["captures"]
    assert f["se"] > 0 and b["se"] > 0
    assert interaction["mean"] == 2 and interaction["se"] == 0
    np.testing.assert_array_equal(vectors["interaction__" + key + "__captures"], 2)


def test_duplicate_H_B_roles_retained_with_exact_zero_differences():
    data = rows()
    for w in M.WORLDS:
        data[w][4] = data[w][2]
        data[w][5] = data[w][3]
    _, vectors = M.contrasts(data, {name: world() for name in M.WORLDS})
    assert len(vectors) == 1200
    for name, value in vectors.items():
        if "H_D90_minus_B_D90" in name or "H_L92_minus_B_L92" in name:
            assert np.all(value == 0)


def test_selection_uses_all_mutants_and_keeps_losing_winner_and_tie_order():
    r = {i: {"F": np.full(32, 100 if i == 0 else -10.0)} for i in range(65)}
    assert M.selected_mutant(r) == 1
    r[64]["F"][:] = -9
    assert M.selected_mutant(r) == 64
    r[63]["F"][:] = -9
    assert M.selected_mutant(r) == 63


@pytest.mark.parametrize("bad", ["missing", "short", "nan"])
def test_selection_rejects_partial_or_invalid_screens(bad):
    r = {i: {"F": np.full(32, float(i))} for i in range(65)}
    if bad == "missing":
        del r[64]
    elif bad == "short":
        r[1]["F"] = np.zeros(31)
    else:
        r[1]["F"][0] = np.nan
    with pytest.raises(ValueError):
        M.selected_mutant(r)


def test_cross_world_reordered_seeds_rejected():
    data = rows()
    data["blink"] = {i: dict(r, seeds=r["seeds"][::-1]) for i, r in data["blink"].items()}
    with pytest.raises(ValueError, match="same ordered seeds"):
        M.contrasts(data, {name: world() for name in M.WORLDS})


@pytest.mark.parametrize("field", ["income", "cost", "F", "captures", "low_light_captures", "births"])
def test_physical_corruption_blocks_contrasts(field):
    data = rows()
    data["flash"][4][field][0] += 1
    with pytest.raises(ValueError):
        M.contrasts(data, {name: world() for name in M.WORLDS})


def test_real_four_field_monitor_receipts():
    budget = M.read(HERE / "fixtures/Y_budget.json")
    attempt = M.read(HERE / "fixtures/Y_attempt.json")
    assert set(attempt["monitor"]) == {"pid", "ppid", "pgid", "start_ticks"}
    M.owned_processes(attempt, budget, ["gradient"])


@pytest.mark.parametrize("field,value", [("ppid", 1), ("pgid", 1), ("start_ticks", 0)])
def test_real_receipt_identity_corruption_rejected(field, value):
    budget = M.read(HERE / "fixtures/Y_budget.json")
    attempt = M.read(HERE / "fixtures/Y_attempt.json")
    budget["process_identities"][1][field] = value
    with pytest.raises(ValueError):
        M.owned_processes(attempt, budget, ["gradient"])


def test_actual_monitor_receipt_schema():
    source = (SOURCE / "monitor.py").read_text()
    tree = ast.parse(source)
    function = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "process_identity")
    value = next(n for n in ast.walk(function) if isinstance(n, ast.Return)).value
    assert [ast.literal_eval(k) for k in value.keys] == ["pid", "ppid", "pgid", "start_ticks"]
    assert "start_new_session=True" in source


def test_actual_public_Y_budget_mapping_reads_metadata_only(tmp_path):
    tree = ast.parse((SOURCE / "prepare.py").read_text())
    mapping = next(
        n
        for n in tree.body
        if isinstance(n, ast.Assign) and isinstance(n.targets[0], ast.Name) and n.targets[0].id == "Y_SOURCE_MAP"
    )
    function = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "historical_source")
    public_y = ROOT / "results/visibility_gradient_20261014" if ROOT is not None else None
    if public_y is None or not (public_y / "operations/budget.json").is_file():
        # Portable tests retain only this exact historical metadata, not the entire old archive.
        public_y = tmp_path / "public_Y_metadata"
        (public_y / "operations").mkdir(parents=True)
        (public_y / "operations/budget.json").write_bytes((SOURCE / "inputs/Y/budget.json").read_bytes())
    env = {"Y": public_y}
    exec(compile(ast.Module(body=[mapping, function], type_ignores=[]), "historical_source_only", "exec"), env)
    path = env["historical_source"]("budget.json")
    assert path == env["Y"] / "operations/budget.json"
    assert M.read(path)["status"] == "complete"
    assert not (env["Y"] / "budget.json").exists()


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(M.json_bytes(value))


def synthetic_complete(base, monkeypatch):
    """Pure numeric fixtures, deliberately not valid genetic programs; no engine imports."""
    monkeypatch.setattr(M, "PROTOCOL_SHA", "synthetic-protocol")
    p = {
        "worlds": {w: world() for w in M.WORLDS},
        "seeds": {stage: list(range(1000 * j, 1000 * j + n)) for j, (stage, n) in enumerate(M.N.items(), 1)},
        "historical_blink_cpu_per_life": {b: [0.01] * 65 for b in M.PARENTS},
    }
    panels = {b: np.broadcast_to(np.arange(65, dtype=np.float32)[:, None], (65, 875)).copy() for b in M.PARENTS}
    p["panel_genotype_sha256"] = {b: [M.raw_sha(x) for x in table] for b, table in panels.items()}
    selection = {b: {"genome_row": 64, "raw_sha256": p["panel_genotype_sha256"][b][64]} for b in M.PARENTS}
    save(base / "selection.json", selection)
    role_rows = {f"{a}_{b}": i for b in M.PARENTS for a, i in (("P", 0), ("B", M.B_ROWS[b]), ("H", 64))}
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
    for key in ("screen/D90", "screen/L92", "confirm/flash", "confirm/blink"):
        folder = base / "measurement" / key
        index, data[key] = {}, {}
        stages = (
            {"calibration": [0, 1], "screen": list(range(65))}
            if key.startswith("screen/")
            else {"confirm": list(range(6))}
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
                        "world": "flash",
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


def test_complete146_raw_rows_and_aggregates(tmp_path, monkeypatch):
    p, panels, selected, roles, index, data = synthetic_complete(tmp_path, monkeypatch)
    selection, actual_roles, screens, confirmation, indexes, cpu, pins = M.load_rows(tmp_path, p, panels)
    assert selection == selected and actual_roles == roles and indexes == index
    assert len([x for x in pins if "/row_" in x and x.endswith(".npz")]) == 146
    assert all(len(x["screen"]) == 65 for x in screens.values())
    assert all(len(x) == 6 for x in confirmation.values())
    assert (
        sum(M.N[stage] * (4 if stage == "calibration" else 130 if stage == "screen" else 12) for stage in M.N) == 10312
    )
    _, vectors = M.contrasts(confirmation, p["worlds"])
    # Independently construct the worker's 66 metric keys and signs from raw physical columns.
    worker = {}
    for prefix in {name.rsplit("__", 1)[0] for name in vectors if "__F__" not in name}:
        terms = {key: vectors[prefix + "__" + key] for key in M.A.COLS + ("bright_captures",)}
        terms.update(
            capture_income=vectors[prefix + "__F__capture_income"],
            ordinary_cost=sum(vectors[prefix + "__F__" + name + "_cost_saving"] for name, _, _ in M.A.prices(world())),
            guard_cost=vectors[prefix + "__F__guard_charge_saving"],
            extinction_cost=vectors[prefix + "__F__extinction_charge_saving"],
        )
        worker[prefix] = {k: {q: M.A.stats(v)[q] for q in ("mean", "se", "n")} for k, v in terms.items()}
    M.compare_report({"contrasts": worker}, vectors, p["worlds"])
    worker["interaction__H_D90_minus_P_D90"]["captures"]["mean"] += 1
    with pytest.raises(ValueError, match="independent estimate"):
        M.compare_report({"contrasts": worker}, vectors, p["worlds"])


@pytest.mark.parametrize("failure", ["missing_row", "extra_row", "aggregate", "role_table", "selection", "row_index"])
def test_complete_coverage_corruption_is_rejected(tmp_path, monkeypatch, failure):
    p, panels, selected, roles, index, data = synthetic_complete(tmp_path, monkeypatch)
    if failure == "missing_row":
        (tmp_path / "measurement/confirm/blink/confirm/row_0005.npz").unlink()
    elif failure == "extra_row":
        np.savez_compressed(tmp_path / "measurement/confirm/blink/confirm/row_0006.npz", x=[1])
    elif failure == "aggregate":
        path = tmp_path / "measurement/confirm/blink/confirm/scores.npz"
        z = M.npz(path)
        z["F"][0, 0] += 1
        np.savez_compressed(path, **z)
    elif failure == "role_table":
        path = tmp_path / "confirmation_genotypes.npz"
        z = M.npz(path)
        z["genomes"][4, 0] += 1
        np.savez_compressed(path, **z)
    elif failure == "selection":
        selected["D90"] = {"genome_row": 63, "raw_sha256": p["panel_genotype_sha256"]["D90"][63]}
        save(tmp_path / "selection.json", selected)
    else:
        path = tmp_path / "measurement/confirm/blink/row_index.json"
        z = M.read(path)
        z["confirm/row_0000.npz"]["cpu_seconds"] += 1
        save(path, z)
    with pytest.raises((ValueError, FileNotFoundError)):
        M.load_rows(tmp_path, p, panels)


def test_unregistered_source_reader_emits_no_outcomes(tmp_path, monkeypatch):
    monkeypatch.setattr(M, "PROTOCOL_SHA", None)
    summary, vectors = M.analyze(tmp_path)
    assert summary["status"] == "incomplete" and summary["scientific_outcomes_emitted"] is False and vectors == {}


def test_actual_prepared_protocol_bound_without_engine_imports():
    p, panels = M.verify_protocol(SOURCE)
    assert M.sha(SOURCE / "protocol.json") == M.PROTOCOL_SHA
    assert len(p["file_pins"]) == 167 and len(p["production_pins"]) == 35
    assert sum(len(x) for x in panels.values()) == 130
    assert p["roles"] == list(M.LABELS)


def phase_fixture(base, p, selection, roles, indexes):
    save(base / "attempt.json", {"synthetic": True})
    save(base / "startup_identity.json", {"synthetic": True})
    initial_rates = {b: 0.005 for b in M.PARENTS}
    initial_roles = {"flash": {label: 0.005 for label in M.LABELS}, "blink": {}}
    for b in M.PARENTS:
        initial_roles["blink"].update({f"P_{b}": 0.01, f"B_{b}": 0.01, f"H_{b}": 0.01})
    save(
        base / "calibration_projection.json",
        {
            "flash_batch_max_cpu_per_life": initial_rates,
            "startup_cpu_seconds": 5.0,
            "confirmation_role_rates": initial_roles,
            "screen_projection_cpu_seconds": 5 + 1.5 * 2080 * sum(initial_rates.values()),
            "confirmation_projection_cpu_seconds": 180
            + 1.5 * 512 * sum(v for g in initial_roles.values() for v in g.values()),
            "screen_threshold": 3390,
            "confirmation_threshold": 3790,
            "feasible": True,
        },
    )
    selected_roles = {"flash": {}, "blink": {}}
    for b in M.PARENTS:
        for prefix in ("P", "B", "H"):
            selected_roles["flash"][f"{prefix}_{b}"] = 0.01 / 32
            selected_roles["blink"][f"{prefix}_{b}"] = 0.01
    save(
        base / "confirmation_projection.json",
        {
            "confirmation_role_rates": selected_roles,
            "confirmation_projection_cpu_seconds": 180
            + 1.5 * 512 * sum(v for g in selected_roles.values() for v in g.values()),
            "confirmation_threshold": 3790,
            "feasible": True,
        },
    )
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
        "research_genome_lives": 10304,
        "validation_lives": 10,
        "total_genome_lives": 10314,
        "row_index_sha256": {k: M.sha(base / "measurement" / k / "row_index.json") for k in indexes},
        "row_cpu_seconds": 1.46,
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


@pytest.mark.parametrize(
    "failure", [None, "phase_cpu", "row_snapshot", "selection_pin", "selected_rate", "partial_report"]
)
def test_actual_phase_schema_and_fail_closed_mutations(tmp_path, monkeypatch, failure):
    p, panels, selected, roles, indexes, data = synthetic_complete(tmp_path, monkeypatch)
    budget = phase_fixture(tmp_path, p, selected, roles, indexes)
    cpu = {"calibration": 0.04, "screen": 1.3, "confirm": 0.12}
    if failure == "phase_cpu":
        budget["startup_screen_cpu_seconds"] = 14.0
    elif failure == "row_snapshot":
        budget["phase_receipts"]["screens_complete"]["row_snapshot"]["screen/D90"].pop("screen/row_0064.npz")
    elif failure == "selection_pin":
        path = tmp_path / "selection.json"
        path.write_bytes(path.read_bytes() + b" ")
    elif failure == "selected_rate":
        path = tmp_path / "confirmation_projection.json"
        value = M.read(path)
        value["confirmation_role_rates"]["flash"]["H_D90"] = 1
        save(path, value)
    elif failure == "partial_report":
        path = tmp_path / "report.json"
        value = M.read(path)
        value["status"] = "incomplete"
        save(path, value)
    if failure is None:
        M.phases(tmp_path, p, budget, indexes, selected, roles, cpu)
    else:
        with pytest.raises(ValueError):
            M.phases(tmp_path, p, budget, indexes, selected, roles, cpu)
