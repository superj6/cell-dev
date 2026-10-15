"""Narrow AF-to-AH offline terminal recount adaptation; source only."""
from pathlib import Path
import ast
import hashlib
import json
B=Path(__file__).resolve().parent
SOURCE=B.parent/'audit_prediction_continuation_20261014/review_terminal.py'
TARGET=B/'review_terminal.py'
assert not TARGET.exists()
s=SOURCE.read_text().replace('Independent AF terminal','Independent AH terminal')
s=s.replace('ebdc3f37dc5d9a882b2b7d68ed3913a08540be4f476bdd6cf4b6c446e315b5e0','0a9e505969ed11cd8f240f9404bbff2adf9a91d91d5387252fd9595874c61be4')
s=s.replace('LABELS = ("AE_D90", "AE_L92", "AF_D90", "AF_L92")','LABELS = ("AE_L92", "AH_control", "AH_reserve")')
s=s.replace('BACKGROUNDS = ("D90", "L92")','BACKGROUNDS = ("L92",)\nPAIRS = {"primary": ((2, 1),), "gain": ((1, 0), (2, 0))}')
s=s.replace('workers = ["evolve_s" + str(seed) for seed in p["runs"]] + ["confirmation"]','workers = ["evolve_" + run for run in p["runs"]] + ["confirmation"]')
s=s.replace('10316','9804').replace('10322','9810').replace('2048','1536').replace('146','219')
s=s.replace('genomes.shape == (4, 875)','genomes.shape == (3, 875)')
s=s.replace('    for i, seed in enumerate(p["runs"]):\n        key = str(seed)\n        folder = base / f"runs/s{seed}"\n        founder = read(base / p["reference_files"][i])["params"]',
'''    for i, key in enumerate(p["runs"]):
        folder = base / "runs" / key
        founder = read(base / p["reference_files"][0])["params"]''')
s=s.replace('same(original, genomes[i]) and raw(original) == p["founder_mapping"][key]["raw_sha256"]','same(original, genomes[0]) and raw(original) == p["founder_mapping"]["L92"]["raw_sha256"]')
s=s.replace('        check(read(folder / "determinism.json") == numeric, "native numerical receipt differs")',
'''        configured = {"mode": key, "policy": p["reserve_policy"],
            "policy_sha256": hashlib.sha256(json.dumps(p["reserve_policy"],sort_keys=True,separators=(",",":"),allow_nan=False).encode()).hexdigest(),
            "source_pins": {name:p["file_pins"][name] for name in ("reserve_adapter.py","search.py")}}
        check(read(folder / "determinism.json") == dict(numeric,external_selection=configured), "extended native numerical receipt differs")''')
s=s.replace('            binding["generation"] == 4','            binding["selection_identity"] == configured\n            and binding["generation"] == 4')
s=s.replace('genomes[i + 2]','genomes[i + 1]')
needle='        native[key] = {\n'
insert='''        lines = [json.loads(line) for line in (folder/"lineage.jsonl").read_text().splitlines() if line.strip()]
        check(len(lines)==5, "complete founder/four-generation policy logs required")
        decisions = checked["selection"]["policy_decisions"]
        check(len(decisions)==4 and checked["selection"]["tie_ranking_calls_replayed"]==12,
              "complete policy tie replay receipt required")
        for generation,(line,decision) in enumerate(zip(lines[1:],decisions)):
            item=line["exploratory_reserve"]
            active=key=="reserve" and generation<3
            check(item["mode"]==key and item["generation"]==generation and item["active"]==active
                  and item["policy_sha256"]==configured["policy_sha256"], "policy lineage identity differs")
            check([r["size"] for r in item["ranking_calls"]]==[256,256,64]
                  and [len(r["fitness"]) for r in item["ranking_calls"]]==[256,256,64], "complete rank input coverage")
            check(decision["generation"]==generation and decision["active"]==active
                  and decision["ranking_calls_exact"]==3 and decision["protected_ids"]==item["reserve_ids"]
                  and len(item["reserve_ids"])==(2 if active else 0), "reader policy replay binding differs")
        check(checked["selection"]["genetic_random_draws"]==0 and checked["selection"]["simulation_calls"]==0,
              "offline policy audit executed forbidden work")
'''
s=s.replace(needle,insert+needle)
s=s.replace('            "full_reader_genetic_replay": checked["genetic_replay"],','            "full_reader_genetic_replay": checked["genetic_replay"],\n            "full_reader_policy_replay": checked["selection"],')
needle='    folder = base / "confirmation"\n    index = read(folder / "row_index.json")'
insert='''    first=summary["native_audit"]["matched_first_cohort"]
    check(summary["native_audit"]["first_base_F_bitwise_equal"] is True and
          first["candidate_shape"]==[256,875] and first["candidate_dtype"]=="float32" and
          len(first["row_raw_sha256"])==256, "full first-cohort replay receipt differs")
    claimed=endpoint["matched_first_cohort"]
    check(claimed["initial_population_raw_sha256"]==first["initial_raw_sha256"] and
          claimed["recorded_genetics_sha256"]==hashlib.sha256(json.dumps(first["signature"],sort_keys=True).encode()).hexdigest()
          and claimed["initial_rows"]==32 and claimed["candidate_count"]==256 and
          claimed["offspring_count"]==224 and claimed["base_F_exact"] is True,
          "first-cohort producer/replay binding differs")
'''
s=s.replace(needle,insert+needle)
s=s.replace('range(4)','range(3)').replace('"four complete rows required"','"three complete rows required"')
# Restore generation loops with four generations; only the new explicit range is absent, old source uses literals.
a=s.index('    check(\n        set(summary["contrasts"]) == {"primary"}')
b=s.index('    stored = npz(',a)
old=s[a:b]
start=old.index('        delta = ')
body=old[start:]
body=body.replace('summary["contrasts"]["primary"]','summary["contrasts"][category]')
body=body.replace('report["primary"]','report[category]')
body=body.replace('"primary__" + LABELS[a]','category + "__" + LABELS[a]')
body=body.replace('compact[LABELS[a]]','compact[category+"__"+LABELS[a]]')
new='''    check(set(summary["contrasts"])==set(PAIRS), "exact contrast categories differ")
    vectors, compact = {}, {}
    for category,pairs in PAIRS.items():
        check(set(summary["contrasts"][category])=={LABELS[a] for a,b in pairs}
              and set(report[category])=={LABELS[a] for a,b in pairs}, "exact contrast roles differ")
        for a,b in pairs:
'''+''.join('    '+line+'\n' for line in body.rstrip().splitlines())
s=s[:a]+new+s[b:]
s=s.replace('    resource = summary["resources"]',
'''    behavioral=summary["primary_behavioral_estimate"]
    check(behavioral["contrast"]=="AH_reserve_minus_AH_control" and behavioral["metric"]=="captures", "primary behavioral label differs")
    check_stats(behavioral, rows[2]["captures"]-rows[1]["captures"])
    resource = summary["resources"]''')
s=s.replace('"raw_rows": 4','"raw_rows": 3')
s=s.replace('"primary_contrasts": compact','"all_three_contrasts": compact')
s=s.replace('"Native full checkpoint/genetic replay is supplied by the frozen reader and its separately repeated terminal audit; this helper rechecks source/count/log/endpoint and health receipts."','"Native full checkpoint/genetic/policy replay is supplied by the frozen reader and its separately repeated terminal audit; this helper rechecks source/count/log/endpoint/rank-coverage and health receipts."')
TARGET.write_text(s)
oldtree,newtree=ast.parse(SOURCE.read_text()),ast.parse(s)
f=lambda t:next(n for n in t.body if isinstance(n,ast.FunctionDef) and n.name=='physical')
assert ast.dump(f(oldtree))==ast.dump(f(newtree))
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
record={'status':'source_only_prepared_not_executed','original_literal_accounting_source':str(SOURCE.relative_to(B.parents[1])),
        'original_sha256':sha(SOURCE),'script_sha256':sha(TARGET),
        'physical_function_AST_identical_to_completed_AF_verifier':True,
        'raw_rows':3,'raw_lives':1536,'research_lives':9804,'startup_goldens':6,'total_calls':9810,'paired_vectors':219,
        'runtime_artifacts_opened':0,'scientific_outcomes_read':False,'simulation_calls':0,'compilation_calls':0,
        'requires':'Exact root terminal-clearance SHA and explicit --run; separate frozen reader replay after terminal.'}
(B/'terminal_verifier_preparation.json').write_text(json.dumps(record,indent=2)+'\n')
print(json.dumps(record,indent=2))
