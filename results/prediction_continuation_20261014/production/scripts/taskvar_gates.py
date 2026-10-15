"""Offline E7 admission checks. No simulation, selection or world changes.

Input JSON has one shared ``seeds`` list, ``tuning_seeds`` and ``runs``. Each run
has ``kind``, ``footprint`` and per-life ``F``. Reflex kinds are ``frozen_reflex``
and ``retuned_reflex``; controllers use ``information`` and ``ablation``;
quieter/smaller reflexes use ``do_less``. See results/taskvar/README.md.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np


def validate_lives(result, world, *, allow_guards: bool = False) -> None:
    """Allow genome death; optionally retain compute guards in mutant screens."""
    from src.life import spec

    status = result["status"].astype(np.int64)
    guards = spec.STATUS["guard_cells"] | spec.STATUS["guard_events"]
    invalid = spec.STATUS["capacity"] | spec.STATUS["ledger_mismatch"] | (0 if allow_guards else guards)
    if np.any(status & invalid):
        raise ValueError("life hit a compute guard, capacity limit or ledger mismatch")
    ended = (status & (spec.STATUS["extinct"] | (guards if allow_guards else 0))) != 0
    if not np.isfinite(result.ledger).all() or np.any(~ended & (result["t_end"] != world.t0 + world.T)):
        raise ValueError("life was incomplete or contains non-finite ledger entries")


def paired(a, b) -> dict:
    a, b = np.asarray(a, dtype=float), np.asarray(b, dtype=float)
    if a.ndim != 1 or a.shape != b.shape or len(a) < 2:
        raise ValueError("paired scores must have matching one-dimensional shapes and at least two lives")
    if not np.all(np.isfinite(a)) or not np.all(np.isfinite(b)):
        raise ValueError("scores must be finite")
    d = a - b
    return {"mean": float(d.mean()), "se": float(d.std(ddof=1) / np.sqrt(len(d))), "n": len(d)}


def clears_bar(d: dict) -> bool:
    return d["mean"] >= 1.0 and d["mean"] > 3.0 * d["se"]


def admission(record: dict) -> dict:
    """Apply plan 0.4, conservatively marking missing evidence incomplete.

    Select a whole reflex by its mean on fresh lives, never a different reflex
    per life. A privileged ceiling and hand-built tissue scores cannot admit
    a world. Leakage metadata records a separate replay audit, not an inference
    from a large fitness gain.
    """
    seeds = record["seeds"]
    if len(seeds) < 2 or len(seeds) != len(set(seeds)):
        raise ValueError("scoring seeds must contain at least two distinct lives with no duplicates")
    tuning = record.get("tuning_seeds", [])
    if set(tuning) & set(seeds):
        raise ValueError("tuning and scoring lives overlap")
    runs = record["runs"]
    from src.life import spec

    for name, run in runs.items():
        if len(run["F"]) != len(seeds):
            raise ValueError(f"{name}: one score per shared seed is required")
        paired(run["F"], run["F"])
        if "status" in run:
            status = np.asarray(run["status"])
            if status.shape != (len(seeds),) or not np.isfinite(status).all():
                raise ValueError(f"{name}: invalid status array")
            invalid = sum(spec.STATUS[key] for key in ("guard_cells", "guard_events", "capacity", "ledger_mismatch"))
            if np.any(status.astype(np.int64) & invalid):
                raise ValueError(f"{name}: invalid or guarded scoring lives")
            if "t_end" in run:
                end = np.asarray(run["t_end"])
                if end.shape != status.shape or not np.isfinite(end).all():
                    raise ValueError(f"{name}: invalid end times")
                alive = (status.astype(np.int64) & spec.STATUS["extinct"]) == 0
                if np.any(alive & (end != record.get("t0", 0) + record["T"])):
                    raise ValueError(f"{name}: incomplete scoring lives")
    missing = []
    if len(seeds) < 512:
        missing.append("at least 512 fresh paired lives")
    if not tuning:
        missing.append("recorded tuning seeds")
    if record.get("engine") == "scratch controller harness":
        parity = record.get("world_parity_audit") or {}
        if not (parity.get("passed") is True and parity.get("artifact")):
            missing.append("scratch-world parity audit")
    fp = record["reflex_footprint"]
    refs = {n: r for n, r in runs.items()
            if r["kind"] in ("frozen_reflex", "retuned_reflex") and r["footprint"] == fp}
    for kind in ("frozen_reflex", "retuned_reflex"):
        if not any(r["kind"] == kind for r in refs.values()):
            missing.append(kind)
    infos = {n: r for n, r in runs.items() if r["kind"] == "information" and r["footprint"] == fp
             and r.get("privileged") is False}
    quiet = {n: r for n, r in runs.items() if r["kind"] == "do_less"}
    if not infos:
        missing.append("information controller at reflex footprint with privileged=false")
    if not quiet:
        missing.append("quieter or smaller reflex scores")
    report = {"world": record["world"], "T": record["T"], "n": len(seeds), "missing": missing,
              "verdict": "incomplete", "checks": {}}
    if not refs or not infos:
        return report
    best_ref = max(refs, key=lambda n: np.mean(refs[n]["F"]))
    best_info = max(infos, key=lambda n: np.mean(infos[n]["F"]))
    ref, info = runs[best_ref], runs[best_info]
    leak = info.get("replay_audit") or {}
    if not (leak.get("passed") is True and leak.get("artifact") and info.get("source_sha256")
            and leak.get("source_sha256") == info.get("source_sha256")):
        missing.append("controller replay audit with artifact and source hash")
    if record.get("engine") == "scratch controller harness" and (
            not record.get("harness_identity") or leak.get("harness_identity") != record["harness_identity"]):
        missing.append("replay audit bound to the scored harness/kernel/adapter sources")
    gap = paired(info["F"], ref["F"])
    report.update(best_reflex=best_ref, information_controller=best_info, information_gap=gap)
    report["checks"]["information_gap"] = clears_bar(gap)
    if quiet:
        best_quiet = max(quiet, key=lambda n: np.mean(quiet[n]["F"]))
        do_less = paired(quiet[best_quiet]["F"], ref["F"])
        report.update(best_do_less=best_quiet, do_less_gap=do_less)
        report["checks"]["do_less"] = do_less["mean"] < gap["mean"] / 4.0
    if record.get("capability"):
        capability_name = record.get("capability_controller", best_info)
        capability = runs.get(capability_name, {})
        if capability.get("kind") != "information" or capability.get("privileged") is not False:
            missing.append("valid information controller for the specific capability")
            return report
        audit = capability.get("replay_audit") or {}
        if not (audit.get("passed") is True and audit.get("artifact") and capability.get("source_sha256")
                and audit.get("source_sha256") == capability["source_sha256"]):
            missing.append("replay audit of the capability controller")
        if record.get("engine") == "scratch controller harness" and (
                audit.get("harness_identity") != record.get("harness_identity")):
            missing.append("capability replay audit bound to the scored harness sources")
        ablations = {n: r for n, r in runs.items() if r["kind"] == "ablation"
                     and r["footprint"] == capability["footprint"]
                     and r.get("ablation_of") == capability_name and r.get("privileged") is False
                     and r.get("mechanism") == record["capability"]}
        if not ablations:
            missing.append("matched capability ablation at the information controller footprint")
        else:
            best_abl = max(ablations, key=lambda n: np.mean(ablations[n]["F"]))
            ablation = runs[best_abl]
            if ablation.get("source_sha256") != capability.get("source_sha256"):
                missing.append("ablation and full controller must use the same source")
            full_params, ablated_params = capability.get("params"), ablation.get("params")
            changed = ablation.get("disabled_parameters", [])
            if full_params is None or ablated_params is None or len(full_params) != len(ablated_params):
                missing.append("matched full and ablated parameter vectors")
            elif any(a != b and i not in changed for i, (a, b) in enumerate(zip(full_params, ablated_params))):
                missing.append("ablation changes parameters outside its named mechanism")
            specific = paired(capability["F"], ablation["F"])
            report.update(capability_controller=capability_name, ablation=best_abl, ablation_gap=specific)
            if runs[best_abl].get("isolates_capability") is not True:
                missing.append("ablation isolating the named capability")
            else:
                report["specific_part"] = specific
                report["checks"]["specific_part"] = clears_bar(specific)
    if not missing:
        report["verdict"] = "pass" if all(report["checks"].values()) else "fail"
    return report


def duration_gate(reports: list[dict], worlds: list[str]) -> dict:
    """G5 rechecks each named world's admission at both unmeasured durations."""
    rows = {}
    for report in reports:
        key = (report["world"], float(report["T"]))
        if key in rows:
            raise ValueError(f"duplicate world/duration result: {key}")
        rows[key] = report
    checks = {f"{w}@{t}": rows.get((w, t), {}).get("verdict", "incomplete")
              for w in worlds for t in (768, 1536)}
    verdict = "incomplete" if not checks or "incomplete" in checks.values() else (
        "pass" if all(v == "pass" for v in checks.values()) else "fail")
    return {"gate": "G5", "verdict": verdict, "checks": checks}


def gradient_report(data: dict) -> dict:
    """Report the sampled mutant fraction, not a gate or a causal explanation.

    Arrays are [parent + mutants, paired lives]. Confirmation on fresh lives is
    required before naming a screen winner; small screens have low power.
    """
    fitness = np.asarray(data["F"], dtype=float)
    if fitness.ndim != 2 or min(fitness.shape) < 2:
        raise ValueError("gradient F needs a parent, mutants and at least two paired lives")
    for key in ("n_end", "clicks", "captures"):
        if np.asarray(data[key]).shape != fitness.shape or not np.isfinite(data[key]).all():
            raise ValueError(f"gradient {key} must be finite and match F")
    guard_fraction = None
    if "status" in data:
        from src.life import spec

        status = np.asarray(data["status"])
        if status.shape != fitness.shape or not np.isfinite(status).all():
            raise ValueError("gradient status must be finite and match F")
        status = status.astype(np.int64)
        if np.any(status & (spec.STATUS["capacity"] | spec.STATUS["ledger_mismatch"])):
            raise ValueError("gradient contains a capacity failure or ledger mismatch")
        guards = (status[1:] & (spec.STATUS["guard_cells"] | spec.STATUS["guard_events"])) != 0
        guard_fraction = float(guards.mean())
    rows = []
    for i in range(1, len(fitness)):
        delta = paired(fitness[i], fitness[0])
        row = {"mutant": i - 1, "fitness": delta, "beneficial": delta["mean"] > 2 * delta["se"]}
        for key in ("n_end", "clicks", "captures"):
            row[key] = paired(data[key][i], data[key][0])
        row["shrinks"] = row["n_end"]["mean"] < 0
        row["clicks_less"] = row["clicks"]["mean"] < 0
        rows.append(row)
    return {"report_only": True, "mutants": len(rows), "lives": fitness.shape[1],
            "beneficial_fraction": sum(r["beneficial"] for r in rows) / len(rows), "rows": rows,
            "guard_life_fraction": guard_fraction,
            "interpretation": "Screen associations only; lower size/clicks do not establish why fitness improves."}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("records", type=Path, nargs="+")
    parser.add_argument("--g5-worlds", nargs="+")
    args = parser.parse_args()
    reports = [admission(json.loads(path.read_text())) for path in args.records]
    out = duration_gate(reports, args.g5_worlds) if args.g5_worlds else reports
    print(json.dumps(out, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
