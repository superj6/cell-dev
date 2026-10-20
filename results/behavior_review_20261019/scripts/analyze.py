"""Behaviour metrics from the saved reference traces (g0 vs g250 per lineage)."""
import glob, json, pickle, sys
from collections import defaultdict
import numpy as np, pandas as pd

D = "traces"; T = 1024.0; RHO = 1.0


def unit(v):
    n = np.linalg.norm(v, axis=-1, keepdims=True)
    return v / np.where(n > 0, n, 1)


def lives(task):
    out = defaultdict(list)
    for p in sorted(glob.glob(f"{D}/*_{task}_*.pkl")):
        r = pickle.load(open(p, "rb"))
        m = r["meta"]
        if m["task"] == task:
            out[(m["lin"], m["stage"])].append(r)
    return out


def mse(x):
    x = np.asarray([v for v in x if np.isfinite(v)], float)
    return (float(x.mean()), float(x.std(ddof=1) / np.sqrt(len(x))) if len(x) > 1 else np.nan) if len(x) else (np.nan, np.nan)


def anatomy(r):
    c = r["cells"]; alive = c[np.isinf(c.t_death)]
    ke = r["knobs_end"].loc[alive.cid]
    types = len(np.unique(np.round(ke.to_numpy(), 2), axis=0))
    ring = np.maximum.reduce([alive.a.abs(), alive.b.abs(), (alive.a + alive.b).abs()]) if len(alive) else [0]
    sp = r["spikes"]
    return dict(n=len(alive), S=int((alive.z == 0).sum()), M=int((alive.z == 1).sum()), H=int((alive.z >= 2).sum()),
                types=types, ring=float(np.max(ring)), spikes_S=int((sp.z == 0).sum()), spikes_M=int((sp.z == 1).sum()),
                spikes_H=int((sp.z >= 2).sum()))


def pursuit(r):
    tj = r["traj"]; P = tj[["X", "Y"]].to_numpy(); Q = tj[["tx", "ty"]].to_numpy()
    d = np.linalg.norm(Q - P, axis=1)
    v = np.diff(P, axis=0); sp = np.linalg.norm(v, axis=1)
    b = unit(Q[:-1] - P[:-1]); cosv = (unit(v) * b).sum(1)
    ck = r["clicks"]; dc = np.linalg.norm(ck[["tx", "ty"]].to_numpy() - ck[["X", "Y"]].to_numpy(), axis=1) if len(ck) else np.array([])
    near, far = d < RHO, d > 1.5
    st = r["strokes"]; s = st[st.pulled]
    us = unit(s[["nx", "ny"]].to_numpy()); bs = unit(s[["tx", "ty"]].to_numpy() - s[["X", "Y"]].to_numpy())
    led = r["ledger"]
    return dict(captures=led.get("captures", np.nan), clicks=len(ck), harmful=int((ck.outcome == "blob1").sum()) if len(ck) else 0,
                time_near=float(near.mean()), mean_d=float(np.nanmean(d)), speed=float(sp.mean()),
                approach=float(np.nanmean(cosv[sp > 0.02])) if (sp > 0.02).any() else np.nan,
                click_rate_near=float((dc < RHO).sum() / max(near.sum(), 1)), click_rate_far=float((dc > 1.5).sum() / max(far.sum(), 1)),
                precision=float(led.get("captures", 0) / max(len(ck), 1)), stroke_align=float((us * bs).sum(1).mean()) if len(s) else np.nan,
                strokes_per_t=len(s) / T)


BINS = [(-5, 0), (0, 2.5), (2.5, 5), (5, 10), (10, 20), (20, 40), (40, 80), (80, 1e9)]


def flash(r, on=5.0):
    """Per lag-since-flash-end bin: stroke rate, stroke alignment to the current target and to the remembered
    (flash-end) position, velocity alignment, distance; plus capture lags."""
    tj = r["traj"]; P = tj[["X", "Y"]].to_numpy(); Q = tj[["tx", "ty"]].to_numpy(); tt = tj.t.to_numpy()
    pl = r["placements"]; pl = pl[pl.blob == 0].sort_values("t"); tp = pl.t.to_numpy()
    st = r["strokes"]; s = st[st.pulled]; ck = r["clicks"]
    res = {k: dict(n_str=0, t=0.0, a_cur=[], a_rem=[], v_cur=[], v_rem=[], dist=[]) for k in range(len(BINS))}
    caps = []
    for i, t0 in enumerate(tp):
        t1 = tp[i + 1] if i + 1 < len(tp) else T
        if t0 < 40 or t1 - t0 < 1:
            continue
        te = t0 + on; k_e = min(int(np.floor(te)), len(tt) - 1)
        rem = Q[k_e]  # target position at flash end (what the organism last saw)
        for k, (lo, hi) in enumerate(BINS):
            a, b_ = max(te + lo, t0), min(te + hi, t1)
            if b_ <= a:
                continue
            res[k]["t"] += b_ - a
            ss = s[(s.t >= a) & (s.t < b_)]
            res[k]["n_str"] += len(ss)
            if len(ss):
                u = unit(ss[["nx", "ny"]].to_numpy()); dot = ss[["X", "Y"]].to_numpy()
                res[k]["a_cur"] += list((u * unit(ss[["tx", "ty"]].to_numpy() - dot)).sum(1))
                res[k]["a_rem"] += list((u * unit(rem[None] - dot)).sum(1))
            ii = np.arange(int(np.ceil(a)), min(int(np.floor(b_)), len(tt) - 1))
            if len(ii):
                v = P[ii + 1] - P[ii]; m = np.linalg.norm(v, axis=1) > 0.02
                if m.any():
                    res[k]["v_cur"] += list((unit(v[m]) * unit(Q[ii][m] - P[ii][m])).sum(1))
                    res[k]["v_rem"] += list((unit(v[m]) * unit(rem[None] - P[ii][m])).sum(1))
                res[k]["dist"] += list(np.linalg.norm(Q[ii] - P[ii], axis=1))
        c = ck[(ck.t > t0 + 1e-9) & (ck.t <= t1) & (ck.outcome == "capture")]
        caps.append(float(c.t.min() - te) if len(c) else np.nan)
    return res, caps


def patches(r):
    pe = r["patch_events"]; tj = r["traj"]; P = tj[["X", "Y"]].to_numpy(); tt = tj.t.to_numpy()
    start = pe[pe.kind == 18].sort_values("slot"); n = len(start)
    C = start[["x", "y"]].to_numpy()
    d = np.linalg.norm(P[:, None, :] - C[None], axis=2); near = d.min(1) < RHO; slot = np.where(near, d.argmin(1), -1)
    # stock step function per slot
    ev = []
    for _, e in pe.iterrows():
        k = int(e.kind)
        if k == 18: ev.append((e.t, int(e.slot), int(e.stock)))
        elif k in (19, 23) and not np.isnan(e.stock_after): ev.append((e.t, int(e.slot), int(e.stock_after)))
        elif k == 20 and int(e.slot) < n: ev.append((e.t, int(e.slot), int(e.stock_after)))
    ev.sort()
    stock = np.zeros((len(tt), n))
    cur = np.zeros(n); j = 0
    for i, t in enumerate(tt):
        while j < len(ev) and ev[j][0] <= t:
            cur[ev[j][1]] = ev[j][2]; j += 1
        stock[i] = cur
    visits, arr_stock, dep_stock = [], [], []
    i = 0
    while i < len(tt):
        if slot[i] >= 0:
            s0, i0 = slot[i], i
            while i < len(tt) and slot[i] == s0: i += 1
            visits.append(i - i0); arr_stock.append(stock[i0, s0]); dep_stock.append(stock[min(i, len(tt) - 1), s0])
        else:
            i += 1
    ck = r["clicks"]
    inpatch = ck[ck.patch < n] if len(ck) else ck
    empty_taps = int((inpatch.stock_before == 0).sum()) if len(ck) else 0
    t_near_empty = float(sum(stock[k, slot[k]] == 0 for k in range(len(tt)) if slot[k] >= 0))
    orig = ck[ck.resource_outcome == 1].origin.value_counts().to_dict() if len(ck) else {}
    out = dict(time_near=float(near.mean()), visits=len(visits), visit_len=float(np.mean(visits)) if visits else np.nan,
               dep_empty=float(np.mean(np.array(dep_stock) == 0)) if dep_stock else np.nan,
               arr_empty=float(np.mean(np.array(arr_stock) == 0)) if arr_stock else np.nan,
               empty_tap_rate=empty_taps / max(t_near_empty, 1.0), empty_taps=empty_taps, t_near_empty=t_near_empty,
               h_initial=orig.get(1, 0), h_refill=orig.get(2, 0), h_contact=orig.get(3, 0),
               misses_out=int((ck.patch >= n).sum()) if len(ck) else 0)
    jobs = pe[pe.kind == 22]
    stay, at_due = [], []
    for _, jb in jobs.iterrows():
        s0 = int(jb.slot); ii = (tt >= jb.t) & (tt <= jb.due)
        if ii.any():
            stay.append(float((slot[ii] == s0).mean()))
        k = min(int(jb.due), len(tt) - 1); at_due.append(float(d[k, s0] < RHO))
    out.update(jobs=len(jobs), job_stay=float(np.mean(stay)) if stay else np.nan, job_at_due=float(np.mean(at_due)) if at_due else np.nan)
    return out


def matching(r):
    te = r["task_events"]; sp = r["spikes"]; st = r["strokes"]; tj = r["traj"]
    ph = te[te.kind == 15].sort_values("t"); rs = te[te.kind == 16]
    trials = []
    for tr_id, g in ph.groupby("trial"):
        row = {"trial": tr_id, "cls": int(g.sample_class.iloc[0])}
        for phase, name in ((0, "sample"), (1, "blank"), (2, "choice")):
            x = g[g.phase == phase]
            row[name] = float(x.t.iloc[0]) if len(x) else np.nan
        res_ = rs[rs.trial == tr_id]
        row["outcome"] = int(res_.outcome.iloc[0]) if len(res_) else -1
        row["slot"] = int(res_.slot.iloc[0]) if len(res_) else -1
        if np.isfinite(row["blank"]) and np.isfinite(row["choice"]) and row["blank"] > 40:
            b0, b1 = row["blank"], row["choice"]
            for lo, hi, nm in ((0, 2.5, "b_early"), (2.5, 1e9, "b_late"), (-2.5, 0, "s_late")):
                a, c = b0 + lo, min(b0 + hi, b1) if hi < 1e8 else b1
                if nm == "s_late":
                    a, c = b0 - 2.5, b0
                dur = max(c - a, 1e-9)
                for z, pn in ((0, "S"), (1, "M"), (2, "H")):
                    sel = (sp.t >= a) & (sp.t < c) & ((sp.z == z) if z < 2 else (sp.z >= 2))
                    row[f"{nm}_{pn}"] = float(sel.sum() / dur)
                ss = st[(st.t >= a) & (st.t < c) & st.pulled]
                row[f"{nm}_str"] = float(len(ss) / dur)
            trials.append(row)
    return trials


if __name__ == "__main__":
    which = sys.argv[1:] or ["anatomy", "pursuit", "flash", "patches", "matching"]
    report = {}
    if "anatomy" in which or "pursuit" in which:
        for task in ["pool", "persistent", "harmful_decoy", "flash10", "flash00", "patches", "contact_food"]:
            for (lin, st), rs in sorted(lives(task).items()):
                if "anatomy" in which:
                    A = pd.DataFrame([anatomy(r) for r in rs]).mean().round(2).to_dict()
                    report.setdefault("anatomy", {})[f"{lin}|{st}|{task}"] = A
                if "pursuit" in which:
                    Pm = pd.DataFrame([pursuit(r) for r in rs])
                    report.setdefault("pursuit", {})[f"{lin}|{st}|{task}"] = {k: mse(Pm[k]) for k in Pm}
    if "flash" in which:
        for task in ["flash00", "flash10"]:
            for (lin, st), rs in sorted(lives(task).items()):
                agg = {k: dict(n_str=0, t=0.0, a_cur=[], a_rem=[], v_cur=[], v_rem=[], dist=[]) for k in range(len(BINS))}
                caps = []
                for r in rs:
                    res, c = flash(r); caps += c
                    for k in res:
                        for f in ("n_str", "t"): agg[k][f] += res[k][f]
                        for f in ("a_cur", "a_rem", "v_cur", "v_rem", "dist"): agg[k][f] += res[k][f]
                report.setdefault("flash", {})[f"{lin}|{st}|{task}"] = dict(
                    bins=[dict(bin=BINS[k], rate=agg[k]["n_str"] / max(agg[k]["t"], 1e-9),
                               **{f: mse(agg[k][f]) for f in ("a_cur", "a_rem", "v_cur", "v_rem", "dist")}) for k in agg],
                    segments=len(caps), caught=float(np.mean(np.isfinite(caps))) if caps else np.nan,
                    cap_lag_median=float(np.nanmedian(caps)) if np.isfinite(caps).any() else np.nan)
    if "patches" in which:
        for task in ["patches", "contact_food"]:
            for (lin, st), rs in sorted(lives(task).items()):
                Pm = pd.DataFrame([patches(r) for r in rs])
                report.setdefault("patches", {})[f"{lin}|{st}|{task}"] = {k: mse(Pm[k]) for k in Pm}
    if "matching" in which:
        for (lin, st), rs in sorted(lives("matching").items()):
            rows = []
            for i, r in enumerate(rs):
                for t in matching(r):
                    t["life"] = i; rows.append(t)
            report.setdefault("matching", {})[f"{lin}|{st}"] = rows
    name = "report_" + "_".join(which) + ".json"
    json.dump(report, open(name, "w"), default=float)
    print("wrote", name)
