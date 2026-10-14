// Memory-family measuring sticks (scratch; never part of an organism). Compiled into the harness translation unit
// after ctl_builtin.c (so the static helper P_ is visible), via
//   python make_ckernel.py --fast --out memory/mk_fast.so --ctl memory/mem_ctl.c
//
// 1101  M1  privileged pursuit with a chosen DARK policy (decomposes the ceiling into "knowing during darkness"
//           vs "remembering"): C1's logic, but while the target is dark (or dim) it uses
//             dark_mode 0: the truth (= C1);  1: the last seen position extrapolated with the last seen velocity;
//             2: the last seen position held (no velocity);  3: nothing (no steering, no taps: a perfect-sensing
//             pursuer without memory).
//           After `dark_taps` commanded taps on a remembered (not seen) target, the memory is dropped (it presumes
//           a capture and a re-placement it cannot see).
// 1102  C5  information-matched Bayes MEMORY tracker: C4's grid posterior (visible / dark mass, ping and no-ping
//           evidence, timer re-placement, blink transitions, own-click captures), plus
//             - dim dark state (dark_amp: a dark target still emits pings at dark_amp * lam_s; flash-dim worlds),
//             - optional velocity memory: an exponentially weighted least-squares velocity of the tracked mode
//               (posterior mean within the best rho_c box, sampled only when that box holds >= conf_v of the mass
//               and a ping arrived within seen_win), clipped to the world's target speed v_t; the whole posterior
//               drifts with v * exp(-(t - t_sample) / tau_turn) (the expected run-and-tumble velocity),
//             - ablation idle_dark: no steering and no tapping while the controller's own belief that the target
//               is dark (dark mass fraction) exceeds idle_dark (it can represent darkness but not act on memory).
//           Everything it reads: pings, its clock, its own commanded strokes (efference / key models), footprint,
//           body constants, and world RULES in p (never per-life hidden state).
#include "ctl_api.h"

// =========================================================================================== 1101: M1
// p: [0..11] as C1 (dt gain lead kmax min_align tol tap_r tap_kappa use_dark(ignored) chase_food poison_margin hold_r)
//    [12] dark_mode (0)  [13] dark_taps (2)
typedef struct { double lx, ly, lvx, lvy, lt; int seen, ntaps; } M1St;
static int m1_init(Ctl *k) {
  M1St *st = calloc(1, sizeof(M1St));
  if (!st) return -1;
  k->st = st;
  ctl_wake(k, k->t0);
  return 0;
}
static void m1_wake(Ctl *k, double t) {
  M1St *st = k->st;
  CtlTruth tr;
  if (!ctl_truth(k, &tr)) return;
  const double lat = k->latency, dt = P_(k, 0, 0.25), gain = P_(k, 1, 1.0), lead = P_(k, 2, 1.0);
  const int mode = (int)P_(k, 12, 0.0);
  const double ta = t + lat;
  ctl_set_motor_sign(k, ta >= tr.t_flip ? -1.0 : 1.0);
  double gx, gy, gvx, gvy, rho = tr.rho_c;
  int remembered = 0;
  if (mode == 0 || tr.visible) {
    gx = tr.X + tr.dx; gy = tr.Y + tr.dy; gvx = tr.vx; gvy = tr.vy;
    st->lx = gx; st->ly = gy; st->lvx = gvx; st->lvy = gvy; st->lt = t; st->seen = 1; st->ntaps = 0;
  } else if (mode != 3 && st->seen) {
    remembered = 1;
    if (mode == 1) { gx = st->lx + st->lvx * (t - st->lt); gy = st->ly + st->lvy * (t - st->lt); gvx = st->lvx; gvy = st->lvy; }
    else { gx = st->lx; gy = st->ly; gvx = 0.0; gvy = 0.0; }
  } else {
    k->diag[7] += dt;  // time idle in the dark
    ctl_wake(k, t + dt);
    return;
  }
  double px, py;
  ctl_pending_disp(k, INFINITY, &px, &py);
  const double ex = tr.X + tr.Fx * k->tau_z / tr.gam + px, ey = tr.Y + tr.Fy * k->tau_z / tr.gam + py;
  const double h = lat + lead;
  const double ox = gx + gvx * h - ex, oy = gy + gvy * h - ey;
  ctl_steer(k, gain * ox, gain * oy, t, P_(k, 3, 1.0), P_(k, 4, 0.5), P_(k, 5, 0.15));
  if (k->hot >= 0) {
    const double tk = P_(k, 7, 1.0);
    const double tt = ctl_last_fire(k, k->hot) + k->t_ref_min > ta ? ctl_last_fire(k, k->hot) + k->t_ref_min : ta;
    double qx, qy;
    ctl_pending_disp(k, tt, &qx, &qy);
    const double e = exp(-(tt - t) / k->tau_z), kk = k->tau_z * (1.0 - e) / tr.gam;
    const double dxa = tr.X + tr.Fx * kk + qx, dya = tr.Y + tr.Fy * kk + qy;
    const double tgx = gx + gvx * (tt - t) - dxa, tgy = gy + gvy * (tt - t) - dya;
    const double tr_ = P_(k, 6, 0.8) * rho;
    if (tgx * tgx + tgy * tgy <= tr_ * tr_ && ctl_tap_would_click(k, tk, tt)) {
      const double before = k->diag[3];
      ctl_fire(k, k->hot, tk, tt);
      if (remembered && k->diag[3] > before) {
        k->diag[8] += 1.0;  // taps on a remembered target
        if (++st->ntaps >= (int)P_(k, 13, 2.0)) st->seen = 0;
      }
    }
  }
  ctl_wake(k, t + dt);
}
static void m1_fini(Ctl *k) { free(k->st); }
static const CtlDef CTL_M1 = {1101, "M1 privileged pursuit, dark policy", m1_init, NULL, m1_wake, m1_fini};
CTL_REGISTER(CTL_M1)

// =========================================================================================== 1102: C5
// p: [0] sigma [1] lam_s [2] lam_bg [3] v_t [4] tau_eff [5] R_min [6] R_max [7] t_resp [8] rho_c [9] blink_on
//    [10] blink_off [11] dt (0.5) [12] h (0.2) [13] W (7.0) [14] blur_every (2.0) [15] gain (1.0) [16] kmax (1.0)
//    [17] min_align (0.5) [18] tol (0.15) [19] q_tap (0.3) [20] steer_min (0.0)       (= C4's layout)
//    [21] dark_amp (0)  [22] vel (0/1)  [23] tau_turn (20)  [24] tau_v (8)  [25] conf_v (0.5)  [26] idle_dark (0 off)
//    [27] sig_p (0.7: ping position noise for the velocity's uncertainty)  [28] vel_gain (1.0)  [29] gate (1.5)
// diag: [5] sum best-box mass at steering  [6] steering calls  [9] posterior resets  [10] mean dark fraction x ticks
//       [11] ticks idle by idle_dark  [12] velocity samples  [13] sum |v_eff| over ticks  [14] ticks
#define C5_HIST 64
#define C5_TRK 128
typedef struct {
  int N, c, M, nm, ndisk, blink, flash;
  double h, gx0, gy0, var_acc, t_blur, t_last;
  double *Pv, *Pd, *tmp, *sat, *E, *Ed, *ann, ratio, ratio_d, sig4, tot, damp;
  int amin, amax, emin, emax;
  int *disk;
  double clk[64]; int nclk;
  double ht[C5_HIST], hx[C5_HIST], hy[C5_HIST]; int hn, hh;
  // velocity memory
  double tt_[C5_TRK], tx_[C5_TRK], ty_[C5_TRK]; int tn, th_;
  double vx, vy, t_vs, last_ping, bcx, bcy; int have_bc;
  int bi, bj; double best;
} C5St;
static inline int c5_in(const C5St *st, int i, int j) { return i >= 0 && j >= 0 && i < st->N && j < st->N; }
static void c5_hist_push(Ctl *k, C5St *st, double t) {
  double x, y;
  ctl_eff_pos(k, t, &x, &y);
  const int i = (st->hh + st->hn) % C5_HIST;
  st->ht[i] = t; st->hx[i] = x; st->hy[i] = y;
  if (st->hn < C5_HIST) st->hn++; else st->hh = (st->hh + 1) % C5_HIST;
}
static void c5_pos_at(Ctl *k, C5St *st, double t, double *x, double *y) {
  if (t >= ctl_now(k)) { ctl_eff_pos(k, t, x, y); return; }
  double pt = ctl_now(k), px, py;
  ctl_eff_pos(k, pt, &px, &py);
  for (int q = st->hn - 1; q >= 0; q--) {
    const int i = (st->hh + q) % C5_HIST;
    if (st->ht[i] <= t) {
      const double w = pt > st->ht[i] ? (t - st->ht[i]) / (pt - st->ht[i]) : 0.0;
      *x = st->hx[i] + w * (px - st->hx[i]); *y = st->hy[i] + w * (py - st->hy[i]);
      return;
    }
    pt = st->ht[i]; px = st->hx[i]; py = st->hy[i];
  }
  *x = px; *y = py;
}
static void c5_body_cell(const C5St *st, double bx, double by, int *oi, int *oj) {
  *oi = (int)lround((bx - st->gx0) / st->h); *oj = (int)lround((by - st->gy0) / st->h);
}
static void c5_place(C5St *st, double bx, double by, double mv, double md) {
  int oi, oj;
  c5_body_cell(st, bx, by, &oi, &oj);
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
static void c5_trk_reset(C5St *st) { st->tn = 0; st->th_ = 0; st->vx = 0.0; st->vy = 0.0; st->t_vs = -INFINITY; }
static void c5_normalize(Ctl *k, C5St *st) {
  double s = 0.0;
  const int NN = st->N * st->N;
  for (int i = 0; i < NN; i++) s += st->Pv[i] + (st->blink ? st->Pd[i] : 0.0);
  if (!(s > 1e-280) || !isfinite(s)) {
    memset(st->Pv, 0, sizeof(double) * NN);
    if (st->blink) memset(st->Pd, 0, sizeof(double) * NN);
    double bx, by;
    ctl_eff_pos(k, ctl_now(k), &bx, &by);
    st->tot = 0.0;
    c5_place(st, bx, by, 1.0, 0.0);
    c5_trk_reset(st);
    k->diag[9] += 1.0;
    return;
  }
  const double r = 1.0 / s;
  for (int i = 0; i < NN; i++) { st->Pv[i] *= r; if (st->blink) st->Pd[i] *= r; }
  st->tot = 1.0;
}
static void c5_recentre(Ctl *k, C5St *st) {
  double bx, by;
  ctl_eff_pos(k, ctl_now(k), &bx, &by);
  int oi, oj;
  c5_body_cell(st, bx, by, &oi, &oj);
  if (abs(oi) <= st->N / 6 && abs(oj) <= st->N / 6) return;
  const int N = st->N;
  for (int g = 0; g < 1 + st->blink; g++) {
    double *P = g ? st->Pd : st->Pv;
    for (int i = 0; i < N; i++)
      for (int j = 0; j < N; j++) {
        const int si = i + oi, sj = j + oj;
        st->tmp[i * N + j] = c5_in(st, si, sj) ? P[si * N + sj] : 0.0;
      }
    memcpy(P, st->tmp, sizeof(double) * N * N);
  }
  st->gx0 += oi * st->h; st->gy0 += oj * st->h;
  c5_normalize(k, st);
}
static void c5_blur(C5St *st) {
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
}
static void c5_capture(Ctl *k, C5St *st, double tc) {
  double bx, by;
  c5_pos_at(k, st, tc, &bx, &by);
  int oi, oj;
  c5_body_cell(st, bx, by, &oi, &oj);
  double mv = 0.0, md = 0.0;
  for (int q = 0; q < st->ndisk; q++) {
    const int i = st->c + oi + st->disk[2 * q], j = st->c + oj + st->disk[2 * q + 1];
    if (!c5_in(st, i, j)) continue;
    mv += st->Pv[i * st->N + j]; st->Pv[i * st->N + j] = 0.0;
    if (st->blink) { md += st->Pd[i * st->N + j]; st->Pd[i * st->N + j] = 0.0; }
  }
  st->tot -= mv + md;
  if (st->flash) c5_place(st, bx, by, mv + md, 0.0);
  else c5_place(st, bx, by, mv, md);
  c5_trk_reset(st);  // the tracked target was probably re-placed
}
static double c5_mass_at(const C5St *st, double x, double y) {
  int oi, oj;
  c5_body_cell(st, x, y, &oi, &oj);
  double m = 0.0;
  for (int q = 0; q < st->ndisk; q++) {
    const int i = st->c + oi + st->disk[2 * q], j = st->c + oj + st->disk[2 * q + 1];
    if (!c5_in(st, i, j)) continue;
    m += st->Pv[i * st->N + j] + (st->blink ? st->Pd[i * st->N + j] : 0.0);
  }
  return st->tot > 0.0 ? m / st->tot : 0.0;
}
static void c5_process_clicks(Ctl *k, C5St *st, double t) {
  int w = 0;
  for (int q = 0; q < st->nclk; q++) {
    if (st->clk[q] <= t) c5_capture(k, st, st->clk[q]);
    else st->clk[w++] = st->clk[q];
  }
  st->nclk = w;
}
static double c5_dark_frac(const C5St *st) {
  if (!st->blink) return 0.0;
  double md = 0.0, s = 0.0;
  const int NN = st->N * st->N;
  for (int i = 0; i < NN; i++) { md += st->Pd[i]; s += st->Pv[i] + st->Pd[i]; }
  return s > 0.0 ? md / s : 0.0;
}
static void c5_tap(Ctl *k, C5St *st, double t) {
  if (k->hot >= 0) {
    double ta = t + k->latency;
    const double lf = ctl_last_fire(k, k->hot) + k->t_ref_min;
    if (lf > ta) ta = lf;
    double ax, ay;
    ctl_eff_pos(k, ta, &ax, &ay);
    const double q = c5_mass_at(st, ax, ay);
    if (q >= P_(k, 19, 0.3) && ctl_tap_would_click(k, 1.0, ta) && st->nclk < 64) {
      const double before = k->diag[3];
      const double tf = ctl_fire(k, k->hot, 1.0, t);
      if (k->diag[3] > before && tf > 0) st->clk[st->nclk++] = tf;
    }
  }
}
static void c5_best(Ctl *k, C5St *st) {  // best rho_c box (summed-area table) -> st->bi, bj, best (normalized)
  const int N = st->N;
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
  st->bi = bi; st->bj = bj; st->best = best / (st->tot > 0.0 ? st->tot : 1.0);
}
static void c5_steer(Ctl *k, C5St *st, double t) {
  const double gain = P_(k, 15, 1.0);
  if (gain <= 0.0) return;
  if (st->best < P_(k, 20, 0.0)) return;
  const double gx = st->gx0 + (st->bi - st->c) * st->h, gy = st->gy0 + (st->bj - st->c) * st->h;
  double fx, fy;
  ctl_eff_final(k, &fx, &fy);
  ctl_steer(k, gain * (gx - fx), gain * (gy - fy), t, P_(k, 16, 1.0), P_(k, 17, 0.5), P_(k, 18, 0.15));
  k->diag[5] += st->best; k->diag[6] += 1.0;
}
// velocity memory: target pings (pings within `gate` of the tracked mode's centre, while that mode holds >= conf_v of
// the mass) are regressed on time (weights exp((t_i - t) / tau_v)); the slope, clipped to the world's speed v_t, is
// the target velocity estimate. The whole posterior drifts with v * vel_gain * exp(-(t - t_last_target_ping) / tau_turn).
static void c5_trk_push(Ctl *k, C5St *st, double tc, double px, double py) {
  if (!st->have_bc || st->best < P_(k, 25, 0.5)) return;
  const double gate = P_(k, 29, 1.5), dx = px - st->bcx, dy = py - st->bcy;
  if (dx * dx + dy * dy > gate * gate) return;
  const int i = (st->th_ + st->tn) % C5_TRK;
  st->tt_[i] = tc; st->tx_[i] = px; st->ty_[i] = py;
  if (st->tn < C5_TRK) st->tn++; else st->th_ = (st->th_ + 1) % C5_TRK;
  k->diag[12] += 1.0;
}
static void c5_velocity(Ctl *k, C5St *st, double t, double dt) {
  const double vt = P_(k, 3, 0.1), tau_v = P_(k, 24, 8.0), tau_turn = P_(k, 23, 20.0);
  const double cx = st->gx0 + (st->bi - st->c) * st->h, cy = st->gy0 + (st->bj - st->c) * st->h;
  if (st->have_bc) {  // the tracked mode jumped (re-acquisition elsewhere): restart the track
    const double dx = cx - st->bcx, dy = cy - st->bcy;
    if (dx * dx + dy * dy > 1.5 * 1.5) c5_trk_reset(st);
  }
  st->bcx = cx; st->bcy = cy; st->have_bc = 1;
  if (st->tn >= 6) {
    double sw = 0.0, st_ = 0.0, stt = 0.0, sx = 0.0, sy = 0.0, stx = 0.0, sty = 0.0, tmin = t, tmax = -INFINITY;
    for (int q = 0; q < st->tn; q++) {
      const int a = (st->th_ + q) % C5_TRK;
      const double u = st->tt_[a] - t, w = exp(u / tau_v);
      if (st->tt_[a] < tmin) tmin = st->tt_[a];
      if (st->tt_[a] > tmax) tmax = st->tt_[a];
      sw += w; st_ += w * u; stt += w * u * u; sx += w * st->tx_[a]; sy += w * st->ty_[a];
      stx += w * u * st->tx_[a]; sty += w * u * st->ty_[a];
    }
    const double den = sw * stt - st_ * st_;
    if (tmax - tmin >= 3.0 && den > 1e-12 && tmax > st->t_vs) {
      double vx = (sw * stx - st_ * sx) / den, vy = (sw * sty - st_ * sy) / den;
      // shrink toward 0 by the slope's uncertainty (prior per axis N(0, v_t^2 / 2); ping position noise sig_p)
      const double sp2 = P_(k, 27, 0.7) * P_(k, 27, 0.7), se2 = sp2 * sw / den, pv = 0.5 * vt * vt;
      const double shrink = pv / (pv + se2);
      vx *= shrink; vy *= shrink;
      const double sp = sqrt(vx * vx + vy * vy), cap = vt;
      if (sp > cap && sp > 0.0) { vx *= cap / sp; vy *= cap / sp; }
      st->vx = vx; st->vy = vy; st->t_vs = tmax;
      if (k->priv) {  // DEBUG ONLY (privileged runs): accuracy of the velocity estimate; never used for control
        CtlTruth tr;
        if (ctl_truth(k, &tr)) {
          k->diag[7] += sqrt((vx - tr.vx) * (vx - tr.vx) + (vy - tr.vy) * (vy - tr.vy)); k->diag[8] += 1.0;
          k->diag[15] += sqrt(vx * vx + vy * vy);
        }
      }
    }
  }
  const double f = P_(k, 28, 1.0) * exp(-(t - st->t_vs) / (tau_turn > 0.0 ? tau_turn : 1e9));
  const double sx = st->vx * f * dt, sy = st->vy * f * dt;
  st->gx0 += sx; st->gy0 += sy;
  st->bcx += sx; st->bcy += sy;
  k->diag[13] += sqrt(st->vx * st->vx + st->vy * st->vy) * f;
}
static int c5_init(Ctl *k) {
  if (k->np < 30) return -1;
  C5St *st = calloc(1, sizeof(C5St));
  if (!st) return -1;
  k->st = st;
  st->h = P_(k, 12, 0.2);
  const double W = P_(k, 13, 7.0);
  st->c = (int)lround(W / st->h); st->N = 2 * st->c + 1; st->M = st->N - 1;
  const int N = st->N, M = st->M, W2 = 2 * M + 1;
  st->blink = P_(k, 9, 0.0) > 0.0 && P_(k, 10, 0.0) != 0.0;
  st->flash = st->blink && P_(k, 10, 0.0) < 0.0;
  st->damp = st->blink ? P_(k, 21, 0.0) : 0.0;
  st->Pv = calloc((size_t)N * N, sizeof(double)); st->Pd = calloc((size_t)N * N, sizeof(double));
  st->tmp = calloc((size_t)N * N, sizeof(double)); st->sat = calloc((size_t)(N + 1) * (N + 1), sizeof(double));
  st->E = calloc((size_t)W2 * W2, sizeof(double)); st->Ed = calloc((size_t)W2 * W2, sizeof(double));
  st->ann = calloc((size_t)W2 * W2, sizeof(double));
  const double rho = P_(k, 8, 1.0);
  const int rr = (int)ceil(rho / st->h);
  st->disk = calloc((size_t)2 * (2 * rr + 1) * (2 * rr + 1), sizeof(int));
  if (!st->Pv || !st->Pd || !st->tmp || !st->sat || !st->E || !st->Ed || !st->ann || !st->disk) return -1;
  for (int u = -rr; u <= rr; u++)
    for (int v = -rr; v <= rr; v++)
      if ((u * u + v * v) * st->h * st->h <= rho * rho) { st->disk[2 * st->ndisk] = u; st->disk[2 * st->ndisk + 1] = v; st->ndisk++; }
  const double sig = P_(k, 0, 0.6), lam_s = P_(k, 1, 2.0), lam_bg = P_(k, 2, 0.05), dt = P_(k, 11, 0.25);
  const double Rmin = P_(k, 5, 2.0), Rmax = P_(k, 6, 6.0);
  st->ratio = lam_s / (lam_bg > 1e-9 ? lam_bg : 1e-9); st->ratio_d = st->ratio * st->damp; st->sig4 = 4.0 * sig;
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
      st->Ed[(u + M) * W2 + (v + M)] = exp(-dt * lam * st->damp);
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
  st->last_ping = -INFINITY; st->t_vs = -INFINITY;
  c5_place(st, 0.0, 0.0, 1.0, 0.0);
  c5_normalize(k, st);
  st->t_last = k->t0; st->t_blur = k->t0;
  c5_hist_push(k, st, k->t0);
  ctl_wake(k, k->t0 + dt);
  return 0;
}
static int c5_idle(Ctl *k, C5St *st) {
  const double th = P_(k, 26, 0.0);
  return th > 0.0 && st->blink && c5_dark_frac(st) > th;
}
static void c5_ping(Ctl *k, double t, int s) {
  C5St *st = k->st;
  c5_process_clicks(k, st, t);
  st->last_ping = t;
  double bx, by;
  c5_pos_at(k, st, t - k->d_min, &bx, &by);
  const double px = bx + k->sense_xy[2 * s], py = by + k->sense_xy[2 * s + 1], sig = P_(k, 0, 0.6);
  const int N = st->N, rr = (int)ceil(st->sig4 / st->h);
  int oi, oj;
  c5_body_cell(st, px, py, &oi, &oj);
  for (int i = st->c + oi - rr; i <= st->c + oi + rr; i++)
    for (int j = st->c + oj - rr; j <= st->c + oj + rr; j++) {
      if (!c5_in(st, i, j)) continue;
      const double x = st->gx0 + (i - st->c) * st->h - px, y = st->gy0 + (j - st->c) * st->h - py;
      const double hl = exp(-(x * x + y * y) / (2.0 * sig * sig));
      const double add = st->Pv[i * N + j] * st->ratio * hl;
      st->Pv[i * N + j] += add; st->tot += add;
      if (st->ratio_d > 0.0) { const double ad = st->Pd[i * N + j] * st->ratio_d * hl; st->Pd[i * N + j] += ad; st->tot += ad; }
    }
  if (P_(k, 22, 0.0) > 0.0) c5_trk_push(k, st, t - k->d_min, px, py);
  if (st->tot > 1e200) c5_normalize(k, st);
  if (!c5_idle(k, st)) c5_tap(k, st, t);
}
static void c5_wake(Ctl *k, double t) {
  C5St *st = k->st;
  const int N = st->N, M = st->M, W2 = 2 * M + 1;
  const double dt = P_(k, 11, 0.25);
  c5_process_clicks(k, st, t);
  double bx, by;
  c5_pos_at(k, st, 0.5 * (st->t_last + t), &bx, &by);
  int oi, oj;
  c5_body_cell(st, bx, by, &oi, &oj);
  for (int u = st->emin; u <= st->emax; u++) {
    const int i = st->c + oi + u;
    if (i < 0 || i >= N) continue;
    for (int v = st->emin; v <= st->emax; v++) {
      const int j = st->c + oj + v;
      if (j < 0 || j >= N) continue;
      const double old = st->Pv[i * N + j], nw = old * st->E[(u + M) * W2 + (v + M)];
      st->Pv[i * N + j] = nw; st->tot -= old - nw;
      if (st->damp > 0.0) {
        const double od = st->Pd[i * N + j], nd = od * st->Ed[(u + M) * W2 + (v + M)];
        st->Pd[i * N + j] = nd; st->tot -= od - nd;
      }
    }
  }
  const double tr = P_(k, 7, 50.0), hz = tr > 0.0 ? 1.0 - exp(-dt / tr) : 0.0;
  if (st->blink) {
    const double a = 1.0 - exp(-dt / P_(k, 9, 20.0)), b = st->flash ? 0.0 : 1.0 - exp(-dt / P_(k, 10, 20.0));
    for (int i = 0; i < N * N; i++) {
      const double v = st->Pv[i], d = st->Pd[i];
      st->Pv[i] = (1.0 - a) * v + b * d; st->Pd[i] = a * v + (1.0 - b) * d;
    }
  }
  if (hz > 0.0) {
    double md = 0.0;
    if (st->blink) for (int i = 0; i < N * N; i++) md += st->Pd[i];
    const double mv = st->tot - md;
    const double f = hz / (1.0 - hz);
    double cx, cy;
    ctl_eff_pos(k, t, &cx, &cy);
    if (st->flash) c5_place(st, cx, cy, f * (mv + md), 0.0);
    else c5_place(st, cx, cy, f * mv, f * md);
  }
  const double vt = P_(k, 3, 0.1);
  st->var_acc += vt * vt * P_(k, 4, 5.0) * dt;
  if (t - st->t_blur >= P_(k, 14, 1.0)) { c5_blur(st); st->t_blur = t; }
  c5_normalize(k, st);
  c5_recentre(k, st);
  st->t_last = t;
  c5_hist_push(k, st, t);
  c5_best(k, st);
  if (P_(k, 22, 0.0) > 0.0) c5_velocity(k, st, t, dt);
  k->diag[14] += 1.0;
  if (c5_idle(k, st)) { k->diag[11] += 1.0; ctl_wake(k, t + dt); return; }
  c5_tap(k, st, t);
  c5_steer(k, st, t);
  ctl_wake(k, t + dt);
}
static void c5_fini(Ctl *k) {
  C5St *st = k->st;
  if (st) { free(st->Pv); free(st->Pd); free(st->tmp); free(st->sat); free(st->E); free(st->Ed); free(st->ann); free(st->disk); free(st); }
}
static const CtlDef CTL_C5 = {1102, "C5 Bayes memory tracker", c5_init, c5_ping, c5_wake, c5_fini};
CTL_REGISTER(CTL_C5)
