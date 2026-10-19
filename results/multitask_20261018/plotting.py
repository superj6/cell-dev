#!/usr/bin/env python3
"""Plot saved confirmation summaries; no simulator calls or new evaluations."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D

LINEAGES = [("AO_s7", "AO"), ("D90_Z_s5", "D90"), ("speck_s6", "s6"), ("speck_s8", "s8")]
TRAINED = [
    ("pool", "Moving food"),
    ("persistent", "Persistent movement"),
    ("flash10", "Flashing, then dim"),
    ("flash00", "Flashing, then dark"),
    ("patches", "Replenishing patches"),
    ("contact_food", "Contact-food patches"),
    ("harmful_decoy", "Food with harmful decoy"),
]
RESERVED = [
    ("pool_transfer", "Moving food"),
    ("persistent_transfer", "Persistent movement"),
    ("flash_dim_transfer", "Flashing, then dim"),
    ("flash_dark_transfer", "Flashing, then dark"),
    ("patches_transfer", "Replenishing patches"),
    ("contact_food_transfer", "Contact-food patches"),
    ("harmful_decoy_transfer", "Food with harmful decoy"),
]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--study", type=Path, default=Path("outputs/multitask_20261018"))
    parser.add_argument("--out", type=Path, default=Path(__file__).resolve().parent)
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    data = {}
    sources = {}
    rows = []
    for lineage, _ in LINEAGES:
        path = args.study / "runs" / lineage / "confirmation" / "summary.json"
        raw = path.read_bytes()
        summary = json.loads(raw)
        assert summary["status"] == "complete"
        data[lineage] = summary
        sources[lineage] = {"path": str(path), "sha256": hashlib.sha256(raw).hexdigest()}
        for group, tasks in [("trained", TRAINED), ("reserved", RESERVED)]:
            for task, label in tasks:
                value = summary["paired"]["g250_minus_g0"][task]["captures"]
                assert value["n"] == 512
                for stage in ["0", "250"]:
                    assert summary["results"][stage][task]["captures"]["n"] == 512
                rows.append({"lineage": lineage, "group": group, "task": task,
                             "label": label, "g0_mean": summary["results"]["0"][task]["captures"]["mean"],
                             "g250_mean": summary["results"]["250"][task]["captures"]["mean"],
                             "paired_change": value["mean"], "paired_se": value["se"], "lives": value["n"]})
    with (args.out / "captures.csv").open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    (args.out / "sources.json").write_text(json.dumps(sources, indent=2) + "\n")

    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 11,
                         "axes.spines.top": False, "axes.spines.right": False,
                         "axes.spines.left": False, "svg.fonttype": "none"})
    fig, axes = plt.subplots(1, 4, figsize=(16, 9), sharex=True, sharey=True)
    fig.subplots_adjust(left=0.215, right=0.975, bottom=0.205, top=0.79, wspace=0.15)
    training_color, reserved_color = "#24639d", "#188272"
    ys = list(range(7)) + list(range(8, 15))
    for ax, (lineage, label) in zip(axes, LINEAGES):
        ax.axvspan(-2, 0, color="#faf0ee", zorder=0)
        ax.axhspan(7.45, 14.6, color="#f2f8f7", zorder=0)
        ax.axvline(0, color="#5b6570", lw=1.2)
        ax.axhline(7, color="#aeb8be", lw=0.7)
        for _group, tasks, color, offset in [("trained", TRAINED, training_color, 0),
                                            ("reserved", RESERVED, reserved_color, 8)]:
            for i, (task, _) in enumerate(tasks):
                estimate = data[lineage]["paired"]["g250_minus_g0"][task]["captures"]
                ax.errorbar(estimate["mean"], i + offset, xerr=3 * estimate["se"],
                            fmt="o", color=color, markeredgecolor="white", markeredgewidth=0.7,
                            markersize=7, capsize=3, elinewidth=1.7, zorder=3)
        ax.set_title(label, fontsize=16, fontweight="bold", pad=17)
        ax.set_xlim(-2, 8)
        ax.set_xticks([-2, 0, 2, 4, 6, 8])
        ax.set_ylim(14.65, -0.65)
        ax.set_yticks(ys, [label for _, label in TRAINED + RESERVED])
        ax.tick_params(axis="y", length=0, pad=12)
        ax.tick_params(axis="x", colors="#46535e")
        ax.grid(axis="x", color="#e1e7eb", linewidth=0.6)
        ax.set_axisbelow(True)
        ax.spines["bottom"].set_color("#b5bfc7")

    fig.text(0.065, 0.943, "Food collection after 250 generations", fontsize=23, fontweight="bold", color="#162636")
    fig.text(0.065, 0.902, "One unchanged reporting genome per stage across tasks · 512 fresh lives per condition", fontsize=13, color="#455461")
    fig.legend(handles=[Line2D([0], [0], marker="o", color=training_color, label="Trained conditions", lw=1.7),
                        Line2D([0], [0], marker="o", color=reserved_color, label="Reserved variants", lw=1.7)],
               loc="upper left", bbox_to_anchor=(0.06, 0.87), ncol=2, frameon=False, fontsize=12)
    fig.text(0.595, 0.145, "Change in food captured per life (generation 250 − generation 0)", ha="center", fontsize=13)
    fig.text(0.065, 0.09, "Bars: ±3 paired standard errors; descriptive uncertainty, without correction for multiple comparisons.", fontsize=10.5, color="#43515c")
    fig.text(0.065, 0.061, "Food counts exclude costs and harmful taps. Patch totals include initial, passive-regrowth and contact-regrowth food. Matching is omitted.", fontsize=10.5, color="#43515c")
    fig.text(0.065, 0.032, "Reserved variants change world parameters. These comparisons alone do not establish memory, useful internal circuitry, or superiority to another selection method.", fontsize=10.5, color="#43515c")
    fig.savefig(args.out / "food_changes.png", dpi=160, facecolor="white")
    fig.savefig(args.out / "food_changes.svg", facecolor="white")
    plt.close(fig)
    print(f"Saved food_changes.png and food_changes.svg; {len(rows)} paired estimates from four saved summaries.")


if __name__ == "__main__":
    main()
