"""Source-only adaptation of the historical controller core; never runs or builds lives.

Run only when deliberately refreshing the reviewed scratch sources. The copied engine
is fixed at the integrated ABI5 conservation fix. Controllers are separate translation
units with an opaque Ctl handle; the prototype world and truth API are not copied.
"""
from pathlib import Path
import hashlib
import json
import re

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
WORKTREE = ROOT / "outputs/abi5_delayed_match_20261015/worktree"
OLD = ROOT / "results/open_headroom/harness"


def prepare():
    kernel = WORKTREE / "src/life/kernel.c"
    (HERE / "kernel.abi5.c").write_bytes(kernel.read_bytes())
    old_header = (OLD / "ctl_api.h").read_text()
    public = old_header.split("struct Ctl {", 1)[1].split("  // ---- controller-owned", 1)[0]
    public = public.replace("  int priv;                           // 1 = privileged\n", "")
    internal = old_header.split("  // ---- harness-internal: do not read or write from a controller\n", 1)[1].split("};", 1)[0]
    api = '''/* ABI5 scratch information instrument. No world truth, reward or seed API.
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
typedef struct {''' + public + '''} CtlInfo;
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
#define CTL_REGISTER(def) \\
  __attribute__((constructor)) static void ctl_reg_##def(void) { ctl_register(&def); }
#endif
'''
    (HERE / "ctl_api.h").write_text(api)
    core = (OLD / "ctl_core.c").read_text()
    core = core[:core.index("int ctl_truth(")] + core[core.index("// ----------------------------------------------------------------------------------- kernel-side hooks"):]
    core = core.replace('#include "ctl_api.h"', '#include "ctl_api.h"\nstruct Ctl {\n  CtlInfo v;\n  void *st;\n  double diag[CTL_NDIAG];\n' + internal + '};\n')
    fields = ('n_sense n_act hot centre sense_ab act_ab sense_xy act_xy act_face n_fill t0 T latency '
              't_ref_min tau_z g_n gam th_click th_rel d_min d0 p np extra n_extra quant').split()
    for field in fields:
        core = re.sub(r'k->' + field + r'\b', 'k->v.' + field, core)
    core = core.replace('CTL_F_PRIV = 1, ', '')
    core = core.replace('  k->priv = (cfg->flags & CTL_F_PRIV) != 0; k->v.quant = (cfg->flags & CTL_F_QUANT) != 0;',
                        '  k->v.quant = 1;  // legal motor grid is mandatory in this harness')
    # Retain every commanded impulse so candidate-time queries can reconstruct past positions.
    start, end = core.index('static void eff_anchor_to('), core.index('static int eff_push(')
    core = core[:start] + 'static void eff_advance(Ctl *k, double t) { (void)k; (void)t; }\n' + core[end:]
    core = core.replace('void ctl_set_motor_sign(Ctl *k, double sign) { k->_sign = sign < 0.0 ? -1.0 : 1.0; }', '')
    core = core.replace('  if (threads < 1) threads = 1;', '  if (threads != 1) return -5;')
    core = core.replace('if (!ctl_find(ctl_id[i]) || !(ctl_lat[i] >= 0.0) || !(ctl_tref[i] >= 0.0)) return -5;',
                        'if (!ctl_find(ctl_id[i]) || !(ctl_lat[i] >= w[W_D0]) || !isfinite(ctl_lat[i]) ||\n'
                        '        !(ctl_tref[i] >= 0.5) || !isfinite(ctl_tref[i]) || w[W_NOISE] != 0.0 ||\n'
                        '        (ctl_flags && (ctl_flags[i] & ~14))) return -5;')
    core = core.replace('  if (n_lives < 0 || !lat', '  if (!ctl_lat || !ctl_tref) return -1;\n  if (n_lives < 0 || !lat')
    core += '''
double ctl_next_impulse_after(const Ctl *k, double t) {
  for (int i = 0; i < k->_npend; i++) if (k->_pend[3*i] > t) return k->_pend[3*i];
  return INFINITY;
}
const CtlInfo *ctl_public(const Ctl *k) { return &k->v; }
void *ctl_state(const Ctl *k) { return k->st; }
void ctl_set_state(Ctl *k, void *state) { k->st = state; }
void ctl_diagnostic(Ctl *k, int slot, double value) {
  if (slot >= 5 && slot < CTL_NDIAG) k->diag[slot] = value;
}
'''
    (HERE / "ctl_core.c").write_text(core)
    pins = {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in (kernel, OLD / "ctl_core.c", OLD / "ctl_api.h", Path(__file__))}
    (HERE / "source_origins.json").write_text(json.dumps(pins, indent=2) + "\n")


if __name__ == "__main__":
    prepare()
