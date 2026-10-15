"""AN planning only: retained resource receipts and raw timing metadata, no life execution."""
import hashlib
import json
import os
from pathlib import Path
import zipfile

import numpy as np

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[2]
AM = ROOT / 'outputs/autonomous_capture_value_selection_20261015'
HOST = 'pid:[4026531836]'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text())


def save(name, value):
    (OUT / name).write_text(json.dumps(value, indent=2) + '\n')


def main():
    prior_path = ROOT / 'outputs/audit_capture_value_selection_20261015/operations/prior_resource_evidence.json'
    prior = read(prior_path)
    for name, digest in (prior['budget_pins'] | prior['source_pins']).items():
        assert sha(ROOT / name) == digest
    budget = read(AM / 'budget.json')
    clear = read(AM / 'terminal_review/host_clearance.json')
    assert budget['status'] == 'complete' and budget['exit_code'] == 0 and budget['cleanup_error'] is None
    assert clear['status'] == 'cleared' and clear['budget_sha256'] == sha(AM / 'budget.json')
    assert budget['pid_namespace'] == clear['pid_namespace'] == HOST
    assert not clear['remaining_identities'] and not clear['remaining_group_members']
    assert not budget['running'] and not budget['queued']
    cleanup = budget['terminal_cleanup']
    assert cleanup['checked_in_monitor'] and cleanup['same_pid_namespace']
    assert cleanup['all_owned_groups_exited'] and cleanup['all_worker_identities_exited']
    assert not any(cleanup[k] for k in ('remaining_group_members', 'remaining_worker_identities', 'remaining_descendants'))
    assert len(budget['process_identities']) == clear['identities_checked'] == 4
    assert len(budget['owned_process_groups']) == clear['groups_checked'] == 3
    phase_pins = {}
    for item in budget['phase_records'].values():
        path = AM / item['path']
        assert sha(path) == item['sha256']
        value = read(path)
        assert value['status'] == 'complete' and value['exit_code'] == 0
        phase_pins[str(path.relative_to(ROOT))] = sha(path)
    assert budget['search_cpu_seconds'] + budget['confirmation_cpu_seconds'] == budget['cpu_seconds']
    processes = prior['processes'] + budget['process_identities']
    groups = prior['process_groups'] + budget['owned_process_groups']
    assert len(processes) == len({(x['pid'], x['start_ticks']) for x in processes}) == 60
    assert len(groups) == len(set(groups)) == 43
    budget_pins = prior['budget_pins'] | {
        str(path.relative_to(ROOT)): sha(path) for path in (AM / 'budget.json',)}
    source_paths = [prior_path, AM / 'terminal_review/host_clearance.json']
    resource = {
        'status': 'prior_evidence_verified_host_recheck_required',
        'verification_pid_namespace': os.readlink('/proc/self/ns/pid'),
        'required_host_pid_namespace': HOST,
        'processes': processes, 'process_groups': groups, 'budget_pins': budget_pins,
        'process_count': len(processes), 'group_count': len(groups), 'budget_count': len(budget_pins),
        'source_pins': {str(path.relative_to(ROOT)): sha(path) for path in source_paths},
        'AM_phase_budget_pins': phase_pins,
        'AM_CPU_seconds': budget['cpu_seconds'],
        'limitations': prior['limitations'] + [
            'AM phase budgets are cumulative process usage; they are verified individually but never added as independent CPU totals.',
            'This read-only receipt extends prior evidence; root must perform the final live check in the host PID namespace.'
        ], 'new_lives': 0, 'new_seed_reservations': 0,
        'review_source_sha256': sha(Path(__file__))
    }
    save('prior_resource_evidence.json', resource)

    protocol = read(AM / 'protocol.json')
    endpoints = read(AM / 'endpoints.json')
    index = read(AM / 'row_index.json')
    assert len(index) == 16
    timing = []
    for world, world_spec in protocol['worlds'].items():
        assert world_spec['world']['R_cap'] == 500
        abi = world_spec['abi']
        for i, role in enumerate(protocol['roles']):
            name = f'raw/{world}/row_{i:02d}.npz'
            path = AM / name
            entry = index[name]
            assert sha(path) == entry['sha256'] and entry['lives'] == 512 and entry['abi'] == abi
            with zipfile.ZipFile(path) as archive, archive.open('ledger.npy') as stream:
                version = np.lib.format.read_magic(stream)
                assert version in ((1, 0), (2, 0))
                header = np.lib.format.read_array_header_1_0 if version == (1, 0) else np.lib.format.read_array_header_2_0
                shape, fortran, dtype = header(stream)
            assert shape == (512, 57 if abi == 3 else 58) and dtype == np.dtype('float64') and not fortran
            with np.load(path, allow_pickle=False) as row:
                assert str(row['protocol_sha256'].item()) == sha(AM / 'protocol.json')
                assert str(row['endpoints_sha256'].item()) == sha(AM / 'endpoints.json')
                assert str(row['world_name'].item()) == world and str(row['role'].item()) == role
                assert str(row['genome_raw_sha256'].item()) == endpoints['genomes'][i]['raw_sha256']
                assert np.array_equal(row['seeds'], np.asarray(protocol['seeds'], dtype=np.uint64))
                cpu, wall = float(row['cpu_seconds']), float(row['wall_seconds'])
                assert np.isfinite([cpu, wall]).all() and min(cpu, wall) > 0
                assert cpu == entry['cpu_seconds'] and wall == entry['wall_seconds']
            timing.append({'path': str(path.relative_to(ROOT)), 'sha256': sha(path),
                           'world': world, 'role': role, 'cpu_seconds': cpu, 'wall_seconds': wall,
                           'cpu_per_life': cpu / 512, 'shape': list(shape)})
    old_path = ROOT / 'outputs/audit_capture_value_selection_20261015/operations/timing_review.json'
    old = read(old_path)
    floor = 0.2041540473847656
    # The literal is pinned to the accepted preceding review, not inferred from current outcomes.
    assert floor in [x for x in old.values() if isinstance(x, (float, int))]
    observed = max(x['cpu_per_life'] for x in timing)
    rate = max(floor, observed)
    search = 180 + 1.5 * 20534 * rate
    confirmation = 180 + 1.5 * 7680 * rate
    result = {
        'status': 'metadata_only_cost_review_passed', 'AM_timing_rows': timing,
        'historical_conservative_CPU_per_life': floor, 'observed_AM_max_CPU_per_life': observed,
        'planning_CPU_per_life': rate,
        'scope': {'search_research_lives': 20534, 'search_arms': 1,
                  'confirmation_roles': ['AM_current_start', 'generation4', 'generation8'],
                  'confirmation_worlds': ['pool', 'persistent', 'blink80_5', 'blink80_20', 'turn100_blink80_20'],
                  'confirmation_lives_per_row': 512, 'confirmation_research_lives': 7680,
                  'startup_lives': 8, 'total_calls': 28222,
                  'generation_prices': {'acquisition': 500},
                  'native_diagnostic_price': 500, 'confirmation_price': 500},
        'projection': {'formula': '180 + 1.5 * research calls * max(historical floor, observed AM row rate), separately for search and confirmation',
            'search_CPU_seconds': search, 'confirmation_CPU_seconds': confirmation,
            'combined_CPU_seconds': search + confirmation,
            'search_cap': 7200, 'confirmation_cap': 3600, 'total_cap': 10800,
            'search_stop_margin': 7190 - search, 'confirmation_stop_margin': 3590 - confirmation,
            'total_stop_margin': 10790 - search - confirmation},
        'source_pins': {str(path.relative_to(ROOT)): sha(path) for path in
            (old_path, AM / 'protocol.json', AM / 'row_index.json', AM / 'endpoints.json', AM / 'budget.json')},
        'limitations': [
            'These are conservative planning projections, not upper bounds for unseen evolving bodies. Both hard phase caps and memory limits remain necessary.',
            'All prices remain 500. Longer cue gaps and evolving bodies can have different runtimes; historical rates are only planning anchors.',
            'Old worlds retain exact AM physics. The new longer-gap and combined context exposure is audited separately; this timing receipt makes no held-out claim.',
            'Only timing and identity scalars, seeds and ledger headers were read. No outcome or genotype arrays were loaded.',
            'No current phase CPU is added to historical timing estimates; phase receipts are cumulative.'
        ], 'new_lives': 0, 'engine_builds': 0, 'genetic_draws': 0,
        'review_source_sha256': sha(Path(__file__))
    }
    assert search < 7190 and confirmation < 3590 and search + confirmation < 10790
    save('timing_review.json', result)
    print(json.dumps({'resource_sha256': sha(OUT / 'prior_resource_evidence.json'),
        'timing_sha256': sha(OUT / 'timing_review.json'), 'processes': len(processes), 'groups': len(groups),
        'budgets': len(budget_pins), 'AM_max_CPU_per_life': observed,
        'search_projection': search, 'confirmation_projection': confirmation}, indent=2))


if __name__ == '__main__':
    main()
