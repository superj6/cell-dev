// Prediction-family measuring sticks (scratch; never part of an organism).
//
// 1201 "PF interceptor": INFORMATION-MATCHED. A particle filter over the target's (x, y, heading) with the world's
// fixed rules as parameters (halo sigma, lam_s, lam_bg, target speed v_m, tumble time tau_turn, placement annulus
// R_min..R_max, timer t_resp, capture radius rho_c) - constants of the world, never per-life hidden state (as C4).
// It sees only: its pings (sense index + delivery time), its clock, its own strokes (efference copy / key model).
//   ping at sense cell s, delivered at t (screen read at t - d_min):  w_i *= 1 + (lam_s/lam_bg) halo(target_i - p_s)
//   every tick dt (no-ping evidence):                                 w_i *= exp(-dt lam_s sum_s halo(target_i - p_s))
//   motion: straight at speed v_m along the particle's heading; tumble to a uniform heading at rate 1/tau_turn;
//           timer re-placement on the annulus around the dot at rate 1/t_resp (heading kept, as in the world);
//           optional extra position diffusion q_pos (model slack; with v_m = 0 it is the ablation's whole motion model)
//   own clicks: at each commanded click time the particles within rho_c of the dot are re-placed (a capture).
//   Both stochastic moves use a boosted proposal (prob >= b_min / tb_min per tick) with importance weights, so the
//   re-placement and tumble hypotheses keep enough particles; systematic resampling + roughening when ESS is low.
// Decisions at every wake:
//   tap  : q = posterior P(|target(ta) - dot(ta)| <= rho_c), ta = the earliest stroke time; tap if q >= q_tap.
//   steer: predicted target positions at t + latency + lead are histogrammed (cell g = r_box / 1.5); the best
//          3x3-cell box's weighted mean is the aim; if its mass >= steer_min the dot's eventual commanded position is
//          steered onto it (ctl_steer, gain). With v_m = 0 there is no prediction: the aim is the current estimate.
// p: [0] sigma [1] lam_s [2] lam_bg [3] v_m [4] tau_turn (0 = never) [5] R_min [6] R_max [7] t_resp [8] rho_c
//    [9] N (particles, <= 8192) [10] dt [11] q_pos [12] lead [13] gain [14] kmax [15] min_align [16] tol
//    [17] q_tap [18] tap_kappa [19] r_box [20] steer_min [21] b_min [22] tb_min [23] ess_thr [24] rough_xy
//    [25] rough_th [26] seed [27] tap_on_ping (0/1) [28] v_follow (0..1: when no box is confident, follow the
//    posterior mean velocity) [29] intercept (0: aim the eventual position (pursuit); 1: aim the position at the
//    horizon, scaled by the fraction of a new stroke's travel completed by then)
//    [30] blind (0/1; default 0 when absent): LEAKAGE CONTROL - ignore every ping and all no-ping evidence, so the
//    filter runs on its priors, its clock and its own actions only. Vectors with 30 entries behave exactly as before.
#include "ctl_api.h"

static double PF_P(const Ctl *k, int i, double d) { return i < k->np ? k->p[i] : d; }

#define PF_HIST 128
#define PF_MAXCLK 64
typedef struct {
  int N;
  double *x, *y, *vx, *vy, *w, *bx, *by, *bvx, *bvy, *bw;
  double tp, tev;                                  // particle time; last no-ping evidence time
  uint64_t s0, s1;                                 // xorshift128+
  double *G; int GN; double Gh, GR, Gdt;           // exp(-Gdt lam_s E(rel)) on a grid (rel = target - body)
  double ratio, inv2s2, cut2;
  double ht[PF_HIST], hx[PF_HIST], hy[PF_HIST]; int hn, hh;
  double clk[PF_MAXCLK]; int nclk;
  double *H, *S; int HN; double Hg; int *cell;     // aim histogram, its summed-area table, particle cells
} PFSt;

static inline uint64_t pf_next(PFSt *st) {
  uint64_t a = st->s0; const uint64_t b = st->s1;
  st->s0 = b; a ^= a << 23; a ^= a >> 17; a ^= b ^ (b >> 26); st->s1 = a;
  return a + b;
}
static inline double pf_u(PFSt *st) { return (double)(pf_next(st) >> 11) * (1.0 / 9007199254740992.0); }
static inline double pf_n(PFSt *st) {
  double u = pf_u(st); if (u < 1e-300) u = 1e-300;
  return sqrt(-2.0 * log(u)) * cos(6.283185307179586 * pf_u(st));
}
static void pf_hist_push(Ctl *k, PFSt *st, double t) {
  double x, y;
  ctl_eff_pos(k, t, &x, &y);
  if (st->hn > 0) { const int last = (st->hh + st->hn - 1) % PF_HIST; if (st->ht[last] == t) return; }
  const int i = (st->hh + st->hn) % PF_HIST;
  st->ht[i] = t; st->hx[i] = x; st->hy[i] = y;
  if (st->hn < PF_HIST) st->hn++; else st->hh = (st->hh + 1) % PF_HIST;
}
static void pf_pos_at(Ctl *k, PFSt *st, double t, double *x, double *y) {  // the dot (efference) at time t
  if (t >= ctl_now(k)) { ctl_eff_pos(k, t, x, y); return; }
  double pt = ctl_now(k), px, py;
  ctl_eff_pos(k, pt, &px, &py);
  for (int q = st->hn - 1; q >= 0; q--) {
    const int i = (st->hh + q) % PF_HIST;
    if (st->ht[i] <= t) {
      const double w = pt > st->ht[i] ? (t - st->ht[i]) / (pt - st->ht[i]) : 0.0;
      *x = st->hx[i] + w * (px - st->hx[i]); *y = st->hy[i] + w * (py - st->hy[i]);
      return;
    }
    pt = st->ht[i]; px = st->hx[i]; py = st->hy[i];
  }
  *x = px; *y = py;
}
static void pf_annulus(Ctl *k, PFSt *st, double *ox, double *oy) {
  const double rmin = PF_P(k, 5, 2.0), rmax = PF_P(k, 6, 6.0);
  const double r = rmin + pf_u(st) * (rmax - rmin), th = 6.283185307179586 * pf_u(st);
  *ox = r * cos(th); *oy = r * sin(th);
}
static void pf_heading(Ctl *k, PFSt *st, double *vx, double *vy) {
  const double v = PF_P(k, 3, 0.1), th = 6.283185307179586 * pf_u(st);
  *vx = v * cos(th); *vy = v * sin(th);
}
static inline double pf_G(const PFSt *st, double rx, double ry) {
  if (rx <= -st->GR || rx >= st->GR || ry <= -st->GR || ry >= st->GR) return 1.0;
  const int i = (int)((rx + st->GR) / st->Gh + 0.5), j = (int)((ry + st->GR) / st->Gh + 0.5);
  if (i < 0 || j < 0 || i >= st->GN || j >= st->GN) return 1.0;
  return st->G[i * st->GN + j];
}
static void pf_normalize(PFSt *st) {
  double s = 0.0;
  for (int i = 0; i < st->N; i++) s += st->w[i];
  if (!(s > 1e-300) || !isfinite(s)) { for (int i = 0; i < st->N; i++) st->w[i] = 1.0 / st->N; return; }
  const double r = 1.0 / s;
  for (int i = 0; i < st->N; i++) st->w[i] *= r;
}
static void pf_reset(Ctl *k, PFSt *st, double cx, double cy) {  // lost: restart from the placement prior
  for (int i = 0; i < st->N; i++) {
    double ox, oy; pf_annulus(k, st, &ox, &oy);
    st->x[i] = cx + ox; st->y[i] = cy + oy; pf_heading(k, st, &st->vx[i], &st->vy[i]); st->w[i] = 1.0 / st->N;
  }
  k->diag[10] += 1.0;
}
static void pf_process_clicks(Ctl *k, PFSt *st, double t) {
  int keep = 0;
  const double rho = PF_P(k, 8, 1.0), r2 = rho * rho;
  for (int q = 0; q < st->nclk; q++) {
    const double tc = st->clk[q];
    if (tc > t) { st->clk[keep++] = tc; continue; }
    double dx_, dy_;
    pf_pos_at(k, st, tc, &dx_, &dy_);
    const double h = tc - st->tp;
    for (int i = 0; i < st->N; i++) {
      const double ex = st->x[i] + st->vx[i] * h - dx_, ey = st->y[i] + st->vy[i] * h - dy_;
      if (ex * ex + ey * ey <= r2) {
        double ox, oy; pf_annulus(k, st, &ox, &oy);
        st->x[i] = dx_ + ox - st->vx[i] * h; st->y[i] = dy_ + oy - st->vy[i] * h;
      }
    }
  }
  st->nclk = keep;
}
static void pf_resample(Ctl *k, PFSt *st) {
  const int N = st->N;
  const double u0 = pf_u(st) / N, rxy = PF_P(k, 24, 0.05), rth = PF_P(k, 25, 0.05);
  double c = st->w[0];
  int j = 0;
  for (int i = 0; i < N; i++) {
    const double u = u0 + (double)i / N;
    while (u > c && j < N - 1) { j++; c += st->w[j]; }
    st->bx[i] = st->x[j]; st->by[i] = st->y[j]; st->bvx[i] = st->vx[j]; st->bvy[i] = st->vy[j];
  }
  const double ux = rxy * 3.4641016151377544, ut = rth * 3.4641016151377544;
  for (int i = 0; i < N; i++) {
    double x = st->bx[i], y = st->by[i], vx = st->bvx[i], vy = st->bvy[i];
    if (ux > 0.0) { x += ux * (pf_u(st) - 0.5); y += ux * (pf_u(st) - 0.5); }
    if (ut > 0.0 && (vx != 0.0 || vy != 0.0)) {
      const double a = ut * (pf_u(st) - 0.5), sp = sqrt(vx * vx + vy * vy);
      double nx = vx - a * vy, ny = vy + a * vx;
      const double r = sp / sqrt(nx * nx + ny * ny); vx = nx * r; vy = ny * r;
    }
    st->x[i] = x; st->y[i] = y; st->vx[i] = vx; st->vy[i] = vy; st->w[i] = 1.0 / N;
  }
  k->diag[5] += 1.0;
}
static void pf_tap(Ctl *k, PFSt *st, double t) {
  if (k->hot < 0) return;
  const double kap = PF_P(k, 18, 1.0);
  double ta = t + k->latency;
  const double lf = ctl_last_fire(k, k->hot) + k->t_ref_min;
  if (lf > ta) ta = lf;
  if (!ctl_tap_would_click(k, kap, ta) || st->nclk >= PF_MAXCLK) return;
  double ax, ay;
  ctl_eff_pos(k, ta, &ax, &ay);
  const double rho = PF_P(k, 8, 1.0), r2 = rho * rho, h = ta - st->tp;
  double q = 0.0;
  for (int i = 0; i < st->N; i++) {
    const double ex = st->x[i] + st->vx[i] * h - ax, ey = st->y[i] + st->vy[i] * h - ay;
    if (ex * ex + ey * ey <= r2) q += st->w[i];
  }
  if (q >= PF_P(k, 17, 0.3)) {
    const double before = k->diag[3];
    const double tf = ctl_fire(k, k->hot, kap, t);
    if (k->diag[3] > before && tf > 0.0) { st->clk[st->nclk++] = tf; k->diag[6] += 1.0; k->diag[7] += q; }
  }
}
static void pf_steer(Ctl *k, PFSt *st, double t) {
  const double gain = PF_P(k, 13, 1.0);
  if (gain <= 0.0) return;
  const int HN = st->HN, c = HN / 2;
  double cx, cy;
  ctl_eff_pos(k, t, &cx, &cy);
  const double hz = k->latency + PF_P(k, 12, 1.0) + (t - st->tp);
  double tot = 0.0;
  const double ig = 1.0 / st->Hg;
  int amin = HN, amax = -1, bmin = HN, bmax = -1;
  for (int i = 0; i < st->N; i++) {
    const double px = st->x[i] + st->vx[i] * hz - cx, py = st->y[i] + st->vy[i] * hz - cy;
    st->bx[i] = px; st->by[i] = py;
    const int a = (int)lrint(px * ig) + c, b = (int)lrint(py * ig) + c;
    tot += st->w[i];
    if (a < 0 || b < 0 || a >= HN || b >= HN) { st->cell[i] = -1; continue; }
    st->cell[i] = a * HN + b;
    if (a < amin) amin = a;
    if (a > amax) amax = a;
    if (b < bmin) bmin = b;
    if (b > bmax) bmax = b;
  }
  if (amax < 0) return;
  // histogram on the occupied box only (local indices), then the 3x3-box maximum via a summed-area table
  const int na = amax - amin + 1, nb = bmax - bmin + 1, n1 = nb + 1;
  memset(st->H, 0, sizeof(double) * na * nb);
  for (int i = 0; i < st->N; i++) {
    const int cl = st->cell[i];
    if (cl < 0) continue;
    const int a = cl / HN - amin, b = cl % HN - bmin;
    st->H[a * nb + b] += st->w[i];
  }
  double *S = st->S;
  for (int i = 0; i <= na; i++) S[i * n1] = 0.0;
  for (int j = 0; j <= nb; j++) S[j] = 0.0;
  for (int i = 0; i < na; i++) {
    double row = 0.0;
    for (int j = 0; j < nb; j++) { row += st->H[i * nb + j]; S[(i + 1) * n1 + (j + 1)] = S[i * n1 + (j + 1)] + row; }
  }
  double best = -1.0; int bi = c, bj = c;
  for (int i = 0; i < na; i++) {
    const int i0 = i - 1 < 0 ? 0 : i - 1, i1 = i + 2 > na ? na : i + 2;
    for (int j = 0; j < nb; j++) {
      const int j0 = j - 1 < 0 ? 0 : j - 1, j1 = j + 2 > nb ? nb : j + 2;
      const double m = S[i1 * n1 + j1] - S[i0 * n1 + j1] - S[i1 * n1 + j0] + S[i0 * n1 + j0];
      if (m > best) { best = m; bi = i + amin; bj = j + bmin; }
    }
  }
  if (tot > 0.0) best /= tot;
  double fx, fy;
  ctl_eff_final(k, &fx, &fy);
  if (best >= PF_P(k, 20, 0.0)) {
    double sx = 0.0, sy = 0.0, sw = 0.0;
    for (int i = 0; i < st->N; i++) {
      const int cl = st->cell[i];
      if (cl < 0) continue;
      const int a = cl / HN, b = cl - a * HN;
      if (a < bi - 1 || a > bi + 1 || b < bj - 1 || b > bj + 1) continue;
      sx += st->w[i] * st->bx[i]; sy += st->w[i] * st->by[i]; sw += st->w[i];
    }
    if (sw <= 0.0) return;
    const double gx = cx + sx / sw, gy = cy + sy / sw;
    double dx, dy;
    if (PF_P(k, 29, 0.0) > 0.0) {  // intercept: position at the horizon, scaled by a new stroke's completed travel
      const double tH = t + hz - (t - st->tp);
      double hx, hy;
      ctl_eff_pos(k, tH, &hx, &hy);
      const double tr = hz - k->latency, frac = tr > 0.05 ? 1.0 - exp(-tr / k->tau_z) : 0.05;
      const double mix = PF_P(k, 29, 0.0);
      dx = mix * (gx - hx) / frac + (1.0 - mix) * (gx - fx);
      dy = mix * (gy - hy) / frac + (1.0 - mix) * (gy - fy);
    } else { dx = gx - fx; dy = gy - fy; }
    ctl_steer(k, gain * dx, gain * dy, t, PF_P(k, 14, 1.0), PF_P(k, 15, 0.5), PF_P(k, 16, 0.15));
    k->diag[8] += 1.0; k->diag[9] += best;
  } else if (PF_P(k, 28, 0.0) > 0.0) {  // follow the posterior mean velocity (keeps the relative geometry)
    double mvx = 0.0, mvy = 0.0;
    for (int i = 0; i < st->N; i++) { mvx += st->w[i] * st->vx[i]; mvy += st->w[i] * st->vy[i]; }
    if (tot > 0.0) { mvx /= tot; mvy /= tot; }
    const double f = PF_P(k, 28, 0.0), dtw = PF_P(k, 10, 0.25);
    double ex, ey;  // keep the eventual position ahead of the current one by v * tau_z (steady pursuit)
    ex = cx + mvx * k->tau_z - fx; ey = cy + mvy * k->tau_z - fy;
    (void)dtw;
    ctl_steer(k, f * ex, f * ey, t, PF_P(k, 14, 1.0), PF_P(k, 15, 0.5), PF_P(k, 16, 0.15));
    k->diag[11] += 1.0;
  }
}
static int pf_init(Ctl *k) {
  if (k->np < 27) return -1;
  PFSt *st = calloc(1, sizeof(PFSt));
  if (!st) return -1;
  k->st = st;
  int N = (int)PF_P(k, 9, 1000.0);
  if (N < 16) N = 16;
  if (N > 8192) N = 8192;
  st->N = N;
  double **arr[] = {&st->x, &st->y, &st->vx, &st->vy, &st->w, &st->bx, &st->by, &st->bvx, &st->bvy, &st->bw};
  for (int i = 0; i < 10; i++) { *arr[i] = malloc(sizeof(double) * N); if (!*arr[i]) return -1; }
  uint64_t sd = (uint64_t)(int64_t)PF_P(k, 26, 1.0) * 0x9E3779B97F4A7C15ULL + 0x632BE59BD9B4E019ULL;
  for (int r = 0; r < 2; r++) {  // splitmix64
    uint64_t z = (sd += 0x9E3779B97F4A7C15ULL);
    z = (z ^ (z >> 30)) * 0xBF58476D1CE4E5B9ULL; z = (z ^ (z >> 27)) * 0x94D049BB133111EBULL; z ^= z >> 31;
    if (r == 0) st->s0 = z | 1; else st->s1 = z | 2;
  }
  const double sig = PF_P(k, 0, 0.6), lam_s = PF_P(k, 1, 2.0), lam_bg = PF_P(k, 2, 0.05), dt = PF_P(k, 10, 0.25);
  st->ratio = lam_s / (lam_bg > 1e-9 ? lam_bg : 1e-9);
  st->inv2s2 = 1.0 / (2.0 * sig * sig);
  st->cut2 = 25.0 * sig * sig;
  double rs = 0.0;
  for (int s = 0; s < k->n_sense; s++) {
    const double r = hypot(k->sense_xy[2 * s], k->sense_xy[2 * s + 1]);
    if (r > rs) rs = r;
  }
  st->Gh = 0.1; st->GR = rs + 5.0 * sig; st->GN = 2 * (int)ceil(st->GR / st->Gh) + 1; st->Gdt = dt;
  st->G = malloc(sizeof(double) * st->GN * st->GN);
  if (!st->G) return -1;
  for (int i = 0; i < st->GN; i++)
    for (int j = 0; j < st->GN; j++) {
      const double x = -st->GR + i * st->Gh, y = -st->GR + j * st->Gh;
      double lam = 0.0;
      for (int s = 0; s < k->n_sense; s++) {
        const double dx = x - k->sense_xy[2 * s], dy = y - k->sense_xy[2 * s + 1];
        lam += lam_s * exp(-(dx * dx + dy * dy) * st->inv2s2);
      }
      st->G[i * st->GN + j] = exp(-dt * lam);
    }
  const double rb = PF_P(k, 19, 1.0);
  st->Hg = rb / 1.5;
  if (st->Hg < 0.1) st->Hg = 0.1;
  const double Rh = PF_P(k, 6, 6.0) + 6.0;
  st->HN = 2 * (int)ceil(Rh / st->Hg) + 1;
  st->H = malloc(sizeof(double) * st->HN * st->HN);
  st->S = malloc(sizeof(double) * (st->HN + 1) * (st->HN + 1));
  st->cell = malloc(sizeof(int) * N);
  if (!st->H || !st->S || !st->cell) return -1;
  st->tp = k->t0; st->tev = k->t0;
  pf_reset(k, st, 0.0, 0.0);
  k->diag[10] = 0.0;
  pf_hist_push(k, st, k->t0);
  ctl_wake(k, k->t0 + dt);
  return 0;
}
static void pf_ping(Ctl *k, double t, int s) {
  PFSt *st = k->st;
  pf_hist_push(k, st, t);
  pf_process_clicks(k, st, t);
  if (PF_P(k, 30, 0.0) > 0.0) return;  // blind control
  const double tr = t - k->d_min;
  double bx, by;
  pf_pos_at(k, st, tr, &bx, &by);
  const double px = bx + k->sense_xy[2 * s], py = by + k->sense_xy[2 * s + 1], h = tr - st->tp;
  const double ratio = st->ratio, i2 = st->inv2s2, cut2 = st->cut2;
  double mx = 0.0;
  for (int i = 0; i < st->N; i++) {
    const double ex = st->x[i] + st->vx[i] * h - px, ey = st->y[i] + st->vy[i] * h - py, d2 = ex * ex + ey * ey;
    if (d2 < cut2) st->w[i] *= 1.0 + ratio * exp(-d2 * i2);
    if (st->w[i] > mx) mx = st->w[i];
  }
  if (mx > 1e100) pf_normalize(st);
  if (PF_P(k, 27, 0.0) > 0.0) pf_tap(k, st, t);
}
static void pf_wake(Ctl *k, double t) {
  PFSt *st = k->st;
  const int N = st->N;
  const double dt = PF_P(k, 10, 0.25);
  pf_process_clicks(k, st, t);
  // no-ping evidence over (tev, t], read at the mid-interval screen time; then drift to t (one pass)
  const double D = t - st->tev, hd = t - st->tp;
  if (D > 0.0 && PF_P(k, 30, 0.0) > 0.0) {  // blind control: no evidence, drift only
    for (int i = 0; i < N; i++) { st->x[i] += st->vx[i] * hd; st->y[i] += st->vy[i] * hd; }
    st->tev = t;
  } else if (D > 0.0) {
    const double tm = 0.5 * (st->tev + t) - k->d_min, h = tm - st->tp;
    double bx, by;
    pf_pos_at(k, st, tm, &bx, &by);
    const double pw = D / st->Gdt;
    const int exact = fabs(pw - 1.0) < 1e-9;
    for (int i = 0; i < N; i++) {
      const double g = pf_G(st, st->x[i] + st->vx[i] * h - bx, st->y[i] + st->vy[i] * h - by);
      st->w[i] *= exact ? g : pow(g, pw);
      st->x[i] += st->vx[i] * hd; st->y[i] += st->vy[i] * hd;
    }
    st->tev = t;
  } else
    for (int i = 0; i < N; i++) { st->x[i] += st->vx[i] * hd; st->y[i] += st->vy[i] * hd; }
  st->tp = t;
  const double trs = PF_P(k, 7, 50.0), ttu = PF_P(k, 4, 20.0);
  const double pr = trs > 0.0 ? 1.0 - exp(-dt / trs) : 0.0, pt = ttu > 0.0 ? 1.0 - exp(-dt / ttu) : 0.0;
  const double bmin = PF_P(k, 21, 0.0), tbmin = PF_P(k, 22, 0.0);
  const double pb = pr > 0.0 ? (pr > bmin ? pr : bmin) : 0.0, ptb = pt > 0.0 ? (pt > tbmin ? pt : tbmin) : 0.0;
  // event particles get the importance ratio relative to the non-event ones (a common factor cancels at normalization)
  const double wr = pb > 0.0 ? (pr / pb) / ((1.0 - pr) / (1.0 - pb)) : 1.0;
  const double wt = ptb > 0.0 ? (pt / ptb) / ((1.0 - pt) / (1.0 - ptb)) : 1.0;
  const double qp = PF_P(k, 11, 0.0) * sqrt(dt) * 3.4641016151377544;  // uniform noise with sd q_pos sqrt(dt)
  double cx, cy;
  ctl_eff_pos(k, t, &cx, &cy);
  if (pb > 0.0) {  // geometric skipping: O(number of events)
    const double lq = log(1.0 - pb);
    for (int i = (int)floor(log(1.0 - pf_u(st)) / lq); i < N; i += 1 + (int)floor(log(1.0 - pf_u(st)) / lq)) {
      double ox, oy; pf_annulus(k, st, &ox, &oy);
      st->x[i] = cx + ox; st->y[i] = cy + oy; st->w[i] *= wr;
    }
  }
  if (ptb > 0.0) {
    const double lq = log(1.0 - ptb);
    for (int i = (int)floor(log(1.0 - pf_u(st)) / lq); i < N; i += 1 + (int)floor(log(1.0 - pf_u(st)) / lq)) {
      pf_heading(k, st, &st->vx[i], &st->vy[i]); st->w[i] *= wt;
    }
  }
  if (qp > 0.0)
    for (int i = 0; i < N; i++) { st->x[i] += qp * (pf_u(st) - 0.5); st->y[i] += qp * (pf_u(st) - 0.5); }
  // normalize, resample when the effective sample size is low
  double s = 0.0;
  for (int i = 0; i < N; i++) s += st->w[i];
  if (!(s > 1e-300) || !isfinite(s)) pf_reset(k, st, cx, cy);
  else {
    const double r = 1.0 / s;
    double s2 = 0.0;
    for (int i = 0; i < N; i++) { st->w[i] *= r; s2 += st->w[i] * st->w[i]; }
    if (1.0 / s2 < PF_P(k, 23, 0.5) * N) pf_resample(k, st);
  }
  pf_hist_push(k, st, t);
  pf_tap(k, st, t);
  pf_steer(k, st, t);
  ctl_wake(k, t + dt);
}
static void pf_fini(Ctl *k) {
  PFSt *st = k->st;
  if (!st) return;
  free(st->x); free(st->y); free(st->vx); free(st->vy); free(st->w);
  free(st->bx); free(st->by); free(st->bvx); free(st->bvy); free(st->bw);
  free(st->G); free(st->H); free(st->S); free(st->cell); free(st);
}
static const CtlDef CTL_PF = {1201, "PF interceptor", pf_init, pf_ping, pf_wake, pf_fini};
CTL_REGISTER(CTL_PF)
