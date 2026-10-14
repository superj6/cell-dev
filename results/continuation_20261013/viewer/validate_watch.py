"""Synthetic checks by default; eight short C/JS comparisons only after a worker is released."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import resource
import signal
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = next(path for path in HERE.parents if (path / "src/life/spec.py").exists())
sys.path.insert(0, str(ROOT))
sys.dont_write_bytecode = True
for name in ("OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS"):
    os.environ[name] = "1"
os.environ["ATEN_CPU_CAPABILITY"] = "avx2"
os.environ["OMP_WAIT_POLICY"] = "PASSIVE"
os.environ.pop("CELLDEV_THREADS_FILE", None)
CPU_CAP = 15.0


def write(path, data):
    path.write_text(json.dumps(data, indent=2, allow_nan=False) + "\n")


def html_path():
    local = HERE / "watch.html"
    return local if local.exists() else HERE.parent / "watch.html"


def synthetic():
    completed = subprocess.run(["node", str(HERE / "test_watch.js")], capture_output=True, text=True, check=True)
    result = {"ui": json.loads(completed.stdout), "actual_simulated_lives": 0,
              "visual_browser_check": "Not performed; synthetic DOM and canvas checks only."}
    write(HERE / "ui_validation.json", result)
    return result


def worker():
    os.sched_setaffinity(0, set(os.sched_getaffinity(0)) & set(range(12)))
    import numpy as np

    from src.life import build, spec

    data = json.loads((HERE / "bodies.json").read_text())
    cases = []
    for name in ("pool", "base"):
        overrides = {"sigma": 0.4, "lam_s": 4.0} if name == "pool" else {}
        world = spec.world("catch_speck_l4", T=32, d0=0.5, d_min=0.25, **overrides)
        for body in data["bodies"]:
            result = build.run(world, [data["default_seed"]], genomes=np.asarray([body["genome"]]),
                               abi=spec.V3, kind="hexprism", threads=1)
            cases.append({"world": name, "body": body["name"], "seed": data["default_seed"], "T": 32,
                          "ledger": {key: repr(float(result.ledger[0, i])) for i, key in enumerate(spec.V3.LEDGER)},
                          "hashes": {key: f"{int(value):016x}" for key, value in
                                     zip(spec.V3.HASHES, result.hashes[0])}})
            write(HERE / "truth_T32.partial.json", cases)
    write(HERE / "truth_T32.json", cases)
    result = subprocess.run(["node", str(HERE / "verify_parity.js")], capture_output=True, text=True, check=True)
    record = {"parity": json.loads(result.stdout), "kernel_lives": 8, "browser_engine_lives": 8,
              "duration": 32, "default_seed": data["default_seed"], "research_lives": 0,
              "html_sha256": hashlib.sha256(html_path().read_bytes()).hexdigest(),
              "engine_sha256": data["engine_sha256"],
              "scope": "Short validation only; no new full-life parity or scientific evidence."}
    write(HERE / "parity_result.json", record)


def own_cpu():
    used = resource.getrusage(resource.RUSAGE_SELF)
    return used.ru_utime + used.ru_stime


def group_cpu(group):
    ticks = os.sysconf("SC_CLK_TCK")
    total = 0
    for path in Path("/proc").glob("[0-9]*/stat"):
        try:
            fields = path.read_text().rsplit(")", 1)[1].split()
            if int(fields[2]) == group:
                total += sum(int(fields[i]) for i in (11, 12, 13, 14))
        except (FileNotFoundError, ProcessLookupError):
            pass
    return total / ticks


def simulate():
    if (HERE / "parity_budget.json").exists():
        raise RuntimeError("A parity budget already exists; review it instead of silently repeating lives")
    start_cpu, start = own_cpu(), time.monotonic()
    log = (HERE / "parity.log").open("w")
    process = subprocess.Popen([sys.executable, str(Path(__file__)), "--worker"], stdout=log, stderr=log,
                               start_new_session=True, cwd=ROOT)
    last_cpu, stopped, wait_status, usage = 0.0, False, None, None
    while True:
        waited, status, waited_usage = os.wait4(process.pid, os.WNOHANG)
        if waited:
            wait_status, usage = status, waited_usage
            process.returncode = os.waitstatus_to_exitcode(status)
            break
        used = group_cpu(process.pid) + own_cpu() - start_cpu
        last_cpu = max(last_cpu, used)
        if used >= CPU_CAP - 1.5 or time.monotonic() - start >= 180:
            stopped = True
            try:
                os.killpg(process.pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
            time.sleep(0.15)
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            _, wait_status, usage = os.wait4(process.pid, 0)
            process.returncode = os.waitstatus_to_exitcode(wait_status)
            break
        time.sleep(0.1)
    log.close()
    used = max(last_cpu, usage.ru_utime + usage.ru_stime + own_cpu() - start_cpu)
    budget = {"status": "budget_stop" if stopped else "complete" if process.returncode == 0 else "failed",
              "cpu_seconds": used, "cap_cpu_seconds": CPU_CAP, "wall_seconds": time.monotonic() - start,
              "exit_code": process.returncode, "simulation_workers": 1}
    write(HERE / "parity_budget.json", budget)
    if budget["status"] != "complete" or used > CPU_CAP:
        raise RuntimeError("Short parity did not complete within its fixed cap; inspect parity_budget.json")
    report = json.loads((HERE / "parity_result.json").read_text())
    report.update(budget=budget, ui=json.loads((HERE / "ui_validation.json").read_text())["ui"])
    write(HERE / "validation.json", report)
    print(json.dumps(report, indent=2))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--simulate", action="store_true")
    parser.add_argument("--released-worker", action="store_true", help="Operator confirms one worker is available")
    parser.add_argument("--worker", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.worker:
        worker()
        return
    report = synthetic()
    if not args.simulate:
        print(json.dumps(report, indent=2))
        return
    if not args.released_worker:
        raise RuntimeError("Actual parity waits for root's explicit release of one unused simulation worker")
    simulate()


if __name__ == "__main__":
    main()
