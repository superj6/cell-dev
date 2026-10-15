"""C3 fallback: ES-train the harness's generic recurrent controller (C3 tiny RNN, info-matched) in a world where the
designed PF controller failed the 3 SE bar while the ceiling is large. Used only in such worlds.
usage: c3_es.py WORLD [FOOTPRINT=hollow3] [N_H=6] [GENS=40] [POP=16] [LPG=24] [CPU_CAP_S=21600]
Tuning lives: block 125 (256; LPG fresh per generation); scoring is done by c3_score in the same script on the first
512 lives of block 130 vs the best reflex of out/score_WORLD__main.npz. Output: params/WORLD__c3__FP.json,
out/c3.json[WORLD]. Separable CMA-ES on all weights (H.es_tune), sigma0 0.3, bounds +-3, thr in [0, 1.5]."""
import resource
import sys

from pcommon import *  # noqa: F401,F403

world = sys.argv[1]
fpn = sys.argv[2] if len(sys.argv) > 2 else "hollow3"
n_h = int(sys.argv[3]) if len(sys.argv) > 3 else 6
gens = int(sys.argv[4]) if len(sys.argv) > 4 else 40
pop = int(sys.argv[5]) if len(sys.argv) > 5 else 16
lpg = int(sys.argv[6]) if len(sys.argv) > 6 else 24
cap = float(sys.argv[7]) if len(sys.argv) > 7 else 21600.0
fp = H.footprint(fpn)
rng = np.random.default_rng(3)
x0 = H.rnn_params(fp, n_h, dt=0.5, thr=0.5, rng=rng, scale=0.1)
lo = np.full_like(x0, -3.0); hi = np.full_like(x0, 3.0)
lo[:3] = hi[:3] = x0[:3]
lo[2], hi[2] = 0.0, 1.5
sig = np.full_like(x0, 0.3)
tsd = seeds(256, B_C3)
cpu0 = resource.getrusage(resource.RUSAGE_SELF)
logf = open(f"{HERE}/logs/c3_{world}__{fpn}.log", "a")


def log(s):
    print(s, flush=True); logf.write(s + "\n"); logf.flush()


def cpu_used():
    r = resource.getrusage(resource.RUSAGE_SELF)
    return r.ru_utime + r.ru_stime - cpu0.ru_utime - cpu0.ru_stime


x, done = x0, 0
while done < gens and cpu_used() < cap:
    step = min(10, gens - done)
    res = H.es_tune(H.C3, x, fp, WORLDS[world], tsd, sigma0=sig, lo=lo, hi=hi, iters=step, popsize=pop,
                    lives_per_gen=lpg, threads=THREADS, seed=11 + done, log=log, mask=np.arange(2, len(x0)),
                    privileged=False, lib=LIB)
    x, done = res["x"], done + step
    log(f"block of {step} gens done ({done}/{gens}): F_tune {res['F']:+.3f}, CPU {cpu_used():.0f} s")
S = jload(f"{HERE}/out/score_{world}__main.json")
Z = np.load(f"{HERE}/out/score_{world}__main.npz")
key = lambda n: n.replace("@", "_at_").replace(" ", "_").replace(":", "_").replace("(", "").replace(")", "")  # noqa
sd = seeds(512, B_SCORE)
assert list(Z["seeds"][:512]) == sd
r = ctl(H.C3, x, fpn, world, sd, privileged=False)
gap = paired(Fv(r), Z[key(S["best_reflex"])][:512])
log(f"C3@{fpn} on fresh lives: F {Fv(r).mean():+.3f}, gap vs {S['best_reflex']} {fmt(gap)}")
jdump(dict(world=world, footprint=fpn, n_h=n_h, gens=done, pop=pop, lpg=lpg, x=x, cpu_s=cpu_used()),
      f"{HERE}/params/{world}__c3__{fpn}.json")
out = jload(f"{HERE}/out/c3.json", {})
out[world] = dict(gap=f"{fmt(gap)} (C3 RNN n_h {n_h} @{fpn}, {done} ES gens, {cpu_used() / 3600:.2f} CPU-h)", F=float(Fv(r).mean()),
                  gap_raw=gap)
jdump(out, f"{HERE}/out/c3.json")
