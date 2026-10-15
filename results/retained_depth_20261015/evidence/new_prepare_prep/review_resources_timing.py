"""AO planning: verify prior cleanup and read AN timing metadata; no scientific execution."""
import hashlib
import json
import os
from pathlib import Path
import zipfile

import numpy as np

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[2]
AN = ROOT / 'outputs/autonomous_occlusion_acquisition_20261015'
VIEWER = ROOT / 'outputs/an_watchable_20261015'
HOST = 'pid:[4026531836]'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text())


def save(name, value):
    (OUT / name).write_text(json.dumps(value, indent=2) + '\n')


def main():
    prior_path = ROOT / 'outputs/audit_occlusion_acquisition_20261015/operations/prior_resource_evidence.json'
    prior = read(prior_path)
    for name, digest in (prior['budget_pins'] | prior['source_pins']).items():
        assert sha(ROOT / name) == digest
    budget = read(AN / 'budget.json')
    clear = read(AN / 'terminal_review/host_clearance.json')
    assert budget['status'] == 'complete' and budget['exit_code'] == 0 and budget['cleanup_error'] is None
    assert clear['status'] == 'cleared' and clear['budget_sha256'] == sha(AN / 'budget.json')
    assert budget['pid_namespace'] == clear['pid_namespace'] == HOST
    assert not clear['remaining_identities'] and not clear['remaining_group_members']
    assert not budget['running'] and not budget['queued']
    cleanup = budget['terminal_cleanup']
    assert cleanup['checked_in_monitor'] and cleanup['same_pid_namespace']
    assert cleanup['all_owned_groups_exited'] and cleanup['all_worker_identities_exited']
    assert not any(cleanup[k] for k in ('remaining_group_members', 'remaining_worker_identities', 'remaining_descendants'))
    assert len(budget['process_identities']) == clear['identities_checked'] == 3
    assert len(budget['owned_process_groups']) == clear['groups_checked'] == 2
    phase_pins = {}
    for item in budget['phase_records'].values():
        path = AN / item['path']
        assert sha(path) == item['sha256']
        value = read(path)
        assert value['status'] == 'complete' and value['exit_code'] == 0
        phase_pins[str(path.relative_to(ROOT))] = sha(path)
    assert budget['search_cpu_seconds'] + budget['confirmation_cpu_seconds'] == budget['cpu_seconds']
    vb = read(VIEWER / 'validation_budget.json')
    vc = read(VIEWER / 'host_cleanup.json')
    assert vb['status'] == 'complete' and vb['exit_code'] == 0 and vb['cleanup_error'] is None
    assert vb['all_processes_exited'] and not vb['running'] and not vb['queued']
    assert vb['js_replay_lives'] == 6 and vb['new_C_lives'] == vb['new_research_lives'] == 0
    assert vc['status'] == 'cleared' and vc['budget_sha256'] == sha(VIEWER / 'validation_budget.json')
    assert vc['wrapper_completed'] and vc['pid_namespace'] == vb['pid_namespace'] == HOST
    assert not vc['remaining_identities'] and not vc['remaining_group_members']
    assert len(vb['processes']) == vc['identities_checked'] == 1
    assert len(vb['process_groups']) == vc['groups_checked'] == 1
    processes = prior['processes'] + budget['process_identities'] + vb['processes']
    groups = prior['process_groups'] + budget['owned_process_groups'] + vb['process_groups']
    assert len(processes) == len({(x['pid'], x['start_ticks']) for x in processes}) == 64
    assert len(groups) == len(set(groups)) == 46
    budget_pins = prior['budget_pins'] | {str(path.relative_to(ROOT)): sha(path)
        for path in (AN / 'budget.json', VIEWER / 'validation_budget.json')}
    assert len(budget_pins) == 23
    resource = {'status': 'prior_evidence_verified_host_recheck_required',
        'verification_pid_namespace': os.readlink('/proc/self/ns/pid'), 'required_host_pid_namespace': HOST,
        'processes': processes, 'process_groups': groups, 'budget_pins': budget_pins,
        'process_count': len(processes), 'group_count': len(groups), 'budget_count': len(budget_pins),
        'source_pins': {str(path.relative_to(ROOT)): sha(path) for path in
            (prior_path, AN / 'terminal_review/host_clearance.json', VIEWER / 'host_cleanup.json')},
        'AN_phase_budget_pins': phase_pins, 'AN_CPU_seconds': budget['cpu_seconds'],
        'AN_viewer_engineering_CPU_seconds': vb['cpu_seconds'],
        'limitations': prior['limitations'] + [
            'AN phase budgets are cumulative process usage, verified but never summed as independent totals.',
            'The six AN viewer replays are separate engineering uses of existing seeds, not research lives.',
            'Root must perform the final live check in the original host PID namespace.'
        ], 'new_lives': 0, 'new_seed_reservations': 0, 'review_source_sha256': sha(Path(__file__))}
    save('prior_resource_evidence.json', resource)

    protocol, endpoints, index = (read(AN / name) for name in ('protocol.json', 'endpoints.json', 'row_index.json'))
    assert len(index) == 15
    timing = []
    for world, world_spec in protocol['worlds'].items():
        assert world_spec['world']['R_cap'] == 500
        abi = world_spec['abi']
        for i, role in enumerate(protocol['roles']):
            name = f'raw/{world}/row_{i:02d}.npz'
            path = AN / name
            entry = index[name]
            assert sha(path) == entry['sha256'] and entry['lives'] == 512 and entry['abi'] == abi
            with zipfile.ZipFile(path) as archive, archive.open('ledger.npy') as stream:
                version = np.lib.format.read_magic(stream)
                assert version in ((1, 0), (2, 0))
                header = np.lib.format.read_array_header_1_0 if version == (1, 0) else np.lib.format.read_array_header_2_0
                shape, fortran, dtype = header(stream)
            assert shape == (512, 57 if abi == 3 else 58) and dtype == np.dtype('float64') and not fortran
            with np.load(path, allow_pickle=False) as row:
                assert str(row['protocol_sha256'].item()) == sha(AN / 'protocol.json')
                assert str(row['endpoints_sha256'].item()) == sha(AN / 'endpoints.json')
                assert str(row['world_name'].item()) == world and str(row['role'].item()) == role
                assert str(row['genome_raw_sha256'].item()) == endpoints['genomes'][i]['raw_sha256']
                assert np.array_equal(row['seeds'], np.asarray(protocol['seeds'], dtype=np.uint64))
                cpu, wall = float(row['cpu_seconds']), float(row['wall_seconds'])
                assert np.isfinite([cpu, wall]).all() and min(cpu, wall) > 0
                assert cpu == entry['cpu_seconds'] and wall == entry['wall_seconds']
            timing.append({'path': str(path.relative_to(ROOT)), 'sha256': sha(path), 'world': world, 'role': role,
                'cpu_seconds': cpu, 'wall_seconds': wall, 'cpu_per_life': cpu / 512, 'shape': list(shape)})
    old_path = ROOT / 'outputs/audit_occlusion_acquisition_20261015/operations/timing_review.json'
    old = read(old_path)
    historical_rate = old['historical_conservative_CPU_per_life']
    assert historical_rate == 0.2041540473847656
    # Root accepted phase scaling for this bounded exploratory pair. Keep the failing old model visible.
    search_direct = budget['search_cpu_seconds'] * 6
    confirmation_direct = budget['confirmation_cpu_seconds'] * 2
    search_padded, confirmation_padded = search_direct * 1.5, confirmation_direct * 1.5
    historical_search = 180 + 1.5 * 123116 * historical_rate
    historical_confirmation = 180 + 1.5 * 15360 * historical_rate
    assert search_padded < 23990 and confirmation_padded < 4790
    assert search_padded + confirmation_padded < 28790
    assert historical_search > 24000
    result = {'status': 'metadata_only_measured_phase_projection_fits_hard_caps', 'AN_timing_rows': timing,
        'historical_conservative_CPU_per_life': historical_rate,
        'observed_AN_max_CPU_per_life': max(x['cpu_per_life'] for x in timing),
        'scope': {'search_research_lives': 123116, 'search_arms': 2, 'generations_per_arm': 24,
            'search_research_lives_per_arm': 61558, 'confirmation_roles': ['AM_reference', 'AN_start', 'unchanged8', 'unchanged24', 'balanced8', 'balanced24'],
            'confirmation_worlds': list(protocol['worlds']), 'confirmation_lives_per_row': 512,
            'confirmation_research_lives': 15360, 'startup_lives': 12, 'total_calls': 138488,
            'all_prices': 500},
        'projection': {'basis': 'Complete AN process-phase CPU, including startup, compilation and overhead; sixfold search (two arms times threefold duration) and twofold confirmation roles.',
            'AN_search_CPU_seconds': budget['search_cpu_seconds'], 'AN_confirmation_CPU_seconds': budget['confirmation_cpu_seconds'],
            'search_multiplier': 6, 'confirmation_multiplier': 2, 'uncertainty_multiplier': 1.5,
            'search_direct_CPU_seconds': search_direct, 'confirmation_direct_CPU_seconds': confirmation_direct,
            'search_CPU_seconds': search_padded, 'confirmation_CPU_seconds': confirmation_padded,
            'combined_CPU_seconds': search_padded + confirmation_padded,
            'search_cap': 24000, 'confirmation_cap': 4800, 'total_cap': 28800,
            'search_stop_margin': 23990 - search_padded, 'confirmation_stop_margin': 4790 - confirmation_padded,
            'total_stop_margin': 28790 - search_padded - confirmation_padded},
        'historical_pessimistic_projection': {'formula': '180 + 1.5 * research calls * 0.2041540473847656, per phase',
            'search_CPU_seconds': historical_search, 'confirmation_CPU_seconds': historical_confirmation,
            'combined_CPU_seconds': historical_search + historical_confirmation,
            'fits_search_cap': historical_search <= 24000, 'fits_confirmation_cap': historical_confirmation <= 4800,
            'interpretation': 'This older per-life floor does not pass. It remains an explicit runtime risk, not a claimed feasibility gate.'},
        'source_pins': {str(path.relative_to(ROOT)): sha(path) for path in
            (old_path, AN / 'protocol.json', AN / 'row_index.json', AN / 'endpoints.json', AN / 'budget.json')},
        'limitations': [
            'Parent explicitly accepted measured complete AN phase scaling for a bounded exploratory pair under unchanged hard caps; this is not a guarantee.',
            'AN ended with smaller bodies, but a balanced allocation can regrow bodies and costs can increase over 24 generations.',
            'Unseen body costs and stochastic compiler/runtime overhead can exhaust search or confirmation caps. No retry, arm dropping, scope shrinking or cap extension is allowed.',
            'Only timing and identity scalars, seeds and ledger headers were read here. No outcome or genotype arrays were loaded.',
            'Both arms use the same five known world definitions and fixed prices; equal life counts do not imply equal CPU.'
        ], 'new_lives': 0, 'engine_builds': 0, 'genetic_draws': 0, 'review_source_sha256': sha(Path(__file__))}
    save('timing_review.json', result)
    print(json.dumps({'resource_sha256': sha(OUT / 'prior_resource_evidence.json'), 'timing_sha256': sha(OUT / 'timing_review.json'),
        'processes': len(processes), 'groups': len(groups), 'budgets': len(budget_pins),
        'search_projection': search_padded, 'confirmation_projection': confirmation_padded,
        'historical_search_projection': historical_search, 'historical_confirmation_projection': historical_confirmation}, indent=2))


if __name__ == '__main__':
    main()
