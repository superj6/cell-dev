"""One owned worker: exactly1024 development and5632 confirmation calls after release."""
from pathlib import Path
import argparse,json,os,resource,sys,time
from common import STUDY,ROOT,ROLES,PRIOR_CPU,checked_release,parent_check,read,save,sha

def cpu():return sum(r.ru_utime+r.ru_stime for r in (resource.getrusage(0),resource.getrusage(-1)))

def run():
    parent_check();protocol=checked_release()
    import numpy as np
    from dataclasses import replace
    import raw as h
    sys.path.insert(0,str(STUDY/'policy_sources'))
    import make_ckernel
    inputs=read(STUDY/'inputs.json')
    world=h.spec.world('catch_delayed_match_l4',T=85.,t0=0.,t_open=0.)
    assert h.V.pack_world(world).tolist()==protocol['world_vector']
    production=h.build.load()
    matcher_path=Path(make_ckernel.build(STUDY/'build-cache/matcher.so',controllers=[STUDY/'policy_sources/matching.c']))
    matcher=h.load(matcher_path)
    save(STUDY/'startup.json',dict(simulator_calls=0,production_library=str(h.build.library_path()),
        production_sha256=sha(h.build.library_path()),matcher_library=str(matcher_path),
        matcher_sha256=sha(matcher_path),source_pins=protocol['source_pins']))
    raw=STUDY/'raw';raw.mkdir(exist_ok=False)
    index=[];durations={'tissue':[],'instrument':[]};selected=None

    def checkpoint():
        parent_check()
        monitored=read(STUDY/'budget.json')['cpu_seconds']
        if (PRIOR_CPU+max(cpu(),monitored)>=1195.0):
            raise RuntimeError('development stopped to preserve2400 CPU seconds for confirmation and cleanup')

    def account(x):
        row=x.ledger[0];L=h.V.L
        get=lambda key:float(row[L[key]])
        if not np.isfinite(row).all():raise ValueError('nonfinite ledger')
        invalid=sum(h.spec.STATUS[name] for name in ('raster_overflow','fate_overflow','ledger_mismatch','capacity'))
        if int(get('status'))&invalid:raise ValueError('invalid accounting/log status retained; no admission')
        for cls in ('narrow','broad'):
            assert get('choice_opportunities_'+cls)+get('choice_carry_in_'+cls)==sum(get(q+'_'+cls) for q in
                ('correct_choices','wrong_choices','choice_timeouts','unfinished_choices'))
        correct=get('correct_choices_narrow')+get('correct_choices_broad')
        wrong=get('wrong_choices_narrow')+get('wrong_choices_broad')
        assert get('income')==500.*correct
        col=world.c_live*get('live_time')
        for price,key in ((world.c_spike,'spikes'),(world.c_tw,'kappa_sum'),(world.c_msg,'contact_events'),
                          (world.c_div,'claims'),(world.c_sec,'sec_int'),(world.c_miss,'misses'),(world.c_rec,'rec_gain')):
            col=col+price*get(key)
        col=col+50.*wrong
        assert abs(col-get('cost'))<=1e-9*max(1.,abs(col))
        assert (get('income')-col-get('guard_charge'))/85.==get('F')

    def call(stage,seed,role,entry):
        parent_check()
        if stage=='development':checkpoint()
        if len(index)>=6656:raise ValueError('fixed scientific call ceiling reached')
        name=f'{stage}_{seed}_{role}'
        row=dict(index=len(index),stage=stage,seed=seed,role=role,status='started')
        index.append(row);save(STUDY/'row_index.json',index)
        started=cpu()
        if 'controller' in entry:
            x=h.run_controller(matcher,world,seed,entry['controller'],entry['parameters'])
            if x.diag[0,15]!=0.:raise ValueError('instrument numerical failure')
            backend='instrument'
        else:
            body=entry['body'];w=replace(world,flags=world.flags|h.V.FLAGS['program_mode']|body['flags'])
            x=h.run_tissue(production,w,seed,programs=np.asarray(body['program']),init=body['cells'])
            x.diag=np.zeros((1,16));backend='tissue'
        elapsed=cpu()-started;durations[backend].append(elapsed)
        rt,ru=x.spikes(0);fi,ff=x.fates(0)
        path=raw/(name+'.npz')
        np.savez_compressed(path,ledger=x.ledger,hashes=x.hashes,diag=x.diag,
            raster_t=rt,raster_uid=ru,fate_i=fi,fate_f=ff,seed=np.array(seed,dtype=np.uint64))
        row.update(status='complete',backend=backend,cpu_seconds=elapsed,path=str(path.relative_to(STUDY)),sha256=sha(path))
        save(STUDY/'row_index.json',index)
        account(x)
        return x

    def bits(a,b):
        if a.shape!=b.shape or a.dtype!=b.dtype or a.tobytes()!=b.tobytes():raise ValueError('paired identity mismatch')

    try:
        candidates=[dict(role=e['id'],body=e['body']) for e in inputs['reflex_panel']]+[
            dict(role=e['id'],controller=e['controller'],parameters=e['parameters']) for e in inputs['instrument_panel']]
        values=np.empty((16,64))
        for j,seed in enumerate(protocol['development_seeds']):
            for i,e in enumerate(candidates):values[i,j]=call('development',seed,e['role'],e).ledger[0,h.V.L['F']]
            if j==0:
                # Throughput-only decision; no arm changes or scientific seed inspection.
                projected=1.5*(max(durations['tissue'])*3840+max(durations['instrument'])*2816)
                save(STUDY/'throughput.json',dict(first_fixed_calls=16,conservative_projected_cpu=projected,
                    consumed_cpu=PRIOR_CPU+cpu(),remaining_cpu=3600.-PRIOR_CPU-cpu()))
                if projected>3600.-PRIOR_CPU-cpu()-5.:raise RuntimeError('fixed panel projected outside budget; incomplete')
        means=values.mean(axis=1);ri=int(np.argmax(means[:12]));ii=int(np.argmax(means[12:]))
        selected=dict(reflex_index=ri,instrument_index=ii,development_mean_F=means.tolist(),
                      tie_rule='first table row',no_confirmation_observed=True)
        save(STUDY/'selection.json',selected,exclusive=True)
        checkpoint();checked_release()
        ref=inputs['reflex_panel'][ri];instrument=inputs['instrument_panel'][ii]
        arms={role:dict(controller=10+i,parameters=instrument['parameters']) for i,role in enumerate(ROLES[:5])}
        arms.update(R0=dict(body=inputs['R0']),R1=dict(body=ref['body']))
        arms.update({role:dict(body=body) for role,body in inputs['do_less_by_reflex'][ri].items()})
        save(STUDY/'selected_arms.json',arms,exclusive=True)
        for seed in protocol['confirmation_seeds']:
            observed={}
            for role in ROLES:observed[role]=call('confirmation',seed,role,arms[role])
            e,p=observed['E'],observed['P']
            bits(e.ledger,p.ledger);bits(e.hashes,p.hashes)
            for x,y in zip(e.spikes(0),p.spikes(0)):bits(x,y)
            for x,y in zip(e.fates(0),p.fates(0)):bits(x,y)
            bits(e.diag[:,6:],p.diag[:,6:])
            i=observed['I'];bits(i.diag[:,5:6],e.diag[:,5:6])
            it,iu=i.spikes(0);et,eu=e.spikes(0)
            bits(it[it<65.5],et[et<65.5]);bits(iu[it<65.5],eu[et<65.5])
        assert len(index)==6656 and all(r['status']=='complete' for r in index)
        checked_release();parent_check()
        from analyze import analyze
        summary=analyze(protocol,index)
        save(STUDY/'summary.json',summary)
        save(STUDY/'measurement_complete.json',dict(status='complete',backend_calls=6656,engineering_calls=40,
            total_package_calls=6696,development_calls=1024,confirmation_calls=5632,
            protocol_sha256=sha(STUDY/'protocol.json'),row_index_sha256=sha(STUDY/'row_index.json'),
            summary_sha256=sha(STUDY/'summary.json'),selected_arms_sha256=sha(STUDY/'selected_arms.json')))
    except BaseException as error:
        save(STUDY/'measurement_incomplete.json',dict(status='incomplete',error=repr(error),
             attempted_calls=len(index),completed_calls=sum(r['status']=='complete' for r in index),
             selection=selected,cpu_seconds=PRIOR_CPU+cpu()))
        raise

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--run-child',action='store_true');a=p.parse_args()
    if a.run_child:run()
    else:print(json.dumps(dict(status='source_only',new_simulator_calls=0,planned_scientific_calls=6656)))
