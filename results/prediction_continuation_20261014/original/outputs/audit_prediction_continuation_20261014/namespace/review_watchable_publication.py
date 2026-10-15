"""Read-only AF namespace supplement and AE viewer claim review; no engines/replays."""
from pathlib import Path
import hashlib,json,re,sys
import numpy as np
ROOT=Path(__file__).resolve().parents[3]
OUT=Path(__file__).resolve().parent
SOURCE=ROOT/'outputs/ae_watchable_20261014'
PUBLIC=ROOT/'results/ae_watchable_20261014'
AE=ROOT/'results/prediction_gradient_20261014'
HTML=ROOT/'results/atlas/persistent_target.html'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p):return json.loads(p.read_text())
def main():
 audit=read(OUT/'seed_audit.json');assert sha(OUT/'seed_audit.json')=='96abcd3e6a81ad8c0710b0ac870c993bb01dc115d08eb8920c000251e01960d8'
 manifest=read(PUBLIC/'manifest.json');assert len(manifest['artifacts'])==19
 assert {p.name for p in PUBLIC.iterdir() if p.is_file()}==set(manifest['artifacts'])|{'manifest.json'}
 pairs=[]
 for n,item in manifest['artifacts'].items():
  assert item['origin']==str((SOURCE/n).relative_to(ROOT)) and sha(SOURCE/n)==sha(PUBLIC/n)==item['sha256']
  assert (PUBLIC/n).stat().st_size==item['bytes']
  pairs.append({'source':item['origin'],'copy':str((PUBLIC/n).relative_to(ROOT)),'sha256':item['sha256'],'bytes':item['bytes']})
 assert not list(SOURCE.rglob('*.npz')) and not list(PUBLIC.rglob('*.npz'))
 assert manifest['external_artifacts'][str(HTML.relative_to(ROOT))]=={'sha256':sha(HTML),'bytes':HTML.stat().st_size}
 data=(PUBLIC/'bodies.json').read_text().strip();engine=(ROOT/'results/atlas/play/lifesim.js').read_text();ui=(PUBLIC/'viewer.js').read_text()
 expected=(PUBLIC/'template.html').read_text().replace('__DATA__',data).replace('__ENGINE__',engine).replace('__UI__',ui)
 assert expected.encode()==HTML.read_bytes()
 assert not any(x in expected for x in ('__DATA__','__ENGINE__','__UI__'))
 embedded=re.search(r'<script id="comparison-data" type="application/json">(.*?)</script>',expected,re.S).group(1)
 assert embedded==data
 body=json.loads(data);truth=read(PUBLIC/'truth.json');ap=read(AE/'protocol.json');summary=read(AE/'analysis_result/summary.json');roles=read(AE/'confirmation_roles.json')
 assert body['seed']==truth['seed']==ap['seeds']['confirm'][0]==52300000
 assert body['source_summary_sha256']==sha(AE/'analysis_result/summary.json')
 assert body['summary']=={b:summary['contrasts']['H_'+b+'_minus_P_'+b] for b in ('D90','L92')}
 assert [x['name'] for x in body['bodies']]==roles['roles']
 assert [x['genotype_sha256'] for x in body['bodies']]==[roles['genotype_sha256'][x] for x in roles['roles']]
 # Static source packing and first existing raw records only; no created or changed genotypes.
 sys.path.insert(0,str(ROOT))
 from src.life import spec
 with np.load(AE/'confirmation_genotypes.npz',allow_pickle=False) as z:raw=z['genomes']
 packed=spec.V3.pack_genomes(raw,'hexprism')
 for i,(b,t) in enumerate(zip(body['bodies'],truth['cases'])):
  assert b['abi']==3 and b['mode']=='grn' and b['world']=={k:ap['world'][k] for k in spec.V3.WORLD_KEYS}
  assert np.array_equal(np.asarray(b['genome'],dtype=np.float64),packed[i])
  p=AE/f'measurement/confirm/persistent/confirm/row_{i:04d}.npz'
  assert t['source_sha256']==sha(p) and t['role']==roles['roles'][i] and t['seed']==52300000
  with np.load(p,allow_pickle=False) as z:
   assert int(z['seeds'][0])==52300000 and [float(v).hex() for v in z['ledger'][0]]==t['ledger_hex']
  assert [float(x).hex() for x in t['ledger']]==t['ledger_hex']
 assert truth['ledger']==list(spec.V3.LEDGER)
 replay=read(PUBLIC/'replay_stdout.json');budget=read(PUBLIC/'validation_budget.json');uicheck=read(PUBLIC/'ui_check.json')
 assert replay['status']=='complete' and replay['js_replay_lives']==4 and replay['new_C_lives']==replay['new_research_lives']==0
 assert [r['role'] for r in replay['rows']]==roles['roles'] and all(r['ledger_columns_bitwise_equal']==57 and r['status']==0 and r['seed']==52300000 for r in replay['rows'])
 assert [r['captures'] for r in replay['rows']]==[3,3,4,2]
 assert budget['status']=='complete' and budget['all_processes_exited'] and not budget['running'] and not budget['queued'] and not budget['cleanup_error']
 assert budget['stdout_sha256']==sha(PUBLIC/'replay_stdout.json') and budget['stderr_sha256']==sha(PUBLIC/'replay_stderr.txt')
 assert uicheck['status']=='passed' and uicheck['assertions']==60 and uicheck['realEngineLives']==0
 assert [x['width'] for x in uicheck['layouts']]==[540,330]
 previous=read(OUT/'final_namespace_delta.json')['root_watchable_illustration']['source_pins']
 assert all(sha(ROOT/n)==v for n,v in previous.items())
 native=set(sum(audit['run_life_seeds'].values(),[]));fresh=set(audit['confirmation_seeds'])
 assert 52300000 not in native|fresh and not 52310000<=52300000<52320000
 seedfields=[]
 def visit(x,path):
  if isinstance(x,dict):
   for k,v in x.items():
    if re.fullmatch(r'seeds?',k,re.I):seedfields.append({'path':path+'.'+k,'value':v})
    else:visit(v,path+'.'+k)
  elif isinstance(x,list):
   for i,v in enumerate(x):
    if isinstance(v,(dict,list)):visit(v,path+'.'+str(i))
 for n in manifest['artifacts']:
  if n.endswith('.json'):visit(read(PUBLIC/n),n)
 actual={v for x in seedfields for v in (x['value'] if isinstance(x['value'],list) else [x['value']])}
 assert actual=={52300000}
 assert 'src.life.build' not in sys.modules and 'src.checkpoint' not in sys.modules
 docpins={str(p.relative_to(ROOT)):sha(p) for p in (ROOT/'README.md',ROOT/'RESULTS.md',PUBLIC/'README.md',PUBLIC/'template.html',PUBLIC/'viewer.js')}
 review={'status':'passed_read_only_source_and_scientific_review','source_sha256':sha(Path(__file__)),'source_pins':docpins,'public_manifest_sha256':sha(PUBLIC/'manifest.json'),'html_sha256':sha(HTML),'exact_source_copies':19,'standalone_html_exact_reconstruction':True,'embedded_engine_sha256':sha(ROOT/'results/atlas/play/lifesim.js'),'unchanged_four_genotypes_and_V_world':True,'existing_raw_truth_columns_verified':228,'recorded_JS_replay_columns_matched':228,'recorded_mock_assertions':60,'new_replays_in_review':0,'claims_review':['Viewer mean and paired SE data exactly equal complete AE confirmation summary.','L92 capture gain is modest and most fitness gain remains cost saving; D90 capture change is unresolved at the study three-SE rule.','The first confirmation seed was chosen by position, not outcome: this life has L92H2 versusP3 captures, D90H4 versusP3. Both counterexamples to the average direction remain displayed.','Caption explains same seed does not imply identical later target placement; capture and body position affect placement.','Controls only choose the lineage, pause/restart and playback rate; they do not add organism inputs or alter world constants.','Both simulations start paused; hidden-tab pause and finite drawing layouts are present in source and covered by the recorded mock checks.','No memory, prediction or new-algorithm inference is asserted.'], 'limitations':['No real browser binary or screenshot was available; this is source and exact-build review plus existing mock/Node receipts, not independent rendered-browser validation.','Four replays concern existing lives, not additional research observations or a general cross-browser determinism guarantee.'],'simulation_calls':0,'compiled_libraries':0,'genetic_draws':0,'AF_genotype_copies':0}
 (OUT.parent/'watchable_ui_scientific_review.json').write_text(json.dumps(review,indent=2)+'\n')
 supplement={'status':'passed','registered':False,'reserved':False,'previous_seed_audit_sha256':sha(OUT/'seed_audit.json'),'previous_final_delta_sha256':sha(OUT/'final_namespace_delta.json'),'public_manifest_sha256':sha(PUBLIC/'manifest.json'),'exact_source_copy_pairs':pairs,'external_html':{'path':str(HTML.relative_to(ROOT)),'sha256':sha(HTML),'bytes':HTML.stat().st_size,'embedded_data_exact_source_match':True},'public_folder_files_including_manifest':20,'external_html_files':1,'publication_files_total':21,'new_npz_files':0,'new_seed_values':[],'explicit_reused_seed_values':[52300000],'seed_field_occurrences':seedfields,'AF_native_ids_intersection':[],'AF_whole_block_intersection':[],'seven_previous_frozen_seed_artifacts_unchanged':True,'illustration_budget_sha256':sha(PUBLIC/'validation_budget.json'),'illustration_js_replays':4,'new_C_or_research_lives':0,'ui_scientific_review_sha256':sha(OUT.parent/'watchable_ui_scientific_review.json'),'source_sha256':sha(Path(__file__)),'scope':'Narrow copy/publication supplement:19 byte-identical source artifacts, one public manifest and one exactly reconstructed self-contained HTML. The only seed is existingAE52300000; no full historical scan or candidate change is implied.','review_simulation_calls':0,'compiled_libraries':0,'genetic_draws':0}
 (OUT/'watchable_publication_supplement.json').write_text(json.dumps(supplement,indent=2)+'\n')
 print(json.dumps({'status':'passed','supplement_sha256':sha(OUT/'watchable_publication_supplement.json'),'UI_review_sha256':sha(OUT.parent/'watchable_ui_scientific_review.json'),'public_manifest_sha256':sha(PUBLIC/'manifest.json'),'source_copy_pairs':19,'new_seed_values':[],'existing_seed':52300000}))
if __name__=='__main__':main()
