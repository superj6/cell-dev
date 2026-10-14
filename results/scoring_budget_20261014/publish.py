"""Publish reviewed S preparation, deliberately held at the user's wrap-up request; no release or lives."""
import hashlib
import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WORK = Path(__file__).resolve().parent
PUBLIC = ROOT / 'results/scoring_budget_20261014'
AUDIT = ROOT / 'outputs/audit_s_20261014'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text())


for name in ('ready.json', 'budget.json', 'references', 'references.pending', 'runs', 'confirmation'):
    if (WORK / name).exists():
        raise ValueError('S must remain unlaunched and unfrozen at user-requested hold: ' + name)
protocol = read(WORK / 'protocol.json')
review = read(AUDIT / 'science_review.json')
assert review['status'] == 'passed' and review['combined_tests_passed'] == 103
for relative, expected in review['sha256'].items():
    assert sha(WORK / relative) == expected, relative
files = {name: WORK / name for name in ('PREREG.md', 'protocol.json', 'prepare.py', 'measure.py',
         'run_budgeted.py', 'test_prepared.py', 'test_monitor.py', 'seed_audit.json', 'initialization.json', 'publish.py')}
for folder in ('configs', 'inputs', 'initialization', 'sources'):
    files.update({str(path.relative_to(WORK)): path for path in (WORK / folder).rglob('*')
                  if path.is_file() and '__pycache__' not in path.parts and path.suffix != '.pyc'})
for relative, expected in protocol['source_identity'].items():
    assert sha(ROOT / relative) == expected
    files['sources/' + relative] = ROOT / relative
for name, expected in protocol['helpers'].items():
    path = ROOT / 'scripts' / name
    assert sha(path) == expected
    files['sources/scripts/' + name] = path
for relative, expected in protocol['template_pins'].items():
    assert sha(ROOT / relative) == expected
    files['templates/' + relative] = ROOT / relative
for relative, pins in protocol['dependencies'].items():
    for name, expected in pins.items():
        path = ROOT / relative / name
        assert sha(path) == expected
        files['dependencies/' + Path(relative).name + '/' + name] = path
for name, expected in protocol['P_pins'].items():
    path = ROOT / protocol['P_study'] / name
    assert sha(path) == expected
    files['dependencies/P/' + name] = path
for name in ('science_review.json', 'actual_initialization_review.json', 'monitor_review.json',
             'monitor_validation.json', 'check_final_preparation.py'):
    files['review/' + name] = AUDIT / name
PUBLIC.mkdir(parents=True, exist_ok=True)
for relative, original in files.items():
    destination = PUBLIC / relative
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists() and destination.read_bytes() != original.read_bytes():
        raise ValueError('refuse to overwrite differing public preparation: ' + relative)
    shutil.copyfile(original, destination)
readme = '''# Scoring-budget comparison — prepared and held

**Status: deliberately held at the user's wrap-up request.** No S readiness marker,
reference freezing, budget, search or confirmation exists. This archive registers and
preserves the reviewed design; it is not a result or permission to launch.

S would compare eight generations using six initial plus eight recheck lives with P's
sixteen generations using three plus four. Both branches start from their identical
P initialization: all 32 raw genomes, initial mutation records and genetics RNG states
match exactly. The same fixed D founders and run seeds are retained regardless of P's
outcomes. Both complete P endpoints would be independently audited and frozen together
before either S search.

Each policy spends 16,384 selection genome-lives per branch. This is not equal CPU work:
S has 18,944 T1024-equivalent selection lives in each branch, versus P's 20,480 and
17,920. Fresh block105 confirmation would compare all six fixed D/P/S roles over three
durations and256 shared seeds. The planned total is37,484 research lives, capped at
14,400 cumulative CPU-seconds with at most four search threads; S would wait for R.

The primary effects are S−matched P; all four secondary S/P−D effects and both signs
would remain. Life-level SE describes fixed endpoints, not evolutionary reliability.
The design changes sampling effort and generation count together.

See [PREREG.md](PREREG.md) for the complete prospective scope and limits.
[protocol.json](protocol.json) binds sources, inputs, initialization, namespaces and
configurations. The independent science/source and monitor reviews cover103 pure or
mocked tests. No preparation or test simulated research lives or read active P/Q/R
outcomes.184 P/S seed IDs intentionally overlap, including cross-stage reuse;144 S IDs
are new. Fresh confirmation block105 avoids all audited prior/prepared streams.

Archived scripts preserve their original workspace paths and are not a standalone
launcher from this directory. No readiness file is supplied. Future work must honor
the explicit hold and obtain a new release decision; it cannot infer approval from
this prepared archive.
'''
# Keep simple prose spacing in the public entry point.
for before, after in [('and256', 'and 256'), ('is37,484', 'is 37,484'), ('cover103', 'cover 103'),
                      ('outcomes.184', 'outcomes. 184'), ('reuse;144', 'reuse; 144'), ('block105', 'block 105')]:
    readme = readme.replace(before, after)
(PUBLIC / 'README.md').write_text(readme)
files['README.md'] = PUBLIC / 'README.md'
artifacts = {relative: {'sha256': sha(PUBLIC / relative), 'bytes': (PUBLIC / relative).stat().st_size}
             for relative in sorted(files)}
manifest = {'format': 1, 'status': 'prepared_not_released', 'release_status': 'user_requested_wrap_up_hold',
            'simulated_lives': 0, 'active_P_Q_R_outcomes_read': False,
            'artifacts': artifacts, 'total_artifact_bytes': sum(meta['bytes'] for meta in artifacts.values()),
            'protocol_sha256': sha(PUBLIC / 'protocol.json'), 'source_identity': protocol['source_identity'],
            'planned_research_genome_lives': 37484, 'max_cpu_seconds': 14400, 'max_simulation_threads': 4,
            'pure_or_mock_tests_passed': 103,
            'reference_freezing_status': 'Not executed; requires completed audited P and a future explicit release.'}
(PUBLIC / 'provenance.json').write_text(json.dumps(manifest, indent=2) + '\n')
print(json.dumps({'status': manifest['release_status'], 'artifacts': len(artifacts),
                  'bytes': manifest['total_artifact_bytes'], 'provenance_sha256': sha(PUBLIC / 'provenance.json')}))
