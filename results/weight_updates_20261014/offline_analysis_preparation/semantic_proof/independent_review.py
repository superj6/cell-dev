"""Record an independent read-only source review; no lives or O outcome access."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


p = json.loads((HERE / 'source_proof.json').read_text())
for relative, digest in p['source_sha256'].items():
    assert sha(ROOT / relative) == digest
assert sha(HERE / 'COMBINED_CLAMP_SOURCE_AUDIT.md') == p['proof_sha256']
result = {
    'status': 'passed', 'reviewer': 'audit_de independent read-only source review',
    'simulated_lives': 0, 'O_outcomes_read': False,
    'source_proof_sha256': sha(HERE / 'source_proof.json'),
    'proof_sha256': p['proof_sha256'], 'source_sha256': p['source_sha256'],
    'review_script_sha256': sha(Path(__file__)),
    'checks': [
        'C204 and F16 skip identical GRN, phenotype, new division and apoptosis branches; only derive differs.',
        'derive writes sd and weff; sd only feeds disabled division, while arrivals use current weff.',
        'GRN mode theta is unchanged; no modeled GRN/readout/derive computation fee exists.',
        'Claims copy daughter genes at send; resolution never rereads mother. Birth decodes/derives in both arms.',
        'Pre-fork partition follows theta decode, so identity_clamp alone can reset phenotype after fork.',
        'C/F preserve local chemistry, contact updates, membrane and spike paths; feedback can propagate differences.',
        'Reference implementation flag paths agree with C; POOL kill/stuck defaults are disabled.',
        'Bounded tick/spike/claim/notice timing is below800; old state and early causal changes persist.',
        'Complete matched-triplet structural checks exclude guards only from checks, never fitness.',
    ],
    'interpretation': 'Conditional ongoing effective receive-weight update effect from local chemical/contact state, '
                      'including early transient carryover and subsequent feedback; not pure memory or learning.',
    'limitations': ['No simulation validates a new parameter regime; existing fixed physics is reused.',
                    'No event-hash, host-CPU or cross-genotype footprint equality is claimed.'],
}
(HERE / 'source_proof_review.json').write_text(json.dumps(result, indent=2) + '\n')
print(json.dumps({'status': result['status'], 'sha256': sha(HERE / 'source_proof_review.json')}))
