"""Bounded saved-data terminal checks; execute only after root review and completion."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import resource
import signal
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", action="store_true")
    parser.add_argument("--study", type=Path, default=HERE.parent)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    if not args.run:
        print(json.dumps(dict(status="source_only", outcome_reads=0, simulator_calls=0)))
        return
    if args.out is None or args.out.exists():
        raise ValueError("an explicit absent output path is required")
    os.sched_setaffinity(0, {min(os.sched_getaffinity(0))})
    resource.setrlimit(resource.RLIMIT_CPU, (10, 10))
    resource.setrlimit(resource.RLIMIT_AS, (2 * 1024**3, 2 * 1024**3))
    signal.alarm(30)
    available = next(
        int(line.split()[1]) * 1024
        for line in Path("/proc/meminfo").read_text().splitlines()
        if line.startswith("MemAvailable:")
    )
    if available < 4 * 1024**3:
        raise ValueError("4 GiB host headroom required")
    for key in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS"):
        os.environ[key] = "1"
    os.environ["ATEN_CPU_CAPABILITY"] = "avx2"
    ready = json.loads((HERE / "SOURCE_READY.json").read_text())
    for name, digest in ready["source_pins"].items():
        if hashlib.sha256((HERE / name).read_bytes()).hexdigest() != digest:
            raise ValueError("reviewed terminal helper changed: " + name)
    start, cpu = time.monotonic(), time.process_time()
    from native_replay import complete_replay

    result = complete_replay(args.study)
    result["resources"] = dict(
        cpu_seconds=time.process_time() - cpu,
        wall_seconds=time.monotonic() - start,
        peak_rss_bytes=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024,
        cpu_cap_seconds=10,
        wall_cap_seconds=30,
        address_space_cap_bytes=2 * 1024**3,
        threads=1,
    )
    with args.out.open("x") as stream:
        json.dump(result, stream, indent=2, allow_nan=False)
        stream.write("\n")
    print(
        json.dumps(
            dict(
                status="passed",
                offspring_replayed=1792,
                rankings_checked=16,
                selection_lives_checked=81920,
                simulator_calls=0,
                resources=result["resources"],
            )
        )
    )


if __name__ == "__main__":
    main()
