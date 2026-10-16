"""Verify a complete depth archive from saved bytes and receipts; never import the simulator."""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path, PurePosixPath

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
ROOT = next((parent for parent in HERE.parents if (parent / '.git').is_dir()), None)
PROTOCOL = '86593f759c5c17823d4eaff19800728229f757eb2ffc82b2f54660e9b32653bb'
REVISION = '1a7f38bd3222bacf27367fd99998d87776c34ec5'
REGISTRATION = ('manifest.json', 'README.md', 'publish.py', 'verify_public.py')
TRAIN = ('patch', 'pool', 'persistent')
WORLDS = (*TRAIN, 'blink80_20', 'transfer', 'reserved_capacity3')
ROLES = ('AO', 'G8_joint', 'Pareto4_joint', 'depth8_joint')


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


def pins(base, values, label):
    for name, digest in values.items():
        require(sha(checked(base, name)) == digest, label + ': ' + name)


def cleared(record):
    proof = record['terminal_cleanup']
    require(proof['checked_in_monitor'] and proof['same_pid_namespace'] and proof['all_owned_groups_exited']
            and proof['all_worker_identities_exited'] and not proof['remaining_descendants']
            and not proof['remaining_group_members'] and not proof['remaining_worker_identities'], 'owned cleanup')


def terminal_bindings(base):
    """Check live-study or staged terminal evidence without reading a partial run."""
    base = Path(base)
    p = read(base / 'protocol.json')
    require(sha(base / 'protocol.json') == PROTOCOL and p['source_revision'] == REVISION
            and (p['research_lives'], p['startup_lives'], p['total_calls']) == (97334, 8, 97342), 'fixed protocol')
    whole, measured, budget = [read(base / name) for name in
                              ('study_complete.json', 'measurement_complete.json', 'budget.json')]
    require(all(row['status'] == 'complete' and row['protocol_sha256'] == PROTOCOL
                for row in (whole, measured, budget)), 'complete terminal markers required')
    for category in ('source_pins', 'input_pins'):
        pins(base, p[category], 'frozen ' + category)
    for field, name in (('seed_audit_sha256', 'namespace/seed_audit.json'),
                        ('reservation_sha256', 'reservation.json')):
        require(sha(base / name) == p[field], 'namespace binding')
    ready, review, release = [read(base / name) for name in
                             ('READY.json', 'reviews/actual_input_review.json', 'release.json')]
    require(all(item['protocol_sha256'] == PROTOCOL for item in (ready, review, release))
            and review['status'] == 'passed' and release['status'] == 'released'
            and release['launch_source_sha256'] == sha(base / 'run.py')
            and release['actual_input_review_sha256'] == sha(base / 'reviews/actual_input_review.json'),
            'review/release')
    require((whole['research_lives'], whole['startup_lives'], whole['total_calls']) == (97334, 8, 97342),
            'whole-study calls')
    for field, name in (('search_complete_sha256', 'runs/pareto/search_complete.json'),
                        ('measurement_complete_sha256', 'measurement_complete.json'),
                        ('summary_sha256', 'summary.json'), ('budget_sha256', 'budget.json')):
        require(whole[field] == sha(base / name), 'whole-study binding: ' + name)
    limits, phases = p['runtime_budget'], p['phase_budgets']
    require((limits['cpu_seconds'], limits['wall_seconds'], limits['threads'], limits['workers'])
            == (10620, 7020, 2, 1) and set(phases) == {'pareto', 'measurement'}, 'fixed runtime scope')
    require(budget['release_sha256'] == sha(base / 'release.json') and not budget['running']
            and not budget['queued'] and budget['error'] is None, 'terminal release and no queued work')
    require(budget['cpu_seconds'] < budget['cap_cpu_seconds'] == 10620
            and budget['wall_seconds'] < budget['cap_wall_seconds'] == 7020
            and budget['peak_owned_rss_bytes'] < 4*1024**3, 'whole runtime caps')
    cleared(budget)
    require(set(whole['phase_budget_pins']) == set(budget['phases']) == {'pareto', 'measurement'}, 'two owned phases')
    for phase in ('pareto', 'measurement'):
        name = f'execution/{phase}/budget.json'
        record, attempt = read(base / name), read(base / f'execution/{phase}/attempt.json')
        require(whole['phase_budget_pins'][phase] == sha(base / name) and budget['phases'][phase] == record,
                'phase budget binding')
        require(record['status'] == 'complete' and record['exit_code'] == record['worker_exit_code'] == 0
                and not record['running'] and not record['queued'] and not record['cleanup_error']
                and record['protocol_sha256'] == attempt['protocol_sha256'] == PROTOCOL
                and record['release_sha256'] == attempt['release_sha256'] == sha(base / 'release.json')
                and record['attempt_sha256'] == sha(base / f'execution/{phase}/attempt.json'), 'owned attempt')
        require(record['cpu_seconds'] < record['cap_cpu_seconds'] <= limits['cpu_seconds']
                and record['wall_seconds'] < record['cap_wall_seconds'] <= phases[phase]['wall_seconds']
                and record['peak_owned_rss_bytes'] < record['cap_rss_bytes'] == 4*1024**3
                and record['available_memory_bytes'] >= record['minimum_available_bytes'] == 4*1024**3
                and record['worker_address_space_bytes'] == 8*1024**3, 'phase resource caps')
        require(budget['phase_cpu_seconds'][phase] < phases[phase]['cpu_seconds'], 'phase allocation')
        identities = {item['name']: item for item in record['process_identities']}
        require(set(identities) == {'monitor', 'worker'}
                and identities['monitor'] == dict(attempt['monitor'], name='monitor')
                and identities['worker']['ppid'] == identities['monitor']['pid']
                and identities['worker']['pid'] == identities['worker']['pgid']
                and record['pid_namespace'] == attempt['pid_namespace'] == release['pid_namespace']
                and any(row['pid'] == identities['worker']['pid'] and row['exit_code'] == 0
                        for row in record['wait4_receipts']), 'process identity/exit binding')
        cleared(record)
    require(whole['package_cpu_seconds_with_full_reserve'] == budget['cpu_seconds']+180 < 10800
            and whole['package_wall_seconds_with_full_reserve'] == budget['wall_seconds']+180 < 7200,
            'package including full reserve')
    search = read(base / 'runs/pareto/search_complete.json')
    require(search['status'] == 'complete' and search['arm'] == 'pareto'
            and search['protocol_sha256'] == PROTOCOL and search['release_sha256'] == sha(base / 'release.json')
            and search['research_lives'] == 81974 and search['startup_lives'] == 4
            and search['count_proof'] == dict(selection=81920, valid=48, final=6, growth_half=2,
                native_evals=2560, generations=8, children_per_generation=224)
            and search['reporting_endpoint_selected'] is False and search['native_rank0_only'] is True,
            'native search inventory and endpoint separation')
    expected = {'checkpoint.pt', 'config.yaml', 'determinism.json', 'curves.jsonl', 'lineage.jsonl',
                'population.json', 'best_genome.json', 'results.jsonl', 'search_startup.json',
                *(f'selection/g{g:03d}.npz' for g in range(8))}
    require(set(search['output_pins']) == expected, 'complete native output inventory')
    pins(base / 'runs/pareto', search['output_pins'], 'native output')
    require(files(base / 'runs/pareto/selection') == {f'g{g:03d}.npz' for g in range(8)}, 'eight selection arrays')
    for name, meta in search['checkpoint_log_pins'].items():
        data = checked(base / 'runs/pareto', name).read_bytes()
        require(len(data) == meta['bytes'] and hashlib.sha256(data).hexdigest() == meta['sha256'], 'checkpoint log')
    expected_measurement = dict(status='complete', research_lives=15360, startup_lives=4, total_calls=15364,
        endpoint_lives=3072, confirmation_lives=12288, endpoint_batches=3, confirmation_batches=6,
        protocol_sha256=PROTOCOL, endpoint_index_sha256=sha(base / 'endpoint_index.json'),
        row_index_sha256=sha(base / 'row_index.json'), endpoint_selection_sha256=sha(base / 'endpoint_selection.json'),
        endpoints_sha256=sha(base / 'endpoints.json'), startup_sha256=sha(base / 'startup.json'))
    require(measured == expected_measurement, 'complete nine-cohort measurement')
    population, selected, endpoints = [read(base / name) for name in
                                       ('endpoint_population.json', 'endpoint_selection.json', 'endpoints.json')]
    require(population['status'] == selected['status'] == 'complete'
            and population['protocol_sha256'] == selected['protocol_sha256'] == endpoints['protocol_sha256'] == PROTOCOL
            and population['array_sha256'] == sha(base / 'endpoint_population.npz')
            and len(population['ids']) == len(set(population['ids'])) == 32
            and population['reporting_endpoint_selected'] is False, 'full final population snapshot')
    pins(base, population['source_pins'], 'endpoint population sources')
    require(selected['population_manifest_sha256'] == sha(base / 'endpoint_population.json')
            and selected['endpoint_index_sha256'] == sha(base / 'endpoint_index.json')
            and selected['genome_file_sha256'] == sha(base / 'joint_genome.json')
            and endpoints['roles'] == list(ROLES) and len(endpoints['genomes']) == 4
            and endpoints['endpoint_selection_sha256'] == sha(base / 'endpoint_selection.json')
            and endpoints['references_manifest_sha256'] == sha(base / p['references_manifest']),
            'frozen reporting endpoint')
    for role, item in zip(ROLES, endpoints['genomes'], strict=True):
        require(item['role'] == role and sha(checked(base, item['path'])) == item['file_sha256'], 'fixed endpoint file')
    raw_pins = {}
    for stage, worlds, prefix, row_ids, count in (
        ('endpoint', TRAIN, 'endpoint_', population['ids'], 1024),
        ('confirmation', WORLDS, '', list(range(4)), 2048)):
        index = read(base / ('endpoint_index.json' if prefix else 'row_index.json'))
        require(set(index) == {f'{prefix}raw/{world}.npz' for world in worlds}, 'exact cohort index')
        for world in worlds:
            name, scored = f'{prefix}raw/{world}.npz', f'{prefix}scored/{world}.npz'
            item = index[name]
            require(item['status'] == 'validated' and item['abi'] == 6 and item['stage'] == stage
                    and item['world'] == world and item['row_ids'] == row_ids
                    and item['requested_lives'] == item['lives'] == count and item['scored_path'] == scored,
                    'cohort inventory: ' + name)
            raw_pins[name], raw_pins[scored] = item['sha256'], item['scored_sha256']
        for kind in ('raw', 'scored'):
            require(files(base / (prefix+kind)) == {world+'.npz' for world in worlds}, 'exact cohort file set')
    pins(base, raw_pins, 'raw/scored bytes')
    summary = read(base / 'summary.json')
    require(summary['status'] == 'complete' and summary['protocol_sha256'] == PROTOCOL
            and (summary['research_lives'], summary['startup_lives'], summary['endpoint_lives'],
                 summary['confirmation_lives'], summary['endpoint_batches'], summary['confirmation_batches'])
            == (15360, 4, 3072, 12288, 3, 6), 'summary inventory')
    for field, name in (('row_index_sha256', 'row_index.json'),
                        ('endpoint_index_sha256', 'endpoint_index.json'),
                        ('endpoints_sha256', 'endpoints.json'),
                        ('endpoint_selection_sha256', 'endpoint_selection.json')):
        require(summary[field] == sha(base / name), 'summary binding')
    for phase, name in (('pareto', 'runs/pareto/search_startup.json'), ('measurement', 'startup.json')):
        startup = read(base / name)
        require(startup['protocol_sha256'] == PROTOCOL and startup['startup_lives'] == 4
                and startup['identity'] == p['expected_numerical_identity'], 'four-call phase startup')
        patch = startup['patches']
        require(patch['lives'] == 2 and patch['name'] == 'reflex_count1' and patch['seed'] == 42000000
                and patch['fixture_sha256'] == sha(base / 'inputs/patch_truth.json')
                and patch['calls_path'] == f'execution/{phase}/patch_truth/calls.json'
                and patch['calls_sha256'] == sha(base / patch['calls_path']), 'startup raw binding')
        calls = read(base / patch['calls_path'])
        require([item['backend'] for item in calls] == ['C_full', 'C_fast'], 'two startup patch backends')
        for item, filename in zip(calls, ('full.npz', 'fast.npz'), strict=True):
            require(item['status'] == 'validated' and item['seed'] == 42000000
                    and item['raw_sha256'] == sha(base / f'execution/{phase}/patch_truth/{filename}'),
                    'startup raw')
    accounting = read(base / 'reviews/independent_accounting.json')
    require(accounting['status'] == 'passed' and accounting['protocol_sha256'] == PROTOCOL
            and accounting['summary_sha256'] == sha(base / 'summary.json')
            and accounting['source_sha256'] == sha(base / 'terminal_accounting/check.py')
            and accounting['search_complete_sha256'] == sha(base / 'runs/pareto/search_complete.json')
            and accounting['checkpoint_sha256'] == sha(base / 'runs/pareto/checkpoint.pt'),
            'independent accounting pins')
    require((accounting['endpoint_ledgers_checked'], accounting['confirmation_ledgers_checked'],
             accounting['raw_batches'], accounting['scored_batches'], accounting['startup_calls_verified'],
             accounting['original_search_research'], accounting['original_total_calls'])
            == (3072, 12288, 9, 9, 8, 81974, 97342)
            and accounting['new_lives'] == accounting['new_builds'] == accounting['new_random_draws'] == 0,
            'independent accounting coverage')
    require(all(accounting['artifact_pins'].get(name) == pin for name, pin in raw_pins.items()),
            'audited raw/scored coverage')
    pins(base, accounting['artifact_pins'], 'audited accounting artifact')
    genetics = read(base / 'terminal_genetics/receipt.json')
    require(genetics['status'] == 'passed' and genetics['protocol_sha256'] == PROTOCOL
            and (genetics['initial_rows'], genetics['offspring_replayed'], genetics['point_additions_replayed'],
                 genetics['scored_candidate_rows_bound'], genetics['all_final_rows_bound'],
                 genetics['rankings_checked'],
                 genetics['tie_permutations_checked'], genetics['selection_lives_checked'])
            == (32, 1792, 3584, 2048, 32, 16, 24, 81920)
            and genetics['calls'] == dict(simulator=0, builds=0, random_draws=0),
            'independent recorded genetics coverage')
    require(genetics['source_pins_verified'] == p['source_pins'] and genetics['input_pins_verified'] == p['input_pins']
            and genetics['artifact_pins'].get('runs/pareto/checkpoint.pt') == sha(base / 'runs/pareto/checkpoint.pt')
            and genetics['artifact_pins'].get('runs/pareto/search_complete.json')
            == sha(base / 'runs/pareto/search_complete.json'), 'genetics source/checkpoint bindings')
    pins(base, genetics['artifact_pins'], 'genetics artifact')
    pins(base / 'terminal_genetics', genetics['source_sha256'], 'genetics helper')
    pins(base, genetics['selection_audit']['artifact_pins'], 'independent selection artifact')
    tables = read(base / 'reviews/tables_receipt.json')
    require(tables['status'] == 'complete' and tables['summary_sha256'] == sha(base / 'summary.json')
            and tables['source_sha256'] == sha(base / 'terminal_tables/report_tables.py') and tables['new_lives'] == 0,
            'table receipt')
    require(set(tables['output_pins']) == {'TABLES.md', 'confirmation_rows.csv', 'acquisition.png', 'acquisition.svg',
                                         'primary_differences.png', 'primary_differences.svg'}, 'table/plot set')
    pins(base, tables['output_pins'], 'table/plot')
    return p, raw_pins


def verify(base, installed_sources=False):
    base = Path(base).resolve()
    manifest = read(base / 'manifest.json')
    require(manifest['status'] == 'complete' and manifest['protocol_sha256'] == PROTOCOL
            and (manifest['research_lives'], manifest['startup_lives'], manifest['total_calls']) == (97334, 8, 97342),
            'complete manifest')
    manifest_files(base, manifest)
    original = read(base / 'registration/manifest.json')
    require(original['status'] == 'prospective' and original['scientific_calls'] == 0
            and original['planned_calls'] == 97342 and original['protocol_sha256'] == PROTOCOL, 'registration scope')
    for name, pin in original['files'].items():
        path = checked(base, 'registration/'+name if name in REGISTRATION else name)
        require(sha(path) == pin['sha256'] and path.stat().st_size == pin['bytes'], 'prospective bytes: ' + name)
    require(read(base / 'release.json')['prospective_manifest_sha256'] == sha(base / 'registration/manifest.json'),
            'released prospective manifest')
    p, raw_pins = terminal_bindings(base)
    pins(base / 'production', p['production_pins'], 'retained production')
    if installed_sources:
        require(ROOT is not None, 'installed-source comparison requires a repository checkout')
        pins(ROOT, p['production_pins'], 'installed production')
    accounting = read(base / 'reviews/independent_accounting.json')
    for key, item in accounting['borrowed_sources'].items():
        require(sha(checked(base / 'audit_dependencies', key+'.py')) == item['sha256'], 'retained borrowed checker')
    for fast, digest in p['expected_numerical_identity']['kernels'].items():
        require(sha(base / f'native_binaries/{fast}.so') == digest, 'retained native binary')
    for field, name in (('release_sha256', 'release.json'), ('summary_sha256', 'summary.json'),
                        ('source_revision', None), ('prospective_manifest_sha256', 'registration/manifest.json')):
        require(manifest[field] == (REVISION if name is None else sha(base / name)), 'manifest terminal binding')
    receipt = read(base / 'packaging_receipt.json')
    require(receipt['status'] == 'staged' and receipt['protocol_sha256'] == PROTOCOL
            and receipt['summary_sha256'] == sha(base / 'summary.json')
            and receipt['prospective_manifest_sha256'] == sha(base / 'registration/manifest.json')
            and receipt['helper_sha256'] == sha(base / 'terminal_package/pack.py')
            and receipt['raw_scored_files'] == raw_pins
            and receipt['simulator_calls'] == receipt['builds'] == receipt['random_draws'] == 0, 'packaging receipt')
    require(all((base / name).is_file() for name in ('REPORT.md', 'README.md', 'NEXT_DECISION.md')), 'terminal prose')
    return dict(status='passed', archive_files=len(manifest['files']), protocol_sha256=PROTOCOL,
        raw_batches=9, scored_batches=9, research_lives=97334, total_calls=97342,
        installed_sources_checked=installed_sources, simulator_calls=0, builds=0, random_draws=0)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--archive', type=Path, default=HERE)
    parser.add_argument('--installed-sources', action='store_true')
    args = parser.parse_args()
    print(json.dumps(verify(args.archive, args.installed_sources), indent=2))
