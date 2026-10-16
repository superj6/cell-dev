"""One owned viewer worker: C export, descendant Node replay, then supplied-state UI smoke."""
from __future__ import annotations

import argparse
import json
import os
import resource
import subprocess
import sys
import time
from pathlib import Path

import monitor_core
from export import ARTIFACT, BUDGET, HERE, ROOT, checked_record, export, read, save, sha

EXECUTION = HERE/"execution"


def call_counts():
    result = {}
    for name, key in (("C_calls.json", "C_full_lives"), ("JS_calls.json", "JS_replay_lives")):
        calls = read(ARTIFACT/name) if (ARTIFACT/name).exists() else []
        result[key] = sum(call["status"] in ("returned", "validated") for call in calls)
        result[key+"_attempted"] = len(calls)
        result[key+"_validated"] = sum(call["status"] == "validated" for call in calls)
    return result


def child(record_path):
    checked_record(record_path, worker=True)
    worker = dict(monitor_core.identity(os.getpid()), pid_namespace=monitor_core.pid_namespace(),
                  record_sha256=sha(record_path), attempt_sha256=sha(EXECUTION/"attempt.json"))
    save(EXECUTION/"worker_identity.json", worker, exclusive=True)
    nodes = []
    stage = "C_export"

    def node(script, stdout_name, stderr_name, extra=()):
        checked_record(record_path, worker=True)
        env = dict(os.environ, CELLDEV_WATCHABLE_WORKER_PID=str(worker["pid"]),
                   CELLDEV_WATCHABLE_WORKER_START_TICKS=str(worker["start_ticks"]),
                   CELLDEV_WATCHABLE_WORKER_SHA256=sha(EXECUTION/"worker_identity.json"))
        command = ["/usr/bin/node", "--single-threaded", "--single-threaded-gc", "--max-old-space-size=512",
                   str(HERE/script), *extra]
        before = resource.getrusage(resource.RUSAGE_CHILDREN)
        started = time.monotonic()
        with (ARTIFACT/stdout_name).open("x") as out, (ARTIFACT/stderr_name).open("x") as err:
            process = subprocess.Popen(command, cwd=HERE, env=env, stdout=out, stderr=err,
                                       stdin=subprocess.DEVNULL, close_fds=True)
            identity = monitor_core.identity(process.pid)
            if identity["ppid"] != worker["pid"] or identity["pgid"] != worker["pgid"]:
                raise ValueError("Node must remain a descendant in the owned worker group")
            row = dict(script=script, command=command, identity=identity, status="started")
            nodes.append(row)
            save(EXECUTION/"node_calls.json", nodes)
            code = process.wait()
        after = resource.getrusage(resource.RUSAGE_CHILDREN)
        row.update(status="complete" if code == 0 else "failed", exit_code=code,
                   cpu_seconds=after.ru_utime+after.ru_stime-before.ru_utime-before.ru_stime,
                   wall_seconds=time.monotonic()-started, stdout_sha256=sha(ARTIFACT/stdout_name),
                   stderr_sha256=sha(ARTIFACT/stderr_name))
        save(EXECUTION/"node_calls.json", nodes)
        if code != 0:
            raise ValueError(script+" failed with exit code "+str(code))

    try:
        export(record_path)  # Same worker, exactly twelve full C calls.
        stage = "JS_replay"
        node("replay.js", "replay_stdout.json", "replay_stderr.log",
             ("--replay-child", "--record", str(record_path)))
        stage = "UI_smoke"
        node("test_ui.js", "ui_smoke.json", "ui_smoke_stderr.log")
        checked_record(record_path, worker=True)
        counts = call_counts()
        ui, replay = read(ARTIFACT/"ui_smoke.json"), read(ARTIFACT/"replay_receipt.json")
        if (any(counts[key] != 12 for key in counts) or replay["status"] != "complete"
                or ui["status"] != "passed" or ui["actual_simulator_calls"] != 0
                or ui["builds"] != 0 or ui["random_draws"] != 0 or ui["real_browser_tested"]):
            raise ValueError("fixed C/JS inventory or supplied-state UI receipt differs")
        save(EXECUTION/"pipeline_complete.json", dict(status="complete", **counts,
             record_sha256=sha(record_path), attempt_sha256=sha(EXECUTION/"attempt.json"),
             worker_identity_sha256=sha(EXECUTION/"worker_identity.json"),
             node_calls_sha256=sha(EXECUTION/"node_calls.json"),
             export_receipt_sha256=sha(ARTIFACT/"export_receipt.json"),
             replay_receipt_sha256=sha(ARTIFACT/"replay_receipt.json"),
             ui_smoke_sha256=sha(ARTIFACT/"ui_smoke.json"),
             C_calls_sha256=sha(ARTIFACT/"C_calls.json"), JS_calls_sha256=sha(ARTIFACT/"JS_calls.json"),
             new_research_cases=0, real_browser_tested=False), exclusive=True)
    except BaseException as error:
        save(EXECUTION/"pipeline_incomplete.json", dict(status="incomplete", stage=stage,
             error=repr(error), **call_counts(), record_sha256=sha(record_path)), exclusive=True)
        raise


def validate_completion(record_path):
    checked_record(record_path)
    marker = read(EXECUTION/"pipeline_complete.json")
    if (marker["status"] != "complete" or marker["record_sha256"] != sha(record_path)
            or marker["attempt_sha256"] != sha(EXECUTION/"attempt.json")
            or any(marker[key] != 12 for key in call_counts()) or call_counts() !=
            {key: marker[key] for key in call_counts()}):
        raise ValueError("complete fixed pipeline marker required")
    for base, name, key in (
            (EXECUTION, "worker_identity.json", "worker_identity_sha256"),
            (EXECUTION, "node_calls.json", "node_calls_sha256"),
            (ARTIFACT, "export_receipt.json", "export_receipt_sha256"),
            (ARTIFACT, "replay_receipt.json", "replay_receipt_sha256"),
            (ARTIFACT, "ui_smoke.json", "ui_smoke_sha256"),
            (ARTIFACT, "C_calls.json", "C_calls_sha256"), (ARTIFACT, "JS_calls.json", "JS_calls_sha256")):
        if marker[key] != sha(base/name):
            raise ValueError("pipeline output changed: "+name)
    nodes = read(EXECUTION/"node_calls.json")
    worker = read(EXECUTION/"worker_identity.json")
    attempt = read(EXECUTION/"attempt.json")
    if (len(nodes) != 2 or [row["script"] for row in nodes] != ["replay.js", "test_ui.js"]
            or any(row["status"] != "complete" or row["exit_code"] != 0 for row in nodes)
            or any(row["identity"]["ppid"] != worker["pid"] or row["identity"]["pgid"] != worker["pgid"]
                   for row in nodes)
            or worker["ppid"] != attempt["monitor"]["pid"] or worker["pid"] != worker["pgid"]
            or worker["pid_namespace"] != attempt["pid_namespace"]
            or worker["record_sha256"] != sha(record_path)
            or worker["attempt_sha256"] != sha(EXECUTION/"attempt.json")):
        raise ValueError("owned pipeline worker/descendant records differ")
    return marker


def run(record_path):
    start = time.monotonic()
    checked_record(record_path)
    if any(path.exists() for path in (EXECUTION, ARTIFACT, HERE/"validation_budget.json")):
        raise ValueError("first attempt refuses prior viewer execution artifacts")
    EXECUTION.mkdir()
    record_digest = sha(record_path)
    budget = dict(BUDGET, wall_seconds=BUDGET["wall_seconds"]-(time.monotonic()-start), cleanup_margin_seconds=5)
    command = [str(ROOT/".venv/bin/python"), "-u", str(Path(__file__).resolve()),
               "--child", "--record", str(record_path)]
    result, failure = None, None
    try:
        result = monitor_core.run_worker(EXECUTION, command, budget, record_digest, record_digest,
            lambda: validate_completion(record_path), environment=dict(os.environ,
                CELL_DEV_WATCHABLE_RECORD_SHA256=record_digest, NUMEXPR_NUM_THREADS="1"))
    except BaseException as error:
        failure = repr(error)
        if (EXECUTION/"budget.json").exists():
            result = read(EXECUTION/"budget.json")
    if result is None:
        raise RuntimeError("owned monitor failed before a budget record: "+str(failure))
    if result["status"] == "complete":
        worker = read(EXECUTION/"worker_identity.json")
        owned_workers = [row for row in result["process_identities"] if row["name"] == "worker"]
        if (len(owned_workers) != 1 or any(worker[key] != owned_workers[0][key]
                for key in ("pid", "ppid", "pgid", "start_ticks"))):
            failure = "pipeline worker identity differs from the monitor's recorded worker"
    proof = result.get("terminal_cleanup") or {}
    cleared = (proof.get("all_owned_groups_exited", False) and proof.get("all_worker_identities_exited", False)
               and not proof.get("remaining_descendants", ["unknown"]))
    cpu = max(result["cpu_seconds"], monitor_core.consumed_cpu(-1))
    wall = time.monotonic()-start
    counts = call_counts()
    complete = (result["status"] == "complete" and failure is None and cleared
                and cpu < BUDGET["cpu_seconds"] and wall < BUDGET["wall_seconds"]
                and all(value == 12 for value in counts.values()))
    receipt = dict(status="complete" if complete else "incomplete", **counts,
        record_sha256=record_digest, monitor_budget_sha256=sha(EXECUTION/"budget.json"),
        cpu_seconds=cpu, wall_seconds=wall, cap_cpu_seconds=60, cap_wall_seconds=180,
        peak_owned_rss_bytes=result["peak_owned_rss_bytes"], all_processes_exited=bool(cleared),
        terminal_cleanup=proof, error=failure or result.get("error"), reason=result.get("reason"),
        new_research_cases=0, actual_workers=1, threads_per_worker=1, real_browser_tested=False)
    for name, key in (("export_receipt.json", "export_receipt_sha256"),
                      ("replay_receipt.json", "replay_receipt_sha256"), ("ui_smoke.json", "ui_smoke_sha256")):
        receipt[key] = sha(ARTIFACT/name) if (ARTIFACT/name).exists() else None
    save(HERE/"validation_budget.json", receipt, exclusive=True)
    print(json.dumps(receipt, indent=2))
    return 0 if complete else 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--run", action="store_true")
    mode.add_argument("--child", action="store_true")
    parser.add_argument("--record", type=Path)
    args = parser.parse_args()
    if not args.run and not args.child:
        print(json.dumps(dict(status="source_only", C_full_lives=0, JS_replay_lives=0)))
    elif args.record is None:
        parser.error("--record is required")
    elif args.child:
        child(args.record.resolve())
    else:
        sys.exit(run(args.record.resolve()))
