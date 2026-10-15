"""Independent AF source/config/timing review; no initialization, builds or lives."""
from pathlib import Path
import ast, hashlib, json, math, sys
import numpy as np
from omegaconf import OmegaConf
ROOT=Path(__file__).resolve().parents[2]
OUT=Path(__file__).resolve().parent
STUDY=ROOT/'outputs/autonomous_prediction_continuation_20261014'
AE=ROOT/'results/prediction_gradient_20261014'
sys.path.insert(0,str(ROOT))
from src.life import spec

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p):return json.loads(p.read_text())
def functions(path):return {n.name:n for n in ast.parse(path.read_text()).body if isinstance(n,ast.FunctionDef)}
def pure(path,names,scope):
 nodes=[functions(path)[n] for n in names]
 exec(compile(ast.Module(body=nodes,type_ignores=[]),str(path),'exec'),scope)
def main():
 forbidden=('inputs','configs','initialization','protocol.json','ready.json','attempt.json','budget.json','runs','confirmation','build-cache','generation_claim.json','preparation_claim.json')
 assert all(not(STUDY/n).exists() for n in forbidden)
 lifecycle=('own_cpu','child_cpu','proc_table','active_cpu','consumed_cpu','child_limit','send_signal','enable_subreaper','cleanup_group','cleanup','interrupt','process_identity')
 old=functions(ROOT/'results/decoy_evolution_20261014/run_budgeted.py');new=functions(STUDY/'run_budgeted.py')
 assert all(ast.dump(old[n],include_attributes=False)==ast.dump(new[n],include_attributes=False) for n in lifecycle)
 for name in ('scoring.py','numerical.py','world_contract.py'):
  assert sha(STUDY/name)==sha(AE/name)
 scope={'STUDY':STUDY,'PARENTS':('D90','L92'),'TEMPLATE':ROOT/'results/decoy_evolution_20261014/runs/s53091/config.yaml','math':math}
 pure(STUDY/'prepare.py',['search_config','cost_projection'],scope)
 cfg=scope['search_config'](0,'unused-source-review.json')
 assert cfg.seed==0 and cfg.threads==2 and cfg.mode=='life'
 assert cfg.evolve.breeding=='sex' and (cfg.evolve.mu,cfg.evolve.lam,cfg.evolve.generations)==(32,224,4)
 assert (cfg.evolve.recheck_k,cfg.evolve.recheck_lives,cfg.evolve.recheck_key)==(64,4,'all')
 assert (cfg.evolve.dup_rate,cfg.evolve.del_rate,cfg.evolve.dup_split)==(0,0,False)
 assert (cfg.evolve.n_mut,cfg.evolve.p_cell,cfg.evolve.n_mut_scale,cfg.evolve.random_ties)==(2,.5,True,True)
 assert cfg.life.abi==3 and cfg.life.T==1024 and cfg.life.T_choices is None and cfg.life.lives==3
 assert cfg.life.extinct_charge and cfg.life.fast_kernel and not cfg.envelope.enabled
 assert cfg.evolve.heldout_every==4 and cfg.life.valid_lives==16
 assert (cfg.life.final_top,cfg.life.final_lives,cfg.life.final_fork_lives)==(1,2,0)
 assert not cfg.life.heldout and not cfg.life.size_curve and not cfg.clones.conditions and not cfg.clones.every
 assert cfg.life.flags==[] and cfg.life.freeze_frac is None and cfg.life.t_open==0
 assert cfg.logging.checkpoint_every==1 and cfg.logging.lineage=='all'
 p=read(AE/'protocol.json');selected=read(AE/'selection.json');roles=read(AE/'confirmation_roles.json');summary=read(AE/'analysis_result/summary.json')
 world=spec.world(cfg.life.world,T=cfg.life.T,**dict(cfg.world));packed=spec.V3.pack_world(world)
 assert packed.dtype==np.float64 and packed.shape==(66,)
 assert packed.tolist()==p['world_packing']['values'] and hashlib.sha256(packed.tobytes()).hexdigest()==p['world_packing']['raw_sha256']
 assert (world.d0,world.d_min,world.v_t,world.tau_turn)==(1,.5,.3,200)
 assert (world.visibility_mode,world.visibility_on,world.visibility_off,world.visibility_low)==(0,0,0,1)
 assert spec.V3.LEDGER_SIZE==57 and spec.V3.GENOME_SIZE==875
 rates={};evidence=[]
 for j,background in enumerate(('D90','L92')):
  rates[background]={};row=selected[background]['genome_row']
  for label,folder,stage,index,n,oldrole in [('H_screen',f'measurement/screen/{background}','screen',row,32,'H_'+background),('H_confirm','measurement/confirm/persistent','confirm',j+2,512,'H_'+background),('P_confirm','measurement/confirm/persistent','confirm',j,512,'P_'+background)]:
   rel=f'{folder}/{stage}/row_{index:04d}.npz';path=AE/rel;idx=read(AE/f'{folder}/row_index.json')[f'{stage}/row_{index:04d}.npz']
   assert sha(path)==summary['input_pins'][rel]==idx['sha256']
   with np.load(path,allow_pickle=False) as z:
    cpu=float(z['cpu_seconds']);identity=json.loads(str(z['identity']));seeds=z['seeds'].tolist()
    assert cpu==idx['cpu_seconds'] and math.isfinite(cpu) and cpu>0
    assert seeds==identity['seeds']==p['seeds'][stage] and len(seeds)==n
    assert identity['genome_index']==index and identity['genome_sha256']==roles['genotype_sha256'][oldrole]
    assert identity['protocol_sha256']==sha(AE/'protocol.json') and identity['world']=='persistent' and identity['stage']==stage
   rates[background][label]=cpu/n;evidence.append({'path':str(path.relative_to(ROOT)),'sha256':sha(path),'background':background,'timing_role':label,'lives':n,'cpu_seconds':cpu,'cpu_per_life':cpu/n})
 maxima={b:max(x.values()) for b,x in rates.items()}
 search=180+1.5*4134*sum(maxima.values());confirm=180+1.5*512*sum(3*x for x in maxima.values())
 actual=scope['cost_projection'](rates)
 assert actual['rates_cpu_per_life']==rates and actual['lineage_max_cpu_per_life']==maxima
 assert actual['startup_search_projection']==search and actual['confirmation_projection']==confirm and actual['feasible']
 assert search<=3390 and confirm<=1990
 for file,count in ((STUDY/'prepare.py',0),(STUDY/'run_budgeted.py',0),(STUDY/'measure.py',1),(ROOT/'src/run.py',1)):
  calls=[n for n in ast.walk(ast.parse(file.read_text())) if isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute) and n.func.attr=='numerical_identity'];assert len(calls)==count
 assert 'src.life.build' not in sys.modules and 'src.evolve' not in sys.modules and 'src.checkpoint' not in sys.modules
 sourcepins={str(p.relative_to(ROOT)):sha(p) for p in sorted(STUDY.iterdir()) if p.is_file()}
 for pth in (Path(__file__),ROOT/'src/life/spec.py',ROOT/'src/life/evaluate.py',ROOT/'src/evolve.py',ROOT/'src/run.py',ROOT/'src/checkpoint.py',ROOT/'src/genome.py',AE/'protocol.json',AE/'operations/budget.json',AE/'selection.json',AE/'confirmation_roles.json',AE/'analysis_result/summary.json',ROOT/'results/decoy_evolution_20261014/run_budgeted.py',scope['TEMPLATE']):sourcepins[str(pth.relative_to(ROOT))]=sha(pth)
 result={'status':'passed_source_design','registered':False,'reserved':False,'source_pins':sourcepins,'reviewed_reuse':{'monitor_lifecycle_AST_identical_functions':list(lifecycle),'AE_byte_identical_helpers':['scoring.py','numerical.py','world_contract.py']},'world':{'abi':3,'packed_fields':66,'ledger_fields':57,'genome_fields':875,'packing_sha256':hashlib.sha256(packed.tobytes()).hexdigest(),'exact_retained_AE_V_world':True},'calls':{'selection':8192,'periodic_validation':64,'final_diagnostics':12,'search_research':8268,'confirmation_research':2048,'research':10316,'startup_identity_invocations':3,'startup_goldens':6,'total':10322,'half_duration_diagnostic_calls':4,'unique_native_life_IDs_per_run':64,'unique_native_life_IDs_total':128},'genetic_RNG':'Each native run uses cfg.seed for founder fill, parental choices/crossover/mutations; tie generator uses cfg.seed+7919001. These seed the genetic RNG, not direct life IDs. No draws executed by this review.','life_seed_schedule':'hash64(run_seed,LIFE+purpose,index,life): gen four generations×seven IDs, valid g0/g3×16, final index0/1×2. The half-duration diagnostics reuse final0 IDs.','cost_evidence':evidence,'cost_projection':actual,'cost_limitations':['CPU timings already count both worker threads; no wall-time substitution or second thread multiplier.','Each lineage rate is max of selected H32 screen,H512 confirmation,original P512 confirmation. The known start receives1r and unknown endpoint2r before outer1.5. These are planning allowances, not guaranteed bounds.','Each search costs4,134 measured lives conservatively all priced at T1024 although two diagnostics/run are T512. Startup/builds/failures/monitor/teardown are included by real aggregate accounting.','Search stops at3,390 CPU-s; aggregate total stops at5,390. The2,000 CPU-s reserve is minimum remaining capacity after the3,400 search ceiling, not an independent hard confirmation ceiling.'], 'scientific_scope':['Both fixed AE selections are included regardless of previous gain sign; no comparison outcome selects a background.','Two four-generation runs test further local accessibility of capture improvements under unchanged production fitness. Cost-only gains remain possible and must be decomposed.','Endpoint is final population rank0 from each complete run, frozen together before paired512 confirmations; tiny native final redraws do not choose confirmation candidates.','No claim of memory, prediction, communication mechanism or general reliability across evolutionary runs follows from these two runs.','Native diagnostics retain summaries rather than complete raw ledgers; full raw accounting applies to2,048 confirmation lives.'], 'review_helper_history':{'first_attempt':'Pure audit helper referenced nonexistent Abi.genome_size instead of existing GENOME_SIZE constant; fixed helper only before timing review, no producer change or simulation.','error_sha256':sha(OUT/'history/source_review_initial_helper_error.txt')},'simulation_calls':0,'compiled_libraries':0,'genetic_draws':0,'genotype_copies':0,'absent_runtime_paths':list(forbidden)}
 (OUT/'independent_source_design_review.json').write_text(json.dumps(result,indent=2)+'\n')
 print(json.dumps({'status':result['status'],'review_sha256':sha(OUT/'independent_source_design_review.json'),'rates':maxima,'search_projection':search,'confirmation_projection':confirm,'calls':result['calls']}))
if __name__=='__main__':main()
