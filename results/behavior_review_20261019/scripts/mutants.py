"""Single-step neighbourhood of each final (g250) genome: are there one-mutation steps toward memory use?
Screen 192 ordinary mutants (the run's own operator: n_mut 2 scaled, p_cell 0.5, no dup/del) on 32 lives each of
flash00 (dark-phase captures) and matching (balanced accuracy), then confirm the top 4 per task on 256 fresh paired
lives against the unchanged parent. Also records each mutant's POOL F on 16 lives for trade-offs."""
from common import *
NM, NS, NC, TOP = 192, 32, 256, 4


def runB(G, w, sd, threads=2):
    B, n = len(G), len(sd)
    lv = build.run(w, list(sd) * B, genomes=ABI.pack_genomes(np.asarray(G), w.lattice), abi=ABI, threads=threads,
                   genome_of=[b for b in range(B) for _ in range(n)])
    return {k: np.asarray(lv[k], dtype=float).reshape(B, n) for k in
            ("F", "captures", "low_light_captures", "misses", "correct_choices_narrow", "correct_choices_broad",
             "wrong_choices_narrow", "wrong_choices_broad", "n_end") if k in ABI.LEDGER}


def bal_acc(r):
    n = r["correct_choices_narrow"] / np.maximum(r["correct_choices_narrow"] + r["wrong_choices_narrow"], 1)
    b = r["correct_choices_broad"] / np.maximum(r["correct_choices_broad"] + r["wrong_choices_broad"], 1)
    return 0.5 * (n + b), n, b


out = {}
gen = torch.Generator().manual_seed(45919)
t0 = time.time()
for li, lin in enumerate(LINEAGES):
    p = layout.from_dict(SEL[lin]["250"]["genome"]).reshape(1, -1)
    kids = layout.mutate(p.repeat(NM, 1), gen, 2, 0.5)
    G = torch.cat([p, kids]).detach().numpy().astype(np.float32)
    rec = {}
    sf = seeds(NS, 500 + li); sm = seeds(NS, 510 + li); sp = seeds(16, 520 + li)
    rf = runB(G, world("flash00"), sf); rm = runB(G, world("matching"), sm); rp = runB(G, world("pool"), sp)
    ba = bal_acc(rm)[0]
    rec["screen"] = dict(flash_low=rf["low_light_captures"].mean(1).tolist(), flash_F=rf["F"].mean(1).tolist(),
                         match_bal=ba.mean(1).tolist(), match_F=rm["F"].mean(1).tolist(), pool_F=rp["F"].mean(1).tolist())
    conf = {}
    for task, score in (("flash00", rf["low_light_captures"].mean(1)), ("matching", ba.mean(1))):
        idx = [int(i) for i in np.argsort(-score[1:])[:TOP] + 1]
        sc = seeds(NC, 600 + 10 * li + (task == "matching"))
        r = runB(G[[0] + idx], world(task), sc)
        rows = []
        for j, i in enumerate(idx, start=1):
            if task == "flash00":
                d = r["low_light_captures"][j] - r["low_light_captures"][0]
            else:
                d = bal_acc(r)[0][j] - bal_acc(r)[0][0]
            dF = r["F"][j] - r["F"][0]
            rows.append(dict(row=i, screen=float(score[i]), d=float(d.mean()), d_se=float(d.std(ddof=1) / np.sqrt(NC)),
                             dF=float(dF.mean()), dF_se=float(dF.std(ddof=1) / np.sqrt(NC))))
        base = (r["low_light_captures"][0].mean() if task == "flash00" else bal_acc(r)[0][0].mean())
        conf[task] = dict(parent=float(base), parent_screen=float(score[0]), top=rows)
    rec["confirm"] = conf
    out[lin] = rec
    json.dump(out, open(OUT / "mutants.json", "w"))
    print(lin, f"{time.time() - t0:.0f}s", json.dumps(conf)[:600], flush=True)
