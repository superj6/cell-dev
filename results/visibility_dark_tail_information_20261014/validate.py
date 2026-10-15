"""Fixed 76-life AD validation package; no automatic release or extension. Default dry run."""
from __future__ import annotations

import argparse
import ctypes
import importlib
import json
import os
import subprocess
import sys
import time
from pathlib import Path

import numpy as np
from contracts import ROLES, VALIDATION_MATRIX, calibration_projection

from common import ROOT, STUDY, parent_check, protocol, read, require_release, save, sha


def equal(a,b):
    return a.shape==b.shape and a.dtype==b.dtype and a.tobytes()==b.tobytes()


def compile_libraries(value):
    from frozen import BUNDLE, checked_library, load_harness
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
    # The production identity lives run in a separate process before any scratch imports.
    # It inherits this validation worker's process group, environment and CPU limits.
    save(STUDY/'validation/progress.json',{'status':'running','simulation_calls_started':2,'current':'production_identity'})
    subprocess.run([sys.executable,str(STUDY/'production_identity.py'),'--run',
                    '--expected-parent',str(os.getpid())],check=True)
    identity_path=STUDY/'validation/startup_identity.json'
    identity=read(identity_path)
    if (identity.get('status')!='complete' or identity.get('simulation_calls')!=2
            or identity.get('numerical_identity_invocations')!=1
            or identity.get('identity')!=value['expected_numerical_identity']):
        raise ValueError('isolated standard numerical identity pair incomplete')
    libraries=compile_libraries(value)
    from frozen import checked_library, load_harness
    from raw import run
    H=load_harness()
    protocol_sha=sha(STUDY/'protocol.json')
    seeds=value['validation_seeds'][:2]
    count=2
    receipts={'startup_identity':{'path':str(identity_path.relative_to(STUDY)),
        'sha256':sha(identity_path),'simulation_calls':2,'T':200,'seeds':[11,11],
        'library':'isolated_production_full_and_fast'}}
    def persist(label,arrays,meta):
        path=STUDY/'validation'/(label+'.npz')
        np.savez_compressed(path,**arrays)
        receipts[label]={'path':str(path.relative_to(STUDY)),'sha256':sha(path),**meta}
        return arrays
    def scratch(label,candidate,world,seeds_,libkey='full',duration=128,override=None,cid=None,extra=None):
        nonlocal count
        parent_check(parent,phase="validation")
        protocol()
        count+=len(seeds_)
        save(STUDY/'validation/progress.json',{'status':'running','simulation_calls_started':count,'current':label})
        c0,w0=time.process_time(),time.monotonic()
        lib=libraries[libkey]
        arrays=run(candidate,world,seeds_,STUDY/lib['path'],lib['sha256'],duration=duration,override=override,cid=cid,extra=extra)
        arrays.update(cpu_seconds=np.asarray(time.process_time()-c0),wall_seconds=np.asarray(time.monotonic()-w0))
        return persist(label,arrays,{'simulation_calls':len(seeds_),'T':duration,'seeds':seeds_,'library':libkey})
    checks=[]
    unwrapped={}
    # 8 tissue bridge lives: R0/R1 x first two seeds x scratch/production.
    for world_name,world in value['worlds'].items():
        candidates={x['role']:x for x in world['candidates']}
        for role in ('R0','R1'):
            for index,seed in enumerate(seeds):
                label=f'{world_name}_{role}_{index}'
                old=scratch(label+'_scratch',candidates[role],world,[seed])
                path=STUDY/'validation'/(label+'_production.npz')
                lib=libraries['production']
                parent_check(parent,phase="validation")
                protocol()
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
                if not passed:
                    raise ValueError('scratch/production physical bridge failed: '+label)
                checks.append({'check':'production_bridge','case':label,'passed':True,'excluded_ledger':[21,22],
                               'mapped_capture_column':[21,57],'excluded_hashes':['all','world']})
        # 12 full/fast lives: I/A/B x first two seeds x full/fast.
        for role in ('I','A','B'):
            full=scratch(f'{world_name}_{role}_full',candidates[role],world,seeds,'full')
            fast=scratch(f'{world_name}_{role}_fast',candidates[role],world,seeds,'fast')
            if any(not equal(full[key],fast[key]) for key in ('ledger','diag','latency')):
                raise ValueError('full/fast mismatch')
            unwrapped[(world_name,role)]=full
            checks.append({'check':'full_fast','case':world_name+'_'+role,'passed':True,'hash_note':'fast hashes are not replay evidence'})
    # 15 recorded/replayed/control lives. All callbacks and requested actions are logged.
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
        if not np.isfinite(log).all():
            raise ValueError('nonfinite replay log')
        callbacks=log[(log[:,0]==0)|(log[:,0]==4),:3].copy()
        actions=log[(log[:,0]!=0)&(log[:,0]!=4)].copy()
        return arrays,callbacks,actions
    for world_name,world in value['worlds'].items():
        for candidate in [x for x in world['candidates'] if x['role'] in ('I','A','B')]:
            role=candidate['role']
            prefix=f'{world_name}_{role}'
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
            if equal(actions,control):
                raise ValueError('closed-loop replay control did not differ')
            logs['control']=control
            persist(prefix+'_replay_logs',logs,{'simulation_calls':0,'source':'retained replay instrumentation','truth_calls':int(lib.x_truth_count())})
            checks.append({'check':'C5_replay','case':prefix,'passed':True,'callbacks':len(callbacks),'action_records':len(actions),'truth_calls':0})
    # 39 cost calibration lives: every fixed role on the same three fresh seeds.
    calibration_cpu={}
    for world_name,world in value['worlds'].items():
        if [candidate['role'] for candidate in world['candidates']]!=ROLES:
            raise ValueError('calibration role order changed')
        for candidate in world['candidates']:
            row=scratch(f'{world_name}_{candidate["role"]}_calibration',candidate,world,
                        value['validation_seeds'],'fast',1024)
            calibration_cpu[candidate['role']]=float(row['cpu_seconds'])
    if count!=76:
        raise ValueError('validation life count changed')
    projection=calibration_projection(calibration_cpu,value['historical_cpu_per_life'])
    save(STUDY/'validation/calibration_projection.json',projection)
    if not projection['feasible']:
        raise ValueError('fixed cost feasibility gate failed; no research or extension')
    parent_check(parent,phase="validation")
    protocol()
    save(STUDY/'validation/report.json',{'status':'complete','simulation_calls':count,'protocol_sha256':protocol_sha,
        'source_pins':value['file_pins'],'production_pins':value['production_pins'],'libraries':libraries,
        'checks':checks,'artifacts':receipts,'no_retuning':True,'no_research_outcomes':True,
        'identity':receipts['startup_identity'],'validation_matrix':VALIDATION_MATRIX,
        'calibration_cpu_seconds':calibration_cpu,'calibration_projection':projection})


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run',action='store_true')
    parser.add_argument('--expected-parent',type=int)
    args=parser.parse_args()
    if args.run:
        validate(args.expected_parent)
    else:
        print(json.dumps({'status':'dry_run','simulation_calls':0,'planned_validation_lives':76,'research_lives':6656,'compiled_libraries':0,'planned_libraries':6,'standard_identity_invocations':1,
                          'validation_cpu_cap':180,'note':'No compilation/simulation performed by this dry run.'}))
