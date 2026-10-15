"""Explicit ABI-3 allocation and foreign-call boundary for unchanged archived controllers/bodies."""
from __future__ import annotations

import ctypes
from dataclasses import replace

import numpy as np
from frozen import checked_library, load_harness, modules_pinned


def array_check(name, array, dtype, shape):
    if not isinstance(array,np.ndarray) or array.dtype != np.dtype(dtype) or array.shape != tuple(shape) or not array.flags.c_contiguous:
        raise ValueError('raw ABI array mismatch: '+name)
    if array.dtype.kind == 'f' and not np.isfinite(array).all():
        raise ValueError('nonfinite raw input/output: '+name)


def prepare_arrays(candidate, world_entry, seeds, *, duration=None, override=None, cid=None, extra=None):
    H = load_harness()
    n = len(seeds)
    if n < 1 or len(set(map(int,seeds))) != n:
        raise ValueError('unique nonempty seed batch required')
    base = H.spec.World(**world_entry['base_world'])
    if duration is not None:
        base = replace(base,T=duration)
    if override:
        base = replace(base,**override)
    flags = base.flags | H.V3.flags('program_mode') | candidate['body_flags']
    base = replace(base,flags=flags)
    wv = np.repeat(H.V3.pack_world(base)[None,:],n,axis=0)
    for key,value in world_entry['scratch_slots'].items():
        wv[:,H.XSLOT[key]] = value
    tab,unit = H.V3.lattice_tables(base.lattice)
    cells,counts = H.build._init(candidate['cells'],n,H.V3)
    controller = 'params' in candidate
    arrays = dict(world=np.ascontiguousarray(wv),seeds=H.build._seeds(seeds),
        lattice=np.ascontiguousarray(tab),unit=np.ascontiguousarray(unit),
        program=np.ascontiguousarray(np.asarray(candidate['program'],dtype=np.float64)[None,:]),
        gof=np.zeros(n,dtype=np.int32),cells=cells,counts=counts,
        ledger=np.zeros((n,57),dtype=np.float64),hashes=np.zeros((n,5),dtype=np.uint64))
    if controller:
        if candidate['controller_id'] != 1102 or candidate['action'] != dict(latency='d0',charge='relay',t_ref_min=.5,privileged=False,quant=False):
            raise ValueError('unregistered controller/action configuration')
        arrays.update(params=np.ascontiguousarray(np.repeat(np.asarray(candidate['params'],dtype=np.float64)[None,:],n,axis=0)),
            cids=np.full(n,1102 if cid is None else cid,dtype=np.int32),latency=np.full(n,base.d0,dtype=np.float64),
            tref=np.full(n,.5,dtype=np.float64),flags=np.full(n,6,dtype=np.int32),
            extra=np.ascontiguousarray(np.zeros(1) if extra is None else np.asarray(extra,dtype=np.float64)),
            diag=np.zeros((n,16),dtype=np.float64))
    validate_boundary(arrays,n,controller)
    modules_pinned()
    return arrays,base


def validate_boundary(a,n,controller):
    for name,dtype,shape in [('world','float64',(n,66)),('seeds','uint64',(n,4)),
        ('program','float64',(1,129)),('gof','int32',(n,)),('cells','int32',(n,1024,4)),
        ('counts','int32',(n,)),('ledger','float64',(n,57)),('hashes','uint64',(n,5))]:
        array_check(name,a[name],dtype,shape)
    if a['lattice'].ndim != 1 or len(a['lattice']) < 2:
        raise ValueError('invalid lattice shape')
    d = int(a['lattice'][1])
    array_check('lattice',a['lattice'],'int32',(2+7*d,))
    array_check('unit',a['unit'],'float64',(d,3))
    if np.any(a['counts']<1) or np.any(a['counts']>1024) or np.any(a['gof'] != 0):
        raise ValueError('invalid cell counts/program index')
    if controller:
        for name,dtype,shape in [('params','float64',(n,30)),('cids','int32',(n,)),('latency','float64',(n,)),
            ('tref','float64',(n,)),('flags','int32',(n,)),('diag','float64',(n,16))]:
            array_check(name,a[name],dtype,shape)
        array_check('extra',a['extra'],'float64',(a['extra'].size,))
        if a['extra'].ndim != 1 or np.any(a['flags'] != 6) or not np.all(np.isin(a['cids'],[1102,1901,1902])):
            raise ValueError('privilege/controller flags changed')
        if np.any(a['latency'] != a['world'][:,7]) or np.any(a['tref'] != .5):
            raise ValueError('latency/refractory rule changed')


def run(candidate, world_entry, seeds, library, library_sha, *, duration=None,override=None,cid=None,extra=None):
    load_harness()
    controller = 'params' in candidate
    a,base = prepare_arrays(candidate,world_entry,seeds,duration=duration,override=override,cid=cid,extra=extra)
    n = len(seeds)
    lib = checked_library(library,library_sha)
    validate_boundary(a,n,controller)
    def ptr(name,t):
        return a[name].ctypes.data_as(ctypes.POINTER(t))
    i32,u64,f64 = ctypes.c_int32,ctypes.c_uint64,ctypes.c_double
    shared = [ptr('program',f64),ptr('gof',i32),ptr('cells',i32),ptr('counts',i32),
        ptr('world',f64),ptr('seeds',u64),ptr('ledger',f64),ptr('hashes',u64),
        0,None,None,None,0,None,None,None]
    if controller:
        rc = lib.ctl_life_run(n,2,ptr('lattice',i32),ptr('unit',f64),1,*shared,
            ptr('cids',i32),ptr('params',f64),30,ptr('latency',f64),ptr('tref',f64),ptr('flags',i32),
            ptr('extra',f64),len(a['extra']),ptr('diag',f64))
    else:
        rc = lib.life_run(n,2,ptr('lattice',i32),ptr('unit',f64),0,None,1,*shared)
    if rc != 0:
        raise ValueError('foreign simulation returned '+str(rc))
    validate_boundary(a,n,controller)
    validate_ledger(a['ledger'],base)
    modules_pinned()
    return {'ledger':a['ledger'],'hashes':a['hashes'],
            'diag':a['diag'] if controller else np.empty((n,0)),
            'latency':a['latency'] if controller else np.empty(0)}


def validate_ledger(ledger,base):
    H = load_harness()
    if ledger.ndim != 2 or ledger.shape[1] != 57 or ledger.dtype != np.float64 or not np.isfinite(ledger).all():
        raise ValueError('invalid full raw ledger')
    L,S = H.V3.L,H.spec.STATUS
    status = ledger[:,L['status']]
    if np.any(status != status.astype(np.int64)) or np.any(status<0):
        raise ValueError('invalid status')
    status = status.astype(np.int64)
    if np.any(status & S['extinct']):
        raise ValueError('unexpected extinction of fixed static program/controller footprint')
    forbidden = sum(S[k] for k in ('guard_cells','guard_events','capacity','ledger_mismatch','raster_overflow','fate_overflow'))
    if np.any(status & forbidden) or np.any(status & ~sum(S.values())):
        raise ValueError('guarded/capacity/overflow/mismatched/unknown status')
    end = ledger[:,L['t_end']]
    if np.any(end < base.t0) or np.any(end > base.t0+base.T) or np.any(((status&S['extinct'])==0)&(end != base.t0+base.T)):
        raise ValueError('incomplete life')
    if np.any(ledger[:,21]<0) or np.any(ledger[:,21]>ledger[:,L['captures']]) or np.any(ledger[:,22]<0) or np.any(ledger[:,22]>ledger[:,L['captures']]):
        raise ValueError('invalid scratch capture aliases')
    cost = H.V3.column_cost(ledger,base)
    if not np.allclose(ledger[:,L['cost']],cost,rtol=1e-9,atol=1e-9):
        raise ValueError('full ledger cost mismatch')
    if not np.array_equal(ledger[:,L['F']],H.V3.fitness(ledger,base)):
        raise ValueError('raw F mismatch')
