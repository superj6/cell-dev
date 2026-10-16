/* ABI5 scratch information instrument. No world truth, reward or seed API.
 * Ctl is opaque. This header exposes only fixed footprint/physics, supplied parameters,
 * observed ping callbacks, own clock, and own action models. It is not an organism API. */
#ifndef CTL_API_H
#define CTL_API_H
#include <stdint.h>
#define CTL_NDIAG 16
#define CTL_MAXDEF 32
typedef struct Ctl Ctl;
typedef struct {
  int id; const char *name;
  int (*init)(Ctl *);
  void (*ping)(Ctl *, double, int);
  void (*wake)(Ctl *, double);
  void (*fini)(Ctl *);
} CtlDef;
typedef struct {
  // ---- footprint (read-only); positions are planar offsets in the body frame (LIFE_ABI 4.3)
  int n_sense, n_act, hot;            // hot: act index of the hotspot (0, 0, 1), -1 if the footprint lacks it
  int centre;                         // sense index of (0, 0, 0), -1 if absent
  const int32_t *sense_ab, *act_ab;   // [n][2] (a, b)
  const double *sense_xy, *act_xy;    // [n][2]
  const double *act_face;             // [n_act][2] exposed face (sum of unit vectors to empty act-plane sites) at t0
  int64_t n_fill;                     // filled footprint at t0 (drag gam = n_fill ^ drag_exp)
  // ---- body physics constants (the same in every life of a world family; not per-life hidden state)
  double t0, T, latency, t_ref_min, tau_z, g_n, gam, th_click, th_rel, d_min, d0;
  // ---- parameters
  const double *p; int np;            // this life's parameter vector
  const double *extra; int n_extra;   // shared extra array (same for every life of the call)
  int quant;                          // 1 = ctl_fire rounds kappa up to the GRN grid {0.25, 0.5, 1}
} CtlInfo;
const CtlInfo *ctl_public(const Ctl *k);
void *ctl_state(const Ctl *k);
void ctl_set_state(Ctl *k, void *state);
void ctl_diagnostic(Ctl *k, int slot, double value); /* write-only slots 5..15 */
double ctl_now(const Ctl *k);
double ctl_fire(Ctl *k, int act, double kappa, double requested_time);
double ctl_wake(Ctl *k, double time);
double ctl_last_fire(const Ctl *k, int act);
double ctl_twitch(const Ctl *k, int act, double time);
int ctl_key_armed(const Ctl *k);
int ctl_tap_would_click(const Ctl *k, double kappa, double time);
/* Own commanded displacement, including past emission times; never reads true position. */
void ctl_eff_pos(Ctl *k, double time, double *x, double *y);
void ctl_eff_final(Ctl *k, double *x, double *y);
double ctl_next_impulse_after(const Ctl *k, double time); /* own commanded history only */
void ctl_pending_disp(Ctl *k, double time, double *x, double *y);
int ctl_steer(Ctl *k, double dx, double dy, double time, double kmax, double align, double tol);
void ctl_register(const CtlDef *definition);
#define CTL_REGISTER(def) \
  __attribute__((constructor)) static void ctl_reg_##def(void) { ctl_register(&def); }
#endif
