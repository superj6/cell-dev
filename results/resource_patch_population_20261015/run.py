"""Release the published development panel and run one bounded owned measurement worker."""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

sys.dont_write_bytecode = True
from common import ROOT, STUDY, checked_protocol, read, save, sha  # noqa: E402


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', action='store_true')
    parser.add_argument('--public-commit')
    args = parser.parse_args()
    if not args.run:
        print('source only: no reservation, release, build or life')
        return
    if args.public_commit is None or len(args.public_commit) != 40:
        raise ValueError('exact prospective publication commit required')
    protocol = checked_protocol()
    public = ROOT / 'results/resource_patch_population_20261015'
    review = read(STUDY / 'reviews/actual_input_review.json')
    if (review['status'] != 'passed' or review['protocol_sha256'] != sha(STUDY / 'protocol.json')
            or sha(public / 'protocol.json') != sha(STUDY / 'protocol.json')
            or sha(public / 'reviews/actual_input_review.json') != sha(STUDY / 'reviews/actual_input_review.json')
            or sha(public / 'run.py') != sha(Path(__file__))):
        raise ValueError('reviewed prospective protocol, input review or launcher differs')
    manifest = read(public / 'manifest.json')
    if (manifest['status'] != 'prospective' or manifest['scientific_calls'] != 0
            or manifest['planned_calls'] != 15524 or manifest['protocol_sha256'] != sha(STUDY / 'protocol.json')):
        raise ValueError('prospective call inventory differs')
    for name, pin in manifest['files'].items():
        if sha(public / name) != pin['sha256']:
            raise ValueError('published artifact differs: ' + name)
    for ref in ('HEAD', 'origin/master'):
        if subprocess.check_output(['git', 'rev-parse', ref], cwd=ROOT, text=True).strip() != args.public_commit:
            raise ValueError('prospective commit must be both HEAD and origin/master')
    if subprocess.check_output(['git', 'status', '--porcelain'], cwd=ROOT):
        raise ValueError('clean tracked publication required')
    if any((STUDY / name).exists() for name in ('release.json', 'execution', 'raw', 'scored', 'startup.json',
            'row_index.json', 'measurement_complete.json', 'study_complete.json', 'budget.json', 'build-cache')):
        raise ValueError('first release refuses previous runtime artifacts')
    available = next(int(line.split()[1]) * 1024 for line in Path('/proc/meminfo').read_text().splitlines()
                     if line.startswith('MemAvailable:'))
    if available < protocol['runtime_budget']['minimum_available_bytes']:
        raise ValueError('host memory reserve unavailable')
    save(STUDY / 'release.json', dict(status='released', protocol_sha256=sha(STUDY / 'protocol.json'),
        prospective_commit=args.public_commit, prospective_manifest_sha256=sha(public / 'manifest.json'),
        actual_input_review_sha256=sha(STUDY / 'reviews/actual_input_review.json'),
        pid_namespace=os.readlink('/proc/self/ns/pid'), available_memory_bytes=available,
        launch_source_sha256=sha(Path(__file__)),
        authorization='Standing user authorization for bounded safe local experiments; budget reported before launch.'),
        exclusive=True)
    execution = STUDY / 'execution'
    execution.mkdir(exist_ok=False)

    def complete_check():
        marker = read(STUDY / 'measurement_complete.json')
        expected = dict(status='complete', research_lives=15520, startup_lives=4, total_calls=15524,
                        batches=20, genomes=97, genome_world_rows=485, lives_per_genome_world=32,
                        protocol_sha256=sha(STUDY / 'protocol.json'),
                        row_index_sha256=sha(STUDY / 'row_index.json'),
                        rows_manifest_sha256=sha(STUDY / protocol['rows_input']),
                        startup_sha256=sha(STUDY / 'startup.json'))
        if marker != expected:
            raise ValueError('complete measurement marker differs')
        index = read(STUDY / 'row_index.json')
        names = {f'raw/{world}/{group}.npz' for world in protocol['worlds'] for group in protocol['groups']}
        if set(index) != names:
            raise ValueError('exact twenty cohort batches required')
        for name, entry in index.items():
            if sha(STUDY / name) != entry['sha256'] or sha(STUDY / entry['scored_path']) != entry['scored_sha256']:
                raise ValueError('returned raw/scored batch changed')
        summary = read(STUDY / 'summary.json')
        if summary['status'] != 'complete' or summary['protocol_sha256'] != sha(STUDY / 'protocol.json'):
            raise ValueError('complete analysis must accompany the measurement')

    import monitor_core
    result = monitor_core.run_worker(execution,
        [str(ROOT / '.venv/bin/python'), '-u', str(STUDY / 'measure.py'), '--run-child'],
        protocol['runtime_budget'], sha(STUDY / 'protocol.json'), sha(STUDY / 'release.json'), complete_check)
    save(STUDY / 'budget.json', result, exclusive=True)
    if result['status'] != 'complete':
        raise SystemExit(1)
    save(STUDY / 'study_complete.json', dict(status='complete', research_lives=15520, startup_lives=4,
        total_calls=15524, protocol_sha256=sha(STUDY / 'protocol.json'),
        measurement_complete_sha256=sha(STUDY / 'measurement_complete.json'),
        summary_sha256=sha(STUDY / 'summary.json'),
        budget_sha256=sha(STUDY / 'budget.json'),
        execution_budget_sha256=sha(execution / 'budget.json'),
        package_cpu_seconds_with_full_reserve=result['cpu_seconds'] + 60,
        package_wall_seconds_with_full_reserve=result['wall_seconds'] + 60), exclusive=True)
    print(json.dumps({key: result[key] for key in ('status', 'cpu_seconds', 'wall_seconds')}))


if __name__ == '__main__':
    main()
