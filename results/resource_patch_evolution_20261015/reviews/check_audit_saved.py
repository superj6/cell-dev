"""Check audit arithmetic on completed baseline bytes and supplied guard/extinction ledgers."""
from __future__ import annotations

import importlib.util
import json
import math
import resource
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0,str(ROOT))
START_CPU, START_WALL = time.process_time(), time.perf_counter()
loaded = importlib.util.spec_from_file_location('independent_patch_audit',HERE/'audit_accounting.py')
A = importlib.util.module_from_spec(loaded)
loaded.loader.exec_module(A)


def main():
    import numpy as np

    from src.life import spec

    prior = ROOT/'results/resource_patch_baseline_20261015'
    p = A.read(prior/'protocol.json')
    labels = tuple(spec.V6.LEDGER)
    n = 0
    for name, entry in A.read(prior/'row_index.json').items():
        if entry['group'] == 'engineering':
            continue
        world = p['worlds'][entry['world']]['world']
        with np.load(prior/name,allow_pickle=False) as data:
            ledger = data['ledger'].reshape(-1,107)[0]
        A.one_life(ledger,world,labels,A.source_counts(spec,world,int(entry['seed']),float(ledger[18])))
        n += 1
    assert n == 448
    world = p['worlds']['patch']['world']
    seed = 42000000
    for status, endpoint, extinct_time in ((0,1024.,-1.),(4,512.,-1.),(1,1024.,256.)):
        d = {name:0. for name in labels}
        d.update(n_end=0. if status==1 else 1., n_S_end=0. if status==1 else 1.,
                 n_peak=1.,deaths=1. if status==1 else 0.,t_end=endpoint,t_ext=extinct_time,status=float(status))
        arrivals = A.source_counts(spec,world,seed,endpoint)
        for slot,count in enumerate(arrivals):
            d[f'patch_stock_open_{slot}'] = d[f'patch_stock_end_{slot}'] = 2.
            d[f'patch_source_{slot}'] = d[f'patch_spill_{slot}'] = float(count)
        if status==4:
            d['guard_charge'] = world['c_live']*world['n_max']*(1024.-endpoint)
            d['net'] = -d['guard_charge']
            d['F'] = d['net']/1024.
        result = A.one_life([d[k] for k in labels],world,labels,arrivals)
        if status==1:
            A.equal(result['extinct_charge'],world['c_live']*.75,'extinction arithmetic')
        else:
            A.equal(result['extinct_charge'],0.,'nonextinct arithmetic')
        corrupt = dict(d,patch_source_0=d['patch_source_0']+1)
        try:
            A.one_life([corrupt[k] for k in labels],world,labels,arrivals)
        except ValueError:
            pass
        else:
            raise AssertionError('corrupt source counter accepted')
    summary = A.scalar_statistics([float(i) for i in range(512)])
    A.equal(summary['mean'],255.5,'closed-form mean')
    A.close(summary['se'],math.sqrt(42.75),'closed-form sample standard error')
    result = dict(status='passed',audit_source_sha256=A.sha(HERE/'audit_accounting.py'),
        checker_sha256=A.sha(Path(__file__)),completed_baseline_science_rows=n,
        synthetic_status_cases=3,corrupt_source_rejections=3,closed_form_statistics=True,
        active_study_outputs_read=False,new_lives=0,new_builds=0,new_genetic_draws=0,
        resources=dict(cpu_seconds=time.process_time()-START_CPU,wall_seconds=time.perf_counter()-START_WALL,
                       max_rss_KiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,threads=1))
    with (HERE/'audit_source_checks.json').open('x') as stream:
        json.dump(result,stream,indent=2)
        stream.write('\n')
    print(json.dumps(result))


if __name__ == '__main__':
    main()
