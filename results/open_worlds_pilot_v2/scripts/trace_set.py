"""Trace the generalist, the farmer and the shelter-hider (fresh seeds), and save the traces."""
import pickle

from common import ecology, grid_genome, top_genome, trace

SET = [("generalist_plume", top_genome("AO_s7_LP", 75), "plume", 8_300_001),
       ("farmer", grid_genome("AO_s7_U", 75, "farm", (1, 2)), "farm", 8_300_003),
       ("hider", grid_genome("D90_Z_s5_LP", 50, "predator", (3, 0)), "predator", 8_300_002)]
for name, org, fam, seed in SET:
    tr = trace(org, seed, ecology.realize(fam, seed, T=1024), check=True)
    pickle.dump(tr, open(f"trace_{name}.pkl", "wb"))
    print(name, "F", round(tr.ledger["F"], 2), "kernel", round(tr.meta["kernel_F"], 2), tr.eco_clicks.outcome.value_counts().to_dict(), flush=True)
