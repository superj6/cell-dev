"""Wait for G completion, then run the fixed decoy diagnostic alongside H under a two-worker CPU cap."""
from __future__ import annotations

import argparse
import ctypes
import hashlib
import json
import math
import os
import resource
import signal
import subprocess
import time
from pathlib import Path

ROOT = next(p for p in Path(__file__).resolve().parents if (p / "src/life/spec.py").exists())
STUDY = ROOT / "outputs/autonomous_decoy_gradient_20261014"
CAP, STOP, POLL = 3600, 3588, 2
DEPENDENCY = "outputs/autonomous_structural_20261013"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_json(path):
    return json.loads(path.read_text())


def save(path, value):
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n")
    temporary.replace(path)


def cpu(pid=None):
    own = resource.getrusage(resource.RUSAGE_SELF)
    children = resource.getrusage(resource.RUSAGE_CHILDREN)
    total = own.ru_utime + own.ru_stime + children.ru_utime + children.ru_stime
    if pid is None:
        return total
    processes = {}
    for directory in Path("/proc").iterdir():
        if not directory.name.isdigit():
            continue
        try:
            fields = (directory / "stat").read_text().rsplit(")", 1)[1].split()
            processes[int(directory.name)] = (int(fields[1]), sum(int(fields[i]) for i in (11, 12, 13, 14)))
        except (FileNotFoundError, ProcessLookupError, PermissionError):
            continue
    pending, ticks = [pid], 0
    while pending:
        current = pending.pop()
        if current in processes:
            ticks += processes[current][1]
            pending.extend(child for child, (parent, _) in processes.items() if parent == current)
    return total + ticks / os.sysconf("SC_CLK_TCK")


def check_ready():
    ready = read_json(STUDY / "ready.json")
    required = {"protocol.json", "measure.py", "run_budgeted.py", "prepare.py", "prereg_draft.md", "test_prepared.py"}
    if set(ready["files"]) != required:
        raise ValueError("readiness file pin set differs")
    for relative, expected in ready["files"].items():
        if sha(STUDY / relative) != expected:
            raise ValueError("released study file changed: " + relative)
    protocol = read_json(STUDY / "protocol.json")
    if set(protocol["dependencies"]) != {DEPENDENCY}:
        raise ValueError("I waits only for completed G; dependency set changed")
    for relative, expected in protocol["source_identity"].items():
        if sha(ROOT / relative) != expected:
            raise ValueError("source changed: " + relative)
    for name, expected in protocol["helpers"].items():
        if sha(ROOT / "scripts" / name) != expected:
            raise ValueError("measurement helper changed: " + name)
    for relative, expected in protocol["input_sha256"].items():
        if sha(STUDY / relative) != expected:
            raise ValueError("fixed input changed: " + relative)
    for dependency, files in protocol["dependencies"].items():
        for name, expected in files.items():
            if sha(ROOT / dependency / name) != expected:
                raise ValueError("dependency protocol/monitor changed: " + dependency)
    if protocol["max_cpu_seconds"] != CAP or protocol["simulation_workers"] != 2:
        raise ValueError("resource cap changed")
    return protocol


def dependencies_complete(protocol):
    ready = True
    for relative in protocol["dependencies"]:
        path = ROOT / relative / "budget.json"
        if not path.exists():
            ready = False
            continue
        record = read_json(path)
        if record["status"] in ("waiting_for_workers", "running"):
            ready = False
            continue
        if record["status"] != "complete":
            raise ValueError("dependency did not finish normally: " + relative)
        if record.get("running") or record.get("queued"):
            raise ValueError("completed dependency still contains queued or running jobs")
    return ready


def child_limit(seconds):
    if ctypes.CDLL(None).prctl(1, signal.SIGKILL, 0, 0, 0) != 0:
        raise OSError("cannot bind worker lifetime to monitor")
    if os.getppid() == 1:
        os._exit(1)
    hard = int(math.floor(seconds))
    if hard < 2:
        raise ValueError("not enough CPU budget remains to start a worker")
    resource.setrlimit(resource.RLIMIT_CPU, (hard - 1, hard))


def terminate(process):
    try:
        os.killpg(process.pid, signal.SIGTERM)
    except ProcessLookupError:
        pass
    try:
        return process.wait(timeout=2)
    except subprocess.TimeoutExpired:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        return process.wait()


def interrupted(signum, frame):
    raise KeyboardInterrupt(f"monitor received signal {signum}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", action="store_true")
    args = parser.parse_args()
    if not args.run:
        print(json.dumps({"status": "dry_run", "genome_lives": 11328, "max_cpu_seconds": CAP,
                          "workers": 2, "wait_for": "G complete; H may use the other two workers",
                          "study": str(STUDY)}))
        return
    protocol = check_ready()
    budget_path = STUDY / "budget.json"
    if budget_path.exists() or ((STUDY / "measurement").exists()
                               and any((STUDY / "measurement").rglob("*.npz"))):
        raise ValueError("existing budget or scientific rows require explicit resource review; no automatic restart")
    started, process, stopped = time.monotonic(), None, False
    old_handler = signal.signal(signal.SIGTERM, interrupted)
    try:
        while not dependencies_complete(protocol):
            save(budget_path, {"status": "waiting_for_workers", "cpu_seconds": cpu(), "cap_cpu_seconds": CAP})
            time.sleep(POLL)
        check_ready()
        affinity = os.sched_getaffinity(0).intersection(range(12))
        if not affinity:
            raise ValueError("fast CPU affinity is empty")
        os.sched_setaffinity(0, affinity)
        env = dict(os.environ, ATEN_CPU_CAPABILITY="avx2", OMP_WAIT_POLICY="PASSIVE", OMP_NUM_THREADS="2",
                   MKL_NUM_THREADS="2", OPENBLAS_NUM_THREADS="2", PYTHONUNBUFFERED="1",
                   CELL_DEV_CACHE=str(ROOT / "outputs/e1_resume/kernel-cache"))
        env.pop("CELLDEV_THREADS_FILE", None)
        remaining = CAP - cpu()
        if remaining < CAP - STOP:
            raise ValueError("waiting/preparation consumed the available CPU budget")
        with (STUDY / "run.log").open("a") as log:
            process = subprocess.Popen([str(ROOT / ".venv/bin/python"), str(STUDY / "measure.py"), "--run"],
                                       cwd=ROOT, env=env, stdout=log, stderr=subprocess.STDOUT,
                                       start_new_session=True, preexec_fn=lambda: child_limit(remaining))
            try:
                while process.poll() is None:
                    consumed = cpu(process.pid)
                    if consumed >= STOP:
                        stopped = True
                        terminate(process)
                    save(budget_path, {"status": "cpu_budget_exhausted" if stopped else "running",
                                       "cpu_seconds": consumed, "cap_cpu_seconds": CAP,
                                       "wall_seconds": time.monotonic() - started, "pid": process.pid,
                                       "simulation_workers": 2, "running": {str(process.pid): "decoy_gradient"},
                                       "queued": []})
                    if not stopped:
                        time.sleep(POLL)
            finally:
                if process.poll() is None:
                    terminate(process)
    except BaseException as error:
        save(budget_path, {"status": "monitor_failed", "cpu_seconds": cpu(), "cap_cpu_seconds": CAP,
                           "wall_seconds": time.monotonic() - started, "error": type(error).__name__,
                           "running": {}, "queued": []})
        raise
    finally:
        signal.signal(signal.SIGTERM, old_handler)
    report_path = STUDY / "measurement/report.json"
    done = report_path.exists() and read_json(report_path)["status"] == "complete"
    consumed = cpu()
    complete = process.returncode == 0 and done and not stopped and consumed < CAP
    save(budget_path, {"status": "complete" if complete else "incomplete", "cpu_seconds": consumed,
                       "cap_cpu_seconds": CAP, "wall_seconds": time.monotonic() - started,
                       "exit_code": process.returncode, "simulation_workers": 2, "running": {}, "queued": [],
                       "cpu_budget_exhausted": stopped or consumed >= CAP})
    raise SystemExit(0 if complete else 1)


if __name__ == "__main__":
    main()
