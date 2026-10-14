"""Generate vctl.c: a renamed verbatim copy of the harness's C4 (id 1005, bitwise identical by default), plus
  - ablation switches in extra parameter slots p[21..26] (all 0 = C4 exactly);
  - a fire/ping logger (global, single-thread use only) for the leakage replay test;
  - id 1006 'V4 replay': C4 driven ONLY by an injected ping stream (extra = [n, t1, s1, ...]); real pings ignored.
p[21] dead: drop a ping at sense cell s within `dead` of the last kept ping at s (a refractory relay cell)
p[22] no_neg: 1 = skip the no-ping (negative) evidence factor
p[23] (unused)
p[24] steer_mode: 1 = C0-like steering (each kept ping strokes its own column's act cell, kappa 1, column refractory
      0.5) instead of posterior steering
p[25] tap_mode: 1 = C0-like tapping (a centre ping taps, kappa 1, refractory 4) instead of the posterior tap rule
p[26] (unused)
diag[12], diag[13]: efference position at t0 + T (to compare with the ledger's X_end, Y_end)
"""
import os, re
HERE = os.path.dirname(os.path.abspath(__file__))
SRC = "/home/jgon/project/ml/cell-dev/outputs/openhr/harness/ctl_builtin.c"
s = open(SRC).read()
i = s.index("// =========================================================================================== 5: C4")
c4 = s[i:]
c4 = c4.replace("c4_", "v4_").replace("C4St", "V4St").replace("C4_HIST", "V4_HIST").replace("CTL_C4", "CTL_V4")
c4 = c4.replace('{5, "C4 Bayes grid tracker"', '{1005, "V4 = copy of C4 with ablation switches"')
def sub(old, new):
    global c4
    assert c4.count(old) == 1, old
    c4 = c4.replace(old, new)
# ablation hooks
sub("static void v4_ping(Ctl *k, double t, int s) {\n  V4St *st = k->st;\n",
    "static void v4_ping(Ctl *k, double t, int s) {\n  V4St *st = k->st;\n"
    "  if (v4h_log_on) v4h_log(0, t, (double)s, 0, 0, 0);\n"
    "  if (P_(k, 21, 0.0) > 0.0) { if (t - v4h_lastping(k)[s] < P_(k, 21, 0.0)) return; v4h_lastping(k)[s] = t; }\n"
    "  if (P_(k, 24, 0.0) == 1.0) v4h_c0_steer(k, t, s);\n"
    "  if (P_(k, 25, 0.0) == 1.0 && s == k->centre) v4h_c0_tap(k, t);\n")
sub("  for (int u = st->emin; u <= st->emax; u++) {\n    const int i = st->c + oi + u;\n    if (i < 0 || i >= N) continue;\n    for (int v = st->emin; v <= st->emax; v++) {\n      const int j = st->c + oj + v;\n      if (j < 0 || j >= N) continue;\n      const double old",
    "  if (P_(k, 22, 0.0) == 0.0)\n  for (int u = st->emin; u <= st->emax; u++) {\n    const int i = st->c + oi + u;\n    if (i < 0 || i >= N) continue;\n    for (int v = st->emin; v <= st->emax; v++) {\n      const int j = st->c + oj + v;\n      if (j < 0 || j >= N) continue;\n      const double old")
sub("static void v4_tap(Ctl *k, V4St *st, double t) {\n  if (k->hot >= 0) {",
    "static void v4_tap(Ctl *k, V4St *st, double t) {\n  if (k->hot >= 0 && P_(k, 25, 0.0) != 1.0) {")
sub("  const double gain = P_(k, 15, 1.0);\n  if (gain <= 0.0) return;",
    "  const double gain = P_(k, 15, 1.0);\n  if (gain <= 0.0 || P_(k, 24, 0.0) == 1.0) return;")
sub("static void v4_fini(Ctl *k) {\n  V4St *st = k->st;\n",
    "static void v4_fini(Ctl *k) {\n  V4St *st = k->st;\n"
    "  { double ex, ey; ctl_eff_pos(k, k->t0 + k->T, &ex, &ey); k->diag[12] = ex; k->diag[13] = ey; }\n"
    "  v4h_aux_free(k);\n")
head = r'''
// ---------------------------------------------------------------- verify_headline helpers (scratch)
#include <stdlib.h>
static int v4h_log_on = 0;
static double *v4h_buf = NULL; static long v4h_n = 0, v4h_cap = 0;
static void v4h_log(double kind, double a, double b, double c, double d, double e) {
  if (v4h_n + 6 > v4h_cap) { long nc = v4h_cap ? 2 * v4h_cap : 1 << 16; double *q = realloc(v4h_buf, nc * sizeof(double)); if (!q) return; v4h_buf = q; v4h_cap = nc; }
  double *r = v4h_buf + v4h_n; r[0] = kind; r[1] = a; r[2] = b; r[3] = c; r[4] = d; r[5] = e; v4h_n += 6;
}
void v4h_log_enable(int on) { v4h_log_on = on; v4h_n = 0; }
long v4h_log_get(double *out, long cap) { long m = v4h_n < cap ? v4h_n : cap; memcpy(out, v4h_buf, m * sizeof(double)); return v4h_n; }
static double v4h_fire(Ctl *k, int a, double kappa, double t) {
  const double r = ctl_fire(k, a, kappa, t);
  if (v4h_log_on) v4h_log(1, ctl_now(k), (double)a, kappa, t, r);
  return r;
}
static double v4h_wake(Ctl *k, double t) { return ctl_wake(k, t); }
static int v4h_steer(Ctl *k, double dx, double dy, double t, double kmax, double ma, double tol) {
  const double d2 = k->diag[2];
  const int r = ctl_steer(k, dx, dy, t, kmax, ma, tol);
  if (v4h_log_on) { v4h_log(2, ctl_now(k), dx, dy, t, (double)r); v4h_log(3, kmax, ma, tol, k->diag[2] - d2, 0); }
  return r;
}
// per-life auxiliary state for ablations, keyed by the Ctl pointer (k->st belongs to the C4 copy)
typedef struct { Ctl *k; double *lastping, *lastcol, lasttap; int *col; } V4Aux;
static _Thread_local V4Aux v4h_aux = {0};
static V4Aux *v4h_get(Ctl *k) {
  if (v4h_aux.k != k) {
    free(v4h_aux.lastping); free(v4h_aux.lastcol); free(v4h_aux.col);
    v4h_aux.k = k; v4h_aux.lasttap = -INFINITY;
    v4h_aux.lastping = malloc(sizeof(double) * (k->n_sense + 1)); v4h_aux.lastcol = malloc(sizeof(double) * (k->n_sense + 1));
    v4h_aux.col = malloc(sizeof(int) * (k->n_sense + 1));
    for (int s = 0; s < k->n_sense; s++) {
      v4h_aux.lastping[s] = -INFINITY; v4h_aux.lastcol[s] = -INFINITY; v4h_aux.col[s] = -1;
      for (int a = 0; a < k->n_act; a++)
        if (k->act_ab[2 * a] == k->sense_ab[2 * s] && k->act_ab[2 * a + 1] == k->sense_ab[2 * s + 1]) v4h_aux.col[s] = a;
    }
  }
  return &v4h_aux;
}
static void v4h_aux_free(Ctl *k) {
  if (v4h_aux.k == k) { free(v4h_aux.lastping); free(v4h_aux.lastcol); free(v4h_aux.col); memset(&v4h_aux, 0, sizeof v4h_aux); }
}
static double *v4h_lastping(Ctl *k) { return v4h_get(k)->lastping; }
static void v4h_c0_steer(Ctl *k, double t, int s) {  // C0's column rule (kappa 1, column refractory 0.5)
  V4Aux *x = v4h_get(k);
  const int a = x->col[s];
  if (a < 0 || a == k->hot || t - x->lastcol[s] < 0.5) return;  // as C0: the centre column never steers
  x->lastcol[s] = t;
  v4h_fire(k, a, 1.0, t);
}
static void v4h_c0_tap(Ctl *k, double t) {  // C0's centre tap rule (kappa 1, refractory 4)
  V4Aux *x = v4h_get(k);
  if (k->hot < 0 || t - x->lasttap < 4.0) return;
  x->lasttap = t;
  v4h_fire(k, k->hot, 1.0, t);
}
#define ctl_fire v4h_fire
#define ctl_wake v4h_wake
#define ctl_steer v4h_steer
'''
tail = r'''
#undef ctl_fire
#undef ctl_wake
#undef ctl_steer
// ---------------------------------------------------------------- 1006: C4 copy driven by an injected ping stream
static _Thread_local long v4r_i = 0;
static int v4r_init(Ctl *k) {
  v4r_i = 0;
  const int r = v4_init(k);
  if (r) return r;
  const long n = k->n_extra > 0 ? (long)k->extra[0] : 0;
  for (long q = 0; q < n; q++) ctl_wake(k, k->extra[1 + 2 * q]);
  return 0;
}
static void v4r_ping(Ctl *k, double t, int s) { (void)k; (void)t; (void)s; }  // real pings are ignored
static void v4r_wake(Ctl *k, double t) {
  const long n = k->n_extra > 0 ? (long)k->extra[0] : 0;
  int hit = 0;
  while (v4r_i < n && k->extra[1 + 2 * v4r_i] == t) { v4_ping(k, t, (int)k->extra[2 + 2 * v4r_i]); v4r_i++; hit = 1; }
  if (!hit) v4_wake(k, t);
}
static const CtlDef CTL_V4R = {1006, "V4 replay (injected pings only)", v4r_init, v4r_ping, v4r_wake, v4_fini};
CTL_REGISTER(CTL_V4R)
'''
open(os.path.join(HERE, "vctl.c"), "w").write(head + c4 + tail)
print("wrote vctl.c")
