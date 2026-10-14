// Example external controller (template for capability agents). Build into your own library:
//   python make_ckernel.py --out /your/dir/my_ckernel_fast.so --fast --ctl /your/dir/example_ctl.c
// and run it from Python with  H.ctl_run(1000, params, fp, world, seeds, lib="/your/dir/my_ckernel_fast.so").
// Pick an id >= 1000 (built-ins use 0-99); prefix every static name with your controller's tag to avoid clashes
// (all controllers share one translation unit).
#include "ctl_api.h"

// "centre clicker with a refractory hold": information-matched. It taps on a centre ping unless it tapped within
// p[0] time units, and steers toward the column of the most recent non-centre ping with an eventual displacement
// of p[1] (a crude reflex). p: [0] hold (3.5)  [1] step (0.5)
typedef struct { double last_tap; } ExSt;

static int ex_init(Ctl *k) {
  ExSt *st = calloc(1, sizeof(ExSt));
  if (!st) return -1;
  st->last_tap = -INFINITY;
  k->st = st;
  return 0;
}
static void ex_ping(Ctl *k, double t, int s) {
  ExSt *st = k->st;
  const double hold = k->np > 0 ? k->p[0] : 3.5, step = k->np > 1 ? k->p[1] : 0.5;
  if (s == k->centre) {
    if (k->hot >= 0 && t - st->last_tap >= hold && ctl_tap_would_click(k, 1.0, t + k->latency)) {
      st->last_tap = t;
      ctl_fire(k, k->hot, 1.0, t);
      k->diag[5] += 1.0;  // your own diagnostics: diag[5..15]
    }
    return;
  }
  const double x = k->sense_xy[2 * s], y = k->sense_xy[2 * s + 1], r = sqrt(x * x + y * y);
  if (r > 0.0) ctl_steer(k, step * x / r, step * y / r, t, 1.0, 0.5, 0.05);
}
static void ex_fini(Ctl *k) { free(k->st); }

static const CtlDef CTL_EXAMPLE = {1000, "example centre clicker", ex_init, ex_ping, NULL, ex_fini};
CTL_REGISTER(CTL_EXAMPLE)
