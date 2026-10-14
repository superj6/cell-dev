"""Wait for a two-worker slot, then run the registered frozen-tissue measurement under its CPU cap."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import resource
import signal
import subprocess
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
# An archived copy always preserves the registered working directory.
STUDY = ROOT / "outputs/autonomous_frozen_20261013"
DEPENDENCY = ROOT / "outputs/autonomous_continuation_20261013"
CAP_CPU_SECONDS = 3600
STOP_CPU_SECONDS = 3588
POLL_SECONDS = 2
HELPERS = ("taskvar_confirm.py", "taskvar_factorial.py", "taskvar_second_step.py",
           "taskvar_gradient.py", "taskvar_gates.py")


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(".tmp")
    temp.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n")
    temp.replace(path)


def cpu(pid):
    usage = resource.getrusage(resource.RUSAGE_CHILDREN)
    total = usage.ru_utime + usage.ru_stime
    if pid is not None:
        try:
            fields = Path(f"/proc/{pid}/stat").read_text().rsplit(")", 1)[1].split()
            total += (int(fields[11]) + int(fields[12])) / os.sysconf("SC_CLK_TCK")
        except FileNotFoundError:
            pass
    return total


def check_ready():
    ready = json.loads((STUDY / "ready.json").read_text())
    if ready["monitor_sha256"] != sha(Path(__file__)):
        raise ValueError("monitor differs from readiness pin")
    if ready["runner_sha256"] != sha(ROOT / "scripts/taskvar_frozen_gain.py"):
        raise ValueError("scientific runner differs from readiness pin")
    if set(ready["helpers"]) != set(HELPERS):
        raise ValueError("measurement helper pin set differs")
    for name, expected in ready["helpers"].items():
        if sha(ROOT / "scripts" / name) != expected:
            raise ValueError(f"measurement helper differs: {name}")
    if not ready["source_identity"]:
        raise ValueError("source identity must not be empty")
    for relative, expected in ready["source_identity"].items():
        if sha(ROOT / relative) != expected:
            raise ValueError(f"numerical/search source differs: {relative}")
    for name, key in (("run_budgeted.py", "monitor_sha256"), ("protocol.json", "protocol_sha256")):
        if sha(DEPENDENCY / name) != ready["dependency"][key]:
            raise ValueError(f"continuation dependency differs: {name}")
    return ready


def dependency_available():
    path = DEPENDENCY / "budget.json"
    if not path.exists():
        return False
    before = json.loads(path.read_text())
    if before["status"] not in ("running", "complete"):
        raise ValueError("continuation stopped abnormally: inspect before launching another study")
    if before["status"] == "complete" and (before["queued"] or before["running"]):
        raise ValueError("continuation completion record contains active work")
    return not before["queued"] and len(before["running"]) <= 1


def child_limit():
    # The normal monitor stops earlier. RLIMIT_CPU bounds an unresponsive scientific process too.
    resource.setrlimit(resource.RLIMIT_CPU, (CAP_CPU_SECONDS - 1, CAP_CPU_SECONDS))


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
        print(json.dumps({"status": "dry_run", "genome_lives": 4096, "max_cpu_seconds": CAP_CPU_SECONDS,
                          "workers": 2, "workdir": str(STUDY),
                          "wait_for": "at most one remaining two-worker continuation job"}))
        return
    check_ready()
    status_path = STUDY / "budget.json"
    if status_path.exists():
        raise ValueError("budget record exists: inspect prior resource use before any restart")
    if (STUDY / "measurement").exists() and any((STUDY / "measurement").rglob("*.npz")):
        raise ValueError("measurement rows exist without a budget record: inspect prior resource use")
    print("Waiting for two available simulation workers.", flush=True)
    while not dependency_available():
        save(status_path, {"status": "waiting_for_workers", "cpu_seconds": cpu(None),
                           "cap_cpu_seconds": CAP_CPU_SECONDS})
        time.sleep(POLL_SECONDS)
    # D launches at most one two-worker confirmation after its two evolution jobs finish.
    check_ready()
    affinity = os.sched_getaffinity(0).intersection(range(12))
    if not affinity:
        raise ValueError("fast CPUs0-11 unavailable; inspect host affinity")
    os.sched_setaffinity(0, affinity)
    env = dict(os.environ, ATEN_CPU_CAPABILITY="avx2", OMP_WAIT_POLICY="PASSIVE", OMP_NUM_THREADS="2",
               MKL_NUM_THREADS="2", CELL_DEV_CACHE=str(ROOT / "outputs/e1_resume/kernel-cache"), PYTHONUNBUFFERED="1")
    env.pop("CELLDEV_THREADS_FILE", None)
    command = [str(ROOT / ".venv/bin/python"), "-m", "scripts.taskvar_frozen_gain", "--run",
               "--out", str(STUDY / "measurement"), "--threads", "2", "--max-cpu-seconds", str(CAP_CPU_SECONDS)]
    start, stopped = time.monotonic(), False
    old_handler = signal.signal(signal.SIGTERM, interrupted)
    try:
        with (STUDY / "run.log").open("a") as log:
            process = subprocess.Popen(command, cwd=ROOT, env=env, stdout=log, stderr=subprocess.STDOUT,
                                       start_new_session=True, preexec_fn=child_limit)
            print(f"Started frozen-tissue study: pid {process.pid}", flush=True)
            try:
                while process.poll() is None:
                    consumed = cpu(process.pid)
                    if consumed >= STOP_CPU_SECONDS:
                        stopped = True
                        terminate(process)
                    save(status_path, {"status": "cpu_budget_exhausted" if stopped else "running",
                                       "cpu_seconds": consumed, "cap_cpu_seconds": CAP_CPU_SECONDS,
                                       "wall_seconds": time.monotonic() - start, "pid": process.pid,
                                       "affinity": sorted(affinity)})
                    if not stopped:
                        time.sleep(POLL_SECONDS)
            finally:
                if process.poll() is None:
                    terminate(process)
    except BaseException as error:
        save(status_path, {"status": "monitor_failed", "cpu_seconds": cpu(None),
                           "cap_cpu_seconds": CAP_CPU_SECONDS, "wall_seconds": time.monotonic() - start,
                           "error": type(error).__name__, "affinity": sorted(affinity)})
        raise
    finally:
        signal.signal(signal.SIGTERM, old_handler)
    report_path = STUDY / "measurement/report.json"
    complete = report_path.exists() and json.loads(report_path.read_text())["status"] == "complete"
    consumed = cpu(None)
    exhausted = stopped or process.returncode in (-signal.SIGXCPU, -signal.SIGKILL) or consumed >= CAP_CPU_SECONDS
    status = "complete" if process.returncode == 0 and complete and not exhausted else "incomplete"
    save(status_path, {"status": status, "cpu_seconds": consumed, "cap_cpu_seconds": CAP_CPU_SECONDS,
                       "wall_seconds": time.monotonic() - start, "exit_code": process.returncode,
                       "cpu_budget_exhausted": exhausted, "affinity": sorted(affinity)})
    raise SystemExit(0 if status == "complete" else 1)


if __name__ == "__main__":
    main()
