"""Prepared two-replicate continuation and fixed endpoint measurement; dry-run unless --run.

An explicit ready.json pin is required before launch. The 10800 CPU-second cap
includes both production evolution processes and the later paired confirmation.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import resource
import signal
import subprocess
import sys
import time
from dataclasses import asdict
from pathlib import Path

os.environ.setdefault("ATEN_CPU_CAPABILITY", "avx2")
ROOT = Path(__file__).resolve().parents[2]
STUDY = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(".tmp")
    temp.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n")
    temp.replace(path)


def check_protocol():
    protocol = json.loads((STUDY / "protocol.json").read_text())
    if sha(STUDY / "seed_audit.json") != protocol["seed_audit_sha256"]:
        raise ValueError("seed audit differs from prepared protocol")
    for value in protocol["configs"].values():
        if sha(ROOT / value["path"]) != value["sha256"]:
            raise ValueError("continuation configuration changed")
    for relative, digest in protocol["source_identity"].items():
        if sha(ROOT / relative) != digest:
            raise ValueError("engine/search source changed after preparation")
    for name in ("founder", "pilot"):
        if sha(ROOT / protocol[name + "_file"]) != protocol[name + "_sha256"]:
            raise ValueError("fixed genotype changed after preparation")
    return protocol


def check_ready():
    path = STUDY / "ready.json"
    if not path.exists():
        raise ValueError("not released: root must register the experiment and create ready.json first")
    ready = json.loads(path.read_text())
    if ready["runner_sha256"] != sha(Path(__file__)) or ready["protocol_sha256"] != sha(STUDY / "protocol.json"):
        raise ValueError("runner or protocol differs from readiness pins")
    for name in ("taskvar_confirm.py", "taskvar_gradient.py", "taskvar_gates.py"):
        if ready["helpers"][name] != sha(ROOT / "scripts" / name):
            raise ValueError("measurement helper differs from readiness pins")
    return ready


def duration_mixture(rows, candidate: int, reference: int):
    """Average durations within each shared seed, retaining their covariance."""
    import numpy as np

    if set(rows) != {"768", "1024", "1536"}:
        raise ValueError("need exactly the three registered durations")
    effects = [np.asarray(value[candidate]["F"]) - np.asarray(value[reference]["F"]) for value in rows.values()]
    values = np.stack(effects)
    if values.ndim != 2 or values.shape[1] < 2 or not np.isfinite(values).all():
        raise ValueError("duration effects must be finite and share paired life arrays")
    return values.mean(axis=0)


def confirm_endpoints():
    """Only called after both complete; freeze final population rank zero before looking at any confirmation."""
    import numpy as np
    from omegaconf import OmegaConf

    from scripts.taskvar_confirm import COLS, atomic_npz, compare_rows, score_row
    from scripts.taskvar_gates import paired
    from src import checkpoint
    from src.genome import Layout
    from src.life import spec
    from src.life.evaluate import LifeEvaluator

    protocol, ready = check_protocol(), check_ready()
    identity = checkpoint.numerical_identity()
    if identity != protocol["expected_numerical_identity"]:
        raise ValueError("confirmation numerical identity differs from the original measurement")
    paths = [ROOT / protocol["pilot_file"], ROOT / protocol["founder_file"]]
    checkpoint_hashes = {}
    search_health = {}
    for seed in protocol["runs"]:
        folder = STUDY / f"runs/s{seed}"
        cfg = OmegaConf.load(ROOT / protocol["configs"][str(seed)]["path"])
        path = folder / "checkpoint.pt"
        saved = checkpoint.load(path)
        checkpoint.validate(saved, cfg, identity)
        if saved["state"]["generation"] != protocol["generations"]:
            raise ValueError("refuse endpoint measurement of an incomplete continuation")
        curves = saved["state"]["curves"]
        if [row["gen"] for row in curves] != list(range(protocol["generations"])):
            raise ValueError("checkpoint lacks the complete ordered search history")
        search_health[str(seed)] = {
            key: max(float(row[key]) for row in curves)
            for key in ("pop_invalid", "pop_mismatch", "recheck_invalid")}
        save(STUDY / "search_health.json", search_health)
        if any(value != 0 for value in search_health[str(seed)].values()):
            raise ValueError("invalid or mismatched search lives require investigation before endpoint inference")
        selected = folder / "best_genome.json"
        _, genome = Layout.load(selected)
        if genome.numpy().tobytes() != saved["state"]["population"][0].numpy().tobytes():
            raise ValueError("saved best differs from final production population rank zero")
        paths.append(selected)
        checkpoint_hashes[str(seed)] = sha(path)
    layout, _ = Layout.load(paths[0])
    genomes = np.stack([Layout.load(path)[1].numpy() for path in paths])
    labels = ["pilot_s5", "founder_row38", *[f"s{seed}_final_rank0" for seed in protocol["runs"]]]
    seeds = json.loads((STUDY / "seed_audit.json").read_text())["confirm_seeds"]
    cfg = OmegaConf.load(ROOT / protocol["configs"][str(protocol["runs"][0])]["path"])
    evaluator = LifeEvaluator(cfg, layout)
    worlds = {str(duration): spec.world("catch_speck_l4", T=duration, d0=0.5, d_min=0.25, sigma=0.4, lam_s=4.0)
              for duration in (768, 1024, 1536)}
    manifest = {"format": 1, "labels": labels, "seeds": seeds, "seed_block": 91,
                "genotype_sha256": {label: hashlib.sha256(genome.tobytes()).hexdigest()
                                    for label, genome in zip(labels, genomes)},
                "checkpoint_sha256": checkpoint_hashes, "search_health": search_health,
                "protocol_sha256": sha(STUDY / "protocol.json"),
                "numerical_identity": identity, "ready": ready,
                "worlds": {name: asdict(world) for name, world in worlds.items()},
                "selection": "Exactly final population rank0 from each completed16-generation run; no reselection"}
    out = STUDY / "confirmation"
    previous = out / "manifest.json"
    if previous.exists() and json.loads(previous.read_text()) != manifest:
        raise ValueError("confirmation inputs changed")
    if not previous.exists() and out.exists() and any(out.rglob("*.npz")):
        raise ValueError("cached confirmation rows have no manifest")
    save(previous, manifest)
    atomic_npz(out / "genotypes.npz", genomes=genomes, labels=np.asarray(labels))
    index_path = out / "row_index.json"
    index = json.loads(index_path.read_text()) if index_path.exists() else {}
    for relative, digest in index.items():
        if sha(out / relative) != digest:
            raise ValueError("cached confirmation row differs from checkpoint hash")
    all_rows, report = {}, {"report_only": True, "status": "incomplete", "worlds": {}, "primary": {}}
    for name, world in worlds.items():
        rows = {}
        for i in range(4):
            rows[i] = score_row(out / name, i, genomes, world, seeds, evaluator, 2)
            path = out / name / f"row_{i:04d}.npz"
            index[str(path.relative_to(out))] = sha(path)
            save(index_path, index)
        atomic_npz(out / name / "scores.npz", seeds=np.asarray(seeds, dtype=np.uint64),
                   genome_indices=np.arange(4), **{key: np.stack([rows[i][key] for i in range(4)]) for key in COLS})
        all_rows[name] = rows
        report["worlds"][name] = {
            labels[i]: {"vs_founder": compare_rows(rows[i], rows[1], world),
                        "vs_pilot": compare_rows(rows[i], rows[0], world)} for i in (2, 3)}
        save(out / "report.json", report)
    for i in (2, 3):
        by_seed = duration_mixture(all_rows, i, 1)
        estimate = paired(by_seed, np.zeros_like(by_seed))
        report["primary"][labels[i]] = {**estimate, "above_3se": estimate["mean"] > 3 * estimate["se"],
                                       "at_least_0p5": estimate["mean"] >= 0.5}
    report.update(status="complete", independent_search_replicates=2,
                  interpretation="Each primary averages three duration effects within seed before computing SE; "
                                 "the256 seed clusters are shared across runs. This is two exploratory continuations, "
                                 "not an estimate of general search reliability or evidence of a new algorithm.")
    save(out / "report.json", report)


def child_cpu():
    usage = resource.getrusage(resource.RUSAGE_CHILDREN)
    return usage.ru_utime + usage.ru_stime


def active_cpu(pid):
    try:
        fields = Path(f"/proc/{pid}/stat").read_text().rsplit(")", 1)[1].split()
        return (int(fields[11]) + int(fields[12])) / os.sysconf("SC_CLK_TCK")
    except FileNotFoundError:
        return 0.0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", action="store_true")
    parser.add_argument("--confirm-child", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args()
    protocol = check_protocol()
    if args.confirm_child:
        confirm_endpoints()
        return
    commands = {f"evolve_s{seed}": [str(ROOT / ".venv/bin/python"), "-m", "src.run", "--config",
                                   str(ROOT / protocol["configs"][str(seed)]["path"])]
                for seed in protocol["runs"]}
    commands["confirmation"] = [str(ROOT / ".venv/bin/python"), str(Path(__file__)), "--confirm-child"]
    if not args.run:
        print(json.dumps({"status": "dry_run", "commands": commands, "max_cpu_seconds": 10800,
                          "planned_genome_lives": protocol["planned_genome_lives"],
                          "note": "No simulation or numerical golden replay was executed."}, indent=2))
        return
    check_ready()
    status_path = STUDY / "budget.json"
    if status_path.exists():
        raise SystemExit("Existing budget record: inspect consumed resources before any continuation/restart.")
    fast_cpus = os.sched_getaffinity(0).intersection(range(12))
    if not fast_cpus:
        raise SystemExit("Expected fast CPUs0-11 are unavailable; inspect host affinity.")
    os.sched_setaffinity(0, fast_cpus)
    env = dict(os.environ, ATEN_CPU_CAPABILITY="avx2", OMP_WAIT_POLICY="PASSIVE", OMP_NUM_THREADS="2",
               MKL_NUM_THREADS="2", CELL_DEV_CACHE=str(ROOT / "outputs/e1_resume/kernel-cache"), PYTHONUNBUFFERED="1")
    # This environment variable could silently enlarge the registered worker budget.
    env.pop("CELLDEV_THREADS_FILE", None)
    queue, running, completed = list(commands)[:2], {}, []
    start, stopped, confirmation_queued = time.monotonic(), None, False
    while queue or running or not confirmation_queued:
        cpu = child_cpu() + sum(active_cpu(pid) for pid in running)
        if cpu >= protocol["max_cpu_seconds"] - 10:
            stopped = "cpu_budget_exhausted"
        if stopped:
            queue.clear()
            confirmation_queued = True
            for pid in running:
                try:
                    os.killpg(pid, signal.SIGTERM)
                except ProcessLookupError:
                    pass
        if not queue and not running and len(completed) == 2 and not stopped and not confirmation_queued:
            queue.append("confirmation")
            confirmation_queued = True
        while queue and len(running) < 2 and not stopped:
            name = queue.pop(0)
            check_protocol()
            check_ready()
            log_path = STUDY / "logs" / f"{name}.log"
            log_path.parent.mkdir(parents=True, exist_ok=True)
            log = log_path.open("a")
            process = subprocess.Popen(commands[name], cwd=ROOT, env=env, stdout=log, stderr=subprocess.STDOUT,
                                       start_new_session=True)
            running[process.pid] = (process, log, name)
            print(f"Started {name}: pid{process.pid}", flush=True)
        for pid, (process, log, name) in list(running.items()):
            code = process.poll()
            if code is not None:
                log.close()
                completed.append({"name": name, "exit_code": code})
                del running[pid]
                if code and not stopped:
                    stopped = "job_failed"
        cpu = child_cpu() + sum(active_cpu(pid) for pid in running)
        save(status_path, {"cpu_seconds": cpu, "cap_cpu_seconds": protocol["max_cpu_seconds"],
                           "wall_seconds": time.monotonic() - start, "affinity": sorted(fast_cpus),
                           "running": {str(pid): entry[2] for pid, entry in running.items()},
                           "completed": completed, "queued": queue,
                           "status": stopped or ("running" if running or queue or not confirmation_queued else "complete")})
        if running or queue or not confirmation_queued:
            time.sleep(2)
    raise SystemExit(1 if stopped else 0)


if __name__ == "__main__":
    main()
