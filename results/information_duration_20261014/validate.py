"""Forty bounded T64 validation lives using the unchanged retained C4-copy/replay controller."""
from __future__ import annotations

import ctypes
import time
from pathlib import Path

import numpy as np

import measure as M
from scripts.taskvar_gates import validate_lives
from scripts.taskvar_measure import compile_measurement
from src.life import build, spec


def same(left, right):
    return left.shape == right.shape and left.dtype == right.dtype and left.tobytes() == right.tobytes()


def run_validation(protocol, out):
    out = Path(out)
    if out.exists():
        raise ValueError("validation already exists; no unaccounted repeat")
    out.mkdir(parents=True)
    library = out / "replay.so"
    H = compile_measurement(library, M.STUDY / "sources/vctl.c", fast=False)
    lib = H.load(str(library), fast=False)
    lib.v4h_log_enable.argtypes = [ctypes.c_int]
    lib.v4h_log_get.restype = ctypes.c_long
    lib.v4h_log_get.argtypes = [ctypes.POINTER(ctypes.c_double), ctypes.c_long]
    config = protocol["validation"]
    if config != {"T": 64, "seeds": list(range(51_099_000, 51_099_004)),
                  "closed_loop_indices": [0, 1], "control_indices": [2, 3], "threads": 1, "candidate_lives": 40}:
        raise ValueError("fixed bounded validation plan differs")
    fp, counted = H.footprint("hollow3"), []
    started = time.process_time()

    def keep(tag, result, world, **extra):
        validate_lives(result, spec.world(world.preset, **world.over))
        arrays = dict(ledger=result.ledger, hashes=result.hashes,
                      diag=getattr(result, "diag", np.empty((len(result.ledger), 0))), **extra)
        path = out / (tag + ".npz")
        np.savez_compressed(path, **arrays)
        counted.append({"tag": tag, "lives": len(result.ledger), "sha256": M.sha(path)})

    def run(cid, params, world, seed, extra=None):
        return H.ctl_run(cid, params, fp, world, [seed], extra=extra, threads=1,
                         lib=str(library), fast=False, latency="d0", charge="relay",
                         t_ref_min=.5, privileged=False, quant=False)

    def logged(tag, cid, params, world, seed, extra=None):
        lib.v4h_log_enable(1)
        try:
            result = run(cid, params, world, seed, extra)
            buffer = np.zeros(1 << 20, dtype=np.float64)
            count = lib.v4h_log_get(buffer.ctypes.data_as(ctypes.POINTER(ctypes.c_double)), len(buffer))
            if count <= 0 or count > len(buffer) or count % 6:
                raise ValueError("bounded C4 replay log is empty or exceeds capacity")
            log = buffer[:count].reshape(-1, 6).copy()
        finally:
            lib.v4h_log_enable(0)
        pings, actions = log[log[:, 0] == 0][:, 1:3], log[log[:, 0] >= 1]
        keep(tag, result, world, pings=pings, actions=actions)
        return result, pings, actions

    checks = {}
    for name in M.WORLD_NAMES:
        world = H.world_spec(name).with_(T=64)
        ro = world.with_(flags=spec.V3.flags("receptor_off"))
        alien = ro.with_(v_t=.3, tau_turn=5., t_resp=10., R_min=4., R_max=9., sigma=1.2, lam_s=1.)
        params = protocol["candidates"][name][0]["params"]
        copied = np.r_[params, np.zeros(6)]
        rows = []
        for i in config["closed_loop_indices"]:
            seed, other = config["seeds"][i], config["seeds"][i + 2]
            builtin = run(5, params, world, seed)
            keep(f"{name}_{i}_builtin", builtin, world)
            actual, pings, actions = logged(f"{name}_{i}_closed", 1005, copied, world, seed)
            identity = same(builtin.ledger, actual.ledger) and same(builtin.hashes, actual.hashes)
            identity = identity and same(builtin.diag[:, :12], actual.diag[:, :12])
            if not identity:
                raise ValueError("unchanged V4 copy differs from builtin C4")
            injection = np.r_[len(pings), pings.reshape(-1)]
            replay_checks = {}
            for label, ws, sd in (("same_life", ro, seed), ("other_life", ro, other),
                                  ("other_world", alien, other)):
                replay, _, returned = logged(f"{name}_{i}_{label}", 1006, copied, ws, sd, injection)
                replay_checks[label] = same(actions, returned) and replay.diag[0, 0] == 0 and len(actions) > 0
                if not replay_checks[label]:
                    raise ValueError("C4 actions depend on information beyond the retained ping stream")
            _, _, control = logged(f"{name}_{i}_control", 1005, copied, world, other)
            if same(control, actions):
                raise ValueError("closed-loop control did not establish replay sensitivity")
            rows.append({"seed": seed, "copy_bitwise": identity, "replay": replay_checks,
                         "control_differs": True, "pings": len(pings), "action_records": len(actions)})
        seeds = config["seeds"][:2]
        body = H.reflex("hollow3")
        scratch = H.tissue_run(body, world, seeds, threads=1, lib=str(library), fast=False)
        keep(name + "_scratch_reflex", scratch, world)
        production = build.run(body.world("catch_speck_l4", **world.over), seeds,
                               programs=body.program, init=list(body.cells), abi=spec.V3, threads=1)
        keep(name + "_production_reflex", production, world)
        columns = [i for i in range(spec.V3.LEDGER_SIZE) if i not in (21, 22)]
        parity = same(scratch.ledger[:, columns], production.ledger[:, columns])
        parity = parity and same(scratch.hashes[:, 1:], production.hashes[:, 1:])
        if not parity:
            raise ValueError("scratch world physics differs from production ABI3")
        null = H.ctl_run(H.NULL, [], fp, world, seeds, threads=1, lib=str(library), fast=False,
                         charge="none", privileged=False)
        inert = H.tissue_run(fp.inert_body(), world, seeds, threads=1, lib=str(library), fast=False)
        keep(name + "_null", null, world)
        keep(name + "_inert", inert, world)
        null_parity = same(null.hashes[:, 4], inert.hashes[:, 4])
        null_parity = null_parity and all(same(null[key], inert[key]) for key in
                                         ("rec_cand", "rec_accept", "respawns", "dist_sum", "zone_samples", "n_end"))
        if not null_parity:
            raise ValueError("null controller changes the world stream")
        checks[name] = {"controller_replay": rows, "reflex_production_parity": True,
                        "null_inert_world_parity": True, "excluded_ledger_columns": [21, 22],
                        "excluded_hash": "all"}
    count = sum(item["lives"] for item in counted)
    if count != 40:
        raise ValueError("validation life count differs")
    result = {"passed": True, "candidate_lives": count, "T": 64, "records": counted, "checks": checks,
              "cpu_seconds": time.process_time() - started,
              "library_sha256": M.sha(library), "source_sha256": M.sha(library.with_suffix(".c")),
              "note": "Compiler and all validation CPU are additionally charged by the external monitor."}
    M.save(out / "report.json", result)
    return result
