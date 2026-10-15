"""Offline exploratory shared-panel comparison. NumPy only; no engine or draws.

All screen candidates remain. Worlds have different seed sets; pairing is only
mutant versus its own parent within a world. Screen findings are selected,
multiple-comparison exploration, never held-out generalization evidence.
"""

import argparse
import csv
import hashlib
import importlib.util
import itertools
import json
import math
import subprocess
import sys
from pathlib import Path

sys.dont_write_bytecode = True
import numpy as np

HERE = Path(__file__).resolve().parent
WORLDS = {
    "blink": ("visibility_gradient_20261014", "Y", None, 4),
    "dim_flash": ("visibility_flash_gradient_20261014", "AC", "flash", 4),
    "persistent": ("prediction_gradient_20261014", "AE", "persistent", 3),
    "dark_flash": ("visibility_dark_tail_gradient_20261014", "AG", "flash5_dark", 4),
}
PARENTS = ("D90", "L92")
SOURCES = {
    "accounting_v4.py": "results/visibility_flash_gradient_20261014/analysis/offline_accounting.py",
    "accounting_v3.py": "results/prediction_gradient_20261014/analysis/offline_accounting.py",
}
RAW_METRICS = ("F", "captures", "n_end", "live_time", "spikes", "packets", "misses", "clicks", "path")
LIMITS = [
    "All four 32-life screens were used for selection, and this cross-world inspection is post hoc. No screen-based candidate is independently confirmed as broad or generalizing.",
    "128 mutants, four worlds and many correlated metrics are inspected; descriptive three-SE flags are not multiplicity-adjusted tests.",
    "Within each world every row shares32 seeds with its parent. Across worlds seed sets differ: no elementwise cross-world pairing or pooled cross-world SE is used.",
    "Candidates share two selected ancestors and a single fixed mutation panel per ancestor; rows and historical confirmations are not independent evolutionary replicates.",
    "These four related chase environments were all previously examined. None is an untouched held-out task. New per-life seeds test fixed-genome performance, not open-ended task generalization.",
    "Higher fitness can result from lower costs despite lost captures. Capture gains, ordinary savings, guard and extinction savings remain separate.",
    "Low-light captures are not comparable mechanisms across visibility regimes and do not identify memory. Persistent world has no ABI4 low-light column; it is missing, not zero.",
    "Existing512-life confirmations only cover previously frozen roles. They do not validate unconfirmed rows chosen by this analysis; independent historical batches remain separate.",
    "Parent comparisons use the parent within each environment. They do not compare absolute performance across tasks as if task difficulty were identical.",
]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def raw_sha(x):
    return hashlib.sha256(x.tobytes()).hexdigest()


def stats(x):
    x = np.asarray(x, dtype=np.float64)
    assert x.ndim == 1 and np.isfinite(x).all()
    m, se = float(x.mean()), float(x.std(ddof=1) / math.sqrt(len(x)))
    return {"mean": m, "se": se, "n": len(x), "positive_above_3se": m > 3 * se,
            "negative_below_minus3se": m < -3 * se}


def dump(path, value):
    with path.open("x") as f:
        json.dump(value, f, indent=2, allow_nan=False)
        f.write("\n")


def csv_write(path, records):
    fields = list(dict.fromkeys(k for r in records for k in r))
    with path.open("x", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(records)


class Audit:
    def __init__(self, root):
        self.root, self.pins, self.manifests = root, {}, {}

    def pin(self, path):
        rel = str(path.relative_to(self.root))
        self.pins[rel] = {"sha256": sha(path), "bytes": path.stat().st_size}
        return self.pins[rel]["sha256"]

    def archive(self, path):
        key = str(path.relative_to(self.root))
        if key not in self.manifests:
            self.pin(path / "manifest.json")
            self.manifests[key] = json.loads((path / "manifest.json").read_text())
            assert self.manifests[key]["phase"] == "terminal"
        return self.manifests[key]

    def read(self, base, name, npz=False, npy=False):
        path = base / name
        h = self.pin(path)
        info = self.archive(base)["artifacts"][name]
        assert h == info["sha256"] and path.stat().st_size == info["bytes"], str(path)
        if npz:
            with np.load(path, allow_pickle=False) as z:
                return {k: z[k].copy() for k in z.files}
        if npy:
            return np.load(path, allow_pickle=False)
        return json.loads(path.read_text())


def load_helpers(audit):
    modules = {}
    for name, original in SOURCES.items():
        path = HERE / "helpers" / name
        assert sha(path) == audit.pin(audit.root / original), name
        audit.pin(path)
        spec = importlib.util.spec_from_file_location(name[:-3], path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        modules[int(name[-4])] = module
    return modules


def load_row(audit, base, store, stage, index, world, accountant, expected, n):
    idx = audit.read(base, store + "/row_index.json")
    relative = f"{stage}/row_{index:04d}.npz"
    name = store + "/" + relative
    row = audit.read(base, name, npz=True)
    assert idx[relative]["sha256"] == sha(base / name)
    assert float(row["cpu_seconds"]) == idx[relative]["cpu_seconds"]
    identity = json.loads(str(row["identity"]))
    for k, v in expected.items():
        assert identity[k] == v, (name, k)
    assert int(row["genome_index"]) == index
    assert row["seeds"].dtype == np.uint64 and row["seeds"].shape == (n,)
    assert row["seeds"].tolist() == identity["seeds"]
    assert set(row) == set(accountant.COLS) | {"identity", "seeds", "genome_index", "ledger", "cpu_seconds", "wall_seconds"}
    health = accountant.validate_row(row, world, n)
    return row, health, name


def contrast(row, parent, world, accountant):
    assert np.array_equal(row["seeds"], parent["seeds"])
    window = world["T"] - world["t_open"]
    out = {key: row[key] - parent[key] for key in RAW_METRICS}
    if "low_light_captures" in row:
        out["low_light_captures"] = row["low_light_captures"] - parent["low_light_captures"]
        out["bright_captures"] = out["captures"] - out["low_light_captures"]
    wc, wp = accountant.physical_costs(row, world)
    pc, pp = accountant.physical_costs(parent, world)
    out.update(capture_income=(row["income"] - parent["income"]) / window,
               ordinary_cost_saving=(pc - wc) / window,
               guard_charge_saving=(parent["guard_charge"] - row["guard_charge"]) / window,
               extinction_charge_saving=parent["extinct_charge"] - row["extinct_charge"])
    out.update({"cost_saving_" + k: (pp[k] - wp[k]) / window for k in wp})
    residual = out["F"] - sum(out[k] for k in ("capture_income", "ordinary_cost_saving", "guard_charge_saving", "extinction_charge_saving"))
    assert np.allclose(residual, 0, rtol=0, atol=1e-9)
    return out


def record(world_name, study, parent, panel_row, genome, row, baseline, world, accountant, source, kind):
    vectors = contrast(row, baseline, world, accountant)
    result = {"world": world_name, "study": study, "parent": parent, "panel_row": panel_row,
              "genome_sha256": genome, "evidence_kind": kind, "source_row": source,
              "n_lives": len(row["F"]), "screen_selection_inference": kind == "exploratory_screen"}
    for key in RAW_METRICS + (("low_light_captures",) if "low_light_captures" in row else ()):
        result[key + "_absolute_mean"] = float(row[key].mean())
        result[key + "_parent_mean"] = float(baseline[key].mean())
    result["ordinary_cost_absolute_per_time"] = float(accountant.physical_costs(row, world)[0].mean() / world["T"])
    result["captures_parent_fraction"] = float(row["captures"].mean() / baseline["captures"].mean())
    for key, values in vectors.items():
        st = stats(values)
        result[key + "_delta_mean"] = st["mean"]
        result[key + "_delta_se"] = st["se"]
        result[key + "_positive_3se_descriptive"] = st["positive_above_3se"]
        result[key + "_negative_3se_descriptive"] = st["negative_below_minus3se"]
    result["status_nonzero"] = int(np.count_nonzero(row["status"]))
    result["capture_income_exceeds_cost_saving"] = result["capture_income_delta_mean"] > result["ordinary_cost_saving_delta_mean"]
    return result, vectors


def run(root, out):
    assert not out.exists(), "Use a fresh output directory; evidence is never overwritten."
    audit = Audit(root)
    accountants = load_helpers(audit)
    screen, confirmed, vectors, world_info, shared, selections = [], [], {}, {}, None, {}
    counts = {"screen_rows": 0, "screen_lives": 0, "confirmed_raw_rows": 0, "confirmed_raw_lives": 0}
    for key, (directory, study, world_label, abi) in WORLDS.items():
        base = root / "results" / directory
        p = audit.read(base, "protocol.json")
        protocol_hash = sha(base / "protocol.json")
        assert audit.archive(base)["protocol_sha256"] == protocol_hash
        expected_archive_status = ("complete_with_separate_reviewed_receipt_schema_correction"
                                   if study == "Y" else "complete_independently_reconciled")
        assert audit.archive(base)["status"] == expected_archive_status
        assert audit.read(base, "operations/budget.json")["status"] == "complete"
        selection = audit.read(base, "selection.json")
        selections[key] = selection
        if shared is None:
            shared = p["panel_genotype_sha256"]
        assert p["panel_genotype_sha256"] == shared
        world = p["worlds"][world_label] if "worlds" in p else p["world"]
        assert world["T"] == 1024 and world["R_cap"] == 500 and world["t_open"] == 0
        account = accountants[abi]
        world_info[key] = {"study": study, "archive": str(base.relative_to(root)), "protocol_sha256": protocol_hash,
                           "abi": abi, "raw_ledger_columns": list(account.LEDGER), "world": world,
                           "screen_seeds": p["seeds"]["screen"], "selected_rows": selection}
        for parent in PARENTS:
            panel_path = ("inputs/" if study == "Y" else "inputs/Y/inputs/") + parent + "/genomes.npy"
            panel = audit.read(base, panel_path, npy=True)
            assert panel.shape == (65, 875) and panel.dtype == np.float32 and np.isfinite(panel).all()
            assert [raw_sha(x) for x in panel] == shared[parent]
            store = "measurement/" + parent if study == "Y" else "measurement/screen/" + parent
            rows = []
            for i in range(65):
                expected = {"protocol_sha256": protocol_hash, "background": parent, "genome_index": i,
                            "genome_sha256": shared[parent][i], "stage": "screen", "seeds": p["seeds"]["screen"]}
                if world_label is not None:
                    expected["world"] = world_label
                row, health, name = load_row(audit, base, store, "screen", i, world, account, expected, 32)
                rows.append(row)
                rec, vec = record(key, study, parent, i, shared[parent][i], row, rows[0], world, account,
                                  str((base/name).relative_to(root)), "exploratory_screen")
                rec["original_F_selected_in_this_world"] = i == selection[parent]["genome_row"]
                rec["health"] = health
                screen.append(rec)
                vectors.update({f"screen__{key}__{parent}__row{i:02d}__{k}": v for k, v in vec.items()})
                counts["screen_rows"] += 1
                counts["screen_lives"] += len(row["F"])
            assert sorted(range(1, 65), key=lambda i: (-float(rows[i]["F"].mean()), i))[0] == selection[parent]["genome_row"]

        # Retain every existing mutant-parent comparison from the frozen512-life roles.
        confirm_worlds = p["worlds"] if study == "AC" else {world_label or "blink": world}
        role_record = audit.read(base, "confirmation_roles.json") if study != "Y" else None
        for label, cw in confirm_worlds.items():
            ck = {"flash": "dim_flash", "flash5_dark": "dark_flash"}.get(label, label)
            for parent in PARENTS:
                if study == "Y":
                    positions = [(0, 0), (selection[parent]["genome_row"], selection[parent]["genome_row"])]
                    store = "measurement/" + parent
                else:
                    positions = [(j, role_record["panel_rows"][role]) for j, role in enumerate(p["roles"]) if role.endswith("_" + parent)]
                    store = "measurement/confirm/" + label
                crows = []
                for j, i in positions:
                    expected = {"protocol_sha256": protocol_hash, "genome_sha256": shared[parent][i],
                                "stage": "confirm", "seeds": p["seeds"]["confirm"]}
                    if study != "Y":
                        expected.update(world=label, confirmation_roles_sha256=sha(base / "confirmation_roles.json"))
                    else:
                        expected.update(background=parent)
                    row, _, name = load_row(audit, base, store, "confirm", j, cw, account, expected, 512)
                    crows.append((i, row, name))
                    counts["confirmed_raw_rows"] += 1
                    counts["confirmed_raw_lives"] += len(row["F"])
                baseline = next(row for i, row, _ in crows if i == 0)
                for i, row, name in crows:
                    if i == 0:
                        continue
                    rec, vec = record(ck, study, parent, i, shared[parent][i], row, baseline, cw, account,
                                      str((base/name).relative_to(root)), "previously_frozen_512_life_confirmation")
                    confirmed.append(rec)
                    vectors.update({f"confirm__{study}__{ck}__{parent}__row{i:02d}__{k}": v for k, v in vec.items()})

    # Do not combine different world-seed arrays as if lives were paired across worlds.
    seed_sets = {k: set(v["screen_seeds"]) for k, v in world_info.items()}
    assert all(not a & b for a, b in itertools.combinations(seed_sets.values(), 2))
    lookup = {(x["world"], x["parent"], x["panel_row"]): x for x in screen}
    broad = []
    for parent in PARENTS:
        for i in range(65):
            rows = [lookup[k, parent, i] for k in WORLDS]
            item = {"parent": parent, "panel_row": i, "genome_sha256": shared[parent][i],
                    "positive_capture_worlds": sum(r["captures_delta_mean"] > 0 for r in rows),
                    "nonnegative_capture_worlds": sum(r["captures_delta_mean"] >= 0 for r in rows),
                    "positive_F_worlds": sum(r["F_delta_mean"] > 0 for r in rows),
                    "capture_positive3se_worlds_descriptive": sum(r["captures_positive_3se_descriptive"] for r in rows),
                    "capture_negative3se_worlds_descriptive": sum(r["captures_negative_3se_descriptive"] for r in rows),
                    "worst_capture_delta_mean": min(r["captures_delta_mean"] for r in rows),
                    "worst_capture_parent_fraction": min(r["captures_parent_fraction"] for r in rows),
                    "worst_F_delta_mean": min(r["F_delta_mean"] for r in rows),
                    "confirmed_comparisons_available": sum(r["parent"] == parent and r["panel_row"] == i for r in confirmed)}
            for key, r in zip(WORLDS, rows):
                for metric in ("captures", "F", "capture_income", "ordinary_cost_saving", "n_end", "spikes"):
                    for field in ("delta_mean", "delta_se"):
                        item[f"{key}__{metric}__{field}"] = r[metric + "_" + field]
            broad.append(item)
    highlighted = {}
    for parent in PARENTS:
        rows = [r for r in broad if r["parent"] == parent and r["panel_row"] != 0]
        highlighted[parent] = {
            "positive_captures_all_four": [r["panel_row"] for r in rows if r["positive_capture_worlds"] == 4],
            "nonnegative_captures_all_four": [r["panel_row"] for r in rows if r["nonnegative_capture_worlds"] == 4],
            "positive_F_all_four": [r["panel_row"] for r in rows if r["positive_F_worlds"] == 4],
            "top_five_by_worst_capture_mean_exploratory": [r["panel_row"] for r in sorted(rows, key=lambda r: (-r["worst_capture_delta_mean"], r["panel_row"]))[:5]],
        }
    correlation = []
    for parent in PARENTS:
        for a, b in itertools.combinations(WORLDS, 2):
            for metric in ("captures", "F", "ordinary_cost_saving"):
                x = [lookup[a, parent, i][metric + "_delta_mean"] for i in range(1, 65)]
                y = [lookup[b, parent, i][metric + "_delta_mean"] for i in range(1, 65)]
                correlation.append({"parent": parent, "world_a": a, "world_b": b, "metric": metric,
                                    "pearson_over64_mutant_means_descriptive": float(np.corrcoef(x, y)[0, 1])})
    forbidden = [n for n in sys.modules if n.startswith(("src.", "torch"))]
    assert not forbidden, forbidden
    out.mkdir(parents=True)
    csv_write(out / "screen_table.csv", [{k: v for k, v in r.items() if k != "health"} for r in screen])
    csv_write(out / "all_genomes_cross_world.csv", broad)
    csv_write(out / "existing_confirmation_table.csv", confirmed)
    csv_write(out / "cross_world_correlations.csv", correlation)
    np.savez_compressed(out / "paired_vectors.npz", **vectors)
    summary = {"status": "complete_offline_exploratory_analysis", "counts": counts,
               "shared_panel_rows": 130, "worlds": world_info, "highlights": highlighted,
               "confirmed_parent_comparisons": len(confirmed), "screen_status_nonzero": sum(r["status_nonzero"] for r in screen),
               "confirmation_status_nonzero": sum(r["status_nonzero"] for r in confirmed),
               "statistics": "Mean paired difference and sampleSD/sqrt(n); strict3SE descriptive signs only. No cross-world pooled SE or adjusted hypothesis test.",
               "limitations": LIMITS, "new_simulation_calls": 0, "engine_imports": [], "genetic_draws": 0,
               "input_files": len(audit.pins), "paired_arrays": len(vectors), "script_sha256": sha(__file__),
               "source_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()}
    dump(out / "summary.json", summary)
    audit.pin(Path(__file__))
    dump(out / "input_hashes.json", audit.pins)
    dump(out / "output_hashes.json", {p.name: {"sha256": sha(p), "bytes": p.stat().st_size} for p in sorted(out.iterdir()) if p.is_file()})
    print(json.dumps({"status": summary["status"], "counts": counts, "highlights": highlighted,
                      "confirmed_parent_comparisons": len(confirmed), "screen_status_nonzero": summary["screen_status_nonzero"],
                      "confirmation_status_nonzero": summary["confirmation_status_nonzero"]}, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=HERE.parents[2])
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    run(args.repo.resolve(), args.out.resolve())
