"""Synthetic saved-ledger arithmetic only; no simulator, compiler, checkpoint or random generator."""
import ast
import hashlib
import json
import os
import resource
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.dont_write_bytecode = True
sys.path.insert(0, str(ROOT))


def main():
    resource.setrlimit(resource.RLIMIT_CPU, (20, 21))
    resource.setrlimit(resource.RLIMIT_AS, (2 * 1024**3, 2 * 1024**3))
    os.sched_setaffinity(0, {min(os.sched_getaffinity(0))})
    import numpy as np
    from analyze import moments, validate_life

    from src.life import spec

    w, abi = spec.world('catch_resource_patches_l4'), spec.V6

    def row(status=0, end=1024, extinction=-1):
        ledger = np.zeros((1, 107), dtype=np.float64)
        values = dict(status=status, t_end=end, t_ext=extinction, captures=1, clicks=1, income=500,
                      live_time=extinction if status & 1 else end)
        for i in range(3):
            values[f'patch_stock_open_{i}'] = 2
            values[f'patch_stock_end_{i}'] = 1 if i == 0 else 2
        values['patch_harvest_0'] = values['patch_initial_harvest_0'] = 1
        values['cost'] = w.c_live * values['live_time']
        values['guard_charge'] = w.c_live * w.n_max * (1024 - end) if status & 2 else 0
        values['net'] = 500 - values['cost'] - values['guard_charge']
        values['F'] = values['net'] / 1024
        for key, value in values.items():
            ledger[0, abi.L[key]] = value
        return ledger

    checks = []
    good = row()
    result = validate_life(good, w)
    assert result['production_F'] == (500 - .02 * 1024) / 1024
    assert result['initial_income'] == 500 and result['refill_income'] == 0
    checks.append('known physical/F/provenance arithmetic')
    extinct = validate_life(row(status=1, extinction=30), w)
    assert extinct['extinction_charge'] == .02 * (1024 - 30)
    assert extinct['production_F'] == result['production_F']
    checks.append('legitimate extinction retained and surcharged')
    guard = validate_life(row(status=2, end=16), w)
    assert guard['guard'] == 1 and guard['reconstructed_guard_charge'] == .02 * 1024 * 1008
    checks.append('legitimate guard retained with actual-end charge')
    for name, key, value in (
        ('per-slot source conservation', 'patch_source_0', 1),
        ('per-slot stock conservation', 'patch_stock_end_0', 2),
        ('origin conservation', 'patch_initial_harvest_0', 0),
        ('integer counts', 'patch_harvest_0', .5),
        ('inactive slots', 'patch_stock_end_3', 1),
        ('native capture conservation', 'captures', 2),
        ('unknown status', 'status', 1024),
        ('capacity retained then rejected', 'status', spec.STATUS['capacity']),
        ('physical cost corruption', 'cost', 0),
    ):
        bad = good.copy()
        bad[0, abi.L[key]] = value
        try:
            validate_life(bad, w)
        except ValueError:
            checks.append(name)
        else:
            raise AssertionError('did not reject: ' + name)
    m = moments([1., 3.])
    assert m['mean'] == 2 and m['se'] == 1
    checks.append('paired-vector mean/SE reducer')
    for path in HERE.glob('*.py'):
        ast.parse(path.read_text())
    checks.append('all prepared Python syntax')
    receipt = dict(status='passed', checks=checks, count=len(checks), simulation_calls=0, builds=0, random_draws=0,
        source_pins={p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in HERE.glob('*.py')})
    (HERE / 'source_checks.json').write_text(json.dumps(receipt, indent=2) + '\n')
    print(json.dumps(dict(status='passed', checks=len(checks), simulation_calls=0, builds=0)))


if __name__ == '__main__':
    main()
