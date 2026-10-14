// Built-in controllers of the central-controller harness. Each one: a state struct, callbacks, a CtlDef and
// CTL_REGISTER. Parameter layouts are documented per controller and mirrored in harness.py (CONTROLLERS).
#include "ctl_api.h"

static double P_(const Ctl *k, int i, double dflt) { return i < k->np ? k->p[i] : dflt; }

// =========================================================================================== 0: null
// Never acts: the footprint's living cost only. Used by the stream-equality test.
static const CtlDef CTL_NULL = {0, "null", NULL, NULL, NULL, NULL};
CTL_REGISTER(CTL_NULL)

// =========================================================================================== 1: C0 central reflex
// Information-matched. Each sense column's ping drives that column's act cell (if the footprint has one) and the
// centre's pings drive the hotspot tap, the way reflex@hollow3 does (one hop of latency, refractoriness per column).
// p: [0] kappa_m (1.0)  [1] refr_m (0.5): a column ignores pings for refr_m after a triggering ping
//    [2] kappa_tap (1.0)  [3] refr_tap (4.0): the centre ignores pings for refr_tap after a tap trigger
//    [4] n_coinc (1): centre pings within [5] win_coinc (1.0) needed to tap   [6] centre_steer (0): centre pings
//    also stroke the hotspot cell's own column (its face is 0 in a full disk, so this is a no-op there)
typedef struct { int *col; double *last; double last_tap; double *cq; int ncq; } C0St;
static int c0_init(Ctl *k) {
  C0St *st = calloc(1, sizeof(C0St));
  if (!st) return -1;
  st->col = malloc(sizeof(int) * (k->n_sense + 1)); st->last = malloc(sizeof(double) * (k->n_sense + 1));
  st->cq = calloc(64, sizeof(double));
  if (!st->col || !st->last || !st->cq) return -1;
  for (int s = 0; s < k->n_sense; s++) {
    st->col[s] = -1; st->last[s] = -INFINITY;
    for (int a = 0; a < k->n_act; a++)
      if (k->act_ab[2 * a] == k->sense_ab[2 * s] && k->act_ab[2 * a + 1] == k->sense_ab[2 * s + 1]) st->col[s] = a;
  }
  st->last_tap = -INFINITY;
  k->st = st;
  return 0;
}
static void c0_ping(Ctl *k, double t, int s) {
  C0St *st = k->st;
  if (s == k->centre) {
    int nc = (int)P_(k, 4, 1.0);
    if (nc < 1) nc = 1;
    if (nc > 64) nc = 64;
    const double win = P_(k, 5, 1.0);
    for (int i = 63; i > 0; i--) st->cq[i] = st->cq[i - 1];
    st->cq[0] = t;
    st->ncq++;
    int cnt = 0;
    for (int i = 0; i < 64 && i < st->ncq; i++) if (t - st->cq[i] <= win) cnt++;
    if (cnt >= nc && t >= st->last_tap + P_(k, 3, 4.0) && k->hot >= 0) {
      st->last_tap = t;
      ctl_fire(k, k->hot, P_(k, 2, 1.0), t);
    }
    if (P_(k, 6, 0.0) == 0.0) return;
  }
  const int a = st->col[s];
  if (a < 0 || a == k->hot) return;
  if (t < st->last[s] + P_(k, 1, 0.5)) return;
  st->last[s] = t;
  ctl_fire(k, a, P_(k, 0, 1.0), t);
}
static void c0_fini(Ctl *k) {
  C0St *st = k->st;
  if (st) { free(st->col); free(st->last); free(st->cq); free(st); }
}
static const CtlDef CTL_C0 = {1, "C0 central reflex", c0_init, c0_ping, NULL, c0_fini};
CTL_REGISTER(CTL_C0)

// =========================================================================================== 2: C1 privileged pursuit
// Privileged (the ceiling's measuring stick). Every dt it reads the truth, steers so that the dot's eventual position
// (current drift + pending strokes) lands on the target extrapolated by lead + latency, sets the motor sign from the
// true flip state at the stroke time, and taps the hotspot when the predicted dot-target distance at the stroke time
// is within tap_r * rho_c and the key will click. It never taps near a present, 'on', negative blob 1 unless the
// target is also predicted inside the capture radius.
// p: [0] dt (0.25)  [1] gain (1.0)  [2] lead (1.0)  [3] kmax (1.0)  [4] min_align (0.5)  [5] tol (0.15)
//    [6] tap_r (0.8)  [7] tap_kappa (1.0)  [8] use_dark (1: truth also while the target is dark; 0: while dark it
//    extrapolates the last seen position and velocity - a 'perfect sensing + memory' ceiling)  [9] chase_food (1)
//    [10] poison_margin (0.3)  [11] hold_r (0.0): no steering when the target is within hold_r (lets it drift in)
typedef struct { double lx, ly, lvx, lvy, lt; int seen; } C1St;
static int c1_init(Ctl *k) {
  C1St *st = calloc(1, sizeof(C1St));
  if (!st) return -1;
  k->st = st;
  ctl_wake(k, k->t0);
  return 0;
}
static void c1_wake(Ctl *k, double t) {
  C1St *st = k->st;
  CtlTruth tr;
  if (!ctl_truth(k, &tr)) return;
  const double lat = k->latency, dt = P_(k, 0, 0.25), gain = P_(k, 1, 1.0), lead = P_(k, 2, 1.0);
  const double ta = t + lat;
  ctl_set_motor_sign(k, ta >= tr.t_flip ? -1.0 : 1.0);
  // the target as the controller knows it (absolute screen coordinates)
  double gx, gy, gvx, gvy, rho = tr.rho_c;
  if (P_(k, 8, 1.0) != 0.0 || tr.visible) {
    gx = tr.X + tr.dx; gy = tr.Y + tr.dy; gvx = tr.vx; gvy = tr.vy;
    st->lx = gx; st->ly = gy; st->lvx = gvx; st->lvy = gvy; st->lt = t; st->seen = 1;
  } else if (st->seen) {
    gx = st->lx + st->lvx * (t - st->lt); gy = st->ly + st->lvy * (t - st->lt); gvx = st->lvx; gvy = st->lvy;
  } else {
    ctl_wake(k, t + dt);
    return;
  }
  // a positive second blob that is nearer is the goal instead
  const int b1_live = tr.b1_exists && tr.b1_present && tr.b1_on;
  if (P_(k, 9, 1.0) != 0.0 && b1_live && tr.b1_value > 0.0) {
    const double d0 = (gx - tr.X) * (gx - tr.X) + (gy - tr.Y) * (gy - tr.Y);
    const double d1 = tr.b1_dx * tr.b1_dx + tr.b1_dy * tr.b1_dy;
    if (d1 < d0) { gx = tr.X + tr.b1_dx; gy = tr.Y + tr.b1_dy; gvx = tr.b1_vx; gvy = tr.b1_vy; rho = tr.b1_rho; }
  }
  // eventual position of the dot with no new stroke: current drift + every pending stroke
  double px, py;
  ctl_pending_disp(k, INFINITY, &px, &py);
  const double ex = tr.X + tr.Fx * k->tau_z / tr.gam + px, ey = tr.Y + tr.Fy * k->tau_z / tr.gam + py;
  const double h = lat + lead;
  const double ox = gx + gvx * h - ex, oy = gy + gvy * h - ey;
  const double hr = P_(k, 11, 0.0);
  const double rx = gx - tr.X, ry = gy - tr.Y;
  if (!(hr > 0.0 && rx * rx + ry * ry < hr * hr))
    ctl_steer(k, gain * ox, gain * oy, t, P_(k, 3, 1.0), P_(k, 4, 0.5), P_(k, 5, 0.15));
  // tap: predicted distance at the stroke time
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
      int ok = 1;
      if (b1_live && tr.b1_value < 0.0) {  // poison check: only when the target is not surely inside the radius
        const double bx = tr.X + tr.b1_dx + tr.b1_vx * (tt - t) - dxa, by = tr.Y + tr.b1_dy + tr.b1_vy * (tt - t) - dya;
        const double pr = tr.b1_rho + P_(k, 10, 0.3);
        if (bx * bx + by * by <= pr * pr && tgx * tgx + tgy * tgy > 0.25 * rho * rho) ok = 0;
      }
      if (ok) ctl_fire(k, k->hot, tk, tt);
    }
  }
  ctl_wake(k, t + dt);
}
static void c1_fini(Ctl *k) { free(k->st); }
static const CtlDef CTL_C1 = {2, "C1 privileged pursuit", c1_init, NULL, c1_wake, c1_fini};
CTL_REGISTER(CTL_C1)

// =========================================================================================== 3: C2 generic tracker
// Information-matched. Pings are stored in the efference frame (where the controller thinks it was when each ping
// arrived: its own commanded displacement + the sense cell's offset), weighted by exp(-age / tau_f) (and by a
// multiplier that a commanded click scales by `reset`). The target estimate is the background-subtracted centroid;
// it steers the dot's eventual commanded position onto it and taps when the evidence is strong and centred.
// p: [0] tau_f (3.0)  [1] bg (0.05: background pings per sense cell per unit, subtracted at the body's centroid)
//    [2] gain (1.0)  [3] tol (0.2)  [4] r_tap (0.5)  [5] s_tap (1.5)  [6] dt (0.25)  [7] kmax (1.0)
//    [8] reset (0.0)  [9] s_steer (0.5)  [10] c_tap (0 = off: tap when the centre cell's own evidence >= c_tap)
//    [11] min_align (0.5)  [12] t_keep (8 * tau_f)  [13] search_step (0 = off): with too little evidence to steer,
//    each wake commands an eventual displacement of search_step along a heading that turns by [14] search_turn
//    (radians per wake) - a blind arc / spiral search
#define C2_CAP 16384
typedef struct { int n, head; double t[C2_CAP], x[C2_CAP], y[C2_CAP], m[C2_CAP]; int s[C2_CAP]; double cx, cy, th; } C2St;
static int c2_init(Ctl *k) {
  C2St *st = calloc(1, sizeof(C2St));
  if (!st) return -1;
  for (int s = 0; s < k->n_sense; s++) { st->cx += k->sense_xy[2 * s]; st->cy += k->sense_xy[2 * s + 1]; }
  if (k->n_sense > 0) { st->cx /= k->n_sense; st->cy /= k->n_sense; }
  k->st = st;
  ctl_wake(k, k->t0);
  return 0;
}
static void c2_prune(Ctl *k, C2St *st, double t) {
  const double keep = P_(k, 12, 8.0 * P_(k, 0, 3.0));
  while (st->n > 0 && t - st->t[st->head] > keep) { st->head = (st->head + 1) % C2_CAP; st->n--; }
}
// returns the excess evidence; *ex, *ey the estimate (efference frame), *cen the centre cell's evidence
static double c2_est(Ctl *k, C2St *st, double t, double *ex, double *ey, double *cen) {
  const double tau = P_(k, 0, 3.0);
  double S = 0.0, Mx = 0.0, My = 0.0, C = 0.0;
  for (int j = 0; j < st->n; j++) {
    const int i = (st->head + j) % C2_CAP;
    const double w = st->m[i] * exp(-(t - st->t[i]) / tau);
    S += w; Mx += w * st->x[i]; My += w * st->y[i];
    if (st->s[i] == k->centre) C += w;
  }
  double bx, by;
  ctl_eff_pos(k, t, &bx, &by);
  double B = P_(k, 1, 0.05) * k->n_sense * tau;
  if (B < 0.0) B = 0.0;
  const double Sx = S - B;
  *cen = C;
  if (Sx > 1e-9) { *ex = (Mx - B * (bx + st->cx)) / Sx; *ey = (My - B * (by + st->cy)) / Sx; }
  else { *ex = bx; *ey = by; }
  return Sx;
}
static void c2_decide(Ctl *k, C2St *st, double t, int is_wake) {
  c2_prune(k, st, t);
  double ex, ey, cen;
  const double Sx = c2_est(k, st, t, &ex, &ey, &cen);
  if (Sx >= P_(k, 9, 0.5)) {
    double fx, fy;
    ctl_eff_final(k, &fx, &fy);
    const double g = P_(k, 2, 1.0);
    ctl_steer(k, g * (ex - fx), g * (ey - fy), t, P_(k, 7, 1.0), P_(k, 11, 0.5), P_(k, 3, 0.2));
  } else if (is_wake && P_(k, 13, 0.0) > 0.0) {
    st->th += P_(k, 14, 0.0);
    const double sp = P_(k, 13, 0.0);
    ctl_steer(k, sp * cos(st->th), sp * sin(st->th), t, P_(k, 7, 1.0), P_(k, 11, 0.5), 0.5 * sp);
  }
  if (k->hot >= 0) {
    const double ta = t + k->latency;
    double ax, ay;
    ctl_eff_pos(k, ta, &ax, &ay);
    const double d2 = (ex - ax) * (ex - ax) + (ey - ay) * (ey - ay), r = P_(k, 4, 0.5), ct = P_(k, 10, 0.0);
    const int go = (Sx >= P_(k, 5, 1.5) && d2 <= r * r) || (ct > 0.0 && cen >= ct);
    if (go && ctl_tap_would_click(k, 1.0, ta)) {
      const double before = k->diag[3];
      ctl_fire(k, k->hot, 1.0, t);
      if (k->diag[3] > before) {  // a commanded click: discount the evidence it was based on
        const double rs = P_(k, 8, 0.0);
        for (int j = 0; j < st->n; j++) st->m[(st->head + j) % C2_CAP] *= rs;
      }
    }
  }
}
static void c2_ping(Ctl *k, double t, int s) {
  C2St *st = k->st;
  double bx, by;
  ctl_eff_pos(k, t, &bx, &by);
  if (st->n == C2_CAP) { st->head = (st->head + 1) % C2_CAP; st->n--; }
  const int i = (st->head + st->n) % C2_CAP;
  st->t[i] = t; st->x[i] = bx + k->sense_xy[2 * s]; st->y[i] = by + k->sense_xy[2 * s + 1]; st->m[i] = 1.0;
  st->s[i] = s;
  st->n++;
  c2_decide(k, st, t, 0);
}
static void c2_wake(Ctl *k, double t) {
  c2_decide(k, k->st, t, 1);
  ctl_wake(k, t + P_(k, 6, 0.25));
}
static void c2_fini(Ctl *k) { free(k->st); }
static const CtlDef CTL_C2 = {3, "C2 generic tracker", c2_init, c2_ping, c2_wake, c2_fini};
CTL_REGISTER(CTL_C2)

// =========================================================================================== 4: C3 tiny RNN
// Information-matched weights-vector hook. Every dt: x = [ping counts per sense cell since the last tick,
// key armed (own model), hotspot twitch (own model)]; h = tanh(W_in x + W_h h + b_h); o = W_o h + b_o; act cell a
// strokes with kappa min(1, o_a) when o_a > thr.
// p: [0] n_h  [1] dt  [2] thr  then W_in [n_h][n_sense + 2], W_h [n_h][n_h], b_h [n_h], W_o [n_act][n_h], b_o [n_act]
// (harness.rnn_size(footprint, n_h) gives the length).
typedef struct { int nh, nin; double *cnt, *h, *h2, *x; } C3St;
static int c3_init(Ctl *k) {
  const int nh = (int)P_(k, 0, 0.0), nin = k->n_sense + 2;
  const int need = 3 + nh * nin + nh * nh + nh + k->n_act * nh + k->n_act;
  if (nh < 1 || k->np < need) return -1;
  C3St *st = calloc(1, sizeof(C3St));
  if (!st) return -1;
  st->nh = nh; st->nin = nin;
  st->cnt = calloc(k->n_sense + 1, sizeof(double)); st->h = calloc(nh, sizeof(double));
  st->h2 = calloc(nh, sizeof(double)); st->x = calloc(nin, sizeof(double));
  if (!st->cnt || !st->h || !st->h2 || !st->x) return -1;
  k->st = st;
  ctl_wake(k, k->t0 + P_(k, 1, 0.5));
  return 0;
}
static void c3_ping(Ctl *k, double t, int s) { (void)t; ((C3St *)k->st)->cnt[s] += 1.0; }
static void c3_wake(Ctl *k, double t) {
  C3St *st = k->st;
  const int nh = st->nh, nin = st->nin;
  const double *W_in = k->p + 3, *W_h = W_in + nh * nin, *b_h = W_h + nh * nh, *W_o = b_h + nh, *b_o = W_o + k->n_act * nh;
  for (int s = 0; s < k->n_sense; s++) st->x[s] = st->cnt[s];
  st->x[k->n_sense] = ctl_key_armed(k);
  st->x[k->n_sense + 1] = k->hot >= 0 ? ctl_twitch(k, k->hot, t) : 0.0;
  for (int i = 0; i < nh; i++) {
    double v = b_h[i];
    for (int j = 0; j < nin; j++) v += W_in[i * nin + j] * st->x[j];
    for (int j = 0; j < nh; j++) v += W_h[i * nh + j] * st->h[j];
    st->h2[i] = tanh(v);
  }
  memcpy(st->h, st->h2, sizeof(double) * nh);
  const double thr = P_(k, 2, 0.5);
  for (int a = 0; a < k->n_act; a++) {
    double o = b_o[a];
    for (int j = 0; j < nh; j++) o += W_o[a * nh + j] * st->h[j];
    if (o > thr) ctl_fire(k, a, o > 1.0 ? 1.0 : o, t);
  }
  for (int s = 0; s < k->n_sense; s++) st->cnt[s] = 0.0;
  ctl_wake(k, t + P_(k, 1, 0.5));
}
static void c3_fini(Ctl *k) {
  C3St *st = k->st;
  if (st) { free(st->cnt); free(st->h); free(st->h2); free(st->x); free(st); }
}
static const CtlDef CTL_C3 = {4, "C3 tiny RNN", c3_init, c3_ping, c3_wake, c3_fini};
CTL_REGISTER(CTL_C3)

// =========================================================================================== 99: replay
// Test tool: p = [n, (t_rel, act index, kappa) x n]; schedules every stroke at t0 + t_rel from init. Run it with
// latency ~0 and t_ref_min 0 to replay a tissue body's act-plane raster exactly.
static int rp_init(Ctl *k) {
  const int n = (int)P_(k, 0, 0.0);
  if (k->np < 1 + 3 * n) return -1;
  for (int i = 0; i < n; i++) ctl_fire(k, (int)k->p[1 + 3 * i + 1], k->p[1 + 3 * i + 2], k->t0 + k->p[1 + 3 * i]);
  return 0;
}
static const CtlDef CTL_REPLAY = {99, "replay", rp_init, NULL, NULL, NULL};
CTL_REGISTER(CTL_REPLAY)

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
#define C4_HIST 64
typedef struct {
  int N, c, M, nm, ndisk, blink, flash;
  double h, gx0, gy0, var_acc, t_blur, t_last;
  double *Pv, *Pd, *tmp, *sat, *E, *ann, ratio, sig4, tot;  // tot: current total mass (Pv + Pd)
  int amin, amax, emin, emax;     // offset supports: annulus template, no-ping factor E (E < 1 only inside)
  int *disk;                      // offsets (du, dv) within rho_c
  double clk[64]; int nclk;       // pending commanded click times
  double ht[C4_HIST], hx[C4_HIST], hy[C4_HIST]; int hn, hh;  // efference history (t, x, y)
} C4St;
static inline int c4_in(const C4St *st, int i, int j) { return i >= 0 && j >= 0 && i < st->N && j < st->N; }
static void c4_hist_push(Ctl *k, C4St *st, double t) {
  double x, y;
  ctl_eff_pos(k, t, &x, &y);
  const int i = (st->hh + st->hn) % C4_HIST;
  st->ht[i] = t; st->hx[i] = x; st->hy[i] = y;
  if (st->hn < C4_HIST) st->hn++; else st->hh = (st->hh + 1) % C4_HIST;
}
static void c4_pos_at(Ctl *k, C4St *st, double t, double *x, double *y) {  // efference position at a past time t
  if (t >= ctl_now(k)) { ctl_eff_pos(k, t, x, y); return; }
  double pt = ctl_now(k), px, py;
  ctl_eff_pos(k, pt, &px, &py);
  for (int q = st->hn - 1; q >= 0; q--) {
    const int i = (st->hh + q) % C4_HIST;
    if (st->ht[i] <= t) {
      const double w = pt > st->ht[i] ? (t - st->ht[i]) / (pt - st->ht[i]) : 0.0;
      *x = st->hx[i] + w * (px - st->hx[i]); *y = st->hy[i] + w * (py - st->hy[i]);
      return;
    }
    pt = st->ht[i]; px = st->hx[i]; py = st->hy[i];
  }
  *x = px; *y = py;
}
static void c4_body_cell(const C4St *st, double bx, double by, int *oi, int *oj) {
  *oi = (int)lround((bx - st->gx0) / st->h); *oj = (int)lround((by - st->gy0) / st->h);
}
static void c4_place(C4St *st, double bx, double by, double mv, double md) {  // add placement mass around (bx, by)
  int oi, oj;
  c4_body_cell(st, bx, by, &oi, &oj);
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
static void c4_normalize(Ctl *k, C4St *st) {
  double s = 0.0;
  const int NN = st->N * st->N;
  for (int i = 0; i < NN; i++) s += st->Pv[i] + (st->blink ? st->Pd[i] : 0.0);
  if (!(s > 1e-280) || !isfinite(s)) {  // lost track: restart from the placement prior around the dot
    memset(st->Pv, 0, sizeof(double) * NN);
    if (st->blink) memset(st->Pd, 0, sizeof(double) * NN);
    double bx, by;
    ctl_eff_pos(k, ctl_now(k), &bx, &by);
    st->tot = 0.0;
    c4_place(st, bx, by, 1.0, 0.0);
    k->diag[9] += 1.0;
    return;
  }
  const double r = 1.0 / s;
  for (int i = 0; i < NN; i++) { st->Pv[i] *= r; if (st->blink) st->Pd[i] *= r; }
  st->tot = 1.0;
}
static void c4_recentre(Ctl *k, C4St *st) {
  double bx, by;
  ctl_eff_pos(k, ctl_now(k), &bx, &by);
  int oi, oj;
  c4_body_cell(st, bx, by, &oi, &oj);
  if (abs(oi) <= st->N / 6 && abs(oj) <= st->N / 6) return;
  const int N = st->N;
  for (int g = 0; g < 1 + st->blink; g++) {
    double *P = g ? st->Pd : st->Pv;
    for (int i = 0; i < N; i++)
      for (int j = 0; j < N; j++) {
        const int si = i + oi, sj = j + oj;
        st->tmp[i * N + j] = c4_in(st, si, sj) ? P[si * N + sj] : 0.0;
      }
    memcpy(P, st->tmp, sizeof(double) * N * N);
  }
  st->gx0 += oi * st->h; st->gy0 += oj * st->h;
  c4_normalize(k, st);  // mass shifted off the grid is dropped
}
static void c4_blur(C4St *st) {
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
static void c4_capture(Ctl *k, C4St *st, double tc) {  // a commanded click at tc: mass under the dot is re-placed
  double bx, by;
  c4_pos_at(k, st, tc, &bx, &by);
  int oi, oj;
  c4_body_cell(st, bx, by, &oi, &oj);
  double mv = 0.0, md = 0.0;
  for (int q = 0; q < st->ndisk; q++) {
    const int i = st->c + oi + st->disk[2 * q], j = st->c + oj + st->disk[2 * q + 1];
    if (!c4_in(st, i, j)) continue;
    mv += st->Pv[i * st->N + j]; st->Pv[i * st->N + j] = 0.0;
    if (st->blink) { md += st->Pd[i * st->N + j]; st->Pd[i * st->N + j] = 0.0; }
  }
  st->tot -= mv + md;
  if (st->flash) c4_place(st, bx, by, mv + md, 0.0);
  else c4_place(st, bx, by, mv, md);
}
static double c4_mass_at(const C4St *st, double x, double y) {  // posterior mass within rho_c of (x, y)
  int oi, oj;
  c4_body_cell(st, x, y, &oi, &oj);
  double m = 0.0;
  for (int q = 0; q < st->ndisk; q++) {
    const int i = st->c + oi + st->disk[2 * q], j = st->c + oj + st->disk[2 * q + 1];
    if (!c4_in(st, i, j)) continue;
    m += st->Pv[i * st->N + j] + (st->blink ? st->Pd[i * st->N + j] : 0.0);
  }
  return st->tot > 0.0 ? m / st->tot : 0.0;
}
static void c4_process_clicks(Ctl *k, C4St *st, double t) {
  int w = 0;
  for (int q = 0; q < st->nclk; q++) {
    if (st->clk[q] <= t) c4_capture(k, st, st->clk[q]);
    else st->clk[w++] = st->clk[q];
  }
  st->nclk = w;
}
static void c4_tap(Ctl *k, C4St *st, double t) {
  if (k->hot >= 0) {
    double ta = t + k->latency;
    const double lf = ctl_last_fire(k, k->hot) + k->t_ref_min;
    if (lf > ta) ta = lf;
    double ax, ay;
    ctl_eff_pos(k, ta, &ax, &ay);
    const double q = c4_mass_at(st, ax, ay);
    if (q >= P_(k, 19, 0.3) && ctl_tap_would_click(k, 1.0, ta) && st->nclk < 64) {
      const double before = k->diag[3];
      const double tf = ctl_fire(k, k->hot, 1.0, t);
      if (k->diag[3] > before && tf > 0) st->clk[st->nclk++] = tf;
    }
  }
}
static void c4_steer(Ctl *k, C4St *st, double t) {
  const int N = st->N;
  const double gain = P_(k, 15, 1.0);
  if (gain <= 0.0) return;
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
static int c4_init(Ctl *k) {
  if (k->np < 21) return -1;
  C4St *st = calloc(1, sizeof(C4St));
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
  c4_place(st, 0.0, 0.0, 1.0, 0.0);  // the target is placed (visible) around the dot at t0
  c4_normalize(k, st);
  st->t_last = k->t0; st->t_blur = k->t0;
  c4_hist_push(k, st, k->t0);
  ctl_wake(k, k->t0 + dt);
  return 0;
}
static void c4_ping(Ctl *k, double t, int s) {
  C4St *st = k->st;
  c4_process_clicks(k, st, t);
  double bx, by;
  c4_pos_at(k, st, t - k->d_min, &bx, &by);  // the screen was read at the candidate time, d_min before delivery
  const double px = bx + k->sense_xy[2 * s], py = by + k->sense_xy[2 * s + 1], sig = P_(k, 0, 0.6);
  const int N = st->N, rr = (int)ceil(st->sig4 / st->h);
  int oi, oj;
  c4_body_cell(st, px, py, &oi, &oj);
  for (int i = st->c + oi - rr; i <= st->c + oi + rr; i++)
    for (int j = st->c + oj - rr; j <= st->c + oj + rr; j++) {
      if (!c4_in(st, i, j)) continue;
      const double x = st->gx0 + (i - st->c) * st->h - px, y = st->gy0 + (j - st->c) * st->h - py;
      const double add = st->Pv[i * N + j] * st->ratio * exp(-(x * x + y * y) / (2.0 * sig * sig));
      st->Pv[i * N + j] += add; st->tot += add;
    }
  if (st->tot > 1e200) c4_normalize(k, st);
  c4_tap(k, st, t);
}
static void c4_wake(Ctl *k, double t) {
  C4St *st = k->st;
  const int N = st->N, M = st->M, W2 = 2 * M + 1;
  const double dt = P_(k, 11, 0.25);
  c4_process_clicks(k, st, t);
  // no-ping evidence of the last tick at the mid-interval body position
  double bx, by;
  c4_pos_at(k, st, 0.5 * (st->t_last + t), &bx, &by);
  int oi, oj;
  c4_body_cell(st, bx, by, &oi, &oj);
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
    if (st->flash) c4_place(st, cx, cy, f * (mv + md), 0.0);
    else c4_place(st, cx, cy, f * mv, f * md);
  }
  // motion
  const double vt = P_(k, 3, 0.1);
  st->var_acc += vt * vt * P_(k, 4, 5.0) * dt;
  if (t - st->t_blur >= P_(k, 14, 1.0)) { c4_blur(st); st->t_blur = t; }
  c4_normalize(k, st);
  c4_recentre(k, st);
  st->t_last = t;
  c4_hist_push(k, st, t);
  c4_tap(k, st, t);
  c4_steer(k, st, t);
  ctl_wake(k, t + dt);
}
static void c4_fini(Ctl *k) {
  C4St *st = k->st;
  if (st) { free(st->Pv); free(st->Pd); free(st->tmp); free(st->sat); free(st->E); free(st->ann); free(st->disk); free(st); }
}
static const CtlDef CTL_C4 = {5, "C4 Bayes grid tracker", c4_init, c4_ping, c4_wake, c4_fini};
CTL_REGISTER(CTL_C4)
