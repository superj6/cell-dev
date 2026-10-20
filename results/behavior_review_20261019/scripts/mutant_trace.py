"""Re-create AO's best dark-flash mutant (screen row 104), record what changed, and trace it on the parent's seeds."""
import multiprocessing as mp, pickle
from common import *
from traces import LIVES, TASK_OFF
gen = torch.Generator().manual_seed(45919)
p = layout.from_dict(SEL["AO_s7"]["250"]["genome"]).reshape(1, -1)
ops = []
kids = layout.mutate(p.repeat(192, 1), gen, 2, 0.5, ops=ops)
rows = {104: kids[103], 152: kids[151]}
for r, k in rows.items():
    print("row", r, "mutations:", ops[r - 1])
G = {r: k.detach().numpy().astype(np.float32) for r, k in rows.items()}
D = OUT / "traces_mut"; D.mkdir(exist_ok=True)
def job(a):
    r, i = a
    w = world("flash00"); sd = seeds(LIVES["flash00"], TASK_OFF["flash00"])[i]
    tr = probe.trace(Org(f"AO_mut{r}", G[r]), sd, "x", abi=ABI, _w=w)
    keep = dict(traj=tr.traj, strokes=tr.strokes, clicks=tr.clicks, placements=tr.placements, task_events=None,
                patch_events=None, motion=tr.motion, cells=tr.cells[["cid", "a", "b", "z", "plane", "cls", "t_birth", "t_death", "n_spikes"]],
                spikes=tr.spikes[["t", "cid", "a", "b", "z", "mask"]], knobs_end=tr.knobs_end,
                ledger={k: tr.ledger[k] for k in tr.ledger if isinstance(tr.ledger[k], (int, float))},
                meta=dict(seed=sd, lin="AO_s7", stage=f"mut{r}", task="flash00"))
    pickle.dump(keep, open(D / f"AO_s7_gmut{r}_flash00_{i:02d}.pkl", "wb"))
    return r, i
if __name__ == "__main__":
    with mp.get_context("fork").Pool(4) as pool:
        list(pool.imap_unordered(job, [(r, i) for r in rows for i in range(LIVES["flash00"])]))
    print("done")
