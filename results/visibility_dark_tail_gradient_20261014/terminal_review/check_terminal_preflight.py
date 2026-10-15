"""Source/resource-only terminal AG preflight; no engine or outcome inspection."""
from pathlib import Path
import hashlib,json
ROOT=Path(__file__).resolve().parents[2]
A=Path(__file__).resolve().parent
S=ROOT/'outputs/autonomous_visibility_dark_tail_gradient_20261014'
P=ROOT/'results/visibility_dark_tail_gradient_20261014'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
read=lambda p:json.loads(p.read_text())
BUDGET='932df03fe1f994ec1f3bee9a85c2b3772c380e08489a87f423655863af8d497d'
CLEAR='1154e2910f9276ce66419788f75e182224e953fe8e85ec899725489a6c241a68'
PRE='3133a0e487e75a3053553d42ffcf05f7217453b0144333968570694bb7929103'
assert sha(S/'budget.json')==BUDGET and sha(S/'terminal_process_clearance.json')==CLEAR
assert sha(P/'prelaunch/manifest.json')==PRE
b=read(S/'budget.json');c=read(S/'terminal_process_clearance.json');r=read(S/'ready.json');m=read(P/'prelaunch/manifest.json')
assert b['status']=='complete' and b['exit_code']==0 and not b['running'] and not b['queued'] and not b.get('cleanup_error')
assert b['cpu_seconds']<=b['cap_cpu_seconds']==5400 and b['startup_screen_cpu_seconds']<=3400
assert c['status']=='cleared' and c['all_processes_exited'] and c['budget_sha256']==BUDGET
identities={(x['pid'],x['start_ticks']) for x in b['process_identities']}
assert identities=={(x['pid'],x['start_ticks']) for x in c['processes']}
assert set(c['process_groups'])==set(b['owned_process_groups'])
active=[]
for p in Path('/proc').iterdir():
    if not p.name.isdecimal():continue
    try:
        raw=(p/'stat').read_text();v=raw[raw.rfind(')')+2:].split();pid=int(p.name);start=int(v[19]);group=int(v[2])
    except (OSError,ValueError,IndexError):continue
    if (pid,start) in identities or group in c['process_groups']:active.append((pid,start,group))
assert not active,active
for name,item in m['artifacts'].items():assert sha(P/name)==item['sha256'],name
mapping={}
for name,digest in r['source_pins'].items():
    assert sha(S/name)==digest,name
    origin=str((S/name).relative_to(ROOT))
    targets=[n for n,x in m['artifacts'].items() if x['origin']==origin and x['sha256']==digest]
    assert targets,(name,'missing exact prospective mapping');mapping[name]=targets
for name,digest in r['production_pins'].items():
    assert sha(ROOT/name)==digest and sha(P/'production'/name)==digest,name
assert len(mapping)==232 and len(r['production_pins'])==35 and len(m['artifacts'])==317
receipt={'status':'passed_terminal_source_resource_preflight','budget_sha256':BUDGET,'clearance_sha256':CLEAR,'ready_sha256':sha(S/'ready.json'),'prelaunch_manifest_sha256':PRE,'prepared_artifacts_preserved':317,'released_local_pins_unchanged':232,'released_production_pins_unchanged':35,'cpu_seconds':b['cpu_seconds'],'startup_screen_cpu_seconds':b['startup_screen_cpu_seconds'],'confirmation_cpu_seconds':b['cpu_seconds']-b['startup_screen_cpu_seconds'],'cap_cpu_seconds':5400,'recorded_identities_checked_gone':len(identities),'owned_groups_checked_gone':len(c['process_groups']),'script_sha256':sha(Path(__file__)),'simulation_calls':0,'compiled_libraries':0,'scientific_outcomes_read':False}
(A/'terminal_preflight.json').write_text(json.dumps(receipt,indent=2)+'\n')
(A/'actual_ready_mapping_review.json').write_text(json.dumps({'status':'passed','ready_sha256':sha(S/'ready.json'),'prelaunch_manifest_sha256':PRE,'source_pin_archive_paths':mapping,'local_count':232,'production_count':35,'all_prelaunch_bytes_unchanged':True},indent=2)+'\n')
print(json.dumps(receipt,indent=2))
