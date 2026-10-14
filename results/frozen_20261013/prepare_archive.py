"""Archive E's preparation and validation without creating ready.json or running scientific lives."""
from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
STUDY = ROOT / 'outputs/autonomous_frozen_20261013'
OUT = ROOT / 'results/frozen_20261013'
PRIOR = ROOT / 'results/pool_mutants_20261013'
DEPENDENCY = ROOT / 'outputs/autonomous_continuation_20261013'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text())


def write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, allow_nan=False) + '\n')


def main():
    manifest = read(STUDY / 'validation_smoke/manifest.json')
    smoke = read(STUDY / 'validation_smoke/validation.json')
    assert smoke['status'] == 'complete' and smoke['genome_lives'] == 16 and smoke['validation_only']
    assert sha(ROOT / 'scripts/taskvar_frozen_gain.py') == manifest['runner_sha256']
    for name, expected in manifest['helpers'].items():
        assert sha(ROOT / 'scripts' / name) == expected, name
    for name, expected in manifest['numerical_identity']['sources'].items():
        assert sha(ROOT / name) == expected, name
    ready = {'monitor_sha256': sha(STUDY / 'run_budgeted.py'), 'runner_sha256': manifest['runner_sha256'],
             'helpers': manifest['helpers'], 'source_identity': manifest['numerical_identity']['sources'],
             'dependency': {'monitor_sha256': sha(DEPENDENCY / 'run_budgeted.py'),
                            'protocol_sha256': sha(DEPENDENCY / 'protocol.json')},
             'validated_scientific_runner_commit': '7462bbf894734a11fff3e2545a0195703d179207'}
    # Preparation is not launch release. Root may copy this to ready.json after review/commit.
    write(STUDY / 'ready.template.json', ready)
    protocol_text = (ROOT / 'results/taskvar/prereg.md').read_text()
    excerpt = protocol_text.split('### E. Lateral dependence with tissue held fixed (2026-10-13)', 1)[1]
    excerpt = excerpt.split('\n### ', 1)[0]
    (STUDY / 'protocol_excerpt.md').write_text('# E. Lateral dependence with tissue held fixed\n' + excerpt)
    protocol = {'status': 'prepared_not_released', 'scientific_genome_lives': 4096, 'validation_genome_lives': 16,
        'seed_block': 92, 'seeds': list(range(51_920_000, 51_920_512)), 'T': 1536, 'fork': 768,
        'accounting_open': 800, 'window': 736, 'genotypes': ['original_s5', 'fixed_s5_row38'],
        'genome_sha256': manifest['genome_sha256'], 'conditions': ['normal','freeze','lateral_off','freeze+lateral_off'],
        'worlds': manifest['worlds'], 'max_cpu_seconds': 3600, 'workers': 2,
        'primary': '(winner-parent)freeze - (winner-parent)freeze+lateral_off, paired before mean/SE',
        'working_directory': 'outputs/autonomous_frozen_20261013',
        'preregistration': 'results/taskvar/prereg.md#e-lateral-dependence-with-tissue-held-fixed-2026-10-13',
        'preregistration_sha256_at_preparation': sha(ROOT / 'results/taskvar/prereg.md'),
        'source_commit': ready['validated_scientific_runner_commit'],
        'dependency': 'Wait until continuation queue is empty and at most one two-worker job remains.',
        'budget': 'Monitor sends TERM at3588 CPU-s, waits at most2wall-s, then KILL; child RLIMIT_CPU soft3599/hard3600.',
        'settling_bounds': {'claim_resolution_before': 768.25, 'presence_notices_before': 768.75,
            'prefork_spike_delivery_before': 771.003, 'note': 'Prior dynamic state is not erased.'},
        'limitations': ['Different genotypes retain different tissue footprints.',
            'Freeze changes computation by fixing genes, phenotype and effective weights.',
            'Chemical transport and membrane/receptor/spike dynamics continue.',
            'Newborns from prior claims initialize normally, then all future ticks inherit active freeze.',
            'No adult maturity, novel circuit, or matched-footprint claim follows from this contrast.']}
    write(STUDY / 'protocol.json', protocol)
    files = {}
    def keep(source, relative):
        destination = OUT / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
        files[str(relative)] = {'sha256': sha(destination), 'bytes': destination.stat().st_size}
    for name in ('README.md','run_budgeted.py','test_run_budgeted.py','prepare_archive.py','ready.template.json',
                 'protocol.json','protocol_excerpt.md'):
        keep(STUDY / name, name)
    keep(STUDY / 'monitor_validation.json', 'validation/monitor_validation.json')
    keep(ROOT / 'tests/test_taskvar_frozen_gain.py', 'tests/test_taskvar_frozen_gain.py')
    for name in ('taskvar_frozen_gain.py', *manifest['helpers']):
        keep(ROOT / 'scripts' / name, Path('sources') / name)
    for name in ('run_budgeted.py','protocol.json','ready.json'):
        keep(DEPENDENCY / name, Path('dependency') / name)
    for relative, expected in manifest['prior_artifacts'].items():
        assert sha(PRIOR / relative) == expected, relative
        keep(PRIOR / relative, Path('inputs/prior') / relative)
    for path in sorted((STUDY / 'validation_smoke').rglob('*')):
        if path.is_file() and path.name in ('manifest.json','report.json','validation.json','genotypes.npz','scores.npz'):
            keep(path, Path('validation/smoke') / path.relative_to(STUDY / 'validation_smoke'))
    write(OUT / 'provenance.json', {'status':'preparation_archive', 'simulated_lives_by_export':0,
        'numerical_identity':manifest['numerical_identity'],'artifacts':files})
    print(json.dumps({'status':'prepared','out':str(OUT),'hashed_artifacts':len(files),
                      'ready_json_created':False,'simulated_lives':0},indent=2))


if __name__ == '__main__':
    main()
