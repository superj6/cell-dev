"""Separable CMA-ES tuning of the PF controller (H.es_tune, common random numbers within a generation).
usage: tune_pf.py WORLD VARIANT FOOTPRINT GENS [START_JSON] [KNOBSET] [POP] [LIVES_PER_GEN] [N_TUNE_LIVES=256]
  VARIANT: full (velocity state) | abl (ablation: v_m 0, no tumbles; motion = position diffusion q_pos)
  START_JSON: a params/*.json to warm-start from (its decision knobs; the world rules are re-filled for WORLD)
  KNOBSET: all | short (lead, gain, q_tap, intercept, tol)
Tuning lives: block 122 (256 lives; LIVES_PER_GEN fresh subset per generation); the final pick (ES mean vs best seen)
is re-measured on all 256. Output: params/WORLD__VARIANT__FOOTPRINT.json"""
import sys
import time

from pcommon import *  # noqa: F401,F403

world, variant, fpn, gens = sys.argv[1], sys.argv[2], sys.argv[3], int(sys.argv[4])
start = sys.argv[5] if len(sys.argv) > 5 and sys.argv[5] not in ("-", "") else None
knobset = sys.argv[6] if len(sys.argv) > 6 else "all"
pop = int(sys.argv[7]) if len(sys.argv) > 7 else 10
lpg = int(sys.argv[8]) if len(sys.argv) > 8 else 24
ntune = int(sys.argv[9]) if len(sys.argv) > 9 else 256
vel = variant == "full"
FULL = ["lead", "gain", "q_tap", "tol", "min_align", "intercept", "b_min", "tb_min", "rough_xy", "rough_th", "r_box",
        "steer_min"]
ABL = ["q_pos", "lead", "gain", "q_tap", "tol", "min_align", "intercept", "b_min", "rough_xy", "r_box", "steer_min"]
SHORT = ["lead", "gain", "q_tap", "intercept", "tol"] if vel else ["q_pos", "gain", "q_tap", "intercept", "tol"]
knobs = SHORT if knobset == "short" else (FULL if vel else ABL)
WORLD_RULES = ("sigma", "lam_s", "lam_bg", "v_m", "tau_turn", "R_min", "R_max", "t_resp", "rho_c")
x0 = pf_params(world, velocity=vel)
if start:
    st = jload(start)
    for k, v in st["params"].items():
        if k not in WORLD_RULES:
            x0[PF_NAMES.index(k)] = v
x0 = np.clip(x0, *pf_bounds(x0, knobs))
lo, hi = pf_bounds(x0, knobs)
mask = [PF_NAMES.index(k) for k in knobs]
tsd = seeds(ntune, B_TUNE)
fp = H.footprint(fpn)
t = time.time()
logf = open(f"{HERE}/logs/tune_{world}__{variant}__{fpn}.log", "a")


def log(s):
    print(s, flush=True)
    logf.write(s + "\n"); logf.flush()


log(f"== {world} {variant} {fpn} gens {gens} pop {pop} lpg {lpg} start {start} knobs {knobs}")
res = H.es_tune(PF, x0, fp, WORLDS[world], tsd, lo=lo, hi=hi, iters=gens, popsize=pop, lives_per_gen=lpg,
                threads=THREADS, seed=7, log=log, mask=mask, lib=LIB)
cpu = (time.time() - t) * THREADS
F0 = float(H.ctl_batch(PF, x0[None, :], fp, WORLDS[world], tsd, threads=THREADS, lib=LIB).mean()) if ntune >= 256 else float('nan')  # transfers skip it (CPU)
log(f"done: F_tune {res['F']:+.3f} (start {F0:+.3f}) {cpu:.0f} CPU-s")
out = dict(world=world, variant=variant, footprint=fpn, params=pf_dict(res["x"]), F_tune=res["F"], F_start=F0,
           tune_block=B_TUNE, tune_lives=ntune, gens=gens, pop=pop, lives_per_gen=lpg, knobs=knobs, start=start,
           cpu_s=cpu, history=res["history"])
jdump(out, f"{HERE}/params/{world}__{variant}__{fpn}.json")
