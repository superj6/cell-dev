"""Bind the published study and current process namespace, then run its frozen monitor once."""
import argparse
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
        print('source only: no release, build or life')
        return
    if args.public_commit is None or len(args.public_commit) != 40:
        raise ValueError('exact committed prospective publication required')
    protocol = checked_protocol()
    public = ROOT / 'results/resource_patch_selection_20261015'
    review = read(STUDY / 'reviews/actual_input_review.json')
    if (review['status'] != 'passed' or review['protocol_sha256'] != sha(STUDY / 'protocol.json')
            or sha(public / 'protocol.json') != sha(STUDY / 'protocol.json')
            or sha(public / 'reviews/actual_input_review.json') != sha(STUDY / 'reviews/actual_input_review.json')
            or sha(public / 'release_and_run.py') != sha(Path(__file__))):
        raise ValueError('reviewed published protocol or launcher differs')
    manifest = read(public / 'manifest.json')
    if (manifest['status'] != 'prospective' or manifest['scientific_calls'] != 0
            or manifest['planned_calls'] != 30808 or manifest['protocol_sha256'] != sha(STUDY / 'protocol.json')):
        raise ValueError('prospective manifest differs')
    for name, pin in manifest['files'].items():
        if sha(public / name) != pin['sha256']:
            raise ValueError('published artifact differs: ' + name)
    for ref in ('HEAD', 'origin/master'):
        actual = subprocess.check_output(['git', 'rev-parse', ref], cwd=ROOT, text=True).strip()
        if actual != args.public_commit:
            raise ValueError('committed publication not at both local and remote-tracking master')
    if subprocess.check_output(['git', 'status', '--porcelain'], cwd=ROOT) != b'':
        raise ValueError('publication requires clean tracked workspace')
    runtime = ('release.json', 'attempt.json', 'budget.json', 'execution', 'runs', 'raw', 'scored',
               'endpoints.json', 'build-cache')
    if any((STUDY / name).exists() for name in runtime):
        raise ValueError('first release refuses any prior runtime artifact')
    available = next(int(line.split()[1]) * 1024 for line in Path('/proc/meminfo').read_text().splitlines()
                     if line.startswith('MemAvailable:'))
    if available < protocol['budget']['minimum_available_bytes']:
        raise ValueError('host available-memory reserve unavailable')
    save(STUDY / 'release.json', dict(status='released', protocol_sha256=sha(STUDY / 'protocol.json'),
        prospective_commit=args.public_commit, public_commit=args.public_commit,
        prospective_manifest_sha256=sha(public / 'manifest.json'), public_manifest_sha256=sha(public / 'manifest.json'),
        actual_input_review_sha256=sha(STUDY / 'reviews/actual_input_review.json'),
        pid_namespace=os.readlink('/proc/self/ns/pid'), available_memory_bytes=available,
        launch_source_sha256=sha(Path(__file__)), authorization='Standing user authorization for bounded safe local experiments; budget reported before launch.'),
        exclusive=True)
    import monitor
    sys.argv = [str(STUDY / 'monitor.py'), '--run']
    monitor.main()


if __name__ == '__main__':
    main()
