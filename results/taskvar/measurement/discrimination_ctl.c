// Discrimination measuring sticks (scratch; never part of an organism).
//
// 1100  D2 two-blob Bayes grid tracker. A generalisation of the harness's C4 (same grid machinery) that tracks BOTH
//       screen blobs: the target (blob 0) and the second blob (blob 1: poison / decoy), on two grids P0, P1 in the
//       efference frame, plus the mass A that blob 1 is absent (b2_p < 1). Factored (assumed-density) filter:
//         ping at screen point p (read d_min before delivery):
//             m0 = E_P0[lam0(x0 - p)],  m1 = E_P1[lam1(x1 - p)]   (lam0 = lam_s halo_sigma, lam1 = lam_s b2_amp halo_b2sigma)
//             P0(x0) *= lam_bg + m1 + lam0(x0 - p);   P1(x1) *= lam_bg + m0 + lam1(x1 - p);   A *= lam_bg + m0
//           (the exact marginal update of an independent prior, since the ping rate is additive), then re-factor;
//         no ping over dt: P0 *= exp(-dt sum_s lam0), P1 *= exp(-dt sum_s lam1)        (exact: the rate is additive)
//         timer re-placement (rate 1/t_resp; blob 1 follows the target's placements in b2_mode 0, its own timer in
//           mode 1 - the same hazard either way): mass moves to the placement annulus; blob 1 present w.p. b2_p;
//         own commanded click at t_c: q0 = P0 mass under the dot (a capture) is re-placed; in mode 0 blob 1 is re-placed
//           with probability q0; in mode 1 its mass under the dot is re-placed with probability 1 - q0;
//         motion: Gaussian blur of both grids (variance v_t^2 tau_eff per unit time).
//       Tap when q0 >= q_tap * (1 + w_p * q1), q0 = P0 mass within rho_c of the dot at the stroke time, q1 = P(blob 1
//       within b2_rho there). Steer to the rho_c box that maximises P0 - w_s P1.
//       model (p[25]):  0 = BLIND: no blob-1 model (exactly C4's single-blob filter: every ping is target or noise);
//                       1 = INFO: the two-blob filter above (information-matched; the b2_* world RULES are parameters);
//                       2 = ORACLE-B1 (privileged): blob 1's true position / presence replace P1 (in the ping update
//                           and in q1: 1 if the true blob 1 will be within b2_rho + p_margin of the dot at the stroke
//                           time). The target is still tracked from pings only, so 2 minus 0 is the value of perfect
//                           discrimination for an information-matched tracker.
// p: [0] sigma [1] lam_s [2] lam_bg [3] v_t [4] tau_eff [5] R_min [6] R_max [7] t_resp [8] rho_c
//    [9] b2_amp [10] b2_sigma [11] b2_p [12] b2_mode [13] b2_rho [14] b2_value
//    [15] dt (0.5) [16] h (0.2) [17] W (7) [18] blur_every (2) [19] gain (1) [20] kmax (1) [21] min_align (0.5)
//    [22] tol (0.15) [23] q_tap (0.3) [24] steer_min (0) [25] model (1) [26] w_p (4) [27] w_s (0) [28] p_margin (0)
//    [29] tau_eff1 (blob-1 diffusion; <= 0: = tau_eff)
// diag: [5] sum of steer box mass [6] steers [7] taps vetoed by the blob-1 term [8] sum q1 at taps [9] restarts
//       [10] taps [11] sum q0 at taps
#include "ctl_api.h"

#define D2_HIST 64
typedef struct {
  int N, c, M, model, mode1, has1;
  double h, gx0, gy0, var0, var1, t_blur, t_last;
  double *P0, *P1, A, tot0, tot1;
  double *tmp, *sat, *E0, *E1, *ann, ratio;
  int e0min, e0max, e1min, e1max, amin, amax;
  int *disk, ndisk, *disk1, ndisk1;
  double *gx, *gy;               // separable halo factors (scratch)
  double clk[64]; int nclk;
  double ht[D2_HIST], hx[D2_HIST], hy[D2_HIST]; int hn, hh;
} D2St;

static double D2P(const Ctl *k, int i, double d) { return i < k->np ? k->p[i] : d; }
static inline int d2_in(const D2St *st, int i, int j) { return i >= 0 && j >= 0 && i < st->N && j < st->N; }
static void d2_hist_push(Ctl *k, D2St *st, double t) {
  double x, y;
  ctl_eff_pos(k, t, &x, &y);
  const int i = (st->hh + st->hn) % D2_HIST;
  st->ht[i] = t; st->hx[i] = x; st->hy[i] = y;
  if (st->hn < D2_HIST) st->hn++; else st->hh = (st->hh + 1) % D2_HIST;
}
static void d2_pos_at(Ctl *k, D2St *st, double t, double *x, double *y) {
  if (t >= ctl_now(k)) { ctl_eff_pos(k, t, x, y); return; }
  double pt = ctl_now(k), px, py;
  ctl_eff_pos(k, pt, &px, &py);
  for (int q = st->hn - 1; q >= 0; q--) {
    const int i = (st->hh + q) % D2_HIST;
    if (st->ht[i] <= t) {
      const double w = pt > st->ht[i] ? (t - st->ht[i]) / (pt - st->ht[i]) : 0.0;
      *x = st->hx[i] + w * (px - st->hx[i]); *y = st->hy[i] + w * (py - st->hy[i]);
      return;
    }
    pt = st->ht[i]; px = st->hx[i]; py = st->hy[i];
  }
  *x = px; *y = py;
}
static void d2_cell(const D2St *st, double bx, double by, int *oi, int *oj) {
  *oi = (int)lround((bx - st->gx0) / st->h); *oj = (int)lround((by - st->gy0) / st->h);
}
// add mass m of the placement annulus around (bx, by) to grid P (returns the mass actually added)
static double d2_place(D2St *st, double *P, double bx, double by, double m) {
  int oi, oj;
  d2_cell(st, bx, by, &oi, &oj);
  const int M = st->M, W2 = 2 * M + 1;
  double added = 0.0;
  for (int u = st->amin; u <= st->amax; u++) {
    const int i = st->c + oi + u;
    if (i < 0 || i >= st->N) continue;
    for (int v = st->amin; v <= st->amax; v++) {
      const int j = st->c + oj + v;
      if (j < 0 || j >= st->N) continue;
      const double a = st->ann[(u + M) * W2 + (v + M)];
      if (a == 0.0) continue;
      P[i * st->N + j] += m * a; added += m * a;
    }
  }
  return added;
}
static void d2_normalize(Ctl *k, D2St *st) {
  const int NN = st->N * st->N;
  double s = 0.0;
  for (int i = 0; i < NN; i++) s += st->P0[i];
  if (!(s > 1e-280) || !isfinite(s)) {
    memset(st->P0, 0, sizeof(double) * NN);
    double bx, by;
    ctl_eff_pos(k, ctl_now(k), &bx, &by);
    st->tot0 = d2_place(st, st->P0, bx, by, 1.0);
    k->diag[9] += 1.0;
    s = st->tot0;
  }
  double r = 1.0 / s;
  for (int i = 0; i < NN; i++) st->P0[i] *= r;
  st->tot0 = 1.0;
  if (st->model != 1) return;
  s = st->A;
  for (int i = 0; i < NN; i++) s += st->P1[i];
  if (!(s > 1e-280) || !isfinite(s)) {
    memset(st->P1, 0, sizeof(double) * NN);
    double bx, by;
    ctl_eff_pos(k, ctl_now(k), &bx, &by);
    const double bp = D2P(k, 11, 1.0);
    d2_place(st, st->P1, bx, by, bp);
    st->A = 1.0 - bp;
    k->diag[9] += 1.0;
    s = 1.0;
  }
  r = 1.0 / s;
  for (int i = 0; i < NN; i++) st->P1[i] *= r;
  st->A *= r;
  st->tot1 = 1.0;
}
static void d2_shift(D2St *st, double *P, int oi, int oj) {
  const int N = st->N;
  for (int i = 0; i < N; i++)
    for (int j = 0; j < N; j++) {
      const int si = i + oi, sj = j + oj;
      st->tmp[i * N + j] = d2_in(st, si, sj) ? P[si * N + sj] : 0.0;
    }
  memcpy(P, st->tmp, sizeof(double) * N * N);
}
static void d2_recentre(Ctl *k, D2St *st) {
  double bx, by;
  ctl_eff_pos(k, ctl_now(k), &bx, &by);
  int oi, oj;
  d2_cell(st, bx, by, &oi, &oj);
  if (abs(oi) <= st->N / 6 && abs(oj) <= st->N / 6) return;
  d2_shift(st, st->P0, oi, oj);
  if (st->model == 1) d2_shift(st, st->P1, oi, oj);
  st->gx0 += oi * st->h; st->gy0 += oj * st->h;
  d2_normalize(k, st);
}
static void d2_blur1(D2St *st, double *P, double var) {
  const double s = sqrt(var) / st->h;
  if (s < 0.05) return;
  int r = (int)ceil(3.0 * s);
  if (r > 12) r = 12;
  double kern[25], ks = 0.0;
  for (int d = -r; d <= r; d++) { kern[d + r] = exp(-0.5 * d * d / (s * s)); ks += kern[d + r]; }
  for (int d = 0; d <= 2 * r; d++) kern[d] /= ks;
  const int N = st->N;
  for (int i = 0; i < N; i++) {
    const double *row = P + (size_t)i * N;
    double *out = st->tmp + (size_t)i * N;
    for (int j = 0; j < N; j++) {
      double v = 0.0;
      if (j >= r && j < N - r) { const double *q = row + j - r; for (int d = 0; d <= 2 * r; d++) v += kern[d] * q[d]; }
      else for (int d = -r; d <= r; d++) { const int jj = j + d; if (jj >= 0 && jj < N) v += kern[d + r] * row[jj]; }
      out[j] = v;
    }
  }
  for (int i = 0; i < N; i++) {
    double *out = P + (size_t)i * N;
    if (i >= r && i < N - r) {
      for (int j = 0; j < N; j++) out[j] = 0.0;
      for (int d = 0; d <= 2 * r; d++) {
        const double kd = kern[d], *q = st->tmp + (size_t)(i - r + d) * N;
        for (int j = 0; j < N; j++) out[j] += kd * q[j];
      }
    } else {
      for (int j = 0; j < N; j++) {
        double v = 0.0;
        for (int d = -r; d <= r; d++) { const int ii = i + d; if (ii >= 0 && ii < N) v += kern[d + r] * st->tmp[ii * N + j]; }
        out[j] = v;
      }
    }
  }
}
static double d2_mass(const D2St *st, const double *P, const int *disk, int nd, double x, double y) {
  int oi, oj;
  d2_cell(st, x, y, &oi, &oj);
  double m = 0.0;
  for (int q = 0; q < nd; q++) {
    const int i = st->c + oi + disk[2 * q], j = st->c + oj + disk[2 * q + 1];
    if (!d2_in(st, i, j)) continue;
    m += P[i * st->N + j];
  }
  return m;
}
static void d2_capture(Ctl *k, D2St *st, double tc) {  // a commanded click at tc
  double bx, by;
  d2_pos_at(k, st, tc, &bx, &by);
  int oi, oj;
  d2_cell(st, bx, by, &oi, &oj);
  double mv = 0.0;
  for (int q = 0; q < st->ndisk; q++) {
    const int i = st->c + oi + st->disk[2 * q], j = st->c + oj + st->disk[2 * q + 1];
    if (!d2_in(st, i, j)) continue;
    mv += st->P0[i * st->N + j]; st->P0[i * st->N + j] = 0.0;
  }
  st->tot0 -= mv;
  st->tot0 += d2_place(st, st->P0, bx, by, mv);
  if (st->model != 1) return;
  const double q0 = st->tot0 > 0.0 ? mv / st->tot0 : 0.0, bp = D2P(k, 11, 1.0);
  const int NN = st->N * st->N;
  if (!st->mode1) {  // blob 1 is re-placed with the target (probability q0)
    for (int i = 0; i < NN; i++) st->P1[i] *= 1.0 - q0;
    st->A *= 1.0 - q0;
    d2_place(st, st->P1, bx, by, q0 * st->tot1 * bp);
    st->A += q0 * st->tot1 * (1.0 - bp);
  } else {  // its own placement after a click on it (if the click was not a capture: probability 1 - q0)
    double m1 = 0.0;
    for (int q = 0; q < st->ndisk1; q++) {
      const int i = st->c + oi + st->disk1[2 * q], j = st->c + oj + st->disk1[2 * q + 1];
      if (!d2_in(st, i, j)) continue;
      const double mv1 = (1.0 - q0) * st->P1[i * st->N + j];
      m1 += mv1; st->P1[i * st->N + j] -= mv1;
    }
    d2_place(st, st->P1, bx, by, m1 * bp);
    st->A += m1 * (1.0 - bp);
  }
}
static void d2_process_clicks(Ctl *k, D2St *st, double t) {
  int w = 0;
  for (int q = 0; q < st->nclk; q++) {
    if (st->clk[q] <= t) d2_capture(k, st, st->clk[q]);
    else st->clk[w++] = st->clk[q];
  }
  st->nclk = w;
}
// q1: probability that blob 1 is within b2_rho (+ margin for the oracle) of the dot at the stroke time ta
static double d2_q1(Ctl *k, D2St *st, double ax, double ay, double ta) {
  if (st->model == 1) return st->tot1 > 0.0 ? d2_mass(st, st->P1, st->disk1, st->ndisk1, ax, ay) / st->tot1 : 0.0;
  if (st->model == 2) {
    CtlTruth tr;
    if (!ctl_truth(k, &tr)) return 0.0;
    if (!(tr.b1_exists && tr.b1_present && tr.b1_on)) return 0.0;
    double ex, ey;
    ctl_eff_pos(k, ctl_now(k), &ex, &ey);
    const double h = ta - ctl_now(k);
    const double bx = ex + tr.b1_dx + tr.b1_vx * h - ax, by = ey + tr.b1_dy + tr.b1_vy * h - ay;
    const double r = D2P(k, 13, 1.0) + D2P(k, 28, 0.0);
    return bx * bx + by * by <= r * r ? 1.0 : 0.0;
  }
  return 0.0;
}
static void d2_tap(Ctl *k, D2St *st, double t) {
  if (k->hot < 0) return;
  double ta = t + k->latency;
  const double lf = ctl_last_fire(k, k->hot) + k->t_ref_min;
  if (lf > ta) ta = lf;
  double ax, ay;
  ctl_eff_pos(k, ta, &ax, &ay);
  const double q0 = st->tot0 > 0.0 ? d2_mass(st, st->P0, st->disk, st->ndisk, ax, ay) / st->tot0 : 0.0;
  const double qt = D2P(k, 23, 0.3);
  if (q0 < qt || st->nclk >= 64 || !ctl_tap_would_click(k, 1.0, ta)) return;
  const double q1 = st->model ? d2_q1(k, st, ax, ay, ta) : 0.0;
  if (q0 < qt * (1.0 + D2P(k, 26, 4.0) * q1)) { k->diag[7] += 1.0; return; }
  const double before = k->diag[3];
  const double tf = ctl_fire(k, k->hot, 1.0, t);
  if (k->diag[3] > before && tf > 0) { st->clk[st->nclk++] = tf; k->diag[8] += q1; k->diag[10] += 1.0; k->diag[11] += q0; }
}
static void d2_steer(Ctl *k, D2St *st, double t) {
  const int N = st->N, N1 = N + 1;
  const double gain = D2P(k, 19, 1.0);
  if (gain <= 0.0) return;
  const int r = (int)lround(D2P(k, 8, 1.0) / st->h);
  const double ws = st->model == 1 ? D2P(k, 27, 0.0) : 0.0;
  const double w0 = 1.0 / (st->tot0 > 0.0 ? st->tot0 : 1.0), w1 = ws / (st->tot1 > 0.0 ? st->tot1 : 1.0);
  double *S = st->sat;
  for (int i = 0; i <= N; i++) S[i * N1] = 0.0;
  for (int j = 0; j <= N; j++) S[j] = 0.0;
  for (int i = 0; i < N; i++) {
    double row = 0.0;
    for (int j = 0; j < N; j++) {
      row += w0 * st->P0[i * N + j] - (ws != 0.0 ? w1 * st->P1[i * N + j] : 0.0);
      S[(i + 1) * N1 + (j + 1)] = S[i * N1 + (j + 1)] + row;
    }
  }
  double best = -1e300; int bi = st->c, bj = st->c;
  for (int i = 0; i < N; i++) {
    const int i0 = i - r < 0 ? 0 : i - r, i1 = i + r + 1 > N ? N : i + r + 1;
    for (int j = 0; j < N; j++) {
      const int j0 = j - r < 0 ? 0 : j - r, j1 = j + r + 1 > N ? N : j + r + 1;
      const double m = S[i1 * N1 + j1] - S[i0 * N1 + j1] - S[i1 * N1 + j0] + S[i0 * N1 + j0];
      if (m > best) { best = m; bi = i; bj = j; }
    }
  }
  if (best < D2P(k, 24, 0.0)) return;
  const double gx = st->gx0 + (bi - st->c) * st->h, gy = st->gy0 + (bj - st->c) * st->h;
  double fx, fy;
  ctl_eff_final(k, &fx, &fy);
  ctl_steer(k, gain * (gx - fx), gain * (gy - fy), t, D2P(k, 20, 1.0), D2P(k, 21, 0.5), D2P(k, 22, 0.15));
  k->diag[5] += best; k->diag[6] += 1.0;
}
static void d2_Etable(Ctl *k, D2St *st, double *E, double lam, double sig, double dt, int *emin, int *emax) {
  const int M = st->M, W2 = 2 * M + 1;
  for (int u = -M; u <= M; u++)
    for (int v = -M; v <= M; v++) {
      const double x = u * st->h, y = v * st->h;
      double l = 0.0;
      for (int s = 0; s < k->n_sense; s++) {
        const double dx = x - k->sense_xy[2 * s], dy = y - k->sense_xy[2 * s + 1];
        l += lam * exp(-(dx * dx + dy * dy) / (2.0 * sig * sig));
      }
      E[(u + M) * W2 + (v + M)] = exp(-dt * l);
    }
  *emin = M; *emax = -M;
  for (int u = -M; u <= M; u++)
    for (int v = -M; v <= M; v++)
      if (E[(u + M) * W2 + (v + M)] < 1.0 - 1e-15) {
        if (u < *emin) *emin = u;
        if (u > *emax) *emax = u;
        if (v < *emin) *emin = v;
        if (v > *emax) *emax = v;
      }
}
static int *d2_disk(double rho, double h, int *nd) {
  const int rr = (int)ceil(rho / h);
  int *d = calloc((size_t)2 * (2 * rr + 1) * (2 * rr + 1), sizeof(int));
  if (!d) return NULL;
  *nd = 0;
  for (int u = -rr; u <= rr; u++)
    for (int v = -rr; v <= rr; v++)
      if ((u * u + v * v) * h * h <= rho * rho) { d[2 * *nd] = u; d[2 * *nd + 1] = v; (*nd)++; }
  return d;
}
static int d2_init(Ctl *k) {
  if (k->np < 26) return -1;
  D2St *st = calloc(1, sizeof(D2St));
  if (!st) return -1;
  k->st = st;
  st->model = (int)D2P(k, 25, 1.0);
  st->has1 = D2P(k, 9, 0.0) > 0.0;
  if (!st->has1) st->model = 0;
  if (st->model == 2 && !k->priv) return -1;  // the oracle needs the privileged flag
  st->mode1 = D2P(k, 12, 0.0) != 0.0;
  st->h = D2P(k, 16, 0.2);
  const double W = D2P(k, 17, 7.0);
  st->c = (int)lround(W / st->h); st->N = 2 * st->c + 1; st->M = st->N - 1;
  const int N = st->N, M = st->M, W2 = 2 * M + 1;
  st->P0 = calloc((size_t)N * N, sizeof(double)); st->P1 = calloc((size_t)N * N, sizeof(double));
  st->tmp = calloc((size_t)N * N, sizeof(double)); st->sat = calloc((size_t)(N + 1) * (N + 1), sizeof(double));
  st->E0 = calloc((size_t)W2 * W2, sizeof(double)); st->E1 = calloc((size_t)W2 * W2, sizeof(double));
  st->ann = calloc((size_t)W2 * W2, sizeof(double));
  st->gx = calloc((size_t)N, sizeof(double)); st->gy = calloc((size_t)N, sizeof(double));
  st->disk = d2_disk(D2P(k, 8, 1.0), st->h, &st->ndisk);
  st->disk1 = d2_disk(D2P(k, 13, 1.0), st->h, &st->ndisk1);
  if (!st->P0 || !st->P1 || !st->tmp || !st->sat || !st->E0 || !st->E1 || !st->ann || !st->gx || !st->gy || !st->disk ||
      !st->disk1) return -1;
  const double sig = D2P(k, 0, 0.6), lam_s = D2P(k, 1, 2.0), lam_bg = D2P(k, 2, 0.05), dt = D2P(k, 15, 0.5);
  const double Rmin = D2P(k, 5, 2.0), Rmax = D2P(k, 6, 6.0);
  st->ratio = lam_s / (lam_bg > 1e-9 ? lam_bg : 1e-9);
  d2_Etable(k, st, st->E0, lam_s, sig, dt, &st->e0min, &st->e0max);
  if (st->model == 1) d2_Etable(k, st, st->E1, lam_s * D2P(k, 9, 0.0), D2P(k, 10, 1.5), dt, &st->e1min, &st->e1max);
  double sa = 0.0;
  for (int u = -M; u <= M; u++)
    for (int v = -M; v <= M; v++) {
      const double x = u * st->h, y = v * st->h, rr2 = sqrt(x * x + y * y);
      const double a = (rr2 >= Rmin && rr2 <= Rmax && rr2 > 0.0) ? 1.0 / rr2 : 0.0;
      st->ann[(u + M) * W2 + (v + M)] = a; sa += a;
    }
  if (sa > 0.0) for (int i = 0; i < W2 * W2; i++) st->ann[i] /= sa;
  st->amax = (int)ceil(Rmax / st->h) + 1;
  if (st->amax > M) st->amax = M;
  st->amin = -st->amax;
  st->tot0 = d2_place(st, st->P0, 0.0, 0.0, 1.0);
  if (st->model == 1) {
    const double bp = D2P(k, 11, 1.0);
    d2_place(st, st->P1, 0.0, 0.0, bp);
    st->A = 1.0 - bp;
    st->tot1 = 1.0;
  }
  d2_normalize(k, st);
  st->t_last = k->t0; st->t_blur = k->t0;
  d2_hist_push(k, st, k->t0);
  ctl_wake(k, k->t0 + dt);
  return 0;
}
// separable halo factors around screen point (px, py) for a window of radius rr cells around its grid cell
static void d2_factors(D2St *st, double px, double py, double sig, int ci, int cj, int rr) {
  const double inv = 1.0 / (2.0 * sig * sig);
  for (int d = -rr; d <= rr; d++) {
    const int i = ci + d, j = cj + d;
    if (i >= 0 && i < st->N) { const double x = st->gx0 + (i - st->c) * st->h - px; st->gx[i] = exp(-x * x * inv); }
    if (j >= 0 && j < st->N) { const double y = st->gy0 + (j - st->c) * st->h - py; st->gy[j] = exp(-y * y * inv); }
  }
}
static void d2_ping(Ctl *k, double t, int s) {
  D2St *st = k->st;
  d2_process_clicks(k, st, t);
  double bx, by;
  d2_pos_at(k, st, t - k->d_min, &bx, &by);
  const double px = bx + k->sense_xy[2 * s], py = by + k->sense_xy[2 * s + 1];
  const double sig = D2P(k, 0, 0.6), lam_s = D2P(k, 1, 2.0), lam_bg = D2P(k, 2, 0.05);
  const int N = st->N;
  int ci, cj;
  d2_cell(st, px, py, &ci, &cj);
  const int r0 = (int)ceil(4.0 * sig / st->h);
  d2_factors(st, px, py, sig, st->c + ci, st->c + cj, r0);
  const int i00 = st->c + ci - r0 < 0 ? 0 : st->c + ci - r0, i01 = st->c + ci + r0 >= N ? N - 1 : st->c + ci + r0;
  const int j00 = st->c + cj - r0 < 0 ? 0 : st->c + cj - r0, j01 = st->c + cj + r0 >= N ? N - 1 : st->c + cj + r0;
  // expected blob-0 rate at p (under the prior) and blob-1 rate
  double m0 = 0.0, m1 = 0.0;
  if (st->model == 1) {
    for (int i = i00; i <= i01; i++)
      for (int j = j00; j <= j01; j++) m0 += st->P0[i * N + j] * st->gx[i] * st->gy[j];
    m0 *= lam_s / (st->tot0 > 0.0 ? st->tot0 : 1.0);
    const double sig1 = D2P(k, 10, 1.5), lam1 = lam_s * D2P(k, 9, 0.0);
    const int r1 = (int)ceil(4.0 * sig1 / st->h);
    // blob-1 factors in separate buffers: reuse tmp rows (2N doubles needed)
    double *g1x = st->tmp, *g1y = st->tmp + N;
    const double inv = 1.0 / (2.0 * sig1 * sig1);
    const int i10 = st->c + ci - r1 < 0 ? 0 : st->c + ci - r1, i11 = st->c + ci + r1 >= N ? N - 1 : st->c + ci + r1;
    const int j10 = st->c + cj - r1 < 0 ? 0 : st->c + cj - r1, j11 = st->c + cj + r1 >= N ? N - 1 : st->c + cj + r1;
    for (int i = i10; i <= i11; i++) { const double x = st->gx0 + (i - st->c) * st->h - px; g1x[i] = exp(-x * x * inv); }
    for (int j = j10; j <= j11; j++) { const double y = st->gy0 + (j - st->c) * st->h - py; g1y[j] = exp(-y * y * inv); }
    for (int i = i10; i <= i11; i++) {
      double row = 0.0;
      for (int j = j10; j <= j11; j++) row += st->P1[i * N + j] * g1y[j];
      m1 += row * g1x[i];
    }
    m1 *= lam1 / (st->tot1 > 0.0 ? st->tot1 : 1.0);
    // blob-1 update: P1 *= 1 + lam1 halo1 / (lam_bg + m0)
    const double f1 = lam1 / (lam_bg + m0);
    for (int i = i10; i <= i11; i++)
      for (int j = j10; j <= j11; j++) {
        const double add = st->P1[i * N + j] * f1 * g1x[i] * g1y[j];
        st->P1[i * N + j] += add; st->tot1 += add;
      }
  } else if (st->model == 2) {
    CtlTruth tr;
    if (ctl_truth(k, &tr) && tr.b1_exists && tr.b1_present && tr.b1_on) {
      double ex, ey;
      ctl_eff_pos(k, ctl_now(k), &ex, &ey);
      // blob 1 at the read time (t - d_min), in the efference frame
      const double x1 = ex + tr.b1_dx - tr.b1_vx * k->d_min, y1 = ey + tr.b1_dy - tr.b1_vy * k->d_min;
      const double sig1 = D2P(k, 10, 1.5), dx = x1 - px, dy = y1 - py;
      m1 = lam_s * D2P(k, 9, 0.0) * exp(-(dx * dx + dy * dy) / (2.0 * sig1 * sig1));
    }
  }
  // blob-0 update: P0 *= 1 + lam0 halo0 / (lam_bg + m1)
  const double f0 = lam_s / (lam_bg + m1);
  for (int i = i00; i <= i01; i++)
    for (int j = j00; j <= j01; j++) {
      const double add = st->P0[i * N + j] * f0 * st->gx[i] * st->gy[j];
      st->P0[i * N + j] += add; st->tot0 += add;
    }
  if (st->tot0 > 1e200 || st->tot1 > 1e200) d2_normalize(k, st);
  d2_tap(k, st, t);
}
static void d2_noping(D2St *st, double *P, const double *E, int emin, int emax, int oi, int oj, double *tot) {
  const int N = st->N, M = st->M, W2 = 2 * M + 1;
  for (int u = emin; u <= emax; u++) {
    const int i = st->c + oi + u;
    if (i < 0 || i >= N) continue;
    for (int v = emin; v <= emax; v++) {
      const int j = st->c + oj + v;
      if (j < 0 || j >= N) continue;
      const double old = P[i * N + j], nw = old * E[(u + M) * W2 + (v + M)];
      P[i * N + j] = nw; *tot -= old - nw;
    }
  }
}
static void d2_wake(Ctl *k, double t) {
  D2St *st = k->st;
  const int N = st->N;
  const double dt = D2P(k, 15, 0.5);
  d2_process_clicks(k, st, t);
  double bx, by;
  d2_pos_at(k, st, 0.5 * (st->t_last + t), &bx, &by);
  int oi, oj;
  d2_cell(st, bx, by, &oi, &oj);
  d2_noping(st, st->P0, st->E0, st->e0min, st->e0max, oi, oj, &st->tot0);
  if (st->model == 1) d2_noping(st, st->P1, st->E1, st->e1min, st->e1max, oi, oj, &st->tot1);
  const double tr = D2P(k, 7, 50.0), hz = tr > 0.0 ? 1.0 - exp(-dt / tr) : 0.0;
  if (hz > 0.0) {
    const double f = hz / (1.0 - hz);
    double cx, cy;
    ctl_eff_pos(k, t, &cx, &cy);
    st->tot0 += d2_place(st, st->P0, cx, cy, f * st->tot0);
    if (st->model == 1) {
      const double bp = D2P(k, 11, 1.0), m = f * st->tot1;
      d2_place(st, st->P1, cx, cy, m * bp);
      st->A += m * (1.0 - bp);
      st->tot1 += m;
    }
  }
  const double vt = D2P(k, 3, 0.1), te1 = D2P(k, 29, 0.0) > 0.0 ? D2P(k, 29, 0.0) : D2P(k, 4, 5.0);
  st->var0 += vt * vt * D2P(k, 4, 5.0) * dt;
  st->var1 += vt * vt * te1 * dt;
  if (t - st->t_blur >= D2P(k, 18, 2.0)) {
    d2_blur1(st, st->P0, st->var0); st->var0 = 0.0;
    if (st->model == 1) { d2_blur1(st, st->P1, st->var1); }
    st->var1 = 0.0;
    st->t_blur = t;
  }
  d2_normalize(k, st);
  d2_recentre(k, st);
  st->t_last = t;
  d2_hist_push(k, st, t);
  d2_tap(k, st, t);
  d2_steer(k, st, t);
  (void)N;
  ctl_wake(k, t + dt);
}
static void d2_fini(Ctl *k) {
  D2St *st = k->st;
  if (st) {
    free(st->P0); free(st->P1); free(st->tmp); free(st->sat); free(st->E0); free(st->E1); free(st->ann);
    free(st->gx); free(st->gy); free(st->disk); free(st->disk1); free(st);
  }
}
static const CtlDef CTL_D2 = {1100, "D2 two-blob Bayes tracker", d2_init, d2_ping, d2_wake, d2_fini};
CTL_REGISTER(CTL_D2)
