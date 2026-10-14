"""V fixed information measurement: max two workers and 3600 cumulative CPU seconds, dry-run by default."""
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

ROOT = Path(__file__).resolve().parents[2]
STUDY = Path(__file__).resolve().parent
CAP, RESERVE = 3600, 10
DEPENDENCY = ROOT / "outputs/autonomous_decoy_evolution_20261014/budget.json"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def save(path, value):
    temp = path.with_suffix(".tmp")
    with temp.open("w") as stream:
        stream.write(json.dumps(value, indent=2, allow_nan=False) + "\n")
        stream.flush()
        os.fsync(stream.fileno())
    temp.replace(path)


def proc_table():
    table = {}
    for directory in Path("/proc").iterdir():
        if not directory.name.isdigit():
            continue
        try:
            fields = (directory / "stat").read_text().rsplit(")", 1)[1].split()
            table[int(directory.name)] = {"ppid": int(fields[1]), "pgrp": int(fields[2]),
                "start_ticks": int(fields[19]), "cpu_ticks": sum(int(fields[i]) for i in (11, 12, 13, 14))}
        except (FileNotFoundError, ProcessLookupError, PermissionError):
            continue
    return table


def resource_clearance():
    receipt = json.loads((STUDY / "resource_clearance.json").read_text())
    if receipt.get("all_processes_exited") is not True or receipt["dependency_budget"] != str(DEPENDENCY.relative_to(ROOT)):
        raise ValueError("U resource clearance is absent or names another dependency")
    if receipt["dependency_budget_sha256"] != sha(DEPENDENCY):
        raise ValueError("U budget changed after resource clearance")
    budget = json.loads(DEPENDENCY.read_text())
    if budget.get("status") not in ("complete", "incomplete", "cpu_budget_exhausted", "job_failed", "interrupted", "monitor_failed"):
        raise ValueError("U has not finalized; scientific success is not required")
    table = proc_table()
    for identity in receipt["processes"]:
        current = table.get(identity["pid"])
        if current and current["start_ticks"] == identity["start_ticks"]:
            raise ValueError("an identified U process remains alive")
    if any(row["pgrp"] in receipt["process_groups"] for row in table.values()):
        raise ValueError("a U process group remains alive")
    if not receipt["processes"]:
        raise ValueError("clearance must record the exited U monitor/worker identities")
    return receipt


def readiness():
    path = STUDY / "ready.json"
    if not path.exists():
        raise ValueError("not released: root must register V and create ready.json")
    ready = json.loads(path.read_text())
    for name in ("protocol.json", "measure.py", "run_budgeted.py", "resource_clearance.json"):
        if ready[name] != sha(STUDY / name):
            raise ValueError("readiness source or protocol pin changed")
    resource_clearance()
    return ready


def calibration_prior():
    value = json.loads((STUDY / "calibration_budget.json").read_text())
    if value["status"] != "complete" or value["cap_cpu_seconds"] != 30 or not 0 <= value["cpu_seconds"] <= 30:
        raise ValueError("calibration incomplete or over its fixed cap")
    return float(value["cpu_seconds"])


def prior_usage(path, resume):
    if not path.exists():
        if resume:
            raise ValueError("--resume requires an existing finalized budget record")
        return calibration_prior(), []
    saved = json.loads(path.read_text())
    if not resume:
        raise ValueError("existing budget record; explicit --resume is required")
    if saved["status"] == "running":
        raise ValueError("unfinalized prior monitor: CPU use must be reconciled before resuming")
    if saved["status"] == "complete":
        raise ValueError("study is already complete; no rescore is allowed")
    if saved["ready"] != readiness() or saved["cap_cpu_seconds"] != CAP:
        raise ValueError("prior budget source pins or cap changed")
    if saved.get("cleanup_error"):
        raise ValueError("prior cleanup failed; explicit process/accounting reconciliation is required")
    table = proc_table()
    groups = saved.get("owned_process_groups")
    if not isinstance(groups, list) or not groups:
        raise ValueError("prior owned process-group receipt is missing")
    for attempt in saved["attempts"]:
        for role in ("monitor", "worker"):
            pid, start = attempt.get(role + "_pid"), attempt.get(role + "_start_ticks")
            if not isinstance(pid, int) or not isinstance(start, int):
                raise ValueError("prior process identity receipt is incomplete")
            current = table.get(pid)
            if current and current["start_ticks"] == start:
                raise ValueError("prior V process remains alive; cannot resume")
    if any(row["pgrp"] in groups for row in table.values()):
        raise ValueError("prior V process group remains alive; cannot resume")
    total = saved["cpu_seconds"]
    if not math.isfinite(total) or total < calibration_prior():
        raise ValueError("invalid cumulative CPU accounting")
    return float(total), saved["attempts"]


def child_usage():
    use = resource.getrusage(resource.RUSAGE_CHILDREN)
    return use.ru_utime + use.ru_stime


def process_tree_cpu(root_pid):
    processes = proc_table()
    pending, total = [root_pid], 0
    while pending:
        pid = pending.pop()
        if pid in processes:
            total += processes[pid]["cpu_ticks"]
            pending.extend(child for child, row in processes.items() if row["ppid"] == pid)
    return total / os.sysconf("SC_CLK_TCK")


def process_group_cpu(group):
    return sum(row["cpu_ticks"] for row in proc_table().values() if row["pgrp"] == group) / os.sysconf("SC_CLK_TCK")


def enable_subreaper():
    # Orphaned compiler descendants become our children, so cleanup can reap and charge their CPU.
    libc = ctypes.CDLL(None)
    if libc.prctl(36, 1, 0, 0, 0) != 0:  # Linux PR_SET_CHILD_SUBREAPER
        raise OSError("cannot enable complete descendant CPU accounting")


def cleanup_group(process):
    """Always terminate/reap the owned group, including descendants of an already exited leader."""
    deadline = time.monotonic() + 3
    while True:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        code = process.poll()
        if code is not None:
            while True:
                try:
                    pid, _ = os.waitpid(-process.pid, os.WNOHANG)
                except ChildProcessError:
                    break
                if pid == 0:
                    break
            if not any(row["pgrp"] == process.pid for row in proc_table().values()):
                return
        if time.monotonic() >= deadline:
            raise RuntimeError("owned process group did not exit after SIGKILL")
        time.sleep(.05)


def child_limits(remaining, reserve, expected_parent):
    libc = ctypes.CDLL(None)
    if libc.prctl(1, signal.SIGKILL, 0, 0, 0) != 0:
        raise OSError("cannot bind worker lifetime to CPU monitor")
    if os.getppid() != expected_parent:
        os._exit(1)
    soft = max(1, int(math.floor(remaining - reserve)))
    resource.setrlimit(resource.RLIMIT_CPU, (soft, soft + 1))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--run", action="store_true")
    mode.add_argument("--calibrate", action="store_true")
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args()
    calibration = args.calibrate
    cap, reserve = (30, 2) if calibration else (CAP, RESERVE)
    command = [str(ROOT / ".venv/bin/python"), str(STUDY / "measure.py"),
               "--calibration-worker" if calibration else "--worker"]
    if not (args.run or calibration):
        print(json.dumps({"status": "dry_run", "candidate_lives": 3584, "max_cpu_seconds": CAP,
                          "threads": 2, "command": command, "resource_dependency": str(DEPENDENCY)}))
        return
    if calibration:
        if args.resume:
            raise ValueError("the fixed calibration cannot be repeated or extended")
        ready = json.loads((STUDY / "calibration_plan.json").read_text())
        for name, digest in ready["source_pins"].items():
            if sha(ROOT / name) != digest:
                raise ValueError("calibration source pin changed")
        path = STUDY / "calibration_budget.json"
        if path.exists() or (STUDY / "calibration").exists():
            raise ValueError("calibration already attempted")
        prior, attempts = 0.0, []
    else:
        ready = readiness()
        path = STUDY / "budget.json"
        prior, attempts = prior_usage(path, args.resume)
        if not path.exists() and (STUDY / "manifest.json").exists():
            raise ValueError("scientific checkpoints exist without their cumulative budget record")
    if prior >= cap - reserve:
        raise ValueError("original study CPU budget is exhausted")
    affinity = os.sched_getaffinity(0).intersection(range(12))
    if not affinity:
        raise ValueError("registered fast CPUs0–11 unavailable")
    os.sched_setaffinity(0, affinity)
    env = dict(os.environ, ATEN_CPU_CAPABILITY="avx2", OMP_WAIT_POLICY="PASSIVE", OMP_NUM_THREADS="2",
               MKL_NUM_THREADS="2", OPENBLAS_NUM_THREADS="2", PYTHONUNBUFFERED="1",
               CELLDEV_PREDINFO_MONITOR_PID=str(os.getpid()))
    env.pop("CELLDEV_THREADS_FILE", None)
    enable_subreaper()
    expected_parent = os.getpid()
    start, reaped = time.monotonic(), child_usage()
    interrupted = []
    for signum in (signal.SIGINT, signal.SIGTERM):
        signal.signal(signum, lambda sig, frame: interrupted.append(sig))
    attempt = {"number": len(attempts) + 1, "monitor_pid": os.getpid(), "prior_cpu_seconds": prior,
               "monitor_start_ticks": proc_table()[os.getpid()]["start_ticks"]}
    attempts = [*attempts, attempt]
    record = {"status": "running", "cpu_seconds": prior, "cap_cpu_seconds": cap, "ready": ready,
              "attempts": attempts, "affinity": sorted(affinity), "worker_pid": None}
    save(path, record)
    reason, terminated_at, process = None, None, None
    log = (STUDY / ("calibration.log" if calibration else "measurement.log")).open("a")
    try:
        process = subprocess.Popen(command, cwd=ROOT, env=env, stdout=log, stderr=subprocess.STDOUT,
                                   start_new_session=True, preexec_fn=lambda: child_limits(cap - prior, reserve, expected_parent))
        identity = proc_table().get(process.pid)
        record.update(worker_pid=process.pid, worker_start_ticks=None if identity is None else identity["start_ticks"],
                      owned_process_groups=[process.pid])
        attempt.update(worker_pid=process.pid, worker_start_ticks=record["worker_start_ticks"])
        while True:
            code = process.poll()
            usage = child_usage() - reaped + process_group_cpu(process.pid)
            cpu = prior + usage + time.process_time()
            reason = reason or ("interrupted" if interrupted else None)
            if cpu >= cap - reserve:
                reason = "cpu_budget_exhausted"
            if reason and code is None:
                if terminated_at is None:
                    terminated_at = time.monotonic()
                sig = signal.SIGKILL if time.monotonic() - terminated_at >= 1 else signal.SIGTERM
                try:
                    os.killpg(process.pid, sig)
                except ProcessLookupError:
                    pass
            record.update(cpu_seconds=cpu, wall_seconds=time.monotonic() - start)
            if code is not None:
                cleanup_group(process)
                cpu = prior + child_usage() - reaped + process_group_cpu(process.pid) + time.process_time()
                record.update(cpu_seconds=cpu, wall_seconds=time.monotonic() - start)
                if cpu >= cap - reserve:
                    reason = "cpu_budget_exhausted"
                if reason is None:
                    reason = "complete" if code == 0 else "job_failed"
                attempt.update(exit_code=code, cpu_seconds=cpu - prior)
                record.update(status=reason, worker_pid=None)
            save(path, record)
            if code is not None:
                break
            time.sleep(0.1 if calibration else 0.5)
    except BaseException as error:
        if process is not None:
            try:
                cleanup_group(process)
            except BaseException as cleanup_error:
                record["cleanup_error"] = type(cleanup_error).__name__ + ": " + str(cleanup_error)
        cpu = prior + child_usage() - reaped + time.process_time()
        if process is not None:
            cpu += process_group_cpu(process.pid)
        record.update(status="monitor_failed", error=type(error).__name__, cpu_seconds=cpu, worker_pid=None)
        save(path, record)
        raise
    finally:
        log.close()
    raise SystemExit(0 if reason == "complete" else 1)


if __name__ == "__main__":
    main()
