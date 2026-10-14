"""Run the preregistered structural-operator comparison within 14400 CPU-seconds; dry-run by default."""

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
STUDY = ROOT / "outputs/autonomous_structural_20261013"
CAP, RESERVE = 14400, 20
HELPERS = ("taskvar_confirm.py", "taskvar_gradient.py", "taskvar_gates.py")


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n")
    temporary.replace(path)


def check_protocol():
    protocol = json.loads((STUDY / "protocol.json").read_text())
    if protocol["max_cpu_seconds"] != CAP or protocol["max_simulation_threads"] != 4:
        raise ValueError("registered resource limit differs")
    if protocol["runs"] != [51089, 51090] or protocol["generations"] != 16:
        raise ValueError("registered search scope differs")
    if protocol["structural_operators"] != {
        "dup_rate": 0.02,
        "del_rate": 0.01,
        "dup_split": False,
        "n_mut_scale": True,
        "existing_production_operators": True,
    }:
        raise ValueError("structural policy differs")
    for name, key in (("seed_audit.json", "seed_audit_sha256"), ("prepare.py", "prepare_sha256")):
        if sha(STUDY / name) != protocol[key]:
            raise ValueError(f"preparation input differs: {name}")
    for value in protocol["configs"].values():
        if sha(ROOT / value["path"]) != value["sha256"]:
            raise ValueError("prepared configuration differs")
    for relative, expected in protocol["source_identity"].items():
        if sha(ROOT / relative) != expected:
            raise ValueError(f"numerical/search source differs: {relative}")
    for name in ("founder", "pilot"):
        if sha(ROOT / protocol[name + "_file"]) != protocol[name + "_sha256"]:
            raise ValueError("fixed input genotype differs")
    for relative, expected in protocol["D_pins"].items():
        if sha(ROOT / protocol["D_study"] / relative) != expected:
            raise ValueError("fixed control protocol differs")
    return protocol


def check_ready():
    ready = json.loads((STUDY / "ready.json").read_text())
    for name, key in (
        ("run_budgeted.py", "monitor_sha256"),
        ("measure.py", "measurement_sha256"),
        ("protocol.json", "protocol_sha256"),
    ):
        if sha(STUDY / name) != ready[key]:
            raise ValueError(f"readiness pin differs: {name}")
    if set(ready["helpers"]) != set(HELPERS):
        raise ValueError("helper pins differ")
    for name, expected in ready["helpers"].items():
        if sha(ROOT / "scripts" / name) != expected:
            raise ValueError("measurement helper differs")
    return ready


def prerequisites(protocol):
    """Wait on completion, without reading any fitness outcome."""
    controls = [ROOT / protocol["D_study"], ROOT / "outputs/autonomous_frozen_20261013"]
    optional = ROOT / "outputs/autonomous_discrimination_20261013"
    if (optional / "ready.json").exists():
        controls.append(optional)
    for folder in controls:
        path = folder / "budget.json"
        if not path.exists():
            return False
        value = json.loads(path.read_text())
        if value["status"] in ("running", "waiting_for_workers"):
            return False
        if value["status"] != "complete":
            raise ValueError(f"predecessor stopped abnormally: {folder.name}")
        if value.get("running") or value.get("queued"):
            raise ValueError("completed predecessor still has active work")
    return True


def child_cpu():
    usage = resource.getrusage(resource.RUSAGE_CHILDREN)
    return usage.ru_utime + usage.ru_stime


def active_cpu(pid):
    # Include active compiler descendants as well as worker OpenMP threads.
    processes = {}
    for directory in Path("/proc").iterdir():
        if not directory.name.isdigit():
            continue
        try:
            fields = (directory / "stat").read_text().rsplit(")", 1)[1].split()
            processes[int(directory.name)] = (int(fields[1]), sum(int(fields[i]) for i in (11, 12, 13, 14)))
        except (FileNotFoundError, ProcessLookupError, PermissionError):
            continue
    pending, total = [pid], 0
    while pending:
        current = pending.pop()
        if current in processes:
            total += processes[current][1]
            pending.extend(child for child, (parent, _) in processes.items() if parent == current)
    return total / os.sysconf("SC_CLK_TCK")


def child_limit(seconds):
    libc = ctypes.CDLL(None)
    if libc.prctl(1, signal.SIGKILL, 0, 0, 0) != 0:
        raise OSError("cannot bind worker lifetime to monitor")
    if os.getppid() == 1:
        os._exit(1)
    hard = max(2, int(math.floor(seconds)))
    resource.setrlimit(resource.RLIMIT_CPU, (hard - 1, hard))


def stop(process):
    try:
        os.killpg(process.pid, signal.SIGTERM)
    except ProcessLookupError:
        pass


def kill(process):
    try:
        os.killpg(process.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass


def interrupt(signum, frame):
    raise KeyboardInterrupt(f"monitor interrupted by signal {signum}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", action="store_true")
    args = parser.parse_args()
    protocol = check_protocol()
    commands = {"neutrality": [str(ROOT / ".venv/bin/python"), str(STUDY / "measure.py"), "--mode", "neutrality"]}
    commands.update(
        {
            f"evolve_s{seed}": [
                str(ROOT / ".venv/bin/python"),
                "-m",
                "src.run",
                "--config",
                str(ROOT / protocol["configs"][str(seed)]["path"]),
            ]
            for seed in protocol["runs"]
        }
    )
    commands["confirmation"] = [str(ROOT / ".venv/bin/python"), str(STUDY / "measure.py"), "--mode", "confirm"]
    if not args.run:
        print(
            json.dumps(
                {
                    "status": "dry_run",
                    "commands": commands,
                    "max_cpu_seconds": CAP,
                    "planned_genome_lives": protocol["planned_genome_lives"],
                    "neutrality_validation_lives": 18,
                    "simulated_lives": 0,
                    "workdir": str(STUDY),
                },
                indent=2,
            )
        )
        return
    check_ready()
    status_path = STUDY / "budget.json"
    if status_path.exists():
        raise ValueError("budget record exists: reconcile consumed resources before any restart")
    if any((STUDY / folder).exists() for folder in ("runs", "confirmation", "neutrality")):
        raise ValueError("unaccounted run artifacts exist before launch")
    while not prerequisites(protocol):
        save(
            status_path,
            {
                "status": "waiting_for_workers",
                "cpu_seconds": child_cpu(),
                "cap_cpu_seconds": CAP,
                "running": {},
                "queued": ["neutrality", "evolve_s51089", "evolve_s51090", "confirmation"],
            },
        )
        time.sleep(2)
    check_protocol()
    check_ready()
    affinity = os.sched_getaffinity(0).intersection(range(12))
    if not affinity:
        raise ValueError("fast CPUs0-11 unavailable")
    os.sched_setaffinity(0, affinity)
    env = dict(
        os.environ,
        ATEN_CPU_CAPABILITY="avx2",
        OMP_WAIT_POLICY="PASSIVE",
        OMP_NUM_THREADS="2",
        MKL_NUM_THREADS="2",
        CELL_DEV_CACHE=str(ROOT / "outputs/e1_resume/kernel-cache"),
        PYTHONUNBUFFERED="1",
    )
    env.pop("CELLDEV_THREADS_FILE", None)
    queue, running, completed = ["neutrality"], {}, []
    phase, reason, stop_time = "neutrality", None, None
    start = time.monotonic()
    old_handler = signal.signal(signal.SIGTERM, interrupt)
    try:
        while queue or running:
            consumed = child_cpu() + sum(active_cpu(pid) for pid in running)
            if consumed >= CAP - RESERVE:
                reason = reason or "cpu_budget_exhausted"
            for pid, (_, _, name) in running.items():
                if name == "neutrality" and active_cpu(pid) >= 26:
                    reason = reason or "neutrality_budget_exhausted"
            if reason:
                queue.clear()
                if stop_time is None:
                    stop_time = time.monotonic()
                    for process, _, _ in running.values():
                        stop(process)
                if time.monotonic() - stop_time >= 2:
                    for process, _, _ in running.values():
                        kill(process)
            while queue and len(running) < 2 and not reason:
                name = queue.pop(0)
                check_protocol()
                check_ready()
                log_path = STUDY / "logs" / f"{name}.log"
                log_path.parent.mkdir(parents=True, exist_ok=True)
                log = log_path.open("a")
                remaining = min(30, CAP - consumed) if name == "neutrality" else CAP - consumed
                process = subprocess.Popen(
                    commands[name],
                    cwd=ROOT,
                    env=env,
                    stdout=log,
                    stderr=subprocess.STDOUT,
                    start_new_session=True,
                    preexec_fn=lambda limit=remaining: child_limit(limit),
                )
                running[process.pid] = (process, log, name)
                print(f"Started {name}: pid {process.pid}", flush=True)
            for pid, (process, log, name) in list(running.items()):
                code = process.poll()
                if code is not None:
                    log.close()
                    completed.append({"name": name, "exit_code": code})
                    del running[pid]
                    if code:
                        reason = reason or "job_failed"
            if not running and not queue and not reason:
                if phase == "neutrality":
                    result = json.loads((STUDY / "neutrality/report.json").read_text())
                    if result["status"] != "complete" or result["genome_lives"] != 18 or result["cpu_seconds"] > 30:
                        raise ValueError("neutrality validation did not finish under its cap")
                    queue = ["evolve_s51089", "evolve_s51090"]
                    phase = "search"
                elif phase == "search":
                    queue = ["confirmation"]
                    phase = "confirmation"
                else:
                    result = json.loads((STUDY / "confirmation/report.json").read_text())
                    if result["status"] != "complete":
                        raise ValueError("confirmation did not complete")
            consumed = child_cpu() + sum(active_cpu(pid) for pid in running)
            if consumed >= CAP:
                reason = reason or "cpu_budget_exhausted"
                queue.clear()
            save(
                status_path,
                {
                    "status": reason or ("running" if running or queue else "complete"),
                    "cpu_seconds": consumed,
                    "cap_cpu_seconds": CAP,
                    "wall_seconds": time.monotonic() - start,
                    "running": {str(pid): entry[2] for pid, entry in running.items()},
                    "queued": queue,
                    "completed": completed,
                    "phase": phase,
                    "affinity": sorted(affinity),
                },
            )
            if running or queue:
                time.sleep(2)
    except BaseException as error:
        reason = reason or "monitor_failed"
        for process, _, _ in running.values():
            stop(process)
        deadline = time.monotonic() + 2
        for process, log, _ in running.values():
            try:
                process.wait(timeout=max(0, deadline - time.monotonic()))
            except subprocess.TimeoutExpired:
                kill(process)
                process.wait()
            log.close()
        save(
            status_path,
            {
                "status": reason,
                "cpu_seconds": child_cpu(),
                "cap_cpu_seconds": CAP,
                "wall_seconds": time.monotonic() - start,
                "error": type(error).__name__,
                "running": {},
                "queued": [],
                "completed": completed,
            },
        )
        raise
    finally:
        signal.signal(signal.SIGTERM, old_handler)
    raise SystemExit(1 if reason else 0)


if __name__ == "__main__":
    main()
