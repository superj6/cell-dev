"""Source/seed review receipts only; no imports from the engine or producer."""
import ast
import hashlib
import json
from pathlib import Path
import xml.etree.ElementTree as ET

ROOT=Path(__file__).resolve().parents[2]
OUT=Path(__file__).resolve().parent
STUDY=ROOT/'outputs/autonomous_visibility_dark_tail_information_20261014'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
read=lambda p:json.loads(p.read_text())
def save(name,value):
 p=OUT/name;p.write_text(json.dumps(value,indent=2)+'\n');return sha(p)
def definition(path,name):
 tree=ast.parse(path.read_text())
 return ast.dump(next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name==name),include_attributes=False)
old=ROOT/'outputs/autonomous_visibility_information_x2_20261014'
functions=read(OUT/'lifecycle_reuse.json')['monitor_functions_AST_identical']
for name in functions:assert definition(old/'monitor.py',name)==definition(STUDY/'monitor.py',name)
assert definition(old/'common.py','parent_check')==definition(STUDY/'common.py','parent_check')
assert (STUDY/'numerical.py').read_bytes()==(ROOT/'outputs/autonomous_visibility_flash_gradient_20261014/numerical.py').read_bytes()
identity=ast.parse((STUDY/'production_identity.py').read_text())
assert len([n for n in ast.walk(identity) if isinstance(n,ast.Call) and isinstance(n.func,ast.Name) and n.func.id=='numerical_identity'])==1
assert not any((STUDY/n).exists() for n in ('protocol.json','registration.json','inputs','original','ready.json','attempt.json','budget.json','validation','rows','build-cache'))
sourcepins={str(p.relative_to(ROOT)):sha(p) for p in sorted(STUDY.iterdir()) if p.is_file()}
xml=ET.parse(OUT/'source_tests.xml').getroot()
suites=[xml] if xml.tag=='testsuite' else list(xml.findall('testsuite'))
assert sum(int(x.attrib['tests']) for x in suites)==11
assert not sum(int(x.attrib.get(k,0)) for x in suites for k in ('errors','failures'))
cost=read(OUT/'cost_review.json'); total=0.
import numpy as np
for row in cost['rows']:
 p=ROOT/row['row_path'];assert sha(p)==row['row_sha256']
 with np.load(p,allow_pickle=False) as x:
  cpu=float(x['cpu_seconds']);assert cpu==row['cpu_seconds'];total+=cpu
assert total==cost['historical_research_cpu_seconds']
source_receipt={
 'status':'passed_source_only_review','protocol_or_input_binding_complete':False,
 'source_pins':sourcepins,'review_source_sha256':sha(Path(__file__)),
 'reused_lifecycle_functions_AST_identical':functions,'live_parent_guard_AST_identical_to_X2':True,
 'numerical_source_byte_identical_to_AC':True,
 'scope':{'research_lives':6656,'validation_lives':76,'total_calls':6732,'cpu_cap':2400,'validation_cap':180,'stop_thresholds':[170,2390],'concurrent_worker_groups':1,'threads_per_worker':2},
 'identity':{'invocations':1,'lives':2,'seed':11,'T':200,'ABI':3,'inherited_owned_validation_group':True,
  'persisted_monitor_identity_fields':['pid','ppid','pgid','start_ticks'],'expected_recorded_leaders':3,
  'nested_PID_individually_recorded':False,
  'source_evidence':'validate.py invokes one production_identity.py child before scratch imports; no new session; nested parent_check binds live monitor attempt/start ticks, parent, session/group and phase. Group CPU and teardown include descendants. No unsupported nested-PID or persisted sid claim.'},
 'ABI_boundary':'Frozen ABI3 metadata [3,875,129,66,57,5,23,1024,7,18] precedes raw data calls; explicit contiguous shapes include world66, ledger57 and1024x4 cells. Separate production child verifies ABI4 metadata [4,875,129,70,58,5,23,1024,7,18]; bridge maps scratch21 to production57 and excludes only scratch aliases21/22 plus all/world hashes.',
 'candidate_delta':'Only physical visibility_low .25->0 and scratch dark_amp .25->0; I/B params[21] .25->0. A parameters unchanged, its metadata difference list becomes [9,10]; bodies, programs, all other parameters and controller sources are retained.',
 'validation':'8 R0/R1 bridge +12 I/A/B full-fast +15 recorded/replayed/control +39 all-role calibration +2 isolated goldens; callback and requested-action bytes matched, truth-read count remains zero; no scientific outcome selection.',
 'budget':'One validation group then one research group; cumulative monitor/children/group CPU includes compiler failures and teardown. 180 allowance plus 1.5 times512 times sum(max(new3lifeCPU/3, old512lifeCPU/512)) must be <=2390, every role retained. First attempt only; clean AC terminal status is resource dependency, not success gate.',
 'historical_cost':{'timing_rows_checked':13,'research_cpu_seconds':total,'historical_floor_projection':180+1.5*total,'new_calibration_required':True,'cost_review_sha256':sha(OUT/'cost_review.json')},
 'existing_mock_tests':{'count':11,'junit_sha256':sha(OUT/'source_tests.xml'),'rerun_by_this_review':False},
 'limitations':['These unchanged transferred reflexes are not newly optimized in darkness.','Model and idle-action ablations are broad instruments, not isolated memory lesions.','Finite flash and motor/queued-signal persistence can support simple old-direction strategies.','Information payoff does not prove evolved memory or require a hand-built winning organism.','Actual prepared source/input pins and final reader still require review before root release.'],
 'blockers':[],'new_lives':0,'new_compilations':0,'genotypes_copied_or_generated':0}
source_sha=save('independent_source_review.json',source_receipt)
base=read(OUT/'candidate_namespace_review.json');delta=read(OUT/'final_namespace_delta.json')
assert base['actual_overlap_count']==0 and delta['status']=='passed'
assert not delta['actual_overlaps'] and not delta['NPZ_errors'] and not delta['JSON_errors']
assert len(delta['new_or_modified_npz_records'])==163 and delta['seed_members_read']==158
assert delta['current_npz_paths']==73060 and delta['unchanged_npz_paths']==72897
assert len(delta['JSON_numeric_matches'])==16
assert sorted((OUT/'final_text_matches.txt').read_text().splitlines())==sorted((OUT/'candidate_text_matches.txt').read_text().splitlines())
seeds={'validation':list(range(52_260_000,52_260_003)),'research':list(range(52_270_000,52_270_512))}
assert not(set(seeds['validation'])&set(seeds['research'])) and 11 not in sum(seeds.values(),[])
AC=ROOT/'outputs/autonomous_visibility_flash_gradient_20261014'
ac=read(AC/'seed_audit.json')['seeds'];oldids={x for ids in ac.values() for x in ids}
assert len(oldids)==546 and not oldids.intersection(sum(seeds.values(),[]))
seed_sha={k:hashlib.sha256(json.dumps(v,separators=(',',':')).encode()).hexdigest() for k,v in seeds.items()}
seed_receipt={'status':'passed','registered':False,'reserved':False,'authority':'Root candidate-only namespace review; registration and runtime release remain separate.',
 'seeds':seeds,'stage_seed_sha256_compact_json':seed_sha,'whole_blocks_half_open':base['whole_blocks_half_open'],
 'decimal_base':51000000,'stride':10000,'blocks':[126,127],
 'intentional_reuse':{'validation_aliases':dict(zip(['v0','v1','v2'],seeds['validation'])),'actual_calls_per_validation_seed':[29,32,13],
 'bridge':'R0/R1 each v0/v1 scratch and production:8 calls','full_fast':'I/A/B each v0/v1 full and fast:12 calls',
 'callback_replay':'Each I/A/B recordv0,replayv0,replayv1,alternate-world replayv1,ordinary controlv1:15 calls',
 'calibration':'All13roles share[v0,v1,v2],39 calls','research':'All13roles share all512freshIDs,6656 calls',
 'engineering_goldens':{'seeds':[11,11],'T':200,'ABI':3,'purpose':'Existing numerical compatibility; explicitly reused and excluded from fresh science allocation'}},
 'candidate_review_sha256':sha(OUT/'candidate_namespace_review.json'),'candidate_inventory_sha256':sha(OUT/'candidate_namespace_inventory.json'),
 'final_delta_sha256':sha(OUT/'final_namespace_delta.json'),'final_delta_source_sha256':sha(OUT/'final_namespace_delta.py'),
 'namespace_history_references_sha256':sha(OUT/'namespace_history_references.json'),
 'history_access':'Exact committed repository paths/commit/SHA in namespace_history_references.json are required for complete historical coverage; the prospective AD folder alone will not contain that older32MB evidence. No network or silent source fallback is implied.',
 'AC_terminal':{'budget_sha256':sha(AC/'budget.json'),'clearance_sha256':sha(AC/'terminal_process_clearance.json'),'registration_sha256':sha(AC/'registration.json'),
 'public_terminal_manifest_sha256':sha(ROOT/'results/visibility_flash_gradient_20261014/manifest.json'),'registered_science_ids':546,'all_explicitly_disjoint':True},
 'coverage':{'NPZ_paths':73060,'unchanged_from_candidate':72897,'new_or_modified':163,'new_seed_members_read':158,'whole_block_overlaps':0,'new_NPZ_errors':0,'JSON_errors':0,
 'JSON_matches':16,'JSON_classification':'Prior AC block125 exclusive upper endpoint only','text_matches':7,'text_delta':'Same seven exact lines as classified candidate text matches; search output order differs','text_sha256':sha(OUT/'final_text_matches.txt'),
 'baseline_fixture_errors':'The16 earlier AC synthetic JSON-under-NPZ artifacts remain explicitly classified by the pinned candidate review; no new errors.'},
 'validation_source_pins':{str((STUDY/n).relative_to(ROOT)):sha(STUDY/n) for n in ('contracts.py','validate.py','production_identity.py')},
 'stage_mapping_review_sha256':source_sha,'required_before_release':['Root registration','One authorized retained-input preparation','Independent exact prepared source/input and analyzer review','Published preparation and root ready marker'],
 'new_lives':0,'new_compilations':0,'genotypes_copied_or_generated':0}
seed_sha=save('seed_audit.json',seed_receipt)
final={'status':'passed','seed_audit_sha256':seed_sha,'independent_source_review_sha256':source_sha,'seeds_counts':{k:len(v) for k,v in seeds.items()},
 'final_delta_sha256':sha(OUT/'final_namespace_delta.json'),'AC_public_manifest_sha256':sha(ROOT/'results/visibility_flash_gradient_20261014/manifest.json'),
 'actual_overlaps':[],'new_errors':[],'registered':False,'reserved':False,'source_only':True}
print(json.dumps(final,indent=2));save('final_namespace_review.json',final)
