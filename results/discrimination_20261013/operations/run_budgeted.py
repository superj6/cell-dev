"""Two-worker discrimination measurement under one cumulative1800 CPU-second cap; dry-run by default."""
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
CAP, RESERVE = 1800, 10


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def save(path, value):
    temp = path.with_suffix(".tmp")
    with temp.open("w") as stream:
        stream.write(json.dumps(value, indent=2, allow_nan=False) + "\n")
        stream.flush()
        os.fsync(stream.fileno())
    temp.replace(path)


def readiness():
    path = STUDY / "ready.json"
    if not path.exists():
        raise ValueError("not released: root must register F and create ready.json")
    ready = json.loads(path.read_text())
    for name in ("protocol.json", "measure.py", "run_budgeted.py"):
        if ready[name] != sha(STUDY / name):
            raise ValueError("readiness source or protocol pin changed")
    return ready


def prior_usage(path, resume):
    if not path.exists():
        if resume:
            raise ValueError("--resume requires an existing finalized budget record")
        return 0.0, []
    saved = json.loads(path.read_text())
    if not resume:
        raise ValueError("existing budget record; explicit --resume is required")
    if saved["status"] == "running":
        raise ValueError("unfinalized prior monitor: CPU use must be reconciled before resuming")
    if saved["status"] == "complete":
        raise ValueError("study is already complete; no rescore is allowed")
    if saved["ready"] != readiness() or saved["cap_cpu_seconds"] != CAP:
        raise ValueError("prior budget source pins or cap changed")
    total = saved["cpu_seconds"]
    if not math.isfinite(total) or total < 0:
        raise ValueError("invalid cumulative CPU accounting")
    return float(total), saved["attempts"]


def child_usage():
    use = resource.getrusage(resource.RUSAGE_CHILDREN)
    return use.ru_utime + use.ru_stime


def process_tree_cpu(root_pid):
    """Include compiler descendants and waited child CPU, alongside all worker OpenMP threads."""
    processes = {}
    for directory in Path("/proc").iterdir():
        if not directory.name.isdigit():
            continue
        try:
            fields = (directory / "stat").read_text().rsplit(")", 1)[1].split()
            processes[int(directory.name)] = (int(fields[1]), sum(int(fields[i]) for i in (11, 12, 13, 14)))
        except (FileNotFoundError, ProcessLookupError, PermissionError):
            continue
    pending, total = [root_pid], 0
    while pending:
        pid = pending.pop()
        if pid in processes:
            total += processes[pid][1]
            pending.extend(child for child, (parent, _) in processes.items() if parent == pid)
    return total / os.sysconf("SC_CLK_TCK")


def child_limits(remaining):
    # A monitor death stops the worker rather than leaving simulations running unobserved.
    libc = ctypes.CDLL(None)
    if libc.prctl(1, signal.SIGKILL, 0, 0, 0) != 0:  # Linux PR_SET_PDEATHSIG
        raise OSError("cannot bind worker lifetime to CPU monitor")
    if os.getppid() == 1:
        os._exit(1)
    soft = max(1, int(math.floor(remaining - RESERVE)))
    resource.setrlimit(resource.RLIMIT_CPU, (soft, soft + 1))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", action="store_true")
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args()
    protocol = json.loads((STUDY / "protocol.json").read_text())
    command = [str(ROOT / ".venv/bin/python"), str(STUDY / "measure.py"), "--worker"]
    if not args.run:
        print(json.dumps({"status": "dry_run", "candidate_lives": protocol["candidate_lives"],
                          "max_cpu_seconds": CAP, "threads": 2, "command": command}))
        return
    ready = readiness()
    path = STUDY / "budget.json"
    prior, attempts = prior_usage(path, args.resume)
    if prior >= CAP - RESERVE:
        raise ValueError("original study CPU budget is exhausted")
    if not path.exists() and (STUDY / "manifest.json").exists():
        raise ValueError("scientific checkpoints exist without their cumulative budget record")
    affinity = os.sched_getaffinity(0).intersection(range(12))
    if not affinity:
        raise ValueError("registered fast CPUs0–11 unavailable")
    os.sched_setaffinity(0, affinity)
    env = dict(os.environ, ATEN_CPU_CAPABILITY="avx2", OMP_WAIT_POLICY="PASSIVE", OMP_NUM_THREADS="2",
               MKL_NUM_THREADS="2", OPENBLAS_NUM_THREADS="2", PYTHONUNBUFFERED="1",
               CELLDEV_DISCRIM_MONITOR_PID=str(os.getpid()))
    env.pop("CELLDEV_THREADS_FILE", None)
    start, own_cpu, reaped = time.monotonic(), time.process_time(), child_usage()
    interrupted = []
    for signum in (signal.SIGINT, signal.SIGTERM):
        signal.signal(signum, lambda sig, frame: interrupted.append(sig))
    attempt = {"number": len(attempts) + 1, "monitor_pid": os.getpid(), "prior_cpu_seconds": prior}
    attempts = [*attempts, attempt]
    record = {"status": "running", "cpu_seconds": prior, "cap_cpu_seconds": CAP, "ready": ready,
              "attempts": attempts, "affinity": sorted(affinity), "worker_pid": None}
    save(path, record)
    reason, terminated_at, process = None, None, None
    log = (STUDY / "measurement.log").open("a")
    try:
        process = subprocess.Popen(command, cwd=ROOT, env=env, stdout=log, stderr=subprocess.STDOUT,
                                   start_new_session=True, preexec_fn=lambda: child_limits(CAP - prior))
        record["worker_pid"] = process.pid
        while True:
            code = process.poll()
            usage = child_usage() - reaped + (0 if code is not None else process_tree_cpu(process.pid))
            cpu = prior + usage + time.process_time() - own_cpu
            reason = reason or ("interrupted" if interrupted else None)
            if cpu >= CAP - RESERVE:
                reason = "cpu_budget_exhausted"
            if reason and code is None:
                if terminated_at is None:
                    terminated_at = time.monotonic()
                sig = signal.SIGKILL if time.monotonic() - terminated_at >= 2 else signal.SIGTERM
                try:
                    os.killpg(process.pid, sig)
                except ProcessLookupError:
                    pass
            record.update(cpu_seconds=cpu, wall_seconds=time.monotonic() - start)
            if code is not None:
                if reason is None:
                    reason = "complete" if code == 0 else "job_failed"
                attempt.update(exit_code=code, cpu_seconds=cpu - prior)
                record.update(status=reason, worker_pid=None)
            save(path, record)
            if code is not None:
                break
            time.sleep(0.5)
    finally:
        if process is not None and process.poll() is None:
            os.killpg(process.pid, signal.SIGKILL)
            process.wait()
        log.close()
    raise SystemExit(0 if reason == "complete" else 1)


if __name__ == "__main__":
    main()
