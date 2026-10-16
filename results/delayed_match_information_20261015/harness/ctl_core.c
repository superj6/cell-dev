// Central-controller mode: harness core. #included at the end of ckernel.c (one translation unit with the kernel),
// so it uses the kernel's static functions and Ctx directly. Controllers see only ctl_api.h.
#include "ctl_api.h"
struct Ctl {
  CtlInfo v;
  void *st;
  double diag[CTL_NDIAG];
  void *_c; const CtlDef *_def;
  double _now, _sign;
  int32_t *_sense_site, *_act_site; uint64_t *_sense_uid, *_act_uid; int32_t _wake_site;
  double *_last, *_z, *_tz;           // per act cell: last scheduled stroke, commanded twitch after it, its time
  int _armed_cmd;                     // key state after every scheduled hotspot stroke
  double _ex, _ey, _gx, _gy, _te;     // efference anchor: commanded displacement and force at _te
  double *_pend; int _npend, _cappend; // scheduled strokes after _te: (t, fx, fy) sorted by t
  int64_t _n_wake_pending;
  int32_t *_buf_i; double *_buf_d;    // scratch for the shipped helpers
  int _charge;                        // 1: c_rec per ping (g_r 1); 2: + one relay spike (c_spike + c_msg)
};


// per-life configuration handed to run_one through the thread-local g_ctl_cfg (declared in the kernel patch)
struct CtlCfg {
  int32_t id;
  const double *p; int32_t np;
  double latency, t_ref_min;
  int32_t flags;            // CTL_F_* below
  const double *extra; int32_t n_extra;
  double *diag;             // [CTL_NDIAG] out
};
enum { CTL_F_CHARGE_REC = 2, CTL_F_CHARGE_RELAY = 4, CTL_F_QUANT = 8 };

static const CtlDef *ctl_defs[CTL_MAXDEF];
static int ctl_ndefs = 0;
void ctl_register(const CtlDef *d) {
  for (int i = 0; i < ctl_ndefs; i++)
    if (ctl_defs[i]->id == d->id) { ctl_defs[i] = d; return; }  // a later registration of an id replaces it
  if (ctl_ndefs < CTL_MAXDEF) ctl_defs[ctl_ndefs++] = d;
}
static const CtlDef *ctl_find(int id) {
  for (int i = 0; i < ctl_ndefs; i++)
    if (ctl_defs[i]->id == id) return ctl_defs[i];
  return NULL;
}

// ------------------------------------------------------------------------------------------ efference model
static void eff_advance(Ctl *k, double t) { (void)k; (void)t; }
static int eff_push(Ctl *k, double t, double fx, double fy) {
  if (k->_npend == k->_cappend) {
    int nc = k->_cappend ? 2 * k->_cappend : 64;
    double *q = realloc(k->_pend, (size_t)nc * 3 * sizeof(double));
    if (!q) return -1;
    k->_pend = q; k->_cappend = nc;
  }
  int i = k->_npend;
  while (i > 0 && k->_pend[3 * (i - 1)] > t) {
    memcpy(k->_pend + 3 * i, k->_pend + 3 * (i - 1), 3 * sizeof(double));
    i--;
  }
  k->_pend[3 * i] = t; k->_pend[3 * i + 1] = fx; k->_pend[3 * i + 2] = fy;
  k->_npend++;
  return 0;
}
void ctl_eff_pos(Ctl *k, double t, double *x, double *y) {
  double te = k->_te, ex = k->_ex, ey = k->_ey, gx = k->_gx, gy = k->_gy;
  if (t < te) t = te;
  for (int i = 0; i < k->_npend && k->_pend[3 * i] <= t; i++) {
    const double ti = k->_pend[3 * i];
    if (ti > te) {
      const double e = exp(-(ti - te) / k->v.tau_z), kk = k->v.tau_z * (1.0 - e) / k->v.gam;
      ex += gx * kk; ey += gy * kk; gx *= e; gy *= e; te = ti;
    }
    gx += k->_pend[3 * i + 1]; gy += k->_pend[3 * i + 2];
  }
  if (t > te) {
    const double e = exp(-(t - te) / k->v.tau_z), kk = k->v.tau_z * (1.0 - e) / k->v.gam;
    ex += gx * kk; ey += gy * kk;
  }
  *x = ex; *y = ey;
}
void ctl_eff_final(Ctl *k, double *x, double *y) {
  double ex = k->_ex, ey = k->_ey, kk = k->v.tau_z / k->v.gam;
  ex += k->_gx * kk; ey += k->_gy * kk;
  for (int i = 0; i < k->_npend; i++) { ex += k->_pend[3 * i + 1] * kk; ey += k->_pend[3 * i + 2] * kk; }
  *x = ex; *y = ey;
}
double ctl_next_impulse_after(const Ctl *k, double t) {
  for (int i = 0; i < k->_npend; i++) if (k->_pend[3*i] > t) return k->_pend[3*i];
  return INFINITY;
}
void ctl_pending_disp(Ctl *k, double t, double *x, double *y) {
  double sx = 0.0, sy = 0.0;
  for (int i = 0; i < k->_npend; i++) {
    const double ti = k->_pend[3 * i];
    if (ti < k->_now || ti >= t) continue;
    const double f = isinf(t) ? 1.0 : 1.0 - exp(-(t - ti) / k->v.tau_z), kk = k->v.tau_z * f / k->v.gam;
    sx += k->_pend[3 * i + 1] * kk; sy += k->_pend[3 * i + 2] * kk;
  }
  *x = sx; *y = sy;
}


// ----------------------------------------------------------------------------------------- actions
double ctl_now(const Ctl *k) { return k->_now; }
double ctl_last_fire(const Ctl *k, int a) { return (a >= 0 && a < k->v.n_act) ? k->_last[a] : -INFINITY; }
double ctl_twitch(const Ctl *k, int a, double t) {
  if (a < 0 || a >= k->v.n_act) return 0.0;
  if (t <= k->_tz[a]) return k->_z[a];
  return k->_z[a] * exp(-(t - k->_tz[a]) / k->v.tau_z);
}
int ctl_key_armed(const Ctl *k) { return k->_armed_cmd; }
int ctl_tap_would_click(const Ctl *k, double kappa, double t) {
  if (k->v.hot < 0) return 0;
  const double zt = ctl_twitch(k, k->v.hot, t);
  int armed = k->_armed_cmd;
  if (!armed && zt < k->v.th_rel) armed = 1;
  double zn = zt + kappa;
  if (zn > 1.0) zn = 1.0;
  return armed && zn >= k->v.th_click;
}
static double ctl_fire_time(const Ctl *k, int a, double t) {
  double tf = t, lo = k->_now + k->v.latency;
  if (tf < lo) tf = lo;
  if (k->_last[a] > -INFINITY && tf < k->_last[a] + k->v.t_ref_min) tf = k->_last[a] + k->v.t_ref_min;
  if (!(tf > k->_now)) tf = nextafter(k->_now, INFINITY);
  return tf;
}
double ctl_fire(Ctl *k, int a, double kappa, double t) {
  Ctx *c = (Ctx *)k->_c;
  if (a < 0 || a >= k->v.n_act || !(kappa > 0.0) || !isfinite(t)) { k->diag[4] += 1.0; return -1.0; }
  if (kappa > 1.0) kappa = 1.0;
  if (k->v.quant) kappa = kappa <= 0.25 ? 0.25 : (kappa <= 0.5 ? 0.5 : 1.0);
  const double tf = ctl_fire_time(k, a, t);
  if (tf >= k->v.t0 + k->v.T) { k->diag[4] += 1.0; return -1.0; }
  const double zt = k->_z[a] * exp(-(tf - k->_tz[a]) / k->v.tau_z);
  double zn = zt + kappa;
  if (zn > 1.0) zn = 1.0;
  const double dz = zn - zt;
  if (a == k->v.hot) {
    if (!k->_armed_cmd && zt < k->v.th_rel) k->_armed_cmd = 1;
    if (k->_armed_cmd && zn >= k->v.th_click) { k->_armed_cmd = 0; k->diag[3] += 1.0; }
  }
  const double fx = k->v.act_face[2 * a], fy = k->v.act_face[2 * a + 1];
  if (dz > 0.0 && (fx != 0.0 || fy != 0.0)) {
    const double g = k->_sign * k->v.g_n * dz;
    if (eff_push(k, tf, g * fx, g * fy)) c->fail |= FAIL_ALLOC;
  }
  k->_z[a] = zn; k->_tz[a] = tf; k->_last[a] = tf;
  int32_t ei;
  Ev *e = ev_make(c, &ei, tf, k->_act_site[a], G_EXO, X_FORCE);
  if (!e) return -1.0;
  e->uid = k->_act_uid[a]; e->u2 = 0; e->x[0] = kappa;
  push_ev(c, ei);
  k->diag[2] += 1.0;
  return tf;
}
double ctl_wake(Ctl *k, double t) {
  Ctx *c = (Ctx *)k->_c;
  double tw = t;
  const double lo = nextafter(k->_now, INFINITY);
  if (!(tw >= lo)) tw = lo;
  if (!isfinite(tw) || tw >= k->v.t0 + k->v.T) return -1.0;
  int32_t ei;
  Ev *e = ev_make(c, &ei, tw, k->_wake_site, G_EXO, X_WAKE);
  if (!e) return -1.0;
  e->uid = 0; e->u2 = 0;
  push_ev(c, ei);
  return tw;
}
int ctl_steer(Ctl *k, double dx, double dy, double t, double kmax, double min_align, double tol) {
  int n = 0;
  int32_t *used = k->_buf_i;
  double *tf = k->_buf_d, *head = k->_buf_d + k->v.n_act;  // per cell: earliest stroke time and twitch headroom there
  const double unit = k->_sign * k->v.g_n * k->v.tau_z / k->v.gam;  // eventual displacement per unit dz per unit face
  for (int a = 0; a < k->v.n_act; a++) {
    used[a] = k->v.act_face[2 * a] == 0.0 && k->v.act_face[2 * a + 1] == 0.0;
    if (used[a]) continue;
    tf[a] = ctl_fire_time(k, a, t);
    head[a] = 1.0 - ctl_twitch(k, a, tf[a]);
    if (head[a] < 0.02) used[a] = 1;
  }
  for (int it = 0; it < k->v.n_act; it++) {
    const double nd = sqrt(dx * dx + dy * dy);
    if (nd < tol) break;
    int best = -1;
    double best_red = 0.0, best_dz = 0.0;
    for (int a = 0; a < k->v.n_act; a++) {
      if (used[a]) continue;
      const double mx = unit * k->v.act_face[2 * a], my = unit * k->v.act_face[2 * a + 1];
      const double mm = sqrt(mx * mx + my * my), proj = (mx * dx + my * dy) / mm;
      if (proj < min_align * nd || proj <= 0.0) continue;
      double dz = proj / mm;
      if (dz > head[a]) dz = head[a];
      if (dz > kmax) dz = kmax;
      if (dz < 0.02) continue;
      const double red = dz * proj * mm;  // reduction of the error along its direction (approx.)
      if (red > best_red) { best_red = red; best = a; best_dz = dz; }
    }
    if (best < 0) break;
    const double zt = 1.0 - head[best];
    used[best] = 1;
    if (ctl_fire(k, best, best_dz, t) < 0.0) continue;
    const double dzr = k->_z[best] - zt;  // the twitch increment actually commanded (after quantization)
    dx -= dzr * unit * k->v.act_face[2 * best]; dy -= dzr * unit * k->v.act_face[2 * best + 1];
    n++;
  }
  return n;
}
// ----------------------------------------------------------------------------------- kernel-side hooks
static void ctl_free(Ctl *k) {
  if (!k) return;
  free((void *)k->v.sense_ab); free((void *)k->v.act_ab); free((void *)k->v.sense_xy); free((void *)k->v.act_xy);
  free((void *)k->v.act_face); free(k->_sense_site); free(k->_act_site); free(k->_sense_uid); free(k->_act_uid);
  free(k->_last); free(k->_z); free(k->_tz); free(k->_pend); free(k->_buf_i); free(k->_buf_d);
  free(k);
}
static int ctl_create(Ctx *c, const int32_t *init, int32_t n_init) {
  const struct CtlCfg *cfg = g_ctl_cfg;
  const CtlDef *def = ctl_find(cfg->id);
  if (!def) return -1;
  Ctl *k = calloc(1, sizeof(Ctl));
  if (!k) return -1;
  int ns = 0, na = 0;
  for (int32_t j = 0; j < n_init; j++) { ns += init[4 * j + 2] == 0; na += init[4 * j + 2] == 1; }
  int32_t *sab = malloc(sizeof(int32_t) * 2 * (ns + 1)), *aab = malloc(sizeof(int32_t) * 2 * (na + 1));
  double *sxy = malloc(sizeof(double) * 2 * (ns + 1)), *axy = malloc(sizeof(double) * 2 * (na + 1));
  double *face = calloc(2 * (na + 1), sizeof(double));
  k->_sense_site = malloc(sizeof(int32_t) * (ns + 1)); k->_act_site = malloc(sizeof(int32_t) * (na + 1));
  k->_sense_uid = malloc(sizeof(uint64_t) * (ns + 1)); k->_act_uid = malloc(sizeof(uint64_t) * (na + 1));
  k->_last = malloc(sizeof(double) * (na + 1)); k->_z = calloc(na + 1, sizeof(double));
  k->_tz = malloc(sizeof(double) * (na + 1)); k->_buf_i = calloc(na + ns + 1, sizeof(int32_t));
  k->_buf_d = calloc(2 * (na + ns + 1), sizeof(double));
  k->v.sense_ab = sab; k->v.act_ab = aab; k->v.sense_xy = sxy; k->v.act_xy = axy; k->v.act_face = face;
  if (!sab || !aab || !sxy || !axy || !face || !k->_sense_site || !k->_act_site || !k->_sense_uid || !k->_act_uid ||
      !k->_last || !k->_z || !k->_tz || !k->_buf_i || !k->_buf_d) { ctl_free(k); return -1; }
  k->v.hot = -1; k->v.centre = -1;
  int is = 0, ia = 0;
  for (int32_t j = 0; j < n_init; j++) {
    const int32_t a = init[4 * j], b = init[4 * j + 1], z = init[4 * j + 2];
    if (z > 1) continue;
    const uint64_t uid = hash1(c->seed, S_ZYG, (uint64_t)j) | 1ULL;
    const int32_t si = site_find(c, a, b, z);
    double ox, oy;
    planar(c, a, b, &ox, &oy);
    if (z == 0) {
      sab[2 * is] = a; sab[2 * is + 1] = b; sxy[2 * is] = ox; sxy[2 * is + 1] = oy;
      k->_sense_site[is] = si; k->_sense_uid[is] = uid;
      if (a == 0 && b == 0) k->v.centre = is;
      is++;
    } else {
      aab[2 * ia] = a; aab[2 * ia + 1] = b; axy[2 * ia] = ox; axy[2 * ia + 1] = oy;
      k->_act_site[ia] = si; k->_act_uid[ia] = uid;
      if (a == 0 && b == 0) k->v.hot = ia;
      ia++;
    }
  }
  k->v.n_sense = ns; k->v.n_act = na;
  for (int i = 0; i < na; i++) {  // exposed face at t0: in-plane neighbour sites of the act plane outside the footprint
    double nx = 0.0, ny = 0.0;
    for (int d = 0; d < c->nplane; d++) {
      const int32_t a2 = aab[2 * i] + c->off_a[d], b2 = aab[2 * i + 1] + c->off_b[d];
      int occ = 0;
      for (int q = 0; q < na; q++) if (aab[2 * q] == a2 && aab[2 * q + 1] == b2) { occ = 1; break; }
      if (!occ) { nx = nx + c->unit[3 * d]; ny = ny + c->unit[3 * d + 1]; }
    }
    face[2 * i] = nx; face[2 * i + 1] = ny;
    k->_last[i] = -INFINITY; k->_tz[i] = c->t0;
  }
  k->v.n_fill = c->n_fill; k->v.gam = c->gam;
  k->v.t0 = c->t0; k->v.T = c->T; k->v.latency = cfg->latency; k->v.t_ref_min = cfg->t_ref_min; k->v.tau_z = c->tau_z;
  k->v.g_n = c->g_n; k->v.th_click = c->th_click; k->v.th_rel = c->th_rel; k->v.d_min = c->d_min; k->v.d0 = c->d0;
  k->v.p = cfg->p; k->v.np = cfg->np; k->v.extra = cfg->extra; k->v.n_extra = cfg->n_extra;
  k->v.quant = 1;  // legal motor grid is mandatory in this harness
  k->_charge = ((cfg->flags & CTL_F_CHARGE_REC) ? 1 : 0) | ((cfg->flags & CTL_F_CHARGE_RELAY) ? 2 : 0);
  k->_c = c; k->_def = def; k->_now = c->t0; k->_sign = 1.0; k->_armed_cmd = 1; k->_te = c->t0;
  k->_wake_site = n_init > 0 ? site_find(c, init[0], init[1], init[2]) : 0;
  c->ctl = k;
  if (def->init && def->init(k)) return -1;
  return 0;
}
static void ctl_on_ping(Ctx *c, double t, int32_t si, uint64_t uid) {
  Ctl *k = (Ctl *)c->ctl;
  int s = -1;
  for (int i = 0; i < k->v.n_sense; i++) if (k->_sense_site[i] == si) { s = i; break; }
  if (s < 0) return;  // not a footprint sense cell (cannot happen: no births in controller mode)
  k->_now = t;
  eff_advance(k, t);
  k->diag[0] += 1.0;
  if (k->_charge & 1) {  // as a sense cell with g_r = 1 (LIFE_ABI 7.10): c_rec per delivered event
    Rec *rr = emit(c, R_RECEPT);
    if (rr) { rr->u1 = uid; rr->i1 = 1; rr->x[0] = 1.0; }
  }
  if (k->_charge & 2) {  // one relay spike of the sense cell to the plane above: c_spike + c_msg * 1, no twitch
    Rec *r = emit(c, R_SPIKE);
    if (r) { r->u1 = uid; r->x[0] = 0.0; r->i1 = 1; r->x[1] = 0.0; r->x[2] = 0.0; r->x[3] = 0.0; }
  }
  if (k->_def->ping) k->_def->ping(k, t, s);
}
static void ctl_on_wake(Ctx *c, double t) {
  Ctl *k = (Ctl *)c->ctl;
  k->_now = t;
  eff_advance(k, t);
  k->diag[1] += 1.0;
  if (k->_def->wake) k->_def->wake(k, t);
}
static void ctl_destroy(Ctx *c) {
  Ctl *k = (Ctl *)c->ctl;
  if (!k) return;
  if (k->_def && k->_def->fini) k->_def->fini(k);
  if (g_ctl_cfg && g_ctl_cfg->diag) memcpy(g_ctl_cfg->diag, k->diag, sizeof k->diag);
  ctl_free(k);
  c->ctl = NULL;
}

// ------------------------------------------------------------------------------------------------ exports
int32_t ctl_count(void) { return ctl_ndefs; }
int32_t ctl_info(int32_t i, char *name, int32_t cap) {  // id of registered controller i (and its name)
  if (i < 0 || i >= ctl_ndefs) return -1;
  if (name && cap > 0) { strncpy(name, ctl_defs[i]->name ? ctl_defs[i]->name : "", (size_t)cap - 1); name[cap - 1] = 0; }
  return ctl_defs[i]->id;
}

// life_run with a controller per life (program mode only, heap scheduler only). Extra return code -5: unknown
// controller id, a non-program life, a window scheduler, or latency < 0.
int32_t ctl_life_run(int32_t n_lives, int32_t threads, const int32_t *lat, const double *unit, int32_t n_programs,
                     const double *programs, const int32_t *genome_of, const int32_t *init_cells,
                     const int32_t *n_init, const double *world, const uint64_t *seeds, double *ledger,
                     uint64_t *hashes, int64_t raster_cap, double *raster_t, uint64_t *raster_uid, int64_t *raster_n,
                     int64_t fate_cap, int64_t *fate_i, double *fate_f, int64_t *fate_n,
                     const int32_t *ctl_id, const double *ctl_p, int32_t np, const double *ctl_lat,
                     const double *ctl_tref, const int32_t *ctl_flags, const double *extra, int32_t n_extra,
                     double *diag) {
  if (!ctl_lat || !ctl_tref) return -1;
  if (n_lives < 0 || !lat || !unit || !genome_of || !world || !seeds || !ledger || !hashes || !programs || !ctl_id)
    return -1;
  if (!lattice_ok(lat)) return -4;
  for (int32_t i = 0; i < n_lives; i++) {
    const double *w = world + (int64_t)i * WORLD_SIZE;
    if (!world_ok(w)) return -2;
    if (!(((int64_t)w[W_FLAGS]) & F_PROGRAM) || w[W_WINDOWH] != 0.0) return -5;
    if (!ctl_find(ctl_id[i]) || !(ctl_lat[i] >= w[W_D0]) || !isfinite(ctl_lat[i]) ||
        !(ctl_tref[i] >= 0.5) || !isfinite(ctl_tref[i]) || w[W_NOISE] != 0.0 ||
        (ctl_flags && (ctl_flags[i] & ~14))) return -5;
    const int32_t gi = genome_of[i];
    if (gi < 0 || gi >= n_programs) return -1;
    if (!row_finite(programs + (int64_t)gi * PROGRAM_SIZE, PROGRAM_SIZE)) return -1;
    const int32_t ni = n_init ? n_init[i] : 0;
    if (ni < 1 || ni > MAX_INIT || !init_cells) return -4;
    const int32_t *ic = init_cells + (int64_t)i * MAX_INIT * 4;
    const int32_t R = (int32_t)w[W_FABRICR], L_max = (int32_t)w[W_LMAX];
    uint64_t keys[MAX_INIT];
    for (int32_t j = 0; j < ni; j++) {
      const int32_t a = ic[4 * j], b = ic[4 * j + 1], z = ic[4 * j + 2], row = ic[4 * j + 3];
      if (row < -1 || row >= N_ROWS) return -4;
      if (z < 0 || z >= L_max || a < -COORD_MAX || a > COORD_MAX || b < -COORD_MAX || b > COORD_MAX) return -4;
      if (R > 0 && !in_disk(lat[0] % 3, a, b, R)) return -4;
      keys[j] = sitekey(a, b, z);
    }
    if (ni > 1) {
      qsort(keys, (size_t)ni, sizeof(uint64_t), key_cmp);
      for (int32_t j = 1; j < ni; j++)
        if (keys[j] == keys[j - 1]) return -4;
    }
  }
  if (threads != 1) return -5;
  if (raster_cap < 0) raster_cap = 0;
  if (fate_cap < 0) fate_cap = 0;
  int32_t rc = 0;
#pragma omp parallel for schedule(dynamic, 1) num_threads(threads)
  for (int32_t i = 0; i < n_lives; i++) {
    const double *w = world + (int64_t)i * WORLD_SIZE;
    const double *pg = programs + (int64_t)genome_of[i] * PROGRAM_SIZE;
    const int32_t ni = n_init[i];
    const int32_t *ic = init_cells + (int64_t)i * MAX_INIT * 4;
    const int rl = raster_cap > 0 && raster_t && raster_uid;
    const int fl = fate_cap > 0 && fate_i && fate_f;
    struct CtlCfg cfg = {ctl_id[i], ctl_p ? ctl_p + (int64_t)i * np : NULL, np, ctl_lat[i], ctl_tref[i],
                         ctl_flags ? ctl_flags[i] : 0, extra, n_extra, diag ? diag + (int64_t)i * CTL_NDIAG : NULL};
    g_ctl_cfg = &cfg;
    int r = run_one(lat, unit, NULL, pg, w, seeds + (int64_t)i * 4, ic, ni, ledger + (int64_t)i * LEDGER_SIZE,
                    hashes + (int64_t)i * HASH_SIZE, rl ? raster_cap : 0, rl ? raster_t + (int64_t)i * raster_cap : NULL,
                    rl ? raster_uid + (int64_t)i * raster_cap : NULL, raster_n ? raster_n + i : NULL,
                    fl ? fate_cap : 0, fl ? fate_i + (int64_t)i * fate_cap * FATE_I : NULL,
                    fl ? fate_f + (int64_t)i * fate_cap * FATE_F : NULL, fate_n ? fate_n + i : NULL);
    g_ctl_cfg = NULL;
    if (r) {
#pragma omp critical
      rc = r;
    }
  }
  return rc;
}

const CtlInfo *ctl_public(const Ctl *k) { return &k->v; }
void *ctl_state(const Ctl *k) { return k->st; }
void ctl_set_state(Ctl *k, void *state) { k->st = state; }
void ctl_diagnostic(Ctl *k, int slot, double value) {
  if (slot >= 5 && slot < CTL_NDIAG) k->diag[slot] = value;
}
