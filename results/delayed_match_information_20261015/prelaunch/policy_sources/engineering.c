/* Harness tests only. No delayed-matching information policy is implemented here. */
#include "ctl_api.h"
#include <math.h>
#include <stdlib.h>

static const CtlDef null_def = {0, "null", NULL, NULL, NULL, NULL};
CTL_REGISTER(null_def)

/* ID 99: replay supplied ordinary act strokes (relative time, act index, kappa).
 * Supplied triples are declared engineering inputs, never hidden-world observations. */
static int replay_init(Ctl *k) {
  const CtlInfo *v = ctl_public(k);
  for (int j = 0; j + 2 < v->np; j += 3)
    ctl_fire(k, (int)v->p[j + 1], v->p[j + 2], v->t0 + v->p[j]);
  return 0;
}
static const CtlDef replay_def = {99, "script replay", replay_init, NULL, NULL, NULL};
CTL_REGISTER(replay_def)

/* ID 98: issue the same supplied triples from wake callbacks one latency before each
 * requested time. This exercises callback causality versus prequeued replay. */
static int script_init(Ctl *k) {
  const CtlInfo *v = ctl_public(k);
  int *j = calloc(1, sizeof *j);
  if (!j) return -1;
  ctl_set_state(k, j);
  if (v->np >= 3) ctl_wake(k, v->t0 + v->p[0] - v->latency);
  return 0;
}
static void script_wake(Ctl *k, double t) {
  (void)t;
  const CtlInfo *v = ctl_public(k);
  int *j = ctl_state(k);
  if (*j + 2 >= v->np) return;
  ctl_fire(k, (int)v->p[*j + 1], v->p[*j + 2], v->t0 + v->p[*j]);
  *j += 3;
  if (*j + 2 < v->np) ctl_wake(k, v->t0 + v->p[*j] - v->latency);
}
static void script_fini(Ctl *k) { free(ctl_state(k)); }
static const CtlDef script_def = {98, "callback script", script_init, NULL, script_wake, script_fini};
CTL_REGISTER(script_def)
