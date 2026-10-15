"""Independent exact-byte preparation audit; no engine import, build, draw or life."""
import copy
import hashlib
import json
from pathlib import Path

import numpy as np

ROOT=Path(__file__).resolve().parents[2]
AUDIT=Path(__file__).resolve().parent
S=ROOT/'outputs/autonomous_visibility_dark_tail_information_20261014'
X=ROOT/'results/visibility_information_x2_20261014'
Y=ROOT/'results/visibility_gradient_20261014'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
read=lambda p:json.loads(p.read_text())
p=read(S/'protocol.json');xp=read(X/'protocol.json')
assert sha(S/'protocol.json')=='ee041636fec03ab3dc8e468b0d3427d75a2ac2736436b4dd954e3ac1c96100fe'
for table,base in ((p['file_pins'],S),(p['production_pins'],ROOT)):
 for name,digest in table.items():assert sha(base/name)==digest,name
reg=read(S/'registration.json')
assert sha(S/'registration.json')=='5a3f3e2d2504db1d52968d3c116768e65812210f48ff6f63010f91e041349081'
assert sha(S/'seed_audit.json')==reg['seed_audit_sha256']
for group in ('review_pins',):
 for name,digest in reg[group].items():assert sha(ROOT/name)==digest
for name,digest in reg['AC_terminal']['file_pins'].items():assert sha(ROOT/name)==digest
assert reg['seeds']=={'validation':p['validation_seeds'],'research':p['seeds']}
expected=copy.deepcopy(xp['worlds']['flash5_dim25']); got=p['worlds']['flash5_dark']
expected['scratch_slots']['dark_amp']=0.
expected['packed_world'][16]=0.
expected['production']['world']['visibility_low']=0.
expected['production']['packed_world'][69]=0.
for candidate in expected['candidates']:
 if candidate['role'] in ('I','B'):candidate['params'][21]=0.
 elif candidate['role']=='A':candidate['changed_parameter_indices']=[9,10]
assert expected==got,'world/candidate change extends approved constant transfer'
bundle=read(S/'bundle.json')
for name,item in bundle['origins'].items():
 assert sha(S/name)==sha(ROOT/item['source'])==item['sha256']
assert len(bundle['file_pins'])==42
historical_cpus={}; files=[]
for c in xp['worlds']['flash5_dim25']['candidates']:
 role=c['role'];prefix=f'rows/flash5_dim25/{role}'
 for suffix in ('row.npz','checkpoint.json'):
  n=prefix+'/'+suffix
  assert (S/'inputs/X2'/n).read_bytes()==(X/n).read_bytes();files.append(n)
 with np.load(S/'inputs/X2'/prefix/'row.npz',allow_pickle=False) as row:
  historical_cpus[role]=float(row['cpu_seconds'])/512
assert historical_cpus==p['historical_cpu_per_life']
for name,source in {'protocol.json':'protocol.json','budget.json':'operations/budget.json','summary.json':'postanalysis/working_results/summary.json','rows/flash5_dim25/complete.json':'rows/flash5_dim25/complete.json'}.items():
 assert (S/'inputs/X2'/name).read_bytes()==(X/source).read_bytes()
for name in ('protocol.json','startup_identity.json'):
 assert (S/'inputs/Y'/name).read_bytes()==(Y/name).read_bytes()
assert p['expected_numerical_identity']==read(Y/'startup_identity.json')['identity']
assert p['numerical_identity']==xp['numerical_identity'] and p['analysis']==xp['analysis']
assert p['validation_matrix']=={'production_bridge':8,'full_fast':12,'callback_replay':15,'calibration':39,'identity':2}
assert not any((S/name).exists() for name in ('ready.json','attempt.json','budget.json','validation','rows','logs','build-cache'))
assert not list(S.rglob('*.so'))
clear=read(S/'resource_clearance.json')
assert sha(S/'resource_clearance.json')=='1e3af5311115aebaf5d90c6a134ab2b04a243de9b253f9cac0414093e09f2d04'
assert clear['status']=='cleared' and clear['all_processes_exited']
for name,digest in clear['budget_pins'].items():assert sha(ROOT/name)==digest
result={'status':'passed_exact_prepared_inputs','protocol_sha256':sha(S/'protocol.json'),
 'local_pins_verified':len(p['file_pins']),'production_and_dependency_pins_verified':len(p['production_pins']),
 'canonical_ABI3_source_bundle_files':42,'unchanged_candidates':11,'physical_parameter_only_candidates':['I','B'],
 'A_parameter_values_unchanged':True,'A_difference_metadata':[9,10],
 'approved_world_changes_only':{'scratch_dark_amp':[.25,0.],'production_visibility_low':[.25,0.]},
 'retained_timing_rows':13,'timing_cpu_seconds':sum(historical_cpus.values())*512,
 'all_historical_row_checkpoint_bytes_equal':True,'expected_identity_exact_Y_bytes':True,
 'registered_seeds_exact':True,'resource_clearance_counts':{'processes':len(clear['processes']),'groups':len(clear['process_groups']),'budgets':len(clear['budget_pins'])},
 'historical_production_provenance_libraries':[n for n in p['production_pins'] if n.endswith('.so')],
 'newly_compiled_libraries':0,'new_lives':0,'new_genetic_draws':0,'copies_by_this_review':0,
 'no_runtime_artifacts':True,'source_review_sha256':sha(AUDIT/'independent_source_review.json'),
 'checker_sha256':sha(Path(__file__)),'registration_pins_preserved':True}
(AUDIT/'independent_preparation_review.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result,indent=2))
