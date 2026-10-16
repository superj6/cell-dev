"""Compile scratch ABI5 instrumentation with separately compiled opaque-API controllers.

No prototype-world patches, privileged truth, or ledger repurposing. The normal
life_run path is preserved. Building does not run a simulator life.
"""
from pathlib import Path
import argparse
import hashlib
import json
import subprocess

HERE = Path(__file__).resolve().parent


def patched_source():
    s = (HERE / "kernel.abi5.c").read_text()
    def sub(old, new):
        nonlocal s
        assert s.count(old) == 1, (s.count(old), old[:100])
        s = s.replace(old, new)
    sub('enum { X_KILL, X_STUCK };', 'enum { X_KILL, X_STUCK, X_FORCE, X_WAKE };')
    sub('  int fail;\n} Ctx;\n', '  int fail;\n  int ctl_mode; void *ctl;\n} Ctx;\n'
        'struct CtlCfg;\nstatic _Thread_local const struct CtlCfg *g_ctl_cfg = NULL;\n'
        'static int ctl_create(Ctx *, const int32_t *, int32_t);\n'
        'static void ctl_destroy(Ctx *);\n'
        'static void ctl_on_ping(Ctx *, double, int32_t, uint64_t);\n'
        'static void ctl_on_wake(Ctx *, double);\n')
    # Preserve ordinary inert-cell ticks, notices, receptor candidates and maintenance order.
    sub('        if (rec_on && e->uid == X->uid) n_rec++;  // a RECEPTOR that is not delivered vanishes\n',
        '        if (rec_on && e->uid == X->uid) n_rec++;  // a RECEPTOR that is not delivered vanishes\n'
        '        if (c->ctl && X && e->uid == X->uid && !(c->fl & F_RECEPTOR_OFF))\n'
        '          ctl_on_ping(c, t, si, X->uid);  // callback may reallocate events\n')
    sub('    const Ev *e = &c->ev[c->grp[G_EXO][i]];\n    if (!X || !X->alive || e->uid != X->uid) continue;\n',
        '    const Ev *e = &c->ev[c->grp[G_EXO][i]];\n'
        '    if (e->sub == X_WAKE) { if (c->ctl) ctl_on_wake(c, t); continue; }\n'
        '    if (e->sub == X_FORCE) {\n'
        '      if (X && X->alive && e->uid == X->uid) {\n'
        '        const double kp = e->x[0], old = X->th[K_KAPPA];\n'
        '        X->th[K_KAPPA] = kp; fire(c, si, X, t); X->th[K_KAPPA] = old;\n'
        '      }\n      continue;\n    }\n'
        '    if (!X || !X->alive || e->uid != X->uid) continue;\n')
    sub('  if (c->kind == WK_CATCH) catch_start(c);  // the world exists before the first time group (9.7.1)\n'
        '  start_life(c, init, n_init);\n',
        '  c->ctl_mode = g_ctl_cfg != NULL;\n'
        '  if (c->kind == WK_CATCH) catch_start(c);  // the world exists before the first time group (9.7.1)\n'
        '  start_life(c, init, n_init);\n'
        '  if (c->ctl_mode && !c->fail && ctl_create(c, init, n_init)) c->fail |= FAIL_ALLOC;\n')
    sub('  close_life(c, L);\n  for (int i = 0; i < HASH_SIZE; i++) H[i] = c->H[i];\n',
        '  close_life(c, L);\n  if (c->ctl_mode) ctl_destroy(c);\n'
        '  for (int i = 0; i < HASH_SIZE; i++) H[i] = c->H[i];\n')
    return s + '\n#include "ctl_core.c"\n'


def build(out=None, fast=False, controllers=()):
    out = Path(out or HERE / ('ckernel_fast.so' if fast else 'ckernel.so')).resolve()
    out.parent.mkdir(parents=True, exist_ok=True)
    generated = out.with_suffix('.c')
    generated.write_text(patched_source())
    sources = [generated, HERE / 'engineering.c', *map(Path, controllers)]
    command = ['gcc', '-O3', '-fopenmp', '-ffp-contract=off', '-fPIC', '-shared', '-std=c11',
               '-Wall', '-Wextra', '-I' + str(HERE)]
    if fast:
        command.append('-DLIFE_FAST')
    command += ['-o', str(out), *map(str, sources), '-lm']
    result = subprocess.run(command, text=True, capture_output=True)
    out.with_suffix('.build.log').write_text(result.stdout + result.stderr)
    result.check_returncode()
    files = [HERE / 'kernel.abi5.c', HERE / 'ctl_api.h', HERE / 'ctl_core.c', Path(__file__), *sources, out]
    receipt = dict(command=command, fast=fast, simulator_calls=0,
                   sha256={str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in files})
    out.with_suffix('.build.json').write_text(json.dumps(receipt, indent=2) + '\n')
    return str(out)


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--out')
    p.add_argument('--fast', action='store_true')
    p.add_argument('--controller', action='append', default=[])
    a = p.parse_args()
    print(build(a.out, a.fast, a.controller))
