"""Verify the complete population archive with hashes and receipt schemas only; never simulate."""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path, PurePosixPath

HERE = Path(__file__).resolve().parent
ROOT = next(parent for parent in HERE.parents if (parent / '.git').is_dir())
PROTOCOL = '6fb2a4f9744ff15377346bde4b2d7af42a7e12087e5f9d2d9cc622af7a5ee33f'
REVISION = '5d556443e91d558de8de27ab2e5dc7ae11a51415'
REGISTRATION = ('manifest.json', 'README.md', 'verify_public.py', 'publish.py')
GROUPS = {'G8': (0, 32), 'mean4': (32, 64), 'pareto4': (64, 96), 'AO': (96, 97)}
WORLDS = ('patch', 'pool', 'persistent', 'blink80_20', 'transfer')


def require(value, message):
    if not value:
        raise ValueError(message)


def read(path):
    return json.loads(Path(path).read_text())


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def checked(base, name):
    relative = PurePosixPath(name)
    require(relative.parts and not relative.is_absolute() and str(relative) == name
            and all(part not in ('.', '..') for part in relative.parts), 'unsafe relative path')
    path = Path(base)
    for part in relative.parts:
        path /= part
        require(not path.is_symlink(), 'symlink in evidence')
    require(path.resolve().is_relative_to(Path(base).resolve()), 'escaped evidence path')
    return path


def files(base):
    result = set()
    for path in Path(base).rglob('*'):
        require(not path.is_symlink(), 'symlink in archive')
        if path.is_file() and '__pycache__' not in path.parts:
            result.add(str(path.relative_to(base)))
    return result


def manifest_files(base, manifest):
    require(files(base) == set(manifest['files']) | {'manifest.json'}, 'exact manifest file set')
    for name, pin in manifest['files'].items():
        path = checked(base, name)
        require(sha(path) == pin['sha256'] and path.stat().st_size == pin['bytes'], 'manifest: ' + name)


def terminal_bindings(base):
    base = Path(base)
    p = read(base / 'protocol.json')
    require(sha(base / 'protocol.json') == PROTOCOL and p['source_revision'] == REVISION
            and (p['research_lives'], p['startup_lives'], p['total_calls']) == (15520, 4, 15524), 'fixed protocol')
    require(p['groups'] == list(GROUPS) and list(p['worlds']) == list(WORLDS)
            and p['seeds'] == list(range(52510000, 52510032)), 'fixed panel')
    for category in ('source_pins', 'input_pins'):
        for name, pin in p[category].items():
            require(sha(checked(base, name)) == pin, 'frozen source/input: ' + name)
    for field, name in (('seed_audit_sha256', 'namespace/seed_audit.json'),
                        ('reservation_sha256', 'reservation.json')):
        require(sha(base / name) == p[field], 'namespace evidence')
    ready, review, release = [read(base / name) for name in
                             ('READY.json', 'reviews/actual_input_review.json', 'release.json')]
    require(all(item['protocol_sha256'] == PROTOCOL for item in (ready, review, release))
            and review['status'] == 'passed' and release['status'] == 'released'
            and release['launch_source_sha256'] == sha(base / 'run.py')
            and release['actual_input_review_sha256'] == sha(base / 'reviews/actual_input_review.json'), 'review/release')
    whole, measured, budget = [read(base / name) for name in
                              ('study_complete.json', 'measurement_complete.json', 'budget.json')]
    require(all(item['status'] == 'complete' and item['protocol_sha256'] == PROTOCOL
                for item in (whole, measured, budget)), 'three complete terminal markers')
    for item in (whole, measured):
        require((item['research_lives'], item['startup_lives'], item['total_calls']) == (15520, 4, 15524), 'terminal count')
    require((measured['batches'], measured['genomes'], measured['genome_world_rows'],
             measured['lives_per_genome_world']) == (20, 97, 485, 32), 'measurement dimensions')
    for field, name in (('measurement_complete_sha256', 'measurement_complete.json'),
                        ('summary_sha256', 'summary.json'), ('budget_sha256', 'budget.json'),
                        ('execution_budget_sha256', 'execution/budget.json')):
        require(whole[field] == sha(base / name), 'whole-study binding: ' + name)
    require(read(base / 'execution/budget.json') == budget and budget['exit_code'] == budget['worker_exit_code'] == 0
            and not budget['running'] and not budget['queued'] and not budget['cleanup_error'], 'cleared owned budget')
    require(budget['release_sha256'] == sha(base / 'release.json')
            and budget['attempt_sha256'] == sha(base / 'execution/attempt.json'), 'owned attempt')
    limits = p['runtime_budget']
    require(budget['cpu_seconds'] < budget['cap_cpu_seconds'] == limits['cpu_seconds'] == 2640
            and budget['wall_seconds'] < budget['cap_wall_seconds'] == limits['wall_seconds'] == 1740
            and budget['peak_owned_rss_bytes'] < budget['cap_rss_bytes'] == 4*1024**3
            and budget['available_memory_bytes'] >= budget['minimum_available_bytes'] == 4*1024**3
            and budget['worker_address_space_bytes'] == 8*1024**3, 'runtime resource caps')
    cleanup = budget['terminal_cleanup']
    require(cleanup['same_pid_namespace'] and cleanup['all_owned_groups_exited']
            and cleanup['all_worker_identities_exited'] and not cleanup['remaining_descendants']
            and not cleanup['remaining_group_members'] and not cleanup['remaining_worker_identities'], 'ownership cleanup')
    require(whole['package_cpu_seconds_with_full_reserve'] == budget['cpu_seconds']+60 < 2700
            and whole['package_wall_seconds_with_full_reserve'] == budget['wall_seconds']+60 < 1800,
            'package including full preparation/terminal reserve')
    rows_sha, index_sha = sha(base / p['rows_input']), sha(base / 'row_index.json')
    require(measured['rows_manifest_sha256'] == rows_sha and measured['row_index_sha256'] == index_sha
            and measured['startup_sha256'] == sha(base / 'startup.json'), 'measurement links')
    summary = read(base / 'summary.json')
    require(summary['status'] == 'complete' and summary['protocol_sha256'] == PROTOCOL
            and summary['row_index_sha256'] == index_sha and summary['rows_manifest_sha256'] == rows_sha
            and (summary['research_lives'], summary['startup_lives'], summary['genomes'],
                 summary['paired_life_clusters'], summary['raw_batches']) == (15520, 4, 97, 32, 20), 'summary binding')
    index, raw_pins = read(base / 'row_index.json'), {}
    expected = {f'raw/{world}/{group}.npz' for world in WORLDS for group in GROUPS}
    require(set(index) == expected, 'exact twenty raw batches')
    for world in WORLDS:
        for group, (start, stop) in GROUPS.items():
            name, scored = f'raw/{world}/{group}.npz', f'scored/{world}/{group}.npz'
            item = index[name]
            require(item['status'] == 'validated' and item['abi'] == 6 and item['group'] == group
                    and item['world'] == world and item['row_indices'] == list(range(start, stop))
                    and item['requested_lives'] == item['lives'] == (stop-start)*32
                    and item['scored_path'] == scored, 'batch scope: ' + name)
            raw_pins[name], raw_pins[scored] = item['sha256'], item['scored_sha256']
    require({prefix+'/'+name for prefix in ('raw', 'scored') for name in files(base/prefix)} == set(raw_pins),
            'exact twenty raw plus twenty scored files')
    for name, pin in raw_pins.items():
        require(sha(checked(base, name)) == pin, 'raw/scored bytes: ' + name)
    startup = read(base / 'startup.json')
    require(startup['protocol_sha256'] == PROTOCOL and startup['startup_lives'] == 4
            and startup['identity'] == p['expected_numerical_identity'], 'four retained startup calls')
    patch = startup['patches']
    require(patch['lives'] == 2 and patch['seed'] == 42000000 and patch['name'] == 'reflex_count1'
            and patch['fixture_sha256'] == sha(base / 'inputs/patch_truth.json')
            and patch['calls_path'] == 'startup_truth/calls.json'
            and patch['calls_sha256'] == sha(base / patch['calls_path']), 'patch startup binding')
    calls = read(base / patch['calls_path'])
    require([item['backend'] for item in calls] == ['C_full', 'C_fast'], 'two patch startup backends')
    for item, name in zip(calls, ('full.npz', 'fast.npz'), strict=True):
        require(item['status'] == 'validated' and item['seed'] == 42000000
                and item['raw_sha256'] == sha(base / 'startup_truth' / name), 'retained startup raw')
    audit = read(base / 'reviews/independent_review.json')
    require(audit['status'] == 'passed' and audit['protocol_sha256'] == PROTOCOL
            and audit['summary_sha256'] == sha(base / 'summary.json')
            and audit['source_sha256'] == sha(base / 'terminal_review/independent_review.py'), 'terminal review binding')
    borrowed = audit['borrowed_scalar_source']
    require(borrowed['path'].startswith('results/') and sha(checked(ROOT, borrowed['path'])) == borrowed['sha256'],
            'retained independent scalar checker')
    require((audit['raw_batches'], audit['scored_batches'], audit['genome_world_rows'],
             audit['research_rows_checked'], audit['retained_startup_calls'], audit['total_original_calls'],
             audit['ranking_rows_checked'], audit['cached_rows_checked'], audit['shared_seed_clusters'])
            == (20, 20, 485, 15520, 4, 15524, 97, 64, 32)
            and audit['new_lives'] == audit['new_builds'] == audit['new_seed_or_genetic_draws'] == 0,
            'independent review coverage')
    require(audit['artifact_pins'].get('row_index.json') == index_sha
            and all(audit['artifact_pins'].get(name) == pin for name, pin in raw_pins.items()), 'audited raw/index coverage')
    for name, pin in audit['artifact_pins'].items():
        require(sha(checked(base, name)) == pin, 'independently reviewed artifact: ' + name)
    tables = read(base / 'tables_receipt.json')
    require(tables['status'] == 'complete' and tables['summary_sha256'] == sha(base / 'summary.json')
            and tables['source_sha256'] == sha(base / 'terminal_tables/report_tables.py')
            and tables['new_lives'] == tables['builds'] == tables['random_draws'] == 0, 'saved-table receipt')
    require(set(tables['files']) == {'TABLES.md', 'population_rows.csv', 'population_acquisition.svg',
            'population_acquisition.png', 'cached_fresh_ranks.svg', 'cached_fresh_ranks.png'}, 'table/plot coverage')
    for name, pin in tables['files'].items():
        require(sha(checked(base, name)) == pin, 'saved table/plot: ' + name)
    return p, raw_pins


def verify(base):
    base = Path(base).resolve()
    manifest = read(base / 'manifest.json')
    require(manifest['status'] == 'complete' and manifest['protocol_sha256'] == PROTOCOL
            and (manifest['research_lives'], manifest['startup_lives'], manifest['total_calls']) == (15520, 4, 15524),
            'complete manifest')
    manifest_files(base, manifest)
    historical = read(base / 'registration/manifest.json')
    require(historical['status'] == 'prospective' and historical['scientific_calls'] == 0
            and historical['planned_calls'] == 15524 and historical['protocol_sha256'] == PROTOCOL, 'registration scope')
    for name, pin in historical['files'].items():
        path = checked(base, 'registration/'+name if name in REGISTRATION else name)
        require(sha(path) == pin['sha256'] and path.stat().st_size == pin['bytes'], 'preserved registration: ' + name)
    require(read(base/'release.json')['prospective_manifest_sha256'] == sha(base/'registration/manifest.json'),
            'released public registration')
    p, raw_pins = terminal_bindings(base)
    for item in read(base / 'namespace_references.json'):
        require(item['public_path'].startswith('results/') and sha(checked(ROOT, item['public_path'])) == item['sha256'],
                'public namespace reference')
    for name, pin in p['original_input_pins'].items():
        require(sha(checked(ROOT, name)) == pin, 'original public scientific source')
    for name, pin in p['production_pins'].items():
        value = subprocess.check_output(['git', 'show', REVISION+':'+name], cwd=ROOT)
        require(hashlib.sha256(value).hexdigest() == pin, 'committed production dependency')
    receipt = read(base / 'packaging_receipt.json')
    require(receipt['status'] == 'staged' and receipt['protocol_sha256'] == PROTOCOL
            and receipt['summary_sha256'] == sha(base/'summary.json')
            and receipt['prospective_manifest_sha256'] == sha(base/'registration/manifest.json')
            and receipt['helper_sha256'] == sha(base/'terminal_package/pack.py')
            and receipt['raw_scored_files'] == raw_pins
            and receipt['simulator_calls'] == receipt['builds'] == receipt['random_draws'] == 0, 'packaging receipt')
    return dict(status='passed', archive_files=len(manifest['files']), protocol_sha256=PROTOCOL,
                raw_batches=20, scored_batches=20, research_lives=15520, total_calls=15524,
                simulator_calls=0, builds=0, random_draws=0)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--archive', type=Path, default=HERE)
    print(json.dumps(verify(parser.parse_args().archive), indent=2))
