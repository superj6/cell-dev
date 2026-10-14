"""Wait for L completion, then run M under a cumulative 1800-worker-CPU-second cap."""
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
STUDY = ROOT / "outputs/autonomous_gene_interaction_20261014"
CAP, STOP, POLL = 1800, 1788, 1
DEPENDENCIES = ("outputs/autonomous_s7_20261014",)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n")
    temporary.replace(path)


def check_ready():
    from measure import check_protocol

    protocol = check_protocol()
    dependencies(protocol)
    ready = json.loads((STUDY / "ready.json").read_text())
    if set(ready["files"]) != {"run_budgeted.py", "measure.py", "protocol.json"}:
        raise ValueError("readiness file pin set differs")
    for name in ("run_budgeted.py", "measure.py", "protocol.json"):
        if sha(STUDY / name) != ready["files"][name]:
            raise ValueError("readiness pin differs: " + name)
    if set(ready["dependencies"]) != set(protocol["wait_for_studies"]):
        raise ValueError("dependency readiness pin set differs")
    for path, files in ready["dependencies"].items():
        if set(files) != {"protocol.json", "run_budgeted.py"}:
            raise ValueError("dependency source pin set differs")
        for name, digest in files.items():
            if sha(ROOT / path / name) != digest:
                raise ValueError("dependency source differs: " + path + "/" + name)
    return ready


def dependencies(protocol):
    paths = protocol["wait_for_studies"]
    if len(paths) != 1 or set(paths) != set(DEPENDENCIES):
        raise ValueError("registered L dependency set differs")
    return paths


def dependency_available():
    protocol = json.loads((STUDY / "protocol.json").read_text())
    complete = True
    for name in dependencies(protocol):
        path = ROOT / name / "budget.json"
        if not path.exists():
            complete = False
            continue
        value = json.loads(path.read_text())
        if value["status"] in ("running", "waiting_for_workers"):
            complete = False
            continue
        if value["status"] != "complete":
            raise ValueError("dependency stopped abnormally; inspect before M launch")
        if value.get("running") or value.get("queued"):
            raise ValueError("completed dependency still records active work")
    return complete


def cpu(pid=None):
    own = resource.getrusage(resource.RUSAGE_SELF)
    usage = resource.getrusage(resource.RUSAGE_CHILDREN)
    total = own.ru_utime + own.ru_stime + usage.ru_utime + usage.ru_stime
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


def child_limit(seconds, parent_pid):
    if ctypes.CDLL(None).prctl(1, signal.SIGKILL, 0, 0, 0) != 0:
        raise OSError("cannot bind worker lifetime to monitor")
    if os.getppid() != parent_pid:
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
        process.wait(timeout=2)
    except subprocess.TimeoutExpired:
        pass
    # The direct child may have exited while one of its descendants ignored TERM.
    try:
        os.killpg(process.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass
    return process.wait()


def interrupt(signum, frame):
    raise KeyboardInterrupt(f"monitor interrupted by signal {signum}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", action="store_true")
    args = parser.parse_args()
    if not args.run:
        print(json.dumps({"status": "dry_run", "genome_lives": 2048, "max_cpu_seconds": CAP,
                          "threads": 2, "wait_for": "L complete", "simulated_lives": 0}))
        return
    ready = check_ready()
    status = STUDY / "budget.json"
    if status.exists():
        raise ValueError("budget record exists: no automatic resource reset or restart")
    if (STUDY / "measurement").exists() or (STUDY / "run.log").exists():
        raise ValueError("measurement artifacts exist without resource accounting")
    start, stopped, process = time.monotonic(), False, None
    old_handler = signal.signal(signal.SIGTERM, interrupt)
    affinity = set()
    try:
        while not dependency_available():
            if cpu() >= STOP:
                raise ValueError("waiting exhausted the available CPU budget")
            save(status, {"status": "waiting_for_workers", "cpu_seconds": cpu(), "cap_cpu_seconds": CAP,
                          "running": {}, "queued": ["measurement"], "ready": ready})
            time.sleep(POLL)
        if check_ready() != ready:
            raise ValueError("readiness changed while waiting")
        affinity = os.sched_getaffinity(0).intersection(range(12))
        if not affinity:
            raise ValueError("fast CPUs0-11 unavailable")
        os.sched_setaffinity(0, affinity)
        env = dict(os.environ, ATEN_CPU_CAPABILITY="avx2", OMP_WAIT_POLICY="PASSIVE", OMP_NUM_THREADS="2",
                   MKL_NUM_THREADS="2", OPENBLAS_NUM_THREADS="2", PYTHONUNBUFFERED="1",
                   CELL_DEV_CACHE=str(ROOT / "outputs/e1_resume/kernel-cache"))
        env.pop("CELLDEV_THREADS_FILE", None)
        command = [str(ROOT / ".venv/bin/python"), str(STUDY / "measure.py"), "--run"]
        remaining, parent_pid = CAP - cpu(), os.getpid()
        if remaining <= CAP - STOP:
            raise ValueError("insufficient cumulative CPU remains before launch")
        # Persist ownership before Popen; a crash must never permit an unaccounted restart.
        save(status, {"status": "running", "cpu_seconds": cpu(), "cap_cpu_seconds": CAP,
                      "running": {}, "queued": ["measurement"], "ready": ready})
        with (STUDY / "run.log").open("a") as log:
            process = subprocess.Popen(command, cwd=ROOT, env=env, stdout=log, stderr=subprocess.STDOUT,
                                       start_new_session=True,
                                       preexec_fn=lambda: child_limit(remaining, parent_pid))
            while process.poll() is None:
                consumed = cpu(process.pid)
                if consumed >= STOP:
                    stopped = True
                    terminate(process)
                save(status, {"status": "cpu_budget_exhausted" if stopped else "running",
                              "cpu_seconds": consumed, "cap_cpu_seconds": CAP,
                              "wall_seconds": time.monotonic() - start,
                              "running": {} if stopped else {str(process.pid): "measurement"}, "queued": [],
                              "affinity": sorted(affinity), "ready": ready})
                if not stopped:
                    time.sleep(POLL)
        report = STUDY / "measurement/report.json"
        result = json.loads(report.read_text()) if report.exists() else {}
        complete = result.get("status") == "complete" and result.get("research_genome_lives") == 2048
        if check_ready() != ready:
            raise ValueError("readiness changed during measurement")
    except BaseException as error:
        if process is not None and process.poll() is None:
            terminate(process)
        save(status, {"status": "monitor_failed", "cpu_seconds": cpu(), "cap_cpu_seconds": CAP,
                      "error": type(error).__name__, "wall_seconds": time.monotonic() - start,
                      "running": {}, "queued": [], "ready": ready})
        raise
    finally:
        if process is not None and process.poll() is None:
            terminate(process)
        signal.signal(signal.SIGTERM, old_handler)
    consumed = cpu()
    exhausted = stopped or process.returncode in (-signal.SIGXCPU, -signal.SIGKILL) or consumed >= CAP
    success = process.returncode == 0 and complete and not exhausted
    save(status, {"status": "complete" if success else "incomplete", "cpu_seconds": consumed,
                  "cap_cpu_seconds": CAP, "cpu_budget_exhausted": exhausted, "exit_code": process.returncode,
                  "wall_seconds": time.monotonic() - start, "running": {}, "queued": [],
                  "affinity": sorted(affinity), "ready": ready})
    raise SystemExit(0 if success else 1)


if __name__ == "__main__":
    main()
