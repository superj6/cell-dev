"""Replay test: the act-plane raster of a tissue body, replayed by the REPLAY controller on the same footprint, must
reproduce the tissue life's world bitwise (world hash, captures, clicks, path, dot end position, receptor columns)."""
import numpy as np
import harness as H
from src.life import spec

V3 = spec.V3
KAPPA = V3.K["kappa"]


def schedule(body, res, i, fp):
    """(t_rel, act index, kappa) of every act-plane spike with kappa > 0 in life i of a tissue body."""
    fi, ff = res.fates(i)
    uid_site = {int(r[1]) & 0xFFFFFFFFFFFFFFFF: (int(r[3]), int(r[4]), int(r[6])) for r in fi if r[0] == 1}
    row_of = {(a, b, z): row for a, b, z, row in body.cells}
    act_idx = {ab: j for j, ab in enumerate(fp.act)}
    t, u = res.spikes(i)
    out = []
    for tt, uu in zip(t, u):
        a, b, z = uid_site[int(uu)]
        if z != 1:
            continue
        kap = float(body.program[row_of[(a, b, z)] * V3.P + KAPPA])
        if kap > 0:
            out.append((float(tt), act_idx[(a, b)], kap))
    return out


def run(world, n=8, block=0, body=None, fp=None, threads=4):
    body = body or H.reflex("hollow3")
    fp = fp or H.footprint("hollow3")
    sd = H.seeds(n, block)
    tis = H.tissue_run(body, world, sd, threads=threads, fast=False, raster_cap=200000, fate_cap=4000)
    rows = []
    for i in range(n):
        sch = schedule(body, tis, i, fp)
        rows.append([len(sch)] + [x for e in sch for x in e])
    m = max(len(r) for r in rows)
    P = np.zeros((n, m))
    for i, r in enumerate(rows):
        P[i, :len(r)] = r
    rep = H.ctl_run(H.REPLAY, P, fp, world, sd, threads=threads, fast=False, latency=0.0, t_ref_min=0.0,
                    charge="receptor")
    cols = ("captures", "misses", "clicks", "b2_clicks", "nudges", "path", "X_end", "Y_end", "rec_cand", "rec_accept",
            "rec_events", "rec_gain", "dist_sum", "zone_samples", "respawns", "beats", "P_int", "kills", "income")
    eq = {c: bool(np.array_equal(tis[c], rep[c])) for c in cols}
    eq["world_hash"] = bool(np.array_equal(tis.hashes[:, 4], rep.hashes[:, 4]))
    return eq, tis, rep


if __name__ == "__main__":
    import sys
    for w in sys.argv[1:] or ["base1", "base", "pool", "blink20", "flash6", "flip_mid", "lead", "decoy_lite", "wound25"]:
        eq, tis, rep = run(w)
        bad = [k for k, v in eq.items() if not v]
        print(f"{w:12s} all equal: {not bad}  {'MISMATCH ' + str(bad) if bad else ''}  caps {tis['captures'].mean():.1f}"
              f"/{rep['captures'].mean():.1f} F tissue {tis['F'].mean():+.2f} replay {rep['F'].mean():+.2f}", flush=True)
