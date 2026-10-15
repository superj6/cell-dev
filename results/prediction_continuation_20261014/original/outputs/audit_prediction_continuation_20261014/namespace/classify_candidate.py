"""Classify AF candidate proof and resolve scan-time synthetic writes; no reservation or life."""
from pathlib import Path
import hashlib, importlib.util, io, json, zipfile
import numpy as np
ROOT=Path(__file__).resolve().parents[3]
OUT=Path(__file__).resolve().parent
LOW,HIGH=52_310_000,52_320_000
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p):return json.loads(p.read_text())
def main():
 d=read(OUT/'candidate_namespace_inventory.json')
 assert not d['NPZ_numeric_matches'] and not d['JSON_errors']
 fields={'whole_blocks_half_open.2.1','whole_block_half_open.1','same_whole_blocks_half_open.2.1'}
 assert all(x['value']==LOW and x['field'] in fields and 'prediction_gradient_20261014' in x['path'] for x in d['JSON_numeric_matches'])
 assert d['historical_actual_matches_excluding_prior_endpoint']==[LOW]
 native=set(sum(d['run_life_seeds'].values(),[]));confirm=d['stage_seed_lists']['confirm']
 assert len(native)==128 and len(confirm)==512 and not native&set(confirm) and 11 not in native|set(confirm)
 s=importlib.util.spec_from_file_location('af_namespace_predicate',OUT/'namespace_audit.py');h=importlib.util.module_from_spec(s);s.loader.exec_module(h)
 reader=OUT.parent/'reader_source_review.json'
 assert sha(reader)=='49784209ceb2c4b2f92157a2b2af10c459bd91ffe83b7776f939eebad827350d'
 resolutions=[];stable_records={}
 for e in d['NPZ_errors']:
  p=ROOT/e['path'];assert e['synthetic_fixture']
  if e['error'].startswith('BadZipFile:'):
   assert 'test_tmp_v2/one_four_row_fixture0/confirmation/genotypes.npz' in str(p)
   assert p.read_bytes()==b'synthetic file-hash placeholder, not a genotype archive'
   resolutions.append({'path':e['path'],'sha256':sha(p),'classification':'Deliberate file-hash-only synthetic placeholder, not a genetic archive or unexamined research data.'})
  else:
   assert e['error']=='ValueError: NPZ changed during audit' and 'test_tmp_final/one_four_row_fixture0/' in str(p)
   st=h.stat(p);members={}
   with zipfile.ZipFile(p) as z:
    for member in z.namelist():
     if not h.seed_member(member):continue
     raw=z.read(member);v=np.load(io.BytesIO(raw),allow_pickle=False)
     assert np.issubdtype(v.dtype,np.integer) and not any(LOW<=int(x)<HIGH or int(x) in native for x in v.flat)
     assert set(map(int,v.flat))==set(range(512))
     members[member]={'npy_sha256':hashlib.sha256(raw).hexdigest(),'count':int(v.size),'min':int(v.min()),'max':int(v.max())}
   assert h.stat(p)==st
   stable_records[e['path']]={'stat':st,'synthetic_fixture':True,'seed_members':members}
   resolutions.append({'path':e['path'],'sha256':sha(p),'classification':'Synthetic fixture changed during initial scan; re-read after reader freeze, valid ZIP, all seed members0..511 and disjoint.','seed_members':members})
 ae=ROOT/'outputs/autonomous_prediction_gradient_20261014';public=ROOT/'results/prediction_gradient_20261014'
 schedule=read(ae/'seed_audit.json')['seeds'];declared=set(sum(schedule.values(),[]))
 assert len(declared)==546 and not declared & (native|set(confirm))
 assert all(not LOW<=x<HIGH for x in declared)
 actual=set();pairs=[];stage_counts={}
 for p in sorted((ae/'measurement').rglob('row_*.npz')):
  relative=p.relative_to(ae);other=public/relative
  assert sha(p)==sha(other)
  with zipfile.ZipFile(p) as z:
   ids=np.load(io.BytesIO(z.read('seeds.npy')),allow_pickle=False)
   identity=json.loads(str(np.load(io.BytesIO(z.read('identity.npy')),allow_pickle=False)))
  stage=identity['stage'];assert ids.dtype==np.uint64 and ids.tolist()==identity['seeds']==schedule[stage]
  actual.update(map(int,ids));stage_counts[stage]=stage_counts.get(stage,0)+1
  pairs.append({'canonical':str(p.relative_to(ROOT)),'public':str(other.relative_to(ROOT)),'sha256':sha(p),'stage':stage,'count':int(ids.size)})
 assert len(pairs)==138 and stage_counts=={'calibration':4,'confirm':4,'screen':130} and actual==declared
 ad=read(ROOT/'outputs/autonomous_visibility_dark_tail_information_20261014/seed_audit.json')['seeds'];adset=set(sum(ad.values(),[]))
 assert len(adset)==515 and not adset&(native|set(confirm)) and not any(LOW<=x<HIGH for x in adset)
 review={'status':'passed_candidate_pending_final_delta','registered':False,'reserved':False,'authority':'Candidate-only namespace proof; root registration and runtime release are separate.','runs':[53224,53225],'run_backgrounds':{'53224':'D90','53225':'L92'},'confirmation_seeds':confirm,'run_life_seeds':d['run_life_seeds'],'whole_blocks_half_open':[[LOW,HIGH]],'candidate_unique_life_ids':640,'inventory_sha256':sha(OUT/'candidate_namespace_inventory.json'),'history_references_sha256':sha(OUT/'history_references.json'),'source_pins':{str(p.relative_to(ROOT)):sha(p) for p in [OUT/'namespace_audit.py',Path(__file__),reader,OUT.parent/'analyzer_peer_review.json',ROOT/'outputs/openhr/harness/harness.py',ROOT/'outputs/openhr/prediction/pcommon.py',ROOT/'outputs/openhr/prediction/aggregate.py']},'coverage':{k:d[k] for k in ('current_npz_paths','unchanged_npz_paths','unchanged_seed_members_covered','baseline_unique_payloads_reopened','unique_payloads_total')},'actual_overlap_count':0,'real_npz_errors':0,'unresolved_errors':0,'json_errors':0,'json_matches':d['JSON_numeric_matches'],'json_classification':'All12 hits are prior AE block130 exclusive upper endpoint52310000, not a reserved or used member. No prior use of genetic/run seeds53224/53225 found in targeted JSON/source/config checks.','synthetic_scan_error_resolutions':resolutions,'postfreeze_synthetic_records':stable_records,'text_match_sha256':sha(OUT/'candidate_text_matches.txt'),'text_classification':['Historical prediction block131 uses SEED_BASE43000000 +10000*131 =44310000, disjoint from52310000.','AE source copies use52310000 only as the old exclusive upper endpoint.','Remaining literal matches are fractional numerical results or substrings inside hexadecimal hashes, not reservations.'],'AE_registered_seeds':schedule,'AE_registered_unique_count':546,'AE_actual_raw_row_seed_union_count':len(actual),'AE_runtime_public_identical_rows':pairs,'AE_raw_row_counts':stage_counts,'AD_registered_unique_count':515,'AD_registered_seeds':ad,'AE_terminal_pins':{str((ae/n).relative_to(ROOT)):sha(ae/n) for n in ('protocol.json','registration.json','seed_audit.json','budget.json','terminal_process_clearance.json','ready.json')},'genetic_RNG':{'run_and_mutation_seeds':[53224,53225],'tie_generator_seeds':[7972225,7972226],'scope':'Genetic RNG seeds are separate from the64 hashed evaluation life IDs per run. No RNG draws or genotype generation/copies occurred.'},'intentional_reuse':{'within_generation':'Shared initial3 seeds across256 genomes; separate shared4 recheck seeds across64 genomes.','half_duration_final':'Two T512 calls/run reuse the same two final-purpose index0 seeds as the corresponding T1024 diagnostics.','confirmation':'Same512 fresh seeds across four fixed roles.','golden_validation':'StandardABI3 seed11/T200 full+fast pair in each of three production processes; six calls intentionally reuse seed11.'},'limitations':['Full historical namespace verification needs exact13 referenced committed repository artifacts; no network fetch or live-source substitute.','Changed/new seed-token payloads are read; unchanged equivalence uses stat identity and SHA-pinned seed-payload groups, not full-NPZ rehash claims.','Every distinct seed payload was reopened against these new whole-block and hashed-ID candidates.','Synthetic scan-time writes were resolved after reader freeze. Final delta must still cover later root illustration artifacts before registration.','Only seed arrays, seed-bearing identity metadata and source/header data were inspected; no genotype arrays or scientific outcome arrays loaded.'],'simulation_calls':0,'compiled_libraries':0,'genetic_draws':0,'genotype_copies':0}
 (OUT/'candidate_namespace_review.json').write_text(json.dumps(review,indent=2)+'\n')
 print(json.dumps({'status':review['status'],'review_sha256':sha(OUT/'candidate_namespace_review.json'),'inventory_sha256':review['inventory_sha256'],'AE_identical_raw_rows':len(pairs),'actual_overlap_count':0,'synthetic_write_resolutions':len(stable_records),'intentional_malformed_fixtures':len(resolutions)-len(stable_records)}))
if __name__=='__main__':main()
