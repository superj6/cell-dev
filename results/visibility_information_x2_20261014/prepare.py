"""Freeze unchanged sources and exact candidate arrays. Default dry run; no compilation or simulation."""
from __future__ import annotations
import argparse
from dataclasses import asdict
import json
from pathlib import Path
import platform
import shutil
import subprocess
import sys

import numpy as np
from common import ACTION, ROOT, ROLES, SIZES, STUDY, WORLDS, read, save, sha


def copy_exact(source, target):
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists() and target.read_bytes() != source.read_bytes():
        raise ValueError('already copied input changed: ' + str(target))
    if not target.exists():
        shutil.copyfile(source, target)
    return {'source': str(source.relative_to(ROOT)), 'sha256': sha(target)}


def bundle():
    records = {}
    original = ROOT / 'results/prediction_information_20261014/original'
    for source in sorted((original / 'src').rglob('*.py')) + [original / 'src/life/kernel.c']:
        target = STUDY / 'original' / source.relative_to(original)
        records[str(target.relative_to(STUDY))] = copy_exact(source, target)
    harness = ROOT / 'results/open_headroom/harness'
    for pattern in ('*.c', '*.h', 'harness.py', 'make_ckernel.py'):
        for source in sorted(harness.glob(pattern)):
            target = STUDY / 'original/harness' / source.name
            records[str(target.relative_to(STUDY))] = copy_exact(source, target)
    for name in ('mem_ctl.c', 'mcommon.py', 't8_score.py'):
        source = ROOT / 'results/open_headroom/controllers' / name
        target = STUDY / 'original/controllers' / name
        records[str(target.relative_to(STUDY))] = copy_exact(source, target)
    source = ROOT / 'results/taskvar/measurement/replay_wrapper.c.in'
    target = STUDY / 'original/replay_wrapper.c.in'
    records[str(target.relative_to(STUDY))] = copy_exact(source, target)
    save(STUDY / 'bundle.json', {'status': 'copied_byte_identical', 'origins': records,
         'file_pins': {name: item['sha256'] for name, item in records.items()}})


def descriptions(recovered):
    knobs = recovered['retuned_reflex_knobs']
    rows = [{'role': r, 'kind': k, 'footprint': fp, 'knobs': v} for r,k,fp,v in (
        ('R0','frozen_reflex','hollow3',None), ('R1','retuned_reflex','hollow3',knobs),
        ('D0','do_less','hollow2',None), ('D1','do_less','hollow2',knobs),
        ('D2','do_less','ring2',None), ('D3','do_less','clicker',None),
        ('D4','do_less','hollow3',dict(knobs, **{'K.w0':.75})),
        ('D5','do_less','hollow3',dict(knobs, **{'C.g_r':.5})),
        ('D6','do_less','hollow3',dict(knobs, **{'C.t_ref':4.,'K.t_ref':4.})),
        ('D7','do_less','hollow3',dict(knobs, **{'M.kappa':.5}))) ]
    for role, changes in [('I',{}), ('A', recovered['ablation_A_changes']), ('B',recovered['ablation_B_changes'])]:
        params = list(recovered['full_parameters'])
        for index, value in changes.items():
            params[int(index)] = value
        rows.append({'role':role,'kind':'information' if role == 'I' else 'broad_ablation',
                     'footprint':'hollow3','params':params,'controller_id':1102,'action':ACTION,
                     'isolates_capability':False,'changed_parameter_indices':sorted(map(int,changes))})
    return sorted(rows, key=lambda row: ROLES.index(row['role']))


def candidate_arrays(H, descriptor):
    record = dict(descriptor)
    if 'params' in record:
        fp = H.footprint(record['footprint'])
        cells, program, flags = fp.cells(), H.INERT_PROGRAM, 0
        record['sense_sites'], record['act_sites'] = [list(row) for row in fp.sense], [list(row) for row in fp.act]
    else:
        body = H.hb.CLICKER if record['footprint'] == 'clicker' else H.reflex(record['footprint'], record['knobs'])
        cells, program, flags = body.cells, body.program, body.flags
    record.update(cells=[list(row) for row in cells], program=np.asarray(program, dtype=np.float64).tolist(),
                  body_flags=int(flags), cell_count=len(cells))
    if len(record['program']) != 129 or any(len(c) != 4 for c in record['cells']):
        raise ValueError('candidate ABI mismatch')
    record['program_bytes_sha256'] = __import__('hashlib').sha256(np.asarray(program,dtype='<f8').tobytes()).hexdigest()
    record['cells_bytes_sha256'] = __import__('hashlib').sha256(np.asarray(cells,dtype='<i4').tobytes()).hexdigest()
    return record


def prepare():
    if (STUDY/'ready.json').exists() or (STUDY/'budget.json').exists():
        raise ValueError('prepared/released study is immutable')
    bundle()
    source = ROOT/'outputs/audit_visibility_information_20261014/recovered_inputs.json'
    copy_exact(source,STUDY/'inputs/recovered_inputs.json')
    recovered = read(source)
    for name, entry in recovered['worlds'].items():
        for key in ('score_source','tune_source'):
            if entry[key]:
                copy_exact(ROOT/entry[key], STUDY/'inputs'/name/Path(entry[key]).name)
    copy_exact(ROOT/'outputs/openhr/memory/reflex_knobs_mem.json',STUDY/'inputs/reflex_knobs_mem.json')
    # Production import is isolated in a subprocess: no ABI-4 module enters this worker.
    production_snapshot = json.loads(subprocess.check_output([sys.executable,str(STUDY/'production_snapshot.py')], cwd=ROOT))
    production = production_snapshot['worlds']
    save(STUDY/'inputs/production_worlds.json',production_snapshot)
    audit = ROOT/'outputs/audit_visibility_information_20261014'
    for name in ('namespace_audit.json','namespace_inventory.json','root_text_namespace_review.json','independent_review.json','independent_review.md'):
        if (audit/name).exists():
            # Review receipts may be refreshed while preparation remains unreleased.
            (STUDY/'inputs/reviews').mkdir(parents=True,exist_ok=True)
            shutil.copyfile(audit/name,STUDY/'inputs/reviews'/name)
    from frozen import load_harness, modules_pinned
    H = load_harness()
    worlds = {}
    for name in WORLDS:
        slots = ({'blink_on':5.,'blink_off':-1.,'dim_flag':777.,'dark_amp':.25} if name == 'flash5_dim25'
                 else {'blink_on':20.,'blink_off':20.})
        world = H.WorldSpec(name,over={'T':1024},x=slots)
        packed, base = H.world_vectors(world,H.build._seeds([0]),flags=H.V3.flags('program_mode'))
        candidates = [candidate_arrays(H,item) for item in descriptions(recovered['worlds'][name])]
        if [x['role'] for x in candidates] != ROLES:
            raise ValueError('candidate order changed')
        prod = production[name]
        if len(prod['packed_world']) != 70 or prod['sizes'] != [4,875,129,70,58,5,23,1024,7,18]:
            raise ValueError('production ABI sizes differ')
        old = asdict(H.spec.world('catch_speck_l4',T=1024))
        if any(prod['world'][key] != value for key,value in old.items() if key not in ('name','stage')):
            raise ValueError('production inherited world changed')
        worlds[name] = {'base_world':asdict(base),'scratch_slots':slots,'packed_world':packed[0].tolist(),
                        'production':prod,'candidates':candidates}
    modules_pinned()
    production_paths = [ROOT/name for name in production_snapshot['module_pins']]
    production_paths += [ROOT/'src/life'/n for n in ('kernel.c','spec.py','build.py','reference.py')]
    production_paths += [ROOT/'results/abi4_visibility_20261014'/n for n in ('manifest.json','finalization.json')]
    for folder in ('final_truth','scratch_bridge_replay_guarded'):
        production_paths += [p for p in (ROOT/'results/abi4_visibility_20261014'/folder).rglob('*') if p.is_file() and '__pycache__' not in p.parts]
    file_pins = {str(p.relative_to(STUDY)):sha(p) for folder in ('original','inputs')
                 for p in (STUDY/folder).rglob('*') if p.is_file() and '__pycache__' not in p.parts}
    for path in sorted(STUDY.glob('*.py')) + [STUDY/'bundle.json',STUDY/'README.md',STUDY/'PREREG.md']:
        file_pins[path.name] = sha(path)
    compiler = Path(shutil.which('gcc')).resolve()
    protocol = {'format':1,'study':'X2 visibility information','status':'prepared_not_released','T':1024,'n':512,
        'seeds':list(range(52_130_000,52_130_512)),'seed_block':113,'validation_seed_block':116,
        'validation_seeds':[52_160_000,52_160_001], 'seed_registration':'root_release_required',
        'worlds':worlds,'abi3_sizes':SIZES,'raw_ledger_aliases':{'21':'dark_captures','22':'late_captures'},
        'monitor_scope':{'total_cpu_seconds':3599,'validation_cpu_seconds':179,'max_workers':2,
                         'threads_per_worker':1,'research_lives':13312,'validation_lives':82,'worlds':WORLDS,'roles':ROLES},
        'production_binding':{'status':'complete','integrated_commit':'3c8893b','note':'read-only preset packing; bridge acceptance pins retained'},
        'production_pins':{str(p.relative_to(ROOT)):sha(p) for p in production_paths},
        'production_module_pins':production_snapshot['module_pins'],'file_pins':file_pins,
        'numerical_identity':__import__('numerical').identity(),
        'analysis':{'reference_roles':['R0','R1'],'do_less_roles':ROLES[5:],'full':'I','broad_ablations':['A','B'],
            'reference':'best whole mean; fixed I-R0/I-R1 reported too','information_min_F':1.,'information_SE_multiple':3.,
            'do_less_max_fraction':.25,'capability_specific_admission':'incomplete','G5':'held_unreserved',
            'fitness':'raw accountant F; no added extinction penalty','failure_policy':'any invalid life or missing row leaves complete status false'},
        'simulation_calls_completed':0,'compiled_libraries':0,
        'prior_attempt':{'study':'X','status':'incomplete_before_compile_or_life','cpu_seconds':0.716548,
            'simulation_calls':0,'compiled_libraries':0,'budget_path':'inputs/prior_attempt_X/budget.json',
            'budget_sha256':sha(STUDY/'inputs/prior_attempt_X/budget.json'),
            'combined_total_cpu_upper_bound':3599.716548,'combined_validation_cpu_upper_bound':179.716548}}
    save(STUDY/'protocol.json',protocol)
    save(STUDY/'preparation.json',{'status':'prepared_no_simulation','protocol_sha256':sha(STUDY/'protocol.json'),
                                  'simulation_calls':0,'compiled_libraries':0,'release':False})
    return {'status':'prepared_no_simulation','protocol_sha256':sha(STUDY/'protocol.json'),'worlds':WORLDS,'roles':ROLES}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--prepare',action='store_true')
    args = parser.parse_args()
    print(json.dumps(prepare() if args.prepare else {'status':'dry_run','simulation_calls':0,'compiled_libraries':0,
          'research_lives':13312,'validation_lives':82,'total_cpu_seconds':3599,'validation_cpu_seconds':179}))
