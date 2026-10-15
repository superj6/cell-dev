"""Classify AH candidate-only namespace and completed AG seed metadata."""
from pathlib import Path
import hashlib,io,json,subprocess,zipfile
import numpy as np
ROOT=Path(__file__).resolve().parents[3]
OUT=Path(__file__).resolve().parent
AG=ROOT/'outputs/autonomous_visibility_dark_tail_gradient_20261014'
PUBLIC=ROOT/'results/visibility_dark_tail_gradient_20261014'
LOW,HIGH=52350000,52360000
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
read=lambda p:json.loads(p.read_text())
def main():
 j=read(OUT/'candidate_namespace_inventory.json')
 assert j['native_union_count']==64 and j['paired_native_seeds']=={'control':53226,'reserve':53226}
 native=j['run_life_seeds']['control'];assert native==j['run_life_seeds']['reserve']==j['intentional_overlap']
 confirm=list(range(52350000,52350512));assert j['stage_seed_lists']=={'confirm':confirm}
 candidate=set(native+confirm);assert len(candidate)==576 and 11 not in candidate
 assert not j['NPZ_numeric_matches'] and not j['NPZ_errors'] and not j['JSON_errors'] and not j['JSON_numeric_string_or_key_matches']
 allowed={'whole_blocks_half_open.2.1','whole_block_half_open.1','same_whole_blocks_half_open.2.1'}
 assert len(j['JSON_numeric_matches'])==12 and all(x['value']==LOW and x['field'] in allowed and 'visibility_dark_tail_gradient_20261014' in x['path'] for x in j['JSON_numeric_matches'])
 assert j['historical_actual_matches_excluding_prior_endpoint']==[LOW]
 lines=(OUT/'candidate_text_matches.txt').read_text().splitlines()
 assert len(lines)==8 and all('visibility_dark_tail_gradient_20261014/' in x and '52_350_000' in x or 'visibility_dark_tail_gradient_20261014/' in x and '52,350,000)' in x for x in lines)
 reg=read(AG/'registration.json');registered=set(sum(reg['seeds'].values(),[]))
 assert len(registered)==546 and not registered & candidate and not any(LOW<=x<HIGH for x in registered)
 assert not set(native)&set(confirm)
 raw_pairs=[];seen=set();count=0
 for path in sorted((AG/'measurement').rglob('row_*.npz')):
  relative=path.relative_to(AG);public=PUBLIC/relative;assert sha(path)==sha(public)
  with zipfile.ZipFile(path) as z:
   seeds=np.load(io.BytesIO(z.read('seeds.npy')),allow_pickle=False)
   identity=json.loads(str(np.load(io.BytesIO(z.read('identity.npy')),allow_pickle=False)))
  stage=identity['stage'];assert seeds.dtype==np.uint64 and seeds.tolist()==identity['seeds']==reg['seeds'][stage]
  seen.update(map(int,seeds));count+=len(seeds)
  raw_pairs.append({'canonical':str(path.relative_to(ROOT)),'public':str(public.relative_to(ROOT)),'sha256':sha(path),'stage':stage,'lives':len(seeds)})
 assert len(raw_pairs)==138 and count==6216 and seen==registered
 rel=str((PUBLIC/'manifest.json').relative_to(ROOT));commit=subprocess.check_output(['git','log','-1','--format=%H','--',rel],cwd=ROOT,text=True).strip()
 assert hashlib.sha256(subprocess.check_output(['git','show',commit+':'+rel],cwd=ROOT)).hexdigest()==sha(PUBLIC/'manifest.json')
 refs=read(OUT/'history_references.json')
 for digest,item in refs['content_by_sha256'].items():
  p=ROOT/item['repository_path'];assert sha(p)==digest and p.stat().st_size==item['bytes']
  assert hashlib.sha256(subprocess.check_output(['git','show',item['containing_public_commit']+':'+item['repository_path']],cwd=ROOT)).hexdigest()==digest
 final0=[x['seed'] for x in j['records_by_run']['control'] if x['purpose']=='final' and x['index']==0]
 reuse={'across_arms':{'shared_run_seed':53226,'shared_native_life_ids':native,'reason':'Intentional matched initial cohort/genetic seed and identical native evaluation schedule; later candidate genomes may differ after selection.'},'within_arm':{'generation':'Each generation shares3 base IDs among all256 candidates and4 new recheck IDs among64 shortlist members.','valid':'16 IDs at generations0 and3, distinct from selection.','final':'Two final index0 IDs and two final index1 IDs; index0 pair reused at T512 for growth_at_half after its T1024 final evaluation.','half_duration_reused_ids':final0,'unique_ids_per_arm':64,'logical_stage_seed_uses_per_arm':66,'research_lives_per_arm':4134},'confirmation':{'seeds':confirm,'roles':['AE_L92','AH_control','AH_reserve'],'reason':'512 new shared paired IDs across all3 roles, retaining duplicate genotype roles.'},'golden':{'seed':11,'uses':6,'reason':'One existing ABI3 seed11/T200 full+fast pair per2 search workers and1 confirmation worker.'},'reserve_lottery':'Separate stateless SHA256 domain keyed by shared native seed and external generation; it creates no life seed and consumes no mutation/tie RNG.'}
 source=[Path(__file__),OUT/'namespace_audit.py',OUT/'AH_prepare_candidate.py.txt',ROOT/'src/life/spec.py',ROOT/'src/life/evaluate.py',ROOT/'src/evolve.py',ROOT/'src/run.py',ROOT/'results/decoy_evolution_20261014/runs/s53091/config.yaml']
 r={'status':'passed_candidate_pending_final_delta','registered':False,'reserved':False,'paired_native_seed':53226,'run_life_seeds':j['run_life_seeds'],'records_by_run':j['records_by_run'],'intentional_overlap':native,'confirmation_seeds':confirm,'unique_candidate_ids':576,'base':51000000,'block':135,'whole_blocks_half_open':[[LOW,HIGH]],'inventory_sha256':sha(OUT/'candidate_namespace_inventory.json'),'historical_reference_sha256':sha(OUT/'history_references.json'),'source_pins':{str(p.relative_to(ROOT)):sha(p) for p in source},'coverage':{k:j[k] for k in ('current_npz_paths','unchanged_npz_paths','unchanged_seed_members_covered','baseline_unique_payloads_reopened','unique_payloads_total')},'added_or_modified_NPZs':len(j['changed_npz_records']),'actual_overlap_count':0,'new_NPZ_errors':0,'JSON_errors':0,'unresolved_errors':0,'JSON_matches':j['JSON_numeric_matches'],'JSON_classification':'All12 hits are the excluded upper endpoint of prior AG block134, not research membership or reservation.','text_classification':'All8 initial source matches are the same excluded AG endpoint. Later root candidate declarations and new fixtures require the registration-time delta.','synthetic_errors_classified':[],'inherited_fixture_scope':'Previously classified immutable malformed test placeholders remain covered by exact historical proof; zero new malformed NPZs were encountered. No fixture directory is copied.','AG_terminal_public_commit':commit,'AG_terminal_manifest_sha256':sha(PUBLIC/'manifest.json'),'AG_registered_unique_ids':546,'AG_raw_pairs':raw_pairs,'AG_terminal_pins':{str((AG/n).relative_to(ROOT)):sha(AG/n) for n in ('registration.json','seed_audit.json','ready.json','budget.json','terminal_process_clearance.json')},'intentional_reuse':reuse,'limits':['Candidate IDs are not reserved. Final delta must run after AH source and fixtures settle before root registration.','Unique historical payloads were reopened against these new native hash IDs and whole block, not inferred clear from older audits.','Unchanged reuse binds recorded stat identity and SHA-pinned seed payload equivalence, not full-file cryptographic rehashing.','Only seed arrays and seed-bearing identity metadata read; no outcome/genotype arrays, generation, build or life.','Full historical proof requires21 named committed repository artifacts; exact paths, commits and hashes are retained without duplicating their contents.'],'simulation_calls':0,'compilation_calls':0,'genetic_draws':0,'genotype_copies':0}
 (OUT/'candidate_namespace_review.json').write_text(json.dumps(r,indent=2)+'\n')
 print(json.dumps({'status':r['status'],'candidate_review_sha256':sha(OUT/'candidate_namespace_review.json'),'inventory_sha256':r['inventory_sha256'],'candidate_unique_ids':576,'AG_raw_pairs':138,'actual_overlaps':0,'new_errors':0}))
if __name__=='__main__':main()
