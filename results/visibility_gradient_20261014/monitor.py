"""First-attempt ordinary-mutant visibility pilot; dry-run unless released and run.

Startup, calibration, screening and confirmation share one cumulative CPU ledger.
One two-thread worker pauses for accounted phase acknowledgments; no organism rule changes.
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
CAP, SCREEN_CAP, RESERVE, MARGIN, POLL = 5400, 3400, 2000, 10, 0.25
PARENTS = ("D90", "L92")
SCOPE = {"total_cpu_seconds": CAP, "startup_screen_cpu_seconds": SCREEN_CAP,
         "confirmation_reserve_cpu_seconds": RESERVE, "max_workers": 1,
         "threads_per_worker": 2, "research_lives": 6208, "validation_lives": 10}
ARTIFACTS = ("attempt.json", "budget.json", "measurement", "logs", "build-cache",
             "startup_identity.json", "report.json", "selection.json", "requests",
             "monitor_receipts", "calibration_projection.json")


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
    if protocol.get("monitor_scope") != SCOPE or protocol.get("world_decision") != "complete":
        raise ValueError("registered scope or world decision differs")
    if protocol["world"]["name"] != "catch_speck_blink20_20_l4" or protocol["world"]["T"] != 1024:
        raise ValueError("registered world differs")
    seeds = protocol["seeds"]
    if set(seeds) != {"screen", "confirm", "calibration"}:
        raise ValueError("registered seed stages differ")
    flat = []
    for stage, count in (("screen", 32), ("confirm", 512), ("calibration", 2)):
        values = seeds[stage]
        if len(values) != count or any(type(seed) is not int or seed < 0 for seed in values):
            raise ValueError("stage requires fixed unsigned seed IDs")
        flat.extend(values)
    if len(set(flat)) != len(flat) or 11 in flat:
        raise ValueError("fresh stages and numerical golden overlap")
    if set(protocol["panel_genotype_sha256"]) != set(PARENTS):
        raise ValueError("fixed founder panels differ")
    if any(len(protocol["panel_genotype_sha256"][p]) != 65 for p in PARENTS):
        raise ValueError("all64 mutants and each parent are required")
    check_pins(STUDY, protocol["file_pins"])
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
    required = {"protocol.json", "monitor.py", "measure.py", "scoring.py", "common.py", "numerical.py", "resource_clearance.json"}
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


def expected_rows(stage, selection=None):
    rows = {f"calibration/row_{i:04d}.npz" for i in (0, 1)}
    if stage in ("screens_complete", "complete"):
        rows.update(f"screen/row_{i:04d}.npz" for i in range(65))
    if stage == "complete":
        rows.update(f"confirm/row_{i:04d}.npz" for i in (0, selection["genome_row"]))
    return rows


def row_snapshot(stage, request, protocol):
    selection = read(STUDY / "selection.json") if stage != "calibration_complete" else None
    if selection is not None:
        if set(selection) != set(PARENTS):
            raise ValueError("both winners must be frozen")
        for parent, winner in selection.items():
            index = winner.get("genome_row")
            if (type(index) is not int or not 1 <= index <= 64
                    or winner.get("raw_sha256") != protocol["panel_genotype_sha256"][parent][index]):
                raise ValueError("selected genotype is outside the frozen mutant panel")
    snapshots = {}
    for parent in PARENTS:
        folder = STUDY / "measurement" / parent
        path = folder / "row_index.json"
        if request["row_index_sha256"][parent] != sha(path):
            raise ValueError("row index changed at phase boundary")
        index = read(path)
        if set(index) != expected_rows(stage, selection[parent] if selection is not None else None):
            raise ValueError("fixed phase row set is incomplete or contains extras")
        check_pins(folder, {name: item["sha256"] for name, item in index.items()})
        if any(not isinstance(item.get("cpu_seconds"), (int, float))
               or not math.isfinite(item["cpu_seconds"]) or item["cpu_seconds"] < 0 for item in index.values()):
            raise ValueError("invalid committed row CPU")
        snapshots[parent] = index
    return snapshots


def phase_request(name, protocol, calibration_receipt=None):
    request = read(STUDY / "requests" / (name + ".json"))
    if request.get("protocol_sha256") != sha(STUDY / "protocol.json"):
        raise ValueError("phase request protocol differs")
    if name == "calibration_complete":
        startup = read(STUDY / "startup_identity.json")
        if (request.get("validation_lives") != 10
                or request.get("startup_identity_sha256") != sha(STUDY / "startup_identity.json")
                or startup.get("numerical_identity_invocations") != 1
                or startup.get("golden_lives") != {"abi": 3, "seed": 11, "T": 200, "full": 1, "fast": 1}
                or {k: v for k, v in startup["identity"].items() if k not in ("kernels", "golden")}
                != protocol["expected_startup_metadata"]):
            raise ValueError("startup identity and ten validation lives are incomplete")
    elif name == "screens_complete":
        if (calibration_receipt is None or request.get("scientific_genome_lives") != 4160
                or request.get("selection_sha256") != sha(STUDY / "selection.json")):
            raise ValueError("screens or frozen selection incomplete")
        projection = read(STUDY / "calibration_projection.json")
        rates = {p: max(calibration_receipt["row_snapshot"][p][f"calibration/row_{i:04d}.npz"]["cpu_seconds"]
                        for i in (0, 1)) / 2 for p in PARENTS}
        screen = calibration_receipt["cpu_seconds"] + 1.5 * 2080 * sum(rates.values())
        confirm = 1.5 * 1024 * sum(rates.values())
        if (projection.get("feasible") is not True or projection.get("batch_max_cpu_per_life") != rates
                or projection.get("startup_cpu_seconds") != calibration_receipt["cpu_seconds"]
                or projection.get("screen_projection_cpu_seconds") != screen
                or projection.get("confirmation_projection_cpu_seconds") != confirm
                or screen > SCREEN_CAP - MARGIN or confirm > RESERVE - MARGIN):
            raise ValueError("fixed calibration feasibility check failed")
    else:
        raise ValueError("unknown phase request")
    return row_snapshot(name, request, protocol)


def check_complete(protocol, receipts, consumed):
    report = read(STUDY / "report.json")
    if (report.get("status") != "complete" or report.get("scope") != SCOPE
            or report.get("research_genome_lives") != 6208 or report.get("validation_lives") != 10
            or report.get("total_genome_lives") != 6218 or set(receipts) != {"calibration_complete", "screens_complete"}):
        raise ValueError("fixed scientific work is incomplete")
    snapshots = row_snapshot("complete", report, protocol)
    for receipt in receipts.values():
        for parent, original in receipt["row_snapshot"].items():
            if any(snapshots[parent].get(name) != item for name, item in original.items()):
                raise ValueError("previously acknowledged scientific row changed")
    raw_cpu = sum(item["cpu_seconds"] for values in snapshots.values() for item in values.values())
    if raw_cpu > consumed + 1e-6 or abs(raw_cpu - report["row_cpu_seconds"]) > 1e-6:
        raise ValueError("committed CPU contradicts monitored CPU")
    return report


def check_acknowledged(receipts):
    """Frozen startup/selection artifacts remain bound after the worker proceeds."""
    for name, receipt in receipts.items():
        if (read(STUDY / "monitor_receipts" / (name + ".json")) != receipt
                or sha(STUDY / "requests" / (name + ".json")) != receipt["request_sha256"]):
            raise ValueError("acknowledged phase record changed")
        check_pins(STUDY, receipt["artifact_pins"])


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
    if phase not in ("startup_screen", "confirmation"):
        raise ValueError("invalid phase")
    return SCREEN_CAP if phase == "startup_screen" else CAP


def budget_reason(phase, consumed):
    if not math.isfinite(consumed) or consumed < 0:
        raise ValueError("invalid cumulative CPU accounting")
    if consumed >= phase_limit(phase) - MARGIN:
        return "startup_screen_cpu_budget_exhausted" if phase == "startup_screen" else "cpu_budget_exhausted"
    return None


def interrupt(signum, frame):
    raise KeyboardInterrupt(f"monitor interrupted by signal {signum}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", action="store_true")
    args = parser.parse_args()
    parent_pid = os.getpid()
    prefix = [str(ROOT / ".venv/bin/python")]
    commands = {"gradient": [*prefix, str(STUDY / "measure.py"), "--run", "--monitor-pid", str(parent_pid)]}
    if not args.run:
        print(json.dumps({"status": "dry_run", "simulated_lives": 0, "monitor_scope": SCOPE,
                          "planned_simulation_calls": 6218, "commands": commands}, indent=2))
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
    running, completed, queue = {}, [], ["gradient"]
    phase, reason, stop_time, screen_cpu = "startup_screen", None, None, None
    receipts = {}
    start, affinity = time.monotonic(), set()
    identities = [dict(process_identity(parent_pid), name="monitor")]
    handlers = {sig: signal.signal(sig, interrupt) for sig in (signal.SIGTERM, signal.SIGINT)}
    status_path = STUDY / "budget.json"

    def record(status, **extra):
        save(status_path, {"status": status, "cpu_seconds": consumed_cpu(running), "cap_cpu_seconds": CAP,
            "startup_screen_cap_cpu_seconds": SCREEN_CAP, "startup_screen_cpu_seconds": screen_cpu,
            "confirmation_reserve_cpu_seconds": RESERVE, "phase_receipts": receipts,
            "wall_seconds": time.monotonic() - start, "phase": phase,
            "running": {str(pid): item[2] for pid, item in running.items()}, "queued": list(queue),
            "completed": completed, "affinity": sorted(affinity), "ready": ready,
            "process_identities": identities,
            "owned_process_groups": [item["pgid"] for item in identities if item["name"] != "monitor"], **extra})

    def unchanged():
        if check_protocol() != protocol or check_ready(protocol) != ready:
            raise ValueError("protocol or release changed")
        check_acknowledged(receipts)

    try:
        enable_subreaper()
        affinity = os.sched_getaffinity(0).intersection(range(12))
        if not affinity:
            raise ValueError("registered fast CPU set unavailable")
        os.sched_setaffinity(0, affinity)
        env = dict(os.environ, ATEN_CPU_CAPABILITY="avx2", OMP_WAIT_POLICY="PASSIVE", OMP_NUM_THREADS="2",
                   OMP_THREAD_LIMIT="2", MKL_NUM_THREADS="1", OPENBLAS_NUM_THREADS="1", NUMEXPR_NUM_THREADS="1",
                   PYTHONUNBUFFERED="1", CELL_DEV_CACHE=str(STUDY / "build-cache"),
                   CELLDEV_GRADIENT_MONITOR_PID=str(parent_pid), PYTHONDONTWRITEBYTECODE="1")
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
            while queue and len(running) < 1 and not reason:
                unchanged()
                consumed = consumed_cpu(running)
                reason = budget_reason(phase, consumed)
                if reason:
                    break
                name = queue.pop(0)
                log_path = STUDY / "logs" / (name + ".log")
                log_path.parent.mkdir(parents=True, exist_ok=True)
                log = log_path.open("x")
                remaining = CAP - consumed  # One worker survives the phase switch; monitor owns the earlier ceiling.
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
            if not reason and running and phase == "startup_screen":
                for name in ("calibration_complete", "screens_complete"):
                    request_path = STUDY / "requests" / (name + ".json")
                    if name in receipts or not request_path.exists():
                        continue
                    unchanged()
                    snapshot = phase_request(name, protocol, receipts.get("calibration_complete"))
                    consumed = consumed_cpu(running)
                    reason = budget_reason(phase, consumed)
                    if reason:
                        break
                    request = read(request_path)
                    artifact_pins = ({"startup_identity.json": request["startup_identity_sha256"]}
                                     if name == "calibration_complete" else {
                                         "selection.json": request["selection_sha256"],
                                         "calibration_projection.json": sha(STUDY / "calibration_projection.json")})
                    check_pins(STUDY, artifact_pins)
                    receipt = {"status": "allowed", "protocol_sha256": sha(STUDY / "protocol.json"),
                               "attempt_sha256": sha(STUDY / "attempt.json"),
                               "request_sha256": sha(request_path), "cpu_seconds": consumed,
                               "row_snapshot": snapshot, "artifact_pins": artifact_pins}
                    if name == "screens_complete":
                        screen_cpu, phase = consumed, "confirmation"
                    receipts[name] = receipt
                    save(STUDY / "monitor_receipts" / (name + ".json"), receipt)
            if reason:
                queue.clear()
            if not running and not queue and not reason:
                unchanged()
                if phase != "confirmation":
                    raise ValueError("worker exited before accounted confirmation transition")
                check_complete(protocol, receipts, consumed_cpu(running))
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
