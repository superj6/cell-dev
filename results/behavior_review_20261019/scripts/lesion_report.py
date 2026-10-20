import json, numpy as np
L = json.load(open("lesions.json"))
ARMS = ["lateral_off", "hidden_off", "genes_blind", "freeze"]
def ms(x):
    x = np.asarray(x); return x.mean(), x.std(ddof=1) / np.sqrt(len(x))
print("Lesion cost = lesioned minus intact, same 128 lives, scored after t=200. Units: food items per life (matching: F).")
print("'gain' = g250 - g0 intact; 'x' = how much more (negative) the g250 genome loses than g0 under the lesion (interaction).")
for task in ["pool", "persistent", "flash10", "flash00", "harmful_decoy", "patches", "contact_food", "matching"]:
    print(f"\n{task}")
    key = "F" if task == "matching" else "captures"
    for lin in ["AO_s7", "D90_Z_s5", "speck_s6", "speck_s8"]:
        a, b = L.get(f"{lin}|0|{task}"), L.get(f"{lin}|250|{task}")
        if not a or not b: continue
        g, gs = ms(np.array(b["base"][key]) - np.array(a["base"][key]))
        line = f"  {lin:9s} intact g0 {np.mean(a['base'][key]):6.2f} g250 {np.mean(b['base'][key]):6.2f} (gain {g:+.2f}±{gs:.2f})"
        for arm in ARMS:
            d0 = np.array(a[arm][key]) - np.array(a["base"][key]); d2 = np.array(b[arm][key]) - np.array(b["base"][key])
            x, xs = ms(d2 - d0)
            line += f" | {arm.split('_')[0]:7s} {d0.mean():+6.2f}/{d2.mean():+6.2f} x{x:+.2f}±{xs:.2f}"
        print(line)
