"""Independent actual AF input/config/recorded-addition review; no engine or RNG calls."""
from pathlib import Path
import hashlib,json,sys
import numpy as np
from omegaconf import OmegaConf
ROOT=Path(__file__).resolve().parents[2]
OUT=Path(__file__).resolve().parent
STUDY=ROOT/'outputs/autonomous_prediction_continuation_20261014'
AE=ROOT/'results/prediction_gradient_20261014'
sys.path.insert(0,str(ROOT))
from src.life import spec
EXPECTED='ebdc3f37dc5d9a882b2b7d68ed3913a08540be4f476bdd6cf4b6c446e315b5e0'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p):return json.loads(p.read_text())
def main():
 assert sha(STUDY/'protocol.json')==EXPECTED
 p=read(STUDY/'protocol.json');r=read(STUDY/'registration.json');s=read(STUDY/'seed_audit.json');i=read(STUDY/'initialization.json')
 for base,pins in ((STUDY,p['file_pins']),(ROOT,p['production_pins'])):
  for name,digest in pins.items():assert sha(base/name)==digest,name
 assert p['runs']==r['runs']==s['runs']==[53224,53225]
 assert p['confirmation']=={'labels':['AE_D90','AE_L92','AF_D90','AF_L92'],'seeds':s['confirmation_seeds'],'threads':2,'primary_pairs':[[2,0],[3,1]]}
 assert p['confirmation']['seeds']==r['confirmation_seeds']==list(range(52310000,52310512))
 assert r['native_seed_audit_sha256']==sha(STUDY/'seed_audit.json') and r['resource_clearance_sha256']==sha(STUDY/'resource_clearance.json')
 assert r['founder_policy']=='both_AE_selected_regardless_of_confirmation_sign'
 prior=read(AE/'protocol.json');roles=read(AE/'confirmation_roles.json');selected=read(AE/'selection.json')
 assert p['world']==prior['world'] and p['world_packing']==prior['world_packing'] and p['abi']==3
 packed=spec.V3.pack_world(spec.World(**p['world']))
 assert p['world_packing']=={'abi':3,'keys':list(spec.V3.WORLD_KEYS),'values':packed.tolist(),'raw_sha256':hashlib.sha256(packed.tobytes()).hexdigest()}
 with np.load(STUDY/'inputs/AE/confirmation_genotypes.npz',allow_pickle=False) as z:old=z['genomes'];assert z['roles'].tolist()==roles['roles']
 copies=0
 for q in sorted((STUDY/'inputs/AE').rglob('*')):
  if q.is_file():
   rel=str(q.relative_to(STUDY/'inputs/AE'));remote=AE/('operations/budget.json' if rel=='budget.json' else rel)
   assert sha(q)==sha(remote),rel;copies+=1
 assert sha(STUDY/'inputs/AE_summary.json')==sha(AE/'analysis_result/summary.json')
 before=read(OUT/'independent_source_design_review.json');assert p['cost_projection']==before['cost_projection']
 assert read(STUDY/'inputs/AE_cost_rows.json')['projection']==p['cost_projection']
 for item in before['cost_evidence']:
  local=STUDY/'inputs/AE'/Path(item['path']).relative_to(AE.relative_to(ROOT));assert sha(local)==item['sha256']
  with np.load(local,allow_pickle=False) as z:assert float(z['cpu_seconds'])==item['cpu_seconds']
 fields=spec.V3.GENOME_FIELDS;shapes={f.name:f.shape for f in fields};counts={};configpins={}
 template=OmegaConf.to_container(OmegaConf.load(STUDY/'inputs/U_template.yaml'),resolve=True)
 for j,(run,background) in enumerate(zip(p['runs'],('D90','L92'))):
  key=str(run);mapping=p['founder_mapping'][key];assert mapping['background']==background and mapping['AE_selection']==selected[background]
  assert mapping['raw_sha256']==roles['genotype_sha256']['H_'+background]
  data=read(STUDY/mapping['start_file']);raw=np.concatenate([np.asarray(data['params'][f.name],dtype=np.float32).reshape(-1) for f in fields])
  assert raw.shape==(875,) and raw.tobytes()==old[j+2].tobytes() and hashlib.sha256(raw.tobytes()).hexdigest()==mapping['raw_sha256']
  cfg=OmegaConf.to_container(OmegaConf.load(STUDY/p['configs'][key]['path']),resolve=True)
  expected=json.loads(json.dumps(template));expected['seed']=run;expected['threads']=2
  expected['evolve'].update(generations=4,seed_genome=str(STUDY/mapping['start_file']),dup_rate=0.,del_rate=0.,dup_split=False)
  expected['logging'].update(output_dir=str(STUDY/f'runs/s{run}'),checkpoint_every=1,lineage='all')
  expected['life'].update(abi=3,world='catch_speck_l4',control='ordinary_persistent_AE_selected',T=1024,T_choices=None,flags=[],freeze_frac=None,t_open=0.)
  expected['world']={'d0':1.,'d_min':.5,'v_t':.3,'tau_turn':200.};expected['costs_life']={};expected['envelope']={'enabled':False}
  assert cfg==expected
  w=spec.world(cfg['life']['world'],T=cfg['life']['T'],**cfg['world'])
  assert spec.V3.pack_world(w).tobytes()==packed.tobytes()
  receipt=i['runs'][key];table=np.load(STUDY/receipt['population_file'],allow_pickle=False)
  assert table.dtype==np.float32 and table.shape==(32,875) and np.isfinite(table).all()
  assert table[0].tobytes()==raw.tobytes() and sha(STUDY/receipt['population_file'])==receipt['file_sha256']
  assert hashlib.sha256(table.tobytes()).hexdigest()==receipt['population_raw_sha256']
  assert [x['id'] for x in receipt['copies']]==list(range(1,32)) and all(x['parent']==0 for x in receipt['copies'])
  for record in receipt['copies']:
   assert set(record['ops'])=={'mut'} and len(record['ops']['mut'])==2
   replay=raw.copy();locations=[]
   for name,ix,delta in record['ops']['mut']:
    start,stop=spec.V3.GENOME_SLICES[name];flat=start+np.ravel_multi_index(tuple(ix),shapes[name]);assert flat<stop
    locations.append(flat);replay[flat]=np.float32(replay[flat]+np.float32(delta))
   assert len(set(locations))==2 and replay.tobytes()==table[record['id']].tobytes()
  counts[key]={'background':background,'initial_rows':32,'mutated_copies':31,'recorded_float32_additions':62,'exact_rows_replayed':32,'file_sha256':receipt['file_sha256'],'raw_sha256':receipt['population_raw_sha256'],'RNG_hashes_bound_not_resampled':True}
  configpins[key]=sha(STUDY/p['configs'][key]['path'])
 assert i['simulation_calls']==0 and i['status']=='pure_genetic_preparation'
 assert read(STUDY/'preparation_claim.json')=={'registration_sha256':sha(STUDY/'registration.json'),'simulation_calls':0,'compiled_libraries':0}
 assert read(STUDY/'generation_claim.json')=={'registration_sha256':sha(STUDY/'registration.json'),'runs':[53224,53225]}
 forbidden=('ready.json','attempt.json','budget.json','runs','confirmation','logs','build-cache')
 assert not any((STUDY/n).exists() for n in forbidden) and not list(STUDY.rglob('*.so'))
 assert not {'src.life.build','src.evolve','src.run','src.checkpoint'}&set(sys.modules)
 result={'status':'passed_prepared_unreleased','protocol_sha256':EXPECTED,'local_pin_count':len(p['file_pins']),'production_pin_count':len(p['production_pins']),'registration_sha256':sha(STUDY/'registration.json'),'seed_audit_sha256':sha(STUDY/'seed_audit.json'),'clearance_sha256':sha(STUDY/'resource_clearance.json'),'world_packing_raw_sha256':p['world_packing']['raw_sha256'],'AE_exact_copied_files':copies,'six_timing_rows_equal_review':True,'projection':p['cost_projection'],'configurations_equal_exact_declarative_template_change':configpins,'initialization':counts,'founder_rows':{'D90':54,'L92':31},'confirmation_roles':p['confirmation']['labels'],'counts':{'research':10316,'startup_goldens':6,'planned_total':10322,'actual_simulations':0},'source_sha256':sha(Path(__file__)),'limits':'Replay uses recorded float32 additions without new RNG draws or setup/fill; independent native reader additionally verifies active-mask/block constraints. No runtime outcome or guaranteed future cost claim.','compiled_libraries':0,'genetic_draws':0,'genotype_copies_by_review':0,'absent_runtime_paths':list(forbidden)}
 (OUT/'independent_actual_preparation_review.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
if __name__=='__main__':main()
