"""Independent fixed-panel decoy audit/export; no simulation, compilation or measurement-runner imports."""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import re
import shutil
from pathlib import Path

import numpy as np

HELPER = Path(__file__).with_name("offline_accounting.py")
HELPER_SHA = "4e6800a092455649357cbd411b1352afcd3e4f82f6119ce7b597f068edd8df6c"
if hashlib.sha256(HELPER.read_bytes()).hexdigest() != HELPER_SHA:
    raise ValueError("independent NumPy accounting helper changed")
loader = importlib.util.spec_from_file_location("independent_decoy_accounting", HELPER)
A = importlib.util.module_from_spec(loader)
loader.loader.exec_module(A)
ROOT = next((p for p in Path(__file__).resolve().parents if (p / "src/life/spec.py").exists()), None)
PARENTS = ("s5", "s7")
STAGES = ("screen", "rescore", "confirm")
BLOCKS = {"screen": 95, "rescore": 96, "confirm": 97}
LIVES = {"screen": 32, "rescore": 512, "confirm": 512}
LIMITATIONS = [
    "All 64 preexisting mutants per parent are included, without filtering on their earlier-world scores.",
    "The screen and rescore are selection-biased; fresh confirmation supplies the primary fixed-winner evidence.",
    "Both selected winners are retained even if worse than the parent. No extra candidates or life extensions occur.",
    "Two backgrounds and a fixed 64-mutant panel per background do not estimate general evolvability.",
    "Positive nearby gains do not establish a discrimination circuit, local algorithm or long-term accumulation.",
    "The world uses old conduction, while earlier base/POOL diagnostics used fast conduction; between-study "
    "comparisons are not controlled world-only contrasts.",
    "The controller that motivated this world never enters the organism. No admission or selection change follows.",
    "Guards and extinction retain production penalties; invalid capacity/accounting failures block inference.",
    "Three-SE and >=0.5-F flags, beneficial fractions and selected references are descriptive, not "
    "multiplicity-adjusted discovery claims.",
]
TERMINAL_FAILURES = {"incomplete", "cpu_budget_exhausted", "monitor_failed"}


def operation(base, name):
    path = base / "operations" / name
    return path if path.exists() else base / name


def source(base, relative):
    path = base / "sources" / relative
    if path.exists():
        return path
    if ROOT is None:
        raise ValueError("missing archived source " + relative)
    return ROOT / relative


def raw_sha(value):
    return hashlib.sha256(np.asarray(value).tobytes()).hexdigest()


def shortlist(fitness):
    fitness = np.asarray(fitness)
    if fitness.shape != (65, 32) or not np.isfinite(fitness).all():
        raise ValueError("screen requires all 65 fixed rows and 32 lives")
    return sorted(range(1, 65), key=lambda index: (-float(fitness[index].mean()), index))[:4]


def winner(fitness, indices):
    fitness = np.asarray(fitness)
    if len(indices) != 5 or indices[0] != 0 or len(set(indices)) != 5:
        raise ValueError("rescore requires parent plus four distinct mutants")
    if fitness.shape != (5, 512) or not np.isfinite(fitness).all():
        raise ValueError("rescore requires five finite rows of 512 lives")
    return min(indices[1:], key=lambda index: (-float(fitness[indices.index(index)].mean()), index))


def primary(estimate):
    positive = estimate["mean"] > 3 * estimate["se"]
    direction = "positive" if positive else ("negative" if estimate["mean"] < -3 * estimate["se"] else "unresolved")
    return {**estimate, "direction_above_3se": direction, "above_3se": positive,
            "at_least_0p5": estimate["mean"] >= .5}


def compare(data, index, world):
    counts = {key: A.stats(data[key][index] - data[key][0]) for key in
              ("F", "F_kernel", "n_end", "n_H_end", "live_time", "spikes", "packets", "misses", "clicks",
               "captures", "path", "zone_samples", "samples", "b2_clicks")}
    ordinary = A.pair_terms(data, index, world)
    window = world["T"] - world["t_open"]
    pieces = {"capture_income": world["R_cap"] * (data["captures"][index] - data["captures"][0]) / window,
              "poison_cost_saving": max(0, -world["b2_value"]) *
              (data["b2_clicks"][0] - data["b2_clicks"][index]) / window,
              "miss_cost_saving": world["c_miss"] * (data["misses"][0] - data["misses"][index]) / window}
    pieces["other_cost_saving"] = ordinary["cost_saving"] - pieces["poison_cost_saving"] - pieces["miss_cost_saving"]
    for name in ("guard_charge_saving", "extinction_charge_saving"):
        pieces[name] = ordinary[name]
    pieces["residual"] = data["F"][index] - data["F"][0] - sum(pieces.values())
    if not np.allclose(pieces["residual"], 0, rtol=0, atol=1e-9):
        raise ValueError("independent capture/poison/miss/penalty pieces do not reconcile")
    cost = {name: A.stats(price * data[column][0] / window - price * data[column][index] / window)
            for name, column, price in A.prices(world)}
    guards = {label: float(np.mean(data["status"][i].astype(np.int64) & 6 != 0))
              for label, i in (("parent", 0), ("winner", index))}
    return {**counts, "primary": primary(counts["F"]), "fitness_contributions": {
        key: A.stats(value) for key, value in ordinary.items()}, "cost_saving_components": cost,
        "decoy_fitness_contributions": {key: A.stats(value) for key, value in pieces.items()},
        "guard_fraction": guards}, pieces


def check_comparison(actual, saved, label):
    for key in actual:
        if key in ("fitness_contributions", "cost_saving_components", "decoy_fitness_contributions"):
            for name, value in actual[key].items():
                A.check_stats(value, saved[key][name], label + " " + key + " " + name)
        elif key in ("primary", "guard_fraction"):
            A.equal(actual[key], saved[key], label + " " + key)
        else:
            A.check_stats(actual[key], saved[key], label + " " + key)


def audit_inputs(base):
    p = A.read(base / "protocol.json")
    A.equal(p["parents"], list(PARENTS), "parent backgrounds")
    A.equal(p["mutants_per_parent"], 64, "fixed panel size")
    A.equal(p["new_mutants_generated"], 0, "new mutant count")
    A.equal(p["scientific_genome_lives"], 11328, "research life count")
    A.equal(p["seed_blocks"], BLOCKS, "seed blocks")
    A.equal(p["lives_per_row"], LIVES, "life counts per stage")
    A.equal(p["world"], A.read(base / "inputs/F_protocol.json")["world"], "F's world and all prices")
    for stage in STAGES:
        start = 51_000_000 + 10_000 * BLOCKS[stage]
        A.equal(p["seeds"][stage], list(range(start, start + LIVES[stage])), "ordered seeds " + stage)
    ready = A.read(operation(base, "ready.json"))
    for name, digest in ready["files"].items():
        path = base / "protocol.json" if name == "protocol.json" else operation(base, name)
        A.equal(A.sha(path), digest, "released file " + name)
    for relative, digest in p["source_identity"].items():
        A.equal(A.sha(source(base, relative)), digest, "numerical source " + relative)
    for name, digest in p["helpers"].items():
        A.equal(A.sha(source(base, "scripts/" + name)), digest, "measurement helper " + name)
    for relative, digest in p["input_sha256"].items():
        A.equal(A.sha(base / relative), digest, "fixed input " + relative)
    prior = A.read(base / "inputs/prior_provenance.json")
    A.equal(prior["numerical_identity"], p["expected_numerical_identity"], "original numerical identity")
    for local, original in p["original_archive_paths"].items():
        A.equal(A.sha(base / local), prior["artifacts"][original]["sha256"], "original archive input " + local)
    for dependency, files in p["dependencies"].items():
        for name, digest in files.items():
            path = base / "dependencies" / dependency / name
            if not path.exists():
                path = ROOT / dependency / name
            A.equal(A.sha(path), digest, "dependency source " + name)
    manifest = A.read(base / "measurement/manifest.json")
    A.equal(manifest["protocol_sha256"], A.sha(base / "protocol.json"), "measurement protocol")
    A.equal(manifest["runner_sha256"], A.sha(operation(base, "measure.py")), "measurement source")
    for key, value in (("world", p["world"]), ("seeds", p["seeds"]), ("seed_blocks", BLOCKS),
                       ("numerical_identity", p["expected_numerical_identity"]),
                       ("helpers", p["helpers"]), ("input_sha256", p["input_sha256"])):
        A.equal(manifest[key], value, "measurement manifest " + key)
    panels = {}
    for parent in PARENTS:
        prefix = base / "inputs" / parent
        genomes = np.load(prefix / "genomes.npy", allow_pickle=False)
        params = A.read(prefix / "parent.json")["params"]
        ancestor = np.concatenate([np.asarray(params[key], dtype=np.float32).reshape(-1) for key in A.FIELDS])
        if genomes.dtype != np.float32 or genomes.shape != (65, len(ancestor)) or not np.isfinite(genomes).all():
            raise ValueError("fixed panel dimensions or type differ")
        if not A.identical(genomes[0], ancestor):
            raise ValueError("fixed parent differs from panel row zero")
        original = A.read(prefix / "original_screen_manifest.json")
        A.equal(raw_sha(genomes), original["genomes_sha256"], "original mutant-table bytes")
        A.equal(raw_sha(genomes), manifest["genomes_sha256"][parent], "measured mutant-table bytes")
        A.equal(original["mutants"], 64, "original mutant count")
        A.equal(original["numerical_identity"], p["expected_numerical_identity"], "panel numerical identity")
        A.equal(re.findall(r"^\s*extinct_charge:\s*(\S+)\s*$", (prefix / "config.yaml").read_text(), re.MULTILINE),
                ["true"], "production extinction charge")
        panels[parent] = genomes
    return p, panels


def load_stage(base, parent, stage, indices, protocol):
    folder = base / "measurement" / parent
    index = A.read(folder / "row_index.json")
    aggregate = A.arrays(folder / stage / "scores.npz")
    A.equal(aggregate["seeds"].tolist(), protocol["seeds"][stage], "aggregate seeds")
    A.equal(aggregate["genome_indices"].tolist(), indices, "aggregate selected-row order")
    if any(aggregate[key].shape != (len(indices), LIVES[stage]) for key in A.COLS):
        raise ValueError("aggregate dimensions differ")
    health, cpu = {}, 0.0
    for position, candidate in enumerate(indices):
        name = f"{stage}/row_{candidate:04d}.npz"
        A.equal(A.sha(folder / name), index[name]["sha256"], "raw row receipt " + name)
        row = A.arrays(folder / name)
        A.equal(row["seeds"].tolist(), protocol["seeds"][stage], "raw row seeds")
        A.equal(int(row["genome_index"]), candidate, "raw candidate index")
        health[str(candidate)] = A.validate_row(row, protocol["world"], n=LIVES[stage])
        for column in A.COLS:
            if not A.identical(row[column], aggregate[column][position]):
                raise ValueError("raw and aggregate bytes differ: " + name + " " + column)
        A.equal(float(row["cpu_seconds"]), index[name]["cpu_seconds"], "raw CPU receipt")
        cpu += float(row["cpu_seconds"])
    return aggregate, health, cpu


def analyze(base):
    base = Path(base).resolve()
    budget_path = operation(base, "budget.json")
    if not budget_path.exists() or A.read(budget_path)["status"] != "complete":
        return {"status": "incomplete", "budget_status": A.read(budget_path)["status"]
                if budget_path.exists() else "not_started"}, {}
    budget = A.read(budget_path)
    if (budget["exit_code"] != 0 or not np.isfinite(budget["cpu_seconds"])
            or not 0 < budget["cpu_seconds"] < 3600 or budget["running"] or budget["queued"]):
        raise ValueError("I did not complete inside its fixed CPU budget")
    A.equal(budget["cap_cpu_seconds"], 3600, "monitor cap")
    p, genomes = audit_inputs(base)
    report = A.read(base / "measurement/report.json")
    A.equal(report["status"], "complete", "scientific completion")
    A.equal(report["scientific_genome_lives"], 11328, "scientific life count")
    shortlists, selections = A.read(base / "measurement/shortlist.json"), A.read(base / "measurement/selection.json")
    A.equal(set(shortlists), set(PARENTS), "both frozen shortlists")
    A.equal(set(selections), set(PARENTS), "both frozen confirmation winners")
    summary = {"status": "complete", "scientific_genome_lives": 11328, "seed_blocks": BLOCKS,
               "screen": {}, "rescore": {}, "confirmation": {}, "selection": selections,
               "health": {}, "raw_row_cpu_seconds": 0.0, "startup_validation": {"golden_lives": 2, "T": 200,
               "seed": 11, "scope": "One full/fast E1 pair, separate from research lives and inside CPU cap."}}
    vectors = {stage + "_seeds": np.asarray(p["seeds"][stage], dtype=np.uint64) for stage in STAGES}
    for parent in PARENTS:
        data, health, cpu = load_stage(base, parent, "screen", list(range(65)), p)
        summary["health"][parent] = {"screen": health}
        summary["raw_row_cpu_seconds"] += cpu
        selected = shortlist(data["F"])
        A.equal(shortlists[parent], selected, "fixed top four " + parent)
        screen_values = data["F"][1:] - data["F"][0]
        estimates = [A.stats(value) for value in screen_values]
        saved = report["screen"][parent]
        for index, value in enumerate(estimates):
            A.check_stats(value, saved["paired_estimates"][index], "screen paired mutant estimate")
        fractions = {"positive_mean_fraction": float(np.mean([row["mean"] > 0 for row in estimates])),
                     "positive_above_3se_fraction": float(np.mean([row["mean"] > 3 * row["se"] for row in estimates]))}
        for key, value in fractions.items():
            A.equal(value, saved[key], "screen fraction " + key)
        summary["screen"][parent] = {"shortlist": selected, "paired_estimates": estimates, **fractions}
        vectors[parent + "__screen_differences"] = screen_values
        rescored, health, cpu = load_stage(base, parent, "rescore", [0, *selected], p)
        summary["health"][parent]["rescore"] = health
        summary["raw_row_cpu_seconds"] += cpu
        chosen = winner(rescored["F"], [0, *selected])
        expected = {"genome_row": chosen, "raw_sha256": raw_sha(genomes[parent][chosen]),
                    "source_genome_row": chosen, "mutant_index": chosen - 1}
        A.equal(selections[parent], expected, "frozen winner " + parent)
        A.equal(report["selection"][parent], expected, "reported winner " + parent)
        summary["rescore"][parent] = {}
        for position, candidate in enumerate(selected, 1):
            value, _ = compare(rescored, position, p["world"])
            check_comparison(value, report["rescore"][parent][str(candidate)], "rescored candidate")
            summary["rescore"][parent][str(candidate)] = value
        confirmed, health, cpu = load_stage(base, parent, "confirm", [0, chosen], p)
        summary["health"][parent]["confirm"] = health
        summary["raw_row_cpu_seconds"] += cpu
        value, pieces = compare(confirmed, 1, p["world"])
        check_comparison(value, report["confirmation"][parent], "fresh confirmation " + parent)
        summary["confirmation"][parent] = value
        summary["confirmation"][parent]["absolute_F"] = {
            "parent": A.stats(confirmed["F"][0]), "winner": A.stats(confirmed["F"][1])}
        vectors[parent + "__confirmation_delta"] = confirmed["F"][1] - confirmed["F"][0]
        vectors.update({parent + "__confirmation_" + key: values for key, values in pieces.items()})
        expected_paths = {f"screen/row_{index:04d}.npz" for index in range(65)}
        expected_paths.update(f"rescore/row_{index:04d}.npz" for index in [0, *selected])
        expected_paths.update(f"confirm/row_{index:04d}.npz" for index in [0, chosen])
        A.equal(set(A.read(base / "measurement" / parent / "row_index.json")), expected_paths,
                "all and only prescribed raw rows")
    if not np.isclose(summary["raw_row_cpu_seconds"], report["row_cpu_seconds"], rtol=0, atol=1e-7):
        raise ValueError("raw CPU sum differs from scientific report")
    summary.update(budget={"monitored_cpu_seconds": budget["cpu_seconds"], "cap_cpu_seconds": 3600, "workers": 2},
                   audit={"initial_screen_rows": 130, "total_raw_checkpoints": 144, "raw_ledger_columns": 57,
                          "saved_scored_columns": 60, "complete_original_panels": True,
                          "exact_raw_aggregate_bytes": True, "independent_selection": True,
                          "independent_accounting_helper_sha256": HELPER_SHA, "analysis_simulated_lives": 0},
                   limitations=LIMITATIONS)
    return summary, vectors


def audit_stopped(base):
    """Audit every saved row of a terminal incomplete run without selecting or inferring an effect."""
    base = Path(base).resolve()
    budget = A.read(operation(base, "budget.json"))
    if budget["status"] not in TERMINAL_FAILURES or budget.get("running") or budget.get("queued"):
        raise ValueError("incomplete export requires a terminal stopped monitor with no remaining work")
    if not np.isfinite(budget["cpu_seconds"]) or budget["cpu_seconds"] < 0 or budget["cap_cpu_seconds"] != 3600:
        raise ValueError("invalid stopped-study budget")
    protocol, _ = audit_inputs(base)
    counts, health, unindexed, row_cpu, lives = {}, {}, {}, 0.0, 0
    for parent in PARENTS:
        folder = base / "measurement" / parent
        path = folder / "row_index.json"
        index = A.read(path) if path.exists() else {}
        counts[parent], health[parent] = {stage: 0 for stage in STAGES}, {}
        files = {str(path.relative_to(folder)) for stage in STAGES
                 for path in (folder / stage).glob("row_[0-9][0-9][0-9][0-9].npz")}
        unindexed[parent] = sorted(files - set(index))
        for relative in sorted(files | set(index)):
            receipt = index.get(relative)
            match = re.fullmatch(r"(screen|rescore|confirm)/row_(\d{4})\.npz", relative)
            if match is None or not 0 <= int(match[2]) < 65:
                raise ValueError("unregistered stopped-study checkpoint path")
            stage, candidate = match[1], int(match[2])
            if receipt is not None:
                A.equal(A.sha(folder / relative), receipt["sha256"], "stopped raw row receipt")
            row = A.arrays(folder / relative)
            A.equal(row["seeds"].tolist(), protocol["seeds"][stage], "stopped raw seeds")
            A.equal(int(row["genome_index"]), candidate, "stopped raw genome index")
            health[parent][relative] = A.validate_row(row, protocol["world"], n=LIVES[stage])
            if receipt is not None:
                A.equal(float(row["cpu_seconds"]), receipt["cpu_seconds"], "stopped raw CPU receipt")
            row_cpu += float(row["cpu_seconds"])
            counts[parent][stage] += 1
            lives += LIVES[stage]
    return {"status": "incomplete", "budget_status": budget["status"], "budget": budget,
            "saved_rows": counts, "saved_research_lives": lives, "planned_research_lives": 11328,
            "raw_row_cpu_seconds": row_cpu, "health": health, "unindexed_saved_rows": unindexed,
            "primary_confirmation_inference_allowed": False,
            "analysis_simulated_lives": 0, "limitations": LIMITATIONS + [
                "The registered study did not complete normally. Saved outcomes are partial records, "
                "not a completed confirmation result. No candidate, seed or resource budget was substituted."]}


def stopped_markdown(summary):
    return "\n".join([
        "# Incomplete fixed-panel decoy study", "",
        "The fixed study stopped before normal completion. This archive preserves its complete partial record;",
        "no completed confirmation inference is made and no budget extension or seed replacement was performed.", "",
        f"Monitor status: `{summary['budget_status']}`. Saved research lives: "
        f"{summary['saved_research_lives']:,} of 11,328 planned.",
        f"Consumed CPU: {summary['budget']['cpu_seconds']:.6f} seconds; registered cap: 3,600.", "",
        "Every completed raw ledger was independently checked against its saved production-scored columns,",
        "capture income, ordinary costs, guard charge and extinction charge. Partial screen/rescore/confirmation",
        "records retain every saved sign and remain in `measurement/`; they are not promoted to a primary result.", "",
        "A resource stop between atomic row saving and receipt saving can leave an unindexed completed row;",
        "any such row is independently validated and explicitly listed in `summary.json`. Temporary partial files",
        "remain archived without entering the saved-life count.", "",
        "Recheck the partial archive without simulation: `python analyze.py --check`.", "",
    ])


def export_stopped(base, destination, summary):
    destination.mkdir(parents=True, exist_ok=True)
    historical = destination / "prelaunch"
    if not historical.exists():
        previous = A.read(destination / "preparation_provenance.json")
        for name in (*previous["artifacts"], "preparation_provenance.json"):
            target = historical / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(destination / name, target)
    for name in ("measurement", "inputs"):
        shutil.copytree(base / name, destination / name, dirs_exist_ok=True)
    shutil.copyfile(base / "protocol.json", destination / "protocol.json")
    operations = destination / "operations"
    operations.mkdir(exist_ok=True)
    ready, protocol = A.read(base / "ready.json"), A.read(base / "protocol.json")
    for name in (*ready["files"], "ready.json", "budget.json", "run.log"):
        shutil.copyfile(base / name, operations / name)
    for relative in set(protocol["source_identity"]) | {"scripts/" + name for name in protocol["helpers"]}:
        target = destination / "sources" / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source(base, relative), target)
    for dependency, files in protocol["dependencies"].items():
        for name in files:
            target = destination / "dependencies" / dependency / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / dependency / name, target)
    for name in ("analyze.py", "offline_accounting.py", "test_analysis.py", "test_monitor_review.py"):
        shutil.copyfile(Path(__file__).with_name(name), destination / name)
    A.equal(audit_stopped(destination), summary, "public stopped-study audit")
    A.save(destination / "summary.json", summary)
    (destination / "README.md").write_text(stopped_markdown(summary))
    files = {str(path.relative_to(destination)): {"sha256": A.sha(path), "bytes": path.stat().st_size}
             for path in sorted(destination.rglob("*")) if path.is_file() and path != destination / "provenance.json"
             and "__pycache__" not in path.parts and ".pytest_cache" not in path.parts}
    A.save(destination / "provenance.json", {"status": "incomplete", "artifacts": files,
                                           "analysis_simulated_lives": 0})


def markdown(summary):
    lines = ["# Nearby organism mutations in the existing decoy world", "",
             "The unchanged original s5/s7 panels each contain their parent and all 64 ordinary mutants. The world",
             "matches F exactly: existing ABI3 harmful decoy, T1024, old conduction and unchanged prices.", "",
             "| Parent | Frozen mutant row | Fresh paired ΔF ± SE | Descriptive 3-SE direction | ≥0.5 F |",
             "|---|---:|---:|---|---|"]
    for parent in PARENTS:
        value = summary["confirmation"][parent]["primary"]
        chosen = summary["selection"][parent]["genome_row"]
        lines.append(f"| {parent} | {chosen} | {value['mean']:+.6f} ± {value['se']:.6f} | "
                     f"{value['direction_above_3se']} | {'yes' if value['at_least_0p5'] else 'no'} |")
    lines += ["", "Screening used 32 shared block95 lives. Exactly four mutant rows per parent were rescored on",
              "512 fresh block96 lives; both winning genotypes were frozen before either block97 confirmation.",
              "All signs are retained. Each primary estimate uses 512 paired differences, preserving covariance.", "",
              "| Parent | Initial positive-mean fraction | Initial >3-SE fraction | Top four original rows |",
              "|---|---:|---:|---|"]
    for parent in PARENTS:
        row = summary["screen"][parent]
        lines.append(f"| {parent} | {row['positive_mean_fraction']:.4f} | {row['positive_above_3se_fraction']:.4f} | "
                     f"{row['shortlist']} |")
    lines += ["", "Fresh absolute fitness and changes in captures/body size:", "",
              "| Parent | Parent F | Winner F | Δ captures ± SE | Δ terminal cells ± SE |",
              "|---|---:|---:|---:|---:|"]
    for parent in PARENTS:
        row = summary["confirmation"][parent]
        capture, cells = row["captures"], row["n_end"]
        lines.append(f"| {parent} | {row['absolute_F']['parent']['mean']:+.6f} | "
                     f"{row['absolute_F']['winner']['mean']:+.6f} | {capture['mean']:+.6f} ± {capture['se']:.6f} | "
                     f"{cells['mean']:+.6f} ± {cells['se']:.6f} |")
    lines += ["", "Mean contributions to the same paired fitness gain:", "",
              "| Parent | Capture income | Poison-cost saving | Miss-cost saving | Other-cost saving |",
              "|---|---:|---:|---:|---:|"]
    for parent in PARENTS:
        pieces = summary["confirmation"][parent]["decoy_fitness_contributions"]
        entries = [f"{pieces[key]['mean']:+.6f}" for key in
                   ("capture_income", "poison_cost_saving", "miss_cost_saving", "other_cost_saving")]
        lines.append("| " + parent + " | " + " | ".join(entries) + " |")
    lines += ["", "The full accounting, including guard/extinction terms and per-component paired SEs, is in",
              "`summary.json`. Body size and ordinary costs matter when interpreting a positive gain; these",
              "nearby improvements do not by themselves identify a discrimination mechanism."]
    cpu = summary["budget"]["monitored_cpu_seconds"]
    lines += ["", f"All 11,328 research genome-lives completed in {cpu:.6f} monitored CPU-seconds (cap3,600).",
              "Two existing T200 startup golden lives are separate validation within that CPU cap.", "",
              "Every one of 144 raw checkpoints is preserved, including all 130 initial rows, full ledgers and",
              "production-scored columns. `summary.json` records all rescores, confirmation accounting and health.",
              "`inputs/` preserves original genomes/mutation logs, `operations/` preserves release/resource records,",
              "and `prelaunch/` preserves the full original preparation archive without changing frozen bytes.", "",
              "Recompute without simulation or compilation (Python + NumPy; Matplotlib only for `--plot`):", "",
              "```bash", "python analyze.py --study . --check", "```", "", "Interpretation limits:", ""]
    lines.extend("- " + item for item in LIMITATIONS)
    return "\n".join(lines) + "\n"


def plot(summary, vectors, destination):
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, axes = plt.subplots(1, 2, figsize=(11, 4.8), layout="constrained")
    colors = ("#205493", "#b45309")
    for index, (parent, color) in enumerate(zip(PARENTS, colors)):
        means = vectors[parent + "__screen_differences"].mean(axis=1)
        axes[0].plot(np.arange(1, 65), means, "o", ms=3, alpha=.7, color=color, label=parent)
        value = summary["confirmation"][parent]["primary"]
        axes[1].errorbar(value["mean"], index, xerr=3 * value["se"], fmt="o", capsize=5, color=color)
    axes[0].axhline(0, color="#6b7280", linewidth=1)
    axes[0].set(title="Every initial mutant is retained", xlabel="Original mutant row",
                ylabel="Mean paired ΔF (32 lives)")
    axes[0].legend()
    axes[1].axvline(0, color="#6b7280", linewidth=1)
    axes[1].axvline(.5, color="#9ca3af", linestyle="--", linewidth=1)
    axes[1].set_yticks([0, 1], ["s5 winner − parent", "s7 winner − parent"])
    axes[1].invert_yaxis()
    axes[1].set(title="Fresh fixed-winner confirmation", xlabel="Paired ΔF, mean ± 3 SE (512 lives)")
    fig.suptitle("Existing decoy world; complete preexisting mutant panels", fontsize=14)
    for suffix in ("png", "svg"):
        fig.savefig(destination / ("decoy_gradient." + suffix), dpi=170)
    plt.close(fig)


def export(base, destination, summary, vectors):
    destination.mkdir(parents=True, exist_ok=True)
    historical = destination / "prelaunch"
    if not historical.exists():
        previous = A.read(destination / "preparation_provenance.json")
        for name in (*previous["artifacts"], "preparation_provenance.json"):
            target = historical / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(destination / name, target)
    for name in ("measurement", "inputs"):
        shutil.copytree(base / name, destination / name, dirs_exist_ok=True)
    shutil.copyfile(base / "protocol.json", destination / "protocol.json")
    operations = destination / "operations"
    operations.mkdir(exist_ok=True)
    ready = A.read(base / "ready.json")
    for name in (*ready["files"], "ready.json", "budget.json", "run.log"):
        shutil.copyfile(base / name, operations / name)
    p = A.read(base / "protocol.json")
    for relative in set(p["source_identity"]) | {"scripts/" + name for name in p["helpers"]}:
        target = destination / "sources" / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source(base, relative), target)
    for dependency, files in p["dependencies"].items():
        for name in files:
            target = destination / "dependencies" / dependency / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / dependency / name, target)
    for name in ("analyze.py", "offline_accounting.py", "test_analysis.py", "test_monitor_review.py"):
        shutil.copyfile(Path(__file__).with_name(name), destination / name)
    A.save(destination / "summary.json", summary)
    np.savez_compressed(destination / "independent_contrasts.npz", **vectors)
    (destination / "README.md").write_text(markdown(summary))
    plot(summary, vectors, destination)
    checked, reloaded = analyze(destination)
    A.equal(checked, summary, "public independent summary")
    for key, value in vectors.items():
        if not A.identical(value, reloaded[key]):
            raise ValueError("exported paired array bytes differ")
    for parent in PARENTS:
        for name in A.read(base / "measurement" / parent / "row_index.json"):
            relative = Path("measurement") / parent / name
            A.equal(A.sha(base / relative), A.sha(destination / relative), "exported raw checkpoint bytes")
    files = {str(path.relative_to(destination)): {"sha256": A.sha(path), "bytes": path.stat().st_size}
             for path in sorted(destination.rglob("*")) if path.is_file() and path != destination / "provenance.json"
             and "__pycache__" not in path.parts and ".pytest_cache" not in path.parts}
    A.save(destination / "provenance.json", {"status": "complete", "scientific_genome_lives": 11328,
                                           "artifacts": files, "analysis_simulated_lives": 0})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--study", type=Path, default=Path(__file__).resolve().parent)
    parser.add_argument("--export", type=Path)
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--plot", action="store_true")
    args = parser.parse_args()
    summary, vectors = analyze(args.study)
    if summary["status"] != "complete":
        if summary["budget_status"] in TERMINAL_FAILURES and (args.export or args.check):
            summary = audit_stopped(args.study)
            if args.export:
                export_stopped(args.study.resolve(), args.export.resolve(), summary)
            if args.check:
                for name, item in A.read(args.study / "provenance.json")["artifacts"].items():
                    A.equal(A.sha(args.study / name), item["sha256"], "incomplete public artifact " + name)
                    A.equal((args.study / name).stat().st_size, item["bytes"], "incomplete public size " + name)
                A.equal(A.read(args.study / "summary.json"), summary, "incomplete public summary")
                A.equal((args.study / "README.md").read_text(), stopped_markdown(summary), "incomplete public README")
        print(json.dumps(summary))
        return
    if args.check:
        for name, item in A.read(args.study / "provenance.json")["artifacts"].items():
            A.equal(A.sha(args.study / name), item["sha256"], "public artifact " + name)
            A.equal((args.study / name).stat().st_size, item["bytes"], "public artifact size " + name)
        A.equal(A.read(args.study / "summary.json"), summary, "public summary")
        A.equal((args.study / "README.md").read_text(), markdown(summary), "public readable summary")
        saved = A.arrays(args.study / "independent_contrasts.npz")
        A.equal(set(saved), set(vectors), "public contrast names")
        if any(not A.identical(saved[key], value) for key, value in vectors.items()):
            raise ValueError("public paired arrays differ")
    if args.export:
        export(args.study.resolve(), args.export.resolve(), summary, vectors)
    if args.plot:
        plot(summary, vectors, args.study)
    printed = {"status": summary["status"], "confirmation": {
        parent: summary["confirmation"][parent]["primary"] for parent in PARENTS}, "audit": summary["audit"]}
    print(json.dumps(printed, indent=2))


if __name__ == "__main__":
    main()
