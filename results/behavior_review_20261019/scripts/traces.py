"""Record fully logged reference lives (bitwise-checked against the kernel) for g0 and g250 of each lineage."""
import multiprocessing as mp, pickle, sys, traceback
from common import *

LIVES = dict(pool=6, persistent=6, flash10=8, flash00=12, harmful_decoy=6, patches=6, contact_food=8, matching=8)
TASK_OFF = {t: 100 + i for i, t in enumerate(LIVES)}
DEST = OUT / "traces"; DEST.mkdir(exist_ok=True)
GEN = {(l, s): genome(l, s) for l in LINEAGES for s in ("0", "250")}


def job(args):
    lin, st, task, i = args
    path = DEST / f"{lin}_g{st}_{task}_{i:02d}.pkl"
    if path.exists():
        return str(path), "cached"
    try:
        w = world(task)
        sd = seeds(LIVES[task], TASK_OFF[task])[i]          # same seeds for g0 and g250 (paired)
        tr = probe.trace(Org(f"{lin}_{st}", GEN[(lin, st)]), sd, "x", abi=ABI, _w=w)
        keep = dict(traj=tr.traj, strokes=tr.strokes, clicks=tr.clicks, placements=tr.placements,
                    task_events=tr.task_events, patch_events=tr.patch_events, motion=tr.motion,
                    cells=tr.cells[["cid", "a", "b", "z", "plane", "cls", "t_birth", "t_death", "n_spikes"]],
                    spikes=tr.spikes[["t", "cid", "a", "b", "z", "mask"]], knobs_end=tr.knobs_end,
                    ledger={k: tr.ledger[k] for k in tr.ledger if isinstance(tr.ledger[k], (int, float))},
                    meta=dict(seed=sd, lin=lin, stage=st, task=task, secs=tr.meta.get("seconds")))
        with open(path, "wb") as f:
            pickle.dump(keep, f)
        return str(path), round(tr.meta.get("seconds", 0), 1)
    except Exception:
        return str(path), "ERROR " + traceback.format_exc()[-800:]


if __name__ == "__main__":
    jobs = [(l, s, t, i) for t, n in LIVES.items() for i in range(n) for l in LINEAGES for s in ("0", "250")]
    nproc = int(sys.argv[1]) if len(sys.argv) > 1 else 6
    t0 = time.time(); done = 0
    with mp.get_context("fork").Pool(nproc) as pool:
        for path, info in pool.imap_unordered(job, jobs):
            done += 1
            if isinstance(info, str) and info.startswith("ERROR"):
                print(path, info, flush=True)
            if done % 40 == 0:
                print(f"{done}/{len(jobs)} {time.time() - t0:.0f}s", flush=True)
    print("done", len(jobs), f"{time.time() - t0:.0f}s")
