"""Wait for J/K, then run two fixed s7 continuations under one 14400-worker-CPU-second cap."""
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
STUDY = ROOT / "outputs/autonomous_s7_20261014"
CAP, RESERVE, POLL = 14400, 20, 1
RUNS = (51891, 51892)
HELPERS = ("taskvar_confirm.py", "taskvar_gradient.py", "taskvar_gates.py")
DEPENDENCIES = ("outputs/autonomous_duplicate_use_20261014", "outputs/autonomous_traces_20261014")


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n")
    temporary.replace(path)


def dependencies(protocol):
    paths = protocol["wait_for_studies"]
    if len(paths) != 2 or set(paths) != set(DEPENDENCIES):
        raise ValueError("registered J/K dependency set differs")
    return paths


def check_protocol():
    protocol = json.loads((STUDY / "protocol.json").read_text())
    expected = {"max_cpu_seconds": CAP, "max_simulation_threads": 4, "runs": list(RUNS), "generations": 16,
                "planned_genome_lives": 36012, "confirmation_genome_lives": 3072}
    if any(protocol[key] != value for key, value in expected.items()):
        raise ValueError("registered search/resource scope differs")
    dependencies(protocol)
    for name, key in (("seed_audit.json", "seed_audit_sha256"), ("prepare.py", "prepare_sha256"),
                      ("initialization.json", "initialization_audit_sha256")):
        if sha(STUDY / name) != protocol[key]:
            raise ValueError("preparation input differs: " + name)
    initial = json.loads((STUDY / "initialization.json").read_text())["runs"]
    if set(initial) != {str(seed) for seed in RUNS}:
        raise ValueError("initialization run set differs")
    for seed, record in initial.items():
        if record["population_file"] != f"initialization/s{seed}.npy":
            raise ValueError("initialization population path differs")
        if sha(STUDY / record["population_file"]) != record["file_sha256"]:
            raise ValueError("initialization population differs")
    if set(protocol["configs"]) != {str(seed) for seed in RUNS}:
        raise ValueError("prepared configuration set differs")
    for value in protocol["configs"].values():
        if sha(ROOT / value["path"]) != value["sha256"]:
            raise ValueError("prepared configuration differs")
    for relative, expected in protocol["source_identity"].items():
        if sha(ROOT / relative) != expected:
            raise ValueError("numerical/search source differs: " + relative)
    for name in ("founder", "pilot"):
        if sha(ROOT / protocol[name + "_file"]) != protocol[name + "_sha256"]:
            raise ValueError("fixed input genotype differs")
    for group, directory in (("inputs", STUDY), ("reference_sources", STUDY), ("template_pins", ROOT)):
        for relative, expected in protocol[group].items():
            if sha(directory / relative) != expected:
                raise ValueError(group + " source differs: " + relative)
    if set(protocol["helpers"]) != set(HELPERS):
        raise ValueError("protocol helper pin set differs")
    for name, expected in protocol["helpers"].items():
        if sha(ROOT / "scripts" / name) != expected:
            raise ValueError("protocol measurement helper differs")
    return protocol


def check_ready():
    protocol = check_protocol()
    ready = json.loads((STUDY / "ready.json").read_text())
    for name, key in (("run_budgeted.py", "runner_sha256"), ("measure.py", "measurement_sha256"),
                      ("protocol.json", "protocol_sha256")):
        if sha(STUDY / name) != ready[key]:
            raise ValueError("readiness pin differs: " + name)
    if ready["helpers"] != protocol["helpers"]:
        raise ValueError("helper pin set differs")
    for name, expected in ready["helpers"].items():
        if sha(ROOT / "scripts" / name) != expected:
            raise ValueError("measurement helper differs")
    if set(ready["dependencies"]) != set(dependencies(protocol)):
        raise ValueError("dependency readiness pin set differs")
    for path, files in ready["dependencies"].items():
        if set(files) != {"protocol.json", "run_budgeted.py"}:
            raise ValueError("dependency source pin set differs")
        for name, digest in files.items():
            if sha(ROOT / path / name) != digest:
                raise ValueError("dependency source differs: " + path + "/" + name)
    return ready


def prerequisites(protocol):
    """Read only scheduling status, and inspect both dependencies even when one remains active."""
    complete = True
    for folder in dependencies(protocol):
        path = ROOT / folder / "budget.json"
        if not path.exists():
            complete = False
            continue
        value = json.loads(path.read_text())
        if value["status"] in ("running", "waiting_for_workers"):
            complete = False
            continue
        if value["status"] != "complete":
            raise ValueError("predecessor stopped abnormally: " + folder)
        if value.get("running") or value.get("queued"):
            raise ValueError("completed predecessor still has active work")
    return complete


def child_cpu():
    usage = resource.getrusage(resource.RUSAGE_CHILDREN)
    return usage.ru_utime + usage.ru_stime


def active_cpu(pid):
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


def consumed_cpu(running):
    return child_cpu() + sum(active_cpu(pid) for pid in running)


def child_limit(seconds, parent_pid):
    if ctypes.CDLL(None).prctl(1, signal.SIGKILL, 0, 0, 0) != 0:
        raise OSError("cannot bind worker lifetime to monitor")
    if os.getppid() != parent_pid:
        os._exit(1)
    hard = max(2, int(math.floor(seconds)))
    resource.setrlimit(resource.RLIMIT_CPU, (hard - 1, hard))


def send_signal(process, signum):
    try:
        os.killpg(process.pid, signum)
    except ProcessLookupError:
        pass


def cleanup(running):
    for process, _, _ in running.values():
        send_signal(process, signal.SIGTERM)
    deadline = time.monotonic() + 2
    for process, log, _ in running.values():
        try:
            process.wait(timeout=max(0, deadline - time.monotonic()))
        except subprocess.TimeoutExpired:
            send_signal(process, signal.SIGKILL)
            process.wait()
        log.close()
    running.clear()


def interrupt(signum, frame):
    raise KeyboardInterrupt(f"monitor interrupted by signal {signum}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", action="store_true")
    args = parser.parse_args()
    protocol = check_protocol()
    commands = {f"evolve_s{seed}": [str(ROOT / ".venv/bin/python"), "-m", "src.run", "--config",
                                   str(ROOT / protocol["configs"][str(seed)]["path"])] for seed in RUNS}
    commands["confirmation"] = [str(ROOT / ".venv/bin/python"), str(STUDY / "measure.py"), "--confirm-child"]
    if not args.run:
        print(json.dumps({"status": "dry_run", "commands": commands, "max_cpu_seconds": CAP,
                          "planned_genome_lives": 36012, "max_simulation_threads": 4,
                          "confirmation_threads": 2, "wait_for": list(DEPENDENCIES), "simulated_lives": 0}, indent=2))
        return
    ready = check_ready()
    status_path = STUDY / "budget.json"
    if status_path.exists():
        raise ValueError("budget record exists: no automatic resource reset or restart")
    if any((STUDY / folder).exists() for folder in ("runs", "confirmation", "logs")):
        raise ValueError("unaccounted run artifacts exist before launch")
    running, completed, queue = {}, [], [f"evolve_s{seed}" for seed in RUNS]
    phase, reason, stop_time = "waiting", None, None
    start, affinity = time.monotonic(), set()
    old_handler = signal.signal(signal.SIGTERM, interrupt)

    def record(status, **extra):
        save(status_path, {"status": status, "cpu_seconds": consumed_cpu(running), "cap_cpu_seconds": CAP,
             "wall_seconds": time.monotonic() - start,
             "running": {str(pid): entry[2] for pid, entry in running.items()},
             "queued": list(queue), "completed": completed, "phase": phase, "affinity": sorted(affinity),
             "ready": ready, **extra})

    def unchanged():
        if check_protocol() != protocol or check_ready() != ready:
            raise ValueError("readiness or protocol changed while waiting/running")

    try:
        while not prerequisites(protocol):
            record("waiting_for_workers")
            time.sleep(POLL)
        unchanged()
        affinity = os.sched_getaffinity(0).intersection(range(12))
        if not affinity:
            raise ValueError("fast CPUs0-11 unavailable")
        os.sched_setaffinity(0, affinity)
        env = dict(os.environ, ATEN_CPU_CAPABILITY="avx2", OMP_WAIT_POLICY="PASSIVE", OMP_NUM_THREADS="2",
                   MKL_NUM_THREADS="2", OPENBLAS_NUM_THREADS="2", PYTHONUNBUFFERED="1",
                   CELL_DEV_CACHE=str(ROOT / "outputs/e1_resume/kernel-cache"))
        env.pop("CELLDEV_THREADS_FILE", None)
        phase = "search"
        record("running")  # Establish the non-resettable resource record before creating any worker.
        while queue or running:
            consumed = consumed_cpu(running)
            if consumed >= CAP - RESERVE:
                reason = reason or "cpu_budget_exhausted"
            if reason:
                queue.clear()
                if stop_time is None:
                    stop_time = time.monotonic()
                    for process, _, _ in running.values():
                        send_signal(process, signal.SIGTERM)
                if time.monotonic() - stop_time >= 2:
                    for process, _, _ in running.values():
                        send_signal(process, signal.SIGKILL)
            while queue and len(running) < 2 and not reason:
                unchanged()
                consumed = consumed_cpu(running)
                if consumed >= CAP - RESERVE:
                    reason = "cpu_budget_exhausted"
                    break
                name = queue.pop(0)
                log_path = STUDY / "logs" / f"{name}.log"
                log_path.parent.mkdir(parents=True, exist_ok=True)
                log = log_path.open("a")
                remaining, parent_pid = CAP - consumed, os.getpid()
                try:
                    process = subprocess.Popen(commands[name], cwd=ROOT, env=env, stdout=log,
                        stderr=subprocess.STDOUT, start_new_session=True,
                        preexec_fn=lambda limit=remaining, parent=parent_pid: child_limit(limit, parent))
                except BaseException:
                    log.close()
                    raise
                running[process.pid] = (process, log, name)
                print(f"Started {name}: pid {process.pid}", flush=True)
            for pid, (process, log, name) in list(running.items()):
                code = process.poll()
                if code is not None:
                    log.close()
                    completed.append({"name": name, "exit_code": code})
                    del running[pid]
                    if code:
                        reason = reason or ("cpu_budget_exhausted" if code in (-signal.SIGXCPU, -signal.SIGKILL)
                                            else "job_failed")
            if consumed_cpu(running) >= CAP:
                reason = reason or "cpu_budget_exhausted"
                queue.clear()
            if not running and not queue and not reason:
                if phase == "search":
                    queue, phase = ["confirmation"], "confirmation"
                else:
                    unchanged()
                    result = json.loads((STUDY / "confirmation/report.json").read_text())
                    if result["status"] != "complete" or result["genome_lives"] != 3072:
                        raise ValueError("fixed confirmation did not complete all prescribed lives")
            record("running" if running or queue else ("incomplete" if reason else "complete"),
                   reason=reason, exit_code=1 if reason else (None if running or queue else 0))
            if running or queue:
                time.sleep(POLL)
    except BaseException as error:
        cleanup(running)
        queue.clear()
        record("monitor_failed", reason=reason, error=type(error).__name__, exit_code=1)
        raise
    finally:
        if running:
            cleanup(running)
        signal.signal(signal.SIGTERM, old_handler)
    raise SystemExit(1 if reason else 0)


if __name__ == "__main__":
    main()
