"""Per-sense lesions of four standout generation-50 elites (fresh seeds 8_300_000 + i, 24 lives)."""
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from analyze_g50 import L, SENSES, lesion, load, run  # noqa: E402

PICKS = [("AO_s7_LP", "plume", [3, 3]), ("AO_s7_U", "plume", [3, 3]), ("AO_s7_LP", "predator", [0, 1]),
         ("D90_Z_s5_LP", "predator", [3, 0]), ("AO_s7_LP", "farm", [3, 2])]
out = []
for run_name, fam, (k0, k1) in PICKS:
    d, lay = load(run_name, 50)
    gr = d["elites"][fam]
    i = gr["cells"].index(k0 * 4 + k1)
    g = lay.from_dict(gr["genomes"][i])[None]
    base = run(lay, g, fam)
    on = [m for m in SENSES if base[f"on_{SENSES[m]}"].mean() > 0.5]
    row = dict(run=run_name, world=fam, cell=[k0, k1], F=float(base["F"].mean()), senses_on=[SENSES[m] for m in on])
    for m in on:
        les = run(lay, lesion(g, lay, [m]), fam)
        dF = (base["F"] - les["F"])[0]
        keys = dict(plume=["upflow", "toxin", "food"], predator=["hits", "killed", "shelter", "food"],
                    farm=["planted", "harvested", "spoiled"])[fam]
        row[SENSES[m]] = dict(dF=round(float(dF.mean()), 2), se=round(float(dF.std(ddof=1) / np.sqrt(L)), 2),
                              **{k: round(float(les[k].mean()), 2) for k in keys})
    row["base"] = {k: round(float(base[k].mean()), 2) for k in ("upflow", "toxin", "food", "hits", "killed", "shelter",
                                                                  "planted", "harvested", "spoiled")}
    out.append(row)
    print(json.dumps(row), flush=True)
(Path(__file__).resolve().parent / "sense_lesions_g50.json").write_text(json.dumps(out, indent=1))
