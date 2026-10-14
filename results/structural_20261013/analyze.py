"""Independent completed-study ledger analysis for G; no simulation or endpoint selection."""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import shutil
import sys
from dataclasses import asdict
from pathlib import Path

os.environ.setdefault("ATEN_CPU_CAPABILITY", "avx2")
ROOT = next(p for p in Path(__file__).resolve().parents if (p / "src/life/spec.py").exists())
sys.path.insert(0, str(ROOT))
sys.dont_write_bytecode = True
# Preload the archived package when available before the shared accounting helper imports src.
archived_sources = Path(__file__).resolve().parent / "sources"
if (archived_sources / "src/life/spec.py").exists():
    sys.path.insert(0, str(archived_sources))
    importlib.import_module("src.life.spec")

import numpy as np  # noqa: E402

BASE = Path(__file__).resolve().parent / "sources/accounting_analysis.py"
if not BASE.exists():
    BASE = ROOT / "results/followthrough_20261013/analyze.py"
loader = importlib.util.spec_from_file_location("structural_accounting_audit", BASE)
accounting = importlib.util.module_from_spec(loader)
loader.loader.exec_module(accounting)
STUDY = ROOT / "outputs/autonomous_structural_20261013"
DURATIONS = (768, 1024, 1536)
LABELS = ["pilot_s5", "founder_row38", "d_s51089_final_rank0", "d_s51090_final_rank0",
          "g_s51089_final_rank0", "g_s51090_final_rank0"]
PAIRS = {"primary": [(4, 2), (5, 3)], "secondary": [(4, 1), (5, 1), (4, 0), (5, 0)]}
SEEDS = list(range(51_930_000, 51_930_256))


def equal(actual, expected, label):
    if actual != expected:
        raise ValueError(label + " differs from frozen study")


def raw_sha(array):
    return hashlib.sha256(np.asarray(array).tobytes()).hexdigest()


def operation(study, name):
    local = study / name
    return local if local.exists() else study / "operations" / name


def verify_archive(study):
    if (study / "provenance.json").exists():
        for relative, item in accounting.read_json(study / "provenance.json")["artifacts"].items():
            equal(accounting.digest(study / relative), item["sha256"], "archive artifact " + relative)


def duration_contrast(fitness, candidate, reference):
    if set(fitness) != set(DURATIONS):
        raise ValueError("three fixed duration matrices are required")
    arrays = np.stack([np.asarray(fitness[t][candidate]) - np.asarray(fitness[t][reference]) for t in DURATIONS])
    if arrays.shape != (3, 256) or not np.isfinite(arrays).all():
        raise ValueError("duration contrast needs 256 paired finite seed clusters")
    return arrays.mean(axis=0)


def neutrality_audit(study, protocol):
    from src.genome import Layout

    folder = study / "neutrality"
    report = accounting.read_json(folder / "report.json")
    equal(report["status"], "complete", "neutrality completion")
    equal(report["genome_lives"], 18, "neutrality life count")
    if report["cpu_seconds"] > 30:
        raise ValueError("neutrality exceeded its separate CPU cap")
    manifest = accounting.read_json(folder / "manifest.json")
    equal(manifest["protocol_sha256"], accounting.digest(study / "protocol.json"), "neutrality protocol")
    equal(manifest["seeds"], [51_090_000, 51_090_001], "neutrality seeds")
    equal(manifest["source_slots"], list(range(8)), "neutrality sources")
    equal(manifest["destination_slot"], 8, "neutrality destination")
    world = accounting.spec.world("catch_speck_l4", T=1024, d0=.5, d_min=.25, sigma=.4, lam_s=4)
    equal(manifest["world"], asdict(world), "neutrality world")
    equal(manifest["raster_cap"], 100000, "spike log capacity")
    equal(manifest["fate_cap"], 8192, "fate log capacity")
    layout, founder = Layout.load(study / "inputs" / Path(protocol["founder_file"]).name)
    genotypes = accounting.read_npz(folder / "genotypes.npz")["genomes"]
    expected = [founder] + [layout.duplicate(founder, i, 8, split=False) for i in range(8)]
    equal(genotypes.shape, (9, len(founder)), "neutrality genotype shape")
    for row, genotype in zip(genotypes, expected):
        equal(raw_sha(row), raw_sha(genotype.numpy()), "exact silent-duplicate genotype")
    forbidden = sum(accounting.spec.STATUS[key] for key in ("extinct", "guard_cells", "guard_events",
                    "raster_overflow", "fate_overflow", "ledger_mismatch", "capacity"))
    base = None
    for i, saved in enumerate(report["rows"]):
        equal(saved["row"], i, "neutrality row order")
        path = folder / f"row_{i:02d}.npz"
        equal(accounting.digest(path), saved["raw_sha256"], "neutrality raw evidence")
        row = accounting.read_npz(path)
        equal(raw_sha(genotypes[i]), saved["genome_sha256"], "neutrality genome order")
        equal(row["ledger"].shape, (2, 57), "neutrality ledger shape")
        equal(row["hashes"].shape, (2, 5), "neutrality hash shape")
        status = row["ledger"][:, accounting.spec.V3.L["status"]].astype(np.int64)
        if np.any(status & forbidden) or np.any(row["ledger"][:, accounting.spec.V3.L["t_end"]] != 1024):
            raise ValueError("neutrality has stopping/invalid/log-overflow flags or incomplete time")
        if np.any(row["raster_n"] > 100000) or np.any(row["fate_n"] > 8192):
            raise ValueError("neutrality log counts exceed capacity")
        for life in (0, 1):
            equal(row[f"spike_t_{life}"].shape, (int(row["raster_n"][life]),), "spike time count")
            equal(row[f"spike_uid_{life}"].shape, (int(row["raster_n"][life]),), "spike UID count")
            equal(row[f"fate_i_{life}"].shape, (int(row["fate_n"][life]), 7), "fate integer count")
            equal(row[f"fate_f_{life}"].shape, (int(row["fate_n"][life]), 18), "fate float count")
        if base is None:
            base = row
            continue
        for column in ("ledger", "hashes", "raster_n", "fate_n", "spike_t_0", "spike_uid_0",
                       "spike_t_1", "spike_uid_1", "fate_i_0", "fate_i_1"):
            equal(row[column].shape, base[column].shape, "neutrality array shape")
            equal(str(row[column].dtype), str(base[column].dtype), "neutrality array dtype")
            equal(raw_sha(row[column]), raw_sha(base[column]), "neutrality " + column)
        for life in (0, 1):
            values, original = row[f"fate_f_{life}"], base[f"fate_f_{life}"]
            keep = np.arange(values.shape[1]) != 10
            equal(raw_sha(values[:, keep]), raw_sha(original[:, keep]), "neutrality original fate states")
            equal(raw_sha(values[:, 10]), raw_sha(values[:, 2 + i - 1]), "neutrality copied gene state")
    equal(len(report["rows"]), 9, "neutrality row count")
    return {"status": "passed", "genome_lives": 18, "cpu_seconds": report["cpu_seconds"],
            "interpretation": "Silent starting duplication preserves tested task trajectories; "
                              "this is not functional use."}


def inputs(study):
    from src.genome import Layout

    verify_archive(study)
    protocol = accounting.read_json(study / "protocol.json")
    ready = accounting.read_json(operation(study, "ready.json"))
    for name, key in (("run_budgeted.py", "monitor_sha256"), ("measure.py", "measurement_sha256"),
                      ("protocol.json", "protocol_sha256")):
        equal(accounting.digest(operation(study, name)), ready[key], name)
    equal(protocol["runs"], [51089, 51090], "replicates")
    equal(protocol["generations"], 16, "generation count")
    equal(protocol["max_cpu_seconds"], 14400, "CPU cap")
    equal(protocol["confirmation"]["labels"], LABELS, "fixed labels")
    equal(protocol["confirmation"]["seeds"], SEEDS, "fresh shared seeds")
    for group, pairs in PAIRS.items():
        equal(protocol["confirmation"][group + "_pairs"], [list(pair) for pair in pairs], group + " pairs")
    equal(accounting.digest(operation(study, "prepare.py")), protocol["prepare_sha256"], "preparation")
    equal(accounting.digest(study / "seed_audit.json"), protocol["seed_audit_sha256"], "seed audit")
    for name, expected in ready["helpers"].items():
        candidate = study / "sources" / name
        equal(accounting.digest(candidate if candidate.exists() else ROOT / "scripts" / name), expected, name)
    for relative, expected in protocol["source_identity"].items():
        candidate = study / "sources" / relative
        equal(accounting.digest(candidate if candidate.exists() else ROOT / relative), expected, relative)
    original = {}
    for name in ("pilot", "founder"):
        path = study / "inputs" / Path(protocol[name + "_file"]).name
        equal(accounting.digest(path), protocol[name + "_sha256"], name + " genotype file")
        _, genome = Layout.load(path)
        original[name] = genome.numpy()
    for seed in protocol["runs"]:
        equal(accounting.digest(study / f"configs/s{seed}.yaml"),
              protocol["configs"][str(seed)]["sha256"], "G configuration")
    return protocol, ready, original


def analyze(study):
    protocol, ready, original = inputs(study)
    budget = accounting.read_json(operation(study, "budget.json"))
    equal(budget["status"], "complete", "study completion")
    if budget["cpu_seconds"] > 14400 or budget.get("running") or budget.get("queued"):
        raise ValueError("study is active or above its CPU cap")
    folder = study / "confirmation"
    manifest, report = accounting.read_json(folder / "manifest.json"), accounting.read_json(folder / "report.json")
    equal(report["status"], "complete", "confirmation completion")
    equal(report["genome_lives"], 4608, "confirmation lives")
    equal(manifest["labels"], LABELS, "manifest labels")
    equal(manifest["seeds"], SEEDS, "manifest seeds")
    equal(manifest["seed_block"], 93, "confirmation block")
    equal(manifest["protocol_sha256"], accounting.digest(study / "protocol.json"), "manifest protocol")
    equal(manifest["ready"], ready, "manifest readiness")
    equal(manifest["numerical_identity"], protocol["expected_numerical_identity"], "numerical identity")
    genomes = accounting.read_npz(folder / "genotypes.npz")
    equal(genomes["labels"].tolist(), LABELS, "raw genotype order")
    for i, label in enumerate(LABELS):
        equal(raw_sha(genomes["genomes"][i]), manifest["genotype_sha256"][label], label + " raw genotype")
    equal(raw_sha(genomes["genomes"][0]), raw_sha(original["pilot"]), "original pilot")
    equal(raw_sha(genomes["genomes"][1]), raw_sha(original["founder"]), "row38 founder")
    # Endpoint reconciliation is independent of the scientific measurement runner.
    audit_path = Path(__file__).with_name("audit_search.py")
    audit_loader = importlib.util.spec_from_file_location("structural_search_audit", audit_path)
    audit = importlib.util.module_from_spec(audit_loader)
    audit_loader.loader.exec_module(audit)
    search_audits = audit.audit(study, protocol, manifest, genomes["genomes"])
    row_index = accounting.read_json(folder / "row_index.json")
    equal(set(row_index), {f"{t}/row_{i:04d}.npz" for t in DURATIONS for i in range(6)}, "raw row index")
    worlds, data, per_duration, terms = {}, {}, {}, {}
    for duration in DURATIONS:
        world = accounting.spec.world("catch_speck_l4", T=duration, d0=.5, d_min=.25, sigma=.4, lam_s=4)
        equal(manifest["worlds"][str(duration)], asdict(world), "fixed world")
        values = accounting.read_npz(folder / str(duration) / "scores.npz")
        accounting.check_scores(values, SEEDS, list(range(6)), world)
        for i in range(6):
            relative = f"{duration}/row_{i:04d}.npz"
            path = folder / relative
            if path.exists():
                equal(accounting.digest(path), row_index[relative], "cached row hash")
                raw = accounting.read_npz(path)
                if not np.array_equal(raw["seeds"], SEEDS):
                    raise ValueError("raw row seed order differs")
                for column in accounting.LEDGER_COLS:
                    if not np.array_equal(raw[column], values[column][i]):
                        raise ValueError("aggregate differs from raw row: " + column)
            elif not (study / "provenance.json").exists():
                raise ValueError("local raw row is missing")
        data[duration], worlds[duration] = values, world
        per_duration[str(duration)], terms[duration] = {}, {}
        for pairs in PAIRS.values():
            for a, b in pairs:
                name = LABELS[a] + "__vs__" + LABELS[b]
                per_duration[str(duration)][name] = accounting.pair_report(
                    values, a, b, world, report["worlds"][str(duration)][name])
                terms[duration][name] = accounting.pair_terms(values, a, b, world)
    saved_contrasts = accounting.read_npz(folder / "contrasts.npz")
    if not np.array_equal(saved_contrasts["seeds"], SEEDS):
        raise ValueError("saved contrast seeds differ")
    summaries, contrasts = {"primary": {}, "secondary": {}}, {"seeds": np.asarray(SEEDS, dtype=np.uint64)}
    for group, pairs in PAIRS.items():
        for a, b in pairs:
            name = LABELS[a] + "__vs__" + LABELS[b]
            values = duration_contrast({t: data[t]["F"] for t in DURATIONS}, a, b)
            if not np.array_equal(values, saved_contrasts[name]):
                raise ValueError("saved duration contrast differs")
            estimate = accounting.stats(values)
            accounting.check_summary(estimate, report[group][name], name)
            contributions = {key: accounting.stats(np.stack([terms[t][name][key] for t in DURATIONS]).mean(axis=0))
                             for key in terms[DURATIONS[0]][name]}
            summaries[group][name] = {**estimate, "above_3se": estimate["mean"] > 3 * estimate["se"],
                                     "at_least_0p5": estimate["mean"] >= .5,
                                     "fitness_contributions": contributions}
            contrasts[name] = values
    summary = {"status": "complete", "research_genome_lives": 37548, "confirmation_genome_lives": 4608,
               "validation_genome_lives": 18, "monitored_cpu_seconds": budget["cpu_seconds"],
               "independent_search_replicates": 2, "seeds_per_endpoint_duration": 256, "durations": list(DURATIONS),
               "search_audits": search_audits, "neutrality": neutrality_audit(study, protocol),
               "per_duration": per_duration, **summaries, "limitations": report["limitations"],
               "accounting_analysis_sha256": accounting.digest(BASE)}
    return summary, contrasts


def export(study, out, summary, contrasts):
    if summary["status"] != "complete":
        raise ValueError("only completed fixed-endpoint results can be exported")
    prepared = study if (study / "provenance.json").exists() else ROOT / "results/structural_20261013"
    verify_archive(prepared)
    out.mkdir(parents=True, exist_ok=True)

    def keep(source, relative):
        target = out / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        if source.resolve() != target.resolve():
            shutil.copy2(source, target)

    for relative in accounting.read_json(prepared / "provenance.json")["artifacts"]:
        if "__pycache__" not in Path(relative).parts and Path(relative).suffix != ".pyc":
            keep(prepared / relative, relative)
    if not (out / "PREPARATION.md").exists():
        keep(out / "README.md", "PREPARATION.md")
    for name in ("ready.json", "budget.json"):
        keep(operation(study, name), Path("operations") / name)
    for path in (study / "confirmation").rglob("*"):
        if path.is_file() and path.name in ("manifest.json", "report.json", "genotypes.npz",
                                           "row_index.json", "scores.npz", "contrasts.npz"):
            keep(path, path.relative_to(study))
    for path in (study / "neutrality").iterdir():
        if path.is_file():
            keep(path, path.relative_to(study))
    for path in (study / "runs").rglob("*"):
        if path.is_file() and path.suffix in (".json", ".jsonl", ".yaml", ".pt", ".npz", ".npy"):
            keep(path, path.relative_to(study))
    protocol = accounting.read_json(study / "protocol.json")
    for relative, expected in protocol["source_identity"].items():
        source = study / "sources" / relative
        source = source if source.exists() else ROOT / relative
        equal(accounting.digest(source), expected, "exported numerical source")
        keep(source, Path("sources") / relative)
    controls = study / "dependency"
    if not (controls / "provenance.json").exists():
        controls = ROOT / "results/continuation_20261013"
    verify_archive(controls)
    for relative in accounting.read_json(controls / "provenance.json")["artifacts"]:
        keep(controls / relative, Path("dependency") / relative)
    keep(controls / "provenance.json", "dependency/provenance.json")
    keep(BASE, "sources/accounting_analysis.py")
    helper = Path(__file__).with_name("sources") / "continuation_analyze.py"
    if not helper.exists():
        helper = ROOT / "results/continuation_20261013/analyze.py"
    keep(helper, "sources/continuation_analyze.py")
    for name in ("analyze.py", "audit_search.py", "test_analyze.py", "test_audit_search.py"):
        path = Path(__file__).with_name(name)
        if path.exists():
            keep(path, name)
    accounting.write_json(out / "summary.json", summary)
    np.savez_compressed(out / "independent_contrasts.npz", **contrasts)
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, axes = plt.subplots(1, 2, figsize=(10, 4), layout="constrained")
    for ax, reference, title in zip(axes, ("matched D", "founder"), ("G minus matched D", "G minus row38 founder")):
        group = "primary" if reference == "matched D" else "secondary"
        keys = [name for name in summary[group] if reference == "matched D" or name.endswith("__vs__founder_row38")]
        for i, name in enumerate(keys):
            values = [summary["per_duration"][str(t)][name]["gain"] for t in DURATIONS] + [summary[group][name]]
            ax.errorbar(np.arange(4) + .06 * (2 * i - 1), [v["mean"] for v in values],
                        yerr=[3 * v["se"] for v in values], marker="o", capsize=3, label=f"Run {51089 + i}")
        ax.axhline(0, color=".5", linewidth=1)
        ax.set_xticks(np.arange(4), [str(t) for t in DURATIONS] + ["Mixture"])
        ax.set_xlabel("Lifetime; mixture averages within seed")
        ax.set_ylabel("Paired ΔF, ±3 SE")
        ax.set_title(title)
        ax.legend()
    for extension in ("png", "svg"):
        fig.savefig(out / f"structural_comparison.{extension}", dpi=180)
    plt.close(fig)
    lines = ["# Fixed structural-operator comparison", "",
             "Two preregistered 16-generation searches test silent duplication plus deletion against matched ordinary "
             "evolution. Every endpoint is fixed as final population rank zero; "
             "both signs and both replicates are retained.",
             "", "| Contrast | Duration-mixture mean ± SE | >3 SE | ≥0.5 F |", "|---|---:|---|---|"]
    for group in ("primary", "secondary"):
        for name, value in summary[group].items():
            lines.append(f"| {name.replace('__vs__', ' versus ')} | {value['mean']:+.6f} ± {value['se']:.6f} | "
                         f"{value['above_3se']} | {value['at_least_0p5']} |")
    lines += ["", "Each mixture averages T=768, 1024 and 1536 within the same seed before computing SE across 256 "
              "fresh shared seeds. Complete production fitness, costs, guards and extinction charges are retained.", "",
              f"Research lives: 37,548; separate neutrality validation: 18. Monitored worker CPU: "
              f"{summary['monitored_cpu_seconds']:.3f} seconds, within the fixed 14,400-second cap.", "",
              "This is a two-replicate comparison of duplication, deletion and the existing gene-count-scaled point "
              "mutation policy. Active gene count and duplicate ancestry do not establish functional use. "
              "Life-level SE does not measure uncertainty across evolutionary searches.", "",
              "Raw fixed endpoints, complete checkpoints/lineage, all confirmation ledger fields, neutrality evidence "
              "and source/numerical pins are preserved. Duplicate confirmation row files are omitted after exact "
              "aggregate reconciliation; their original hashes remain in row_index.json.", "",
              "[Prospective protocol](PREREG.md) · [Preparation](PREPARATION.md)", "", "```sh",
              ".venv/bin/python results/structural_20261013/analyze.py --study results/structural_20261013", "```", ""]
    (out / "README.md").write_text("\n".join(lines))
    artifacts = {str(path.relative_to(out)): {"sha256": accounting.digest(path), "bytes": path.stat().st_size}
                 for path in sorted(out.rglob("*")) if path.is_file() and "__pycache__" not in path.parts
                 and path.suffix != ".pyc" and path.name != "provenance.json"}
    # Preserve the nested control provenance too, so the independent checkpoint helper can audit its inputs.
    artifacts["dependency/provenance.json"] = {
        "sha256": accounting.digest(out / "dependency/provenance.json"),
        "bytes": (out / "dependency/provenance.json").stat().st_size}
    accounting.write_json(out / "provenance.json", {
        "status": "complete", "artifacts": artifacts, "simulated_lives_by_analysis": 0,
        "analysis_sha256": accounting.digest(Path(__file__)),
        "numerical_identity": protocol["expected_numerical_identity"]})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--study", type=Path, default=STUDY)
    parser.add_argument("--export", action="store_true")
    parser.add_argument("--out", type=Path, default=ROOT / "results/structural_20261013")
    args = parser.parse_args()
    budget_path = operation(args.study, "budget.json")
    if not budget_path.exists() or accounting.read_json(budget_path)["status"] != "complete":
        print(json.dumps({"status": "awaiting_complete_study", "simulated_lives": 0}))
        return
    summary, contrasts = analyze(args.study)
    if args.export:
        export(args.study, args.out, summary, contrasts)
    print(json.dumps({"status": summary["status"], "primary": summary["primary"], "simulated_lives": 0}, indent=2))


if __name__ == "__main__":
    main()
