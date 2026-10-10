// SWITCHING-family measuring sticks (scratch; never part of an organism).
//
// 1001  SW: two-hypothesis Bayes grid tracker. Information-matched in modes 0/1 (pings, own clock, own strokes and
//       the harness's efference model, footprint, parameters); privileged in mode 2 (reads ONLY the true flip time).
//   The target's position RELATIVE to the dot is tracked on two grids, one per motor-law hypothesis:
//     g = 0: strokes pull (normal law); g = 1: strokes push (flipped law). Each tick the raw efference displacement D
//     (all strokes taken as +1; the harness motor sign is never changed) moves grid g's frame by -s_g D (s_0 = +1,
//     s_1 = -1). Pings and no-ping evidence update both grids with the same halo likelihood; a per-grid background
//     rate lbg_g (fixed world rule; differs only in the cue world) enters through a per-grid log weight. Flips are
//     absorbing: mass moves from grid 0 to grid 1 at the world's hazard (prior P(flipped at t0) = p0, else a flip
//     with probability p_mid uniformly in [fa, fb] after t0). The motor-law posterior P1 = mass of grid 1 is thus a
//     Bayesian change-point detector driven by the CONSEQUENCES of the controller's own strokes (and the cue).
//   Approximation: grid 1 treats every stroke as pushed, including the drift of strokes made before the flip (tau_z).
//   Steering: under the MAP law (P1 > q_switch, with hysteresis), toward the rho_c box of largest mass on that grid.
//   Tap: when the posterior mass within rho_c of the dot at the stroke time (both grids, each with its own predicted
//   displacement) >= q_tap. Captures implied by commanded clicks re-place the mass under the dot (as C4).
//   Modes: 0 = never switches (grid 0 only; the no-switch twin of the same tracker), 1 = Bayes detection,
//          2 = privileged oracle switch (moves all mass to grid 1 at the true flip time; nothing else is read),
//          3 = clock switch (information-matched, no sensing: all mass to grid 1 at t - t0 >= (fa + fb) / 2).
// p: [0] sigma [1] lam_s [2] lbg0 [3] lbg1 [4] v_t [5] tau_eff [6] R_min [7] R_max [8] t_resp [9] rho_c
//    [10] p0 [11] p_mid [12] fa [13] fb [14] mode [15] dt [16] h [17] W [18] blur_every [19] gain [20] kmax
//    [21] min_align [22] tol [23] q_tap [24] q_switch [25] hyst [26] q_latch [27] haz_mult [28] haz_floor
//    [29] steer_min [31] act_style (0 tracker steer/tap; 1 reflex: a column's ping strokes its own act cell
//    (normal law) or the point-mirrored one (flipped law), centre pings tap with refractory 4 - the reflex with
//    the SAME law detector) [30] haz_back (telegraph worlds: flipped -> normal hazard; 0 = flips are absorbing)
// Mode 2 (privileged) reads only tr.flipped (the motor law now) and moves all mass onto that grid.
// diag: [5] first switch to 'flipped' (t; -1 never) [6] time steered flipped [7] latch time (-1 never)
//       [8] number of law changes [9] lost-track resets [10] last switch to 'flipped' (-1 never) [11] P1 at the end
//       [12] time steered flipped at t - t0 < fa (before any midlife flip can happen) [13] steering calls
//       [14] time steered NORMAL at t - t0 >= fb (after every midlife flip has happened)
#include "ctl_api.h"

#define SW_HIST 64
#define SW_MAXCLK 64
#define SW_KMAX 129
typedef struct {
  int N, c, M, ndisk, mode;
  double h;
  double *P[2], *tmp, *sat, *E, *ann;
  int *disk;
  int emin, emax, amax;
  double ux[2], uy[2], tot[2], lw[2], lbg[2], ratio[2];
  int act[2], latched, sgn;
  double tg, egx, egy, t_blur, var_acc, P1_last, t_flip_true, dtn;
  double clk[SW_MAXCLK]; int nclk;
  double ht[SW_HIST], hx[SW_HIST], hy[SW_HIST]; int hn, hh;
  int style, *col, *mir; double *lastp, last_tap;  // style 1: C0-like reflex acts, mapping by the inferred law
} SwSt;

static double SWP(const Ctl *k, int i, double d) { return i < k->np ? k->p[i] : d; }
static inline int sw_live(const SwSt *st, int g) { return st->act[g] && st->tot[g] > 0.0; }

static void sw_hist_push(Ctl *k, SwSt *st, double t) {
  double x, y;
  ctl_eff_pos(k, t, &x, &y);
  const int i = (st->hh + st->hn) % SW_HIST;
  st->ht[i] = t; st->hx[i] = x; st->hy[i] = y;
  if (st->hn < SW_HIST) st->hn++; else st->hh = (st->hh + 1) % SW_HIST;
}
static void sw_pos_at(Ctl *k, SwSt *st, double t, double *x, double *y) {  // raw efference position at any time
  if (t >= ctl_now(k)) { ctl_eff_pos(k, t, x, y); return; }
  double pt = ctl_now(k), px, py;
  ctl_eff_pos(k, pt, &px, &py);
  for (int q = st->hn - 1; q >= 0; q--) {
    const int i = (st->hh + q) % SW_HIST;
    if (st->ht[i] <= t) {
      const double w = pt > st->ht[i] ? (t - st->ht[i]) / (pt - st->ht[i]) : 0.0;
      *x = st->hx[i] + w * (px - st->hx[i]); *y = st->hy[i] + w * (py - st->hy[i]);
      return;
    }
    pt = st->ht[i]; px = st->hx[i]; py = st->hy[i];
  }
  *x = px; *y = py;
}
// grid g: cell (i, j) <-> r = ((i - c) h + ux, (j - c) h + uy). Move the frame so that every mass element's r
// changes by (dx, dy), then re-centre the sub-cell offsets into [-h/2, h/2] by integer array shifts.
static void sw_move(SwSt *st, int g, double dx, double dy) {
  st->ux[g] += dx; st->uy[g] += dy;
  const int si = (int)lround(st->ux[g] / st->h), sj = (int)lround(st->uy[g] / st->h);
  if (si == 0 && sj == 0) return;
  const int N = st->N;
  double *P = st->P[g], *T = st->tmp;
  double lost = 0.0;
  for (int i = 0; i < N; i++)
    for (int j = 0; j < N; j++) {
      const int oi = i - si, oj = j - sj;
      T[i * N + j] = (oi >= 0 && oj >= 0 && oi < N && oj < N) ? P[oi * N + oj] : 0.0;
    }
  for (int i = 0; i < N; i++)
    for (int j = 0; j < N; j++) {
      const int ni = i + si, nj = j + sj;
      if (!(ni >= 0 && nj >= 0 && ni < N && nj < N)) lost += P[i * N + j];
    }
  memcpy(P, T, sizeof(double) * N * N);
  st->tot[g] -= lost;
  if (st->tot[g] < 0.0) st->tot[g] = 0.0;
  st->ux[g] -= si * st->h; st->uy[g] -= sj * st->h;
}
static void sw_place(SwSt *st, int g, double rx, double ry, double mass) {  // mass on the placement annulus at r
  if (mass <= 0.0) return;
  const int N = st->N, M = st->M, W2 = 2 * M + 1;
  const int oi = (int)lround((rx - st->ux[g]) / st->h), oj = (int)lround((ry - st->uy[g]) / st->h);
  for (int u = -st->amax; u <= st->amax; u++) {
    const int i = st->c + oi + u;
    if (i < 0 || i >= N) continue;
    for (int v = -st->amax; v <= st->amax; v++) {
      const int j = st->c + oj + v;
      if (j < 0 || j >= N) continue;
      const double a = st->ann[(u + M) * W2 + (v + M)];
      if (a == 0.0) continue;
      st->P[g][i * N + j] += mass * a; st->tot[g] += mass * a;
    }
  }
}
static void sw_normalize(Ctl *k, SwSt *st) {
  const int NN = st->N * st->N;
  double s[2] = {0.0, 0.0}, lm = -INFINITY;
  for (int g = 0; g < 2; g++) {
    if (!st->act[g]) { st->tot[g] = 0.0; continue; }
    for (int i = 0; i < NN; i++) s[g] += st->P[g][i];
    if (s[g] > 0.0 && st->lw[g] > lm) lm = st->lw[g];
  }
  double S = 0.0;
  for (int g = 0; g < 2; g++) if (st->act[g] && s[g] > 0.0) S += s[g] * exp(st->lw[g] - lm);
  if (!(S > 1e-280) || !isfinite(S)) {  // lost track: restart from the placement prior with the last law belief
    double w1 = st->P1_last;
    if (!st->act[0]) w1 = 1.0;
    if (!st->act[1]) w1 = 0.0;
    for (int g = 0; g < 2; g++) {
      st->lw[g] = 0.0; st->tot[g] = 0.0;
      if (!st->act[g]) continue;
      memset(st->P[g], 0, sizeof(double) * NN);
      sw_place(st, g, 0.0, 0.0, g ? w1 : 1.0 - w1);
    }
    k->diag[9] += 1.0;
    return;
  }
  for (int g = 0; g < 2; g++) {
    if (!st->act[g] || !(s[g] > 0.0)) { st->tot[g] = 0.0; st->lw[g] = 0.0; continue; }
    const double f = exp(st->lw[g] - lm) / S;
    for (int i = 0; i < NN; i++) st->P[g][i] *= f;
    st->tot[g] = s[g] * f; st->lw[g] = 0.0;
  }
  const double z = st->tot[0] + st->tot[1];
  st->P1_last = z > 0.0 ? st->tot[1] / z : st->P1_last;
}
static double sw_disk_mass(const SwSt *st, int g, double rx, double ry) {
  const int N = st->N;
  const int oi = (int)lround((rx - st->ux[g]) / st->h), oj = (int)lround((ry - st->uy[g]) / st->h);
  double m = 0.0;
  for (int q = 0; q < st->ndisk; q++) {
    const int i = st->c + oi + st->disk[2 * q], j = st->c + oj + st->disk[2 * q + 1];
    if (i < 0 || j < 0 || i >= N || j >= N) continue;
    m += st->P[g][i * N + j];
  }
  return m;
}
static void sw_capture(Ctl *k, SwSt *st, double tc) {  // a commanded click at tc: mass under the dot is re-placed
  double bx, by;
  sw_pos_at(k, st, tc, &bx, &by);
  const int N = st->N;
  for (int g = 0; g < 2; g++) {
    if (!sw_live(st, g)) continue;
    const double sg = g ? -1.0 : 1.0, rx = sg * (bx - st->egx), ry = sg * (by - st->egy);
    const int oi = (int)lround((rx - st->ux[g]) / st->h), oj = (int)lround((ry - st->uy[g]) / st->h);
    double m = 0.0;
    for (int q = 0; q < st->ndisk; q++) {
      const int i = st->c + oi + st->disk[2 * q], j = st->c + oj + st->disk[2 * q + 1];
      if (i < 0 || j < 0 || i >= N || j >= N) continue;
      m += st->P[g][i * N + j]; st->P[g][i * N + j] = 0.0;
    }
    st->tot[g] -= m;
    sw_place(st, g, rx, ry, m);
  }
}
static void sw_process_clicks(Ctl *k, SwSt *st, double t) {
  int w = 0;
  for (int q = 0; q < st->nclk; q++) {
    if (st->clk[q] <= t) sw_capture(k, st, st->clk[q]);
    else st->clk[w++] = st->clk[q];
  }
  st->nclk = w;
}
static void sw_transfer(SwSt *st, int a, int b, double m) {  // move fraction m of grid a into grid b (same r)
  if (!(m > 0.0) || !st->act[a] || !st->act[b] || !(st->tot[a] > 0.0)) return;
  const int N = st->N;
  const int si = (int)lround((st->ux[a] - st->ux[b]) / st->h), sj = (int)lround((st->uy[a] - st->uy[b]) / st->h);
  double moved = 0.0;
  for (int i = 0; i < N; i++)
    for (int j = 0; j < N; j++) {
      const double v = st->P[a][i * N + j] * m;
      if (v == 0.0) continue;
      st->P[a][i * N + j] -= v;
      const int ni = i + si, nj = j + sj;
      if (ni >= 0 && nj >= 0 && ni < N && nj < N) { st->P[b][ni * N + nj] += v; st->tot[b] += v; }
      moved += v;
    }
  st->tot[a] -= moved;
  if (m >= 1.0) st->tot[a] = 0.0;
}
static void sw_to_flipped(SwSt *st, double m) { sw_transfer(st, 0, 1, m); }
static void sw_latch(Ctl *k, SwSt *st, double t) {
  if (st->latched) return;
  sw_to_flipped(st, 1.0);
  st->act[0] = 0; st->tot[0] = 0.0; st->latched = 1;
  k->diag[7] = t;
}
static void sw_priv(Ctl *k, SwSt *st, double t) {  // mode 2: the true motor law now is the only truth read
  if (st->mode != 2 && st->mode != 3) return;
  int f;
  if (st->mode == 3) {  // mode 3 (information-matched): clock switch at t - t0 >= (fa + fb) / 2, no sensing, no truth
    f = t - k->t0 >= 0.5 * (SWP(k, 12, 256.0) + SWP(k, 13, 768.0));
  } else {
    CtlTruth tr;
    if (!ctl_truth(k, &tr)) return;
    f = tr.flipped != 0;
  }
  if (st->tot[1 - f] > 0.0) {
    sw_transfer(st, 1 - f, f, 1.0);
    if (f && k->diag[7] < 0.0) k->diag[7] = t;
  }
  (void)t;
}
static void sw_blur(SwSt *st) {
  const double s = sqrt(st->var_acc) / st->h;
  st->var_acc = 0.0;
  if (s < 0.05) return;
  int r = (int)ceil(3.0 * s);
  if (r > 12) r = 12;
  double kern[25], ks = 0.0;
  for (int d = -r; d <= r; d++) { kern[d + r] = exp(-0.5 * d * d / (s * s)); ks += kern[d + r]; }
  for (int d = 0; d <= 2 * r; d++) kern[d] /= ks;
  const int N = st->N;
  for (int g = 0; g < 2; g++) {
    if (!sw_live(st, g)) continue;
    double *P = st->P[g];
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
      for (int j = 0; j < N; j++) out[j] = 0.0;
      for (int d = -r; d <= r; d++) {
        const int ii = i + d;
        if (ii < 0 || ii >= N) continue;
        const double kd = kern[d + r], *q = st->tmp + (size_t)ii * N;
        for (int j = 0; j < N; j++) out[j] += kd * q[j];
      }
    }
  }
}
static void sw_tap(Ctl *k, SwSt *st, double t) {
  if (k->hot < 0 || st->nclk >= SW_MAXCLK) return;
  double ta = t + k->latency;
  const double lf = ctl_last_fire(k, k->hot) + k->t_ref_min;
  if (lf > ta) ta = lf;
  if (!ctl_tap_would_click(k, 1.0, ta)) return;
  double ax, ay;
  ctl_eff_pos(k, ta, &ax, &ay);
  double lm = -INFINITY;
  for (int g = 0; g < 2; g++) if (sw_live(st, g) && st->lw[g] > lm) lm = st->lw[g];
  double q = 0.0, Z = 0.0;
  for (int g = 0; g < 2; g++) {
    if (!sw_live(st, g)) continue;
    const double w = exp(st->lw[g] - lm), sg = g ? -1.0 : 1.0;
    q += w * sw_disk_mass(st, g, sg * (ax - st->egx), sg * (ay - st->egy));
    Z += w * st->tot[g];
  }
  if (!(Z > 0.0)) return;
  if (q / Z >= SWP(k, 23, 0.3)) {
    const double before = k->diag[3];
    const double tf = ctl_fire(k, k->hot, 1.0, t);
    if (k->diag[3] > before && tf > 0) st->clk[st->nclk++] = tf;
  }
}
static void sw_steer(Ctl *k, SwSt *st, double t) {
  const int g = st->sgn;
  if (!sw_live(st, g)) return;
  const double gain = SWP(k, 19, 1.0);
  if (gain <= 0.0) return;
  const int N = st->N, N1 = N + 1, r = (int)lround(SWP(k, 9, 1.0) / st->h);
  double *S = st->sat, *P = st->P[g];
  for (int i = 0; i <= N; i++) S[i * N1] = 0.0;
  for (int j = 0; j <= N; j++) S[j] = 0.0;
  for (int i = 0; i < N; i++) {
    double row = 0.0;
    for (int j = 0; j < N; j++) { row += P[i * N + j]; S[(i + 1) * N1 + (j + 1)] = S[i * N1 + (j + 1)] + row; }
  }
  double best = -1.0; int bi = st->c, bj = st->c;
  for (int i = 0; i < N; i++) {
    const int i0 = i - r < 0 ? 0 : i - r, i1 = i + r + 1 > N ? N : i + r + 1;
    for (int j = 0; j < N; j++) {
      const int j0 = j - r < 0 ? 0 : j - r, j1 = j + r + 1 > N ? N : j + r + 1;
      const double m = S[i1 * N1 + j1] - S[i0 * N1 + j1] - S[i1 * N1 + j0] + S[i0 * N1 + j0];
      if (m > best) { best = m; bi = i; bj = j; }
    }
  }
  best /= st->tot[g];
  if (best < SWP(k, 29, 0.0)) return;
  const double rgx = (bi - st->c) * st->h + st->ux[g], rgy = (bj - st->c) * st->h + st->uy[g];
  double fx, fy;
  ctl_eff_final(k, &fx, &fy);
  const double sg = g ? -1.0 : 1.0;
  ctl_steer(k, gain * (sg * rgx - (fx - st->egx)), gain * (sg * rgy - (fy - st->egy)), t, SWP(k, 20, 1.0),
            SWP(k, 21, 0.5), SWP(k, 22, 0.15));
  k->diag[13] += 1.0;
}
static double sw_hazard(const Ctl *k, double t) {  // flip hazard per unit time at t (given not flipped yet)
  const double tau = t - k->t0, pm = SWP(k, 11, 0.0), fa = SWP(k, 12, 256.0), fb = SWP(k, 13, 768.0);
  double hz = SWP(k, 28, 0.0);
  if (pm > 0.0 && tau >= fa && tau < fb && fb > fa) {
    double S = 1.0 - pm * (tau - fa) / (fb - fa);
    if (S < 1e-6) S = 1e-6;
    hz += SWP(k, 27, 1.0) * pm / (fb - fa) / S;
  }
  return hz;
}
static int sw_init(Ctl *k) {
  if (k->np < 30) return -1;
  SwSt *st = calloc(1, sizeof(SwSt));
  if (!st) return -1;
  k->st = st;
  st->mode = (int)SWP(k, 14, 1.0);
  st->h = SWP(k, 16, 0.25);
  const double W = SWP(k, 17, 6.5);
  st->c = (int)lround(W / st->h); st->N = 2 * st->c + 1; st->M = st->N - 1;
  const int N = st->N, M = st->M, W2 = 2 * M + 1;
  for (int g = 0; g < 2; g++) st->P[g] = calloc((size_t)N * N, sizeof(double));
  st->tmp = calloc((size_t)N * N, sizeof(double)); st->sat = calloc((size_t)(N + 1) * (N + 1), sizeof(double));
  st->E = calloc((size_t)W2 * W2, sizeof(double)); st->ann = calloc((size_t)W2 * W2, sizeof(double));
  const double rho = SWP(k, 9, 1.0);
  const int rr = (int)ceil(rho / st->h);
  st->disk = calloc((size_t)2 * (2 * rr + 1) * (2 * rr + 1), sizeof(int));
  if (!st->P[0] || !st->P[1] || !st->tmp || !st->sat || !st->E || !st->ann || !st->disk) return -1;
  for (int u = -rr; u <= rr; u++)
    for (int v = -rr; v <= rr; v++)
      if ((u * u + v * v) * st->h * st->h <= rho * rho) { st->disk[2 * st->ndisk] = u; st->disk[2 * st->ndisk + 1] = v; st->ndisk++; }
  const double sig = SWP(k, 0, 0.6), lam_s = SWP(k, 1, 2.0);
  st->dtn = SWP(k, 15, 0.5);
  st->lbg[0] = SWP(k, 2, 0.05); st->lbg[1] = SWP(k, 3, 0.05);
  for (int g = 0; g < 2; g++) {
    if (st->lbg[g] < 1e-9) st->lbg[g] = 1e-9;
    st->ratio[g] = lam_s / st->lbg[g];
  }
  const double Rmin = SWP(k, 6, 2.0), Rmax = SWP(k, 7, 6.0);
  double sa = 0.0;
  st->emin = M; st->emax = -M;
  for (int u = -M; u <= M; u++)
    for (int v = -M; v <= M; v++) {
      const double x = u * st->h, y = v * st->h, r2 = sqrt(x * x + y * y);
      double lam = 0.0;
      for (int s = 0; s < k->n_sense; s++) {
        const double dx = x - k->sense_xy[2 * s], dy = y - k->sense_xy[2 * s + 1];
        lam += lam_s * exp(-(dx * dx + dy * dy) / (2.0 * sig * sig));
      }
      const double e = exp(-st->dtn * lam);
      st->E[(u + M) * W2 + (v + M)] = e;
      if (e < 1.0 - 1e-15) {
        if (u < st->emin) st->emin = u;
        if (u > st->emax) st->emax = u;
        if (v < st->emin) st->emin = v;
        if (v > st->emax) st->emax = v;
      }
      const double a = (r2 >= Rmin && r2 <= Rmax && r2 > 0.0) ? 1.0 / r2 : 0.0;
      st->ann[(u + M) * W2 + (v + M)] = a; sa += a;
    }
  if (sa > 0.0) for (int i = 0; i < W2 * W2; i++) st->ann[i] /= sa;
  st->amax = (int)ceil(Rmax / st->h) + 1;
  if (st->amax > M) st->amax = M;
  double p0 = SWP(k, 10, 0.0);
  if (p0 < 0.0) p0 = 0.0;
  if (p0 > 1.0) p0 = 1.0;
  if (st->mode == 0) { st->act[0] = 1; st->act[1] = 0; p0 = 0.0; }
  else if (st->mode == 2 || st->mode == 3) { st->act[0] = 1; st->act[1] = 1; p0 = 0.0; }
  else {
    st->act[0] = p0 < 1.0;
    st->act[1] = p0 > 0.0 || SWP(k, 11, 0.0) > 0.0 || SWP(k, 28, 0.0) > 0.0;
    if (SWP(k, 30, 0.0) > 0.0) st->act[0] = 1;  // telegraph: grid 0 can be re-entered
  }
  st->t_flip_true = INFINITY;
  st->style = (int)SWP(k, 31, 0.0);
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
  st->last_tap = -INFINITY;
  st->tg = k->t0; st->egx = 0.0; st->egy = 0.0; st->t_blur = k->t0;
  if (st->act[0]) sw_place(st, 0, 0.0, 0.0, 1.0 - p0);
  if (st->act[1]) sw_place(st, 1, 0.0, 0.0, p0);
  st->P1_last = p0;
  sw_normalize(k, st);
  st->sgn = st->P1_last > SWP(k, 24, 0.5) ? 1 : 0;
  if (!st->act[0]) st->sgn = 1;
  if (st->sgn) { k->diag[5] = k->t0; k->diag[10] = k->t0; } else { k->diag[5] = -1.0; k->diag[10] = -1.0; }
  if (p0 >= 1.0 && st->mode == 1 && !(SWP(k, 30, 0.0) > 0.0)) { st->latched = 1; k->diag[7] = k->t0; } else k->diag[7] = -1.0;
  sw_priv(k, st, k->t0);
  sw_hist_push(k, st, k->t0);
  ctl_wake(k, k->t0 + st->dtn);
  return 0;
}
static void sw_ping(Ctl *k, double t, int s) {
  SwSt *st = k->st;
  sw_process_clicks(k, st, t);
  sw_priv(k, st, t);
  double bx, by;
  sw_pos_at(k, st, t - k->d_min, &bx, &by);  // the screen was read at the candidate time, d_min before delivery
  const double dx = bx - st->egx, dy = by - st->egy, sig = SWP(k, 0, 0.6), i2 = 1.0 / (2.0 * sig * sig);
  int rr = (int)ceil(4.0 * sig / st->h);
  if (rr > (SW_KMAX - 1) / 2) rr = (SW_KMAX - 1) / 2;
  const int N = st->N;
  double fx[SW_KMAX], fy[SW_KMAX];
  for (int g = 0; g < 2; g++) {
    if (!sw_live(st, g)) continue;
    const double sg = g ? -1.0 : 1.0;
    // a cell's r at the read time is r - s_g (eff(t_read) - eff(t_grid)); the halo is centred on the sense cell
    const double cx = k->sense_xy[2 * s] + sg * dx, cy = k->sense_xy[2 * s + 1] + sg * dy;
    const int i0 = st->c + (int)lround((cx - st->ux[g]) / st->h), j0 = st->c + (int)lround((cy - st->uy[g]) / st->h);
    for (int d = -rr; d <= rr; d++) {
      const double x = (i0 + d - st->c) * st->h + st->ux[g] - cx, y = (j0 + d - st->c) * st->h + st->uy[g] - cy;
      fx[d + rr] = exp(-x * x * i2); fy[d + rr] = exp(-y * y * i2);
    }
    double add_tot = 0.0;
    const double ra = st->ratio[g];
    for (int di = -rr; di <= rr; di++) {
      const int i = i0 + di;
      if (i < 0 || i >= N) continue;
      double *row = st->P[g] + (size_t)i * N;
      const double ax = ra * fx[di + rr];
      for (int dj = -rr; dj <= rr; dj++) {
        const int j = j0 + dj;
        if (j < 0 || j >= N) continue;
        const double add = row[j] * ax * fy[dj + rr];
        row[j] += add; add_tot += add;
      }
    }
    st->tot[g] += add_tot;
    st->lw[g] += log(st->lbg[g]);
  }
  if (st->tot[0] > 1e200 || st->tot[1] > 1e200 || fabs(st->lw[0] - st->lw[1]) > 600.0) sw_normalize(k, st);
  if (st->style == 1) {
    if (s == k->centre) {
      if (k->hot >= 0 && t >= st->last_tap + 4.0 && st->nclk < SW_MAXCLK) {
        st->last_tap = t;
        const double before = k->diag[3], tf = ctl_fire(k, k->hot, 1.0, t);
        if (k->diag[3] > before && tf > 0) st->clk[st->nclk++] = tf;
      }
      return;
    }
    const int a = st->sgn ? st->mir[s] : st->col[s];
    if (a < 0 || a == k->hot || t < st->lastp[s] + 0.5) return;
    st->lastp[s] = t;
    ctl_fire(k, a, 1.0, t);
    return;
  }
  sw_tap(k, st, t);
}
static void sw_wake(Ctl *k, double t) {
  SwSt *st = k->st;
  sw_process_clicks(k, st, t);
  sw_priv(k, st, t);
  const double dt = t - st->tg;
  const int N = st->N, M = st->M, W2 = 2 * M + 1;
  double ex, ey;
  ctl_eff_pos(k, t, &ex, &ey);
  const double Dx = ex - st->egx, Dy = ey - st->egy;
  for (int g = 0; g < 2; g++) {
    if (!sw_live(st, g)) continue;
    const double sg = g ? -1.0 : 1.0;
    sw_move(st, g, -0.5 * sg * Dx, -0.5 * sg * Dy);
    // no-ping evidence of the tick (target halo part; the background part is the per-grid log weight)
    double rem = 0.0;
    double f = dt / st->dtn;
    if (fabs(f - 1.0) < 1e-6) f = 1.0;  // wakes come every dtn (up to rounding): use the template as is
    for (int u = st->emin; u <= st->emax; u++) {
      const int i = st->c + u;
      if (i < 0 || i >= N) continue;
      for (int v = st->emin; v <= st->emax; v++) {
        const int j = st->c + v;
        if (j < 0 || j >= N) continue;
        double e = st->E[(u + M) * W2 + (v + M)];
        if (f != 1.0) e = pow(e, f);
        const double old = st->P[g][i * N + j];
        st->P[g][i * N + j] = old * e; rem += old - old * e;
      }
    }
    st->tot[g] -= rem;
    st->lw[g] -= dt * k->n_sense * st->lbg[g];
    sw_move(st, g, -0.5 * sg * Dx, -0.5 * sg * Dy);
  }
  st->tg = t; st->egx = ex; st->egy = ey;
  sw_normalize(k, st);
  // the flip process (absorbing)
  if (st->mode == 1 && !st->latched && st->act[1]) {
    const double m = 1.0 - exp(-sw_hazard(k, t) * dt), hb = SWP(k, 30, 0.0);
    const double m10 = hb > 0.0 ? 1.0 - exp(-hb * dt) : 0.0;  // telegraph: flipped -> normal at rate haz_back
    // sequential exchange (error O(m * m10), negligible at these rates)
    if (m10 > 0.0) sw_transfer(st, 1, 0, m10);
    sw_to_flipped(st, m);
  }
  // timer re-placement around the dot
  const double tr = SWP(k, 8, 50.0), hz = tr > 0.0 ? 1.0 - exp(-dt / tr) : 0.0;
  if (hz > 0.0) {
    const double fr = hz / (1.0 - hz);
    const double m0 = st->tot[0], m1 = st->tot[1];
    if (sw_live(st, 0)) sw_place(st, 0, 0.0, 0.0, fr * m0);
    if (sw_live(st, 1)) sw_place(st, 1, 0.0, 0.0, fr * m1);
  }
  const double vt = SWP(k, 4, 0.1);
  st->var_acc += vt * vt * SWP(k, 5, 5.0) * dt;
  if (t - st->t_blur >= SWP(k, 18, 2.0)) { sw_blur(st); st->t_blur = t; }
  sw_normalize(k, st);
  // the motor law to steer by
  const double P1 = st->act[0] ? st->tot[1] / (st->tot[0] + st->tot[1] > 0 ? st->tot[0] + st->tot[1] : 1.0) : 1.0;
  if (st->mode == 1 && !st->latched && P1 >= SWP(k, 26, 2.0)) sw_latch(k, st, t);
  int ns;
  if (st->latched || !st->act[0]) ns = 1;
  else if (st->mode == 1) ns = st->sgn ? (P1 > SWP(k, 24, 0.5) - SWP(k, 25, 0.0)) : (P1 > SWP(k, 24, 0.5));
  else if (st->mode == 2 || st->mode == 3) ns = st->tot[1] > st->tot[0];
  else ns = 0;
  const double tau = t - k->t0;
  if (st->sgn) { k->diag[6] += dt; if (tau - dt < SWP(k, 12, 256.0)) k->diag[12] += dt; }
  else if (tau - dt >= SWP(k, 13, 768.0)) k->diag[14] += dt;
  if (ns != st->sgn) {
    k->diag[8] += 1.0;
    if (ns) { if (k->diag[5] < 0.0) k->diag[5] = t; k->diag[10] = t; }
  }
  st->sgn = ns;
  sw_hist_push(k, st, t);
  if (st->style == 0) { sw_tap(k, st, t); sw_steer(k, st, t); }
  ctl_wake(k, t + st->dtn);
}
static void sw_fini(Ctl *k) {
  SwSt *st = k->st;
  if (!st) return;
  const double z = st->tot[0] + st->tot[1];
  k->diag[11] = st->act[0] ? (z > 0 ? st->tot[1] / z : st->P1_last) : 1.0;
  free(st->col); free(st->mir); free(st->lastp); free(st->P[0]); free(st->P[1]); free(st->tmp); free(st->sat); free(st->E); free(st->ann); free(st->disk); free(st);
}
static const CtlDef CTL_SW = {1001, "SW two-hypothesis switch tracker", sw_init, sw_ping, sw_wake, sw_fini};
CTL_REGISTER(CTL_SW)

// 1002  C0M: the central reflex with a selectable motor mapping (information-matched). Each sense column's ping
//   strokes the act cell of the same column (map 0, as C0) or of the point-mirrored column (-a, -b) (map 1: under the
//   flipped push law the opposite rim cell pushes the body toward the sensed side); centre pings tap.
// p: [0] kappa_m (1) [1] refr_m (0.5) [2] kappa_tap (1) [3] refr_tap (4) [4] map (0 / 1) [5] motors (1: on, 0: tap only)
typedef struct { int *col; double *last; double last_tap; } C0MSt;
static int c0m_init(Ctl *k) {
  C0MSt *st = calloc(1, sizeof(C0MSt));
  if (!st) return -1;
  st->col = malloc(sizeof(int) * (k->n_sense + 1)); st->last = malloc(sizeof(double) * (k->n_sense + 1));
  if (!st->col || !st->last) return -1;
  const int mir = SWP(k, 4, 0.0) != 0.0;
  for (int s = 0; s < k->n_sense; s++) {
    st->col[s] = -1; st->last[s] = -INFINITY;
    const int a0 = mir ? -k->sense_ab[2 * s] : k->sense_ab[2 * s], b0 = mir ? -k->sense_ab[2 * s + 1] : k->sense_ab[2 * s + 1];
    for (int a = 0; a < k->n_act; a++)
      if (k->act_ab[2 * a] == a0 && k->act_ab[2 * a + 1] == b0) st->col[s] = a;
  }
  st->last_tap = -INFINITY;
  k->st = st;
  return 0;
}
static void c0m_ping(Ctl *k, double t, int s) {
  C0MSt *st = k->st;
  if (s == k->centre) {
    if (t >= st->last_tap + SWP(k, 3, 4.0) && k->hot >= 0) { st->last_tap = t; ctl_fire(k, k->hot, SWP(k, 2, 1.0), t); }
    return;
  }
  if (SWP(k, 5, 1.0) == 0.0) return;
  const int a = st->col[s];
  if (a < 0 || a == k->hot) return;
  if (t < st->last[s] + SWP(k, 1, 0.5)) return;
  st->last[s] = t;
  ctl_fire(k, a, SWP(k, 0, 1.0), t);
}
static void c0m_fini(Ctl *k) {
  C0MSt *st = k->st;
  if (st) { free(st->col); free(st->last); free(st); }
}
static const CtlDef CTL_C0M = {1002, "C0M central reflex, selectable mapping", c0m_init, c0m_ping, NULL, c0m_fini};
CTL_REGISTER(CTL_C0M)
