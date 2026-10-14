"""Independent analysis/export of fixed transfer, second-step selection and allele factorial studies.

No lives are simulated. Default reports readiness; --export writes a portable
public archive, with --allow-partial permitting completed studies while naming
unfinished ones explicitly. Run the exported analyze.py on that archive to
recompute the same summary and figures from raw aggregates.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sys
from dataclasses import asdict
from pathlib import Path

os.environ.setdefault("ATEN_CPU_CAPABILITY", "avx2")
ROOT = next(path for path in Path(__file__).resolve().parents if (path / "src/genome.py").is_file())
sys.path.insert(0, str(ROOT))

import numpy as np  # noqa: E402
import torch  # noqa: E402

from src.genome import Layout  # noqa: E402
from src.life import spec  # noqa: E402

PHASES = ("transfer", "second_step", "factorial")
CASES = (("s5_base", 5, "base", 38), ("s5_pool", 5, "pool", 38),
         ("s7_base", 7, "base", 15), ("s7_pool", 7, "pool", 29))
DURATIONS = (768, 1024, 1536)
LEDGER_COLS = spec.V3.LEDGER + ("F_kernel", "extinct_charge", "window")


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def array_digest(array):
    return hashlib.sha256(np.asarray(array).tobytes()).hexdigest()


def read_json(path):
    return json.loads(Path(path).read_text())


def write_json(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(".tmp.json")
    temp.write_text(json.dumps(data, indent=2, allow_nan=False) + "\n")
    temp.replace(path)


def read_npz(path):
    with np.load(path, allow_pickle=False) as value:
        return {key: value[key].copy() for key in value.files}


def stats(values):
    values = np.asarray(values, dtype=float)
    if values.ndim != 1 or len(values) < 2 or not np.isfinite(values).all():
        raise ValueError("need finite paired per-seed values")
    return {"mean": float(values.mean()), "se": float(values.std(ddof=1) / np.sqrt(len(values))), "n": len(values)}


def check_summary(expected, saved, name):
    if expected["n"] != saved["n"] or any(
        not np.isclose(expected[key], saved[key], rtol=1e-11, atol=1e-12) for key in ("mean", "se")
    ):
        raise ValueError(f"{name}: saved summary differs from independent per-seed calculation")


def assert_same(actual, expected, name):
    if actual != expected:
        raise ValueError(f"{name}: metadata differs from fixed preregistered study")


def prior_root(study):
    archived = study / "inputs/prior"
    return archived if archived.exists() else ROOT / "results/pool_mutants_20261013"


def source_path(study, name):
    archived = study / "sources" / name
    return archived if archived.exists() else ROOT / "scripts" / name


def check_sources(study, phase, manifest):
    source = source_path(study, f"taskvar_{phase}.py")
    assert_same(digest(source), manifest["runner_sha256"], f"{phase} runner source")
    for name, expected in manifest["helpers"].items():
        assert_same(digest(source_path(study, name)), expected, f"{phase} helper {name}")


def check_prior(study, artifacts):
    prior = prior_root(study)
    for relative, expected in artifacts.items():
        assert_same(digest(prior / relative), expected, f"prior artifact {relative}")
    return prior


def prices(world):
    return {"living": ("live_time", world.c_live), "spiking": ("spikes", world.c_spike),
            "twitching": ("kappa_sum", world.c_tw), "messages": ("contact_events", world.c_msg),
            "division": ("claims", world.c_div), "secretion": ("sec_int", world.c_sec),
            "missed_clicks": ("misses", world.c_miss), "receptors": ("rec_gain", world.c_rec),
            "decoy_clicks": ("b2_clicks", max(0.0, -world.b2_value))}


def check_scores(data, seeds, indices, world):
    if not np.array_equal(data["seeds"], seeds) or not np.array_equal(data["genome_indices"], indices):
        raise ValueError("aggregate seed/genome order differs from fixed manifest")
    expected = (len(indices), len(seeds))
    for key in LEDGER_COLS:
        if data[key].shape != expected or not np.isfinite(data[key]).all():
            raise ValueError(f"invalid aggregate column {key}")
    status = data["status"].astype(np.int64)
    if not np.array_equal(data["status"], status):
        raise ValueError("noninteger status flags")
    invalid = spec.STATUS["capacity"] | spec.STATUS["ledger_mismatch"]
    guards = spec.STATUS["guard_cells"] | spec.STATUS["guard_events"]
    extinct = spec.STATUS["extinct"]
    if np.any(status & invalid):
        raise ValueError("capacity or ledger mismatch cannot become research evidence")
    if np.any(((status & (extinct | guards)) == 0) & (data["t_end"] != world.t0 + world.T)):
        raise ValueError("unexplained incomplete life")
    window = world.T - world.t_open
    if not np.all(data["window"] == window):
        raise ValueError("accounting windows differ")
    cost = np.zeros(expected)
    for key, price in prices(world).values():
        cost += price * data[key]
    guard_charge = np.where(status & guards != 0,
                            world.c_live * world.n_max * (world.t0 + world.T - data["t_end"]), 0.0)
    extinction = world.c_live * np.where(status & extinct != 0,
        world.t0 + world.T - np.maximum(data["t_ext"], world.t0 + world.t_open), 0.0) / window
    for name, reconstructed in (("cost", cost), ("guard_charge", guard_charge), ("extinct_charge", extinction),
        ("F_kernel", (data["income"] - data["cost"] - data["guard_charge"]) / window)):
        if not np.allclose(data[name], reconstructed, rtol=1e-10, atol=1e-9):
            raise ValueError(f"{name} differs from independent production accounting")
    if not np.array_equal(data["F"], data["F_kernel"] - data["extinct_charge"]):
        raise ValueError("fitness differs from kernel/extinction accounting")


def pair_terms(data, winner, parent, world):
    window = world.T - world.t_open
    terms = {"income": (data["income"][winner] - data["income"][parent]) / window,
             "cost_saving": (data["cost"][parent] - data["cost"][winner]) / window,
             "guard_charge_saving": (data["guard_charge"][parent] - data["guard_charge"][winner]) / window,
             "extinction_charge_saving": data["extinct_charge"][parent] - data["extinct_charge"][winner]}
    delta = data["F"][winner] - data["F"][parent]
    terms["accounting_residual"] = delta - sum(terms.values())
    return terms


def pair_report(data, winner, parent, world, saved=None):
    terms = pair_terms(data, winner, parent, world)
    counts = {key: stats(data[key][winner] - data[key][parent]) for key in
              ("captures", "misses", "clicks", "n_end", "n_H_end", "live_time", "spikes", "packets", "path")}
    result = {"parent_F": stats(data["F"][parent]), "winner_F": stats(data["F"][winner]),
              "gain": stats(data["F"][winner] - data["F"][parent]), "counts": counts,
              "fitness_contributions": {key: stats(value) for key, value in terms.items()},
              "cost_saving_components": {name: stats(price * (data[key][parent] - data[key][winner])
                                                       / (world.T - world.t_open))
                                         for name, (key, price) in prices(world).items()}}
    guards = spec.STATUS["guard_cells"] | spec.STATUS["guard_events"]
    result["guard_fraction"] = {label: float(np.mean(data["status"][i].astype(np.int64) & guards != 0))
                                for label, i in (("parent", parent), ("winner", winner))}
    if saved is not None:
        check_summary(result["gain"], saved["F"], "paired gain")
        for key, value in counts.items():
            check_summary(value, saved[key], f"paired {key}")
        for key, value in result["fitness_contributions"].items():
            check_summary(value, saved["fitness_contributions"][key], f"fitness contribution {key}")
        for key, value in result["cost_saving_components"].items():
            check_summary(value, saved["cost_saving_components"][key], f"cost component {key}")
    return result


def load_transfer(study):
    root = study / "transfer"
    manifest, report = read_json(root / "manifest.json"), read_json(root / "report.json")
    assert_same(report["status"], "complete", "transfer completion")
    check_sources(study, "transfer", manifest)
    prior = check_prior(study, manifest["artifacts"])
    seeds = list(range(51_850_000, 51_850_256))
    assert_same(manifest["seeds"], seeds, "transfer seeds")
    assert_same(set(manifest["cases"]), {name for name, _, _, _ in CASES}, "transfer cases")
    result, raw = {}, {}
    for name, body, world_name, original_row in CASES:
        meta = manifest["cases"][name]
        assert_same(meta["source_row"], original_row, f"{name} frozen winner row")
        pool = np.load(prior / f"genomes/s{body}_pool.npy", allow_pickle=False)
        assert_same(array_digest(pool[0]), meta["parent_sha256"], f"{name} parent")
        assert_same(array_digest(pool[original_row]), meta["winner_sha256"], f"{name} winner")
        worlds, data, deltas, terms = {}, {}, {}, {}
        conditions = [f"fast_T{duration}" for duration in DURATIONS] + ["old_T1024"]
        for condition in conditions:
            duration = int(condition.split("T")[1])
            overrides = {"T": duration, "d0": 1.0 if condition.startswith("old") else 0.5,
                         "d_min": 0.5 if condition.startswith("old") else 0.25, "t_open": 0.0}
            if world_name == "pool":
                overrides.update(sigma=0.4, lam_s=4.0)
            world = spec.world("catch_speck_l4", **overrides)
            assert_same(manifest["worlds"][name][condition], asdict(world), f"{name}/{condition} world")
            data[condition] = read_npz(root / name / condition / "scores.npz")
            check_scores(data[condition], seeds, [0, 1], world)
            deltas[condition] = data[condition]["F"][1] - data[condition]["F"][0]
            terms[condition] = pair_terms(data[condition], 1, 0, world)
            worlds[condition] = world
        deltas["duration_average"] = np.stack([deltas[f"fast_T{duration}"] for duration in DURATIONS]).mean(axis=0)
        deltas["fast_minus_old_gain"] = deltas["fast_T1024"] - deltas["old_T1024"]
        averages = {key: stats(np.stack([terms[f"fast_T{t}"][key] for t in DURATIONS]).mean(axis=0))
                    for key in terms["fast_T1024"]}
        stored_contrasts = read_npz(root / name / "contrasts.npz")
        if not np.array_equal(stored_contrasts["seeds"], seeds):
            raise ValueError("transfer contrasts seed order differs")
        for key, value in deltas.items():
            if not np.array_equal(value, stored_contrasts[key]):
                raise ValueError(f"transfer contrast array differs: {name}/{key}")
            check_summary(stats(value), report["cases"][name]["gains"][key], f"{name}/{key}")
        result[name] = {**meta, "gains": {key: stats(value) for key, value in deltas.items()},
                        "duration_average_contributions": averages,
                        "conditions": {condition: pair_report(values, 1, 0, worlds[condition],
                            report["cases"][name]["conditions"][condition]) for condition, values in data.items()}}
        raw[name] = deltas
    return {"status": "complete", "genome_lives": 8192, "seed_block": 85, "lives_per_condition": 256,
            "cpu_seconds": report["cpu_seconds"], "cases": result,
            "interpretation": "The same four fixed winners are measured across durations and conduction speeds. "
            "Mixture effects average per-seed fitness gains equally across three durations before computing SE. "
            "The conduction interaction is fast-minus-old mutant gain, not a selector or a world gate."}, raw, manifest


def independent_selection(scores, mapping, seeds, initial, extra, keep, shortlist, tie_seed):
    """Independent indexing/math implementation of the three production ranking permutations."""
    expanded = np.asarray(scores)[mapping]
    generator = torch.Generator().manual_seed(tie_seed)
    before = array_digest(generator.get_state().numpy())
    def ranked(values):
        permutation = torch.randperm(len(values), generator=generator).numpy()
        return permutation[np.argsort(-np.asarray(values)[permutation], kind="stable")]
    first = expanded[:, :initial].mean(axis=1)
    onestage = ranked(first)[:keep]
    short = ranked(first)[:shortlist]
    pooled = np.concatenate((expanded[short, :initial], expanded[short, initial:initial + extra]), axis=1)
    chosen = ranked(pooled.mean(axis=1))[:keep]
    order = short[chosen]
    winner = int(mapping[order[0]])
    return {"onestage_cohort_entries": onestage.tolist(), "shortlist_cohort_entries": short.tolist(),
            "kept_cohort_entries": order.tolist(), "kept_candidate_rows": mapping[order].tolist(),
            "winner_candidate_row": winner, "winner_cohort_entry": int(order[0]),
            "pooled_kept_fitness": pooled[chosen].mean(axis=1).tolist(),
            "tie_rng_start_sha256": before, "tie_rng_end_sha256": array_digest(generator.get_state().numpy()),
            "initial_seeds": list(seeds[:initial]), "recheck_seeds": list(seeds[initial:initial + extra]),
            "recheck_changed_entries": keep - len(set(order) & set(short[:keep])),
            "parent_copy_entries_retained": int(np.count_nonzero(mapping[order] == 0)),
            "unique_candidate_rows_retained": len(set(mapping[order].tolist()))}


def load_second_step(study):
    root = study / "second_step"
    manifest, report = read_json(root / "manifest.json"), read_json(root / "report.json")
    selection = read_json(root / "selection.json")
    assert_same(report["status"], "complete", "second-step completion")
    check_sources(study, "second_step", manifest)
    assert_same(manifest["candidate_rows"], 225, "second-step unique candidate count")
    assert_same(manifest["original_comparison_row"], 225, "original comparison row")
    assert_same(manifest["rules"], {"low": [3, 4], "high": [12, 16]}, "fixed selection budgets")
    assert_same(manifest["shortlist"], 64, "shortlist")
    assert_same(manifest["keep"], 32, "survivors")
    seeds = {"screen": list(range(51_860_000, 51_860_028)), "confirm": list(range(51_870_000, 51_870_512))}
    assert_same(manifest["seeds"], seeds, "second-step seeds")
    world = spec.world("catch_speck_l4", T=1024, sigma=0.4, lam_s=4, d0=0.5, d_min=0.25)
    assert_same(manifest["world"], asdict(world), "second-step world")
    genomes = np.load(root / "genomes.npy", allow_pickle=False)
    assert_same(array_digest(genomes), manifest["genomes_sha256"], "second-step genomes")
    assert_same(array_digest(genomes[0]), manifest["start_raw_sha256"], "second-step founder")
    assert_same(array_digest(genomes[225]), manifest["original_raw_sha256"], "original parent")
    prior = prior_root(study)
    _, founder = Layout.load(str(prior / "genomes/s5_pool_winner.json"))
    _, original = Layout.load(str(prior / "parents/s5/best_genome.json"))
    if genomes[0].tobytes() != founder.reshape(-1).float().numpy().tobytes():
        raise ValueError("second-step founder differs from frozen prior s5 winner")
    if genomes[225].tobytes() != original.reshape(-1).float().numpy().tobytes():
        raise ValueError("second-step original differs from prior parent")
    for name, path in (("start", prior / "genomes/s5_pool_winner.json"),
                       ("original", prior / "parents/s5/best_genome.json"),
                       ("config", prior / "parents/s5/config.yaml")):
        assert_same(digest(path), manifest["inputs"][name + "_sha256"], f"second-step input {name}")
    mapping = np.array([0] * 32 + list(range(1, 225)))
    assert_same(manifest["cohort_mapping"], mapping.tolist(), "32-copy/224-offspring population")
    screen = read_npz(root / "screen/scores.npz")
    check_scores(screen, seeds["screen"], list(range(225)), world)
    assert_same(digest(root / "screen/scores.npz"), selection["screen_scores_sha256"], "frozen screen")
    rules = {}
    for name, (initial, extra) in manifest["rules"].items():
        recomputed = independent_selection(screen["F"], mapping, seeds["screen"], initial, extra, 32, 64,
                                           manifest["tie_seed"])
        saved = selection["rules"][name]
        for key, value in recomputed.items():
            assert_same(value, saved[key], f"independent selector {name}/{key}")
        _, exported = Layout.load(str(root / f"{name}_selected_genome.json"))
        if exported.reshape(-1).float().numpy().tobytes() != genomes[saved["winner_candidate_row"]].tobytes():
            raise ValueError("exported selected genome differs from independent selector")
        rules[name] = saved
    rows, rolemap, seen = [], {}, {}
    expected_roles = {"original": 225, "start": 0,
                      **{name: value["winner_candidate_row"] for name, value in rules.items()}}
    for role, index in expected_roles.items():
        raw_sha = array_digest(genomes[index])
        if raw_sha not in seen:
            seen[raw_sha] = index
            rows.append(index)
        rolemap[role] = {"candidate_row": index, "scored_row": seen[raw_sha], "raw_sha256": raw_sha}
    assert_same(rolemap, selection["roles"], "confirmation roles")
    assert_same(rows, selection["confirmation_rows"], "deduplicated confirmation rows")
    confirmed = read_npz(root / "confirm/scores.npz")
    check_scores(confirmed, seeds["confirm"], rows, world)
    positions = {role: rows.index(value["scored_row"]) for role, value in rolemap.items()}
    raw, confirmed_report = {}, {}
    for name in ("low", "high"):
        raw[name] = confirmed["F"][positions[name]] - confirmed["F"][positions["start"]]
        confirmed_report[name] = {"candidate_row": rules[name]["winner_candidate_row"],
            "raw_sha256": rolemap[name]["raw_sha256"],
            "second_step": pair_report(confirmed, positions[name], positions["start"], world,
                                         report["confirmation"][name]["second_step_gain"]),
            "total_vs_original": pair_report(confirmed, positions[name], positions["original"], world,
                                               report["confirmation"][name]["total_gain_vs_original"])}
    raw["high_minus_low"] = confirmed["F"][positions["high"]] - confirmed["F"][positions["low"]]
    check_summary(stats(raw["high_minus_low"]), report["high_minus_low"], "high-minus-low selector result")
    start = pair_report(confirmed, positions["start"], positions["original"], world,
                        report["starting_gain_vs_original"])
    return {"status": "complete", "genome_lives": 6300 + len(rows) * 512, "cpu_seconds": report["cpu_seconds"],
            "seed_blocks": {"screen": 86, "confirm": 87}, "selection": rules, "confirmation_roles": rolemap,
            "confirmation": confirmed_report, "starting_gain_vs_original": start,
            "high_minus_low": stats(raw["high_minus_low"]),
            "interpretation": "A single frozen cohort tests a second mutation step and two scoring budgets. "
            "Both selectors share candidates and overlapping screen lives, then receive independent paired confirmation. "
            "This is not a normal population continuation or an equal-compute search comparison."}, raw, manifest


def factorial_deltas(values):
    parent, a, b, ab = values
    return {"A_minus_parent": a - parent, "B_minus_parent": b - parent, "AB_minus_A": ab - a,
            "AB_minus_B": ab - b, "AB_minus_parent": ab - parent, "epistasis": ab - a - b + parent}


def load_factorial(study):
    root = study / "factorial"
    manifest, report = read_json(root / "manifest.json"), read_json(root / "report.json")
    assert_same(report["status"], "complete", "factorial completion")
    check_sources(study, "factorial", manifest)
    prior = check_prior(study, manifest["artifacts"])
    seeds = list(range(51_880_000, 51_880_512))
    assert_same(manifest["seeds"], seeds, "factorial seeds")
    assert_same(manifest["genotype_order"], ["parent", "A", "B", "AB"], "factorial genotype order")
    assert_same(manifest["allele_slots"], [41, 124], "discovered allele slots")
    genotypes = read_npz(root / "genotypes.npz")
    genomes = genotypes["genomes"]
    pool = np.load(prior / "genomes/s5_pool.npy", allow_pickle=False)
    expected = np.repeat(pool[0:1], 4, axis=0)
    expected[1, 41] = pool[38, 41]
    expected[2, 124] = pool[38, 124]
    expected[3] = pool[38]
    if genomes.tobytes() != expected.tobytes():
        raise ValueError("factorial genotypes differ from exact discovered allele reversions")
    for label, genome in zip(("parent", "A", "B", "AB"), genomes):
        assert_same(array_digest(genome), manifest["genotype_sha256"][label], f"factorial {label} genotype")
    results, raw = {}, {}
    for name in ("base", "pool"):
        kwargs = dict(T=1024, d0=0.5, d_min=0.25)
        if name == "pool":
            kwargs.update(sigma=0.4, lam_s=4.0)
        world = spec.world("catch_speck_l4", **kwargs)
        assert_same(manifest["worlds"][name], asdict(world), f"factorial {name} world")
        data = read_npz(root / name / "scores.npz")
        check_scores(data, seeds, [0, 1, 2, 3], world)
        contrasts = {}
        measures = {key: data[key] for key in ("F", "captures", "cost", "income", "live_time", "n_end",
                                              "n_H_end", "path")}
        measures.update(cost_rate=data["cost"] / 1024, income_rate=data["income"] / 1024)
        for measure, values in measures.items():
            contrasts[measure] = {key: stats(value) for key, value in factorial_deltas(values).items()}
            for key, value in contrasts[measure].items():
                check_summary(value, report["worlds"][name]["contrasts"][measure][key], f"factorial {measure}/{key}")
        results[name] = {"contrasts": contrasts,
                         "vs_parent": {label: pair_report(data, i, 0, world,
                             report["worlds"][name]["vs_parent"][label]) for i, label in enumerate(("A", "B", "AB"), 1)}}
        raw[name] = factorial_deltas(data["F"])
    return {"status": "complete", "genome_lives": 4096, "cpu_seconds": report["cpu_seconds"], "seed_block": 88,
            "genotype_order": ["parent", "A", "B", "AB"], "allele_slots": [41, 124], "worlds": results,
            "interpretation": "Four fixed genotypes isolate the fitness effects of two already evolved GRN alleles. "
            "Epistasis is AB-A-B+parent, paired before summarization. This does not identify a novel circuit, "
            "isolate adult operation, or introduce an allele designed by hand."}, raw, manifest


def readiness(study, include):
    complete, pending = [], {}
    snapshot_path = study / "export_state.json"
    snapshot = read_json(snapshot_path).get("pending", {}) if snapshot_path.exists() else {}
    for phase in include:
        path = study / phase / "report.json"
        status = read_json(path).get("status", "missing status") if path.exists() else snapshot.get(phase, "missing report")
        if status == "complete":
            complete.append(phase)
        else:
            pending[phase] = status
    return complete, pending


def copy_file(source, destination):
    destination.parent.mkdir(parents=True, exist_ok=True)
    if source.resolve() != destination.resolve():
        shutil.copy2(source, destination)


def export_files(study, out, complete, manifests):
    paths = set()
    def keep(source, relative):
        destination = out / relative
        copy_file(source, destination)
        paths.add(destination)
    prior_needed = set()
    for phase in complete:
        source = study / phase
        for path in sorted(source.rglob("*")):
            if path.is_file() and (path.name in ("manifest.json", "report.json", "selection.json", "mutation_ops.json",
                "genomes.npy", "genotypes.npz", "scores.npz", "contrasts.npz", "low_selected_genome.json",
                "high_selected_genome.json")):
                keep(path, path.relative_to(study))
        manifest = manifests[phase]
        prior_needed.update(manifest.get("artifacts", {}))
        for name, expected in {f"taskvar_{phase}.py": manifest["runner_sha256"], **manifest["helpers"]}.items():
            path = source_path(study, name)
            assert_same(digest(path), expected, f"archived source {name}")
            keep(path, Path("sources") / name)
    if "second_step" in complete:
        prior_needed.update(("genomes/s5_pool_winner.json", "parents/s5/best_genome.json", "parents/s5/config.yaml"))
    behavior = study / "behavior_from_ledgers"
    if (behavior / "report.json").exists():
        record = read_json(behavior / "report.json")
        assert_same(record["runner_sha256"], digest(behavior / "analyze.py"), "behavior analysis source")
        assert_same(record["simulated_lives"], 0, "retrospective behavior life count")
        assert_same(record["archive_provenance_sha256"], digest(prior_root(study) / "provenance.json"),
                    "behavior prior provenance")
        prior_needed.add("provenance.json")
        for case in record["cases"]:
            for relative, expected in case["source_hashes"].items():
                assert_same(digest(prior_root(study) / relative), expected, "behavior raw input")
                prior_needed.add(relative)
        for name in ("analyze.py", "report.json"):
            keep(behavior / name, Path("behavior_from_ledgers") / name)
    for name in ("second_step_final_audit.json", "independent_selector_analysis.json", "validate_export.py", "export_audit.json"):
        path = study / "validation" / name
        if path.exists():
            keep(path, Path("validation") / name)
    watch = study / "watch"
    if (watch / "validation.json").exists():
        validation, record = read_json(watch / "validation.json"), read_json(watch / "provenance.json")
        for key in ("syntax", "synthetic_interactions"):
            assert_same(validation["ui"][key], "passed", f"viewer {key}")
        assert_same(validation["parity"]["status"], "passed", "viewer short parity")
        assert_same(digest(watch / "watch.html"), record["html_sha256"], "viewer HTML provenance")
        assert_same(record["html_sha256"], validation["html_sha256"], "validated viewer HTML")
        assert_same(digest(watch / "build_watch.py"), record["builder_sha256"], "viewer builder")
        assert_same(digest(watch / "watch.template.html"), record["template_sha256"], "viewer template")
        for relative, expected in record["inputs"].items():
            assert_same(digest(prior_root(study) / relative), expected, "viewer archived genotype")
            prior_needed.add(relative)
        for path in sorted(watch.iterdir()):
            if path.is_file():
                keep(path, Path("watch") / path.name)
        for name in ("watch.html", "COPYING.LGPL-2.1"):
            keep(watch / name, Path(name))
    prior = prior_root(study)
    if (prior / "ERRATA.md").exists():
        prior_needed.add("ERRATA.md")
    for relative in sorted(prior_needed):
        keep(prior / relative, Path("inputs/prior") / relative)
    operations = study / "operations" if (study / "operations").exists() else study
    for name in ("budget_ab.json", "prelaunch_budget_ab.json", "budget_factorial.json", "prelaunch_budget_factorial.json",
                 "run_budgeted.py", "transfer.ready.json", "second_step.ready.json", "factorial.ready.json"):
        path = operations / name
        if path.exists():
            keep(path, Path("operations") / name)
    keep(Path(__file__), Path("analyze.py"))
    return paths


def plots(summary, out):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    made = []
    def save(fig, name):
        for suffix in ("png", "svg"):
            path = out / f"{name}.{suffix}"
            fig.savefig(path, dpi=180)
            if suffix == "svg":
                path.write_text("\n".join(line.rstrip() for line in path.read_text().splitlines()) + "\n")
            made.append(path)
        plt.close(fig)
    transfer = summary["experiments"].get("transfer")
    if transfer:
        fig, axes = plt.subplots(1, 2, figsize=(11, 4.6), layout="constrained")
        labels = list(transfer["cases"])
        y = np.arange(len(labels))
        colors = ("#366c9c", "#b15d32", "#478359")
        for t, shift, color in zip(DURATIONS, (-.2, 0, .2), colors):
            values = [transfer["cases"][name]["gains"][f"fast_T{t}"] for name in labels]
            axes[0].errorbar([v["mean"] for v in values], y + shift, xerr=[3*v["se"] for v in values],
                             fmt="o", capsize=3, label=f"T={t}", color=color)
        for key, shift, label, color in (("duration_average", -.1, "Uniform duration mixture", "#29394a"),
                                        ("fast_minus_old_gain", .1, "Fast − old gain at T1024", "#9568a6")):
            values = [transfer["cases"][name]["gains"][key] for name in labels]
            axes[1].errorbar([v["mean"] for v in values], y + shift, xerr=[3*v["se"] for v in values],
                             fmt="o", capsize=3, label=label, color=color)
        for ax in axes:
            ax.axvline(0, color=".55", lw=1)
            ax.set_yticks(y, [name.replace("_", " / ") for name in labels])
            ax.invert_yaxis()
            ax.set_xlabel("Paired ΔF, ±3 SE")
            ax.legend(fontsize=8, loc="upper center", bbox_to_anchor=(.5, -.18))
            ax.grid(axis="x", color=".92")
        axes[0].set_title("The same fixed winners across life lengths")
        axes[1].set_title("Mixture and conduction interactions")
        fig.suptitle("256 shared fresh seeds; uncertainty retains cross-condition covariance")
        save(fig, "transfer")
    second = summary["experiments"].get("second_step")
    if second:
        labels = ["3 + 4 winner − start", "12 + 16 winner − start", "12 + 16 winner − 3 + 4 winner"]
        values = [second["confirmation"][name]["second_step"]["gain"] for name in ("low", "high")]
        values.append(second["high_minus_low"])
        fig, ax = plt.subplots(figsize=(8.3, 3.8), layout="constrained")
        ax.errorbar([value["mean"] for value in values], np.arange(3), xerr=[3*value["se"] for value in values],
                    fmt="o", capsize=4, color="#366c9c")
        ax.axvline(0, color=".55", lw=1)
        ax.set_yticks(np.arange(3), labels)
        ax.invert_yaxis()
        ax.set_xlabel("Independent 512-life paired ΔF, ±3 SE")
        ax.grid(axis="x", color=".92")
        ax.set_title("One frozen second-generation cohort; two scoring budgets")
        save(fig, "second_step")
    factorial = summary["experiments"].get("factorial")
    if factorial:
        labels = ["A − parent", "B − parent", "AB − parent", "AB − A", "AB − B", "AB − A − B + parent"]
        keys = ["A_minus_parent", "B_minus_parent", "AB_minus_parent", "AB_minus_A", "AB_minus_B", "epistasis"]
        fig, axes = plt.subplots(1, 2, figsize=(10, 4.7), sharey=True, layout="constrained")
        for ax, name in zip(axes, ("base", "pool")):
            values = [factorial["worlds"][name]["contrasts"]["F"][key] for key in keys]
            ax.errorbar([value["mean"] for value in values], np.arange(6), xerr=[3*value["se"] for value in values],
                        fmt="o", capsize=3, color="#478359")
            ax.axvline(0, color=".55", lw=1)
            ax.set_title(name.upper())
            ax.grid(axis="x", color=".92")
            ax.set_yticks(np.arange(6), labels)
            ax.set_xlabel("Paired ΔF, ±3 SE")
        axes[0].invert_yaxis()
        fig.suptitle("Two evolved GRN alleles: individual effects and their interaction")
        save(fig, "allele_factorial")
    return made


def write_readme(summary, out):
    def show(value):
        return f"{value['mean']:+.3f} ± {value['se']:.3f}"
    lines = ["# Following useful mutations through duration, selection and allele effects", "",
        "All experiments keep the organism local and asynchronous and use existing ABI 3 worlds and prices. "
        "The genotypes and comparisons were frozen before scoring; transfer outcomes select no replacement genotype.", ""]
    if "illustrative_viewer" in summary:
        lines += ["[Watch the original s5 parent beside its first-step descendant](watch.html). The page starts "
            "paused and uses a fixed illustrative seed; these single lives were not used to choose a genotype. "
            "Source, exact bodies, license and short parity checks are in `watch/`.", ""]
    if summary["pending"]:
        lines += ["This is a partial archive. Still unfinished: " + ", ".join(summary["pending"]) + ".", ""]
    transfer = summary["experiments"].get("transfer")
    if transfer:
        lines += ["## Transfer of the first-step winners", "",
            "The equal duration mixture averages each seed's gains at T768, T1024 and T1536 before calculating SE. "
            "The conduction interaction subtracts the old-conduction gain from the fast-conduction gain at T1024.", "",
            "| Fixed winner | Duration-mixture gain, F ± SE | Old-conduction T1024 gain | Fast − old gain |",
            "|---|---:|---:|---:|"]
        for name, case in transfer["cases"].items():
            gains = case["gains"]
            lines.append(f"| {name.replace('_', ' / ')} | {show(gains['duration_average'])} | "
                         f"{show(gains['old_T1024'])} | {show(gains['fast_minus_old_gain'])} |")
        lines += ["", "These are unchanged winners, including the earlier weak s7/POOL result. The same s5 genotype "
            "appears in two worlds; four comparisons do not mean four independent discoveries. All four duration "
            "averages are positive by more than three SE on this batch. The old-conduction gains are unresolved; "
            "the fast-minus-old interaction exceeds three SE for the s5 genotype in both worlds. This supports "
            "conduction-dependent expression of that genotype's advantage, without identifying the mechanism.", ""]
    second = summary["experiments"].get("second_step")
    if second:
        lines += ["## A second step under two scoring budgets", "",
            "One fixed pool has 224 ordinary mutants of the prior s5 winner, plus 32 copies of that founder in "
            "the selector. Both selectors shortlist 64 and retain 32. The lower budget uses 3 + 4 lives; the higher "
            "uses 12 + 16. One winner from each is frozen and measured on 512 independent paired lives.", "",
            "| Selector | Chosen candidate row | Additional gain over first-step winner, F ± SE | Total over original s5 |",
            "|---|---:|---:|---:|"]
        for name, label in (("low", "3 + 4"), ("high", "12 + 16")):
            value = second["confirmation"][name]
            lines.append(f"| {label} | {value['candidate_row']} | {show(value['second_step']['gain'])} | "
                         f"{show(value['total_vs_original']['gain'])} |")
        lines += ["", "Higher-budget winner minus lower-budget winner: **" + show(second["high_minus_low"]) + " F**.",
            "", "This is a single cloned-parent candidate pool at T1024. It can demonstrate another available step "
            "or a difference between two selector choices; it cannot establish typical search efficiency, "
            "equal-compute superiority, or reliable long-term accumulation.", ""]
        if second["confirmation"]["low"]["raw_sha256"] == second["confirmation"]["high"]["raw_sha256"]:
            lines += ["Both rules chose the identical genotype, so the high-minus-low comparison is exactly zero. "
                "This cohort supplies no winner-quality separation between the two scoring budgets. Fresh "
                "confirmation does not resolve an additional gain over the first-step founder, so this cohort "
                "does not confirm a second accumulation step.", ""]
    factorial = summary["experiments"].get("factorial")
    if factorial:
        lines += ["## Effects of the two already discovered s5 alleles", "",
            "A copies the evolved W[1,16] allele, which reads the first internal chemical signal. B copies W[4,24], "
            "which reads the local motor-plane cue. AB is the exact prior winner. These are fixed measurement "
            "reversions of evolved values, with no allele tuning.", "",
            "| World | A − parent | B − parent | AB − parent | AB − A − B + parent |", "|---|---:|---:|---:|---:|"]
        for name, value in factorial["worlds"].items():
            contrasts = value["contrasts"]["F"]
            lines.append(f"| {name} | " + " | ".join(show(contrasts[key]) for key in
                ("A_minus_parent", "B_minus_parent", "AB_minus_parent", "epistasis")) + " |")
        lines += ["", "The interaction measures nonadditive fitness. These alleles change gene regulation and "
            "development; the measurements do not establish a new routing algorithm or an adult-only mechanism. "
            "A alone improves fitness by more than three SE in both worlds. Neither B's added effect on A nor "
            "the interaction clears three SE; this batch gives no evidence that B is required for the gain. "
            "An unresolved contrast is not evidence of zero effect.", ""]
    lines += ["## Evidence and limits", "",
        "- `summary.json` independently reconstructs paired effects, income and cost changes from aggregate arrays.",
        "- Experiment directories preserve all aggregate NPZ files, original manifests and reports; second-step "
        "genomes and operations and the four factorial genotypes are included when complete.",
        "- `inputs/prior/` preserves the prior parent/configuration/genotype artifacts used by these experiments. "
        "`sources/` preserves the measured runner and helper sources.",
        "- The [prior archive's lesion clarification](inputs/prior/ERRATA.md) states that new lateral spike "
        "messages are suppressed after the fork, while messages already in flight are processed normally. "
        "Pinned original archive files remain unchanged.",
        "- `behavior_from_ledgers/` preserves a retrospective analysis of the earlier 512-life confirmations, "
        "with zero additional simulated lives. It reports movement, sampled occupancy, clicks/capture and development; "
        "these are descriptive associations and do not isolate adult circuit function.",
        "- `validation/second_step_final_audit.json` records 294 short validation-only genome-lives. The first smoke "
        "consumed reserved G2 seeds 51,100,000 and 51,100,001 at T32; exclude both from future G2 evidence. "
        "The final smoke used validation blocks 8 and 9, and none of the scientific blocks 85–88.",
        "- `operations/` contains available external CPU-monitor records. Intermediate exports may contain "
        "a running-monitor snapshot; every experiment's own completed row CPU is also retained.",
        "- `provenance.json` hashes public artifacts. `analyze.py` can rebuild all reported statistics and figures "
        "without simulating new lives.",
        "- None of these measurements admits or rejects a world, measures matched-footprint information use, "
        "or proves long-term evolutionary accumulation. Fitness remains task income minus the existing costs.", "",
        "```bash", ".venv/bin/python results/followthrough_20261013/analyze.py \\",
        "  --study results/followthrough_20261013 --out outputs/followthrough_reanalysis --export --allow-partial",
        "```", ""]
    (out / "README.md").write_text("\n".join(lines))


def self_check():
    # Perfectly opposed duration fluctuations cancel; treating SEs as independent would not.
    effects = np.array([[1, 3, 5, 7], [7, 5, 3, 1], [4, 4, 4, 4]], dtype=float)
    assert stats(effects.mean(axis=0)) == {"mean": 4, "se": 0, "n": 4}
    assert np.array_equal(factorial_deltas(np.array([[1, 50, 100], [2, 52, 103],
        [6, 54, 103], [9, 58, 108]], dtype=float))["epistasis"], [2, 2, 2])
    tied = independent_selection(np.zeros((5, 28)), np.array([0, 0, 1, 2, 3, 4]), list(range(28)),
                                  3, 4, 2, 4, 1234)
    assert len(tied["kept_cohort_entries"]) == 2
    assert tied == independent_selection(np.zeros((5, 28)), np.array([0, 0, 1, 2, 3, 4]), list(range(28)),
                                         3, 4, 2, 4, 1234)
    print(json.dumps({"analysis_self_check": "passed", "simulated_lives": 0}))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--study", type=Path, default=ROOT / "outputs/autonomous_followthrough_20261013")
    parser.add_argument("--out", type=Path, default=ROOT / "results/followthrough_20261013")
    parser.add_argument("--include", choices=PHASES, nargs="+", default=list(PHASES))
    parser.add_argument("--export", action="store_true")
    parser.add_argument("--allow-partial", action="store_true")
    parser.add_argument("--self-check", action="store_true")
    args = parser.parse_args()
    if args.self_check:
        self_check()
        return
    complete, pending = readiness(args.study, args.include)
    if not complete or (pending and not args.allow_partial):
        print(json.dumps({"status": "incomplete", "complete": complete, "pending": pending}, indent=2))
        return
    records, raw, manifests = {}, {}, {}
    for phase in complete:
        records[phase], raw[phase], manifests[phase] = globals()[f"load_{phase}"](args.study)
    identities = [manifest["numerical_identity"] for manifest in manifests.values()]
    if any(identity != identities[0] for identity in identities):
        raise ValueError("experiments use different numerical/source identities")
    if not args.export:
        print(json.dumps({"status": "ready", "complete": complete, "pending": pending, "out": str(args.out)}, indent=2))
        return
    args.out.mkdir(parents=True, exist_ok=True)
    summary = {"study": "followthrough_20261013", "status": "partial" if pending else "complete",
               "report_only": True, "experiments": records, "pending": pending,
               "completed_genome_lives": sum(record["genome_lives"] for record in records.values()),
               "completed_row_cpu_seconds": sum(record["cpu_seconds"] for record in records.values()),
               "analysis": "Independent accounting and paired arithmetic; second-step rankings independently "
                           "replayed with the same three torch tie permutations, without calling a simulator."}
    behavior_path = args.study / "behavior_from_ledgers/report.json"
    if behavior_path.exists():
        summary["behavior_from_prior_ledgers"] = {"analysis_only": True, "simulated_lives": 0,
            "artifact": "behavior_from_ledgers/report.json",
            "interpretation": "Retrospective descriptive readouts of the prior confirmation data, "
                              "not independent evidence or an adult-only mechanism test."}
    audit_path = args.study / "validation/second_step_final_audit.json"
    if audit_path.exists():
        audit = read_json(audit_path)
        summary["validation_only"] = {"genome_lives": audit["validation_only_total_genome_lives"],
            "final_smoke_seed_blocks": audit["seed_blocks"], "exclude_from_future_G2": [51_100_000, 51_100_001],
            "note": audit["scientific_seed_collision_note"], "artifact": "validation/second_step_final_audit.json"}
    watch_validation = args.study / "watch/validation.json"
    if watch_validation.exists():
        validation = read_json(watch_validation)
        summary["illustrative_viewer"] = {"entrypoint": "watch.html", "default_seed": validation["default_seed"],
            "validation": "watch/validation.json", "validation_kernel_lives": validation["kernel_lives"],
            "validation_browser_engine_lives": validation["browser_engine_lives"],
            "validation_duration": validation["duration"], "short_parity": validation["parity"]["status"],
            "visual_inspection": validation["browser_visual_inspection"],
            "interpretation": "Single illustrative lives, not scientific evidence or genotype selection."}
    paths = export_files(args.study, args.out, complete, manifests)
    write_json(args.out / "export_state.json", {"complete": complete, "pending": pending,
        "note": "Readiness snapshot preserves unfinished-study status during reanalysis of a partial archive."})
    paths.add(args.out / "export_state.json")
    write_json(args.out / "summary.json", summary)
    paths.add(args.out / "summary.json")
    paths.update(plots(summary, args.out))
    write_readme(summary, args.out)
    paths.add(args.out / "README.md")
    write_json(args.out / "provenance.json", {"numerical_identity": identities[0],
        "analysis_sha256": digest(Path(__file__)), "artifacts": {
            str(path.relative_to(args.out)): {"sha256": digest(path), "bytes": path.stat().st_size}
            for path in sorted(paths)}})
    print(json.dumps({"status": "exported", "complete": complete, "pending": pending,
                      "out": str(args.out), "genome_lives": summary["completed_genome_lives"]}, indent=2))


if __name__ == "__main__":
    main()
