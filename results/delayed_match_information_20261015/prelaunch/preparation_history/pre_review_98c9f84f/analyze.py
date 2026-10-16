"""Fixed seed-cluster paired analysis; only saved rows, never new simulator lives."""
import numpy as np
from common import STUDY,ROLES,sha
import raw as h

def summary(x):
    x=np.asarray(x,dtype=float)
    return dict(n=len(x),mean=float(x.mean()),se=float(x.std(ddof=1)/np.sqrt(len(x))))

def analyze(protocol,index):
    arrays={};diags={}
    for role in ROLES:
        rows=[r for r in index if r['stage']=='confirmation' and r['role']==role]
        assert [r['seed'] for r in rows]==protocol['confirmation_seeds']
        values=[];ds=[]
        for r in rows:
            p=STUDY/r['path'];assert sha(p)==r['sha256']
            with np.load(p,allow_pickle=False) as x:values.append(x['ledger'][0]);ds.append(x['diag'][0])
        arrays[role]=np.asarray(values);diags[role]=np.asarray(ds)
    L=h.V.L
    get=lambda role,key:arrays[role][:,L[key]]
    fs={role:get(role,'F') for role in ROLES}
    contrasts={}
    for ref in ('R0','R1','E','N','B'):
        s=summary(fs['I']-fs[ref]);s.update(pass_1F_3SE=s['mean']>=1. and s['mean']>3.*s['se'])
        contrasts['I-'+ref]=s
    margins={}
    for ref in ('R0','R1'):
        for d in ('D0','D1','D2','D3'):
            s=summary(.25*fs['I']+.75*fs[ref]-fs[d]);s.update(point_pass=s['mean']>0.,
                lower_three_se=s['mean']-3.*s['se'],do_less_gain=summary(fs[d]-fs[ref]))
            margins[ref+'/'+d]=s
    per_role={}
    for role in ROLES:
        entry=dict(F=summary(fs[role]),status_counts={str(int(s)):int(np.sum(get(role,'status')==s)) for s in np.unique(get(role,'status'))},
                   ledger_means={key:float(get(role,key).mean()) for key in h.V.LEDGER},classes={})
        for cls in ('narrow','broad'):
            counts={metric:float(get(role,metric+'_'+cls).sum()) for metric in
                ('choice_opportunities','choice_carry_in','correct_choices','wrong_choices','choice_timeouts','unfinished_choices')}
            opportunities=counts['choice_opportunities']+counts['choice_carry_in']
            complete=counts['correct_choices']+counts['wrong_choices']
            counts.update(correct_per_opportunity=None if not opportunities else counts['correct_choices']/opportunities,
                completion_coverage=None if not opportunities else complete/opportunities,
                accuracy_among_completed=None if not complete else counts['correct_choices']/complete,
                gross_reward_per_opportunity=None if not opportunities else (500.*counts['correct_choices']-50.*counts['wrong_choices'])/opportunities,
                narrow_hits=counts['correct_choices'] if cls=='narrow' else counts['wrong_choices'],
                broad_hits=counts['wrong_choices'] if cls=='narrow' else counts['correct_choices'])
            entry['classes'][cls]=counts
        if role in ('I','E','P','N','B'):
            opens=get(role,'choice_opportunities_narrow')+get(role,'choice_opportunities_broad')
            assert np.all(opens<=1.)
            entry['first_trial_scope']='These native class outcomes are the only instrument opportunity; missing/guard cases retained.'
            entry['attempted_tap_callback_count']=int(np.sum(diags[role][:,10]>0.))
            entry['attempted_tap_callback_mean']=None if not np.any(diags[role][:,10]>0.) else float(diags[role][diags[role][:,10]>0.,10].mean())
        per_role[role]=entry
    opn=get('I','choice_opportunities_narrow');opb=get('I','choice_opportunities_broad')
    known=(opn+opb)==1.;y=opn[known];logit=diags['I'][known,5]
    probability=np.exp(-np.logaddexp(0.,-logit))
    calibration=dict(label_source='sole opened native instrument opportunity class; no hidden input to controller',
        n=int(known.sum()),missing=int((~known).sum()),class_counts={'narrow':int(y.sum()),'broad':int(len(y)-y.sum())},
        brier=None if not len(y) else float(np.mean((probability-y)**2)),
        log_loss=None if not len(y) else float(np.mean(np.logaddexp(0.,-(2.*y-1.)*logit))),
        sample_class_accuracy=None if not len(y) else float(np.mean((logit>=0.)==y)))
    admitted=all(contrasts['I-'+r]['pass_1F_3SE'] for r in ('R0','R1','E')) and all(m['point_pass'] for m in margins.values())
    return dict(status='complete',scope='exact T85 fixed-footprint information diagnostic',paired_life_clusters=512,
        contrasts=contrasts,do_less_margins=margins,roles=per_role,sample_calibration=calibration,
        E_P_full_bitwise_identity=True,section_0_4_thresholds_met=admitted,
        unmeasured=['reflex first-trial decomposition','actual capture times','repeated matching','evolved mechanism','mutation gradient','T1024 admission'],
        caveat='Best means the declared development-selected finite family; no evolved behavior or hand-built winner claim.')
