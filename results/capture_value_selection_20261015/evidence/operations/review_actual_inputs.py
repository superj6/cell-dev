"""Read-only prepared AM review; NumPy/YAML and source AST only, never engine imports."""
import ast
import copy
import hashlib
import json
from pathlib import Path
import sys

import numpy as np
import yaml

from audit_namespace import derive_native_ids

ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent
STUDY = ROOT / 'outputs/autonomous_capture_value_selection_20261015'
PROTOCOL = '9210e218d92d912f8b63822980de7fab868ad8904417d0f438a55e2b42922294'

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def read(path):
    return json.loads(path.read_text())

def raw_sha(array):
    return hashlib.sha256(array.tobytes()).hexdigest()

def main():
    assert sha(STUDY/'protocol.json') == PROTOCOL
    p=read(STUDY/'protocol.json')
    pin_counts={}
    for key,base in [('source_pins',STUDY),('input_pins',STUDY),('production_pins',ROOT),
                     ('original_input_pins',ROOT),('review_pins',ROOT)]:
        for name,digest in p[key].items():
            path=(base/name).resolve()
            assert path.is_relative_to(base.resolve()) and sha(path)==digest,name
        pin_counts[key]=len(p[key])
    assert all(not (STUDY/name).exists() for name in ('release.json','attempt.json','execution','build-cache','raw','runs'))
    pop=read(STUDY/'inputs/input_population.json'); rec=p['population_start']
    assert sha(STUDY/'inputs/input_population.json')==rec['file_sha256']
    assert sha(ROOT/'results/retention_selection_20261015/runs/balanced_mixture/population.json')==rec['file_sha256']
    tree=ast.parse((ROOT/'src/genome.py').read_text())
    fields=next(node for node in tree.body if isinstance(node,ast.FunctionDef) and node.name=='_life_fields')
    order=[ast.literal_eval(call.args[0]) for call in fields.body[1].value.elts]
    expected_shapes={'W':(16,25),'b':(16,),'lam':(16,),'s0':(16,),'Q':(16,),
                     'act':(16,),'A':(23,16),'a0':(23,),'Dm':(2,),'km':(2,)}
    table=[]
    for row in pop['genomes']:
        arrays=[np.asarray(row[key],dtype=np.float32) for key in order]
        assert all(array.shape==expected_shapes[key] for key,array in zip(order,arrays))
        table.append(np.concatenate([array.ravel() for array in arrays]))
    table=np.stack(table)
    assert table.shape==(32,875) and np.isfinite(table).all()
    hashes=[raw_sha(row) for row in table]
    assert hashes==rec['row_sha256'] and raw_sha(table)==rec['population_raw_sha256']
    assert rec['old_ids']==pop['ids'] and len(set(pop['ids']))==32 and rec['new_ids']==list(range(32))
    assert rec['old_to_new']==[{'old_id':old,'new_id':i,'row':i,'raw_sha256':hashes[i]}
                              for i,old in enumerate(pop['ids'])]
    ref=p['reference']; endpoint=read(STUDY/ref['path'])
    flat=np.concatenate([np.asarray(endpoint['params'][key],dtype=np.float32).ravel() for key in order])
    assert flat.tobytes()==table[0].tobytes() and raw_sha(flat)==ref['raw_sha256']
    assert sha(STUDY/ref['path'])==ref['file_sha256']
    ancestor=p['ancestral_reference']; original=read(STUDY/ancestor['path'])
    ancestor_flat=np.concatenate([np.asarray(original['params'][key],dtype=np.float32).ravel() for key in order])
    assert ancestor_flat.shape==(875,) and np.isfinite(ancestor_flat).all()
    assert raw_sha(ancestor_flat)==ancestor['raw_sha256'] and sha(STUDY/ancestor['path'])==ancestor['file_sha256']
    assert sha(ROOT/ancestor['source'])==ancestor['file_sha256'] and sha(ROOT/ref['source'])==ref['file_sha256']
    prior=read(STUDY/'inputs/AL_native_audit.json')['runs']['balanced_mixture']
    assert prior['all_32_final_rows_bound'] and prior['genetic_replay']['raw_population_replay_bitwise']
    assert prior['checkpoint_sha256']==sha(STUDY/'inputs/AL_checkpoint.pt')
    assert read(STUDY/'inputs/AL_summary.json')['status']=='complete'
    arms=['current_value','high_value']
    configs={arm:yaml.safe_load((STUDY/p['configs'][arm]['path']).read_text()) for arm in arms}
    for arm,cfg in configs.items():
        assert sha(STUDY/p['configs'][arm]['path'])==p['configs'][arm]['sha256']
        assert cfg['seed']==p['native_seed']==53230 and cfg['threads']==2
        e,life=cfg['evolve'],cfg['life']
        assert (e['mu'],e['lam'],e['generations'],e['heldout_every'],e['recheck_k'],e['recheck_lives'])==(32,224,4,4,64,8)
        assert e['recheck_key']=='all' and e['dup_rate']==e['del_rate']==0 and not e['dup_split']
        assert (life['abi'],life['lives'],life['valid_lives'],life['final_lives'],life['final_top'],life['T'])==(3,8,16,2,1,1024)
        assert life['extinct_charge'] and life['fast_kernel'] and not life['heldout'] and not life['size_curve']
        assert not life['T_choices'] and not life['flags'] and life['t_open']==0 and life['freeze_frac'] is None
        assert not cfg['clones']['every'] and not cfg['clones']['conditions'] and not cfg['envelope']['enabled']
        assert cfg['costs_life']=={} and 'exploratory_reserve' not in cfg
        loader=cfg['population_start']; expected={'version':1,**rec,
          'source_pins':{name:sha(STUDY/name) for name in ('population_loader.py','search.py')}}
        assert loader==expected
        assert e['seed_genome']==str(STUDY/rec['population_file'])
        assert cfg['retention_selection']=={'version':1,'arm':arm,'worlds':p['selection_worlds'],
          'rule':'gen indices even=pool odd=persistent; gen R_cap by arm; diagnostics=persistent R_cap500',
          'selection_capture_value':500. if arm=='current_value' else 2000.,
          'source_pins':{'selection.py':sha(STUDY/'selection.py')}}
    control,mixture=copy.deepcopy(configs[arms[0]]),copy.deepcopy(configs[arms[1]])
    control['logging']['output_dir']=mixture['logging']['output_dir']
    control['retention_selection']['arm']=mixture['retention_selection']['arm']
    control['retention_selection']['selection_capture_value']=mixture['retention_selection']['selection_capture_value']
    assert control==mixture
    al=read(STUDY/'inputs/AL_protocol.json')
    assert p['worlds']==al['worlds']
    assert list(p['worlds'])==['pool','persistent','blink80_5','turn100_blink80_5']
    spec_tree=ast.parse((ROOT/'src/life/spec.py').read_text())
    world=next(node for node in spec_tree.body if isinstance(node,ast.ClassDef) and node.name=='World')
    keys=[node.target.id for node in world.body if isinstance(node,ast.AnnAssign)
          and node.target.id not in ('name','stage','implemented','lattice','lives')]
    assert len(keys)==70
    for name,world0 in p['worlds'].items():
        assert world0['world']['R_cap']==500 and world0['world']['T']==1024
        assert world0['abi']==(3 if name in ('pool','persistent') else 4)
        expected_keys=keys[:66] if world0['abi']==3 else keys
        vector=np.asarray([world0['world'][key] for key in expected_keys],dtype=np.float64)
        assert vector.tobytes()==np.asarray(world0['world_vector'],dtype=np.float64).tobytes()
        assert len(world0['ledger_columns'])==(57 if world0['abi']==3 else 58)
    assert p['selection_worlds']=={key:p['worlds'][key]['world'] for key in ('pool','persistent')}
    audit=read(STUDY/'inputs/seed_audit.json'); native_rows,native_ids=derive_native_ids()
    assert audit['native_records']==native_rows and len(native_ids)==100
    assert audit['run_life_seeds']=={arm:[row['seed'] for row in native_rows] for arm in arms}
    assert p['seeds']==audit['confirmation_seeds']==list(range(52400000,52400512))
    assert not native_ids.intersection(p['seeds'])
    assert (p['research_lives'],p['startup_lives'],p['total_calls'])==(28748,8,28756)
    assert p['search']['research_lives_per_arm']==4*(256*8+64*8)+2*16+6==10278
    assert p['confirmation_lives']==4*4*512==8192
    expected_budget={'cpu_seconds':10800,'wall_seconds':5400,'search_cpu_seconds':7200,
      'confirmation_cpu_seconds':3600,'threads':2,'workers':1,'cleanup_margin_seconds':10,
      'rss_bytes':4*1024**3,'minimum_available_bytes':4*1024**3,'address_space_bytes':8*1024**3}
    assert p['budget']==expected_budget
    timing=read(OUT/'timing_review.json')
    assert timing['scope']['search_research_lives_per_arm']==10278 and timing['scope']['confirmation_research_lives']==8192
    assert sha(OUT/'timing_review.json')=='de0accd5648847161021ac375b3e57d1a9c2cec0b1a1b17dff5123ee25e1ac51'
    assert p['roles']==['AI_control_start','AL_mixture_start','current_value_final','high_value_final']
    assert p['primary']==[{'world':w,'new':'high_value_final','old':'current_value_final','metric':'captures'} for w in ('pool','persistent')]
    assert p['retention_margin_fraction']==.1
    assert not any(name.startswith('src') or name=='torch' for name in sys.modules)
    receipt={'status':'passed_actual_prepared_inputs','protocol_sha256':PROTOCOL,'pin_counts':pin_counts,
      'population_shape':[32,875],'population_raw_sha256':raw_sha(table),'ordered_rows_checked':32,
      'new_ids':list(range(32)),'old_ids':pop['ids'],'row0_old_id':pop['ids'][0],
      'configs_equal_except_arm_price_and_output_path':True,'native_unique_ids_per_arm':100,
      'native_ids_intentionally_shared':True,'confirmation_ids':512,'confirmation_ids_shared_across_all_roles_and_worlds':True,
      'worlds':{name:{'abi':w['abi'],'world_size':len(w['world_vector']),'ledger_size':len(w['ledger_columns'])} for name,w in p['worlds'].items()},
      'exact_prior_AL_worlds':True,
      'gen_world_assignment':'Both arms use even absolute indices POOL and odd persistent, including recheck indices 8 through 15. High-value generation selection uses R_cap 2000; current value and all native diagnostics use 500.',
      'budget':p['budget'],'research_lives':28748,'startup_lives':8,'total_calls':28756,
      'historical_search_projection_cpu_seconds':timing['projection']['search_CPU_seconds'],
      'historical_confirmation_projection_cpu_seconds':timing['projection']['confirmation_CPU_seconds'],
      'simulation_calls':0,'engine_imports':False,'engine_builds':0,'genetic_draws':0,
      'review_script_sha256':sha(Path(__file__)),
      'source_pins':p['source_pins'],'evidence_pins':{name:sha(OUT/name) for name in ('seed_audit.json','producer_operations_source_review.json','producer_schedule_review.json','timing_review.json')},
      'limitations':['No new execution feasibility claim: historical rates do not bound unseen genomes. Hard CPU/memory caps remain decisive.',
                     'All 32 population rows and their order are exact; old fitness, RNG and IDs are not resumed.',
                     'Matched life counts need not give matched CPU; raw per-life mean F can still favor economy over acquisition.']}
    (OUT/'actual_input_review.json').write_text(json.dumps(receipt,indent=2)+'\n')
    print(json.dumps({'status':'passed','receipt_sha256':sha(OUT/'actual_input_review.json'),'pins':pin_counts,'rows':32}))

if __name__=='__main__':main()
