"""Analysis-only aggregation/export of the fixed four-arm mutant study; never runs lives.

Default reports readiness. --export requires all four follow-ups complete and
preserves compact raw arrays, identity, parents and selected genomes publicly.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sys
from pathlib import Path

os.environ.setdefault("ATEN_CPU_CAPABILITY", "avx2")
ROOT = next(path for path in Path(__file__).resolve().parents if (path / "src/genome.py").is_file())
sys.path.insert(0, str(ROOT))

# Imports follow the root path and numerical-dispatch setup for standalone execution.
import numpy as np  # noqa: E402
import torch  # noqa: E402

from src.genome import Layout  # noqa: E402
from src.life import spec  # noqa: E402

STAGES = ("rescore", "confirm", "lesion_normal", "lesion_lateral_off")
ARMS = tuple((body, world) for body in (5, 7) for world in ("base", "pool"))
DEFAULT_STUDY = ROOT / "outputs/autonomous_pool_20261013"
DEFAULT_OUT = ROOT / "results/pool_mutants_20261013"


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def raw_digest(array):
    return hashlib.sha256(np.asarray(array).tobytes()).hexdigest()


def read_json(path):
    return json.loads(Path(path).read_text())


def write_json(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(data, indent=2, allow_nan=False) + "\n")
    temporary.replace(path)


def read_npz(path):
    with np.load(path, allow_pickle=False) as loaded:
        return {key: loaded[key].copy() for key in loaded.files}


def summary(values):
    values = np.asarray(values, dtype=float)
    if values.ndim != 1 or len(values) < 2 or not np.isfinite(values).all():
        raise ValueError("need at least two finite per-life values")
    return {"mean": float(values.mean()), "se": float(values.std(ddof=1) / np.sqrt(len(values))), "n": len(values)}


def check_summary(actual, expected, name):
    if actual["n"] != expected["n"] or any(
        not np.isclose(actual[key], expected[key], rtol=1e-12, atol=1e-12) for key in ("mean", "se")
    ):
        raise ValueError(f"{name}: saved summary differs from raw paired scores")


def check_rows(data, seeds, indices, duration):
    if not np.array_equal(data["seeds"], seeds):
        raise ValueError("stage seed order differs from manifest")
    if "genome_indices" in data and not np.array_equal(data["genome_indices"], indices):
        raise ValueError("stage genome row order differs from selection")
    expected = (len(indices), len(seeds))
    for key, values in data.items():
        if key in ("seeds", "genome_indices"):
            continue
        if values.shape != expected or not np.isfinite(values).all():
            raise ValueError(f"invalid {key} shape or values")
    status = data["status"].astype(np.int64)
    invalid = spec.STATUS["capacity"] | spec.STATUS["ledger_mismatch"]
    ended = spec.STATUS["extinct"] | spec.STATUS["guard_cells"] | spec.STATUS["guard_events"]
    if np.any(status & invalid) or np.any(((status & ended) == 0) & (data["t_end"] != duration)):
        raise ValueError("invalid or unexplained incomplete lives")
    if not np.array_equal(data["F"], data["F_kernel"] - data["extinct_charge"]):
        raise ValueError("fitness differs from production guard/extinction accounting")


def get_parent(study, body):
    public = study / "parents" / f"s{body}" / "best_genome.json"
    if public.exists():
        return public
    return ROOT / f"outputs/catch_pilot/speck_lmax4_hexprism_sex_s{body}/best_genome.json"


def screen_dir(study, body, world):
    return study / "screens" / f"s{body}_{world}_T1024_b80"


def readiness(study):
    pending = []
    for body, world in ARMS:
        path = screen_dir(study, body, world)
        for relative in ("scores.npz", "report.json", "followup/report.json", "followup/selection.json"):
            if not (path / relative).exists():
                pending.append(str(path.relative_to(study) / relative))
        report = path / "followup/report.json"
        if report.exists() and read_json(report).get("last_completed_stage") != "lesion":
            pending.append(str(report.relative_to(study)) + ": lesion unfinished")
    return pending


def load_arm(study, body, world):
    path = screen_dir(study, body, world)
    manifest = read_json(path / "manifest.json")
    follow = path / "followup"
    fm = read_json(follow / "manifest.json")
    report = read_json(follow / "report.json")
    selection = read_json(follow / "selection.json")
    parent = get_parent(study, body)
    if (digest(parent) != manifest["parent_sha256"]
            or digest(parent.parent / "config.yaml") != manifest["config_sha256"]):
        raise ValueError("parent or saved pilot config differs from manifest")
    pool_path = path / "genomes.npy"
    if not pool_path.exists():
        pool_path = study / "genomes" / f"s{body}_pool.npy"
    genomes = np.load(pool_path, allow_pickle=False)
    if raw_digest(genomes) != manifest["genomes_sha256"]:
        raise ValueError("genome pool differs from manifest")
    layout, ancestor = Layout.load(str(parent))
    if not np.array_equal(genomes[0], ancestor.reshape(-1).numpy()):
        raise ValueError("pool parent differs from original genome")
    if manifest["world"] != world or manifest["mutants"] != 64 or manifest["overrides"]["T"] != 1024:
        raise ValueError("not the fixed 64-mutant T1024 study")
    expected_world = {"T": 1024.0, "d0": 0.5, "d_min": 0.25}
    if world == "pool":
        expected_world.update(sigma=0.4, lam_s=4.0)
    if manifest["overrides"] != expected_world or manifest["seeds"] != list(range(51_800_000, 51_800_032)):
        raise ValueError("screen world/seeds differ from the fixed study")
    expected_seeds = {"rescore": list(range(51_810_000, 51_810_512)),
                      "confirm": list(range(51_820_000, 51_820_512)),
                      "lesion": list(range(51_830_000, 51_830_256))}
    if fm["seeds"] != expected_seeds or report["seeds"] != expected_seeds:
        raise ValueError("follow-up seeds/sample sizes differ from the fixed study")
    for field, source in (("screen_manifest_sha256", "manifest.json"), ("screen_scores_sha256", "scores.npz")):
        if fm[field] != digest(path / source):
            raise ValueError("follow-up does not bind the saved screen")
    if fm["numerical_identity"] != manifest["numerical_identity"]:
        raise ValueError("screen and follow-up numerical identities differ")
    if fm["lesion"] != {"t_fork": 256.0, "t_open": 0, "flag": "lateral_off"}:
        raise ValueError("lesion protocol differs from preregistered full-life comparison")
    winner = selection["winner_genome_row"]
    if winner != report["winner_genome_row"] or selection["winner_mutant_index"] != winner - 1:
        raise ValueError("winner indexing differs between artifacts")
    if raw_digest(genomes[winner]) != selection["winner_sha256"]:
        raise ValueError("winner bytes differ from frozen selection")
    screen = read_npz(path / "scores.npz")
    check_rows(screen, manifest["seeds"], list(range(65)), 1024)
    expected_top = sorted(range(1, 65), key=lambda i: (-float(screen["F"][i].mean()), i))[:4]
    if expected_top != selection["selected_genome_rows"] or expected_top != fm["selected_genome_rows"]:
        raise ValueError("rescored set differs from fixed top-four rule")
    arrays = {}
    seed_sets = [set(manifest["seeds"])]
    for stage in ("rescore", "confirm", "lesion"):
        seeds = fm["seeds"][stage]
        if len(seeds) != len(set(seeds)) or any(set(seeds) & previous for previous in seed_sets):
            raise ValueError("seeds repeat across independent stages")
        seed_sets.append(set(seeds))
    for stage in STAGES:
        data = read_npz(follow / stage / "scores.npz")
        seed_stage = "lesion" if stage.startswith("lesion") else stage
        indices = [0, *expected_top] if stage == "rescore" else [0, winner]
        check_rows(data, fm["seeds"][seed_stage], indices, 1024)
        arrays[stage] = data
    rescored = arrays["rescore"]
    row_for = {int(index): i for i, index in enumerate(rescored["genome_indices"])}
    chosen = min(expected_top, key=lambda i: (-float(rescored["F"][row_for[i]].mean()), i))
    if chosen != winner:
        raise ValueError("frozen winner differs from rescore rule")
    confirmed = arrays["confirm"]
    gain = confirmed["F"][1] - confirmed["F"][0]
    normal = arrays["lesion_normal"]
    lesioned = arrays["lesion_lateral_off"]
    interaction = (normal["F"][1] - normal["F"][0]) - (lesioned["F"][1] - lesioned["F"][0])
    check_summary(summary(gain), report["confirmation"]["F"], "confirmation gain")
    check_summary(summary(interaction), report["lesion"]["gain_dependence"], "lesion interaction")
    world_spec = spec.world("catch_speck_l4", **expected_world)
    prices = {"living": ("live_time", world_spec.c_live), "spiking": ("spikes", world_spec.c_spike),
              "twitching": ("kappa_sum", world_spec.c_tw), "messages": ("contact_events", world_spec.c_msg),
              "division": ("claims", world_spec.c_div), "secretion": ("sec_int", world_spec.c_sec),
              "missed_clicks": ("misses", world_spec.c_miss), "receptors": ("rec_gain", world_spec.c_rec),
              "decoy_clicks": ("b2_clicks", spec.b2_cost(world_spec))}
    for stage in ("confirm", "lesion_normal", "lesion_lateral_off"):
        data = arrays[stage]
        comparison = report["confirmation"] if stage == "confirm" else report["lesion"][
            "normal" if stage == "lesion_normal" else "lateral_off"]
        reconstructed = np.zeros_like(data["cost"])
        for name, (column, price) in prices.items():
            component = price * data[column] / 1024
            check_summary(summary(component[0] - component[1]), comparison["cost_saving_components"][name],
                          f"{stage} cost component {name}")
            reconstructed += price * data[column]
        if not np.allclose(reconstructed, data["cost"], rtol=1e-9, atol=1e-9):
            raise ValueError("saved cost components do not recover total cost")
        kernel = (data["income"] - data["cost"] - data["guard_charge"]) / 1024
        if not np.allclose(kernel, data["F_kernel"], rtol=1e-10, atol=1e-10):
            raise ValueError("ledger totals do not recover fitness")
    ops_path = path / "mutation_ops.json"
    if not ops_path.exists():
        ops_path = study / "genomes" / f"s{body}_mutation_ops.json"
    operations = read_json(ops_path)
    return dict(body=body, world=world, path=path, parent=parent, manifest=manifest, follow_manifest=fm,
                report=report, selection=selection, genomes=genomes, pool_path=pool_path, layout=layout,
                screen=screen, arrays=arrays, winner=winner, gain=gain, interaction=interaction,
                operations=operations, ops_path=ops_path)



def small_batch_noise(values):
    """Post-hoc paired-rank noise; fixed ordered disjoint groups, no selection feedback."""
    values = np.asarray(values, dtype=float)
    batches = {}
    for size in (3, 4, 7, 8, 16, 32):
        used = (len(values) // size) * size
        means = values[:used].reshape(-1, size).mean(axis=1)
        batches[str(size)] = {"batch_size": size, "batches": len(means),
                              "ignored_trailing_lives": len(values) - used,
                              "nonpositive_batches": int(np.count_nonzero(means <= 0)),
                              "fraction_nonpositive": float(np.mean(means <= 0)),
                              "exact_zero_batches": int(np.count_nonzero(means == 0))}
    return {"exploratory": True, "paired_difference_sd": float(values.std(ddof=1)), "batches": batches,
            "method": "Disjoint contiguous batches in fixed confirmation seed order; count mean mutant-parent F <=0. "
                      "Batch 3 approximates initial pairwise scoring and batch 7 the 3+4 pooled score, "
                      "not tournament selection.",
            "limitation": "Conditional on these selected winners. This measures pairwise sampling noise, not full "
                          "tournament effectiveness; no verdict, winner or future run is changed by this readout."}


def arm_summary(arm):
    report = arm["report"]
    winner = arm["winner"]
    screen = arm["screen"]
    effects = screen["F"][1:] - screen["F"][0]
    means = effects.mean(axis=1)
    ses = effects.std(axis=1, ddof=1) / np.sqrt(effects.shape[1])
    confirmed = arm["arrays"]["confirm"]
    confirm = summary(arm["gain"])
    interaction = summary(arm["interaction"])
    guards = spec.STATUS["guard_cells"] | spec.STATUS["guard_events"]
    return {
        "parent": f"s{arm['body']}", "world": arm["world"], "world_overrides": arm["manifest"]["overrides"],
        "winner_genome_row": winner, "winner_mutant_index": winner - 1,
        "winner_sha256": arm["selection"]["winner_sha256"],
        "winner_genome": f"genomes/s{arm['body']}_{arm['world']}_winner.json",
        "mutation_operations": arm["operations"][winner - 1],
        "screen": {"mutants": 64, "lives": effects.shape[1], "positive_2se": int(np.count_nonzero(means > 2 * ses)),
                   "nominal_positive_fraction_2se": float(np.mean(means > 2 * ses)),
                   "effect_mean_quantiles": dict(zip(("min", "q25", "median", "q75", "max"),
                                                      np.quantile(means, [0, .25, .5, .75, 1]).tolist())),
                   "guard_life_fraction": float(np.mean(screen["status"][1:].astype(np.int64) & guards != 0)),
                   "selected_genome_rows": report["selected_genome_rows"]},
        "rescore": {key: value["F"] for key, value in report["rescore"].items()},
        "confirmation": {"parent_F": summary(confirmed["F"][0]), "winner_F": summary(confirmed["F"][1]),
                         "gain": confirm, "small_batch_noise": small_batch_noise(arm["gain"]),
                         "positive_3se": confirm["mean"] > 3 * confirm["se"],
                         "gain_at_least_0p5": confirm["mean"] >= .5,
                         "counts": {key: report["confirmation"][key] for key in
                                    ("captures", "clicks", "misses", "n_end", "n_H_end", "live_time")},
                         "fitness_contributions": report["confirmation"]["fitness_contributions"],
                         "cost_saving_components": report["confirmation"]["cost_saving_components"],
                         "guard_fraction": report["confirmation"]["guard_fraction"]},
        "lateral_lesion": {"t_fork": 256, "t_open": 0, "paired_lives": interaction["n"],
                           "scope": "Blocks in-plane spike arrivals; vertical spikes and morphogen packets continue.",
                           "incremental_gain_removed": interaction,
                           "interaction_positive_3se": interaction["mean"] > 3 * interaction["se"],
                           "normal_gain": report["lesion"]["normal"]["F"],
                           "lesioned_gain": report["lesion"]["lateral_off"]["F"],
                           "parent_loss": report["lesion"]["parent_loss"],
                           "winner_loss": report["lesion"]["winner_loss"]},
    }


def cross_world(arms):
    result = {}
    for body in (5, 7):
        base, pool = arms[f"s{body}_base"], arms[f"s{body}_pool"]
        if not np.array_equal(base["genomes"], pool["genomes"]):
            raise ValueError("cross-world comparison requires identical mutation pools")
        if not np.array_equal(base["screen"]["seeds"], pool["screen"]["seeds"]):
            raise ValueError("cross-world comparison requires identical ordered seeds")
        a = base["screen"]["F"][1:] - base["screen"]["F"][0]
        b = pool["screen"]["F"][1:] - pool["screen"]["F"][0]
        # All mutants, including neutral and guarded ones. No selected-only or per-life reference switching.
        contrast = b - a
        ma, mb = a.mean(axis=1), b.mean(axis=1)
        result[f"s{body}"] = {
            "mutants": 64, "paired_lives_per_mutant": a.shape[1],
            "method": "For each unchanged mutant: (F_mutant-F_parent)_POOL minus (F_mutant-F_parent)_base.",
            "exploratory": True,
            "correlation_of_noisy_mean_effects": float(np.corrcoef(ma, mb)[0, 1])
                if ma.std() > 0 and mb.std() > 0 else None,
            "fraction_positive_mean_effect_in_both": float(np.mean((ma > 0) & (mb > 0))),
            "rows": [{"mutant_index": i, "genome_row": i + 1, "base": summary(a[i]), "pool": summary(b[i]),
                      "pool_minus_base": summary(contrast[i])} for i in range(64)],
            "limitation": "32-life screen effects share their parent and lives; noisy associations are descriptive."
        }
    return result


def copy_file(source, target):
    target.parent.mkdir(parents=True, exist_ok=True)
    if source.resolve() != target.resolve():
        shutil.copy2(source, target)


def operational_file(study, name):
    direct = study / name
    return direct if direct.exists() else study / "operations" / name


def export_raw(arms, study, out):
    paths = []
    for label, arm in arms.items():
        source = arm["path"]
        target = out / source.relative_to(study)
        for relative in ("manifest.json", "report.json", "scores.npz", "followup/manifest.json",
                         "followup/report.json", "followup/selection.json", *(
                             f"followup/{stage}/scores.npz" for stage in STAGES)):
            src, dst = source / relative, target / relative
            copy_file(src, dst)
            paths.append(dst)
        body = arm["body"]
        for relative in ("best_genome.json", "config.yaml"):
            dst = out / "parents" / f"s{body}" / relative
            copy_file(arm["parent"].parent / relative, dst)
            paths.append(dst)
        for src, name in ((arm["pool_path"], f"s{body}_pool.npy"),
                          (arm["ops_path"], f"s{body}_mutation_ops.json")):
            dst = out / "genomes" / name
            copy_file(src, dst)
            paths.append(dst)
        winner_file = out / "genomes" / f"{label}_winner.json"
        arm["layout"].save(torch.from_numpy(arm["genomes"][arm["winner"]]), winner_file)
        _, exported = Layout.load(winner_file)
        if raw_digest(exported.numpy()) != arm["selection"]["winner_sha256"]:
            raise ValueError("exported winner did not round-trip exactly")
        paths.append(winner_file)
    mutation_file = study / "winner_mutations.json"
    decoder_file = study / "decode_winner_mutations.py"
    if not decoder_file.exists():
        decoder_file = study / "sources/decode_winner_mutations.py"
    if mutation_file.exists():
        decoded = read_json(mutation_file)
        if len(decoded.get("winners", [])) == 4 and not decoded.get("pending"):
            if decoded["runner_sha256"] != digest(decoder_file):
                raise ValueError("mutation decoder source differs from the complete metadata")
            for entry in decoded["winners"]:
                label = f"{entry['body']}_{entry['world']}"
                if entry["winner_raw_sha256"] != arms[label]["selection"]["winner_sha256"]:
                    raise ValueError("decoded mutation winner differs from frozen selection")
            for source, relative in ((mutation_file, "winner_mutations.json"),
                                     (decoder_file, "sources/decode_winner_mutations.py")):
                target = out / relative
                copy_file(source, target)
                paths.append(target)
        else:
            print("Mutation metadata incomplete: not copied to public artifacts.", flush=True)
    for name in ("benchmark.json", "audit.json", "budget_screens.json", "budget_followup.json",
                 "affinity_adjustment.json", "run_budgeted.py"):
        source = operational_file(study, name)
        if source.exists():
            dst = out / "operations" / name
            copy_file(source, dst)
            paths.append(dst)
    for name in ("taskvar_gradient.py", "taskvar_confirm.py"):
        archived = study / "sources" / name
        source = archived if archived.exists() else ROOT / "scripts" / name
        dst = out / "sources" / name
        copy_file(source, dst)
        paths.append(dst)
    analysis_source = Path(__file__)
    copy_file(analysis_source, out / "analyze.py")
    paths.append(out / "analyze.py")
    return {str(path.relative_to(out)): {"sha256": digest(path), "bytes": path.stat().st_size}
            for path in sorted(set(paths))}


def plot_results(arms, out):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    labels = list(arms)
    ys = np.arange(len(labels))
    fig, axes = plt.subplots(1, 2, figsize=(10, 3.8), sharey=True, layout="constrained")
    for ax, key, title in zip(axes, ("gain", "interaction"),
                              ("Fresh confirmation gain", "Additional gain removed by lateral lesion")):
        values = [summary(arms[label][key]) for label in labels]
        ax.errorbar([v["mean"] for v in values], ys, xerr=[3 * v["se"] for v in values],
                    fmt="o", capsize=4, color="#215a87")
        ax.axvline(0, color="0.5", linewidth=1)
        ax.set_title(title, fontsize=11)
        ax.set_xlabel("Paired ΔF (points and ±3 SE)")
        ax.set_yticks(ys, labels=[label.replace("_", " / ") for label in labels])
        ax.grid(axis="x", color="0.92")
    axes[0].axvline(.5, color="#ad7920", linestyle="--", linewidth=1, label="Practical threshold: +0.5 F")
    axes[0].legend(fontsize=8, loc="best")
    axes[0].invert_yaxis()
    fig.suptitle("One selected mutant per parent/world; independent paired evaluation", fontsize=12)
    fig.supxlabel("Lesion blocks in-plane spikes after t=256; morphogen exchange continues.", fontsize=9)
    for suffix in ("png", "svg"):
        path = out / f"confirmation_and_lateral.{suffix}"
        fig.savefig(path, dpi=180)
        if suffix == "svg":
            path.write_text("\n".join(line.rstrip() for line in path.read_text().splitlines()) + "\n")
    plt.close(fig)
    fig, axes = plt.subplots(1, 2, figsize=(8.5, 4.0), layout="constrained")
    for ax, body in zip(axes, (5, 7)):
        base, pool = arms[f"s{body}_base"], arms[f"s{body}_pool"]
        a = (base["screen"]["F"][1:] - base["screen"]["F"][0]).mean(axis=1)
        b = (pool["screen"]["F"][1:] - pool["screen"]["F"][0]).mean(axis=1)
        ax.scatter(a, b, s=17, alpha=.75, color="#215a87")
        low, high = min(a.min(), b.min()), max(a.max(), b.max())
        ax.plot([low, high], [low, high], color=".6", linestyle="--", linewidth=1)
        ax.axvline(0, color=".7", linewidth=.7)
        ax.axhline(0, color=".7", linewidth=.7)
        ax.set_title(f"s{body}: all 64 unchanged mutations")
        ax.set_xlabel("Base mean mutant − parent F")
        ax.set_ylabel("POOL mean mutant − parent F")
    fig.suptitle("Exploratory screen: 32 paired lives per mutant/world", fontsize=12)
    fig.savefig(out / "screen_cross_world.png", dpi=180)
    plt.close(fig)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--study", type=Path, default=DEFAULT_STUDY)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--export", action="store_true")
    args = parser.parse_args()
    pending = readiness(args.study)
    if pending:
        print(json.dumps({"status": "incomplete", "pending": pending}, indent=2))
        return
    arms = {f"s{body}_{world}": load_arm(args.study, body, world) for body, world in ARMS}
    identity = next(iter(arms.values()))["manifest"]["numerical_identity"]
    if any(arm["manifest"]["numerical_identity"] != identity for arm in arms.values()):
        raise ValueError("study arms have different numerical/source identities")
    cross = cross_world(arms)
    if not args.export:
        print(json.dumps({"status": "ready", "arms": list(arms), "out": str(args.out)}, indent=2))
        return
    args.out.mkdir(parents=True, exist_ok=True)
    # Reject unexpectedly large exports before any copy; planned arrays normally occupy a few MB.
    inputs = set()
    for arm in arms.values():
        inputs.add(arm["path"] / "scores.npz")
        inputs.update(arm["path"].glob("followup/*/scores.npz"))
    input_bytes = sum(path.stat().st_size for path in inputs)
    if input_bytes > 30_000_000:
        raise ValueError(f"unexpectedly large raw evidence: {input_bytes} bytes; review before exporting")
    artifacts = export_raw(arms, args.study, args.out)
    write_json(args.out / "cross_world_screen.json", cross)
    plot_results(arms, args.out)
    arm_reports = {label: arm_summary(arm) for label, arm in arms.items()}
    budgets = {phase: read_json(operational_file(args.study, f"budget_{phase}.json"))
               for phase in ("screens", "followup")
               if operational_file(args.study, f"budget_{phase}.json").exists()}
    record = {
        "study": "pool_mutants_20261013", "status": "complete bounded exploration", "report_only": True,
        "protocol": {"parents": ["s5", "s7"], "worlds": ["base", "pool"], "mutants_per_parent": 64,
                     "screen_lives": 32, "rescored_per_parent_world": 4, "rescore_lives": 512,
                     "confirmed_per_parent_world": 1, "confirm_lives": 512, "lesion_lives_per_arm": 256,
                     "seed_blocks": {"screen": 80, "rescore": 81, "confirm": 82, "lesion": 83},
                     "selection": "Same mutant pool across worlds; top ceil(5%) by screen mean, "
                                  "then best rescore mean.",
                     "ties": "Ascending original genome row", "duration": 1024},
        "arms": arm_reports,
        "confirmation_count": {"selected_winner_comparisons": 4,
                               "unique_winner_genotypes": len({arm["selection"]["winner_sha256"]
                                                                for arm in arms.values()}),
                               "positive_3se": sum(v["confirmation"]["positive_3se"] for v in arm_reports.values()),
                               "positive_3se_and_at_least_0p5": sum(v["confirmation"]["positive_3se"] and
                                   v["confirmation"]["gain_at_least_0p5"] for v in arm_reports.values())},
        "cross_world_screen": {"artifact": "cross_world_screen.json", "exploratory": True,
                               "note": "All 64 matched mutants per parent, including guarded and neutral ones."},
        "budgets": budgets, "raw_aggregate_bytes_before_export": input_bytes,
        "plots": ["confirmation_and_lateral.png", "confirmation_and_lateral.svg", "screen_cross_world.png"],
        "limitations": [
            "64 mutants x 32 screen lives is bounded exploration, not completion of preregistered 256 x 64 G2.",
            "Four selected candidates per arm were rescored; one per arm was independently confirmed. "
            "These rates concern selected mutants and do not estimate an unbiased fitness-effect distribution.",
            "The parents evolved under slower conduction. Gains may partly adapt to faster signaling; "
            "only the sensory world differs between these two arms.",
            "Four parent/world comparisons can select the same genotype more than once; "
            "the summary separately counts unique winners.",
            "Two parents and one generation of mutation do not establish long-term evolutionary accessibility.",
            "Only T=1024 was confirmed; gains under the production mixture of T=768,1024,1536 remain unmeasured.",
            "A lateral interaction can show added dependence on in-plane spikes after t=256; "
            "morphogen exchange continues. This does not identify routing, a new algorithm, "
            "or effects limited to adults.",
            "The lateral lesion can change later development. Whole-life accounting includes the shared prefix.",
            "The share of the information gap captured at a matched footprint was not measured. "
            "No hand-body victory criterion was measured; this study does not admit or reject worlds.",
        ],
    }
    write_json(args.out / "summary.json", record)
    write_json(args.out / "provenance.json", {"numerical_identity": identity, "artifacts": artifacts,
                                             "analysis_sha256": digest(Path(__file__))})
    total_bytes = sum(path.stat().st_size for path in args.out.rglob("*") if path.is_file())
    print(json.dumps({"status": "exported", "out": str(args.out), "total_bytes": total_bytes,
                      "confirmation_count": record["confirmation_count"]}, indent=2))


if __name__ == "__main__":
    main()
