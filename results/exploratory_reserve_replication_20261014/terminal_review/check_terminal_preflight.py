"""Source/resource-only terminal AI preflight; no engine or outcome inspection."""
from pathlib import Path
import hashlib,json
ROOT=Path(__file__).resolve().parents[2]
A=Path(__file__).resolve().parent
S=ROOT/'outputs/autonomous_exploratory_reserve_replication_20261014'
P=ROOT/'results/exploratory_reserve_replication_20261014'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
read=lambda p:json.loads(p.read_text())
BUDGET='e8e7f316d8f28d883793d8d0e9e9b0201c57d62bab3f7eae395e88658c4e098d'
CLEAR='487a9373fd036fe5589f8c29fb276809fdb4bdb1902b2cc9bc2769eb72450d01'
PRE='369766d764fec89120c61558ea688b34490b9d31d3afc6a73b16eca8541c854a'

def main():
    if BUDGET is None or CLEAR is None:
        raise ValueError("root terminal pins are unset; do not inspect a running attempt")
    assert sha(S/'budget.json')==BUDGET and sha(S/'terminal_process_clearance.json')==CLEAR
    assert sha(P/'prelaunch/manifest.json')==PRE
    b=read(S/'budget.json');c=read(S/'terminal_process_clearance.json');r=read(S/'ready.json');m=read(P/'prelaunch/manifest.json')
    assert b['status']=='complete' and b['exit_code']==0 and not b['running'] and not b['queued'] and not b.get('cleanup_error')
    assert b['cpu_seconds']<=b['cap_cpu_seconds']==5400 and b['search_stage_cpu_seconds']<=3400
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
    assert len(mapping)==210 and len(r['production_pins'])==35 and len(m['artifacts'])==331
    receipt={'status':'passed_terminal_source_resource_preflight','budget_sha256':BUDGET,'clearance_sha256':CLEAR,'ready_sha256':sha(S/'ready.json'),'prelaunch_manifest_sha256':PRE,'prepared_artifacts_preserved':331,'released_local_pins_unchanged':210,'released_production_pins_unchanged':35,'cpu_seconds':b['cpu_seconds'],'search_stage_cpu_seconds':b['search_stage_cpu_seconds'],'confirmation_cpu_seconds':b['cpu_seconds']-b['search_stage_cpu_seconds'],'cap_cpu_seconds':5400,'recorded_identities_checked_gone':len(identities),'owned_groups_checked_gone':len(c['process_groups']),'script_sha256':sha(Path(__file__)),'simulation_calls':0,'compiled_libraries':0,'scientific_outcomes_read':False}
    (A/'terminal_preflight.json').write_text(json.dumps(receipt,indent=2)+'\n')
    (A/'actual_ready_mapping_review.json').write_text(json.dumps({'status':'passed','ready_sha256':sha(S/'ready.json'),'prelaunch_manifest_sha256':PRE,'source_pin_archive_paths':mapping,'local_count':210,'production_count':35,'all_prelaunch_bytes_unchanged':True},indent=2)+'\n')
    print(json.dumps(receipt,indent=2))

if __name__ == "__main__":
    import argparse
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check",action="store_true")
    if parser.parse_args().check:
        main()
    else:
        print(json.dumps({"status":"dry_run_no_runtime_reads","writes":False,"requires":"root terminal budget and clearance pins"}))
