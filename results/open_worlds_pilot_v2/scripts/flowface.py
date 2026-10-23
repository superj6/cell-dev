"""Does the body move toward the side where it feels the current (upstream)? Windows of 32 time units."""
import pickle
import sys

import numpy as np
import pandas as pd

import common  # noqa: F401  (puts the repository on the path for unpickling)


def flowface(tr, W=32.0):
    c = tr.cells
    xy = np.stack([c.x.to_numpy(), c.y.to_numpy()], 1)
    nrm = xy / np.maximum(np.linalg.norm(xy, axis=1, keepdims=True), 1e-9)
    fl = tr.recm[tr.recm.m == 5]
    traj = tr.traj.set_index("t")
    cos = lambda a, b: float(a @ b / (np.linalg.norm(a) * np.linalg.norm(b))) if np.linalg.norm(a) * np.linalg.norm(b) > 0 else np.nan  # noqa: E731
    rows = []
    for t0 in np.arange(0, 1024 - W, W):
        f = fl[(fl.t >= t0) & (fl.t < t0 + W)]
        if len(f) < 10:
            continue
        v = (nrm[f.cid.to_numpy()] * f.n.to_numpy()[:, None]).sum(0)
        sk = tr.strokes[(tr.strokes.t >= t0) & (tr.strokes.t < t0 + W) & tr.strokes.pulled]
        pull = np.stack([sk.nx.to_numpy(), sk.ny.to_numpy()], 1).sum(0) if len(sk) else np.zeros(2)
        i0, i1 = int(t0), int(t0 + W)
        d = (traj.loc[i1, ["X", "Y"]].to_numpy(float) - traj.loc[i0, ["X", "Y"]].to_numpy(float)) if i1 in traj.index else np.zeros(2)
        rows.append(dict(t=t0, flow_events=len(f), cos_pull=cos(pull, v), cos_move=cos(d, v), dist=float(np.linalg.norm(d))))
    return pd.DataFrame(rows)


if __name__ == "__main__":
    tr = pickle.load(open(sys.argv[1], "rb"))
    df = flowface(tr)
    print(df[["cos_pull", "cos_move", "dist"]].describe().loc[["mean", "50%", "count"]].to_string(float_format=lambda x: f"{x:.2f}"))
    print("share of windows pulled toward the flow-facing side:", round(float((df.cos_pull > 0).mean()), 2),
          "| moved toward it:", round(float((df.cos_move > 0).mean()), 2))
    sk = tr.strokes[tr.strokes.pulled]
    print("strokes per act cell:", sk.groupby("cid").size().sort_values(ascending=False).to_dict())
    fl = tr.recm[tr.recm.m == 5]
    print("flow deliveries per sense cell:", fl.groupby("cid").n.sum().sort_values(ascending=False).to_dict())
