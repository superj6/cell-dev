"""Root acceptance of actual AI source/namespace receipts; no engine imports or draws."""
from pathlib import Path
import hashlib
import json

AUDIT = Path(__file__).resolve().parent
ROOT = AUDIT.parents[1]
STUDY = ROOT / 'outputs/autonomous_exploratory_reserve_replication_20261014'

def read(p):
    return json.loads(p.read_text())

def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()

fixed = {
    'producer_source_review.json': ('source_only_reviewed_unregistered', 'f0260f2f7124d6e56250f1a7c1a103723fe73159aa14edb1c0a1309a13c49f75'),
    'reader_source_review.json': ('source_only_reader_complete_pending_producer_peer', '5ad8d788c2e325c6144f0b521689f3a5caf8c0349b1c6e443823f7fb91e9c4a2'),
    'analyzer_peer_review.json': ('approved_source_only', '95daafee52f35d6a7a34c36c97b33d38cc41ea8a8d394f5ec2ac0cbfbde462fa'),
    'producer_interface_review.json': ('passed_source_only_producer_reader_interface_review', 'b1d583cf487dde633d7a37520832c1831dbaf71519a03aafc1820c3bec260621'),
    'historical_cost_review.json': ('passed_source_only', '814b15c01d7aa656a97dde37e15f29a5a31d663dd5b6aec0f03f1b4b60d58263'),
    'independent_source_design_review.json': ('approved_source_only_unregistered', '040455be7c47c19c0ef11a7220bb4892da4691ded34ae01916cf1c9227db9f81'),
    'root_helper_source_review.json': ('passed_source_only', 'bede3a24b220882cde5eac75c13abefc469689c769ca78b63719c84ab727de12'),
    'root_helper_independent_review.json': ('passed_source_only_root_helper_review', 'b61b70ab398ff5610a77414d9df833b8e99f79c2683f3ee22230eb1ff82d8be6'),
    'root_helper_review_recovery.json': ('exact_original_recovered', 'fe28229c430b7b740abff072db3f9956fe1bbbae60f66f050acdfa6c4e4ba358'),
    'namespace/candidate_namespace_review.json': ('passed_candidate_pending_final_delta', 'bd7cf69bf0e87e8c823cb0d084859448032784462ce4b80fec298b8606385b9b'),
}
# The final namespace digests are supplied only after the reviewer completes the last inventory delta.
last = read(AUDIT / 'final_namespace_acceptance.json')
assert last['status'] == 'accepted_by_root'
for name, digest in last['pins'].items():
    assert name in ['namespace/final_namespace_delta.json', 'namespace/seed_audit.json']
    fixed[name] = ('passed', digest)
assert len(fixed) == 12
reviews, pins = {}, {}
for name, (status, digest) in fixed.items():
    p = AUDIT / name
    assert sha(p) == digest, name
    d = read(p)
    assert d['status'] == status, (name, d['status'])
    assert not d.get('blockers') and not d.get('findings'), name
    reviews[name] = d
    pins[str(p.relative_to(ROOT))] = digest
producer = reviews['producer_source_review.json']['source_pins']
reader = reviews['reader_source_review.json']['reader_sources']
assert len(producer) == 14 and len(reader) == 6
for name, digest in producer.items():
    assert sha(STUDY / name) == digest, name
for name, digest in reader.items():
    assert sha(AUDIT / 'analysis' / name) == digest, name
peer = reviews['analyzer_peer_review.json']
assert peer['reader_sources'] == reader
for name, digest in peer['producer_sources'].items():
    assert producer[name] == digest, name
interface = reviews['producer_interface_review.json']
assert interface['producer_source_pins'] == producer
for name, digest in interface['reader_source_pins'].items():
    assert reader[name] == digest, name
assert reviews['independent_source_design_review.json']['producer_source_pins'] == producer
assert reviews['reader_source_review.json']['protocol_sha256'] is None
accepted = {
    'status': 'accepted_by_root', 'review_pins': pins,
    'producer_source_pins': producer, 'reader_source_pins': reader,
    'reader_protocol_bound': False,
    'seed_audit_sha256': sha(AUDIT / 'namespace/seed_audit.json'),
    'scientific_scope': 'one_independent_replication_four_generation_pair_two_fresh_reserves',
    'prior_published_milestone': 'b46aca978005cef6b50edafef4b8287f445c0824',
    'simulation_calls': 0, 'genetic_draws': 0,
}
with (AUDIT / 'registration_review_acceptance.json').open('x') as stream:
    stream.write(json.dumps(accepted, indent=2) + '\n')
print(json.dumps({'status': 'accepted_by_root', 'reviews': len(pins),
                  'producer_files': len(producer), 'reader_files': len(reader)}))
