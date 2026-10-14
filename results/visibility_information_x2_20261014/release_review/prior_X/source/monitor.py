"""First-attempt visibility measurement: dry-run unless explicitly released and run.

Validation (including compilation) and research share one cumulative CPU ledger.
Only fixed external measurement workers are launched; no organism behavior is added.
"""
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
CAP, VALIDATION_CAP, MARGIN, POLL = 3600, 180, 10, 0.25
WORLDS = ("flash5_dim25", "blink20")
ROLES = ("R0", "R1", "I", "A", "B", *(f"D{i}" for i in range(8)))
SCOPE = {"total_cpu_seconds": CAP, "validation_cpu_seconds": VALIDATION_CAP,
         "max_workers": 2, "threads_per_worker": 1, "research_lives": 13312,
         "validation_lives": 82, "worlds": list(WORLDS), "roles": list(ROLES)}
ARTIFACTS = ("attempt.json", "budget.json", "validation_budget.json", "validation", "rows", "logs", "build-cache")


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w") as stream:
        stream.write(json.dumps(value, indent=2, allow_nan=False) + "\n")
        stream.flush()
        os.fsync(stream.fileno())
    temporary.replace(path)


def pinned_path(base, name):
    path = (base / name).resolve()
    if not isinstance(name, str) or Path(name).is_absolute() or not path.is_relative_to(base.resolve()):
        raise ValueError("pin must name a file within its declared source root")
    return path


def check_pins(base, pins):
    if not isinstance(pins, dict) or not pins:
        raise ValueError("required source pins are empty")
    for name, digest in pins.items():
        if sha(pinned_path(base, name)) != digest:
            raise ValueError("source pin differs: " + name)


def check_protocol():
    protocol = read(STUDY / "protocol.json")
    if protocol.get("monitor_scope") != SCOPE:
        raise ValueError("registered simulation/resource scope differs")
    if set(protocol["worlds"]) != set(WORLDS):
        raise ValueError("registered worlds differ")
    if len(protocol["seeds"]) != 512 or len(set(protocol["seeds"])) != 512:
        raise ValueError("research seeds must contain 512 distinct fixed life IDs")
    if any(type(seed) is not int or seed < 0 for seed in protocol["seeds"]):
        raise ValueError("research life IDs must be unsigned integers")
    for world in WORLDS:
        if [item["role"] for item in protocol["worlds"][world]["candidates"]] != list(ROLES):
            raise ValueError("registered candidate role order differs")
    check_pins(STUDY, protocol["file_pins"])
    if protocol.get("production_binding", {}).get("status") != "complete":
        raise ValueError("production ABI4 binding is incomplete")
    check_pins(ROOT, protocol["production_pins"])
    return protocol


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
    receipt = read(STUDY / "resource_clearance.json")
    if receipt.get("status") != "cleared" or receipt.get("all_processes_exited") is not True:
        raise ValueError("root resource clearance is absent")
    check_pins(ROOT, receipt["budget_pins"])
    for name in receipt["budget_pins"]:
        budget = read(pinned_path(ROOT, name))
        if budget.get("status") not in ("complete", "incomplete", "cpu_budget_exhausted", "job_failed",
                                        "interrupted", "monitor_failed"):
            raise ValueError("a dependency budget is not terminal")
        if budget.get("cleanup_error") or budget.get("running") or budget.get("queued"):
            raise ValueError("a dependency has unresolved cleanup or queues")
    if not receipt.get("processes") or not receipt.get("process_groups"):
        raise ValueError("resource clearance lacks prior process identities")
    if any(type(group) is not int or group <= 0 for group in receipt["process_groups"]):
        raise ValueError("invalid prior process group")
    table = proc_table()
    for identity in receipt["processes"]:
        if type(identity.get("pid")) is not int or type(identity.get("start_ticks")) is not int:
            raise ValueError("invalid prior process identity")
        row = table.get(identity["pid"])
        if row and row["start_ticks"] == identity["start_ticks"]:
            raise ValueError("a cleared process remains alive")
    if any(row["pgrp"] in receipt["process_groups"] for row in table.values()):
        raise ValueError("a cleared process group remains alive")
    return receipt


def check_ready(protocol):
    ready = read(STUDY / "ready.json")
    if ready.get("status") != "released":
        raise ValueError("root has not released the study")
    required = {"protocol.json", "monitor.py", "measure.py", "validate.py", "resource_clearance.json"}
    if not required.issubset(ready["source_pins"]):
        raise ValueError("release lacks required source pins")
    if any(ready["source_pins"].get(name) != digest for name, digest in protocol["file_pins"].items()):
        raise ValueError("release does not bind every frozen study input")
    check_pins(STUDY, ready["source_pins"])
    if ready.get("production_pins") != protocol["production_pins"]:
        raise ValueError("release production pins differ")
    check_pins(ROOT, ready["production_pins"])
    resource_clearance()
    return ready


def check_validation(protocol):
    report = read(STUDY / "validation/report.json")
    if (report.get("status") != "complete" or report.get("simulation_calls") != 82
            or report.get("protocol_sha256") != sha(STUDY / "protocol.json")
            or report.get("source_pins") != protocol["file_pins"]
            or report.get("production_pins") != protocol["production_pins"]):
        raise ValueError("fixed validation package is incomplete or unpinned")
    return report


def check_validation_budget(protocol, expected_cpu):
    check_validation(protocol)
    value = read(STUDY / "validation_budget.json")
    if (value.get("status") != "complete" or value.get("cpu_seconds") != expected_cpu
            or value.get("cap_cpu_seconds") != VALIDATION_CAP
            or value.get("report_sha256") != sha(STUDY / "validation/report.json")
            or value.get("protocol_sha256") != sha(STUDY / "protocol.json")
            or expected_cpu is None or not 0 <= expected_cpu < VALIDATION_CAP - MARGIN):
        raise ValueError("validation receipt changed during research")
    return value


def check_world(world, protocol):
    folder = STUDY / "rows" / world
    report = read(folder / "complete.json")
    protocol_sha = sha(STUDY / "protocol.json")
    if (report.get("status") != "complete" or report.get("world") != world
            or report.get("protocol_sha256") != protocol_sha or report.get("roles") != list(ROLES)
            or report.get("simulation_calls") != 6656):
        raise ValueError("world measurement is incomplete or unpinned")
    expected = {role + "/checkpoint.json" for role in ROLES}
    if set(report["checkpoint_pins"]) != expected:
        raise ValueError("world completion does not include every registered row")
    check_pins(folder, report["checkpoint_pins"])
    for candidate in protocol["worlds"][world]["candidates"]:
        row = folder / candidate["role"]
        checkpoint = read(row / "checkpoint.json")
        identity = {"protocol_sha256": protocol_sha, "world": world, "candidate": candidate,
                    "seeds": protocol["seeds"]}
        if checkpoint.get("identity") != identity or checkpoint.get("row_sha256") != sha(row / "row.npz"):
            raise ValueError("row identity or raw output pin differs")
    return report


def own_cpu():
    use = resource.getrusage(resource.RUSAGE_SELF)
    return use.ru_utime + use.ru_stime


def child_cpu():
    use = resource.getrusage(resource.RUSAGE_CHILDREN)
    return use.ru_utime + use.ru_stime


def active_cpu(group):
    # Group membership survives leader exit and orphan adoption by this subreaper.
    return sum(row["cpu_ticks"] for row in proc_table().values() if row["pgrp"] == group) / os.sysconf("SC_CLK_TCK")


def consumed_cpu(running):
    return own_cpu() + child_cpu() + sum(active_cpu(pid) for pid in running)


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


def enable_subreaper():
    if ctypes.CDLL(None).prctl(36, 1, 0, 0, 0) != 0:
        raise OSError("cannot enable complete descendant CPU accounting")


def cleanup_group(process):
    """Kill/reap owned descendants even after their leader exited, retaining their CPU."""
    deadline = time.monotonic() + 3
    while True:
        send_signal(process, signal.SIGKILL)
        if process.poll() is not None:
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
        time.sleep(0.05)


def cleanup(running):
    for process, _, _ in running.values():
        send_signal(process, signal.SIGTERM)
    deadline, errors = time.monotonic() + 1, []
    for pid, (process, log, _) in list(running.items()):
        try:
            try:
                process.wait(timeout=max(0, deadline - time.monotonic()))
            except subprocess.TimeoutExpired:
                send_signal(process, signal.SIGKILL)
            cleanup_group(process)
            del running[pid]
        except BaseException as error:
            errors.append(f"{pid}: {type(error).__name__}: {error}")
        finally:
            log.close()
    if errors:
        raise RuntimeError("owned group cleanup failed: " + "; ".join(errors))


def process_identity(pid):
    fields = (Path("/proc") / str(pid) / "stat").read_text().rsplit(")", 1)[1].split()
    return {"pid": pid, "ppid": int(fields[1]), "pgid": int(fields[2]), "start_ticks": int(fields[19])}


def phase_limit(phase):
    if phase not in ("validation", "research"):
        raise ValueError("invalid phase")
    return VALIDATION_CAP if phase == "validation" else CAP


def budget_reason(phase, consumed):
    if not math.isfinite(consumed) or consumed < 0:
        raise ValueError("invalid cumulative CPU accounting")
    if consumed >= phase_limit(phase) - MARGIN:
        return "validation_cpu_budget_exhausted" if phase == "validation" else "cpu_budget_exhausted"
    return None


def interrupt(signum, frame):
    raise KeyboardInterrupt(f"monitor interrupted by signal {signum}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", action="store_true")
    args = parser.parse_args()
    parent_pid = os.getpid()
    prefix = [str(ROOT / ".venv/bin/python")]
    commands = {"validation": [*prefix, str(STUDY / "validate.py"), "--run", "--expected-parent", str(parent_pid)]}
    commands.update({world: [*prefix, str(STUDY / "measure.py"), "--run", "--world", world,
                             "--expected-parent", str(parent_pid)] for world in WORLDS})
    if not args.run:
        print(json.dumps({"status": "dry_run", "simulated_lives": 0, "monitor_scope": SCOPE,
                          "planned_simulation_calls": 13394, "commands": commands}, indent=2))
        return
    protocol = check_protocol()
    ready = check_ready(protocol)
    if any((STUDY / name).exists() for name in ARTIFACTS):
        raise ValueError("prior attempt or run artifacts exist; no reset, retry, or resume")
    # Exclusive claim closes the two-monitor race; a crash leaves the study permanently attempted.
    with (STUDY / "attempt.json").open("x") as stream:
        json.dump({"monitor": process_identity(parent_pid), "ready_sha256": sha(STUDY / "ready.json")}, stream)
        stream.flush()
        os.fsync(stream.fileno())
    running, completed, queue = {}, [], ["validation"]
    phase, reason, stop_time, validation_cpu = "validation", None, None, None
    start, affinity = time.monotonic(), set()
    identities = [dict(process_identity(parent_pid), name="monitor")]
    handlers = {sig: signal.signal(sig, interrupt) for sig in (signal.SIGTERM, signal.SIGINT)}
    status_path = STUDY / "budget.json"

    def record(status, **extra):
        save(status_path, {"status": status, "cpu_seconds": consumed_cpu(running), "cap_cpu_seconds": CAP,
            "validation_cap_cpu_seconds": VALIDATION_CAP, "validation_cpu_seconds": validation_cpu,
            "wall_seconds": time.monotonic() - start, "phase": phase,
            "running": {str(pid): item[2] for pid, item in running.items()}, "queued": list(queue),
            "completed": completed, "affinity": sorted(affinity), "ready": ready,
            "process_identities": identities,
            "owned_process_groups": [item["pgid"] for item in identities if item["name"] != "monitor"], **extra})

    def unchanged():
        if check_protocol() != protocol or check_ready(protocol) != ready:
            raise ValueError("protocol or release changed")
        if phase == "research":
            check_validation_budget(protocol, validation_cpu)

    try:
        enable_subreaper()
        affinity = os.sched_getaffinity(0).intersection(range(12))
        if not affinity:
            raise ValueError("registered fast CPU set unavailable")
        os.sched_setaffinity(0, affinity)
        env = dict(os.environ, ATEN_CPU_CAPABILITY="avx2", OMP_WAIT_POLICY="PASSIVE", OMP_NUM_THREADS="1",
                   OMP_THREAD_LIMIT="1", MKL_NUM_THREADS="1", OPENBLAS_NUM_THREADS="1", NUMEXPR_NUM_THREADS="1",
                   PYTHONUNBUFFERED="1", CELL_DEV_CACHE=str(STUDY / "build-cache"),
                   CELLDEV_VISIBILITY_MONITOR_PID=str(parent_pid))
        env.pop("CELLDEV_THREADS_FILE", None)
        record("running")
        while queue or running:
            reason = reason or budget_reason(phase, consumed_cpu(running))
            if reason:
                queue.clear()
                if stop_time is None:
                    stop_time = time.monotonic()
                    for process, _, _ in running.values():
                        send_signal(process, signal.SIGTERM)
                if time.monotonic() - stop_time >= 1:
                    for process, _, _ in running.values():
                        send_signal(process, signal.SIGKILL)
            while queue and len(running) < (1 if phase == "validation" else 2) and not reason:
                unchanged()
                consumed = consumed_cpu(running)
                reason = budget_reason(phase, consumed)
                if reason:
                    break
                name = queue.pop(0)
                log_path = STUDY / "logs" / (name + ".log")
                log_path.parent.mkdir(parents=True, exist_ok=True)
                log = log_path.open("x")
                remaining = phase_limit(phase) - consumed
                try:
                    process = subprocess.Popen(commands[name], cwd=ROOT, env=env, stdout=log,
                        stderr=subprocess.STDOUT, start_new_session=True,
                        preexec_fn=lambda limit=remaining, parent=parent_pid: child_limit(limit, parent))
                except BaseException:
                    log.close()
                    raise
                running[process.pid] = (process, log, name)
                identities.append(dict(process_identity(process.pid), name=name))
                print(f"Started {name}: pid {process.pid}", flush=True)
            for pid, (process, log, name) in list(running.items()):
                code = process.poll()
                if code is not None:
                    cleanup_group(process)
                    log.close()
                    completed.append({"name": name, "exit_code": code})
                    del running[pid]
                    if code:
                        reason = reason or "job_failed"
            reason = reason or budget_reason(phase, consumed_cpu(running))
            if reason:
                queue.clear()
            if not running and not queue and not reason:
                unchanged()
                if phase == "validation":
                    check_validation(protocol)
                    validation_cpu = consumed_cpu(running)
                    reason = budget_reason(phase, validation_cpu)
                    if reason is None:
                        save(STUDY / "validation_budget.json", {"status": "complete",
                            "cpu_seconds": validation_cpu, "cap_cpu_seconds": VALIDATION_CAP,
                            "report_sha256": sha(STUDY / "validation/report.json"),
                            "protocol_sha256": sha(STUDY / "protocol.json")})
                        queue, phase = list(WORLDS), "research"
                else:
                    for world in WORLDS:
                        check_world(world, protocol)
                    reason = budget_reason(phase, consumed_cpu(running))
            record("running" if running or queue else ("incomplete" if reason else "complete"),
                   reason=reason, exit_code=1 if reason else (None if running or queue else 0))
            if running or queue:
                time.sleep(POLL)
    except BaseException as error:
        cleanup_error = None
        try:
            cleanup(running)
        except BaseException as failure:
            cleanup_error = type(failure).__name__ + ": " + str(failure)
        queue.clear()
        record("monitor_failed", reason=reason, error=type(error).__name__ + ": " + str(error),
               exit_code=1, cleanup_error=cleanup_error)
        raise
    finally:
        for sig, handler in handlers.items():
            signal.signal(sig, handler)
    raise SystemExit(1 if reason else 0)


if __name__ == "__main__":
    main()
