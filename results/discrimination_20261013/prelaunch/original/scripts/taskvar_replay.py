"""Bounded E7 controller leakage replay and production-world parity audit.

Records both pings and the controller's own wake callbacks, then injects that
same ordered stream with real receptors disabled in other lives and worlds.
Every requested action and wake must match bitwise; controls must differ.
The default is two T=64 lives for both full and ablated controllers.
"""
from __future__ import annotations

import argparse
import ctypes
import hashlib
import json
from pathlib import Path

import numpy as np

from scripts.taskvar_gates import validate_lives
from scripts.taskvar_gradient import atomic_json
from scripts.taskvar_measure import INPUTS, ROOT, compile_measurement, harness_identity
from src.life import analysis, build, spec


def bitwise_equal(a, b) -> bool:
    return a.shape == b.shape and a.dtype == b.dtype and a.tobytes() == b.tobytes()


def audit(capability: str, out: Path, lives: int, duration: float) -> dict:
    config_path = INPUTS / f"{capability}.json"
    config = json.loads(config_path.read_text())
    source = INPUTS / config["controller_source"]
    source_hash = hashlib.sha256(source.read_bytes()).hexdigest()
    if source_hash != config["source_sha256"]:
        raise ValueError("controller source hash differs from its measurement config")
    if "k->extra" in source.read_text():
        raise ValueError("replay injection requires a controller that does not read the extra array")
    out.mkdir(parents=True, exist_ok=True)
    template = (INPUTS / "replay_wrapper.c.in").read_text()
    definition = "CTL_PF" if capability == "prediction" else "CTL_D2"
    wrapper = out / "replay_wrapper.c"
    wrapper.write_text(template.replace("@SOURCE@", str(source)).replace("@DEF@", definition))
    library = str(out / "replay.so")
    harness = compile_measurement(Path(library), wrapper, fast=False)
    lib = harness.load(library, fast=False)
    lib.e7_log_size.restype = ctypes.c_long
    lib.e7_log_copy.argtypes = [ctypes.POINTER(ctypes.c_double)]
    world = harness.WorldSpec(capability, over=dict(config["overrides"], T=duration))
    ro = world.with_(flags=spec.V3.flags("receptor_off"))
    alien = ro.with_(v_t=0.4, tau_turn=3.0, t_resp=11.0, R_min=3.0, R_max=9.0, sigma=0.9, lam_s=0.3)
    fp = harness.footprint(config["reflex_footprint"])
    block = 3 if capability == "prediction" else 4
    seeds = analysis.fresh_seeds(2 * lives, seed0=51_000_000 + 10_000 * block)

    def logged(cid, params, ws, seed, extra=None):
        result = harness.ctl_run(cid, params, fp, ws, [seed], extra=extra, threads=1,
                                 privileged=False, lib=library, fast=False)
        validate_lives(result, spec.world(ws.preset, **ws.over))
        log = np.zeros(lib.e7_log_size())
        lib.e7_log_copy(log.ctypes.data_as(ctypes.POINTER(ctypes.c_double)))
        log = log.reshape(-1, 6)
        callbacks = log[(log[:, 0] == 0) | (log[:, 0] == 4), :3]
        actions = log[(log[:, 0] != 0) & (log[:, 0] != 4)]
        return result, callbacks, actions

    rows = []
    ablated = list(config["params"])
    for index, value in config["ablate"].items():
        ablated[int(index)] = value
    for variant, params in (("full", config["params"]), ("ablated", ablated)):
        for i in range(lives):
            _, callbacks, actions = logged(1901, params, world, seeds[i])
            extra = np.r_[len(callbacks), callbacks.reshape(-1)]
            row = {"variant": variant, "seed": seeds[i], "callbacks": len(callbacks),
                   "action_records": len(actions), "checks": {}}
            logs = {"callbacks": callbacks, "actions": actions}
            for name, ws, seed in (("same_life", ro, seeds[i]), ("other_life", ro, seeds[i + lives]),
                                   ("other_world", alien, seeds[i + lives])):
                replay, _, replay_actions = logged(1902, params, ws, seed, extra=extra)
                row["checks"][name] = bool(bitwise_equal(actions, replay_actions)
                                            and replay.diag[0, 0] == 0 and len(actions) > 0)
                logs[name] = replay_actions
            _, _, control = logged(1901, params, world, seeds[i + lives])
            row["control_differs"] = not bitwise_equal(actions, control)
            logs["control"] = control
            np.savez_compressed(out / f"{variant}_{i}_replay.npz", **logs)
            rows.append(row)
    # The scratch copy repurposes two ledger columns and the all-ledger hash.
    # Everything else in a normal tissue life must still match ABI 3 bitwise.
    body = harness.reflex(config["reflex_footprint"])
    scratch = harness.tissue_run(body, world, seeds[:lives], lib=library, fast=False, threads=1)
    production = build.run(body.world("catch_speck_l4", **world.over), seeds[:lives],
                           programs=body.program, init=list(body.cells), abi=spec.V3)
    columns = [i for i in range(scratch.ledger.shape[1]) if i not in (21, 22)]
    validate_lives(scratch, spec.world(world.preset, **world.over))
    validate_lives(production, spec.world(world.preset, **world.over))
    parity = bool(bitwise_equal(scratch.ledger[:, columns], production.ledger[:, columns])
                  and bitwise_equal(scratch.hashes[:, 1:], production.hashes[:, 1:]))
    null = harness.ctl_run(harness.NULL, [], fp, world, seeds[:lives], threads=1, lib=library,
                            fast=False, charge="none", privileged=False)
    inert = harness.tissue_run(fp.inert_body(), world, seeds[:lives], threads=1, lib=library, fast=False)
    for result in (null, inert):
        validate_lives(result, spec.world(world.preset, **world.over))
    null_parity = bitwise_equal(null.hashes[:, 4], inert.hashes[:, 4])
    null_parity = null_parity and all(bitwise_equal(null[key], inert[key]) for key in
                                     ("rec_cand", "rec_accept", "respawns", "dist_sum", "zone_samples", "n_end"))
    passed = all(all(row["checks"].values()) for row in rows)
    passed = passed and all(any(row["control_differs"] for row in rows if row["variant"] == variant)
                            for variant in ("full", "ablated"))
    report = {"passed": passed, "source_sha256": source_hash, "artifact": str(out / "audit.json"),
              "harness_identity": harness_identity(),
              "config_sha256": hashlib.sha256(config_path.read_bytes()).hexdigest(), "T": duration,
              "rows": rows, "world_parity_audit": {"passed": bool(parity and null_parity),
                                                      "null_world_parity": bool(null_parity),
                                                      "artifact": str(out / "audit.json"),
                                                      "seeds": seeds[:lives], "excluded_ledger": [21, 22],
                                                      "excluded_hash": "all"}}
    atomic_json(out / "audit.json", report)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("capability", choices=("prediction", "discrimination"))
    parser.add_argument("--lives", type=int, default=2)
    parser.add_argument("--duration", type=float, default=64)
    parser.add_argument("--out", type=Path, default=ROOT / "outputs/taskvar_e7/audit")
    args = parser.parse_args()
    if args.lives < 1 or args.duration <= 0:
        parser.error("lives and duration must be positive")
    if not args.out.resolve().is_relative_to(ROOT / "outputs"):
        parser.error("study output must be inside the repository outputs/ directory")
    out = args.out / args.capability
    if (out / "audit.json").exists():
        parser.error("audit already exists; use a new output directory")
    report = audit(args.capability, out, args.lives, args.duration)
    print(json.dumps(report, indent=2))
    if not report["passed"] or not report["world_parity_audit"]["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
