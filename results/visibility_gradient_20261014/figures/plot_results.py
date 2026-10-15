"""Plot completed Y confirmation results without loading the simulator."""
import argparse
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("summary", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    data = json.loads(args.summary.read_text())
    if data["status"] != "complete" or data["research_lives"] != 6208:
        raise ValueError("Complete registered study required")
    parents = ("D90", "L92")
    fig, axes = plt.subplots(1, 2, figsize=(10, 4.4), layout="constrained")
    x = np.arange(len(parents))
    definitions = (
        (("Fitness", "columns", "F"),
         ("Capture income", "fitness_pieces", "capture_income"),
         ("Physical cost savings", None, "total_cost_saving")),
        (("All captures", "columns", "captures"),
         ("Dark captures", "columns", "low_light_captures"),
         ("Bright captures", "columns", "bright_captures")),
    )
    colors = ("#264653", "#2a9d8f", "#d57933")
    for ax, entries in zip(axes, definitions, strict=True):
        for i, (label, group, key) in enumerate(entries):
            values = []
            for parent in parents:
                result = data["backgrounds"][parent]["confirmation"]
                item = result[group][key] if group else result[key]
                if item["n"] != 512:
                    raise ValueError("Each point must use all 512 paired seeds")
                values.append(item)
            ax.errorbar(x + (i - 1) * .2, [v["mean"] for v in values],
                        yerr=[v["se"] for v in values], fmt="o", capsize=4,
                        color=colors[i], label=label)
        ax.axhline(0, color="0.65", linewidth=.8)
        ax.set_xticks(x, parents)
        ax.set_xlabel("Evolved founder background")
        ax.spines[["top", "right"]].set_visible(False)
        ax.legend(frameon=False, fontsize=9)
    axes[0].set_ylabel("Selected mutant − parent (F)")
    axes[1].set_ylabel("Selected mutant − parent (captures per life)")
    fig.suptitle("Ordinary mutations in irregular blink", fontsize=14)
    fig.supxlabel("Fresh confirmation: 512 paired lives per background; error bars ±1 SE.\n"
                  "Fixed genomes selected on separate 32-life screens; dark captures alone do not identify memory.",
                  fontsize=9)
    args.out.mkdir(parents=True, exist_ok=True)
    for extension in ("png", "svg"):
        fig.savefig(args.out / ("confirmation." + extension), dpi=180)
    plt.close(fig)


if __name__ == "__main__":
    main()
