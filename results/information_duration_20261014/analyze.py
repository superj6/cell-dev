"""Independent completed-data audit of N; NumPy and source text only, never simulate."""
from __future__ import annotations

import argparse
import ast
import hashlib
import importlib.util
import json
import os
import re
import shutil
import sys
from pathlib import Path

import numpy as np

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
ROOT = next((p for p in HERE.parents if (p / "src/life/spec.py").exists()), None)
PROTOCOL_SHA = "43453144aa4239ff8ac00321af630f1a11d98e571db45f4d4622b9902d69e6d1"
HELPER_SHA = "a30ea457314de89f0403e511338d1c61d4190f741578dc541ef2ac5cdff0cb34"
NAMES = ("full", "frozen", "retuned", "smaller_frozen", "smaller_transferred", "quieter")
WORLDS, DURATIONS = ("base", "pool"), (768, 1536)
READY_FILES = {"protocol.json", "prepare.py", "measure.py", "validate.py", "run_budgeted.py",
               "test_prepared.py", "test_validation.py", "PREREG.md"}
DEPENDENCY = "outputs/autonomous_s7_20261014"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


if sha(HERE / "F_offline.py") != HELPER_SHA:
    raise ValueError("reviewed independent F accounting helper differs")
loader = importlib.util.spec_from_file_location("N_independent_F", HERE / "F_offline.py")
F = importlib.util.module_from_spec(loader)
loader.loader.exec_module(F)
read, save, equal, identical, stats, L = F.read, F.save, F.equal, F.identical, F.stats, F.L


def arrays(path):
    with np.load(path, allow_pickle=False) as saved:
        return {name: saved[name].copy() for name in saved.files}


def operation(base, name):
    archived = base / "operations" / name
    return archived if archived.exists() else base / name


def source(base, relative):
    archived = base / "archive_sources" / relative
    if archived.exists():
        return archived
    if ROOT is None:
        raise ValueError("missing archived numerical source: " + relative)
    return ROOT / relative


def compare_record(actual, expected, label):
    """Require identical structure/counts, with tight tolerance only for computed floating statistics."""
    if isinstance(expected, dict):
        equal(set(actual), set(expected), label + " keys")
        for key, value in expected.items():
            compare_record(actual[key], value, label + "/" + key)
    elif isinstance(expected, float):
        if not np.isfinite(actual) or not np.isclose(actual, expected, rtol=1e-12, atol=1e-12):
            raise ValueError(label + " statistic differs")
    else:
        equal(actual, expected, label)


def validate_ledger(ledger, world, count):
    if ledger.dtype != np.float64 or ledger.shape != (count, 57) or not np.isfinite(ledger).all():
        raise ValueError("invalid finite full ledger")
    status = ledger[:, L["status"]]
    if np.any(status != status.astype(np.int64)) or np.any(status < 0):
        raise ValueError("invalid status encoding")
    if np.any(status.astype(np.int64) & (2 | 4 | 64 | 128)):
        raise ValueError("guarded or invalid life cannot be scored")
    alive = (status.astype(np.int64) & 1) == 0
    if np.any(alive & (ledger[:, L["t_end"]] != world["t0"] + world["T"])):
        raise ValueError("unexplained incomplete life")
    income = world["R_cap"] * ledger[:, L["captures"]]
    cost = F.costs(ledger, world)
    if not identical(income, ledger[:, L["income"]]):
        raise ValueError("capture income bytes differ")
    if not np.allclose(cost, ledger[:, L["cost"]], rtol=1e-9, atol=1e-9):
        raise ValueError("full-ledger cost accounting differs")
    if np.any(ledger[:, L["guard_charge"]] != 0):
        raise ValueError("nonzero guard charge")
    net = income - cost
    if not identical(net, ledger[:, L["net"]]):
        raise ValueError("independent raw net accounting bytes differ")
    fitness = net / (world["T"] - world["t_open"])
    if not identical(fitness, ledger[:, L["F"]]):
        raise ValueError("independent raw fitness bytes differ")
    return {"extinct": int(np.count_nonzero(status.astype(np.int64) & 1)),
            "guarded": 0, "invalid": 0, "other_valid_status": int(np.count_nonzero(status.astype(np.int64) & ~1))}


def generated_text(base):
    """Isolate the pinned text generator without importing its build functions."""
    path = source(base, "results/open_headroom/harness/make_ckernel.py")
    tree = ast.parse(path.read_text())
    node = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "patched_source")
    env = {"os": os, "HERE": "/CELLDEV/results/open_headroom/harness",
           "SRC": str(source(base, "src/life/kernel.c"))}
    exec(compile(ast.Module(body=[node], type_ignores=[]), str(path), "exec"), env)
    text = env["patched_source"](["/CELLDEV/sources/vctl.c"])
    old = "  c->e_on = w[W_TAUR]; c->e_off = w[W_TAUE];"
    equal(text.count(old), 1, "ABI3 epoch adapter target")
    return text.replace(old, "  c->e_on = 0.0; c->e_off = 0.0; // E7 uses ABI 3 blob physics")


def normalize_source(text):
    text = re.sub(r'#include "[^"\n]*/(results/open_headroom/harness/[^"\n]+)"',
                  r'#include "/CELLDEV/\1"', text)
    return re.sub(r'#include "[^"\n]*/vctl\.c"', '#include "/CELLDEV/sources/vctl.c"', text)


def audit_inputs(base):
    equal(sha(base / "protocol.json"), PROTOCOL_SHA, "fixed preregistered N protocol")
    protocol = read(base / "protocol.json")
    equal((protocol["candidate_lives"], protocol["validation_lives"], protocol["simulation_workers"],
           protocol["max_cpu_seconds"]), (12288, 40, 2, 3600), "registered scope")
    equal(protocol["wait_for_studies"], [DEPENDENCY], "L-only dependency")
    for relative, digest in protocol["source_pins"].items():
        equal(sha(source(base, relative)), digest, "numerical source " + relative)
    for relative, digest in protocol["input_sha256"].items():
        equal(sha(base / relative), digest, "recovered input " + relative)
    ready = read(operation(base, "ready.json"))
    equal(set(ready["files"]), READY_FILES, "readiness pin set")
    for name, digest in ready["files"].items():
        equal(sha(base / name), digest, "released file " + name)
    equal(ready["dependencies"], protocol["dependencies"], "release dependency pins")
    dependency = base / "dependencies/L"
    if not dependency.exists():
        if ROOT is None:
            raise ValueError("missing completed L dependency receipt")
        dependency = ROOT / DEPENDENCY
    for name, digest in protocol["dependencies"][DEPENDENCY].items():
        equal(sha(dependency / name), digest, "dependency " + name)
    completed = read(dependency / "budget.json")
    equal(completed["status"], "complete", "L completion")
    if completed.get("running") or completed.get("queued"):
        raise ValueError("L still records active or queued work")
    manifest = read(base / "measurement/manifest.json")
    equal(manifest["protocol_sha256"], sha(base / "protocol.json"), "manifest protocol")
    equal(manifest["ready"], ready, "manifest release")
    for key in ("worlds", "candidates", "seeds"):
        equal(manifest[key], protocol[key], "manifest " + key)
    equal(set(manifest["libraries"]), {"research.c", "research.so", "validation/replay.c", "validation/replay.so"},
          "generated library artifact set")
    for name, digest in manifest["libraries"].items():
        equal(sha(base / "measurement" / name), digest, "compiled artifact " + name)
    expected = generated_text(base)
    for name in ("research.c", "validation/replay.c"):
        equal(normalize_source((base / "measurement" / name).read_text()), expected, "generated C " + name)
    equal(manifest["validation_sha256"], sha(base / "measurement/validation/report.json"), "validation report bytes")
    return protocol, ready, manifest


def validation_audit(base, protocol):
    folder = base / "measurement/validation"
    report = read(folder / "report.json")
    equal((report["passed"], report["candidate_lives"], report["T"]), (True, 40, 64), "validation scope")
    equal(report["library_sha256"], sha(folder / "replay.so"), "validation library")
    equal(report["source_sha256"], sha(folder / "replay.c"), "validation source")
    records = {r["tag"]: r for r in report["records"]}
    equal(len(records), len(report["records"]), "unique validation tags")
    loaded, counted, checks = {}, 0, {}

    def get(tag, count, world):
        nonlocal counted
        if tag in loaded:
            raise ValueError("validation tag reused")
        record = records[tag]
        equal(record["lives"], count, tag + " count")
        equal(sha(folder / (tag + ".npz")), record["sha256"], tag + " bytes")
        row = arrays(folder / (tag + ".npz"))
        validate_ledger(row["ledger"], world, count)
        if row["hashes"].shape != (count, 5) or row["hashes"].dtype != np.uint64:
            raise ValueError("invalid validation hashes")
        if row["diag"].shape[0] != count or not np.isfinite(row["diag"]).all():
            raise ValueError("invalid validation diagnostics")
        loaded[tag] = row
        counted += count
        return row

    def check_log(row, replay=False):
        pings, actions = row["pings"], row["actions"]
        if (pings.dtype != np.float64 or actions.dtype != np.float64 or pings.ndim != 2
                or pings.shape[1] != 2 or not len(pings) or actions.ndim != 2 or actions.shape[1] != 6
                or not len(actions) or not np.isfinite(pings).all() or not np.isfinite(actions).all()):
            raise ValueError("empty or invalid retained controller ping/action log")
        if 6 * (len(pings) + len(actions)) > 1 << 20:
            raise ValueError("reconstructed controller log exceeds the registered capacity")
        if row["diag"].shape != (1, 16):
            raise ValueError("invalid logged controller diagnostic dimensions")
        if row["diag"][0, 0] != (0 if replay else len(pings)):
            raise ValueError("raw log ping count differs from controller diagnostics")
        kinds = actions[:, 0]
        if not np.isin(kinds, (1., 2., 3.)).all():
            raise ValueError("unknown retained controller action record kind")
        steering = np.flatnonzero(kinds == 2)
        detail = np.flatnonzero(kinds == 3)
        if not np.array_equal(steering + 1, detail):
            raise ValueError("steering action/detail records are truncated or mismatched")
        returned, deltas = actions[steering, 5], actions[detail, 4]
        if (not np.array_equal(returned, deltas) or np.any(deltas < 0)
                or np.any(deltas != np.floor(deltas))):
            raise ValueError("steering returned counts differ from accepted-action deltas")
        accepted = float(np.count_nonzero((kinds == 1) & (actions[:, 5] >= 0)))
        accepted += float(deltas.sum())
        if accepted != row["diag"][0, 2]:
            raise ValueError("raw log accepted-action count differs from controller diagnostics")
        return pings, actions

    for name in WORLDS:
        world = dict(protocol["worlds"][name]["768"], T=64)
        controller = []
        for i in (0, 1):
            tag = f"{name}_{i}_"
            builtin, closed = get(tag + "builtin", 1, world), get(tag + "closed", 1, world)
            if not all(identical(builtin[k], closed[k]) for k in ("ledger", "hashes")):
                raise ValueError("validation builtin/copy differs")
            if not identical(builtin["diag"][:, :12], closed["diag"][:, :12]):
                raise ValueError("validation copy diagnostics differ")
            pings, actions = check_log(closed)
            replay_checks = {}
            for variant in ("same_life", "other_life", "other_world"):
                # The alien replay changes motion/halo/rates and receptor flags, not T or accounting prices.
                row = get(tag + variant, 1, world)
                replay_pings, _ = check_log(row, replay=True)
                if not identical(pings, replay_pings):
                    raise ValueError("validation injected ping bytes differ")
                if not identical(actions, row["actions"]) or row["diag"][0, 0] != 0:
                    raise ValueError("validation replay action bytes or receptor count differ")
                replay_checks[variant] = True
            control = get(tag + "control", 1, world)
            check_log(control)
            if identical(actions, control["actions"]):
                raise ValueError("validation closed-loop control did not differ")
            controller.append({"seed": protocol["validation"]["seeds"][i], "copy_bitwise": True,
                               "replay": replay_checks, "control_differs": True,
                               "pings": len(pings), "action_records": len(actions)})
        scratch, production = get(name + "_scratch_reflex", 2, world), get(name + "_production_reflex", 2, world)
        columns = [i for i in range(57) if i not in (21, 22)]
        if (not identical(scratch["ledger"][:, columns], production["ledger"][:, columns])
                or not identical(scratch["hashes"][:, 1:], production["hashes"][:, 1:])):
            raise ValueError("validation production/scratch parity differs")
        null, inert = get(name + "_null", 2, world), get(name + "_inert", 2, world)
        if not identical(null["hashes"][:, 4], inert["hashes"][:, 4]):
            raise ValueError("validation null/inert world hash differs")
        for key in ("rec_cand", "rec_accept", "respawns", "dist_sum", "zone_samples", "n_end"):
            if not identical(null["ledger"][:, L[key]], inert["ledger"][:, L[key]]):
                raise ValueError("validation null/inert column differs: " + key)
        checks[name] = {"controller_replay": controller, "reflex_production_parity": True,
                        "null_inert_world_parity": True, "excluded_ledger_columns": [21, 22], "excluded_hash": "all"}
    equal(set(loaded), set(records), "all validation records retained")
    equal({p.stem for p in folder.glob("*.npz")}, set(records), "validation file set")
    equal(counted, 40, "independent validation life count")
    equal(report["checks"], checks, "recomputed bounded validation checks")
    return {"lives": counted, "raw_records": len(loaded), "copy_comparisons": 4,
            "replay_comparisons": 12, "world_parity_pairs": 4,
            "per_life_ping_and_accepted_action_diagnostics_checked": True,
            "reconstructed_log_capacity_doubles": 1 << 20,
            "original_log_return_count_or_allocator_failure_flag_saved": False,
            "other_world_accounting": "Registered replay alterations preserve T and every accounting price."}


def load_rows(base, protocol, manifest):
    rows, health = {}, {}
    for duration in DURATIONS:
        for name in WORLDS:
            key = f"{name}_T{duration}"
            rows[key], health[key] = {}, {}
            world = protocol["worlds"][name][str(duration)]
            equal([c["name"] for c in protocol["candidates"][name]], list(NAMES), "fixed candidate order")
            for candidate in protocol["candidates"][name]:
                label = candidate["name"]
                folder = base / "measurement/rows" / key / label
                identity = {"manifest": manifest, "condition": [name, duration], "candidate": candidate,
                            "seeds": protocol["seeds"][str(duration)]}
                equal(read(folder / "checkpoint.json"),
                      {"identity": identity, "row_sha256": sha(folder / "row.npz")}, key + "/" + label + " checkpoint")
                row = arrays(folder / "row.npz")
                equal(json.loads(str(row["identity"].item())), identity, "raw row identity")
                health[key][label] = validate_ledger(row["ledger"], world, 512)
                if (row["hashes"].dtype != np.uint64 or row["hashes"].shape != (512, 5)
                        or np.any(row["hashes"] != F.HASH_INIT)):
                    raise ValueError("fast hash initializer differs")
                controller = label == "full"
                if row["diag"].shape != (512, 16 if controller else 0) or not np.isfinite(row["diag"]).all():
                    raise ValueError("raw controller diagnostics differ")
                if controller:
                    if row["latency"].shape != (512,) or np.any(row["latency"] != world["d0"]):
                        raise ValueError("registered controller latency differs")
                elif row["latency"].size:
                    raise ValueError("unexpected tissue latency")
                for timing in ("cpu_seconds", "wall_seconds"):
                    if not np.isfinite(float(row[timing])) or float(row[timing]) < 0:
                        raise ValueError("invalid row timing")
                rows[key][label] = row
    files = list((base / "measurement/rows").rglob("row.npz"))
    equal(len(files), 24, "raw research row count")
    if list((base / "measurement/rows").rglob("*.pending")):
        raise ValueError("uncommitted research row remains")
    return rows, health


def condition(rows, world):
    reference = max(("frozen", "retuned"), key=lambda n: rows[n]["ledger"][:, L["F"]].mean())
    less = max(NAMES[3:], key=lambda n: rows[n]["ledger"][:, L["F"]].mean())
    comparisons, smaller, vectors = {}, {}, {}
    for name in NAMES[1:]:
        label = "full_minus_" + name
        comparisons[label], pieces = F.contrast(rows["full"], rows[name], world)
        vectors[label] = rows["full"]["ledger"][:, L["F"]] - rows[name]["ledger"][:, L["F"]]
        vectors.update({label + "__" + key: value for key, value in pieces.items()})
    for name in NAMES[3:]:
        smaller[name], pieces = F.contrast(rows[name], rows[reference], world)
        label = name + "_minus_best_reflex"
        vectors[label] = rows[name]["ledger"][:, L["F"]] - rows[reference]["ledger"][:, L["F"]]
        vectors.update({label + "__" + key: value for key, value in pieces.items()})
    gap, cheap = comparisons["full_minus_" + reference]["F"], smaller[less]["F"]
    report = {"fixed_comparisons": comparisons, "do_less_comparisons": smaller,
              "best_whole_reflex": reference, "best_whole_do_less": less,
              "candidate_means": {name: stats(row["ledger"][:, L["F"]]) for name, row in rows.items()},
              "descriptive_checks": {"gap_above_3se": gap["mean"] > 3 * gap["se"],
                                     "gap_at_least_1": gap["mean"] >= 1.,
                                     "do_less_below_quarter_gap": cheap["mean"] < .25 * gap["mean"]}}
    return report, vectors


def analyze(base):
    base = Path(base).resolve()
    budget_file = operation(base, "budget.json")
    if not budget_file.exists() or read(budget_file).get("status") != "complete":
        return {"status": "incomplete", "analysis_simulated_lives": 0}, {}
    budget = read(budget_file)
    if budget.get("running") or budget.get("queued"):
        raise ValueError("completed study still records active or queued work")
    if budget["cap_cpu_seconds"] != 3600 or not 0 < budget["cpu_seconds"] < 3600 or budget["exit_code"] != 0:
        raise ValueError("completed monitor resource/exit record differs")
    protocol, ready, manifest = audit_inputs(base)
    equal(budget["ready"], ready, "monitor release")
    bounded = validation_audit(base, protocol)
    rows, health = load_rows(base, protocol, manifest)
    report = read(base / "measurement/report.json")
    for key, expected in {"status": "complete", "candidate_lives": 12288,
                          "completed_candidate_lives": 12288, "validation_lives": 40}.items():
        equal(report[key], expected, "worker " + key)
    equal(report["limitations"], protocol["limitations"], "worker limitations")
    conditions, vectors, ledger_means = {}, {}, {}
    for duration in DURATIONS:
        vectors[f"seeds_T{duration}"] = np.asarray(protocol["seeds"][str(duration)], dtype=np.uint64)
        for world in WORLDS:
            key = f"{world}_T{duration}"
            conditions[key], contrasts = condition(rows[key], protocol["worlds"][world][str(duration)])
            vectors.update({key + "__" + name: value for name, value in contrasts.items()})
            ledger_means[key] = {name: {field: stats(row["ledger"][:, L[field]]) for field in F.LEDGER}
                                 for name, row in rows[key].items()}
    compare_record(report["conditions"], conditions, "worker contrasts")
    order = [f"{world}_T{duration}/{name}" for duration in DURATIONS for world in WORLDS for name in NAMES]
    equal(read(base / "measurement/progress.json"),
          {"status": "complete", "completed_rows": order, "completed_candidate_lives": 12288}, "completed row order")
    row_cpu = sum(float(row["cpu_seconds"]) for group in rows.values() for row in group.values())
    if row_cpu > budget["cpu_seconds"] + .001:
        raise ValueError("row CPU exceeds cumulative monitored CPU")
    summary = {"status": "complete", "research_candidate_lives": 12288, "bounded_validation_lives": 40,
               "budget": {"monitored_cpu_seconds": budget["cpu_seconds"], "row_cpu_seconds": row_cpu,
                          "cap_cpu_seconds": 3600, "workers": 2},
               "conditions": conditions, "candidate_full_ledger_means": ledger_means, "life_health": health,
               "audit": {"raw_research_rows": 24, "ledger_columns": 57, "reconstructed_fitness_bitwise": True,
                         "source_generation_reconstructed": True, "validation": bounded,
                         "analysis_simulated_lives": 0},
               "limitations": protocol["limitations"] + [
                   "Fast research event hashes remain HASH_INIT; file hashes bind data bytes, not a full replay.",
                   "Bounded T64 validation is evidence for these exact cases, not a universal parity proof.",
                   "Raw replay files do not separately retain the logger return count or allocator-failure flag. "
                   "The pinned worker enforces returned-count bounds; offline checks enforce saved record bounds, "
                   "declared counts, ping diagnostics, accepted-action diagnostics and stream identity."]}
    return summary, vectors


def markdown(summary):
    lines = ["# N: fixed information payoff at two durations", "",
             "The unchanged default C4 controller and five fixed reflex references were measured on 512 shared",
             "seeds per world and duration. No controller tuning or organism change was involved.", "",
             "| World/duration | C4 − frozen reflex | C4 − retained retuned reflex |",
             "| --- | ---: | ---: |"]
    for label, report in summary["conditions"].items():
        values = [report["fixed_comparisons"]["full_minus_" + name]["F"] for name in ("frozen", "retuned")]
        lines.append("| " + label + " | " + " | ".join(f"{r['mean']:+.3f} ± {r['se']:.3f}" for r in values) + " |")
    lines += ["", "Values are mean paired F difference ± one SE; every fixed comparison and sign is retained.",
              "The original headline d0=0.5/d_min=0.25 worlds are retained; only duration changes.",
              "The four cells are separate comparisons. Distinct duration seed blocks do not support paired "
              "duration claims.",
              "", f"Research lives: 12,288; bounded validation lives: 40; monitored CPU: "
              f"{summary['budget']['monitored_cpu_seconds']:.3f} / 3,600 seconds.",
              "", "See `summary.json` for all 57-column means, all fixed contrasts, cost decomposition "
              "and limitations.",
              "`PREREG.md` and `prelaunch/` preserve the prospective design. This is an external information-payoff",
              "measurement, not a world-admission decision or a claim about evolved capability.", "",
              "```sh", ".venv/bin/python results/information_duration_20261014/analyze.py "
              "--study results/information_duration_20261014 --check", "```", ""]
    return "\n".join(lines)


def artifact_map(base):
    return {str(p.relative_to(base)): {"sha256": sha(p), "bytes": p.stat().st_size}
            for p in sorted(base.rglob("*")) if p.is_file() and p != base / "provenance.json"
            and "__pycache__" not in p.parts}


def check_archive(base, summary, vectors):
    base = Path(base)
    provenance = read(base / "provenance.json")
    equal(provenance["status"], "complete", "final provenance status")
    equal(provenance["artifacts"], artifact_map(base), "complete artifact hashes and sizes")
    equal(summary, read(base / "summary.json"), "stored independent summary")
    equal((base / "README.md").read_text(), markdown(summary), "reproduced README")
    saved = arrays(base / "independent_contrasts.npz")
    equal(set(saved), set(vectors), "stored contrast set")
    if any(not identical(saved[key], vectors[key]) for key in vectors):
        raise ValueError("stored independent contrast bytes differ")


def export(base, target, summary, vectors):
    base, target = Path(base).resolve(), Path(target).resolve()
    if base == target:
        raise ValueError("completed-data export requires a separate public preparation")
    equal(summary["status"], "complete", "export completion")
    prior = read(target / "provenance.json")
    equal(prior["status"], "prospective_preparation_not_released", "preserved preparation status")
    for name, record in prior["artifacts"].items():
        equal(sha(target / name), record["sha256"], "prelaunch artifact " + name)
        equal((target / name).stat().st_size, record["bytes"], "prelaunch artifact size " + name)
    prelaunch = target / "prelaunch"
    if prelaunch.exists():
        raise ValueError("export prelaunch archive already exists; inspect rather than reset")
    for name in (*prior["artifacts"], "provenance.json"):
        destination = prelaunch / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(target / name, destination)
    for name in ("analyze.py", "F_offline.py", "test_analyze.py"):
        shutil.copy2(HERE / name, target / name)
    shutil.copytree(base / "measurement", target / "measurement")
    (target / "operations").mkdir()
    for name in ("ready.json", "budget.json", "run.log"):
        if operation(base, name).exists():
            shutil.copy2(operation(base, name), target / "operations" / name)
    dep = target / "dependencies/L"
    dep.mkdir(parents=True)
    original = base / "dependencies/L"
    if not original.exists():
        original = ROOT / DEPENDENCY
    for name in ("protocol.json", "run_budgeted.py", "budget.json"):
        shutil.copy2(original / name, dep / name)
    save(target / "summary.json", summary)
    np.savez_compressed(target / "independent_contrasts.npz", **vectors)
    (target / "README.md").write_text(markdown(summary))
    repeated, rebuilt = analyze(target)
    equal(repeated, summary, "copied archive summary")
    equal(set(rebuilt), set(vectors), "copied contrast set")
    if any(not identical(vectors[key], rebuilt[key]) for key in vectors):
        raise ValueError("copied archive contrast bytes differ")
    save(target / "provenance.json", {"status": "complete", "source_study": str(base),
                                       "analysis_simulated_lives": 0, "artifacts": artifact_map(target)})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--study", type=Path, default=HERE)
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--export", type=Path)
    args = parser.parse_args()
    summary, vectors = analyze(args.study)
    if args.check and summary["status"] == "complete":
        check_archive(args.study, summary, vectors)
    if args.export:
        export(args.study, args.export, summary, vectors)
    print(json.dumps({key: summary[key] for key in ("status", "research_candidate_lives", "audit") if key in summary},
                     indent=2))


if __name__ == "__main__":
    main()
