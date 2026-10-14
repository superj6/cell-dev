"""Bounded ABI4/retained-scratch physics bridge; existing test tissues, no controllers or selection."""
from __future__ import annotations

import ctypes
import hashlib
import importlib.util
import json
import resource
import shutil
import subprocess
import time
from dataclasses import asdict, replace
from pathlib import Path

import numpy as np

from src.life import build, spec
from tests.life_helpers import COLUMN3, R3, columns, hexdisk
from tests.test_life_world_catch import TONIC

ROOT = Path(__file__).resolve().parents[3]
MAIN = ROOT.parent.parent
OUT = Path(__file__).resolve().parent
V3, V4 = spec.V3, spec.V4
BASE_SHA = '73c641d1eac5b3aa9396d635ab0debdf2fdde8a9faa38cc7e72e22d08bf3fe61'
CAP_R, CAP_F = 4096, 256


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def cpu():
    own, children = resource.getrusage(resource.RUSAGE_SELF), resource.getrusage(resource.RUSAGE_CHILDREN)
    return own.ru_utime + own.ru_stime + children.ru_utime + children.ru_stime


def scratch_library():
    retained = ROOT / 'results/open_headroom/harness'
    sources = OUT / 'scratch_sources'
    sources.mkdir(exist_ok=True)
    base = MAIN / 'src/life/kernel.c'
    assert sha(base) == BASE_SHA, 'explicit pre-port source no longer matches its receipt'
    shutil.copyfile(base, sources / 'kernel_abi3.c')
    for name in ('make_ckernel.py', 'ctl_core.c', 'ctl_builtin.c', 'ctl_api.h'):
        shutil.copyfile(retained / name, sources / name)
    desc = importlib.util.spec_from_file_location('retained_ckernel_bridge', sources / 'make_ckernel.py')
    mod = importlib.util.module_from_spec(desc)
    desc.loader.exec_module(mod)
    mod.SRC = str(sources / 'kernel_abi3.c')
    # Only exported life_run is called. Controller branches remain disabled for ordinary tissues.
    generated = mod.patched_source()
    generated += '\nint bridge_blink_stream(void) { return S_BLINK; }\n'
    cpath, so = OUT / 'scratch.c', OUT / 'scratch.so'
    cpath.write_text(generated)
    subprocess.run(['gcc', *build.CFLAGS, '-o', str(so), str(cpath), '-lm'], check=True,
                   capture_output=True, text=True)
    lib = ctypes.CDLL(str(so))
    build._declare(lib)
    lib.bridge_blink_stream.argtypes = []
    lib.bridge_blink_stream.restype = ctypes.c_int32
    assert lib.life_abi_version() == 3 and lib.bridge_blink_stream() == spec.S_VISIBILITY == 26
    return lib


def run_scratch(lib, w, program, body, seed):
    neutral = replace(w, visibility_mode=0, visibility_on=0.0, visibility_off=0.0, visibility_low=1.0)
    vec = V3.pack_world(neutral)[None].copy()
    # Exact retained mapping: flash off=-1, renewal off>0; dim sentinel enables residual target amplitude.
    vec[0, 38] = w.visibility_on
    vec[0, 39] = -1.0 if w.visibility_mode == 1 else w.visibility_off
    vec[0, 40] = 0.0  # no motor flip
    vec[0, 16] = w.visibility_low
    vec[0, 19] = 777.0
    lat, unit = V3.lattice_tables(w.lattice)
    init, ni = V3.pack_init([x[:3] for x in body], [x[3] for x in body])
    init = init[None].copy()
    counts = np.array([ni], dtype=np.int32)
    prog = np.ascontiguousarray(program[None], dtype=np.float64)
    gof = np.zeros(1, dtype=np.int32)
    seeds = np.array([[seed, 0, 0, 0]], dtype=np.uint64)
    out = dict(ledger=np.zeros((1,57)), hashes=np.zeros((1,5),dtype=np.uint64),
               raster_t=np.zeros((1,CAP_R)), raster_uid=np.zeros((1,CAP_R),dtype=np.uint64),
               raster_n=np.zeros(1,dtype=np.int64), fate_i=np.zeros((1,CAP_F,7),dtype=np.int64),
               fate_f=np.zeros((1,CAP_F,18)), fate_n=np.zeros(1,dtype=np.int64))
    p = build._ptr
    rc = lib.life_run(1,1,p(lat,build._i32),p(unit,build._f64),0,None,1,p(prog,build._f64),
        p(gof,build._i32),p(init,build._i32),p(counts,build._i32),p(vec,build._f64),p(seeds,build._u64),
        p(out['ledger'],build._f64),p(out['hashes'],build._u64),CAP_R,p(out['raster_t'],build._f64),
        p(out['raster_uid'],build._u64),p(out['raster_n'],build._i64),CAP_F,p(out['fate_i'],build._i64),
        p(out['fate_f'],build._f64),p(out['fate_n'],build._i64))
    assert rc == 0, rc
    return out, vec


def cases():
    base = dict(T=64.0, flags=V4.flags('program_mode'))
    ring = columns(hexdisk(1))
    for mode, preset in ((1,'catch_speck_flash5_dim25_l4'), (2,'catch_speck_blink20_20_l4')):
        for seed in (0,11):
            yield f'mode{mode}_default_s{seed}', spec.world(preset,**base), COLUMN3, ring, seed, False
        yield f'mode{mode}_shifted_window', spec.world(preset,**base,t0=1024.0,t_open=32.0), COLUMN3, ring, 17, False
        yield f'mode{mode}_frequent_timers', spec.world(preset,**base,t_resp=2.0,tau_turn=3.0), COLUMN3, ring, 11, False
        yield f'mode{mode}_unit_multiplier', spec.world(preset,**base,visibility_low=1.0), COLUMN3, ring, 3, False
        # Existing synchronous-act test tissue, unchanged. Nearby stationary target makes dark captures
        # observable as an engineering fixture. Its fitness is never an acceptance criterion.
        quiet = V3.theta()
        tonic = V3.pack_program(TONIC,alone=quiet,rim=quiet,zygote=quiet)
        body = [(0,0,0,R3['zygote']),(0,0,1,R3['contact'])]
        w = spec.world(preset,**base,v_t=0.0,R_min=0.0,R_max=0.5,t_resp=0.0)
        yield f'mode{mode}_low_capture_fixture', w, tonic, body, 11, True


def main():
    start, wall = cpu(), time.time()
    lib = scratch_library()
    ledger_ids = [i for i in range(57) if i not in (21,22)]
    receipts = []
    for name,w,program,body,seed,require_low in cases():
        old, old_world = run_scratch(lib,w,program,body,seed)
        new = build.run(w,[seed],programs=program,init=body,abi=V4,threads=1,raster_cap=CAP_R,fate_cap=CAP_F)
        assert old['ledger'][0,ledger_ids].tobytes() == new.ledger[0,ledger_ids].tobytes(), (name,'physical ledger')
        assert old['ledger'][0,21] == new.ledger[0,57], (name,'low-light captures')
        assert np.array_equal(new.ledger[0,[21,22]], [0.0,0.0]), (name,'original CATCH beats/P_int roles')
        # New visibility event words change world/all; other hash families and every action/fate log agree.
        assert old['hashes'][0,1:4].tobytes() == new.hashes[0,1:4].tobytes(), (name,'local hash families')
        for key in ('raster_t','raster_uid','raster_n','fate_i','fate_f','fate_n'):
            assert old[key].tobytes() == getattr(new,key).tobytes(), (name,key)
        assert int(new.ledger[0,V4.L['status']]) & (spec.STATUS['raster_overflow']|spec.STATUS['fate_overflow']) == 0
        if require_low:
            assert new.ledger[0,57] > 0, (name,'missing positive low-light fixture')
        arrays = dict(program=program,body=np.array(body,dtype=np.int32),world=V4.pack_world(w),scratch_world=old_world)
        arrays.update({f'scratch_{k}':v for k,v in old.items()})
        arrays.update({f'production_{k}':getattr(new,k) for k in old})
        path = OUT / f'{name}.npz'
        np.savez_compressed(path,**arrays)
        receipts.append(dict(name=name,world=asdict(w),seed=seed,fixture='existing tonic two-cell' if require_low else 'COLUMN3 ring1',
                             captures=float(new.ledger[0,V4.L['captures']]),low_light_captures=float(new.ledger[0,57]),
                             spikes=int(new.raster_n[0]),npz_sha256=sha(path)))
    pins = {str(p.relative_to(ROOT)):sha(p) for p in [ROOT/'src/life/spec.py',ROOT/'src/life/build.py',ROOT/'src/life/kernel.c',
              ROOT/'src/life/reference.py',ROOT/'tests/life_helpers.py',ROOT/'tests/test_life_world_catch.py',
              ROOT/'results/open_headroom/harness/make_ckernel.py',ROOT/'results/open_headroom/harness/ctl_core.c',
              ROOT/'results/open_headroom/harness/ctl_builtin.c',ROOT/'results/open_headroom/harness/ctl_api.h']}
    report = dict(status='pass',validation_lives=2*len(receipts),cases=receipts,T=64,threads=1,source_pins=pins,
                  old_base_sha256=BASE_SHA,scratch_source_sha256=sha(OUT/'scratch.c'),scratch_library_sha256=sha(OUT/'scratch.so'),
                  visibility_stream=26,physical_ledger_columns=ledger_ids,excluded_scratch_ledger_columns=[21,22],
                  mapping={'scratch_dark_caps_column':21,'production_low_light_captures_column':57},
                  cpu_seconds=cpu()-start,wall_seconds=time.time()-wall,
                  limitations=['Engineering fixtures only; no information-payoff or evolved-memory claim.',
                               'Scratch all/world hashes deliberately differ because ABI4 adds visibility records and a ledger fold.',
                               'No central-controller entry point is called; ordinary life_run only.',
                               'Short fixed cases do not replace exhaustive validation or later fresh information-payoff tests.'])
    (OUT/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(dict(status=report['status'],cases=len(receipts),validation_lives=report['validation_lives'],
                         cpu_seconds=report['cpu_seconds'],low_light=[(x['name'],x['low_light_captures']) for x in receipts],
                         report_sha256=sha(OUT/'report.json'))))


if __name__ == '__main__':
    main()
