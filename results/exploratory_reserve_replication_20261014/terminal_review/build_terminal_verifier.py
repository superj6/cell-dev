"""Source-only AH-to-AI terminal verifier adaptation; no study artifacts opened."""
from pathlib import Path
import ast
import hashlib
import json
B=Path(__file__).resolve().parent
SOURCE=B.parent/'audit_exploratory_reserve_20261014/review_terminal.py'
TARGET=B/'review_terminal.py'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
assert sha(SOURCE)=='850671f8057d9100e398a0d07489ad88053ab9d81c1ca6e8883a960e4ad0d006'
assert not TARGET.exists()
replacements=[
 ('Independent AH terminal','Independent AI terminal'),
 ('0a9e505969ed11cd8f240f9404bbff2adf9a91d91d5387252fd9595874c61be4',
  '0dc385199dc871a86f7a31a62c393b2c160f0cbae018ceece3ec8f51bb6dff00'),
 ('AH_control','AI_control'),('AH_reserve','AI_reserve')]
source=SOURCE.read_text()
for old,new in replacements:
    assert old in source
    source=source.replace(old,new)
oldtree,newtree=ast.parse(SOURCE.read_text()),ast.parse(source)
for node in ast.walk(newtree):
    if isinstance(node,ast.Constant) and isinstance(node.value,str):
        for old,new in replacements:node.value=node.value.replace(new,old)
assert ast.dump(oldtree)==ast.dump(newtree)
with TARGET.open('x') as f:f.write(source)
record={'status':'source_only_prepared_not_executed',
        'original_literal_accounting_source':str(SOURCE.relative_to(B.parents[1])),
        'original_sha256':sha(SOURCE),'script_sha256':sha(TARGET),
        'allowed_literal_replacements':replacements,
        'entire_module_AST_identical_after_metadata_normalization':True,
        'full57_ledger_arithmetic_unchanged':True,
        'raw_rows':3,'raw_lives':1536,'research_lives':9804,
        'native_search_lives':8268,'startup_goldens':6,'total_calls':9810,'paired_vectors':219,
        'max_cpu_seconds':5400,'search_cpu_seconds':3400,'confirmation_reserved_cpu_seconds':2000,
        'runtime_artifacts_opened':0,'scientific_outcomes_read':False,
        'simulation_calls':0,'compilation_calls':0,'fresh_genetic_draws':0,
        'requires':'Explicit root terminal-clearance SHA, --run and complete canonical summary; separately rerun the frozen reader after root clearance for full genetic/policy replay.'}
with (B/'terminal_verifier_preparation.json').open('x') as f:f.write(json.dumps(record,indent=2)+'\n')
print(json.dumps(record,indent=2))
