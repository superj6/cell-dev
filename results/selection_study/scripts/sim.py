"""Selection-noise study: replay one generation's choice of mu = 32 parents from a measured genomes x lives F matrix.

Each replicate permutes the population's lives (shared across genomes, as in a real generation). The first POOL = 11
lives are the selection lives every scheme draws from in order (lives 0-2 are the generation's 3 shared lives, 3+ the
recheck or extra lives), so all schemes of one replicate are paired; the other N - 11 lives give each genome's true F
(held out from every scheme, so the chosen genomes' truth carries no selection bias).

Schemes: A (3 lives for all); B{key}(K, L2) (3 lives for all, then the top K by the 3-life mean rescored on L2 more
shared lives; parents = top 32 of the shortlist by key 1 = mean over all 3 + L2 lives, key 2 = recheck lives only);
C(n) (n lives for all). Cost = extra lives per generation / 768; cost_ev = the same in kernel events.

Data SE: the point estimate uses all N lives; its SE comes from disjoint half-splits of the lives (each half simulated
on its own): Var(half) ~ E[(m_a - m_b)^2] / 2 and SE(full) ~ SE(half) / sqrt(2) (conservative: a half's truth uses
fewer lives). Paired differences against A get their SE the same way.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

MU, LAM, BASE = 32, 224, 3
POOL = 11
LONE = 0.0328  # G1: the best lone cell on fresh lives
KS, L2S, NS = (40, 48, 64, 96, 128), (2, 3, 4, 5, 6, 8), (4, 5, 6, 8)  # task grid plus K 40 and L2 5
METRICS = ("meanF", "regret", "p_best", "beat", "beat_body", "rank0F", "rank0_beat", "cost_ev")


def schemes(ks=KS, l2s=L2S, ns=NS) -> list[dict]:
    out = [dict(name="A", kind="A", cost=0.0)]
    for K in ks:
        for L2 in l2s:
            for key in (1, 2):
                out.append(dict(name=f"B{key} K{K} L{L2}", kind="B", K=K, L2=L2, key=key, cost=K * L2 / 768))
    for n in ns:
        out.append(dict(name=f"C n{n}", kind="C", n=n, cost=(MU + LAM) * (n - BASE) / 768))
    return out


def take(a: np.ndarray, idx: np.ndarray) -> np.ndarray:
    """a [R, B, ...] gathered along axis 1 by idx [R, k]."""
    return np.take_along_axis(a, idx.reshape(idx.shape + (1,) * (a.ndim - 2)), axis=1)


def simulate(F, events, body, lives, R, rng, plan, keep: bool = False) -> dict[str, dict[str, np.ndarray]]:
    """Per scheme and metric, the R replicate values, on the life subset ``lives`` (``keep``: also the chosen
    genome indices [R, 32] under "chosen")."""
    Fl, El = F[:, lives], events[:, lives]
    B, N = Fl.shape
    perm = np.argsort(rng.random((R, N)), axis=1)
    S = perm[:, :POOL]
    Fs = np.transpose(Fl[:, S], (1, 0, 2))  # [R, B, POOL]
    Es = np.transpose(El[:, S], (1, 0, 2))
    t = (Fl.sum(1)[None, :] - Fs.sum(2)) / (N - POOL)  # [R, B] truth on the held-out lives
    top_true = -np.sort(-t, axis=1)[:, :MU].mean(1)
    best = t.argmax(1)
    base_ev = Es[:, :, :BASE].sum((1, 2))
    s3 = Fs[:, :, :BASE].mean(2)
    order3 = np.argsort(-s3, axis=1, kind="stable")
    out = {}
    for sc in plan:
        if sc["kind"] == "A":
            chosen, extra = order3[:, :MU], np.zeros(R)
        elif sc["kind"] == "C":
            n = sc["n"]
            chosen = np.argsort(-Fs[:, :, :n].mean(2), axis=1, kind="stable")[:, :MU]
            extra = Es[:, :, BASE:n].sum((1, 2))
        else:
            K, L2 = sc["K"], sc["L2"]
            sl = order3[:, :K]
            rec = take(Fs[:, :, BASE:BASE + L2], sl).mean(2)  # [R, K]
            key = rec if sc["key"] == 2 else (BASE * take(s3, sl) + L2 * rec) / (BASE + L2)
            chosen = np.take_along_axis(sl, np.argsort(-key, axis=1, kind="stable")[:, :MU], axis=1)
            extra = take(Es[:, :, BASE:BASE + L2], sl).sum((1, 2))
        tc = take(t, chosen)
        out[sc["name"]] = dict(
            meanF=tc.mean(1), regret=top_true - tc.mean(1), p_best=(chosen == best[:, None]).any(1).astype(float),
            beat=(tc > LONE).mean(1), beat_body=((tc > LONE) & body[chosen]).mean(1), rank0F=tc[:, 0],
            rank0_beat=(tc[:, 0] > LONE).astype(float), cost_ev=extra / base_ev)
        if keep:
            out[sc["name"]]["chosen"] = chosen
    return out


def study(path: Path, R: int = 4000, halves: int = 12, R_half: int = 1000, seed: int = 0, plan=None) -> dict:
    """Point estimates (all lives) with half-split SEs, for every scheme and metric and for each paired difference
    against A; plus a description of the population."""
    z = np.load(path)
    F, events, n_end = z["F"], z["events"].astype(float), z["n_end"]
    body = np.median(n_end, axis=1) >= 2
    plan = plan or schemes()
    rng = np.random.default_rng(seed)
    N = F.shape[1]
    full = simulate(F, events, body, np.arange(N), R, rng, plan)
    point = {s: {m: float(v.mean()) for m, v in d.items()} for s, d in full.items()}
    dpoint = {s: {m: float((full[s][m] - full["A"][m]).mean()) for m in METRICS} for s in full}
    sq = {s: {m: 0.0 for m in METRICS} for s in full}
    dsq = {s: {m: 0.0 for m in METRICS} for s in full}
    for _ in range(halves):
        p = rng.permutation(N)
        a = simulate(F, events, body, p[: N // 2], R_half, rng, plan)
        b = simulate(F, events, body, p[N // 2:], R_half, rng, plan)
        for s in full:
            for m in METRICS:
                sq[s][m] += (a[s][m].mean() - b[s][m].mean()) ** 2
                da, db = (a[s][m] - a["A"][m]).mean(), (b[s][m] - b["A"][m]).mean()
                dsq[s][m] += (da - db) ** 2
    # Var(half) = E[(a - b)^2] / 2; SE(full) = sqrt(Var(half) / 2)
    se = {s: {m: float(np.sqrt(sq[s][m] / halves / 4)) for m in METRICS} for s in full}
    dse = {s: {m: float(np.sqrt(dsq[s][m] / halves / 4)) for m in METRICS} for s in full}
    tF = F.mean(1)
    desc = dict(pop=path.stem, meta=json.loads(str(z["meta"])), lives=int(N), lone_F=float(z["lone_F"].mean()),
                true_best=float(tF.max()), true_top32=float(np.sort(tF)[::-1][:MU].mean()),
                n_beat=int((tF > LONE).sum()), n_body=int(body.sum()), parents_body=float(body[:MU].mean()),
                n_body_beat=int(((tF > LONE) & body).sum()),
                median_n_end=float(np.median(n_end)), guard=float(z["guard"].mean()),
                sd_life_top32=float(np.median(F[np.argsort(-tF)[:MU]].std(1))))
    return dict(desc=desc, point=point, se=se, dpoint=dpoint, dse=dse,
                cost={s["name"]: s["cost"] for s in plan})


def main() -> None:
    out = Path(sys.argv[1])
    paths = [Path(p) for p in sys.argv[2:]]
    res = {}
    for p in paths:
        res[p.stem] = study(p)
        d = res[p.stem]["desc"]
        print(json.dumps({k: d[k] for k in ("pop", "true_best", "true_top32", "n_beat", "n_body_beat")}), flush=True)
    out.write_text(json.dumps(res))


if __name__ == "__main__":
    main()
