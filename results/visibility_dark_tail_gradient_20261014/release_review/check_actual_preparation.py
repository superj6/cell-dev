"""Independent prepared AG input and metadata audit; no engine calls or draws."""
import hashlib
import json
import math
import sys
from pathlib import Path
import numpy as np
from omegaconf import OmegaConf

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent
STUDY = ROOT / 'outputs/autonomous_visibility_dark_tail_gradient_20261014'
sys.path.insert(0, str(ROOT))
from src.life import spec
EXPECTED = 'ff9af8c7fcb140bb4f09b6636e59df92272254851dfe1f33a4d6441be1a7955f'
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p): return json.loads(p.read_text())
def main():
    assert sha(STUDY/'protocol.json') == EXPECTED
    p = read(STUDY/'protocol.json'); reg = read(STUDY/'registration.json')
    for base, pins in ((STUDY,p['file_pins']),(ROOT,p['production_pins'])):
        for n,d in pins.items(): assert sha(base/n)==d,n
    assert p['seeds']==reg['seeds']==read(STUDY/'seed_audit.json')['seeds']
    assert p['seeds']=={'calibration':[52320000,52320001], 'screen':list(range(52330000,52330032)), 'confirm':list(range(52340000,52340512))}
    assert p['monitor_scope']=={'total_cpu_seconds':5400,'startup_screen_cpu_seconds':3400,'confirmation_reserve_cpu_seconds':2000,'startup_calibration_cpu_seconds':180,'max_workers':1,'threads_per_worker':2,'research_lives':6208,'validation_lives':10}
    assert p['roles']==['P_D90','P_L92','H_D90','H_L92']
    assert p['selection']=={'rows':list(range(1,65)),'statistic':'mean_production_F','tie':'lowest_row_index'}
    ad=read(STUDY/'inputs/AD/protocol.json');ac=read(STUDY/'inputs/AC/protocol.json');y=read(STUDY/'inputs/Y/protocol.json')
    for label in ('AD','AC','Y'): assert sha(STUDY/f'inputs/{label}/protocol.json')==p[label+'_protocol_sha256']
    assert p['world']==ad['worlds']['flash5_dark']['production']['world'] and p['abi']==4
    w=spec.World(**p['world']);packed=spec.V4.pack_world(w)
    assert packed.dtype==np.float64 and packed.shape==(70,)
    assert p['world_packing']=={'abi':4,'keys':list(spec.V4.WORLD_KEYS),'values':packed.tolist(),'raw_sha256':hashlib.sha256(packed.tobytes()).hexdigest()}
    assert w.T==1024 and (w.d0,w.d_min,w.v_t,w.tau_turn)==(1,.5,.1,20)
    assert (w.visibility_mode,w.visibility_on,w.visibility_off,w.visibility_low)==(1,5,0,0)
    copies={}
    folders={'Y':'visibility_gradient_20261014','AC':'visibility_flash_gradient_20261014','AD':'visibility_dark_tail_information_20261014'}
    for label,folder in folders.items():
        copies[label]=0
        for local in sorted((STUDY/f'inputs/{label}').rglob('*')):
            if not local.is_file(): continue
            relative=local.relative_to(STUDY/f'inputs/{label}')
            remote=ROOT/'results'/folder/('operations/budget.json' if str(relative)=='budget.json' else relative)
            assert sha(local)==sha(remote),(label,str(relative));copies[label]+=1
    assert copies=={'Y':16,'AC':135,'AD':2}
    changes={};rates={};tables={}
    for b in ('D90','L92'):
        old=OmegaConf.to_container(OmegaConf.load(STUDY/f'inputs/Y/inputs/{b}/config.yaml'),resolve=True)
        current=OmegaConf.to_container(OmegaConf.load(STUDY/f'configs/flash5_dark_{b}.yaml'),resolve=True)
        expected=json.loads(json.dumps(old));expected['life']['world']='catch_speck_flash5_dim25_l4';expected['life']['abi']=4;expected['world']={'visibility_low':0.0}
        assert current==expected
        assert current['life']['T']==1024 and current['threads']==2 and current['life']['fast_kernel'] and current['life']['extinct_charge'] and not current['life']['T_choices'] and not current['envelope']['enabled']
        changes[b]={'life.world':'catch_speck_flash5_dim25_l4','life.abi':4,'world':expected['world']}
        table=np.load(STUDY/f'inputs/Y/inputs/{b}/genomes.npy',allow_pickle=False)
        assert table.dtype==np.float32 and table.shape==(65,875) and np.isfinite(table).all()
        hashes=[hashlib.sha256(row.tobytes()).hexdigest() for row in table]
        assert hashes==p['panel_genotype_sha256'][b]==y['panel_genotype_sha256'][b]==ac['panel_genotype_sha256'][b]
        tables[b]={'file_sha256':sha(STUDY/f'inputs/Y/inputs/{b}/genomes.npy'),'shape':[65,875],'dtype':'float32','all65_genotype_hashes_match_Y_and_AC':True}
        index=read(STUDY/f'inputs/AC/measurement/screen/{b}/row_index.json');rates[b]=[]
        for i in range(65):
            name=f'screen/row_{i:04d}.npz';path=STUDY/f'inputs/AC/measurement/screen/{b}'/name
            assert sha(path)==index[name]['sha256']
            with np.load(path,allow_pickle=False) as row:
                identity=json.loads(str(row['identity']));cpu=float(row['cpu_seconds']);wall=float(row['wall_seconds'])
                assert identity=={'protocol_sha256':p['AC_protocol_sha256'],'background':b,'world':'flash','stage':'screen','genome_index':i,'genome_sha256':hashes[i],'seeds':ac['seeds']['screen']}
                assert math.isfinite(cpu) and cpu>0 and cpu==index[name]['cpu_seconds']
                assert math.isfinite(wall) and wall>=0
                assert np.array_equal(row['seeds'],np.array(ac['seeds']['screen'],dtype=np.uint64))
                rates[b].append(cpu/32)
    assert rates==p['historical_flash_cpu_per_life']
    assert read(STUDY/'preparation_claim.json')=={'registration_sha256':sha(STUDY/'registration.json'),'genetic_draws':0,'retained_panel_rows':130,'simulation_calls':0,'compiled_libraries':0}
    forbidden=('ready.json','attempt.json','budget.json','measurement','logs','build-cache','startup_identity.json','selection.json','requests','monitor_receipts')
    assert all(not (STUDY/n).exists() for n in forbidden) and not list(STUDY.rglob('*.so'))
    assert not ({'src.life.build','src.life.evaluate','src.run','src.evolve'} & set(sys.modules))
    result={'status':'passed_prepared_unreleased','protocol_sha256':EXPECTED,'local_pin_count':len(p['file_pins']),'production_pin_count':len(p['production_pins']),'registration_sha256':sha(STUDY/'registration.json'),'seed_audit_sha256':sha(STUDY/'seed_audit.json'),'world_packing_raw_sha256':p['world_packing']['raw_sha256'],'world_abi':4,'world_size':70,'ledger_size':58,'configuration_changes_verified':changes,'panels':tables,'exact_copied_files':copies,'historical_timing_rows_verified':130,'reviewed_numeric_rates_equal_protocol':True,'source_file_sha256':sha(Path(__file__)),'absent_runtime_paths':list(forbidden),'simulation_calls':0,'compiled_libraries':0,'genetic_draws':0,'genotype_copies_by_review':0,'limits':'Input byte/shape/provenance review only. No simulated behavior or future cost outcome is claimed. Recorded genetic operations are replayed independently by the bound reader.'}
    (OUT/'independent_actual_preparation_review.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2))
if __name__=='__main__': main()
