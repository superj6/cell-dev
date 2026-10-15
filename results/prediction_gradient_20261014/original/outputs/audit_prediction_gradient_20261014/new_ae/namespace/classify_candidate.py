"""Classify the completed seed-only AE candidate inventory; never register or simulate."""
from pathlib import Path
import hashlib
import io
import json
import zipfile
import numpy as np
ROOT=Path(__file__).resolve().parents[4]
OUT=Path(__file__).resolve().parent

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p):return json.loads(p.read_text())
def main():
 d=read(OUT/'candidate_namespace_inventory.json')
 assert not d['NPZ_numeric_matches'] and not d['JSON_errors']
 fields={'whole_blocks_half_open.1.1','whole_block_half_open.1','same_whole_blocks_half_open.1.1'}
 assert all(x['value']==52280000 and x['field'] in fields and 'visibility_dark_tail_information_20261014' in x['path'] for x in d['JSON_numeric_matches'])
 errors=[]
 for x in d['NPZ_errors']:
  p=ROOT/x['path'];v=read(p)
  assert x['synthetic_fixture'] and p.name=='confirmation_genotypes.npz' and v in ({'altered':True},{'frozen':'confirmation_genotypes.npz'})
  errors.append({'path':x['path'],'sha256':sha(p),'classification':'Deliberate JSON bytes under NPZ filename in test_acknowledged_artifact_tamper_rejected','contents':v})
 ad=ROOT/'outputs/autonomous_visibility_dark_tail_information_20261014';schedule=read(ad/'seed_audit.json')['seeds']
 declared=set(schedule['validation']+schedule['research']);candidate=set(sum(d['stage_seed_lists'].values(),[]))
 assert len(declared)==515 and len(candidate)==546 and not declared&candidate
 protocol=read(ad/'protocol.json');assert protocol['seeds']==schedule['research']
 # AD uses research seed lists in identity JSON and checkpoints, not separate seed arrays.
 # Validation raw arrays have no seed metadata: exact three IDs are bound by protocol/source.
 runtime=[];actual=set()
 for folder in ('validation','rows'):
  for p in sorted((ad/folder).rglob('*.npz')):
   public=ROOT/'results/visibility_dark_tail_information_20261014'/p.relative_to(ad)
   assert public.is_file() and sha(public)==sha(p)
   item={'canonical':str(p.relative_to(ROOT)),'public':str(public.relative_to(ROOT)),'full_npz_sha256':sha(p)}
   if folder=='rows':
    with zipfile.ZipFile(p) as z:
     identity=json.loads(str(np.load(io.BytesIO(z.read('identity.npy')),allow_pickle=False)))
    assert identity['seeds']==schedule['research']
    checkpoint=read(p.with_name('checkpoint.json'))
    assert checkpoint['identity']==identity and checkpoint['row_sha256']==sha(p)
    actual.update(identity['seeds']);item['research_identity_seeds_match_registered']=True
   else:item['seed_metadata']='Absent from raw validation NPZ; validation seeds are bound by frozen protocol and validator source.'
   runtime.append(item)
 assert actual==set(schedule['research'])
 assert len(runtime)==58
 review={'status':'passed','registered':False,'reserved':False,
  'authority':'Candidate namespace review only; root registration and runtime release remain separate.',
  'seeds':d['stage_seed_lists'],'whole_blocks_half_open':d['whole_blocks_half_open'],'native_run_seeds':[],
  'candidate_unique_ids':546,'inventory_sha256':sha(OUT/'candidate_namespace_inventory.json'),
  'history_references_sha256':sha(OUT/'history_references.json'),
  'source_pins':{str(p.relative_to(ROOT)):sha(p) for p in [OUT/'namespace_audit.py',Path(__file__),ROOT/'outputs/autonomous_prediction_gradient_20261014/test_source.py',ROOT/'outputs/openhr/prediction/pcommon.py',ROOT/'outputs/openhr/harness/harness.py']},
  'coverage':{k:d[k] for k in ('current_npz_paths','unchanged_npz_paths','unchanged_seed_members_covered','baseline_unique_payloads_reopened','unique_payloads_total')},
  'changed_npz_count':len(d['changed_npz_records']),'actual_overlap_count':0,'real_npz_errors':0,'json_errors':0,
  'json_hits':d['JSON_numeric_matches'],
  'json_classification':'All12 numeric hits are AD block127 exclusive upper endpoint52280000, not an actual seed or reserved member. Intervals are half-open.',
  'historical_integer_match_classification':'The raw integer union also contains only52280000 from the same AD exclusive endpoint; all515 explicitly registered AD IDs are disjoint.',
  'synthetic_npz_errors':errors,'text_match_sha256':sha(OUT/'candidate_text_matches.txt'),
  'text_classification':['Four AD source/public copies contain52280000 as the exclusive endpoint.','Historical prediction block130 uses harness.SEED_BASE43000000 and stride10000, giving44300000, disjoint from candidate52300000.','Other block128/130 spellings are sample sizes or row counts; fractional/hexadecimal matches are not seed reservations.','No whole-block or explicit-ID reservation in the candidate range was found.'],
  'AD_registered_seeds':schedule,'AD_registered_unique_count':515,
  'AD_research_raw_identity_unique_count':len(actual),'AD_runtime_public_identical_file_pairs':runtime,
  'AD_validation_seeds':{'values':schedule['validation'],'scope':'Frozen protocol/validator source binding; raw validation arrays do not independently record seed IDs.'},
  'AD_terminal_pins':{str((ad/n).relative_to(ROOT)):sha(ad/n) for n in ('protocol.json','registration.json','seed_audit.json','budget.json','terminal_process_clearance.json','ready.json','validate.py','validation/report.json')},
  'limitations':['Unchanged-path reuse relies on recorded filesystem identity/stat and exact SHA-pinned seed payload equivalence; no claim that every unchanged full NPZ was rehashed.','For these different candidates every distinct known seed payload was reopened; all changed/new seed-token members were read.','Only seed members or seed-bearing identity metadata were loaded, no scientific outcomes or genotype arrays.','Historical proof requires exact referenced artifacts in the repository; no network fetch or implicit live-source substitute.','Final targeted delta after independent reader fixture freeze remains required before registration.'],
  'simulation_calls':0,'compiled_libraries':0,'genetic_draws':0,'genotype_copies':0}
 (OUT/'candidate_namespace_review.json').write_text(json.dumps(review,indent=2)+'\n')
 print(json.dumps({'status':review['status'],'review_sha256':sha(OUT/'candidate_namespace_review.json'),'inventory_sha256':review['inventory_sha256'],'history_references_sha256':review['history_references_sha256'],'AD_runtime_public_pairs':len(runtime)},indent=2))
if __name__=='__main__':main()
