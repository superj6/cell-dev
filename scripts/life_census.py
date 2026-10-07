"""Random-genome census of the one-life founder distribution (docs/ONE_LIFE_DESIGN.md, Code plan step 4).

    python scripts/life_census.py --config configs/life_bell.yaml --samples 4096 --T 512,1024 [key=value ...]

Draws ``--samples`` genomes exactly as founder sampling does (``layout.random`` in batches of ``evolve.init_samples``
from the run seed's generator, so the first batch is the run's first founder batch) and lives each once per horizon
T, every genome on its own life seed (independent lives; the paired horizons share the seed). Per horizon it reports
the distribution of n_end and n_peak, extinctions, guard trips, lone cells (never divided) and lone pumps (lone with
income), the share clearing ``evolve.min_founder_score``, bodies that beat the best lone cell, and the best F found.
The ``--top`` genomes of the longest horizon are then re-measured on ``--top-lives`` fresh lives shared by all of them
(the winner's curse of a one-life screen). Writes ``<out>/census.json`` and prints a markdown summary.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np
import torch

repo_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(repo_root))

from src.common import load_config  # noqa: E402
from src.evolve import setup  # noqa: E402
from src.life import analysis, build, spec  # noqa: E402
from src.life.evaluate import life_seed  # noqa: E402

LONE_BEST_F = 0.0328  # gate G1: the exhaustive best lone cell on fresh lives (+0.03281)
SIZE_BINS = ((1, 1), (2, 3), (4, 9), (10, 31), (32, 99), (100, 319), (320, 1023))
QUANTILES = (0.1, 0.25, 0.5, 0.75, 0.9, 0.99)
COLUMNS = ("F", "income", "n_end", "n_peak", "births", "deaths", "claims", "spikes", "arrivals", "contact_events",
           "events", "t_end", "status", "live_time")


def _frac(mask) -> float:
    return float(np.mean(mask)) if len(mask) else float("nan")


def _q(x) -> list[float]:
    return [float(v) for v in np.quantile(np.asarray(x, dtype=np.float64), QUANTILES)] if len(x) else []


def zygote_census(layout, params, kind: str) -> dict:
    """Shares of zygote phenotypes (theta at g0): tonic (b > 1), contracting, emitting, dividing, and lone-pump capable
    (tonic and contracting)."""
    th = layout.zygote_phenotype(params, kind)
    K = spec.K
    tonic, kappa = th[:, K["b"]] > 1, th[:, K["kappa"]] > 0
    return dict(tonic=_frac(tonic), contracting=_frac(kappa), pump_capable=_frac(tonic & kappa),
                emitting=_frac((th[:, K["emit0"]] > 0) | (th[:, K["emit1"]] > 0)), dividing=_frac(th[:, K["p_div"]] > 0),
                p_div_ge_1_16=_frac(th[:, K["p_div"]] >= 1 / 16), dying=_frac(th[:, K["p_die"]] > 0))


def horizon(col: dict, min_F: float) -> dict:
    """Census statistics of one horizon from per-genome ledger columns."""
    st = col["status"].astype(np.int64)
    extinct = (st & spec.STATUS["extinct"]) != 0
    g_cells = (st & spec.STATUS["guard_cells"]) != 0
    g_events = (st & spec.STATUS["guard_events"]) != 0
    guard = g_cells | g_events
    invalid = (st & spec.STATUS["capacity"]) != 0
    lone = col["births"] == 0
    pump = lone & (col["income"] > 0)
    body = ~lone & ~guard & ~extinct
    F, n_end = col["F"], col["n_end"]
    clear = F >= min_F
    out = dict(
        lives=len(F), extinct=_frac(extinct), guard=_frac(guard), guard_cells=_frac(g_cells), guard_events=_frac(g_events),
        invalid=int(invalid.sum()), lone=_frac(lone), lone_pump=_frac(pump), lone_silent=_frac(lone & ~pump),
        body=_frac(body), body_messaging=_frac(body & (col["arrivals"] > 0)),
        clear_min_F=_frac(clear), clear_min_F_lone=_frac(clear & lone), clear_min_F_body=_frac(clear & ~lone),
        beat_lone_best=_frac(F > LONE_BEST_F), beat_lone_best_body=_frac((F > LONE_BEST_F) & ~lone),
        n_end_q=_q(n_end), n_peak_q=_q(col["n_peak"]), n_end_body_q=_q(n_end[body]), F_q=_q(F),
        F_lone_pump_q=_q(F[pump]), F_body_q=_q(F[body]),
        n_end_bins={f"{lo}-{hi}" if lo != hi else str(lo): _frac((n_end >= lo) & (n_end <= hi) & ~guard)
                    for lo, hi in SIZE_BINS} | {"guard": _frac(guard)},
        guard_t_end_q=_q(col["t_end"][guard]),
        events_share_guard=float(col["events"][guard].sum() / max(col["events"].sum(), 1.0)),
        cell_time_share_guard=float(col["live_time"][guard].sum() / max(col["live_time"].sum(), 1e-300)),
    )
    i = int(np.argmax(F))
    out["best"] = dict(index=i, F=float(F[i]), n_end=float(n_end[i]), n_peak=float(col["n_peak"][i]),
                       income_per_cell_e3=float(1e3 * col["income"][i] / max(col["live_time"][i], 1e-300)))
    if (~lone).any():
        j = int(np.flatnonzero(~lone)[np.argmax(F[~lone])])
        out["best_body"] = dict(index=j, F=float(F[j]), n_end=float(n_end[j]), n_peak=float(col["n_peak"][j]),
                                guard=bool(guard[j]))
    return out


def census(cfg, samples: int, horizons, top: int = 16, top_lives: int = 64, threads: int | None = None,
           chunk: int = 1024, log=print) -> dict:
    """The census of ``samples`` founder-distribution genomes at every horizon T (module docstring)."""
    threads = int(cfg.threads) if threads is None else int(threads)
    torch.set_num_threads(min(threads, 4))
    _, layout, _, ev = setup(cfg)
    e = cfg.evolve
    gen = torch.Generator().manual_seed(int(cfg.seed))
    batch = int(e.init_samples)
    t0 = time.perf_counter()
    params = torch.cat([layout.random(min(batch, samples - i), gen, float(cfg.genome.init_scale))
                        for i in range(0, samples, batch)])
    t_draw = time.perf_counter() - t0
    t0 = time.perf_counter()
    table = ev.table(params)
    t_pack = time.perf_counter() - t0
    min_F = float(e.get("min_founder_score", 0.0))
    out = dict(config=dict(samples=samples, horizons=[int(T) for T in horizons], seed=int(cfg.seed), lattice=ev.kind,
                           threads=threads, init_scale=float(cfg.genome.init_scale), min_founder_score=min_F,
                           knob_init=None if cfg.genome.get("knob_init") is None else str(cfg.genome.knob_init)),
               zygote=zygote_census(layout, params, ev.kind), t_draw=t_draw, t_pack=t_pack, horizons={})
    cols = {}
    for T in horizons:
        w = ev.world(float(T))
        seeds = [life_seed(int(cfg.seed), "census", int(T), i) for i in range(samples)]
        led, t_run = [], 0.0
        for i in range(0, samples, chunk):
            t1 = time.perf_counter()
            res = build.run(w, seeds[i: i + chunk], genomes=table[i: i + chunk], kind=ev.kind, threads=threads)
            t_run += time.perf_counter() - t1
            led.append(res.ledger)
        led = np.concatenate(led)
        col = {k: led[:, spec.L[k]] for k in COLUMNS}
        cols[int(T)] = col
        h = horizon(col, min_F)
        h.update(t_run=t_run, lives_per_s=samples / t_run, events_per_s=float(col["events"].sum()) / t_run,
                 mean_events=float(col["events"].mean()))
        out["horizons"][str(int(T))] = h
        log(f"T={int(T)}: {samples} lives in {t_run:.1f} s; lone {h['lone']:.3f}, guard {h['guard']:.3f}, "
            f"clear {h['clear_min_F']:.3f}, best F {h['best']['F']:+.4f}")
    if len(horizons) > 1:
        a, b = (cols[int(T)] for T in (horizons[0], horizons[-1]))
        ca, cb = a["F"] >= min_F, b["F"] >= min_F
        out["paired"] = dict(short=int(horizons[0]), long=int(horizons[-1]),
                             clear_short_and_long=_frac(ca & cb), clear_short_only=_frac(ca & ~cb),
                             clear_long_only=_frac(~ca & cb),
                             F_corr=float(np.corrcoef(np.clip(a["F"], -30, None), np.clip(b["F"], -30, None))[0, 1]))
    if top > 0:
        T = int(horizons[-1])
        F = cols[T]["F"]
        idx = np.argsort(-F, kind="stable")[:top]
        seeds = [life_seed(int(cfg.seed), "census", 10_000 + T, s) for s in range(top_lives)]
        w = ev.world(float(T))
        res = build.run([w] * (len(idx) * top_lives), seeds * len(idx), genomes=table[idx],
                        genome_of=np.repeat(np.arange(len(idx)), top_lives), kind=ev.kind, threads=threads)
        Fr = res["F"].reshape(len(idx), top_lives)
        ne = res["n_end"].reshape(len(idx), top_lives)
        rows = []
        for r, i in enumerate(idx):
            s = analysis.summary(Fr[r])
            rows.append(dict(index=int(i), census_F=float(F[i]), F=s["mean"], F_se=s["se"], F_median=s["median"],
                             n_end=float(ne[r].mean()), census_n_end=float(cols[T]["n_end"][i])))
        best = max(rows, key=lambda x: x["F"])
        out["top"] = dict(T=T, lives=top_lives, rows=rows, best=best,
                          winners_curse=float(np.mean([x["census_F"] for x in rows]) / max(np.mean([x["F"] for x in rows]),
                                                                                           1e-12)))
        log(f"top {top} at T={T} re-measured on {top_lives} fresh lives: best {best['F']:+.4f} +- {best['F_se']:.4f} "
            f"(n_end {best['n_end']:.1f}; census F {best['census_F']:+.4f})")
    return out


def _pct(x: float) -> str:
    return f"{100 * x:.1f}%"


def _q3(q: list) -> str:
    return " / ".join(f"{q[i]:g}" for i in (0, 2, 4)) if q else "-"


def markdown(c: dict) -> str:
    """A compact table of the census (one column per horizon)."""
    Ts = list(c["horizons"])
    H = [c["horizons"][T] for T in Ts]
    rows = [
        ("lone (never divided)", lambda h: _pct(h["lone"])),
        ("lone pumps (lone, income > 0)", lambda h: _pct(h["lone_pump"])),
        ("bodies (>= 2 cells, no guard trip)", lambda h: _pct(h["body"])),
        ("bodies with spike arrivals", lambda h: _pct(h["body_messaging"])),
        ("guard trips: N_max / events", lambda h: f"{_pct(h['guard_cells'])} / {_pct(h['guard_events'])}"),
        ("extinct", lambda h: _pct(h["extinct"])),
        (f"F >= {c['config']['min_founder_score']} (all / bodies)",
         lambda h: f"{_pct(h['clear_min_F'])} / {_pct(h['clear_min_F_body'])}"),
        (f"F > {LONE_BEST_F} (best lone cell)", lambda h: _pct(h["beat_lone_best"])),
        ("n_end q10 / q50 / q90", lambda h: _q3(h["n_end_q"])),
        ("n_peak q10 / q50 / q90", lambda h: _q3(h["n_peak_q"])),
        ("body n_end q10 / q50 / q90", lambda h: _q3(h["n_end_body_q"])),
        ("best F (its n_end)", lambda h: f"{h['best']['F']:+.4f} ({h['best']['n_end']:g})"),
        ("best multi-cell F (its n_end)",
         lambda h: f"{h['best_body']['F']:+.4f} ({h['best_body']['n_end']:g})" if "best_body" in h else "-"),
        ("kernel time (lives/s)", lambda h: f"{h['t_run']:.1f} s ({h['lives_per_s']:.0f})"),
        ("share of events in guard-tripped lives", lambda h: _pct(h["events_share_guard"])),
    ]
    lines = ["| T | " + " | ".join(Ts) + " |", "|---|" + "---|" * len(Ts)]
    lines += [f"| {name} | " + " | ".join(f(h) for h in H) + " |" for name, f in rows]
    lines += ["", "Zygote phenotypes: " + ", ".join(f"{k} {_pct(v)}" for k, v in c["zygote"].items())]
    if "top" in c:
        t, b = c["top"], c["top"]["best"]
        lines.append(f"Top {len(t['rows'])} of T={t['T']} on {t['lives']} fresh lives: best F {b['F']:+.4f} +- "
                     f"{b['F_se']:.4f} (n_end {b['n_end']:.1f}); mean census F / mean fresh F = {t['winners_curse']:.2f}")
    return "\n".join(lines)


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--config", default="configs/life_bell.yaml")
    p.add_argument("--samples", type=int, default=4096)
    p.add_argument("--T", default="512,1024", help="horizons, comma-separated")
    p.add_argument("--top", type=int, default=16)
    p.add_argument("--top-lives", type=int, default=64)
    p.add_argument("--threads", type=int, default=None)
    p.add_argument("--out", default="outputs/life_census")
    p.add_argument("overrides", nargs="*")
    args = p.parse_args()
    cfg = load_config(str(repo_root / args.config) if not Path(args.config).is_absolute() else args.config,
                      args.overrides)
    t0 = time.time()
    res = census(cfg, args.samples, [int(x) for x in args.T.split(",")], args.top, args.top_lives, args.threads)
    res["wall_s"] = round(time.time() - t0, 1)
    out = repo_root / args.out if not Path(args.out).is_absolute() else Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "census.json").write_text(json.dumps(res, indent=1))
    print(markdown(res))
