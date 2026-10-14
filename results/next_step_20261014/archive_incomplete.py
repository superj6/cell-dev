"""Archive terminal incomplete P as raw evidence only; never inspect or compare partial endpoint fitness."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


def write(path, value):
    Path(path).write_text(json.dumps(value, indent=2, allow_nan=False) + '\n')


def need(value, message):
    if not value:
        raise ValueError(message)


def terminal_budget(study):
    path = study / 'budget.json'
    raw = path.read_bytes()
    value = json.loads(raw)
    need(value.get('status') in ('incomplete', 'monitor_failed'), 'requires terminal incomplete status')
    need(not value.get('running') and not value.get('queued'), 'workers and queues must be empty')
    need(value.get('exit_code') not in (None, 0), 'failure must have nonzero terminal exit status')
    cpu = value.get('cpu_seconds')
    need(isinstance(cpu, (int, float)) and math.isfinite(cpu) and cpu >= 0, 'invalid terminal CPU accounting')
    need(value.get('cap_cpu_seconds') == 14400, 'registered P cap differs')
    return raw, value


def verify_manifest(folder, manifest):
    for relative, record in manifest['artifacts'].items():
        path = folder / relative
        need(path.is_file() and sha(path) == record['sha256'] and path.stat().st_size == record['bytes'],
             'frozen preparation differs: ' + str(path))


def clean_files(folder):
    return [p for p in folder.rglob('*') if p.is_file()
            and '__pycache__' not in p.parts and '.pytest_cache' not in p.parts and p.suffix != '.pyc']


def gather(study, repo):
    protocol, ready = read(study / 'protocol.json'), read(study / 'ready.json')
    need(protocol['planned_genome_lives'] == 37548, 'registered total differs')
    for name, expected in [('protocol.json', ready['protocol_sha256']), ('run_budgeted.py', ready['runner_sha256']),
                           ('measure.py', ready['measurement_sha256']), ('prepare.py', protocol['prepare_sha256'])]:
        need(sha(study / name) == expected, 'release source changed: ' + name)
    files = {name: study / name for name in ('protocol.json', 'ready.json', 'seed_audit.json', 'initialization.json')}
    if (study / 'search_health.json').exists():
        files['search_health.json'] = study / 'search_health.json'
    for folder in ('configs', 'inputs', 'runs', 'logs', 'initialization', 'confirmation'):
        files.update({str(p.relative_to(study)): p for p in clean_files(study / folder)})
    for name in ('run_budgeted.py', 'measure.py', 'prepare.py', 'test_prepared.py', 'test_monitor.py', 'budget.json'):
        files['operations/' + name] = study / name
    for relative, expected in protocol['source_identity'].items():
        path = repo / relative
        need(sha(path) == expected, 'engine/search source differs: ' + relative)
        files['sources/' + relative] = path
    for name, expected in ready['helpers'].items():
        path = repo / 'scripts' / name
        need(sha(path) == expected, 'helper differs: ' + name)
        files['sources/scripts/' + name] = path
    for relative, expected in protocol['reference_sources'].items():
        need(sha(study / relative) == expected, 'reference source differs: ' + relative)
        files[relative] = study / relative
    for relative, expected in protocol['template_pins'].items():
        need(sha(repo / relative) == expected, 'template source differs: ' + relative)
        files['templates/' + relative] = repo / relative
    for relative, pins in ready['dependencies'].items():
        for name, expected in pins.items():
            need(sha(repo / relative / name) == expected, 'dependency source differs')
        for name in ('protocol.json', 'run_budgeted.py', 'budget.json'):
            files['dependencies/' + Path(relative).name + '/' + name] = repo / relative / name
    # Preserve the reviewed complete-only analyzer unchanged. Its incomplete gate makes no outcome comparison.
    for name in ('analyze.py', 'test_analyze.py'):
        files[name] = study / name
    return files, protocol, ready


def archive(study, target, repo=ROOT):
    study, target, repo = Path(study), Path(target), Path(repo)
    raw_budget, budget = terminal_budget(study)  # No outcomes or preparation reads before this gate.
    need(study.resolve() != target.resolve(), 'source and target must differ')
    old = read(target / 'provenance.json')
    need(old.get('status') == 'prepared_not_released', 'requires untouched original public preparation')
    verify_manifest(target, old)
    bundle = target / 'offline_analysis_preparation'
    bundle_manifest = read(bundle / 'provenance.json')
    verify_manifest(bundle, bundle_manifest)
    preserved_bundle = {str(p.relative_to(bundle)): sha(p) for p in clean_files(bundle)}
    files, protocol, ready = gather(study, repo)
    need(budget['ready'] == ready, 'terminal resource release identity differs')
    need(sum(p.stat().st_size for p in files.values()) < 50 * 1024 * 1024, 'partial archive unexpectedly large')
    for name in ('analyze.py', 'test_analyze.py'):
        need(sha(files[name]) == sha(bundle / name), 'offline analyzer differs from reviewed preparation')
    historical = target / 'prelaunch'
    need(not historical.exists(), 'partial archive refuses an existing prelaunch directory')
    frozen_sources = {rel: sha(path) for rel, path in files.items()}
    for relative in (*old['artifacts'], 'provenance.json'):
        destination = historical / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(target / relative, destination)
    verify_manifest(historical, old)
    for relative, original in files.items():
        destination = target / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        need(not destination.exists() or sha(destination) == sha(original),
             'refuse to overwrite differing archived bytes: ' + relative)
        shutil.copyfile(original, destination)
        need(sha(destination) == frozen_sources[relative], 'copied raw artifact changed')
    for relative, original in files.items():
        need(sha(original) == frozen_sources[relative], 'raw source changed during archival')
    need((study / 'budget.json').read_bytes() == raw_budget, 'terminal budget changed during archival')
    for relative, expected in preserved_bundle.items():
        need(sha(bundle / relative) == expected, 'offline preparation bundle changed')
    summary = {'status': 'incomplete', 'resource_status': budget['status'], 'reason': budget.get('reason'),
               'error': budget.get('error'), 'planned_genome_lives': 37548, 'completed_genome_lives': None,
               'confirmation': None, 'partial_endpoints_compared': False, 'simulated_lives_by_archival': 0,
               'resource_record': budget, 'protocol_sha256': sha(study / 'protocol.json'),
               'interpretation': 'No confirmed P outcome. Partial search checkpoints and logs are raw evidence only.',
               'limits': ['No inference from partial endpoint fitness or validation-best candidates.',
                          'Exact interrupted research-life count is not inferred from planned or checkpoint counts.',
                          'No replacement, rescue, budget extension, restart or downstream execution was performed '
                          'by archival.']}
    write(target / 'summary.json', summary)
    (target / 'README.md').write_text(
        '# Further continuation from both D endpoints — incomplete\n\n'
        'Both P searches completed, but the fresh fixed-endpoint confirmation did not finish within the authorized run. '
        '**There is no confirmed new P outcome.** Partial endpoints are not compared or reselected.\n\n'
        f"The monitor ended with status `{budget['status']}`, reason `{budget.get('reason')}`, after "
        f"{budget['cpu_seconds']:.6f} CPU-seconds under the fixed 14,400 CPU-second ceiling. "
        'The unchanged terminal resource record is in `operations/budget.json`.\n\n'
        'All available search logs/checkpoints and any partial confirmation rows are preserved as raw evidence. '
        'Their presence does not establish a confirmed fitness effect or a scientifically usable partial comparison. '
        'Actual interrupted life counts are not guessed from the original 37,548-life plan.\n\n'
        'The original public preparation is preserved byte-for-byte under `prelaunch/`. The separately reviewed '
        'offline-analysis preparation bundle remains unchanged. The complete-only analyzer remains available, '
        'but its incomplete gate returns no confirmation or endpoint comparisons.\n\n'
        'No simulation was performed during archival, and no budget extension, restart, replacement or rescue '
        'was attempted. The raw records allow inspection of the failure without converting it into a result.\n')
    for name in ('archive_incomplete.py', 'test_archive_incomplete.py'):
        path = Path(__file__).with_name(name)
        if path.exists():
            shutil.copyfile(path, target / name)
    artifacts = {str(p.relative_to(target)): {'sha256': sha(p), 'bytes': p.stat().st_size}
                 for p in sorted(clean_files(target)) if p != target / 'provenance.json'}
    write(target / 'provenance.json', {'format': 1, 'status': 'incomplete', 'artifacts': artifacts,
          'protocol_sha256': sha(study / 'protocol.json'), 'source_identity': protocol['source_identity'],
          'total_artifact_bytes': sum(x['bytes'] for x in artifacts.values()),
          'archive_tool_sha256': sha(Path(__file__)), 'simulated_lives_by_archival': 0,
          'no_confirmed_outcome': True, 'partial_endpoints_compared': False,
          'original_preparation_sha256': sha(historical / 'provenance.json'),
          'offline_preparation_sha256': sha(bundle / 'provenance.json')})
    verify_manifest(target, read(target / 'provenance.json'))
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--study', type=Path, default=Path(__file__).resolve().parent)
    parser.add_argument('--target', type=Path, default=ROOT / 'results/next_step_20261014')
    parser.add_argument('--archive', action='store_true')
    args = parser.parse_args()
    if not args.archive:
        print(json.dumps({'status': 'dry_run', 'simulated_lives': 0,
                          'requires': 'terminal incomplete, empty queues; preserves raw bytes without outcome analysis'}))
        return
    result = archive(args.study, args.target)
    print(json.dumps({key: result[key] for key in ('status', 'reason', 'confirmation', 'partial_endpoints_compared')}))


if __name__ == '__main__':
    main()
