"""Read-only prepared AO review; NumPy/YAML and AST only, no engine imports or draws."""
import argparse
import ast
import copy
import hashlib
import json
import sys
from pathlib import Path

import numpy as np
import yaml
from audit_namespace import derive_native_ids

ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent
STUDY = ROOT / 'outputs/autonomous_retained_depth_20261015'
ARMS = ['unchanged', 'balanced']
ROLES = ['AM_reference', 'AN_start', 'unchanged8', 'unchanged24', 'balanced8', 'balanced24']
PATTERNS = {'unchanged': ['pool', 'persistent', 'blink80_20', 'blink80_20'] * 2,
            'balanced': ['pool', 'persistent', 'pool', 'blink80_20'] * 2}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text())


def raw_sha(array):
    return hashlib.sha256(array.tobytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--protocol-sha', required=True)
    protocol_sha = parser.parse_args().protocol_sha
    assert sha(STUDY / 'protocol.json') == protocol_sha
    p = read(STUDY / 'protocol.json')
    pin_counts = {}
    for key, base in [('source_pins', STUDY), ('input_pins', STUDY), ('production_pins', ROOT),
                      ('original_input_pins', ROOT), ('review_pins', ROOT)]:
        for name, digest in p[key].items():
            path = (base / name).resolve()
            assert path.is_relative_to(base.resolve()) and sha(path) == digest, name
        pin_counts[key] = len(p[key])
    assert all(not (STUDY / name).exists() for name in ('release.json', 'attempt.json', 'execution', 'build-cache', 'raw', 'runs'))
    pop, record = read(STUDY / 'inputs/input_population.json'), p['population_start']
    public = ROOT / 'results/occlusion_acquisition_20261015'
    assert sha(STUDY / 'inputs/input_population.json') == record['file_sha256']
    assert sha(public / 'runs/acquisition/population.json') == record['file_sha256']
    tree = ast.parse((ROOT / 'src/genome.py').read_text())
    fields = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == '_life_fields')
    order = [ast.literal_eval(call.args[0]) for call in fields.body[1].value.elts]
    shapes = {'W': (16, 25), 'b': (16,), 'lam': (16,), 's0': (16,), 'Q': (16,),
              'act': (16,), 'A': (23, 16), 'a0': (23,), 'Dm': (2,), 'km': (2,)}

    def flatten(params):
        arrays = [np.asarray(params[key], dtype=np.float32) for key in order]
        assert all(a.shape == shapes[k] for k, a in zip(order, arrays))
        return np.concatenate([a.ravel() for a in arrays])

    table = np.stack([flatten(row) for row in pop['genomes']])
    assert table.shape == (32, 875) and np.isfinite(table).all()
    hashes = [raw_sha(row) for row in table]
    assert hashes == record['row_sha256'] and raw_sha(table) == record['population_raw_sha256']
    assert record['old_ids'] == pop['ids'] and len(set(pop['ids'])) == 32 and record['new_ids'] == list(range(32))
    assert record['old_to_new'] == [{'old_id': old, 'new_id': i, 'row': i, 'raw_sha256': hashes[i]}
                                  for i, old in enumerate(pop['ids'])]
    for key, role in [('reference', 'AN_start'), ('ancestral_reference', 'AM_reference')]:
        ref = p[key]
        value = read(STUDY / ref['path'])
        flat = flatten(value['params'])
        assert ref['role'] == role and raw_sha(flat) == ref['raw_sha256'] and np.isfinite(flat).all()
        assert sha(STUDY / ref['path']) == ref['file_sha256'] == sha(ROOT / ref['source'])
        if key == 'reference':
            assert flat.tobytes() == table[0].tobytes()
        else:
            assert sha(STUDY / ref['path']) == sha(public / 'inputs/AM_current_start.json')
    prior_audit = read(STUDY / 'inputs/AN_native_audit.json')
    prior_protocol = read(STUDY / 'inputs/AN_protocol.json')
    assert prior_audit['status'] == 'passed' and prior_audit['protocol_sha256'] == sha(STUDY / 'inputs/AN_protocol.json')
    prior = prior_audit['runs']['acquisition']
    assert prior['all_32_final_rows_bound'] and prior['genetic_replay']['raw_population_replay_bitwise']
    assert prior['checkpoint_sha256'] == sha(STUDY / 'inputs/AN_checkpoint.pt')
    assert read(STUDY / 'inputs/AN_summary.json')['status'] == 'complete'
    configs = {arm: yaml.safe_load((STUDY / p['configs'][arm]['path']).read_text()) for arm in ARMS}
    selection_tree = ast.parse((STUDY / 'selection.py').read_text())
    rule = next(ast.literal_eval(n.value) for n in selection_tree.body if isinstance(n, ast.Assign)
                and any(isinstance(t, ast.Name) and t.id == 'RULE' for t in n.targets))
    old_cfg = yaml.safe_load((STUDY / 'inputs/AN_config.yaml').read_text())
    for arm, cfg in configs.items():
        assert sha(STUDY / p['configs'][arm]['path']) == p['configs'][arm]['sha256']
        assert cfg['seed'] == p['native_seed'] == 53232 and cfg['threads'] == 2
        e, life = cfg['evolve'], cfg['life']
        assert (e['mu'], e['lam'], e['generations'], e['heldout_every'], e['recheck_k'], e['recheck_lives']) == (32, 224, 24, 4, 64, 8)
        assert e['recheck_key'] == 'all' and e['dup_rate'] == e['del_rate'] == 0 and not e['dup_split']
        assert (life['abi'], life['lives'], life['valid_lives'], life['final_lives'], life['final_top'], life['T']) == (4, 8, 16, 2, 1, 1024)
        assert life['extinct_charge'] and life['fast_kernel'] and not life['heldout'] and not life['size_curve']
        assert not life['T_choices'] and not life['flags'] and life['t_open'] == 0 and life['freeze_frac'] is None
        assert not cfg['clones']['every'] and not cfg['clones']['conditions'] and not cfg['envelope']['enabled']
        assert cfg['costs_life'] == {} and 'exploratory_reserve' not in cfg
        assert cfg['population_start'] == {'version': 1, **record,
            'source_pins': {name: sha(STUDY / name) for name in ('population_loader.py', 'search.py')}}
        assert e['seed_genome'] == str(STUDY / record['population_file'])
        assert cfg['retention_selection'] == {'version': 1, 'arm': arm, 'worlds': p['selection_worlds'],
            'rule': rule, 'pattern': PATTERNS[arm], 'source_pins': {'selection.py': sha(STUDY / 'selection.py')}}
        expected = copy.deepcopy(old_cfg)
        for key in ('seed', 'population_start', 'retention_selection'):
            expected[key] = cfg[key]
        expected['evolve']['generations'] = 24
        expected['evolve']['seed_genome'] = cfg['evolve']['seed_genome']
        expected['logging']['output_dir'] = cfg['logging']['output_dir']
        expected['life']['control'] = 'retained_depth_AO'
        assert expected == cfg
    assert list(p['worlds']) == ['pool', 'persistent', 'blink80_5', 'blink80_20', 'turn100_blink80_20']
    assert p['worlds'] == prior_protocol['worlds']
    spec_tree = ast.parse((ROOT / 'src/life/spec.py').read_text())
    world = next(node for node in spec_tree.body if isinstance(node, ast.ClassDef) and node.name == 'World')
    keys = [node.target.id for node in world.body if isinstance(node, ast.AnnAssign)
            and node.target.id not in ('name', 'stage', 'implemented', 'lattice', 'lives')]
    assert len(keys) == 70
    for name, world0 in p['worlds'].items():
        assert world0['world']['R_cap'] == 500 and world0['world']['T'] == 1024
        assert world0['abi'] == (3 if name in ('pool', 'persistent') else 4)
        expected_keys = keys[:66] if world0['abi'] == 3 else keys
        vector = np.asarray([world0['world'][key] for key in expected_keys], dtype=np.float64)
        assert vector.tobytes() == np.asarray(world0['world_vector'], dtype=np.float64).tobytes()
        assert len(world0['ledger_columns']) == (57 if world0['abi'] == 3 else 58)
    assert p['selection_worlds'] == {key: p['worlds'][key]['world'] for key in ('pool', 'persistent', 'blink80_20')}
    audit = read(STUDY / 'inputs/seed_audit.json')
    native_rows, native_ids = derive_native_ids()
    assert audit['native_records'] == native_rows and len(native_ids) == 500
    assert audit['run_life_seeds'] == {arm: [row['seed'] for row in native_rows] for arm in ARMS}
    assert p['seeds'] == audit['confirmation_seeds'] == list(range(52420000, 52420512))
    assert not native_ids.intersection(p['seeds'])
    assert (p['research_lives'], p['startup_lives'], p['total_calls']) == (138476, 12, 138488)
    assert p['search'] == {'arms': ARMS, 'generations': 24, 'research_lives_per_arm': 61558,
        'startup_lives_per_arm': 4, 'initial_lives': 8, 'recheck_lives': 8, 'parents': 32, 'offspring': 224}
    assert p['confirmation_lives'] == 6 * 5 * 512 == 15360 and p['confirmation_startup_lives'] == 4
    expected_budget = {'cpu_seconds': 28800, 'wall_seconds': 14400, 'search_cpu_seconds': 24000,
        'confirmation_cpu_seconds': 4800, 'threads': 2, 'workers': 1, 'cleanup_margin_seconds': 10,
        'rss_bytes': 4 * 1024**3, 'minimum_available_bytes': 4 * 1024**3, 'address_space_bytes': 8 * 1024**3}
    assert p['budget'] == expected_budget
    timing = read(OUT / 'timing_review.json')
    assert sha(OUT / 'timing_review.json') == '91318c138b452d8e5ad369fb9075e3eb01aec1cb82578ba98f65b679b1dceff6'
    assert timing['scope']['search_research_lives'] == 123116 and timing['scope']['confirmation_research_lives'] == 15360
    assert p['roles'] == ROLES and p['runs'] == ARMS and p['study'] == 'AO retained-depth comparison'
    assert p['primary'] == [{'world': w, 'new': 'balanced24', 'old': 'unchanged24', 'metric': 'captures'} for w in ('pool', 'blink80_20')]
    assert p['primary_noninferiority'] == {'world': 'blink80_20', 'new': 'balanced24', 'old': 'unchanged24', 'metric': 'captures', 'retained_fraction': .9}
    assert p['retention_margin_fraction'] == .1
    assert p['expected_numerical_identity'] == read(STUDY / 'inputs/startup_identity.json')['identity']
    assert not any(name.startswith('src') or name == 'torch' for name in sys.modules)
    receipt = {'status': 'passed_actual_prepared_inputs', 'protocol_sha256': protocol_sha, 'pin_counts': pin_counts,
        'population_shape': [32, 875], 'population_raw_sha256': raw_sha(table), 'ordered_rows_checked': 32,
        'new_ids': list(range(32)), 'old_ids': pop['ids'], 'row0_old_id': pop['ids'][0],
        'only_declared_public_AN_config_differences': True, 'exact_immutable_AM_reference': True,
        'native_unique_ids_per_arm': 500, 'native_arm_count': 2, 'native_IDs_deliberately_shared': True,
        'confirmation_ids': 512, 'confirmation_ids_shared_across_all_roles_and_worlds': True,
        'worlds': {name: {'abi': w['abi'], 'world_size': len(w['world_vector']), 'ledger_size': len(w['ledger_columns'])} for name, w in p['worlds'].items()},
        'all_five_worlds_exact_prior_AN': True, 'selection_patterns': PATTERNS, 'budget': p['budget'],
        'research_lives': 138476, 'startup_lives': 12, 'total_calls': 138488,
        'measured_phase_search_projection_cpu_seconds': timing['projection']['search_CPU_seconds'],
        'measured_phase_confirmation_projection_cpu_seconds': timing['projection']['confirmation_CPU_seconds'],
        'historical_pessimistic_projection': timing['historical_pessimistic_projection'],
        'simulation_calls': 0, 'engine_imports': False, 'engine_builds': 0, 'genetic_draws': 0,
        'review_script_sha256': sha(Path(__file__)), 'source_pins': p['source_pins'],
        'evidence_pins': {name: sha(OUT / name) for name in ('seed_audit.json', 'producer_operations_source_review.json', 'timing_review.json')},
        'limitations': ['Historical prices, worlds and rules remain fixed; only allocation and longer duration are studied.',
            'The old pessimistic runtime model exceeds caps. Actual AN phase scaling fits; hard caps decide completion if bodies regrow.',
            'All 32 ordered rows are exact, but old fitness/RNG/IDs are not resumed.',
            'All worlds are development-known; captures and economy are distinct outcomes, and neither implies memory or anatomical sophistication.']}
    (OUT / 'actual_input_review.json').write_text(json.dumps(receipt, indent=2) + '\n')
    print(json.dumps({'status': 'passed', 'receipt_sha256': sha(OUT / 'actual_input_review.json'), 'pins': pin_counts, 'rows': 32}))


if __name__ == '__main__':
    main()
