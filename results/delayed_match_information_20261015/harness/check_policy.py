"""Exactly eight reused-seed engineering lives; no scientific tuning or selection."""
from pathlib import Path
import json, os, resource, hashlib, subprocess, time

HERE=Path(__file__).resolve().parent
OUT=HERE.parent/'policy_engineering'
CASES=[(42000000,0.,10),(42000000,0.,11),(42000000,0.,12),
       (42000001,0.,10),(42000001,0.,11),(42000001,0.,12),
       (42000004,-8.,11),(42000004,-8.,12)]
def dump(path,x): path.write_text(json.dumps(x,indent=2,allow_nan=False)+'\n')
def cpu(): return sum(r.ru_utime+r.ru_stime for r in (resource.getrusage(0),resource.getrusage(-1)))
def available(): return int(next(s for s in Path('/proc/meminfo').read_text().splitlines() if s.startswith('MemAvailable:')).split()[1])*1024
def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()

def main():
    OUT.mkdir(exist_ok=False)
    resource.setrlimit(resource.RLIMIT_AS,(8*1024**3,8*1024**3))
    resource.setrlimit(resource.RLIMIT_CPU,(102,103))
    os.environ.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1',CELL_DEV_CACHE=str(OUT/'cache'))
    start,c0=time.monotonic(),cpu()
    pins={str(p):sha(p) for p in HERE.iterdir() if p.suffix in ('.c','.h','.py')}
    dump(OUT/'plan.json',dict(cases=CASES,parameters=[.5,.75],calls=8,cpu_remaining=102.92,
        prior_calls=32,prior_cpu_seconds=17.08,source_sha256=pins,scientific=False))
    calls=[]
    try:
        assert available()>4*1024**3
        command=['gcc','-O2','-ffp-contract=off','-std=c11','-Wall','-Wextra','-I'+str(HERE),
                 str(HERE/'test_matching.c'),'-o',str(OUT/'test_matching'),'-lm']
        r=subprocess.run(command,capture_output=True,text=True);(OUT/'unit_build.log').write_text(r.stdout+r.stderr);r.check_returncode()
        r=subprocess.run([str(OUT/'test_matching')],capture_output=True,text=True)
        (OUT/'unit.log').write_text(r.stdout+r.stderr);r.check_returncode()
        import numpy as np
        import harness as h, make_ckernel
        lib=h.load(make_ckernel.build(OUT/'matcher.so',controllers=[HERE/'matching.c']))
        results={}
        for seed,t0,role in CASES:
            assert cpu()-c0<102.92 and available()>4*1024**3
            assert resource.getrusage(0).ru_maxrss*1024<4*1024**3
            name=f'{seed}_{role}'
            calls.append(dict(case=name,seed=seed,t0=t0,role=role,status='started'));dump(OUT/'calls.json',calls)
            world=h.spec.world('catch_delayed_match_l4',T=85.,t0=t0,t_open=0.)
            x=h.run_controller(lib,world,seed,role,[.5,.75])
            assert x.diag[0,15]==0.
            for cls in ('narrow','broad'):
                get=lambda key:x.ledger[0,h.V.L[key+'_'+cls]]
                assert get('choice_opportunities')+get('choice_carry_in')==sum(get(q) for q in
                     ('correct_choices','wrong_choices','choice_timeouts','unfinished_choices'))
            rt,ru=x.spikes(0);fi,ff=x.fates(0)
            np.savez(OUT/(name+'.npz'),ledger=x.ledger,hashes=x.hashes,diag=x.diag,
                     raster_t=rt,raster_uid=ru,fate_i=fi,fate_f=ff)
            calls[-1]['status']='complete';dump(OUT/'calls.json',calls);results[(seed,role)]=x
            print('complete',name,flush=True)
        def bits(a,b):assert a.shape==b.shape and a.dtype==b.dtype and a.tobytes()==b.tobytes()
        for seed in (42000000,42000001,42000004):
            a,b=results[(seed,11)],results[(seed,12)]
            bits(a.ledger,b.ledger);bits(a.hashes,b.hashes)
            for u,v in zip(a.spikes(0),b.spikes(0)):bits(u,v)
            for u,v in zip(a.fates(0),b.fates(0)):bits(u,v)
            bits(a.diag[:,6:],b.diag[:,6:]) # sealed erased sample diagnostic is intentionally observer-only
        for seed in (42000000,42000001):
            a,b=results[(seed,10)],results[(seed,11)]
            bits(a.diag[:,5:6],b.diag[:,5:6])
            for x,y in zip(a.spikes(0),b.spikes(0)):
                bits(x[a.spikes(0)[0]<65.5],y[b.spikes(0)[0]<65.5])
            assert b.diag[0,6]==0.
        assert pins=={p:sha(Path(p)) for p in pins}
        dump(OUT/'receipt.json',dict(status='passed',calls=calls,cpu_seconds=cpu()-c0,
            wall_seconds=time.monotonic()-start,max_rss_kib=resource.getrusage(0).ru_maxrss,
            child_max_rss_kib=resource.getrusage(-1).ru_maxrss,host_available_end=available(),source_sha256=pins,
            checks=['pure supplied-input replay/math/interface','three E/P full bitwise pairs','per-class conservation'],
            limitation='Engineering fixtures only; no instrument setting or seed selected from performance'))
    except BaseException as e:
        dump(OUT/'failure.json',dict(error=repr(e),calls=calls,cpu_seconds=cpu()-c0,wall_seconds=time.monotonic()-start))
        raise

if __name__=='__main__':main()
