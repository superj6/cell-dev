"""Retained U integer schedule and visibility inventory, proposal only; no engine imports."""
from __future__ import annotations
import hashlib
import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent
RUNS = (53220, 53221)
CONFIRMATION = list(range(52_200_000, 52_200_512))


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main():
    helper_path = ROOT / 'outputs/audit_decoy_evolution_20261014/check_seed_world.py'
    helper = load('retained_U_namespace', helper_path)
    records = {str(run): helper.schedule(run, generations=4) for run in RUNS}
    lists = {run: [row['seed'] for row in values] for run, values in records.items()}
    spec_source = ROOT / 'src/life/spec.py'
    eval_source = ROOT / 'src/life/evaluate.py'
    extracted = helper.source_functions(spec_source, ('splitmix64', 'hash64'), {'MASK64': helper.MASK})
    scope = type('SpecScope', (), {'hash64': staticmethod(extracted['hash64'])})()
    life_seed = helper.source_functions(eval_source, ('life_seed',),
        {'spec': scope, '_SEED_STREAM': helper.SEED_STREAM, 'PURPOSES': helper.PURPOSES})['life_seed']
    for run, values in records.items():
        assert len(values) == len({v['seed'] for v in values}) == 64
        assert all(v['seed'] == life_seed(int(run), v['purpose'], v['index'], v['life']) for v in values)
    hashed = {x for values in lists.values() for x in values}
    assert len(hashed) == 128 and not hashed.intersection(CONFIRMATION) and 11 not in hashed | set(CONFIRMATION)
    prior_path = ROOT / 'results/decoy_evolution_20261014/sources/seed_review/namespace_lists.json'
    prior = json.loads(prior_path.read_text())
    prior_hashed = {x for values in prior['historical_hashed'].values() for x in values}
    prior_hashed.update(row['seed'] for values in prior['U_records_by_run'].values() for row in values)
    assert not hashed.intersection(prior_hashed)
    inventory_path = ROOT / 'outputs/audit_visibility_information_20261014/inventory.py'
    inventory = load('retained_visibility_inventory', inventory_path)
    inventory.OUT = OUT
    inventory.RANGES = [(52_200_000, 52_210_000), (RUNS[0], RUNS[-1] + 1)] + [(x, x + 1) for x in sorted(hashed)]
    result = inventory.inventory()
    result['candidate_block_ids'] = [120]
    result['candidate_native_run_seeds'] = list(RUNS)
    result['additional_ranges_are_singleton_native_hashes'] = True
    result['engine_modules_imported'] = any(name.startswith('src.') for name in sys.modules)
    assert not result['engine_modules_imported']
    result['retained_inventory_sha256'] = sha(inventory_path)
    (OUT / 'namespace_inventory.json').write_text(json.dumps(result, indent=2) + '\n')
    namespace = {'status': 'proposed_not_reserved', 'simulation_calls': 0,
        'runs': list(RUNS), 'run_life_seeds': lists, 'records_by_run': records,
        'confirmation_seeds': CONFIRMATION, 'confirmation_block': 120,
        'confirmation_base': 51_000_000, 'confirmation_stride': 10_000,
        'unique_selection_ids_per_run': 28, 'unique_periodic_validation_ids_per_run': 32,
        'unique_final_ids_per_run': 4, 'unique_native_ids_total': 128,
        'search_lives': 8268, 'confirmation_lives': 3072, 'research_lives': 11340,
        'existing_startup_golden': {'seed': 11, 'abi': 3, 'T': 200, 'calls': 6},
        'intentional_reuse': ['Generation gen0..3 share each initial/recheck life across candidates.',
            'Each final0 two-seed set is used at T1024 and T512; final1 is the two-seed redraw.',
            'All six fixed confirmation roles share the same512 seeds.',
            'Existing startup seed11 is the only deliberately repeated historical golden.'],
        'validation_block_reserved': False, 'seed_reservations': [],
        'prior_native_hashed_count': len(prior_hashed), 'prior_native_hashed_overlap': 0,
        'source_pins': {str(p.relative_to(ROOT)): sha(p) for p in (helper_path, inventory_path, prior_path, spec_source, eval_source)},
        'inventory_sha256': sha(OUT / 'namespace_inventory.json'), 'review_script_sha256': sha(__file__)}
    (OUT / 'namespace_lists.json').write_text(json.dumps(namespace, indent=2) + '\n')
    print(json.dumps({'status': 'inventory_finished_pending_match_review', 'matches': len(result['numeric_matches']),
        'json_files': result['json_files_scanned'], 'npz_files': result['npz_files_inspected'],
        'npz_seed_arrays': result['npz_seed_arrays_scanned'],
        'real_json_errors': [x for x in result['malformed_json'] if not x['synthetic_fixture']],
        'real_npz_errors': [x for x in result['npz_errors'] if not x['synthetic_fixture']],
        'reserved': False, 'simulation_calls': 0}))


if __name__ == '__main__':
    main()
