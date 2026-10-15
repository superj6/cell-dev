"""Independent metadata/input checks of the one prepared AE study; no engine calls."""
import hashlib
import json
import math
import sys
from pathlib import Path
import numpy as np
from omegaconf import OmegaConf
ROOT=Path(__file__).resolve().parents[3]
OUT=Path(__file__).resolve().parent
STUDY=ROOT/'outputs/autonomous_prediction_gradient_20261014'
sys.path.insert(0,str(ROOT))
from src.life import spec
EXPECTED='0f5a591fbfb66fd29b5f9cd11d42b482eb8cb09e74613b17cc384ed2c3daa849'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p):return json.loads(p.read_text())
def main():
 assert sha(STUDY/'protocol.json')==EXPECTED
 p=read(STUDY/'protocol.json');registration=read(STUDY/'registration.json')
 for base,pins in ((STUDY,p['file_pins']),(ROOT,p['production_pins'])):
  for n,d in pins.items():assert sha(base/n)==d,n
 assert p['seeds']==registration['seeds']==read(STUDY/'seed_audit.json')['seeds']
 assert p['monitor_scope']=={'total_cpu_seconds':5400,'startup_screen_cpu_seconds':3400,'confirmation_reserve_cpu_seconds':2000,'startup_calibration_cpu_seconds':180,'max_workers':1,'threads_per_worker':2,'research_lives':6208,'validation_lives':10}
 assert p['roles']==['P_D90','P_L92','H_D90','H_L92']
 assert p['selection']=={'rows':list(range(1,65)),'statistic':'mean_production_F','tie':'lowest_row_index'}
 vp=read(STUDY/'inputs/V/protocol.json');yp=read(STUDY/'inputs/Y/protocol.json')
 assert sha(STUDY/'inputs/V/protocol.json')==p['V_protocol_sha256']
 assert p['world']==vp['world'] and p['abi']==3
 w=spec.World(**p['world']);packed=spec.V3.pack_world(w)
 assert packed.dtype==np.float64 and packed.shape==(66,)
 assert p['world_packing']=={'abi':3,'keys':list(spec.V3.WORLD_KEYS),'values':packed.tolist(),'raw_sha256':hashlib.sha256(packed.tobytes()).hexdigest()}
 assert w.T==1024 and (w.d0,w.d_min,w.v_t,w.tau_turn)==(1,.5,.3,200)
 assert (w.visibility_mode,w.visibility_on,w.visibility_off,w.visibility_low)==(0,0,0,1)
 copies=0
 for local in sorted((STUDY/'inputs/Y').rglob('*')):
  if not local.is_file():continue
  relative=local.relative_to(STUDY/'inputs/Y');remote=ROOT/'results/visibility_gradient_20261014'/relative
  if str(relative)=='budget.json':remote=remote.parent/'operations/budget.json'
  assert sha(local)==sha(remote),str(relative);copies+=1
 changes={};rates={};tables={}
 for background in ('D90','L92'):
  old=OmegaConf.to_container(OmegaConf.load(STUDY/f'inputs/Y/inputs/{background}/config.yaml'),resolve=True)
  current=OmegaConf.to_container(OmegaConf.load(STUDY/f'configs/persistent_{background}.yaml'),resolve=True)
  expected=json.loads(json.dumps(old));expected['life']['world']='catch_speck_l4';expected['life']['abi']=3;expected['world']={'v_t':.3,'tau_turn':200.}
  assert current==expected
  assert current['life']['T']==1024 and current['threads']==2 and current['life']['fast_kernel'] and current['life']['extinct_charge'] and not current['life']['T_choices'] and not current['envelope']['enabled']
  changes[background]={'life.world':'catch_speck_l4','life.abi':3,'world':expected['world']}
  table=np.load(STUDY/f'inputs/Y/inputs/{background}/genomes.npy',allow_pickle=False)
  assert table.dtype==np.float32 and table.shape==(65,875) and np.isfinite(table).all()
  hashes=[hashlib.sha256(row.tobytes()).hexdigest() for row in table]
  assert hashes==p['panel_genotype_sha256'][background]==yp['panel_genotype_sha256'][background]
  tables[background]={'file_sha256':sha(STUDY/f'inputs/Y/inputs/{background}/genomes.npy'),'shape':[65,875],'dtype':'float32','all65_genotype_hashes_match_Y':True}
  index=read(STUDY/f'inputs/Y/measurement/{background}/row_index.json');rates[background]=[]
  for i in range(65):
   name=f'screen/row_{i:04d}.npz';path=STUDY/f'inputs/Y/measurement/{background}'/name
   assert sha(path)==index[name]['sha256']
   with np.load(path,allow_pickle=False) as row:
    identity=json.loads(str(row['identity']));cpu=float(row['cpu_seconds'])
    assert identity=={'protocol_sha256':p['Y_protocol_sha256'],'background':background,'stage':'screen','genome_index':i,'genome_sha256':hashes[i],'seeds':yp['seeds']['screen']}
    assert math.isfinite(cpu) and cpu>0 and cpu==index[name]['cpu_seconds']
    rates[background].append(cpu/32)
 assert rates==p['historical_blink_cpu_per_life']
 assert read(STUDY/'preparation_claim.json')=={'registration_sha256':sha(STUDY/'registration.json'),'genetic_draws':0,'retained_panel_rows':130,'simulation_calls':0,'compiled_libraries':0}
 forbidden=('ready.json','attempt.json','budget.json','measurement','logs','build-cache','startup_identity.json','selection.json','requests','monitor_receipts')
 assert all(not (STUDY/n).exists() for n in forbidden) and not list(STUDY.rglob('*.so'))
 assert 'src.life.build' not in sys.modules
 result={'status':'passed_prepared_unreleased','protocol_sha256':EXPECTED,'local_pin_count':len(p['file_pins']),'production_pin_count':len(p['production_pins']),'registration_sha256':sha(STUDY/'registration.json'),'seed_audit_sha256':sha(STUDY/'seed_audit.json'),'world_packing_raw_sha256':p['world_packing']['raw_sha256'],'world_abi':3,'world_size':66,'ledger_size':57,'configuration_changes_verified':changes,'panels':tables,'exact_Y_copied_files':copies,'historical_timing_rows_verified':130,'reviewed_numeric_rates_equal_protocol':True,'source_file_sha256':sha(Path(__file__)),'absent_runtime_paths':list(forbidden),'simulation_calls':0,'compiled_libraries':0,'genetic_draws':0,'genotype_copies_by_review':0,'limits':'Input byte/shape/provenance review only; no simulated behavior or future cost outcome is claimed. Recorded genetic operations are replayed by the independent reader.'}
 (OUT/'independent_actual_preparation_review.json').write_text(json.dumps(result,indent=2)+'\n')
 print(json.dumps(result,indent=2))
if __name__=='__main__':main()
