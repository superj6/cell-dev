"""Materialize deterministic inputs/pins only: no build, life, or random draw."""
from pathlib import Path
from dataclasses import asdict
import sys,shutil
from common import ROOT,STUDY,ROLES,PRIOR_CPU,PRIOR_WALL,read,save,sha

def prepare():
    if (STUDY/'protocol.json').exists():raise ValueError('preserve prior preparation; no silent overwrite')
    audit=read(STUDY.parent/'seed_audit.json')
    if audit.get('status') not in ('passed','available'):raise ValueError('namespace audit not passed')
    import raw as h
    from panels import reflex_panel,do_less,INSTRUMENTS
    production={}
    for path in sorted((ROOT/'src').rglob('*.py')):
        production[str(path.relative_to(ROOT))]=sha(path)
    production['src/life/kernel.c']=sha(ROOT/'src/life/kernel.c')
    isolated=ROOT/'outputs/abi5_delayed_match_20261015/worktree'
    compared={}
    for name in ('kernel.c','spec.py','reference.py','build.py','handbuilt.py'):
        a,b=ROOT/'src/life'/name,isolated/'src/life'/name
        if a.read_bytes()!=b.read_bytes():raise ValueError('production differs from engineering '+name)
        compared[name]=sha(a)
    assert sha(STUDY/'policy_sources/kernel.abi5.c')==production['src/life/kernel.c']
    r0,rows=reflex_panel()
    inputs=dict(R0=r0,reflex_panel=rows,instrument_panel=INSTRUMENTS,
                do_less_by_reflex=[do_less(r['knobs']) for r in rows])
    save(STUDY/'inputs.json',inputs,exclusive=True)
    seeds=dict(development=list(range(52440000,52440064)),confirmation=list(range(52450000,52450512)))
    assert not set(seeds['development'])&set(seeds['confirmation'])
    save(STUDY/'seeds.json',seeds,exclusive=True)
    save(STUDY/'reservation.json',dict(status='reserved for this prepared, unreleased study',
        blocks=[144,145],whole_blocks_half_open=[[52440000,52450000],[52450000,52460000]],
        actual_seed_arrays_sha256=sha(STUDY/'seeds.json'),seed_audit_sha256=sha(STUDY.parent/'seed_audit.json')),
        exclusive=True)
    save(STUDY/'production_equivalence.json',dict(reference_revision='968bb81f2e146e2e729bca43004628d78a6e9b99',
        compared_sha256=compared,policy_kernel_sha256=sha(STUDY/'policy_sources/kernel.abi5.c'),
        import_root=str(ROOT),isolated_engineering_sources_preserved=True),exclusive=True)
    proposal=ROOT/'outputs/abi5_delayed_match_20261015/coordination/INFORMATION_PAYOFF_PLAN.md'
    shutil.copyfile(proposal,STUDY/'initial_proposal.md')
    shutil.copyfile(STUDY.parent/'INSTRUMENT_SPEC_DRAFT.md',STUDY/'instrument_spec.md')
    source={str(p.relative_to(STUDY)):sha(p) for p in sorted(STUDY.rglob('*'))
            if p.suffix in ('.py','.c','.h','.md')}
    world=h.spec.world('catch_delayed_match_l4',T=85.,t0=0.,t_open=0.)
    protocol=dict(status='prepared_unreleased',title='ABI5 delayed matching information diagnostic',abi=5,
        source_revision='968bb81f2e146e2e729bca43004628d78a6e9b99',roles=list(ROLES),world=asdict(world),
        world_vector=h.V.pack_world(world).tolist(),ledger_columns=list(h.V.LEDGER),
        development_seeds=seeds['development'],confirmation_seeds=seeds['confirmation'],
        development_calls=1024,confirmation_calls=5632,scientific_calls=6656,engineering_calls=40,total_calls=6696,
        scientific_backends=dict(production_C_full=3840,scratch_C_full=2816),
        cumulative_budget=dict(cpu_seconds=3600.,wall_seconds=5400.,prior_engineering_cpu_seconds=PRIOR_CPU,
            prior_engineering_wall_seconds=PRIOR_WALL,confirmation_cpu_reserve=2400.),
        remaining_monitored_budget=dict(cpu_seconds=3600.-PRIOR_CPU,wall_seconds=5400.-PRIOR_WALL,
            cleanup_margin_seconds=5.,threads=1,workers=1,address_space_bytes=8*1024**3,
            rss_bytes=4*1024**3,minimum_available_bytes=4*1024**3),
        source_pins=source,production_pins=production,
        input_pins={name:sha(STUDY/name) for name in ('inputs.json','seeds.json','production_equivalence.json')},
        seed_audit_sha256=sha(STUDY.parent/'seed_audit.json'),reservation_sha256=sha(STUDY/'reservation.json'),
        engineering_receipt_sha256=sha(STUDY.parent/'harness_validation_receipt.json'),
        readouts='native whole-life/class counters for all roles; instrument-only first opportunity and sample calibration; no capture-time/reflex-first-trial claim',
        release='missing release.json intentionally; root must announce and bind exact protocol after source review')
    save(STUDY/'protocol.json',protocol,exclusive=True)
    save(STUDY/'READY.json',dict(status='prepared_unreleased',protocol_sha256=sha(STUDY/'protocol.json'),
        preparation_lives=0,preparation_builds=0,preparation_random_draws=0),exclusive=True)
    print(STUDY/'READY.json')

if __name__=='__main__':prepare()
