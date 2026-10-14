// Central-controller measuring stick: the API a controller sees (scratch harness; never part of the organism).
//
// A controller is a set of callbacks registered under an integer id (CTL_REGISTER below). The harness runs one
// life of the scratch kernel (ckernel.c = repo kernel.c + make_xkernel patches + controller mode) with a fixed
// footprint of inert program cells (sense plane z = 0, act plane z = 1), placed at t0 and charged c_live like any
// program body, and calls the controller:
//   init(k)            once at t0, after the footprint's births;
//   ping(k, t, s)      for every receptor event delivered to live sense cell s (index into k->sense_*), at its
//                      delivery time t (candidate time + d_min, exactly when a tissue sense cell would get it);
//   wake(k, t)         at every time the controller asked for with ctl_wake;
//   fini(k)            once at the end of the life (free k->st; write k->diag[5..15]).
// It acts only through ctl_fire: a stroke of one of its act cells at a time >= now + latency (now = the time of the
// callback that issued it). Strokes follow the kernel's unchanged physics (surface-normal pull, decaying twitch,
// flipped law after t_flip, hotspot key hysteresis and clicks).
//
// INFORMATION RULE. An information-matched controller (k->priv == 0) may use only: its pings, its own clock (callback
// times, wakes), its own past actions (and the harness's efference/twitch/key models of them, below), the
// footprint geometry, its parameters k->p / k->extra and the body-physics constants in this struct. It must not read
// anything else (in particular nothing through k->_c). ctl_truth returns 0 for it. A privileged controller
// (k->priv == 1) may also call ctl_truth.
#ifndef CTL_API_H
#define CTL_API_H
#include <stdint.h>

#define CTL_NDIAG 16       // per-life diagnostics returned to Python; [0..4] are the harness's, [5..15] yours
#define CTL_MAXDEF 512

typedef struct Ctl Ctl;

typedef struct {
  int id;
  const char *name;
  int (*init)(Ctl *k);                    // return 0 on success (nonzero: the life is flagged FAIL_ALLOC)
  void (*ping)(Ctl *k, double t, int s);  // may be NULL
  void (*wake)(Ctl *k, double t);         // may be NULL
  void (*fini)(Ctl *k);                   // may be NULL
} CtlDef;

typedef struct {  // privileged truth at the callback time (left limit: before any record at that instant)
  double t;
  double X, Y;            // the dot (body origin) on the screen
  double Fx, Fy, gam;     // total pull force now and the drag; the dot's free drift from now is F * tau_z / gam
  double dx, dy;          // target minus dot
  double vx, vy;          // target velocity
  int visible;            // 1 unless the target is dark (blink / flash)
  int flipped;            // 1 if strokes now follow the flipped (push) law
  double t_flip;          // absolute flip time (+inf if none)
  int b1_exists, b1_present, b1_on;    // second blob: exists (b2_amp > 0), present (placement draw), epoch on
  double b1_dx, b1_dy, b1_vx, b1_vy;   // blob 1 minus dot, and its velocity
  double b1_value, b1_rho, b1_amp, b1_sigma;
  int armed;              // the hotspot key
  double hot_z;           // hotspot cell's twitch now (0 if it is dead)
  int hot_alive, n_sense_alive, n_act_alive;
  double rho_c, sigma, lam_s, lam_bg, v_t, tau_turn, R_min, R_max, t_resp;  // world constants
} CtlTruth;

struct Ctl {
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
  int priv;                           // 1 = privileged
  int quant;                          // 1 = ctl_fire rounds kappa up to the GRN grid {0.25, 0.5, 1}
  // ---- controller-owned
  void *st;                           // your state (allocate in init, free in fini)
  double diag[CTL_NDIAG];             // per-life diagnostics (write 5..15)
  // ---- harness-internal: do not read or write from a controller
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

// ---- actions and clock
double ctl_now(const Ctl *k);
// Schedule a stroke of act cell a with twitch increment kappa (0, 1] at time max(t, now + latency,
// last stroke of a + t_ref_min). Returns the scheduled time, or -1 if refused (bad index, kappa <= 0, past T).
double ctl_fire(Ctl *k, int a, double kappa, double t);
// Ask for a wake callback at max(t, nextafter(now)) (ignored at or after t0 + T). Returns the time or -1.
double ctl_wake(Ctl *k, double t);
// Privileged truth; returns 0 (and fills nothing) for an information-matched controller.
int ctl_truth(Ctl *k, CtlTruth *out);

// ---- models of the controller's own actions (exact while every commanded cell is alive and the motor law is the one
// set with ctl_set_motor_sign; they never read the world)
double ctl_last_fire(const Ctl *k, int a);           // last scheduled stroke of a (-inf if none)
double ctl_twitch(const Ctl *k, int a, double t);    // commanded twitch of a at t >= its last scheduled stroke
int ctl_key_armed(const Ctl *k);                     // key state after every scheduled hotspot stroke
// Would a hotspot stroke of kappa at time t (>= its last scheduled stroke) click? (key model + twitch model)
int ctl_tap_would_click(const Ctl *k, double kappa, double t);
// Commanded displacement of the dot (efference copy): the position the dot would have at t (>= now) if it had moved
// only by the controller's strokes (scheduled ones included), under the assumed motor sign, from (0, 0) at t0.
void ctl_eff_pos(Ctl *k, double t, double *x, double *y);
void ctl_eff_final(Ctl *k, double *x, double *y);    // the same at t = infinity (all scheduled strokes, full drift)
// Displacement in [now, t] caused only by strokes at or after now (pending: not yet in the truth, which is the left
// limit at now) - for privileged planning; t = INFINITY gives their eventual displacement.
void ctl_pending_disp(Ctl *k, double t, double *x, double *y);
void ctl_set_motor_sign(Ctl *k, double sign);        // +1 normal (pull), -1 flipped (push); affects later strokes
// Steering helper: schedule strokes of rim act cells (greedy, at most one per cell, at time t or the earliest allowed
// time) whose eventual commanded displacement approximates (dx, dy). Cells need alignment >= min_align (cosine)
// with the remaining error; kappa per stroke <= kmax; stops when the remaining error < tol. Returns strokes made.
int ctl_steer(Ctl *k, double dx, double dy, double t, double kmax, double min_align, double tol);

// ---- registry (constructor-time)
void ctl_register(const CtlDef *d);
#define CTL_REGISTER(def) \
  __attribute__((constructor)) static void ctl_reg_##def(void) { ctl_register(&def); }

#endif
