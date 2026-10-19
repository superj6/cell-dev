"""Render saved tissue positions; no simulator, growth or random-number calls."""
import argparse
import json
import os
from pathlib import Path

os.environ.setdefault("MPLCONFIGDIR", str(Path(__file__).resolve().parent / "mplconfig"))
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D

COLORS = ("#2d9a79", "#e39b42", "#9373b6", "#9373b6")
LAYERS = ("Sensing layer", "Action layer", "Internal layer 1", "Internal layer 2")


def main(data_path, output_path, lineage="speck_s6", time=128):
    data = json.loads(Path(data_path).read_text())
    examples = sorted((e for e in data["examples"] if e["lineage"] == lineage and e["task"] == "pool"),
                      key=lambda e: e["generation"])
    if len(examples) != 3:
        raise ValueError("Exactly three saved pursuit examples are required")
    selected = []
    for example in examples:
        frame = max((f for f in example["frames"] if f["t"] <= time), key=lambda f: f["t"])
        alive = set(frame["alive"])
        cells = [c for c in example["cells"] if c["id"] in alive]
        selected.append((example, frame, cells))
    radius = max(2, max(max(abs(c["x"]), abs(c["y"])) for _, _, cells in selected for c in cells)) + .8
    fig, axes = plt.subplots(4, 3, figsize=(11, 9), dpi=160)
    fig.patch.set_facecolor("#f7f9fb")
    for col, (example, frame, cells) in enumerate(selected):
        fired = set(frame["fired"])
        for z in range(4):
            ax = axes[z, col]
            ax.set_facecolor("#f7f9fb")
            rows = [c for c in cells if c["z"] == z]
            if rows:
                # Same axis limits and marker sizes across every panel preserve anatomical scale.
                ax.scatter([c["x"] for c in rows], [c["y"] for c in rows], marker="h", s=61,
                           c=COLORS[z], edgecolors=["#20364b" if c["id"] in fired else "#f7f9fb" for c in rows],
                           linewidths=[1.15 if c["id"] in fired else .45 for c in rows], zorder=3)
            else:
                ax.text(0, 0, "No cells", ha="center", va="center", fontsize=10, color="#96a2ae")
            ax.set(xlim=(-radius, radius), ylim=(-radius, radius), aspect="equal")
            ax.set_xticks([])
            ax.set_yticks([])
            for spine in ax.spines.values():
                spine.set_visible(False)
            ax.text(.97, .04, f"{len(rows)} cells", transform=ax.transAxes,
                    ha="right", va="bottom", color="#597083", fontsize=9)
            if col == 0:
                ax.text(-.18, .5, LAYERS[z].replace(" layer", "\nlayer"), transform=ax.transAxes,
                        ha="right", va="center", fontsize=11, color="#334d62")
            if z == 0:
                label = "Original example" if col == 0 else "Early evolution" if col == 1 else "Latest example"
                ax.set_title(f"{label}\nGeneration {example['generation']} · {len(cells)} cells",
                             fontsize=13, color="#213346", pad=15, linespacing=1.5)
    fig.suptitle("Three evolved bodies, viewed layer by layer", x=.52, y=.985,
                 fontsize=20, color="#213346", fontweight="semibold")
    fig.text(.52, .936, f"SPECK population 6 · moving-food task · same fixed seed · life time {time}",
             ha="center", fontsize=11, color="#617789")
    fig.subplots_adjust(left=.19, right=.97, top=.86, bottom=.135, wspace=.2, hspace=.08)
    legend = [Line2D([], [], marker="h", linestyle="", color=COLORS[z], markersize=8,
                     label=label) for z, label in [(0, "Sensing"), (1, "Action"), (2, "Internal")]]
    legend.append(Line2D([], [], marker="h", linestyle="", color="#fff", markeredgecolor="#20364b",
                         markersize=8, label="Dark outline: fired in preceding interval"))
    fig.legend(handles=legend, loc="lower center", bbox_to_anchor=(.55, .073), ncol=4,
               fontsize=9, frameon=False, labelcolor="#526b7d", columnspacing=1.5)
    fig.text(.52, .047, "Colors identify positions, not learned cell types. Sizes and coordinates use the same scale.",
             ha="center", fontsize=9, color="#667d8e")
    fig.text(.52, .025, "Different reporting representatives; this is not a direct ancestor–descendant chain or evidence of causal circuitry.",
             ha="center", fontsize=9, color="#667d8e")
    target = Path(output_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(target, facecolor=fig.get_facecolor(), dpi=160)
    plt.close(fig)
    print(json.dumps({"output": str(target), "time": time, "examples": [
        {"key": e["key"], "cells": len(cells), "layers": [sum(c["z"] == z for c in cells) for z in range(4)]}
        for e, _, cells in selected], "simulation_calls": 0}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("data")
    parser.add_argument("output")
    parser.add_argument("--time", type=int, default=128)
    parser.add_argument("--lineage", default="speck_s6")
    args = parser.parse_args()
    main(args.data, args.output, args.lineage, args.time)
