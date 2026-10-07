"""Aggregate sweep results into a markdown table, a CSV and learning curves (valid solid, held-out dashed).

    python scripts/aggregate.py outputs/memory_sweep [outputs/other_sweep ...] --out results/memory_sweep
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd


def load(dirs):
    rows, curves = [], []
    for d in dirs:
        for res in sorted(Path(d).glob("*/results.jsonl")):
            for line in res.read_text().splitlines():
                rows.append({**json.loads(line), "sweep": Path(d).name})
            for line in (res.parent / "curves.jsonl").read_text().splitlines():
                c = json.loads(line)
                if "valid" in c:
                    curves.append({**c, "run": res.parent.name, "sweep": Path(d).name})
    return pd.DataFrame(rows), pd.DataFrame(curves)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("dirs", nargs="+")
    p.add_argument("--out", required=True)
    args = p.parse_args()
    df, curves = load(args.dirs)
    # runs that never reached skill are censored, not dropped: their evals_to_skill is +inf, so a group's median is inf
    # when most of its seeds failed ("reached" counts the seeds that got there)
    df["evals_to_skill"] = df["evals_to_skill"].astype(float)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    df.to_csv(out / "results.csv", index=False)
    summary = (
        df.groupby(["sweep", "task", "lattice", "breeding"])
        .agg(runs=("seed", "count"), valid=("valid_score", "median"), heldout=("heldout_score", "median"),
             no_messages=("heldout_no_messages", "median"), shuffled=("heldout_shuffled_types", "median"),
             cells=("n_cells", "median"), energy=("energy", "median"), rung=("rung", "median"),
             reached=("evals_to_skill", "count"), evals_to_skill=("evals_to_skill", "median"))
        .reset_index()
    )
    censored = df.assign(evals_to_skill=df["evals_to_skill"].fillna(float("inf")))
    summary["evals_to_skill"] = (censored.groupby(["sweep", "task", "lattice", "breeding"])["evals_to_skill"].median()
                                 .reset_index(drop=True))
    summary.to_csv(out / "summary.csv", index=False)
    try:
        table = summary.to_markdown(index=False, floatfmt=".3g")
    except ImportError:  # tabulate not installed
        table = summary.to_string(index=False, float_format=lambda x: f"{x:.3g}")
    (out / "summary.md").write_text(table + "\n")
    print(table)
    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        curves["group"] = curves["sweep"] + "/" + curves["run"].str.replace(r"_s\d+$", "", regex=True)
        fig, ax = plt.subplots(figsize=(8, 4.5))
        for group, g in curves.groupby("group"):
            med = g.groupby("gen")[["evals", "valid", "heldout"]].median().set_index("evals")
            line, = ax.plot(med.index, med["valid"].values, label=f"{group} valid")
            ax.plot(med.index, med["heldout"].values, ls="--", color=line.get_color(), label=f"{group} held-out")
        ax.set_xlabel("evaluations")
        ax.set_ylabel("score of the best genome (median over seeds)")
        ax.grid(alpha=0.3)
        ax.legend(fontsize=8)
        fig.tight_layout()
        fig.savefig(out / "curves.png", dpi=120)
    except Exception as exc:  # plotting is best-effort
        print("plot skipped:", exc)


if __name__ == "__main__":
    main()
