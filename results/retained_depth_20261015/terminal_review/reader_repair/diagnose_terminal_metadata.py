"""Metadata-only diagnosis; does not import a reader or read scientific outcome data."""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
STUDY = ROOT / "outputs/autonomous_retained_depth_20261015"
OUT = Path(__file__).resolve().parent
PHASES = ("unchanged", "balanced", "confirmation")
FIELDS = ("pid", "ppid", "pgid", "start_ticks")
STABLE = ("pid", "pgid", "start_ticks")
EXPECTED_BUDGET = "4d45d119c72f926bdd20e16d2456df15817042cb018446698bfe392f06fbbe0a"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(name):
    return json.loads((STUDY / name).read_text())


def terminal(record, namespace, protocol_sha, release_sha):
    assert record["status"] == "complete" and record["exit_code"] == record["worker_exit_code"] == 0
    assert not any(record[key] for key in ("running", "queued", "cleanup_error", "reason", "error"))
    assert (record["pid_namespace"], record["protocol_sha256"], record["release_sha256"]) == (
        namespace, protocol_sha, release_sha)
    for value, cap in (("cpu_seconds", "cap_cpu_seconds"), ("wall_seconds", "cap_wall_seconds")):
        assert math.isfinite(record[value]) and 0 <= record[value] < record[cap]
    proof = record["terminal_cleanup"]
    assert proof["pid_namespace"] == namespace
    assert all(proof[key] is True for key in ("checked_in_monitor", "same_pid_namespace",
                                             "all_owned_groups_exited", "all_worker_identities_exited"))
    assert not any(proof[key] for key in ("remaining_group_members", "remaining_worker_identities",
                                        "remaining_descendants"))
    for row in record["process_identities"]:
        assert all(type(row[key]) is int and row[key] > 0 for key in FIELDS)
    receipts = record["wait4_receipts"]
    assert len({row["pid"] for row in receipts}) == len(receipts)
    assert all(math.isfinite(row[key]) and row[key] >= 0 for row in receipts
               for key in ("user_cpu_seconds", "system_cpu_seconds"))
    assert sum(row["user_cpu_seconds"] + row["system_cpu_seconds"] for row in receipts) <= record["cpu_seconds"] + 1e-6


def main():
    protocol, release, attempt, budget = (read(name) for name in (
        "protocol.json", "release.json", "attempt.json", "budget.json"))
    assert sha(STUDY / "budget.json") == EXPECTED_BUDGET
    protocol_sha, release_sha = sha(STUDY / "protocol.json"), sha(STUDY / "release.json")
    namespace = budget["pid_namespace"]
    assert namespace == "pid:[4026531836]"
    assert release["status"] == "released" and release["protocol_sha256"] == protocol_sha
    assert attempt["protocol_sha256"] == protocol_sha and attempt["release_sha256"] == release_sha
    assert attempt["pid_namespace"] == release["pid_namespace"] == namespace
    assert attempt["budget"] == protocol["budget"]
    assert budget["attempt_sha256"] == sha(STUDY / "attempt.json")
    assert tuple(budget["phase_records"]) == PHASES and set(attempt["commands"]) == set(PHASES)
    terminal(budget, namespace, protocol_sha, release_sha)
    assert (budget["cap_cpu_seconds"], budget["cap_wall_seconds"], budget["search_cpu_cap"],
            budget["confirmation_cpu_cap"], budget["phase"]) == (28800, 14400, 24000, 4800, "confirmation")
    assert 0 <= budget["search_cpu_seconds"] < 24000 and 0 <= budget["confirmation_cpu_seconds"] < 4800
    assert abs(budget["search_cpu_seconds"] + budget["confirmation_cpu_seconds"] - budget["cpu_seconds"]) <= 1e-6
    monitor, *workers = budget["process_identities"]
    assert len(workers) == 3 and [r["name"] for r in workers] == list(PHASES)
    assert monitor == {**attempt["monitor"], "name": "monitor"}
    assert {k: monitor[k] for k in STABLE} == {"pid": 2885667, "pgid": 2885666, "start_ticks": 10138155}
    assert budget["owned_process_groups"] == [w["pid"] for w in workers]
    assert len(set(budget["owned_process_groups"])) == 3
    phase_records, receipts, cpu = {}, [], []
    for phase, worker in zip(PHASES, workers):
        prefix = f"execution/{phase}"
        record, phase_attempt = read(prefix + "/budget.json"), read(prefix + "/attempt.json")
        assert budget["phase_records"][phase] == {"path": prefix + "/budget.json",
                                                 "sha256": sha(STUDY / prefix / "budget.json")}
        terminal(record, namespace, protocol_sha, release_sha)
        observed = record["process_identities"]
        original_assertions = {
            "two_process_identities": len(observed) == 2,
            "global_monitor_full_dict_equal": observed[0] == monitor,
            "worker_exact": observed[1] == {**worker, "name": "worker"},
            "worker_parent_exact": worker["ppid"] == monitor["pid"],
            "worker_group_exact": worker["pgid"] == worker["pid"],
            "owned_group_exact": record["owned_process_groups"] == [worker["pid"]],
            "phase_attempt_digest_exact": record["attempt_sha256"] == sha(STUDY / prefix / "attempt.json"),
            "global_phase_attempt_monitor_full_dict_equal": phase_attempt["monitor"] == attempt["monitor"],
            "namespace_exact": phase_attempt["pid_namespace"] == namespace,
            "protocol_exact": phase_attempt["protocol_sha256"] == protocol_sha,
            "release_exact": phase_attempt["release_sha256"] == release_sha,
            "command_exact": phase_attempt["command"] == attempt["commands"][phase],
        }
        failed = [key for key, ok in original_assertions.items() if not ok]
        assert failed == ([] if phase == "unchanged" else ["global_monitor_full_dict_equal",
                                                         "global_phase_attempt_monitor_full_dict_equal"])
        assert observed[0] == {**phase_attempt["monitor"], "name": "monitor"}
        assert set(phase_attempt["monitor"]) == set(FIELDS)
        assert {key: observed[0][key] for key in STABLE} == {key: monitor[key] for key in STABLE}
        assert observed[0]["ppid"] == (2885666 if phase == "unchanged" else 5729)
        expected_cap = 24000 if phase != "confirmation" else min(28800, budget["search_cpu_seconds"] + 4800)
        assert record["cap_cpu_seconds"] == expected_cap
        assert phase_attempt["budget"] == {"cpu_seconds": expected_cap,
            "wall_seconds": record["cap_wall_seconds"], "threads": 2, "workers": 1,
            "cleanup_margin_seconds": 10, "rss_bytes": 4 * 1024**3,
            "minimum_available_bytes": 4 * 1024**3, "address_space_bytes": 8 * 1024**3}
        assert 0 < record["cap_wall_seconds"] <= 14400
        assert record["cap_rss_bytes"] == record["minimum_available_bytes"] == 4 * 1024**3
        assert record["worker_address_space_bytes"] == 8 * 1024**3
        assert type(record["peak_owned_rss_bytes"]) is int and 0 <= record["peak_owned_rss_bytes"] < 4 * 1024**3
        own = [r for r in record["wait4_receipts"] if r["pid"] == worker["pid"]]
        assert len(own) == 1 and own[0]["exit_code"] == own[0]["wait_status"] == 0
        phase_records[phase] = {"monitor": observed[0], "worker": observed[1],
                                "original_ownership_predicates": original_assertions}
        receipts.extend(record["wait4_receipts"])
        cpu.append(record["cpu_seconds"])
    assert cpu[0] <= cpu[1] <= budget["search_cpu_seconds"] <= cpu[2] <= budget["cpu_seconds"]
    assert receipts == budget["wait4_receipts"]
    assert len(protocol["source_pins"]) == 10
    assert all(sha(STUDY / name) == digest for name, digest in protocol["source_pins"].items())
    clearance = read("terminal_review/host_clearance.json")
    assert clearance["status"] == "cleared" and clearance["budget_sha256"] == EXPECTED_BUDGET
    assert clearance["pid_namespace"] == namespace and clearance["identities_checked"] == 4 and clearance["groups_checked"] == 3
    assert not clearance["remaining_identities"] and not clearance["remaining_group_members"]
    failed_reader = read("analysis_result/summary.json")
    assert failed_reader == {"status": "incomplete", "error": "phase worker/attempt ownership differs",
                             "outcomes_emitted": False}
    names = ["protocol.json", "release.json", "attempt.json", "budget.json", "analyze.py", "monitor.py",
             "terminal_review/host_clearance.json", "analysis_result/summary.json"]
    names.extend(f"execution/{phase}/{name}" for phase in PHASES for name in ("attempt.json", "budget.json"))
    result = {"status": "metadata_verified", "scientific_outcomes_read": False, "corrected_reader_executed": False,
              "root_cause": "monitor PPID changed after original launch; stable process identity and worker ownership did not",
              "pid_namespace": namespace, "original_monitor": monitor, "phases": phase_records,
              "input_pins": {name: sha(STUDY / name) for name in names},
              "frozen_source_pins_verified": protocol["source_pins"],
              "source_sha256": sha(Path(__file__)), "resource_limits_and_reaping_verified": True}
    target = OUT / "metadata_diagnosis.json"
    with target.open("x") as f:
        json.dump(result, f, indent=2, allow_nan=False)
        f.write("\n")
    print(json.dumps({"status": result["status"], "root_cause": result["root_cause"], "scientific_outcomes_read": False}))


if __name__ == "__main__":
    main()
