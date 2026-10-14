"""Build the SCRATCH controller kernel: repo kernel.c + the capability study's prototype world features
(taskvar/capabilities/make_xkernel.py, copied verbatim below) + CENTRAL CONTROLLER MODE. Never touches the repo.

    python make_ckernel.py [--out DIR/ckernel.so] [--ctl extra_controller.c ...] [--fast]

writes DIR/ckernel.c (one translation unit: patched kernel, then ctl_core.c, ctl_builtin.c and every --ctl file
#included) and compiles it with the repo's flags (-O3 -fopenmp -ffp-contract=off ...; --fast adds -DLIFE_FAST).

Prototype world slots (scratch only; same as make_xkernel.py):
  w[38] blink_on, w[39] blink_off (< 0: FLASH), w[40] t_flip, w[16] dark_amp (if w[19] == 777), w[17]/w[18] blob-1
  epochs e_on/e_off. Ledger col 21 (beats) = captures while dark, col 22 (P_int) = captures at t >= t_mark.

Controller-mode patches (active only inside ctl_life_run; life_run is unchanged, so tissue bodies live exactly as
on the xkernel):
  - Ctx gains ctl_mode / ctl; a thread-local g_ctl_cfg carries the per-life controller config into run_one;
  - birth(): in controller mode, cells schedule no TICK and no NOISE events (inert cells; the living cost is charged
    once at close / at a KILL from t_prev = t_birth, the kernel's own closing R_TICK);
  - batch(): every RECEPTOR delivered to the live occupant (and not receptor_off) is reported to the controller
    (ctl_on_ping) whatever its g_r; two new EXO events: X_FORCE (a commanded stroke: fire() with the event's kappa,
    dropped if the addressed cell is gone) and X_WAKE (a controller wake-up, site-independent);
  - run_one(): ctl_create after the t0 births, ctl_destroy after close.
"""
import argparse, os, subprocess, sys
HERE = os.path.dirname(os.path.abspath(__file__))
SRC = "/home/jgon/project/ml/cell-dev/src/life/kernel.c"


def patched_source(ctl_files=()):
    s = open(SRC).read()

    def sub(old, new, count=1):
        nonlocal s
        n = s.count(old)
        assert n == 1, f"patch target found {n} times: {old[:80]!r}"
        s = s.replace(old, new, count)

    # ===================== make_xkernel.py patches (verbatim) =====================
    sub("S_PANG, S_PDIST, S_PPRES };", "S_PANG, S_PDIST, S_PPRES, S_BLINK, S_EPOCH };")
    sub("  int b2_mode;\n", "  int b2_mode;\n  double blink_on, blink_off, blink_next, t_flip_abs, t_mark_abs, e_on, e_off, e_next;\n"
        "  int visible, e_state; uint64_t blink_k, e_k; int64_t dark_caps, late_caps; double dark_amp;\n")
    sub("  if (w[W_KILLRATE] != 0.0 || w[W_WOUNDRATE] != 0.0 || w[W_DRIFTTAU] != 0.0) return 0;\n", "")
    sub("  if (!(w[W_THLO] >= 0.0 && w[W_THLO] < w[W_TH] && w[W_TH] < 1.0)) return 0;\n", "")
    sub("  c->b2_mode = (int)w[W_B2MODE];\n",
        "  c->b2_mode = (int)w[W_B2MODE];\n"
        "  c->blink_on = w[W_KILLRATE]; c->blink_off = w[W_WOUNDRATE];\n"
        "  c->t_flip_abs = w[W_DRIFTTAU] > 0.0 ? w[W_T0] + w[W_DRIFTTAU] : INFINITY;\n"
        "  c->t_mark_abs = w[W_DRIFTTAU] > 0.0 ? w[W_T0] + w[W_DRIFTTAU] : (w[W_KILLT] >= 0.0 ? w[W_T0] + w[W_KILLT] : w[W_T0] + 0.5 * w[W_T]);\n"
        "  c->e_on = w[W_TAUR]; c->e_off = w[W_TAUE];\n"
        "  c->dark_amp = w[W_HINC] == 777.0 ? w[W_THLO] : 0.0;\n")
    sub("  c->next_sample = c->t0 + 1.0;\n}\nstatic void defer_place",
        "  c->next_sample = c->t0 + 1.0;\n"
        "  c->visible = 1; c->blink_k = 0; c->blink_next = INFINITY;\n"
        "  if (c->blink_on > 0.0 && c->blink_off > 0.0) c->blink_next = poisson_next(c->seed, S_BLINK, 0, c->blink_k++, c->t0, c->blink_on);\n"
        "  if (c->blink_on > 0.0 && c->blink_off < 0.0) c->blink_next = c->t0 + c->blink_on;\n"
        "  c->e_state = 1; c->e_k = 0; c->e_next = INFINITY;\n"
        "  if (c->e_on > 0.0 && c->e_off > 0.0 && c->blob[1].exists) c->e_next = poisson_next(c->seed, S_EPOCH, 0, c->e_k++, c->t0, c->e_on);\n"
        "}\nstatic void defer_place")
    sub("  if (b == 1) B->present = draw2(c->seed, S_PPRES, 1, B->q) < c->b2_p;\n",
        "  if (b == 1) B->present = draw2(c->seed, S_PPRES, 1, B->q) < c->b2_p;\n"
        "  if (b == 0 && c->blink_on > 0.0 && c->blink_off < 0.0) { c->visible = 1; c->blink_next = t + c->blink_on; }\n")
    sub("""    if (!(best < t)) return;
    if (kind == 0) world_timer(c, bb);
    else world_turn(c, bb);""",
        """    if (c->blink_next < best) { best = c->blink_next; kind = 2; }
    if (c->e_next < best) { best = c->e_next; kind = 3; }
    if (!(best < t)) return;
    if (kind == 0) world_timer(c, bb);
    else if (kind == 1) world_turn(c, bb);
    else if (kind == 2) {
      if (c->blink_off < 0.0) { c->visible = 0; c->blink_next = INFINITY; }
      else { c->visible = !c->visible;
             c->blink_next = poisson_next(c->seed, S_BLINK, 0, c->blink_k++, best, c->visible ? c->blink_on : c->blink_off); }
    } else {
      c->e_state = !c->e_state;
      c->e_next = poisson_next(c->seed, S_EPOCH, 0, c->e_k++, best, c->e_state ? c->e_on : c->e_off);
    }""")
    sub("  double rate = c->lam_bg + c->lam_s * halo(px - x0, py - y0, c->sigma);\n  if (c->blob[1].exists && c->blob[1].present) {",
        "  double rate = c->lam_bg + (c->visible ? 1.0 : c->dark_amp) * (c->lam_s * halo(px - x0, py - y0, c->sigma));\n  if (c->blob[1].exists && c->blob[1].present && c->e_state) {")
    sub("    if (c->blob[1].exists && c->blob[1].present) {\n      double x1, y1;\n      blob_at(&c->blob[1], t, &x1, &y1);\n      const double fx",
        "    if (c->blob[1].exists && c->blob[1].present && c->e_state) {\n      double x1, y1;\n      blob_at(&c->blob[1], t, &x1, &y1);\n      const double fx")
    sub("    if (cnt) { c->captures++; c->income = c->income + c->R_cap; }\n",
        "    if (cnt) { c->captures++; c->income = c->income + c->R_cap; if (!c->visible) c->dark_caps++; if (t >= c->t_mark_abs) c->late_caps++; }\n")
    sub("    const double gdz = c->g_n * dz, ei = exp(-(t - s->tf) / c->tau_z);",
        "    const double gdz = (t >= c->t_flip_abs ? -c->g_n : c->g_n) * dz, ei = exp(-(t - s->tf) / c->tau_z);")
    sub("  L[L_PINT] = c->P_int;", "  L[L_PINT] = c->kind == WK_CATCH ? (double)c->late_caps : c->P_int;")
    sub("L[L_BEATS] = (double)c->beats;", "L[L_BEATS] = c->kind == WK_CATCH ? (double)c->dark_caps : (double)c->beats;")

    # ===================== controller mode =====================
    sub("enum { X_KILL, X_STUCK };", "enum { X_KILL, X_STUCK, X_FORCE, X_WAKE };")
    sub("  int fail;\n} Ctx;\n",
        "  int fail;\n  int ctl_mode; void *ctl;  // central-controller mode (scratch harness)\n} Ctx;\n"
        "struct CtlCfg;\n"
        "static _Thread_local const struct CtlCfg *g_ctl_cfg = NULL;\n"
        "static int ctl_create(Ctx *c, const int32_t *init, int32_t n_init);\n"
        "static void ctl_destroy(Ctx *c);\n"
        "static void ctl_on_ping(Ctx *c, double t, int32_t si, uint64_t uid);\n"
        "static void ctl_on_wake(Ctx *c, double t);\n")
    sub("  self_ev(c, si, t1, G_TICK, 0, uid, 0);\n  if (c->noise_rate > 0.0) {",
        "  if (!c->ctl_mode) self_ev(c, si, t1, G_TICK, 0, uid, 0);  // controller mode: inert cells never tick\n"
        "  if (c->noise_rate > 0.0 && !c->ctl_mode) {")
    sub("        if (rec_on && e->uid == X->uid) n_rec++;  // a RECEPTOR that is not delivered vanishes\n",
        "        if (rec_on && e->uid == X->uid) n_rec++;  // a RECEPTOR that is not delivered vanishes\n"
        "        if (c->ctl && X && e->uid == X->uid && !(c->fl & F_RECEPTOR_OFF)) ctl_on_ping(c, t, si, X->uid);"
        "  // e may dangle now\n")
    sub("    const Ev *e = &c->ev[c->grp[G_EXO][i]];\n    if (!X || !X->alive || e->uid != X->uid) continue;\n",
        "    const Ev *e = &c->ev[c->grp[G_EXO][i]];\n"
        "    if (e->sub == X_WAKE) { if (c->ctl) ctl_on_wake(c, t); continue; }  // e may dangle now\n"
        "    if (e->sub == X_FORCE) {  // a commanded stroke of the addressed cell, if it is still alive\n"
        "      if (X && X->alive && e->uid == X->uid) {\n"
        "        const double kp = e->x[0], k0 = X->th[K_KAPPA];\n"
        "        X->th[K_KAPPA] = kp; fire(c, si, X, t); X->th[K_KAPPA] = k0;\n"
        "      }\n"
        "      continue;\n"
        "    }\n"
        "    if (!X || !X->alive || e->uid != X->uid) continue;\n")
    sub("  if (c->kind == WK_CATCH) catch_start(c);  // the world exists before the first time group (9.7.1)\n"
        "  start_life(c, init, n_init);\n",
        "  c->ctl_mode = g_ctl_cfg != NULL;\n"
        "  if (c->kind == WK_CATCH) catch_start(c);  // the world exists before the first time group (9.7.1)\n"
        "  start_life(c, init, n_init);\n"
        "  if (c->ctl_mode && !c->fail && ctl_create(c, init, n_init)) c->fail |= FAIL_ALLOC;\n")
    sub("  close_life(c, L);\n  for (int i = 0; i < HASH_SIZE; i++) H[i] = c->H[i];\n",
        "  close_life(c, L);\n  if (c->ctl_mode) ctl_destroy(c);\n  for (int i = 0; i < HASH_SIZE; i++) H[i] = c->H[i];\n")
    s += "\n// ===================== central-controller harness (scratch) =====================\n"
    s += f'#include "{HERE}/ctl_core.c"\n#include "{HERE}/ctl_builtin.c"\n'
    for f in ctl_files:
        s += f'#include "{os.path.abspath(f)}"\n'
    return s


def build(out=None, ctl_files=(), fast=False):
    out = out or os.path.join(HERE, "ckernel_fast.so" if fast else "ckernel.so")
    csrc = out[:-3] + ".c"
    open(csrc, "w").write(patched_source(ctl_files))
    cmd = ["gcc", "-O3", "-fopenmp", "-ffp-contract=off", "-fPIC", "-shared", "-std=c11", f"-I{HERE}"]
    if fast:
        cmd.append("-DLIFE_FAST")
    tmp = out + ".tmp"
    cmd += ["-o", tmp, csrc, "-lm"]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"build failed: {' '.join(cmd)}\n{r.stderr}")
    os.replace(tmp, out)
    return out


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--out")
    ap.add_argument("--ctl", nargs="*", default=[])
    ap.add_argument("--fast", action="store_true")
    a = ap.parse_args()
    print(build(a.out, a.ctl, a.fast))
