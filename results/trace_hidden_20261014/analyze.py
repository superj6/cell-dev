"""Describe delivered hidden/act inputs in completed K traces, without simulator imports."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np

LABELS = ("founder_row38", "d_s51089_final_rank0", "d_s51090_final_rank0")
SEEDS = tuple(range(51_890_000, 51_890_004))
ARCHIVE_SHA = "6ab3b6a5d4f5f0db561cf5ca37a191a8f824065720583de7e63a6de74e7106ed"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def describe(data, label, seed):
    source_z, target = data["arrivals__sz"], data["arrivals__cid"]
    steps, times = data["arrivals__step"], data["arrivals__t"]
    values = data["arrivals__contrib"]
    cell_z, refractory = data["cells__z"], data["steps__refractory"]
    if any(a.shape != times.shape for a in (source_z, target, steps, values)):
        raise ValueError("unaligned arrival columns")
    if (np.any(target < 0) or np.any(target >= len(cell_z)) or np.any(steps < 0)
            or np.any(steps >= len(refractory)) or not np.isfinite(values).all()):
        raise ValueError("invalid arrival reference or contribution")
    nonrefractory = ~refractory[steps]
    rows = []
    for start in (0, 800):
        for path, mask in (
            ("hidden_to_act", (source_z >= 2) & (cell_z[target] == 1)),
            ("act_to_hidden", (source_z == 1) & (cell_z[target] >= 2)),
        ):
            selected = values[nonrefractory & mask & (times >= start)]
            rows.append(dict(genotype=label, seed=seed, start=start, path=path,
                             arrivals=len(selected), mean=float(selected.mean()) if len(selected) else None,
                             negative_share=float((selected < 0).mean()) if len(selected) else None,
                             positive_share=float((selected > 0).mean()) if len(selected) else None))
    return rows


def analyze(archive):
    if sha(archive / "provenance.json") != ARCHIVE_SHA:
        raise ValueError("completed K archive identity differs")
    manifest = json.loads((archive / "provenance.json").read_text())
    report_path = archive / "measurement/report.json"
    if sha(report_path) != manifest["artifacts"]["measurement/report.json"]["sha256"]:
        raise ValueError("trace report differs")
    report = json.loads(report_path.read_text())
    expected = {(label, seed) for label in LABELS for seed in SEEDS}
    actual = [(life["label"], life["seed"]) for life in report["lives"]]
    if report["status"] != "complete" or len(actual) != 12 or set(actual) != expected:
        raise ValueError("need all twelve fixed completed traces")
    rows, sources = [], {}
    for life in report["lives"]:
        relative = "measurement/" + life["trace"]
        path = archive / relative
        if (sha(path) != life["sha256"] or life["sha256"] != manifest["artifacts"][relative]["sha256"]
                or path.stat().st_size != manifest["artifacts"][relative]["bytes"]):
            raise ValueError("trace bytes differ")
        with np.load(path, allow_pickle=False) as data:
            rows.extend(describe(data, life["label"], life["seed"]))
        sources[relative] = life["sha256"]
    return dict(status="exploratory_completed_data_only", simulated_lives=0, rows=rows,
                trace_manifest_sha256=ARCHIVE_SHA, traces=sources,
                limits=["Normal growing lives, not H frozen interventions.",
                        "Actual nonrefractory arrival contributions; zero contributions retained.",
                        "Four descriptive lives per genotype; each life is one unit.",
                        "Input sign and event counts do not identify a causal fitness mechanism.",
                        "The bodies differ in size, state and geometry."])


def render(summary):
    lines = ["# Hidden-cell inputs in twelve saved traces", "",
             "This is an exploratory reanalysis of completed K data. It simulates no new lives.", "",
             "In all four saved D51090 lives, almost all delivered hidden-to-act inputs after t800 are negative.",
             "Act-to-hidden inputs are predominantly positive. This is consistent with inhibitory feedback,",
             "but the founder also has negative hidden-to-act inputs. These signs do not explain the causal",
             "hidden-message fitness effect measured in H: K uses normal growing lives, while H freezes tissue.", "",
             "Each row below describes one life over t800..1536. Counts include only arrivals outside the",
             "receiver's refractory period. Mean input is the effective membrane contribution; zeros remain",
             "in counts and sign fractions. An arrival is not an independent experimental replicate.", "",
             "| Genotype | Seed | Hidden → act arrivals | Mean input | Negative | Act → hidden arrivals | Mean input | Positive |",
             "|---|---:|---:|---:|---:|---:|---:|---:|"]
    for label in LABELS:
        for seed in SEEDS:
            selected = {r["path"]: r for r in summary["rows"]
                        if r["genotype"] == label and r["seed"] == seed and r["start"] == 800}
            h, a = selected["hidden_to_act"], selected["act_to_hidden"]
            lines.append(f"| {label} | {seed} | {h['arrivals']} | {h['mean']:.4f} | "
                         f"{h['negative_share']:.1%} | {a['arrivals']} | {a['mean']:.4f} | "
                         f"{a['positive_share']:.1%} |")
    lines.extend(["", "All 48 per-life descriptions, including full lifetimes, are in `summary.json`.",
                  "The analyzer uses NumPy and the unchanged public K archive, with no simulator imports.",
                  "From the repository root:", "", "```sh",
                  ".venv/bin/python results/trace_hidden_20261014/analyze.py \\",
                  "  --archive results/traces_20261014 --out outputs/trace_hidden_reanalysis",
                  "```", "", "The original exploratory script, its output and the independent review are preserved",
                  "under `review/`. The portable analyzer reproduces every descriptive row exactly.",
                  "This evidence suggests a mechanism to test; it does not establish memory or an algorithm.", ""])
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    summary = analyze(args.archive)
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "summary.json").write_text(json.dumps(summary, indent=2, allow_nan=False) + "\n")
    (args.out / "README.md").write_text(render(summary))
    print(json.dumps({"status": summary["status"], "rows": len(summary["rows"]), "simulated_lives": 0}))


if __name__ == "__main__":
    main()
