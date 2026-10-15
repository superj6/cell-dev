"""Install the reviewed AI analysis package byte-exact; no scientific computation."""
from pathlib import Path
import hashlib
import json
B=Path(__file__).resolve().parent
S=B.parent/'autonomous_exploratory_reserve_replication_20261014'
A=B/'analysis'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
peer=json.loads((B/'bound_analyzer_peer_review.json').read_text())
assert peer['status']=='approved_bound_reader_prepared_unreleased'
assert peer['bound_reader_sha256']==sha(A/'analyze.py')
assert peer['protocol_sha256']==sha(S/'protocol.json')
assert not (S/'analysis').exists() and not (S/'analysis_pins.json').exists()
paths={str(p.relative_to(A)):p for p in sorted(A.rglob('*')) if p.is_file() and '__pycache__' not in p.parts}
for name in ('reader_adaptation_plan.json','reader_source_origins.json','reader_source_review.json',
             'analyzer_peer_review.json','analysis_review.json','bound_analyzer_peer_review.json',
             'actual_input_verification.json','initialization_replay.json','verify_preparation.py',
             'binding_source_record.json','bound_execution_command.json','bound_execution_stdout.json',
             'bound_execution_stderr.txt','bound_execution_review.json',
             'reader_tests.log','reader_tests.xml','reader_tests_final.log','reader_tests_final.xml',
             'reader_lint.txt','reader_lint_final.txt'):
    paths[name]=B/name
for name,source in paths.items():
    target=S/'analysis'/name
    target.parent.mkdir(parents=True,exist_ok=True)
    with target.open('xb') as f:f.write(source.read_bytes())
    assert sha(target)==sha(source)
pins={str((S/'analysis'/name).relative_to(S)):sha(S/'analysis'/name) for name in sorted(paths)}
with (S/'analysis_pins.json').open('x') as f:f.write(json.dumps(pins,indent=2)+'\n')
record={'status':'installed_frozen_unreleased','protocol_sha256':sha(S/'protocol.json'),
        'analysis_pins_sha256':sha(S/'analysis_pins.json'),'files':len(pins),
        'bytes':sum((S/name).stat().st_size for name in pins),
        'bound_peer_sha256':sha(B/'bound_analyzer_peer_review.json'),
        'all_copies_byte_exact':True,'simulation_calls':0,'compilation_calls':0,'fresh_genetic_draws':0}
with (B/'canonical_installation.json').open('x') as f:f.write(json.dumps(record,indent=2)+'\n')
print(json.dumps(record,indent=2))
