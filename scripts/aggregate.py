"""Aggregate sweep results into a markdown table, a CSV and learning curves (valid solid, held-out dashed).

    python scripts/aggregate.py outputs/memory_sweep [outputs/other_sweep ...] --out results/memory_sweep

Rows are mode-aware. Legacy (``mode: trials``) rows give summary.csv / summary.md as before. Life rows
(``mode: life``) are grouped by world, control, lattice, breeding and selection scheme (``one-stage``, or
``recheck K64 L4 all`` for two-stage selection) into summary_life.csv, and their table is appended to summary.md: F
of the best genome on fresh lives, size (n_end, n_peak), income and cost rates, extinction rate, reliance on spikes
(income lost when spikes are undelivered from T/2), evaluations to skill and ``git``, the code revisions the group's
runs started from (short hashes, ``+dirty`` if any ran from a dirty tree, ``?`` for rows that predate the field).
Two-stage groups also report what the recheck did to bodies over all their runs and generations: ``bodies_kept``,
the bodies among the chosen parents over those among the parents one-stage selection would have chosen, and
``body_losses``, the generations where the recheck dropped every such body (empty for one-stage groups).

Every life F, valid and held-out score is measured under base physics, whatever the selection lives were (the
envelope control changes selection only), so conditions compare like for like; ``F_envelope`` is the same final lives
under envelope physics for every condition (robustness). Rows written before that rule (no ``selection_physics``
field) are refused for the envelope control, whose F was then measured under envelope physics.
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


LIFE_KEYS = ["sweep", "world", "control", "lattice", "breeding", "selection"]


def selection(row) -> str:
    """The selection scheme of a life results row (rows without recheck fields are one-stage)."""
    k = row.get("recheck_k")
    if k is None or k != k or not k:  # missing, NaN or 0
        return "one-stage"
    return f"recheck K{int(k)} L{int(row['recheck_lives'])} {row['recheck_key']}"


def git_label(row) -> str:
    """Short revision of a results row, ``+dirty`` if the tree was dirty, ``?`` without the field."""
    rev = row.get("git_rev")
    if not isinstance(rev, str):
        return "?"
    return rev[:7] + ("+dirty" if row.get("git_dirty") is True else "")


def _median_censored(df, keys):
    """Median evaluations to skill with runs that never got there counted as +inf (censored, not dropped)."""
    censored = df.assign(evals_to_skill=df["evals_to_skill"].fillna(float("inf")))
    return censored.groupby(keys)["evals_to_skill"].median().reset_index(drop=True)


def _table(summary) -> str:
    try:
        return summary.to_markdown(index=False, floatfmt=".3g")
    except ImportError:  # tabulate not installed
        return summary.to_string(index=False, float_format=lambda x: f"{x:.3g}")


def life_summary(df):
    """One row per life condition (world, control, lattice, breeding, selection) over its seeds: medians unless
    noted."""
    for col, default in (("control", "full"), ("msg_reliance", float("nan")), ("evals_to_skill", float("nan")),
                         ("F_envelope", float("nan")), ("death_lift", float("nan")),
                         ("selection_physics", None), ("recheck_bodies", float("nan")),
                         ("recheck_bodies_onestage", float("nan")), ("recheck_body_losses", float("nan"))):
        if col not in df:
            df[col] = default
    df = df.assign(control=df["control"].fillna("full"), msg_reliance=df["msg_reliance"].astype(float),
                   evals_to_skill=df["evals_to_skill"].astype(float), F_envelope=df["F_envelope"].astype(float),
                   death_lift=df["death_lift"].astype(float), recheck_bodies=df["recheck_bodies"].astype(float),
                   recheck_bodies_onestage=df["recheck_bodies_onestage"].astype(float),
                   recheck_body_losses=df["recheck_body_losses"].astype(float))
    df = df.assign(selection=[selection(r) for r in df.to_dict("records")],
                   git=[git_label(r) for r in df.to_dict("records")])
    old = (df["control"] == "envelope") & df["selection_physics"].isna()
    if old.any():
        raise ValueError(f"{int(old.sum())} envelope-control rows predate base-physics final lives (their F, valid "
                         "and held-out scores were measured under envelope physics): rerun them")
    summary = (
        df.groupby(LIFE_KEYS)
        .agg(runs=("seed", "count"), F=("F", "median"), F_mean=("F", "mean"), F_best=("F", "max"),
             valid=("valid_score", "median"), heldout=("heldout_score", "median"), cells=("n_cells", "median"),
             n_peak=("n_peak", "median"), income=("income", "median"), energy=("energy", "median"),
             income_per_cell=("income_per_cell", "median"), extinction=("extinction_rate", "median"),
             msg_reliance=("msg_reliance", "median"), F_envelope=("F_envelope", "median"),
             death_lift=("death_lift", "median"), reached=("evals_to_skill", "count"),
             evals_to_skill=("evals_to_skill", "median"), git=("git", lambda x: ",".join(sorted(set(x)))),
             bodies_kept=("recheck_bodies", lambda x: x.sum(min_count=1)),
             onestage=("recheck_bodies_onestage", lambda x: x.sum(min_count=1)),
             body_losses=("recheck_body_losses", lambda x: x.sum(min_count=1)))
        .reset_index()
    )
    summary["evals_to_skill"] = _median_censored(df, LIFE_KEYS)
    summary["bodies_kept"] = summary["bodies_kept"] / summary.pop("onestage")  # NaN when one-stage or no bodies
    return summary


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
    is_life = (df["mode"] == "life") if "mode" in df else pd.Series(False, index=df.index)
    tables = []
    trials = df[~is_life]
    if len(trials):
        trials = trials.reset_index(drop=True)
        summary = (
            trials.groupby(["sweep", "task", "lattice", "breeding"])
            .agg(runs=("seed", "count"), valid=("valid_score", "median"), heldout=("heldout_score", "median"),
                 no_messages=("heldout_no_messages", "median"), shuffled=("heldout_shuffled_types", "median"),
                 cells=("n_cells", "median"), energy=("energy", "median"), rung=("rung", "median"),
                 reached=("evals_to_skill", "count"), evals_to_skill=("evals_to_skill", "median"))
            .reset_index()
        )
        summary["evals_to_skill"] = _median_censored(trials, ["sweep", "task", "lattice", "breeding"])
        summary.to_csv(out / "summary.csv", index=False)
        tables.append(_table(summary))
    if is_life.any():
        life = life_summary(df[is_life].reset_index(drop=True))
        life.to_csv(out / "summary_life.csv", index=False)
        tables.append(("## life\n\n" if tables else "") + _table(life))
    table = "\n\n".join(tables)
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
        ylabel = "score of the best genome (median over seeds)"
        if is_life.all():
            ylabel = "F of the best genome on fresh lives (median over seeds)"
        ax.set_ylabel(ylabel)
        ax.grid(alpha=0.3)
        ax.legend(fontsize=8)
        fig.tight_layout()
        fig.savefig(out / "curves.png", dpi=120)
    except Exception as exc:  # plotting is best-effort
        print("plot skipped:", exc)


if __name__ == "__main__":
    main()
