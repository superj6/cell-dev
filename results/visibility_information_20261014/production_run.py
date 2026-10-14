"""Isolated ABI-4 tissue bridge process, called only by the bounded validation worker."""
from __future__ import annotations
import argparse
import ctypes
from dataclasses import replace
import json
from pathlib import Path
import sys
import time
import numpy as np
from common import ROOT, STUDY, parent_check, require_release, sha


def run(world_name,role,seed,library,digest,out,parent):
    parent_check(parent,nested=True,phase="validation")
    value = require_release()
    sys.path.insert(0,str(ROOT))
    from src.life import build, spec
    for name,module in list(sys.modules.items()):
        if name=='src' or name.startswith('src.'):
            path=Path(module.__file__).resolve()
            if not path.is_relative_to(ROOT/'src'):
                raise ValueError('production engine module escaped main source root')
            relative=str(path.relative_to(ROOT))
            if value['production_module_pins'].get(relative)!=sha(path) or value['production_pins'].get(relative)!=sha(path):
                raise ValueError('production engine module missing or changed pin')
    if list(sys.modules['src'].__path__)!=[str(ROOT/'src')]:
        raise ValueError('production package path changed')
    if build.KERNEL is not spec.V4:
        raise ValueError('production ABI4 required')
    lib = ctypes.CDLL(str(library))
    build._declare(lib)
    sizes=(ctypes.c_int32*10)()
    lib.life_sizes(sizes)
    if sha(library) != digest or lib.life_abi_version() != 4 or list(sizes) != list(spec.V4.SIZES.values()):
        raise ValueError('production library ABI mismatch')
    build._libs[False] = lib
    def forbidden(*args,**kwargs):
        raise ValueError('implicit production compilation disabled')
    build.build = forbidden
    entry = value['worlds'][world_name]
    candidate = next(x for x in entry['candidates'] if x['role']==role)
    if role not in ('R0','R1'):
        raise ValueError('bridge only uses retained reflex rows')
    world = spec.World(**entry['production']['world'])
    world = replace(world,T=128,flags=world.flags|spec.V4.flags('program_mode')|candidate['body_flags'])
    c0,w0 = time.process_time(),time.monotonic()
    result=build.run(world,[seed],programs=np.asarray(candidate['program'],dtype=np.float64),
                     init=candidate['cells'],threads=1,abi=spec.V4,fast=False)
    with out.open('wb') as stream:
        np.savez_compressed(stream,ledger=result.ledger,hashes=result.hashes,
            cpu_seconds=np.asarray(time.process_time()-c0),wall_seconds=np.asarray(time.monotonic()-w0))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run',action='store_true')
    for key in ('world','role','library','sha256','out'):
        parser.add_argument('--'+key)
    parser.add_argument('--seed',type=int)
    parser.add_argument('--expected-parent',type=int)
    args=parser.parse_args()
    if args.run:
        run(args.world,args.role,args.seed,Path(args.library),args.sha256,Path(args.out),args.expected_parent)
    else:
        print(json.dumps({'status':'dry_run','simulation_calls':0}))
