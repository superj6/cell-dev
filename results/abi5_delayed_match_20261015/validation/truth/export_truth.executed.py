"""Fixed ABI5 engineering truth: eight C full, eight C fast and eight Python lives.

Run once after the parent agent clears validation, using a fresh output directory:
  OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 <python> export_truth.py --out <fresh-directory>
Then, from worktree:
  node results/atlas/play/test_delayed_match.js --truth <fresh-directory>/truth.json

The JS command adds exactly sixteen truth replays (one full and one stepped per case),
plus its default boundary suite. The eight predeclared seeds are reused engineering
fixtures in the 42M range. They are not fresh scientific evaluation seeds. No body,
seed or case is selected from observed outcomes. Historical legacy fixtures stay in
their existing tests and are not repeated here.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
from pathlib import Path
import resource
import sys
import time

HERE = Path(__file__).resolve().parent
DEFAULT_WORKTREE = HERE.parent / "worktree"
RASTER_CAP = 65_536
FATE_CAP = 4_096
CPU_SECONDS = 300
ADDRESS_SPACE_BYTES = 2 * 1024 ** 3
FIXED_TIMING = dict(sample_min=15.0, sample_max=15.0, blank_min=25.0, blank_max=25.0,
                    choice_T=50.0, reset_T=5.0)
CASES = (
    dict(name="reflex_preset_0", body=6, seed=42_000_000, world=dict(T=96.0)),
    dict(name="reflex_preset_1", body=6, seed=42_000_001, world=dict(T=96.0)),
    dict(name="grn_fixed", body=0, seed=42_000_002, world=dict(T=128.0, **FIXED_TIMING)),
    dict(name="grn_shifted_carry", body=0, seed=42_000_003,
         world=dict(T=128.0, t0=32.0, t_open=45.0, **FIXED_TIMING)),
    dict(name="reflex_shifted_open", body=6, seed=42_000_004,
         world=dict(T=96.0, t0=-32.0, t_open=40.0, **FIXED_TIMING)),
    dict(name="reflex_deadline_at_end", body=6, seed=42_000_005, add_flags=("motor_off",),
         world=dict(T=96.0, **(FIXED_TIMING | dict(choice_T=56.0)))),
    dict(name="reflex_extinct_world_continues", body=6, seed=42_000_006,
         world=dict(T=96.0, kill_t=1.0, kill_frac=1.0, **FIXED_TIMING)),
    dict(name="grn_guard_before_window", body=0, seed=42_000_007,
         world=dict(T=96.0, t_open=45.0, n_max=1, **FIXED_TIMING)),
)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write_json(path, value):
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n")


def manifest(worktree):
    return dict(
        purpose="engineering parity only; no behavioral admission claim", worktree=str(worktree),
        cases=list(CASES), threads=1, raster_cap=RASTER_CAP, fate_cap=FATE_CAP,
        cpu_seconds_limit=CPU_SECONDS, address_space_bytes_limit=ADDRESS_SPACE_BYTES,
        planned_calls={"C_full": 8, "C_fast": 8, "Python": 8, "JS_truth_full": 8, "JS_truth_stepped": 8},
        exporter_lives=24, planned_cross_backend_truth_lives=40,
        js_boundary_suite="Additional default suite in test_delayed_match.js reports its construction and run counts",
        fast_hash_policy="Assert HASH_INIT constants; never use fast hashes as replay evidence",
        legacy_policy="Existing ABI2/3/4 byte fixtures run separately without regeneration",
    )


def main(worktree, output, plan_only=False):
    worktree = worktree.resolve()
    plan = manifest(worktree)
    if plan_only:
        print(json.dumps(plan, indent=2))
        return
    if output is None:
        raise ValueError("--out is required unless --plan is used")
    output = output.resolve()
    if output.exists() and any(output.iterdir()):
        raise ValueError("output must be a fresh empty directory; partial runs are not resumed")
    output.mkdir(parents=True, exist_ok=True)
    write_json(output / "manifest.json", plan)
    resource.setrlimit(resource.RLIMIT_CPU, (CPU_SECONDS, CPU_SECONDS + 10))
    resource.setrlimit(resource.RLIMIT_AS, (ADDRESS_SPACE_BYTES, ADDRESS_SPACE_BYTES))
    # These are process-local limits; numpy is deliberately imported only after they are set.
    os.environ["OPENBLAS_NUM_THREADS"] = "1"
    os.environ["OMP_NUM_THREADS"] = "1"
    os.environ["MKL_NUM_THREADS"] = "1"
    sys.path.insert(0, str(worktree))
    import numpy as np
    from dataclasses import replace
    from src.life import build, reference, spec

    def equal_bits(a, b, label):
        a, b = np.asarray(a), np.asarray(b)
        if a.shape != b.shape or a.dtype != b.dtype or a.tobytes() != b.tobytes():
            raise AssertionError(label + " differs bitwise")

    def conservation(row):
        for cls in ("narrow", "broad"):
            get = lambda metric: row[spec.V5.L[f"{metric}_{cls}"]]
            assert get("choice_opportunities") + get("choice_carry_in") == sum(get(metric) for metric in (
                "correct_choices", "wrong_choices", "choice_timeouts", "unfinished_choices")), cls

    source = worktree / "results/atlas/play/bodies.json"
    document = json.loads(source.read_text())
    contract = spec.V5
    defaults = spec.world("catch_delayed_match_l4")
    task_keys = ("task_mode", "sample_min", "sample_max", "blank_min", "blank_max", "choice_T", "reset_T",
                 "visibility_mode", "visibility_on", "visibility_off", "visibility_low", "v_t", "tau_turn",
                 "t_resp", "b2_amp", "b2_p", "b2_mode", "sigma", "b2_sigma", "b2_value", "rho_c", "b2_rho",
                 "R_min", "R_max", "R_cap", "c_miss")
    tasks = {key: getattr(defaults, key) for key in task_keys}
    initial_classes = [int(spec.draw(case["seed"], spec.S_TASK_CLASS, 0, 0) >= 0.5) for case in CASES]
    assert set(initial_classes) == {0, 1}, "fixed cases must cover both initial sample classes"
    paths = [source, worktree / "src/life/spec.py", worktree / "src/life/reference.py",
             worktree / "src/life/build.py", worktree / "src/life/kernel.c",
             worktree / "results/atlas/play/lifesim.js", worktree / "results/atlas/play/test_delayed_match.js",
             Path(__file__)]
    source_hashes = {str(path): sha(path) for path in paths}
    fixture = dict(status="incomplete", abi=5, plan=plan, source_sha256=source_hashes,
                   body_source_sha256=sha(source), raster_cap=RASTER_CAP, fate_cap=FATE_CAP,
                   initial_sample_classes=initial_classes, cases=[])
    calls = []
    started, cpu_started = time.monotonic(), time.process_time()

    def call(backend, case, function):
        record = dict(index=len(calls), backend=backend, case=case["name"], seed=case["seed"], status="started")
        calls.append(record)
        write_json(output / "calls.json", calls)
        result = function()
        record["status"] = "complete"
        write_json(output / "calls.json", calls)
        return result

    try:
        for case in CASES:
            body = copy.deepcopy(document["bodies"][case["body"]])
            values = body["world"] | tasks | dict(t0=0.0, t_open=0.0) | case["world"]
            values = {key: int(value) if isinstance(getattr(defaults, key), int) else value
                      for key, value in values.items()}
            for flag in case.get("add_flags", ()):
                values["flags"] |= contract.FLAGS[flag]
            world = replace(defaults, **values)
            vector = contract.pack_world(world)
            body.update(abi=5, world={key: float(getattr(world, key)) for key in contract.WORLD_KEYS},
                        world_vec=vector.tolist(), lattice=document["lattice"], genome_slices=document["genome_slices"])
            genome = np.asarray(body["genome"], dtype=np.float64) if body["mode"] == "grn" else None
            program = np.asarray(body["program"], dtype=np.float64) if body["mode"] == "program" else None
            cells = body.get("cells")
            tables = dict(genomes=None if genome is None else genome[None], programs=program, init=cells,
                          abi=contract, threads=1)
            full = call("C_full", case, lambda: build.run(world, [case["seed"]], **tables,
                                                         raster_cap=RASTER_CAP, fate_cap=FATE_CAP))
            assert int(full.raster_n[0]) <= RASTER_CAP and int(full.fate_n[0]) <= FATE_CAP, "log capacity exceeded"
            fast = call("C_fast", case, lambda: build.run(world, [case["seed"]], **tables, fast=True))
            equal_bits(full.ledger, fast.ledger, case["name"] + " C full/fast ledger")
            assert np.all(fast.hashes == spec.HASH_INIT), "fast hash families must remain constants"
            lat, unit = contract.lattice_tables(world.lattice)
            ref = call("Python", case, lambda: reference.run_life(vector, lat, unit, genome_table=genome,
                program=program, init=cells, seeds=(case["seed"], 0, 0, 0), raster_cap=RASTER_CAP,
                fate_cap=FATE_CAP, abi=contract))
            equal_bits(full.ledger[0], ref.ledger, case["name"] + " C/Python ledger")
            equal_bits(full.hashes[0], ref.hashes, case["name"] + " C/Python hashes")
            rt, ru = full.spikes(0)
            equal_bits(rt, ref.raster_t, case["name"] + " raster times")
            equal_bits(ru, ref.raster_uid, case["name"] + " raster uids")
            assert int(full.raster_n[0]) == ref.raster_n
            fi, ff = full.fates(0)
            equal_bits(fi, ref.fate_i, case["name"] + " fate integers")
            equal_bits(ff, ref.fate_f, case["name"] + " fate floats")
            conservation(ref.ledger)
            fixture["cases"].append(dict(name=case["name"], source_body=case["body"], body=body, seed=case["seed"],
                ledger=[repr(float(value)) for value in ref.ledger], hashes=[f"{int(value):016x}" for value in ref.hashes],
                raster_t=[repr(float(value)) for value in rt], raster_uid=[f"{int(value):016x}" for value in ru],
                raster_total=int(ref.raster_n), fate_i=fi.tolist(), fate_f=[[repr(float(v)) for v in row] for row in ff]))
            write_json(output / "progress.json", dict(status="running", completed_cases=len(fixture["cases"]),
                                                      completed_calls=len(calls), total_calls=24))
            print(f"C full/fast and Python agree: {case['name']}", flush=True)
        assert source_hashes == {str(path): sha(path) for path in paths}, "source changed during the batch"
        fixture.update(status="complete", cpu_seconds=time.process_time() - cpu_started,
                       wall_seconds=time.monotonic() - started, C_lives=8, C_full_lives=8, C_fast_lives=8,
                       Python_lives=8, completed_calls=calls)
        write_json(output / "truth.json", fixture)
        write_json(output / "progress.json", dict(status="complete", completed_cases=8, completed_calls=24))
        print(f"Wrote eight fixed engineering cases to {output / 'truth.json'}", flush=True)
    except BaseException as exc:
        write_json(output / "progress.json", dict(status="failed", completed_cases=len(fixture["cases"]),
                                                  calls=calls, error=repr(exc)))
        raise


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--worktree", type=Path, default=DEFAULT_WORKTREE)
    parser.add_argument("--out", type=Path)
    parser.add_argument("--plan", action="store_true", help="print exact cases, calls and limits without importing simulators")
    args = parser.parse_args()
    main(args.worktree, args.out, args.plan)
