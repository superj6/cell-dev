#include "ctl_api.h"
static long x_truth_calls=0;
static int x_checked_truth(Ctl *k,CtlTruth *out) { x_truth_calls++; return ctl_truth(k,out); }
long x_truth_count(void) { return x_truth_calls; }
#define ctl_truth x_checked_truth
// Measurement instrumentation only. Single-thread use; no organism changes.
#include "ctl_api.h"
static double *e7_log = NULL;
static long e7_n = 0, e7_cap = 0;
static int e7_replaying = 0;
static long e7_next = 0;
static void e7_append(double kind, double a, double b, double c, double d, double e) {
  if (e7_n + 6 > e7_cap) {
    const long cap = e7_cap ? e7_cap * 2 : 65536;
    double *p = realloc(e7_log, cap * sizeof(double));
    if (!p) abort();
    e7_log = p; e7_cap = cap;
  }
  double *p = e7_log + e7_n;
  p[0] = kind; p[1] = a; p[2] = b; p[3] = c; p[4] = d; p[5] = e;
  e7_n += 6;
}
long e7_log_size(void) { return e7_n; }
void e7_log_copy(double *dest) { memcpy(dest, e7_log, e7_n * sizeof(double)); }
static double e7_fire(Ctl *k, int a, double kappa, double t) {
  const double result = ctl_fire(k, a, kappa, t);
  e7_append(1, ctl_now(k), a, kappa, t, result);
  return result;
}
static int e7_steer(Ctl *k, double dx, double dy, double t, double kmax, double align, double tol) {
  const int result = ctl_steer(k, dx, dy, t, kmax, align, tol);
  e7_append(2, ctl_now(k), dx, dy, t, result);
  e7_append(3, kmax, align, tol, 0, 0);
  return result;
}
static double e7_wake(Ctl *k, double t) {
  double result;
  if (!e7_replaying) result = ctl_wake(k, t);
  else {
    // Same return value as ctl_wake, but callbacks come from the recorded stream.
    result = t > ctl_now(k) ? t : nextafter(ctl_now(k), INFINITY);
    if (!(result < k->t0 + k->T)) result = -1.0;
  }
  e7_append(5, ctl_now(k), t, result, 0, 0);
  return result;
}
#define ctl_fire e7_fire
#define ctl_steer e7_steer
#define ctl_wake e7_wake
#include "/home/jgon/project/ml/cell-dev/outputs/autonomous_visibility_dark_tail_information_20261014/original/controllers/mem_ctl.c"
#undef ctl_fire
#undef ctl_steer
#undef ctl_wake

static int e7_record_init(Ctl *k) {
  e7_n = 0; e7_replaying = 0;
  return CTL_C5.init(k);
}
static void e7_record_ping(Ctl *k, double t, int sense) {
  e7_append(0, t, sense, 0, 0, 0);
  CTL_C5.ping(k, t, sense);
}
static void e7_record_wake(Ctl *k, double t) {
  e7_append(4, t, 0, 0, 0, 0);
  CTL_C5.wake(k, t);
}
static int e7_replay_init(Ctl *k) {
  e7_n = 0; e7_replaying = 1; e7_next = 0;
  const int result = CTL_C5.init(k);
  if (result) return result;
  double last = -INFINITY;
  for (long i = 0; i < (long)k->extra[0]; i++) {
    const double t = k->extra[2 + 3 * i];
    if (t != last) ctl_wake(k, t);
    last = t;
  }
  return 0;
}
static void e7_ignore_ping(Ctl *k, double t, int sense) { (void)k; (void)t; (void)sense; }
static void e7_replay_wake(Ctl *k, double t) {
  const long n = (long)k->extra[0];
  while (e7_next < n && k->extra[2 + 3 * e7_next] == t) {
    const double *row = k->extra + 1 + 3 * e7_next++;
    e7_append(row[0], t, row[2], 0, 0, 0);
    if (row[0] == 0) CTL_C5.ping(k, t, (int)row[2]);
    else CTL_C5.wake(k, t);
  }
}
static void e7_fini(Ctl *k) { CTL_C5.fini(k); }
static const CtlDef E7_RECORD = {1901, "E7 record callbacks", e7_record_init, e7_record_ping,
                               e7_record_wake, e7_fini};
static const CtlDef E7_REPLAY = {1902, "E7 replay callbacks", e7_replay_init, e7_ignore_ping,
                               e7_replay_wake, e7_fini};
CTL_REGISTER(E7_RECORD)
CTL_REGISTER(E7_REPLAY)

#undef ctl_truth
