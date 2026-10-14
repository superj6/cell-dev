"""Fixed 82-life X validation package; no automatic release or extension. Default dry run."""
from __future__ import annotations
import argparse
import ctypes
import importlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import numpy as np
from common import ROOT, STUDY, parent_check, protocol, require_release, save, sha


def equal(a,b):
    return a.shape==b.shape and a.dtype==b.dtype and a.tobytes()==b.tobytes()


def compile_libraries(value):
    from frozen import BUNDLE,load_harness,checked_library
    load_harness()
    builder=importlib.import_module('make_ckernel')
    if Path(builder.__file__).resolve()!=BUNDLE/'harness/make_ckernel.py':
        raise ValueError('unfrozen builder')
    builder.SRC=str(BUNDLE/'src/life/kernel.c')
    out=STUDY/'validation/build'
    out.mkdir(parents=True)
    source=BUNDLE/'controllers/mem_ctl.c'
    template=(BUNDLE/'replay_wrapper.c.in').read_text()
    if 'k->extra' in source.read_text():
        raise ValueError('retained C5 source reads replay injection array')
    # Only instrumentation is added: count forbidden truth reads; never alter their values.
    prefix='''#include "ctl_api.h"
static long x_truth_calls=0;
static int x_checked_truth(Ctl *k,CtlTruth *out) { x_truth_calls++; return ctl_truth(k,out); }
long x_truth_count(void) { return x_truth_calls; }
#define ctl_truth x_checked_truth
'''
    marker='    if (row[0] == 0) @DEF@.ping(k, t, (int)row[2]);'
    if template.count(marker)!=1:
        raise ValueError('retained replay callback dispatch changed')
    template=template.replace(marker,'    e7_append(row[0], t, row[2], 0, 0, 0);\n'+marker)
    wrapper=out/'replay_wrapper.c' 
    wrapper.write_text(prefix+template.replace('@SOURCE@',str(source)).replace('@DEF@','CTL_C5')+'\n#undef ctl_truth\n')
    libraries={}
    for key,fast,ctl in [('full',False,source),('fast',True,source),('replay',False,wrapper)]:
        target=out/(key+'.so')
        start=time.process_time()
        builder.build(str(target),[str(ctl)],fast=fast)
        digest=sha(target)
        checked_library(target,digest)
        libraries[key]={'path':str(target.relative_to(STUDY)),'sha256':digest,
            'generated_source':str(target.with_suffix('.c').relative_to(STUDY)),
            'generated_source_sha256':sha(target.with_suffix('.c')),
            'compiler_sha256':value['numerical_identity']['compiler_sha256'],
            'flags':value['numerical_identity']['compiler_flags']+(['-DLIFE_FAST'] if fast else []),
            'note':'compiler child CPU is charged by monitor, not process_time'}
    target=out/'production.so'
    source=ROOT/'src/life/kernel.c'
    command=[value['numerical_identity']['compiler'],*value['numerical_identity']['compiler_flags'],'-o',str(target),str(source),'-lm']
    result=subprocess.run(command,capture_output=True,text=True)
    (out/'production_compile.log').write_text(result.stdout+result.stderr)
    if result.returncode:
        raise ValueError('production compiler failed')
    libraries['production']={'path':str(target.relative_to(STUDY)),'sha256':sha(target),'source_sha256':sha(source),
                             'command':command}
    return libraries


def validate(parent):
    parent_check(parent,phase="validation")
    value=require_release()
    if (STUDY/'validation').exists():
        raise ValueError('first attempt only: validation output already exists')
    (STUDY/'validation').mkdir()
    libraries=compile_libraries(value)
    from frozen import checked_library,load_harness
    from raw import run
    H=load_harness()
    protocol_sha=sha(STUDY/'protocol.json')
    seeds=value['validation_seeds']
    count=0
    receipts={}
    def persist(label,arrays,meta):
        path=STUDY/'validation'/(label+'.npz')
        np.savez_compressed(path,**arrays)
        receipts[label]={'path':str(path.relative_to(STUDY)),'sha256':sha(path),**meta}
        return arrays
    def scratch(label,candidate,world,seeds_,libkey='full',duration=128,override=None,cid=None,extra=None):
        nonlocal count
        parent_check(parent,phase="validation");protocol()
        count+=len(seeds_)
        save(STUDY/'validation/progress.json',{'status':'running','simulation_calls_started':count,'current':label})
        c0,w0=time.process_time(),time.monotonic()
        lib=libraries[libkey]
        arrays=run(candidate,world,seeds_,STUDY/lib['path'],lib['sha256'],duration=duration,override=override,cid=cid,extra=extra)
        arrays.update(cpu_seconds=np.asarray(time.process_time()-c0),wall_seconds=np.asarray(time.monotonic()-w0))
        return persist(label,arrays,{'simulation_calls':len(seeds_),'T':duration,'seeds':seeds_,'library':libkey})
    checks=[]
    unwrapped={}
    # 16 tissue bridge lives, 8 scratch and 8 isolated production lives.
    for world_name,world in value['worlds'].items():
        candidates={x['role']:x for x in world['candidates']}
        for role in ('R0','R1'):
            for index,seed in enumerate(seeds):
                label=f'{world_name}_{role}_{index}'
                old=scratch(label+'_scratch',candidates[role],world,[seed])
                path=STUDY/'validation'/(label+'_production.npz')
                lib=libraries['production']
                parent_check(parent,phase="validation");protocol()
                count+=1
                save(STUDY/'validation/progress.json',{'status':'running','simulation_calls_started':count,'current':label+'_production'})
                subprocess.run([sys.executable,str(STUDY/'production_run.py'),'--run','--world',world_name,'--role',role,
                    '--seed',str(seed),'--library',str(STUDY/lib['path']),'--sha256',lib['sha256'],'--out',str(path),
                    '--expected-parent',str(os.getpid())],check=True)
                with np.load(path,allow_pickle=False) as f:
                    new={key:f[key].copy() for key in f.files}
                receipts[label+'_production']={'path':str(path.relative_to(STUDY)),'sha256':sha(path),
                    'simulation_calls':1,'T':128,'seeds':[seed],'library':'production'}
                cols=[i for i in range(57) if i not in (21,22)]
                passed=equal(old['ledger'][:,cols],new['ledger'][:,cols]) and equal(old['ledger'][:,21],new['ledger'][:,57])
                passed=passed and equal(old['hashes'][:,1:4],new['hashes'][:,1:4])
                if not passed:raise ValueError('scratch/production physical bridge failed: '+label)
                checks.append({'check':'production_bridge','case':label,'passed':True,'excluded_ledger':[21,22],
                               'mapped_capture_column':[21,57],'excluded_hashes':['all','world']})
        # 24 full/fast lives, including the unwrapped references for replay recording.
        for role in ('I','A','B'):
            full=scratch(f'{world_name}_{role}_full',candidates[role],world,seeds,'full')
            fast=scratch(f'{world_name}_{role}_fast',candidates[role],world,seeds,'fast')
            if any(not equal(full[key],fast[key]) for key in ('ledger','diag','latency')):
                raise ValueError('full/fast mismatch')
            unwrapped[(world_name,role)]=full
            checks.append({'check':'full_fast','case':world_name+'_'+role,'passed':True,'hash_note':'fast hashes are not replay evidence'})
    # 30 recorded/replayed/control lives. The archived instrumentation logs all callbacks and requested actions.
    replaylib=libraries['replay']
    lib=checked_library(STUDY/replaylib['path'],replaylib['sha256'])
    lib.e7_log_size.restype=ctypes.c_long
    lib.e7_log_size.argtypes=[]
    lib.e7_log_copy.argtypes=[ctypes.POINTER(ctypes.c_double)]
    lib.e7_log_copy.restype=None
    lib.x_truth_count.restype=ctypes.c_long
    lib.x_truth_count.argtypes=[]
    def logged(label,candidate,world,seed,cid,override=None,extra=None):
        arrays=scratch(label,candidate,world,[seed],'replay',cid=cid,override=override,extra=extra)
        size=int(lib.e7_log_size())
        if size<=0 or size%6 or size>50_000_000 or lib.x_truth_count()!=0:
            raise ValueError('invalid/truncated/privileged replay log')
        log=np.empty(size,dtype=np.float64)
        lib.e7_log_copy(log.ctypes.data_as(ctypes.POINTER(ctypes.c_double)))
        log=log.reshape(-1,6)
        if not np.isfinite(log).all():raise ValueError('nonfinite replay log')
        callbacks=log[(log[:,0]==0)|(log[:,0]==4),:3].copy()
        actions=log[(log[:,0]!=0)&(log[:,0]!=4)].copy()
        return arrays,callbacks,actions
    for world_name,world in value['worlds'].items():
        for candidate in [x for x in world['candidates'] if x['role'] in ('I','A','B')]:
            role=candidate['role'];prefix=f'{world_name}_{role}'
            record,callbacks,actions=logged(prefix+'_record',candidate,world,seeds[0],1901)
            ref=unwrapped[(world_name,role)]
            if any(not equal(record[key],ref[key][:1]) for key in ('ledger','hashes','diag','latency')):
                raise ValueError('instrumentation changed retained controller result')
            extra=np.r_[len(callbacks),callbacks.reshape(-1)]
            ro={'flags':world['base_world']['flags']|H.V3.flags('receptor_off')}
            alien=dict(ro,v_t=.4,tau_turn=3.,t_resp=11.,R_min=3.,R_max=9.,sigma=.9,lam_s=.3)
            logs={'callbacks':callbacks,'actions':actions}
            for tag,seed,over in [('same_life',seeds[0],ro),('other_life',seeds[1],ro),('other_world',seeds[1],alien)]:
                replay,replayed_callbacks,other=logged(prefix+'_'+tag,candidate,world,seed,1902,over,extra)
                if not equal(callbacks,replayed_callbacks) or not equal(actions,other) or len(actions)==0 or replay['diag'][0,0]!=0:
                    raise ValueError('C5 replay leakage/action mismatch')
                logs[tag]=other
                logs[tag+'_callbacks']=replayed_callbacks
            _,_,control=logged(prefix+'_control',candidate,world,seeds[1],1901)
            if equal(actions,control):raise ValueError('closed-loop replay control did not differ')
            logs['control']=control
            persist(prefix+'_replay_logs',logs,{'simulation_calls':0,'source':'retained replay instrumentation','truth_calls':int(lib.x_truth_count())})
            checks.append({'check':'C5_replay','case':prefix,'passed':True,'callbacks':len(callbacks),'action_records':len(actions),'truth_calls':0})
    # 12 cost calibration lives; parameters, seeds, duration and research size remain fixed.
    for world_name,world in value['worlds'].items():
        for candidate in [x for x in world['candidates'] if x['role'] in ('I','A','B')]:
            scratch(f'{world_name}_{candidate["role"]}_calibration',candidate,world,seeds,'fast',1024)
    if count!=82:raise ValueError('validation life count changed')
    parent_check(parent,phase="validation");protocol()
    save(STUDY/'validation/report.json',{'status':'complete','simulation_calls':count,'protocol_sha256':protocol_sha,
        'source_pins':value['file_pins'],'production_pins':value['production_pins'],'libraries':libraries,
        'checks':checks,'artifacts':receipts,'no_retuning':True,'no_research_outcomes':True})


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run',action='store_true')
    parser.add_argument('--expected-parent',type=int)
    args=parser.parse_args()
    if args.run:
        validate(args.expected_parent)
    else:
        print(json.dumps({'status':'dry_run','simulation_calls':0,'planned_validation_lives':82,'research_lives':13312,'compiled_libraries':0,'planned_libraries':4,
                          'validation_cpu_cap':180,'note':'No compilation/simulation performed by this dry run.'}))
