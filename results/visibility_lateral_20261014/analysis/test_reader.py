"""AA source-only eighteen-row closure and actual pure producer-name regression; no engine imports."""

import ast
import importlib.util
from pathlib import Path

import numpy as np
import pytest

HERE = Path(__file__).resolve().parent


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


M = load("AA_reader_test", HERE / "analyze.py")
F = load("AA_row_fixture", HERE / "test_accounting.py")
SOURCE = (
    HERE.parent if (HERE.parent / "measure.py").is_file() else HERE.parent / "autonomous_visibility_lateral_20261014"
)


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(M.json_bytes(value))


def producer_contrasts():
    tree = ast.parse((SOURCE / "measure.py").read_text())
    fn = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "contrasts")
    env = {
        "LABELS": M.LABELS,
        "CONDITIONS": M.CONDITIONS,
        "PAIRS": [(g, a, b) for g, pairs_ in M.PAIRS.items() for a, b in pairs_],
    }
    exec(compile(ast.Module(body=[fn], type_ignores=[]), "<retained pure producer contrasts>", "exec"), env)
    return env["contrasts"]


def stats(values):
    return {"mean": float(values.mean()), "se": float(values.std(ddof=1) / np.sqrt(len(values))), "n": len(values)}


def fixture(base):
    p = {
        "seeds": list(range(128)),
        "worlds": {c: dict(F.world(), fork_flags=f) for c, f in zip(M.CONDITIONS, (0, 16, 2064))},
        "genotypes_file": "synthetic_metadata.txt",
        "genotype_sha256": dict(zip(M.LABELS, ["synthetic" + str(i) for i in range(6)])),
    }
    (base / p["genotypes_file"]).write_text("Explicit synthetic identity metadata; no organism or genome table.\n")
    save(base / "startup_identity.json", {"synthetic": True})
    rows, index, values = {}, {}, {metric: {} for metric in M.METRICS}
    folder = base / "measurement"
    for condition in M.CONDITIONS:
        rows[condition] = {}
        (folder / condition).mkdir(parents=True)
        for i, label in enumerate(M.LABELS):
            original = F.row()
            r = {
                k: np.tile(v, (32, 1)) if k == "ledger" else np.tile(v, 32) if np.asarray(v).ndim else v.copy()
                for k, v in original.items()
            }
            extra = i * {"normal": 3, "freeze": 2, "freeze+lateral_off": 1}[condition]
            eligible = np.arange(128) % 4 < 2
            r["captures"][eligible] += extra
            r["clicks"][eligible] += extra
            F.rebuild(r, p["worlds"][condition])
            expected = {
                "protocol_sha256": M.PROTOCOL_SHA,
                "genotypes_sha256": M.sha(base / p["genotypes_file"]),
                "role": label,
                "condition": condition,
                "stage": condition,
                "genome_index": i,
                "genome_sha256": p["genotype_sha256"][label],
                "seeds": p["seeds"],
            }
            r.update(
                identity=np.asarray(M.canonical(expected)),
                seeds=np.asarray(p["seeds"], dtype=np.uint64),
                genome_index=np.asarray(i),
            )
            path = folder / condition / f"row_{i:04d}.npz"
            np.savez_compressed(path, **r)
            index[str(path.relative_to(folder))] = {"sha256": M.sha(path), "cpu_seconds": float(r["cpu_seconds"])}
            rows[condition][i] = r
        np.savez_compressed(
            folder / condition / "scores.npz",
            seeds=np.asarray(p["seeds"], dtype=np.uint64),
            genome_indices=np.arange(6),
            **{k: np.stack([rows[condition][i][k] for i in range(6)]) for k in M.A.COLS},
        )
        for metric in M.METRICS:
            key = M.METRIC_MAP.get(metric, metric)
            values[metric][condition] = np.stack(
                [M.A.metric_vectors(rows[condition][i], p["worlds"][condition])[key] for i in range(6)]
            )
    save(folder / "row_index.json", index)
    producer = producer_contrasts()
    paired = {metric: producer(v) for metric, v in values.items()}
    np.savez_compressed(
        folder / "paired.npz",
        **{metric + "___" + name: v for metric, group in paired.items() for name, v in group.items()},
    )
    report = {
        "status": "complete",
        "report_only": True,
        "genome_lives": 2304,
        "paired_seeds": 128,
        "startup_validation_genome_lives": 2,
        "protocol_sha256": M.PROTOCOL_SHA,
        "startup_identity_sha256": M.sha(base / "startup_identity.json"),
        "labels": M.LABELS,
        "conditions": M.CONDITIONS,
        "row_cpu_seconds": 0.18,
        "contrasts": {metric: {name: stats(v) for name, v in group.items()} for metric, group in paired.items()},
        "absolute": {
            metric: {c: {M.LABELS[i]: stats(v[i]) for i in range(6)} for c, v in group.items()}
            for metric, group in values.items()
        },
        "frozen_checks": {
            "coverage": [
                {"label": label, "complete_paired_lives": 64, "excluded_from_structural_equality_only": 64}
                for label in M.LABELS
            ],
            "window": [544, 1024],
            "all_fitness_rows_retained": True,
        },
    }
    save(folder / "report.json", report)
    return p, rows, report


def test_actual_monitor_records_four_fields():
    tree = ast.parse((SOURCE / "run_budgeted.py").read_text())
    fn = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "process_identity")
    result = next(n for n in ast.walk(fn) if isinstance(n, ast.Return)).value
    assert [ast.literal_eval(k) for k in result.keys] == ["pid", "ppid", "pgid", "start_ticks"]


def test_complete18rows_match_actual36_producer_names(tmp_path):
    p, _, _ = fixture(tmp_path)
    rows, report, cpu, _ = M.load_rows(tmp_path, p, {"cpu_seconds": 10.0})
    result, vectors = M.A.contrasts(rows, p["worlds"], M.PAIRS, M.LABELS)
    M.validate_report(tmp_path, rows, p, report, result, vectors)
    assert len(result["contrasts"]) == 36 and cpu == pytest.approx(0.18)
    assert all(x["all_fitness_rows_retained"] == 128 for x in result["frozen_structure"].values())


@pytest.mark.parametrize(
    "kind", ["missing", "stale", "seed", "raw58", "named_F", "aggregate", "paired_shape", "reported_sign", "CPU"]
)
def test_partial_or_corrupt_matrix_is_rejected(tmp_path, kind):
    p, rows, report = fixture(tmp_path)
    folder = tmp_path / "measurement"
    path = folder / "normal/row_0000.npz"
    if kind == "missing":
        path.unlink()
    elif kind == "stale":
        np.savez(folder / "normal/row_0006.npz", **rows["normal"][0])
    elif kind == "paired_shape":
        paired = M.npz(folder / "paired.npz")
        key = next(iter(paired))
        paired[key] = paired[key][None, :]
        np.savez_compressed(folder / "paired.npz", **paired)
    elif kind == "reported_sign":
        metric = report["contrasts"]["capture_income"]
        key = next(k for k in metric if "added_lateral_dependence" in k)
        metric[key]["mean"] *= -1
        save(folder / "report.json", report)
    elif kind == "aggregate":
        score = M.npz(folder / "normal/scores.npz")
        score["F"][0, 0] += 1
        np.savez_compressed(folder / "normal/scores.npz", **score)
    elif kind != "CPU":
        r = rows["normal"][0]
        if kind == "seed":
            r["seeds"] = r["seeds"][::-1].copy()
        if kind == "raw58":
            r["ledger"][0, 57] += 1
        if kind == "named_F":
            r["F"] += 1
        np.savez_compressed(path, **r)
        index = M.read(folder / "row_index.json")
        index["normal/row_0000.npz"]["sha256"] = M.sha(path)
        save(folder / "row_index.json", index)
    with pytest.raises((OSError, ValueError)):
        loaded, saved, _, _ = M.load_rows(tmp_path, p, {"cpu_seconds": 0.01 if kind == "CPU" else 10.0})
        result, vectors = M.A.contrasts(loaded, p["worlds"], M.PAIRS, M.LABELS)
        M.validate_report(tmp_path, loaded, p, saved, result, vectors)


def test_no_registered_protocol_produces_no_outcome(tmp_path):
    result, vectors = M.analyze(tmp_path)
    assert result["status"] == "incomplete" and result["scientific_outcomes_emitted"] is False and vectors == {}
