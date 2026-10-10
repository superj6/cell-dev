// 1003  CU: reflex + CUSUM motor-law detector (information-matched; scratch measuring stick, never an organism).
//
// Actions are C0's reflex: an off-centre ping of sense column s strokes the act cell of the same column (mapping 0,
// right under the normal pull law) or of the point-mirrored column (-a, -b) (mapping 1, right under the flipped push
// law); a centre ping taps (refractory refr_tap). The mapping is chosen by a CUSUM change-point test on the
// CONSEQUENCES of the controller's own strokes, using only its pings, its clock and its efference copy:
//   pair event: two pings within tw of each other (read times), sense positions p1 -> p2 at most dmax apart, while the
//     efference copy (normal-law model) moved the dot by D between the two read times. Under the normal law the
//     target's position relative to the dot moves by -D, under the flipped law by +D, so x = (p2 - p1) . D / |D| is
//     about -|D| (normal) or +|D| (flipped). Pairs with |D| < dmin_move are skipped.
//   lost event: a stroke was made and no ping followed within tw (the target was pushed out of the sensed area).
//   evidence that the CURRENT mapping is wrong: e = sgn_cur * a * x + b * [lost], sgn_cur = +1 (mapping 0), -1 (1).
//   S = max(0, S + e - kdrift); when S > h (and t - t0 in [t_min, t_max]) the mapping switches and S resets to 0.
//   two_way 0: the first switch latches (one-way flip worlds); 1: the mapping can switch back (telegraph worlds).
// A clock switch is the special case kdrift < 0 (S grows every event): it switches at the first event after t_min.
// p: [0] a [1] b [2] kdrift [3] h [4] tw [5] dmax [6] two_way [7] t_min [8] t_max [9] refr_tap [10] refr_m
//    [11] dt_sample [12] start_map [13] dmin_move [14] kappa_m
// diag: [5] first switch (t; -1 never) [6] time in mapping 1 [7] switches [8] final mapping [9] pair events
//       [10] lost events [11] last switch (t; -1) [12] time in mapping 1 at t - t0 < 256 [13] S at the end
//       [14] time in mapping 0 at t - t0 >= 768
#include "ctl_api.h"

#define CU_HIST 128
typedef struct {
  int *col, *mir, map, latched;
  double *lastp, last_tap, S, t_map;
  int have_prev; double pt, px, py, pex, pey;  // previous ping: read time, sense position, efference at read time
  double last_stroke, last_ping; int lost_armed;
  double ht[CU_HIST], hx[CU_HIST], hy[CU_HIST]; int hn, hh;
} CuSt;

static double CUP(const Ctl *k, int i, double d) { return i < k->np ? k->p[i] : d; }

static void cu_hist_push(Ctl *k, CuSt *st, double t) {
  double x, y;
  ctl_eff_pos(k, t, &x, &y);
  const int i = (st->hh + st->hn) % CU_HIST;
  st->ht[i] = t; st->hx[i] = x; st->hy[i] = y;
  if (st->hn < CU_HIST) st->hn++; else st->hh = (st->hh + 1) % CU_HIST;
}
static void cu_pos_at(Ctl *k, CuSt *st, double t, double *x, double *y) {  // efference position at a past time
  if (t >= ctl_now(k)) { ctl_eff_pos(k, t, x, y); return; }
  double pt = ctl_now(k), px, py;
  ctl_eff_pos(k, pt, &px, &py);
  for (int q = st->hn - 1; q >= 0; q--) {
    const int i = (st->hh + q) % CU_HIST;
    if (st->ht[i] <= t) {
      const double w = pt > st->ht[i] ? (t - st->ht[i]) / (pt - st->ht[i]) : 0.0;
      *x = st->hx[i] + w * (px - st->hx[i]); *y = st->hy[i] + w * (py - st->hy[i]);
      return;
    }
    pt = st->ht[i]; px = st->hx[i]; py = st->hy[i];
  }
  *x = px; *y = py;
}
static void cu_account(Ctl *k, CuSt *st, double t) {  // time-in-mapping diagnostics up to t
  const double dt = t - st->t_map;
  if (dt <= 0.0) return;
  const double a = st->t_map - k->t0, b = t - k->t0;
  if (st->map) {
    k->diag[6] += dt;
    if (a < 256.0) k->diag[12] += (b < 256.0 ? b : 256.0) - a;
  } else if (b > 768.0) {
    k->diag[14] += b - (a > 768.0 ? a : 768.0);
  }
  st->t_map = t;
}
static void cu_evidence(Ctl *k, CuSt *st, double t, double e) {
  st->S += e - CUP(k, 2, 0.1);
  if (st->S < 0.0) st->S = 0.0;
  const double tau = t - k->t0;
  if (st->latched || tau < CUP(k, 7, 0.0) || tau > CUP(k, 8, 1e300)) return;
  if (st->S > CUP(k, 3, 5.0)) {
    cu_account(k, st, t);
    st->map = !st->map;
    st->S = 0.0;
    k->diag[7] += 1.0;
    if (k->diag[5] < 0.0) k->diag[5] = t;
    k->diag[11] = t;
    if (CUP(k, 6, 0.0) == 0.0) st->latched = 1;
  }
}
static int cu_init(Ctl *k) {
  CuSt *st = calloc(1, sizeof(CuSt));
  if (!st) return -1;
  k->st = st;
  st->col = malloc(sizeof(int) * (k->n_sense + 1)); st->mir = malloc(sizeof(int) * (k->n_sense + 1));
  st->lastp = malloc(sizeof(double) * (k->n_sense + 1));
  if (!st->col || !st->mir || !st->lastp) return -1;
  for (int s = 0; s < k->n_sense; s++) {
    st->col[s] = -1; st->mir[s] = -1; st->lastp[s] = -INFINITY;
    for (int a = 0; a < k->n_act; a++) {
      if (k->act_ab[2 * a] == k->sense_ab[2 * s] && k->act_ab[2 * a + 1] == k->sense_ab[2 * s + 1]) st->col[s] = a;
      if (k->act_ab[2 * a] == -k->sense_ab[2 * s] && k->act_ab[2 * a + 1] == -k->sense_ab[2 * s + 1]) st->mir[s] = a;
    }
  }
  st->last_tap = -INFINITY; st->last_stroke = -INFINITY; st->last_ping = -INFINITY;
  st->map = CUP(k, 12, 0.0) != 0.0;
  st->t_map = k->t0;
  k->diag[5] = -1.0; k->diag[11] = -1.0;
  cu_hist_push(k, st, k->t0);
  ctl_wake(k, k->t0 + CUP(k, 11, 0.25));
  return 0;
}
static void cu_ping(Ctl *k, double t, int s) {
  CuSt *st = k->st;
  const double tr = t - k->d_min, tw = CUP(k, 4, 3.0);
  double ex, ey;
  cu_pos_at(k, st, tr, &ex, &ey);
  const double px = k->sense_xy[2 * s], py = k->sense_xy[2 * s + 1];
  st->last_ping = t; st->lost_armed = 0;
  if (st->have_prev && tr - st->pt <= tw) {
    const double qx = px - st->px, qy = py - st->py, Dx = ex - st->pex, Dy = ey - st->pey;
    const double dD = sqrt(Dx * Dx + Dy * Dy);
    if (sqrt(qx * qx + qy * qy) <= CUP(k, 5, 2.5) && dD >= CUP(k, 13, 0.05)) {
      const double x = (qx * Dx + qy * Dy) / dD;
      k->diag[9] += 1.0;
      cu_evidence(k, st, t, (st->map ? -1.0 : 1.0) * CUP(k, 0, 1.0) * x);
    }
  }
  st->have_prev = 1; st->pt = tr; st->px = px; st->py = py; st->pex = ex; st->pey = ey;
  if (s == k->centre) {
    if (k->hot >= 0 && t >= st->last_tap + CUP(k, 9, 4.0)) { st->last_tap = t; ctl_fire(k, k->hot, 1.0, t); }
    return;
  }
  const int a = st->map ? st->mir[s] : st->col[s];
  if (a < 0 || a == k->hot || t < st->lastp[s] + CUP(k, 10, 0.5)) return;
  st->lastp[s] = t;
  const double tf = ctl_fire(k, a, CUP(k, 14, 1.0), t);
  if (tf > 0) { st->last_stroke = tf; st->lost_armed = 1; }
}
static void cu_wake(Ctl *k, double t) {
  CuSt *st = k->st;
  cu_hist_push(k, st, t);
  const double tw = CUP(k, 4, 3.0);
  if (st->lost_armed && t - st->last_stroke > tw && st->last_ping < st->last_stroke) {
    st->lost_armed = 0;
    k->diag[10] += 1.0;
    cu_evidence(k, st, t, CUP(k, 1, 1.0));
  }
  cu_account(k, st, t);
  ctl_wake(k, t + CUP(k, 11, 0.25));
}
static void cu_fini(Ctl *k) {
  CuSt *st = k->st;
  if (!st) return;
  cu_account(k, st, k->T > 0 ? k->t0 + k->T : st->t_map);
  k->diag[8] = st->map; k->diag[13] = st->S;
  free(st->col); free(st->mir); free(st->lastp); free(st);
}
static const CtlDef CTL_CU = {1003, "CU reflex + CUSUM law detector", cu_init, cu_ping, cu_wake, cu_fini};
CTL_REGISTER(CTL_CU)
