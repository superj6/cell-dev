"""Deterministic finite body/controller tables. No RNG, builds or lives."""
from itertools import product
import raw as h

def encoded(body):
    return dict(name=body.name,program=body.program.tolist(),cells=[list(c) for c in body.cells],flags=int(body.flags))

def reflex_panel():
    base=dict(h.hb.SPECK_TUNED['reflex@hollow3'])
    rows=[]
    for i,(sensor,motor,hot) in enumerate(product((.5,1.,2.),(.5,1.),(.5,1.))):
        knobs=dict(base)
        for key in ('S.g_r','C.g_r'):knobs[key]=h.spec.q8(knobs[key]*sensor)
        knobs['M.kappa']*=motor;knobs['K.kappa']*=hot
        assert h.hb.on_kernel_grid(knobs)
        rows.append(dict(id=f'R{i:02d}',factors=[sensor,motor,hot],knobs=knobs,
                         body=encoded(h.hb.role_body(knobs,'hollow3',name=f'panel_R{i:02d}'))))
    return encoded(h.hb.role_body(base,'hollow3',name='R0_unchanged_reflex')),rows

def do_less(knobs):
    quiet=dict(knobs)
    for key in ('S.g_r','C.g_r'):quiet[key]=h.spec.q8(quiet[key]*.5)
    weaker=dict(knobs)
    for key in ('M.kappa','K.kappa'):
        k=h.spec.KAPPA.index(weaker[key]);weaker[key]=h.spec.KAPPA[max(0,k-1)]
    program,cells=h.inert('hollow3')
    return {
        'D0':dict(name='D0_inert',program=program.tolist(),cells=[list(c) for c in cells],flags=0),
        'D1':encoded(h.hb.role_body(quiet,'hollow3',name='D1_half_sense')),
        'D2':encoded(h.hb.role_body(weaker,'hollow3',name='D2_lower_motor_grid')),
        'D3':encoded(h.hb.role_body(knobs,'hollow2',name='D3_smaller'))}

INSTRUMENTS=[dict(id=f'I{i}',controller=10,parameters=[dt,threshold])
             for i,(dt,threshold) in enumerate(product((.25,.5),(.75,.9)))]
