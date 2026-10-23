"""Readable anatomy of one traced life: body map, per-cell senses, message graph, gene-driven knob changes."""
import sys
import pickle

import numpy as np
import pandas as pd

from common import V8

SN = {1: "odA", 2: "odB", 3: "odC", 4: "odD", 5: "flow", 6: "touch", 7: "vib", 8: "sun", 9: "spare"}
DIRS = ["E", "NE", "NW", "W", "SW", "SE", "up", "down"]


def report(tr, out=sys.stdout):
    c, kb, ke = tr.cells, tr.knobs_birth, tr.knobs_end
    alive = ~np.isfinite(c.t_death)
    p = lambda *a: print(*a, file=out)  # noqa: E731
    p(f"== {tr.meta['org']}  F={tr.ledger['F']:.2f}  cells alive at end {int(alive.sum())} "
      f"(sense plane {int((alive & (c.z == 0)).sum())}, act plane {int((alive & (c.z == 1)).sum())}, "
      f"hidden {int((alive & (c.z >= 2)).sum())})  spikes {len(tr.spikes)}  strokes {len(tr.strokes)}  "
      f"clicks {len(tr.clicks)}")
    # per-cell table
    rm = tr.recm
    sens = rm.groupby(["cid", "m"]).n.sum().unstack(fill_value=0) if len(rm) else pd.DataFrame()
    rows = []
    for i in np.where(alive)[0]:
        r = dict(cid=i, cls=c.cls[i], ab=f"({c.a[i]},{c.b[i]})", z=int(c.z[i]), spikes=int(c.n_spikes[i]),
                 light=int(c.n_rec[i]), w0=ke.w0[i], w1=ke.w1[i], b=ke.b[i], e0=ke.emit0[i], e1=ke.emit1[i],
                 kap=ke.kappa[i], g_light=ke.g_r[i])
        for m, nm in SN.items():
            g = ke[f"g_r{m}"][i]
            n = int(sens.loc[i, m]) if (len(sens) and i in sens.index and m in sens.columns) else 0
            if g != 0 or n:
                r[nm] = f"{g:+.2f}/{n}"
        rows.append(r)
    df = pd.DataFrame(rows).fillna("")
    p("-- cells (knobs at end; modality columns: gain/deliveries)")
    p(df.to_string(index=False, float_format=lambda x: f"{x:.2f}"))
    # message graph
    ar = tr.arrivals
    if len(ar):
        ar = ar[ar.s_cid >= 0]
        g = ar.groupby(["s_cid", "cid", "dir"]).agg(n=("contrib", "size"), w=("contrib", "mean")).reset_index()
        g["dir"] = g["dir"].map(lambda d: d if isinstance(d, str) else DIRS[int(d)])
        g["pre"] = [c.cls[i] for i in g.s_cid]
        g["post"] = [c.cls[i] for i in g.cid]
        p("-- strongest message links (sender -> receiver: count, mean effect on the receiver's membrane)")
        top = g.assign(total=g.n * g.w.abs()).sort_values("total", ascending=False).head(25)
        p(top[["s_cid", "pre", "cid", "post", "dir", "n", "w"]].to_string(index=False, float_format=lambda x: f"{x:+.3f}"))
        cls = g.groupby(["pre", "post"]).agg(n=("n", "sum"), net=("w", lambda s: float((s * g.loc[s.index, "n"]).sum())))
        p("-- message flow between classes (total count, summed effect)")
        p(cls.to_string(float_format=lambda x: f"{x:+.1f}"))
    # knob changes driven by the genes during life
    ph = tr.pheno_changes
    if len(ph):
        names = list(V8.KNOBS)
        ph = ph.assign(name=[k if isinstance(k, str) else names[int(k)] for k in ph.knob])
        s = ph.groupby("name").agg(changes=("t", "size"), cells=("cid", "nunique"),
                                   lo=("new", "min"), hi=("new", "max")).sort_values("changes", ascending=False)
        p("-- knobs the genes retune during life (after growth)")
        p(s.head(15).to_string(float_format=lambda x: f"{x:+.3f}"))
    return df


if __name__ == "__main__":
    report(pickle.load(open(sys.argv[1], "rb")))
