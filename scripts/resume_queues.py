"""Resume local queues (scripts/run_local_queue.py) after a reboot, a crash or a host-memory pause.

    python scripts/resume_queues.py [--registry outputs/autoresume_queues.txt] [--min-available-gib 6]

Meant for cron (``@reboot`` and every 15 minutes). It acts only on the queue directories listed in the registry (one
per line), and only when the queue's monitor is not alive and either
- the queue was still marked running (its monitor died with the machine), or
- the queue stopped itself on the host-memory floor,
and the host has at least ``--min-available-gib`` available. It never touches a queue that finished, that was stopped
on purpose (``--stop``: reason ``signal``) or that hit its CPU, wall-clock or RSS limit.

The queue never retries a job implicitly, so this script names the jobs to retry: every ``interrupted`` or
``stopped`` job. When the dead monitor left jobs marked running, a first resume lets the queue mark them interrupted;
that monitor is then stopped and the queue resumed again with the retries. Jobs resume from their own checkpoints.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
QUEUE = ROOT / "scripts" / "run_local_queue.py"
sys.path.insert(0, str(ROOT / "scripts"))
import run_local_queue as rq  # noqa: E402


def available_gib() -> float:
    for line in Path("/proc/meminfo").read_text().splitlines():
        if line.startswith("MemAvailable:"):
            return int(line.split()[1]) / 1024 ** 2
    return 0.0


def state(q: Path) -> dict:
    return json.loads((q / "monitor.json").read_text())


def monitor_alive(s: dict) -> bool:
    try:
        return rq.alive(s["monitor"], rq.table())
    except (KeyError, TypeError):
        return False


def queue(q: Path, *args: str) -> None:
    argv = [sys.executable, str(QUEUE), "--out", str(q)]
    if "--stop" not in args:
        argv += ["--jobs", str(q / "jobs.json"), "--resume", "--detach"]
    subprocess.run(argv + list(args), check=True, cwd=ROOT)


def wait(q: Path, done, seconds: float = 60.0) -> dict:
    t = time.time()
    while time.time() - t < seconds:
        s = state(q)
        if done(s):
            return s
        time.sleep(2)
    return state(q)


def resume(q: Path, log) -> None:
    s = state(q)
    if s["status"] == "complete" or monitor_alive(s):
        return
    if not (s["status"] == "running" or s.get("stop_reason") == "host_memory_floor"):
        return  # finished, stopped on purpose, or stopped on a CPU, wall-clock or RSS limit
    if any(j["status"] in ("running", "launching") for j in s["jobs"]):
        log(f"{q}: monitor gone with jobs marked running; letting the queue mark them interrupted")
        queue(q)
        time.sleep(15)  # the new monitor marks the dead workers interrupted (and may start pending jobs)
        s = state(q)
        if s["status"] == "running" and monitor_alive(s):
            queue(q, "--stop")  # it exits by itself when nothing was left to start
        s = wait(q, lambda x: x["status"] != "running", 120)
    retry = [j["spec"]["id"] for j in s["jobs"] if j["status"] in ("interrupted", "stopped")]
    args = [a for r in retry for a in ("--retry", r)]
    log(f"{q}: resuming with retries {retry}")
    queue(q, *args)


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--registry", default=str(ROOT / "outputs" / "autoresume_queues.txt"))
    p.add_argument("--min-available-gib", type=float, default=6.0)
    args = p.parse_args(argv)
    reg = Path(args.registry)
    if not reg.exists():
        return 0

    def log(msg):
        print(f"{time.strftime('%Y-%m-%d %H:%M:%S')} {msg}", flush=True)

    queues = [Path(line.strip()) for line in reg.read_text().splitlines() if line.strip() and not line.startswith("#")]
    for q in queues:
        if not (q / "monitor.json").exists():
            continue
        s = state(q)
        if s["status"] == "complete" or monitor_alive(s):
            continue
        if available_gib() < args.min_available_gib:
            log(f"{q}: needs resuming but only {available_gib():.1f} GiB available; waiting")
            continue
        try:
            resume(q, log)
        except (subprocess.CalledProcessError, ValueError, OSError) as e:
            log(f"{q}: resume failed: {e!r}")
    return 0


if __name__ == "__main__":
    os.nice(5)
    sys.exit(main())
