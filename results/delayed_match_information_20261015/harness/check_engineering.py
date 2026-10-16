"""Frozen 32-call harness check, within root's 40-call/120 CPU-second engineering cap.

No matching policy, tuning, fresh scientific seeds, or payoff estimates. Eight
same-input hidden-state controller-policy calls are reserved/pending, not fabricated.
"""
from pathlib import Path
import argparse
import hashlib
import json
import os
import resource
import sys
import time

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
WORKTREE = ROOT / 'outputs/abi5_delayed_match_20261015/worktree'
PAIRS = [
    dict(group='passthrough', seed=42_000_000, body=6, world=dict(T=85.0)),
    dict(group='passthrough', seed=42_000_002, body=0, world=dict(T=85.0)),
    dict(group='passthrough', seed=42_000_004, body=6, world=dict(T=85.0, t0=10.0, t_open=50.0)),
    dict(group='passthrough', seed=42_000_007, body=0, world=dict(T=85.0, t_open=45.0, n_max=1)),
    *[dict(group='null', **x) for x in (
        dict(seed=42_000_000, shape='hollow3', world=dict(T=85.0)),
        dict(seed=42_000_001, shape='hollow3', world=dict(T=85.0)),
        dict(seed=42_000_004, shape='hollow2', world=dict(T=85.0, t0=-8.0)),
        dict(seed=42_000_006, shape='hollow3', world=dict(T=85.0, kill_t=1.0, kill_frac=1.0)))],
    *[dict(group='script_replay', **x) for x in (
        dict(seed=42_000_000, shape='hollow3', world=dict(T=85.0)),
        dict(seed=42_000_001, shape='hollow3', world=dict(T=85.0)),
        dict(seed=42_000_004, shape='hollow2', world=dict(T=85.0, t0=-8.0)),
        dict(seed=42_000_006, shape='hollow3', world=dict(T=85.0, kill_t=1.0, kill_frac=1.0)))],
    *[dict(group='full_fast', seed=42_000_000+i, shape='hollow3', world=dict(T=85.0)) for i in range(2)],
    *[dict(group='python_bridge', seed=42_000_000+i, shape='hollow3', world=dict(T=85.0)) for i in range(2)],
]
# Relative requested time, act index (0 or hotspot), kappa. Includes quantization,
# refractory delay, end refusal and commands delivered after whole-body extinction.
SCRIPT = [(6.0, 'rim', .1), (8.0, 'hot', .6), (11.0, 'rim', .3),
          (11.25, 'rim', .5), (82.0, 'rim', 1.), (84.8, 'hot', 1.), (85., 'hot', 1.)]


def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def dump(p, value): p.write_text(json.dumps(value, indent=2, allow_nan=False) + '\n')
def cpu():
    return sum(x.ru_utime+x.ru_stime for x in
               (resource.getrusage(resource.RUSAGE_SELF), resource.getrusage(resource.RUSAGE_CHILDREN)))
def available():
    row = next(x for x in Path('/proc/meminfo').read_text().splitlines() if x.startswith('MemAvailable:'))
    return int(row.split()[1])*1024


def main(out):
    out.mkdir(parents=True, exist_ok=False)
    t0, c0 = time.monotonic(), cpu()
    resource.setrlimit(resource.RLIMIT_AS, (8*1024**3, 8*1024**3))
    resource.setrlimit(resource.RLIMIT_CPU, (120, 121))
    os.environ.update(OMP_NUM_THREADS='1', OPENBLAS_NUM_THREADS='1', MKL_NUM_THREADS='1')
    os.environ['XDG_CACHE_HOME'] = str(out/'cache')
    os.environ['CELL_DEV_CACHE'] = str(out/'cache')
    pins = {str(p): sha(p) for p in sorted(HERE.iterdir()) if p.suffix in ('.c', '.h', '.py')}
    for name in ('kernel.c', 'spec.py', 'reference.py', 'build.py', 'handbuilt.py'):
        p = WORKTREE / 'src/life' / name
        pins[str(p)] = sha(p)
    assert sha(HERE/'kernel.abi5.c') == sha(WORKTREE/'src/life/kernel.c')
    dump(out/'plan.json', dict(status='engineering only', pairs=PAIRS, script=SCRIPT,
         calls=32, permitted_total=40, policy_checks_pending=8, cpu_cap=120, threads=1,
         address_space_bytes=8*1024**3, rss_stop_bytes=4*1024**3,
         host_available_floor=4*1024**3, source_sha256=pins))
    assert available() >= 4*1024**3
    import numpy as np
    import harness as h
    import make_ckernel
    from src.life import reference
    from dataclasses import replace
    full = h.load(make_ckernel.build(out/'scratch.so'))
    fast = h.load(make_ckernel.build(out/'scratch_fast.so', fast=True))
    production = h.build.load()
    document = json.loads((WORKTREE/'results/atlas/play/bodies.json').read_text())
    calls, checks = [], []

    def call(backend, case, f):
        assert len(calls) < 40
        assert cpu()-c0 < 120 and available() >= 4*1024**3
        assert resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024 < 4*1024**3
        row = dict(index=len(calls), backend=backend, case=case, status='started')
        calls.append(row); dump(out/'calls.json', calls)
        result = f()
        row['status']='complete'; dump(out/'calls.json', calls)
        return result

    def bits(a,b,label):
        assert a.shape == b.shape and a.dtype == b.dtype and a.tobytes()==b.tobytes(), label

    def same(a,b,skip=(),hashes=True):
        cols = [j for j in range(h.V.LEDGER_SIZE) if j not in skip]
        bits(a.ledger[:,cols], b.ledger[:,cols], 'ledger')
        if hashes: bits(a.hashes,b.hashes,'hashes')
        bits(a.raster_n,b.raster_n,'raster counts')
        bits(a.fate_n,b.fate_n,'fate counts')
        for x,y in zip(a.spikes(0), b.spikes(0)): bits(x,y,'spikes')
        for x,y in zip(a.fates(0), b.fates(0)): bits(x,y,'fates')

    try:
        for index, case in enumerate(PAIRS):
            group, seed = case['group'], case['seed']
            world = h.spec.world('catch_delayed_match_l4', t0=0., t_open=0.)
            world = replace(world, **case['world'])
            name = f'{index:02d}_{group}_{seed}'
            if group == 'passthrough':
                body = document['bodies'][case['body']]
                if body['mode']=='program':
                    world=replace(world, flags=world.flags|h.V.FLAGS['program_mode'])
                    kw=dict(programs=np.array(body['program']),init=body['cells'])
                else: kw=dict(genomes=np.array(body['genome'])[None])
                a=call('C production', name, lambda:h.run_tissue(production,world,seed,**kw))
                b=call('C scratch passthrough', name, lambda:h.run_tissue(full,world,seed,**kw))
                same(a,b)
            else:
                shape=case['shape']; program,cells=h.inert(shape)
                world=replace(world,flags=world.flags|h.V.FLAGS['program_mode'])
                hot=next(i for i,x in enumerate([c for c in cells if c[2]==1]) if x[:2]==(0,0))
                params=[v for t,a,k in SCRIPT for v in (t, hot if a=='hot' else 0,k)]
                if group=='null':
                    a=call('C inert tissue',name,lambda:h.run_tissue(production,world,seed,programs=program,init=cells))
                    b=call('C null controller',name,lambda:h.run_controller(full,world,seed,shape=shape,charge='none'))
                    same(a,b)
                elif group=='script_replay':
                    a=call('C callback script',name,lambda:h.run_controller(full,world,seed,98,params,shape))
                    b=call('C prequeued replay',name,lambda:h.run_controller(full,world,seed,99,params,shape))
                    same(a,b,skip=(h.V.L['events'],),hashes=False)
                    bits(a.hashes[:,1:],b.hashes[:,1:],'non-all hash families')
                elif group=='full_fast':
                    a=call('C controller full',name,lambda:h.run_controller(full,world,seed,98,params,shape))
                    b=call('C controller fast',name,lambda:h.run_controller(fast,world,seed,98,params,shape))
                    same(a,b,hashes=False)
                    assert np.all(b.hashes == h.spec.HASH_INIT)
                else:
                    a=call('C null bridge',name,lambda:h.run_controller(full,world,seed,shape=shape,charge='none'))
                    lat,unit=h.V.lattice_tables(world.lattice)
                    b=call('Python inert bridge',name,lambda:reference.run_life(h.V.pack_world(world),lat,unit,
                        program=program,init=cells,seeds=(seed,0,0,0),raster_cap=16384,fate_cap=1024,abi=h.V))
                    bits(a.ledger[0],b.ledger,'Python ledger'); bits(a.hashes[0],b.hashes,'Python hashes')
                    for x,y in zip(a.spikes(0),(b.raster_t,b.raster_uid)): bits(x,y,'Python raster')
                    for x,y in zip(a.fates(0),(b.fate_i,b.fate_f)): bits(x,y,'Python fates')
            np.savez(out/(name+'.npz'),ledger=a.ledger,hashes=a.hashes,
                     raster_t=a.spikes(0)[0],raster_uid=a.spikes(0)[1],fate_i=a.fates(0)[0],fate_f=a.fates(0)[1])
            checks.append(name); dump(out/'checks.json',checks)
            print('PASS',name,flush=True)
        assert pins == {p:sha(p) for p in pins}
        dump(out/'receipt.json',dict(status='passed',calls=calls,checks=checks,cpu_seconds=cpu()-c0,
             wall_seconds=time.monotonic()-t0,max_rss_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
             child_max_rss_kib=resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss,
             host_available_end=available(),source_sha256=pins,pending='full-policy hidden-state and L-only erase audits'))
    except BaseException as error:
        dump(out/'failure.json',dict(error=repr(error),calls=calls,checks=checks,cpu_seconds=cpu()-c0,
             wall_seconds=time.monotonic()-t0))
        raise


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--out',type=Path,required=True)
    main(p.parse_args().out.resolve())
