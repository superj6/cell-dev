"""Classify AI candidate-only namespace and completed AH seed metadata."""
from pathlib import Path
import hashlib,io,json,subprocess,zipfile
import numpy as np
ROOT=Path(__file__).resolve().parents[3]
OUT=Path(__file__).resolve().parent
AH=ROOT/'outputs/autonomous_exploratory_reserve_20261014'
PUBLIC=ROOT/'results/exploratory_reserve_20261014'
LOW,HIGH=52360000,52370000
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
read=lambda p:json.loads(p.read_text())
def main():
 j=read(OUT/'candidate_namespace_inventory.json')
 assert j['native_union_count']==64 and j['paired_native_seeds']=={'control':53227,'reserve':53227}
 native=j['run_life_seeds']['control'];assert native==j['run_life_seeds']['reserve']==j['intentional_overlap']
 confirm=list(range(52360000,52360512));assert j['stage_seed_lists']=={'confirm':confirm}
 candidate=set(native+confirm);assert len(candidate)==576 and 11 not in candidate
 assert not j['NPZ_numeric_matches'] and not j['NPZ_errors'] and not j['JSON_errors'] and not j['JSON_numeric_string_or_key_matches']
 allowed={'whole_blocks_half_open.0.1','whole_block_half_open.1','same_whole_blocks_half_open.0.1'}
 prior_hits=[x for x in j['JSON_numeric_matches'] if x['value']==LOW and x['field'] in allowed and 'exploratory_reserve_20261014' in x['path']]
 draft_hits=[x for x in j['JSON_numeric_matches'] if x['path']=='outputs/audit_exploratory_reserve_replication_20261014/reader_adaptation_plan.json' and x['field']=='namespace_status.native_seed_candidate' and x['value']==53227]
 assert len(prior_hits)==12 and len(draft_hits)==1 and len(j['JSON_numeric_matches'])==13
 assert j['historical_actual_matches_excluding_prior_endpoint']==[LOW]
 lines=(OUT/'candidate_text_matches.txt').read_text().splitlines()
 endpoint=[x for x in lines if 'exploratory_reserve_20261014/namespace/' in x and ('52_360_000' in x or '52360000' in x or '52,360,000)' in x)]
 draft=[x for x in lines if x.startswith('outputs/audit_exploratory_reserve_replication_20261014/register_study.py:') and ('53227' in x or '52360000, 52360512' in x)]
 decimal=[x for x in lines if 'results/structural_20261013/README.md:7:' in x and '-0.252376 ± 0.209347' in x]
 assert len(endpoint)==8 and len(draft)==2 and len(decimal)==2 and len(lines)==12
 reg=read(AH/'registration.json');old_audit=read(AH/'seed_audit.json')
 registered=set(reg['confirmation_seeds']+old_audit['run_life_seeds']['control'])
 assert reg['paired_native_seed']==53226 and len(registered)==576 and not registered & candidate
 assert not any(LOW<=x<HIGH for x in registered) and not set(native)&set(confirm)
 raw_pairs=[]
 for path in sorted((AH/'confirmation/persistent').glob('*.npz')):
  relative=path.relative_to(AH);public=PUBLIC/relative;assert sha(path)==sha(public)
  with zipfile.ZipFile(path) as z:
   seeds=np.load(io.BytesIO(z.read('seeds.npy')),allow_pickle=False)
   assert seeds.dtype==np.uint64 and seeds.tolist()==reg['confirmation_seeds']
   if 'identity.npy' in z.namelist():
    identity=json.loads(str(np.load(io.BytesIO(z.read('identity.npy')),allow_pickle=False)))
    assert identity['seeds']==reg['confirmation_seeds']
  raw_pairs.append({'canonical':str(path.relative_to(ROOT)),'public':str(public.relative_to(ROOT)),'sha256':sha(path),'seed_count':len(seeds)})
 assert len(raw_pairs)==4
 native_log_pairs=[]
 for arm in ('control','reserve'):
  path=AH/'runs'/arm/'lineage.jsonl';public=PUBLIC/path.relative_to(AH);assert sha(path)==sha(public)
  rows=[json.loads(line) for line in path.read_text().splitlines()][1:]
  actual=[]
  for g,row in enumerate(rows):
   expected=[x['seed'] for x in old_audit['records_by_run'][arm] if x['purpose']=='gen' and x['index']==g]
   assert row['gen']==g and row['seeds']+row['recheck']['seeds']==expected
   actual.extend(expected)
  assert len(actual)==28 and len(rows)==4
  native_log_pairs.append({'canonical':str(path.relative_to(ROOT)),'public':str(public.relative_to(ROOT)),'sha256':sha(path),'logged_generation_life_ids':actual})
 rel=str((PUBLIC/'manifest.json').relative_to(ROOT));commit=subprocess.check_output(['git','log','-1','--format=%H','--',rel],cwd=ROOT,text=True).strip()
 assert hashlib.sha256(subprocess.check_output(['git','show',commit+':'+rel],cwd=ROOT)).hexdigest()==sha(PUBLIC/'manifest.json')
 refs=read(OUT/'history_references.json')
 for digest,item in refs['content_by_sha256'].items():
  p=ROOT/item['repository_path'];assert sha(p)==digest and p.stat().st_size==item['bytes']
  assert hashlib.sha256(subprocess.check_output(['git','show',item['containing_public_commit']+':'+item['repository_path']],cwd=ROOT)).hexdigest()==digest
 final0=[x['seed'] for x in j['records_by_run']['control'] if x['purpose']=='final' and x['index']==0]
 reuse={'across_arms':{'shared_run_seed':53227,'shared_native_life_ids':native,'reason':'Intentional matched initial cohort/genetic seed and identical native evaluation schedule; later candidate genomes may differ after selection.'},'within_arm':{'generation':'Each generation shares3 base IDs among all256 candidates and4 new recheck IDs among64 shortlist members.','valid':'16 IDs at generations0 and3, distinct from selection.','final':'Two final index0 IDs and two final index1 IDs; index0 pair reused at T512 for growth_at_half after its T1024 final evaluation.','half_duration_reused_ids':final0,'unique_ids_per_arm':64,'logical_stage_seed_uses_per_arm':66,'research_lives_per_arm':4134},'confirmation':{'seeds':confirm,'roles':['AE_L92','AI_control','AI_reserve'],'reason':'512 new shared paired IDs across all3 roles, retaining duplicate genotype roles.'},'golden':{'seed':11,'uses':6,'reason':'One existing ABI3 seed11/T200 full+fast pair per2 search workers and1 confirmation worker.'},'reserve_lottery':'Separate stateless SHA256 domain keyed by shared native seed and external generation; it creates no life seed and consumes no mutation/tie RNG.'}
 source=[Path(__file__),OUT/'namespace_audit.py',OUT/'AI_prepare_candidate.py.txt',ROOT/'src/life/spec.py',ROOT/'src/life/evaluate.py',ROOT/'src/evolve.py',ROOT/'src/run.py',ROOT/'results/decoy_evolution_20261014/runs/s53091/config.yaml']
 r={'status':'passed_candidate_pending_final_delta','registered':False,'reserved':False,'paired_native_seed':53227,'run_life_seeds':j['run_life_seeds'],'records_by_run':j['records_by_run'],'intentional_overlap':native,'confirmation_seeds':confirm,'unique_candidate_ids':576,'base':51000000,'block':136,'whole_blocks_half_open':[[LOW,HIGH]],'inventory_sha256':sha(OUT/'candidate_namespace_inventory.json'),'historical_reference_sha256':sha(OUT/'history_references.json'),'source_pins':{str(p.relative_to(ROOT)):sha(p) for p in source},'current_proposal_pins':{str((OUT.parent/n).relative_to(ROOT)):sha(OUT.parent/n) for n in ('reader_adaptation_plan.json','register_study.py')},'coverage':{k:j[k] for k in ('current_npz_paths','unchanged_npz_paths','unchanged_seed_members_covered','baseline_unique_payloads_reopened','unique_payloads_total')},'added_or_modified_NPZs':len(j['changed_npz_records']),'actual_overlap_count':0,'new_NPZ_errors':0,'JSON_errors':0,'unresolved_errors':0,'JSON_matches':j['JSON_numeric_matches'],'JSON_classification':'12 hits are the excluded AH block135 upper endpoint; one unexecuted AI reader-plan candidate declaration. No prior use.','text_classification':'8 excluded AH block135 endpoints;2 unexecuted AI root candidate literals;2 existing decimal fitness values accidentally matching the broad source regex.','synthetic_errors_classified':[],'inherited_fixture_scope':'Previously classified immutable malformed test placeholders remain covered by exact historical proof; zero new malformed NPZs were encountered. No fixture directory is copied.','AH_terminal_public_commit':commit,'AH_terminal_manifest_sha256':sha(PUBLIC/'manifest.json'),'AH_registered_unique_ids':576,'AH_confirmation_seed_pairs':raw_pairs,'AH_native_log_pairs':native_log_pairs,'AH_terminal_pins':{str((AH/n).relative_to(ROOT)):sha(AH/n) for n in ('registration.json','seed_audit.json','ready.json','budget.json','terminal_process_clearance.json')},'intentional_reuse':reuse,'limits':['Candidate IDs are not reserved. Final delta must run after AI source and fixtures settle before root registration.','Unique historical payloads were reopened against these new native hash IDs and whole block, not inferred clear from older audits.','Unchanged reuse binds recorded stat identity and SHA-pinned seed payload equivalence, not full-file cryptographic rehashing.','Only seed arrays and seed-bearing identity metadata read; no outcome/genotype arrays, generation, build or life.','Full historical proof requires23 named committed repository artifacts; exact paths, commits and hashes are retained without duplicating their contents.'],'simulation_calls':0,'compilation_calls':0,'genetic_draws':0,'genotype_copies':0}
 (OUT/'candidate_namespace_review.json').write_text(json.dumps(r,indent=2)+'\n')
 print(json.dumps({'status':r['status'],'candidate_review_sha256':sha(OUT/'candidate_namespace_review.json'),'inventory_sha256':r['inventory_sha256'],'candidate_unique_ids':576,'AH_confirmation_seed_pairs':4,'AH_native_log_pairs':2,'actual_overlaps':0,'new_errors':0}))
if __name__=='__main__':main()
