
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
// =========================================================================================== 5: C4 Bayes grid tracker
// Information-matched, with a world MODEL: it sees only pings, its clock and its own actions, but its parameters hold
// the world's fixed rules (halo width and rates, target speed, placement law, timer, capture radius, blink rates) -
// constants of the world family that any tuned or evolved controller could absorb, never per-life hidden state.
// It keeps a posterior over the target's position (efference frame) on a grid, split into visible / dark mass:
//   per ping at sense cell s (screen read d_min before delivery):  P_vis *= 1 + (lam_s / lam_bg) halo(x - p_s)
//   per tick dt (no ping elsewhere):                                P_vis *= exp(-dt sum_s lam_s halo(x - p_s))
//   motion: Gaussian blur, per-axis variance v_t^2 tau_eff per unit time (applied every blur_every)
//   timer:  mass (1 - e^{-dt / t_resp}) re-placed on the placement annulus (R_min..R_max, density ~ 1/r) around the dot
//   blink:  vis -> dark at rate 1/blink_on, dark -> vis at 1/blink_off (blink_off < 0: FLASH, dark until re-placed)
//   after each commanded click at t_c: the mass within rho_c of the dot is re-placed around the dot (a capture)
// Tap: when the posterior mass within rho_c of the dot's commanded position at the stroke time is >= q_tap.
// Steer: toward the cell with the largest mass in a (2r+1)^2 box (r = rho_c / h), via a summed-area table.
// p: [0] sigma [1] lam_s [2] lam_bg [3] v_t [4] tau_eff [5] R_min [6] R_max [7] t_resp [8] rho_c [9] blink_on
//    [10] blink_off [11] dt (0.5) [12] h (0.2) [13] W (7.0) [14] blur_every (2.0) [15] gain (1.0) [16] kmax (1.0)
//    [17] min_align (0.5) [18] tol (0.15) [19] q_tap (0.3) [20] steer_min (0.0: min box mass to steer)
// (harness.bayes_params(world) fills [0]-[10] from the world spec.)
#define V4_HIST 64
typedef struct {
  int N, c, M, nm, ndisk, blink, flash;
  double h, gx0, gy0, var_acc, t_blur, t_last;
  double *Pv, *Pd, *tmp, *sat, *E, *ann, ratio, sig4, tot;  // tot: current total mass (Pv + Pd)
  int amin, amax, emin, emax;     // offset supports: annulus template, no-ping factor E (E < 1 only inside)
  int *disk;                      // offsets (du, dv) within rho_c
  double clk[64]; int nclk;       // pending commanded click times
  double ht[V4_HIST], hx[V4_HIST], hy[V4_HIST]; int hn, hh;  // efference history (t, x, y)
} V4St;
static inline int v4_in(const V4St *st, int i, int j) { return i >= 0 && j >= 0 && i < st->N && j < st->N; }
static void v4_hist_push(Ctl *k, V4St *st, double t) {
  double x, y;
  ctl_eff_pos(k, t, &x, &y);
  const int i = (st->hh + st->hn) % V4_HIST;
  st->ht[i] = t; st->hx[i] = x; st->hy[i] = y;
  if (st->hn < V4_HIST) st->hn++; else st->hh = (st->hh + 1) % V4_HIST;
}
static void v4_pos_at(Ctl *k, V4St *st, double t, double *x, double *y) {  // efference position at a past time t
  if (t >= ctl_now(k)) { ctl_eff_pos(k, t, x, y); return; }
  double pt = ctl_now(k), px, py;
  ctl_eff_pos(k, pt, &px, &py);
  for (int q = st->hn - 1; q >= 0; q--) {
    const int i = (st->hh + q) % V4_HIST;
    if (st->ht[i] <= t) {
      const double w = pt > st->ht[i] ? (t - st->ht[i]) / (pt - st->ht[i]) : 0.0;
      *x = st->hx[i] + w * (px - st->hx[i]); *y = st->hy[i] + w * (py - st->hy[i]);
      return;
    }
    pt = st->ht[i]; px = st->hx[i]; py = st->hy[i];
  }
  *x = px; *y = py;
}
static void v4_body_cell(const V4St *st, double bx, double by, int *oi, int *oj) {
  *oi = (int)lround((bx - st->gx0) / st->h); *oj = (int)lround((by - st->gy0) / st->h);
}
static void v4_place(V4St *st, double bx, double by, double mv, double md) {  // add placement mass around (bx, by)
  int oi, oj;
  v4_body_cell(st, bx, by, &oi, &oj);
  const int M = st->M, W2 = 2 * M + 1;
  for (int u = st->amin; u <= st->amax; u++) {
    const int i = st->c + oi + u;
    if (i < 0 || i >= st->N) continue;
    for (int v = st->amin; v <= st->amax; v++) {
      const int j = st->c + oj + v;
      if (j < 0 || j >= st->N) continue;
      const double a = st->ann[(u + M) * W2 + (v + M)];
      if (a == 0.0) continue;
      st->Pv[i * st->N + j] += mv * a; st->tot += mv * a;
      if (st->blink) { st->Pd[i * st->N + j] += md * a; st->tot += md * a; }
    }
  }
}
static void v4_normalize(Ctl *k, V4St *st) {
  double s = 0.0;
  const int NN = st->N * st->N;
  for (int i = 0; i < NN; i++) s += st->Pv[i] + (st->blink ? st->Pd[i] : 0.0);
  if (!(s > 1e-280) || !isfinite(s)) {  // lost track: restart from the placement prior around the dot
    memset(st->Pv, 0, sizeof(double) * NN);
    if (st->blink) memset(st->Pd, 0, sizeof(double) * NN);
    double bx, by;
    ctl_eff_pos(k, ctl_now(k), &bx, &by);
    st->tot = 0.0;
    v4_place(st, bx, by, 1.0, 0.0);
    k->diag[9] += 1.0;
    return;
  }
  const double r = 1.0 / s;
  for (int i = 0; i < NN; i++) { st->Pv[i] *= r; if (st->blink) st->Pd[i] *= r; }
  st->tot = 1.0;
}
static void v4_recentre(Ctl *k, V4St *st) {
  double bx, by;
  ctl_eff_pos(k, ctl_now(k), &bx, &by);
  int oi, oj;
  v4_body_cell(st, bx, by, &oi, &oj);
  if (abs(oi) <= st->N / 6 && abs(oj) <= st->N / 6) return;
  const int N = st->N;
  for (int g = 0; g < 1 + st->blink; g++) {
    double *P = g ? st->Pd : st->Pv;
    for (int i = 0; i < N; i++)
      for (int j = 0; j < N; j++) {
        const int si = i + oi, sj = j + oj;
        st->tmp[i * N + j] = v4_in(st, si, sj) ? P[si * N + sj] : 0.0;
      }
    memcpy(P, st->tmp, sizeof(double) * N * N);
  }
  st->gx0 += oi * st->h; st->gy0 += oj * st->h;
  v4_normalize(k, st);  // mass shifted off the grid is dropped
}
static void v4_blur(V4St *st) {
  const double s = sqrt(st->var_acc) / st->h;
  st->var_acc = 0.0;
  if (s < 0.05) return;
  int r = (int)ceil(3.0 * s);
  if (r > 12) r = 12;
  double kern[25], ks = 0.0;
  for (int d = -r; d <= r; d++) { kern[d + r] = exp(-0.5 * d * d / (s * s)); ks += kern[d + r]; }
  for (int d = 0; d <= 2 * r; d++) kern[d] /= ks;
  const int N = st->N;
  for (int g = 0; g < 1 + st->blink; g++) {
    double *P = g ? st->Pd : st->Pv;
    for (int i = 0; i < N; i++) {  // along j (interior without bounds checks)
      const double *row = P + (size_t)i * N;
      double *out = st->tmp + (size_t)i * N;
      for (int j = 0; j < N; j++) {
        double v = 0.0;
        if (j >= r && j < N - r) { const double *q = row + j - r; for (int d = 0; d <= 2 * r; d++) v += kern[d] * q[d]; }
        else for (int d = -r; d <= r; d++) { const int jj = j + d; if (jj >= 0 && jj < N) v += kern[d + r] * row[jj]; }
        out[j] = v;
      }
    }
    for (int i = 0; i < N; i++) {  // along i
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
}
static void v4_capture(Ctl *k, V4St *st, double tc) {  // a commanded click at tc: mass under the dot is re-placed
  double bx, by;
  v4_pos_at(k, st, tc, &bx, &by);
  int oi, oj;
  v4_body_cell(st, bx, by, &oi, &oj);
  double mv = 0.0, md = 0.0;
  for (int q = 0; q < st->ndisk; q++) {
    const int i = st->c + oi + st->disk[2 * q], j = st->c + oj + st->disk[2 * q + 1];
    if (!v4_in(st, i, j)) continue;
    mv += st->Pv[i * st->N + j]; st->Pv[i * st->N + j] = 0.0;
    if (st->blink) { md += st->Pd[i * st->N + j]; st->Pd[i * st->N + j] = 0.0; }
  }
  st->tot -= mv + md;
  if (st->flash) v4_place(st, bx, by, mv + md, 0.0);
  else v4_place(st, bx, by, mv, md);
}
static double v4_mass_at(const V4St *st, double x, double y) {  // posterior mass within rho_c of (x, y)
  int oi, oj;
  v4_body_cell(st, x, y, &oi, &oj);
  double m = 0.0;
  for (int q = 0; q < st->ndisk; q++) {
    const int i = st->c + oi + st->disk[2 * q], j = st->c + oj + st->disk[2 * q + 1];
    if (!v4_in(st, i, j)) continue;
    m += st->Pv[i * st->N + j] + (st->blink ? st->Pd[i * st->N + j] : 0.0);
  }
  return st->tot > 0.0 ? m / st->tot : 0.0;
}
static void v4_process_clicks(Ctl *k, V4St *st, double t) {
  int w = 0;
  for (int q = 0; q < st->nclk; q++) {
    if (st->clk[q] <= t) v4_capture(k, st, st->clk[q]);
    else st->clk[w++] = st->clk[q];
  }
  st->nclk = w;
}
static void v4_tap(Ctl *k, V4St *st, double t) {
  if (k->hot >= 0 && P_(k, 25, 0.0) != 1.0) {
    double ta = t + k->latency;
    const double lf = ctl_last_fire(k, k->hot) + k->t_ref_min;
    if (lf > ta) ta = lf;
    double ax, ay;
    ctl_eff_pos(k, ta, &ax, &ay);
    const double q = v4_mass_at(st, ax, ay);
    if (q >= P_(k, 19, 0.3) && ctl_tap_would_click(k, 1.0, ta) && st->nclk < 64) {
      const double before = k->diag[3];
      const double tf = ctl_fire(k, k->hot, 1.0, t);
      if (k->diag[3] > before && tf > 0) st->clk[st->nclk++] = tf;
    }
  }
}
static void v4_steer(Ctl *k, V4St *st, double t) {
  const int N = st->N;
  const double gain = P_(k, 15, 1.0);
  if (gain <= 0.0 || P_(k, 24, 0.0) == 1.0) return;
  const int r = (int)lround(P_(k, 8, 1.0) / st->h), N1 = N + 1;
  double *S = st->sat;
  for (int i = 0; i <= N; i++) S[i * N1] = 0.0;
  for (int j = 0; j <= N; j++) S[j] = 0.0;
  for (int i = 0; i < N; i++) {
    double row = 0.0;
    for (int j = 0; j < N; j++) {
      row += st->Pv[i * N + j] + (st->blink ? st->Pd[i * N + j] : 0.0);
      S[(i + 1) * N1 + (j + 1)] = S[i * N1 + (j + 1)] + row;
    }
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
  best /= st->tot > 0.0 ? st->tot : 1.0;
  if (best < P_(k, 20, 0.0)) return;
  const double gx = st->gx0 + (bi - st->c) * st->h, gy = st->gy0 + (bj - st->c) * st->h;
  double fx, fy;
  ctl_eff_final(k, &fx, &fy);
  ctl_steer(k, gain * (gx - fx), gain * (gy - fy), t, P_(k, 16, 1.0), P_(k, 17, 0.5), P_(k, 18, 0.15));
  k->diag[5] += best; k->diag[6] += 1.0;
}
static int v4_init(Ctl *k) {
  if (k->np < 21) return -1;
  V4St *st = calloc(1, sizeof(V4St));
  if (!st) return -1;
  k->st = st;
  st->h = P_(k, 12, 0.2);
  const double W = P_(k, 13, 7.0);
  st->c = (int)lround(W / st->h); st->N = 2 * st->c + 1; st->M = st->N - 1;
  const int N = st->N, M = st->M, W2 = 2 * M + 1;
  st->blink = P_(k, 9, 0.0) > 0.0 && P_(k, 10, 0.0) != 0.0;
  st->flash = st->blink && P_(k, 10, 0.0) < 0.0;
  st->Pv = calloc((size_t)N * N, sizeof(double)); st->Pd = calloc((size_t)N * N, sizeof(double));
  st->tmp = calloc((size_t)N * N, sizeof(double)); st->sat = calloc((size_t)(N + 1) * (N + 1), sizeof(double));
  st->E = calloc((size_t)W2 * W2, sizeof(double)); st->ann = calloc((size_t)W2 * W2, sizeof(double));
  const double rho = P_(k, 8, 1.0);
  const int rr = (int)ceil(rho / st->h);
  st->disk = calloc((size_t)2 * (2 * rr + 1) * (2 * rr + 1), sizeof(int));
  if (!st->Pv || !st->Pd || !st->tmp || !st->sat || !st->E || !st->ann || !st->disk) return -1;
  for (int u = -rr; u <= rr; u++)
    for (int v = -rr; v <= rr; v++)
      if ((u * u + v * v) * st->h * st->h <= rho * rho) { st->disk[2 * st->ndisk] = u; st->disk[2 * st->ndisk + 1] = v; st->ndisk++; }
  const double sig = P_(k, 0, 0.6), lam_s = P_(k, 1, 2.0), lam_bg = P_(k, 2, 0.05), dt = P_(k, 11, 0.25);
  const double Rmin = P_(k, 5, 2.0), Rmax = P_(k, 6, 6.0);
  st->ratio = lam_s / (lam_bg > 1e-9 ? lam_bg : 1e-9); st->sig4 = 4.0 * sig;
  double sa = 0.0;
  for (int u = -M; u <= M; u++)
    for (int v = -M; v <= M; v++) {
      const double x = u * st->h, y = v * st->h, rr2 = sqrt(x * x + y * y);
      double lam = 0.0;
      for (int s = 0; s < k->n_sense; s++) {
        const double dx = x - k->sense_xy[2 * s], dy = y - k->sense_xy[2 * s + 1];
        lam += lam_s * exp(-(dx * dx + dy * dy) / (2.0 * sig * sig));
      }
      st->E[(u + M) * W2 + (v + M)] = exp(-dt * lam);
      const double a = (rr2 >= Rmin && rr2 <= Rmax && rr2 > 0.0) ? 1.0 / rr2 : 0.0;
      st->ann[(u + M) * W2 + (v + M)] = a; sa += a;
    }
  if (sa > 0.0) for (int i = 0; i < W2 * W2; i++) st->ann[i] /= sa;
  st->emin = M; st->emax = -M;
  for (int u = -M; u <= M; u++)
    for (int v = -M; v <= M; v++)
      if (st->E[(u + M) * W2 + (v + M)] < 1.0 - 1e-15) {
        if (u < st->emin) st->emin = u;
        if (u > st->emax) st->emax = u;
        if (v < st->emin) st->emin = v;
        if (v > st->emax) st->emax = v;
      }
  st->amax = (int)ceil(Rmax / st->h) + 1;
  if (st->amax > M) st->amax = M;
  st->amin = -st->amax;
  st->gx0 = 0.0; st->gy0 = 0.0;
  v4_place(st, 0.0, 0.0, 1.0, 0.0);  // the target is placed (visible) around the dot at t0
  v4_normalize(k, st);
  st->t_last = k->t0; st->t_blur = k->t0;
  v4_hist_push(k, st, k->t0);
  ctl_wake(k, k->t0 + dt);
  return 0;
}
static void v4_ping(Ctl *k, double t, int s) {
  V4St *st = k->st;
  if (v4h_log_on) v4h_log(0, t, (double)s, 0, 0, 0);
  if (P_(k, 21, 0.0) > 0.0) { if (t - v4h_lastping(k)[s] < P_(k, 21, 0.0)) return; v4h_lastping(k)[s] = t; }
  if (P_(k, 24, 0.0) == 1.0) v4h_c0_steer(k, t, s);
  if (P_(k, 25, 0.0) == 1.0 && s == k->centre) v4h_c0_tap(k, t);
  v4_process_clicks(k, st, t);
  double bx, by;
  v4_pos_at(k, st, t - k->d_min, &bx, &by);  // the screen was read at the candidate time, d_min before delivery
  const double px = bx + k->sense_xy[2 * s], py = by + k->sense_xy[2 * s + 1], sig = P_(k, 0, 0.6);
  const int N = st->N, rr = (int)ceil(st->sig4 / st->h);
  int oi, oj;
  v4_body_cell(st, px, py, &oi, &oj);
  for (int i = st->c + oi - rr; i <= st->c + oi + rr; i++)
    for (int j = st->c + oj - rr; j <= st->c + oj + rr; j++) {
      if (!v4_in(st, i, j)) continue;
      const double x = st->gx0 + (i - st->c) * st->h - px, y = st->gy0 + (j - st->c) * st->h - py;
      const double add = st->Pv[i * N + j] * st->ratio * exp(-(x * x + y * y) / (2.0 * sig * sig));
      st->Pv[i * N + j] += add; st->tot += add;
    }
  if (st->tot > 1e200) v4_normalize(k, st);
  v4_tap(k, st, t);
}
static void v4_wake(Ctl *k, double t) {
  V4St *st = k->st;
  const int N = st->N, M = st->M, W2 = 2 * M + 1;
  const double dt = P_(k, 11, 0.25);
  v4_process_clicks(k, st, t);
  // no-ping evidence of the last tick at the mid-interval body position
  double bx, by;
  v4_pos_at(k, st, 0.5 * (st->t_last + t), &bx, &by);
  int oi, oj;
  v4_body_cell(st, bx, by, &oi, &oj);
  if (P_(k, 22, 0.0) == 0.0)
  for (int u = st->emin; u <= st->emax; u++) {
    const int i = st->c + oi + u;
    if (i < 0 || i >= N) continue;
    for (int v = st->emin; v <= st->emax; v++) {
      const int j = st->c + oj + v;
      if (j < 0 || j >= N) continue;
      const double old = st->Pv[i * N + j], nw = old * st->E[(u + M) * W2 + (v + M)];
      st->Pv[i * N + j] = nw; st->tot -= old - nw;
    }
  }
  // visibility transitions and the timer
  const double tr = P_(k, 7, 50.0), hz = tr > 0.0 ? 1.0 - exp(-dt / tr) : 0.0;
  if (st->blink) {
    const double a = 1.0 - exp(-dt / P_(k, 9, 20.0)), b = st->flash ? 0.0 : 1.0 - exp(-dt / P_(k, 10, 20.0));
    for (int i = 0; i < N * N; i++) {
      const double v = st->Pv[i], d = st->Pd[i];
      st->Pv[i] = (1.0 - a) * v + b * d; st->Pd[i] = a * v + (1.0 - b) * d;
    }
  }
  if (hz > 0.0) {  // re-placement by the timer: P <- (1 - hz) P + hz m ann, as P + hz / (1 - hz) m ann (normalized below)
    double md = 0.0;
    if (st->blink) for (int i = 0; i < N * N; i++) md += st->Pd[i];
    const double mv = st->tot - md;
    const double f = hz / (1.0 - hz);
    double cx, cy;
    ctl_eff_pos(k, t, &cx, &cy);
    if (st->flash) v4_place(st, cx, cy, f * (mv + md), 0.0);
    else v4_place(st, cx, cy, f * mv, f * md);
  }
  // motion
  const double vt = P_(k, 3, 0.1);
  st->var_acc += vt * vt * P_(k, 4, 5.0) * dt;
  if (t - st->t_blur >= P_(k, 14, 1.0)) { v4_blur(st); st->t_blur = t; }
  v4_normalize(k, st);
  v4_recentre(k, st);
  st->t_last = t;
  v4_hist_push(k, st, t);
  v4_tap(k, st, t);
  v4_steer(k, st, t);
  ctl_wake(k, t + dt);
}
static void v4_fini(Ctl *k) {
  V4St *st = k->st;
  { double ex, ey; ctl_eff_pos(k, k->t0 + k->T, &ex, &ey); k->diag[12] = ex; k->diag[13] = ey; }
  v4h_aux_free(k);
  if (st) { free(st->Pv); free(st->Pd); free(st->tmp); free(st->sat); free(st->E); free(st->ann); free(st->disk); free(st); }
}
static const CtlDef CTL_V4 = {1005, "V4 = copy of C4 with ablation switches", v4_init, v4_ping, v4_wake, v4_fini};
CTL_REGISTER(CTL_V4)

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
