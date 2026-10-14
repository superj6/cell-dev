"""Small, report-only E6 batches; write incremental results under outputs/<study>/.

Example: .venv/bin/python scripts/life_readouts.py --body router@ring4 --out outputs/e6_readouts/router
BH3 consumes scores with matching seeds, worlds and footprints; see docs/PROBE.md for its input format.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.genome import Layout  # noqa: E402
from src.life import analysis, handbuilt, probe, readouts, spec  # noqa: E402


def write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(".tmp")
    temp.write_text(json.dumps(readouts.json_safe(data), indent=2, allow_nan=False) + "\n")
    temp.replace(path)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    source = p.add_mutually_exclusive_group()
    source.add_argument("--body", default="reflex@hollow3")
    source.add_argument("--genome", type=Path)
    p.add_argument("--world", choices=("base", "pool"), default="base")
    p.add_argument("--lives", type=int, default=8)
    p.add_argument("--trace-lives", type=int, default=1)
    p.add_argument("--seed-base", type=int, default=46_000_000)
    p.add_argument("--T", type=float, default=256.0)
    p.add_argument("--fork", type=float, default=128.0)
    p.add_argument("--silence-window", type=float, default=0.5,
                   help="report distance after this many time units without a delivered ping (default: one base hop)")
    p.add_argument("--threads", type=int, default=1)
    p.add_argument("--bh3-scores", type=Path, help="JSON with best/reflex/c4 Scores records on matching footprints")
    p.add_argument("--out", type=Path, default=ROOT / "outputs" / "e6_readouts")
    a = p.parse_args()
    if a.lives < 2 or not 0 <= a.trace_lives <= a.lives or not 0 <= a.fork < a.T or a.threads < 1:
        p.error("need lives >= 2, 0 <= trace-lives <= lives, 0 <= fork < T, and threads >= 1")
    if a.silence_window <= 0:
        p.error("silence-window must be positive")
    if not a.out.resolve().is_relative_to(ROOT / "outputs"):
        p.error("write study outputs under this repository's outputs/<study>/")
    if a.genome:
        _, genome = Layout.load(a.genome)
        org = handbuilt.GrnBody(a.genome.parent.name, np.asarray(genome, dtype=np.float32).reshape(-1))
    else:
        org, _ = probe.hand(a.body)
    preset = "catch_speck_l4"
    world = dict(T=a.T, d0=0.5, d_min=0.25)
    if a.world == "pool":
        world.update(sigma=0.4, lam_s=4.0)
    seeds = analysis.fresh_seeds(a.lives, a.seed_base)
    fork = dict(t_fork=a.fork, t_open=a.fork)
    base = org.run(seeds, preset=preset, threads=a.threads, **world, **fork)
    off = org.run(seeds, preset=preset, threads=a.threads, fork_flags=spec.V3.flags("lateral_off"), **world, **fork)
    statuses = dict(base=readouts.validate_ledger(base.ledger), lateral_off=readouts.validate_ledger(off.ledger))
    report = dict(schema=1, organism=org.name, preset=preset, world=world, seeds=seeds,
                  status_counts=statuses,
                  lateral=dict(t_fork=a.fork, t_open=a.fork, **readouts.lateral_share(base["F"], off["F"])),
                  raw=dict(base_F=base["F"].tolist(), lateral_off_F=off["F"].tolist()),
                  bh3=dict(status="not measured", reason="requires C4 and best reflex on this best's footprint"),
                  search=[], relay=[], limitations=["small defaults are validation, not fresh-life success claims",
                                                    "lateral_off can also affect development after the fork"])
    if a.bh3_scores:
        inputs = json.loads(a.bh3_scores.read_text())
        scores = [readouts.Scores(**inputs[k]) for k in ("best", "reflex", "c4")]
        if scores[0].seeds != seeds or scores[0].world != dict(preset=preset, **world, t_open=0.0):
            p.error("BH3 score seeds and full-life world must match this report")
        report["bh3"] = readouts.information_share(*scores)
        report["bh3"]["source"] = str(a.bh3_scores)
    path = a.out / "readouts.json"
    write(path, report)
    for seed in seeds[:a.trace_lives]:
        tr = probe.trace(org, seed, preset, **world)
        report["search"].append(readouts.search_signature(tr, silence_window=a.silence_window))
        report["relay"].append(readouts.relay_chains([tr], start=a.fork))
        write(path, report)
    print(path)


if __name__ == "__main__":
    main()
