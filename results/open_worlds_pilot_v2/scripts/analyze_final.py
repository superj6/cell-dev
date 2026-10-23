"""Pilot v2 final check: founders vs generation 100 (U and LP arms), trained and held-out worlds, sense lesions.

Top 8 genomes of each population by stored fitness, 24 fresh paired lives per world (seeds 8_400_000 + i)."""
import json
import sys
from pathlib import Path

import numpy as np
import torch

sys.path.insert(0, str(Path(__file__).resolve().parent))
import analyze_g50 as A  # noqa: E402
from src.life import ecology  # noqa: E402

L = 24
FAMS = list(ecology.FAMILIES) + [f"{f}_transfer" for f in ecology.FAMILIES]
A.L = L
A.WORLDS = {f: [ecology.realize(f, 8_400_000 + s, T=1024) for s in range(L)] for f in FAMS}
OUT = Path(__file__).resolve().parent


def top8(run_name, gen):
    d, lay = A.load(run_name, gen)
    fit = d.get("fitness")
    idx = np.argsort(-np.array(fit))[:8] if fit and None not in fit else np.arange(8)
    return lay, torch.stack([lay.from_dict(d["genomes"][i]) for i in idx])


def per_life(lay, g, fam):
    m = A.run(lay, g, fam)
    return {k: v.mean(0).tolist() for k, v in m.items()}  # mean over the 8 genomes, per life (paired across sets)


sets = {"D90 founders": ("D90_Z_s5_U", 0), "AO founders": ("AO_s7_U", 0),
        "D90 U": ("D90_Z_s5_U", 100), "D90 LP": ("D90_Z_s5_LP", 100),
        "AO U": ("AO_s7_U", 100), "AO LP": ("AO_s7_LP", 100), "scratch g50": ("scratch_LP", 50)}
res = {"sets": {}, "lesion": {}}
for name, (run_name, gen) in sets.items():
    lay, g = top8(run_name, gen)
    res["sets"][name] = {f: per_life(lay, g, f) for f in FAMS}
    print(name, {f: round(float(np.mean(res["sets"][name][f]["F"])), 2) for f in FAMS}, flush=True)
    (OUT / "final.json").write_text(json.dumps(res))
    if gen == 100:
        gl = A.lesion(g, lay)
        res["lesion"][name] = {f: per_life(lay, gl, f)["F"] for f in ecology.FAMILIES}
        print("  senses off", {f: round(float(np.mean(res["lesion"][name][f])), 2) for f in ecology.FAMILIES}, flush=True)
        (OUT / "final.json").write_text(json.dumps(res))
print("done", flush=True)
