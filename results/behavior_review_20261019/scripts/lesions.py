"""Kernel-fork lesions from t=200 (scored over [200, T]) on the same 128 lives, g0 vs g250."""
from common import *
from src.life import analysis
ARMS = ["base", "lateral_off", "hidden_off", "genes_blind", "freeze"]
TASKS = ["pool", "persistent", "flash10", "flash00", "harmful_decoy", "patches", "contact_food", "matching"]
N, TF = 128, 200.0
KEYS = ["F", "captures", "misses", "clicks", "b2_clicks", "low_light_captures", "n_end", "n_H_end",
        "correct_choices_narrow", "correct_choices_broad", "wrong_choices_narrow", "wrong_choices_broad"]
out = {}
path = OUT / "lesions.json"
if path.exists():
    out = json.load(open(path))
t0 = time.time()
for task in TASKS:
    sd = seeds(N, 300 + TASKS.index(task))
    for lin in LINEAGES:
        for st in ("0", "250"):
            key = f"{lin}|{st}|{task}"
            if key in out:
                continue
            g = genome(lin, st); rec = {}
            for arm in ARMS:
                flags = 0 if arm == "base" else ABI.flags(arm)
                w = replace(world(task), t_fork=TF, t_open=TF, fork_flags=flags)
                lv = run(g, w, sd, threads=2)
                rec[arm] = {k: np.asarray(lv[k], dtype=float).tolist() for k in KEYS if k in lv.ledger.dtype.names} \
                    if hasattr(lv.ledger, "dtype") and lv.ledger.dtype.names else \
                    {k: np.asarray(lv[k], dtype=float).tolist() for k in KEYS if _has(lv, k)} if False else \
                    {k: np.asarray(lv[k], dtype=float).tolist() for k in KEYS if k in ABI.LEDGER}
            out[key] = rec
            json.dump(out, open(path, "w"))
    print(task, f"{time.time() - t0:.0f}s", flush=True)
print("done")
