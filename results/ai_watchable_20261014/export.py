"""Draft export for completed AI; default is source-only and opens no AI artifacts."""
import argparse
import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
PROTOCOL = '0dc385199dc871a86f7a31a62c393b2c160f0cbae018ceece3ec8f51bb6dff00'
LABELS = ['AE_L92', 'AI_control', 'AI_reserve']
SEED = 52360000


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text())


def operation(base, name):
    return base / name if (base / name).exists() else base / 'operations' / name


def export(base, authorization):
    approved = read(authorization)
    assert approved['status'] == 'authorized_AI_viewer_export_and_three_JS_checks'
    assert approved['protocol_sha256'] == PROTOCOL
    required = ['export.py', 'viewer.js', 'template.html', 'check_replay.js', 'run_validation.py', 'build.py']
    assert set(required).issubset(approved['source_pins'])
    for name, digest in approved['source_pins'].items():
        assert (HERE / name).resolve().is_relative_to(HERE) and sha(HERE / name) == digest
    assert not any((HERE / n).exists() for n in ('bodies.json', 'truth.json', 'export_receipt.json'))
    protocol_path, summary_path = base / 'protocol.json', base / 'analysis_result/summary.json'
    clear_path, budget_path = operation(base, 'terminal_process_clearance.json'), operation(base, 'budget.json')
    assert sha(protocol_path) == PROTOCOL
    for path, key in [(summary_path, 'summary_sha256'), (clear_path, 'terminal_clearance_sha256'), (budget_path, 'budget_sha256')]:
        assert sha(path) == approved[key], key
    p, summary, clearance, budget = map(read, (protocol_path, summary_path, clear_path, budget_path))
    assert summary['status'] == budget['status'] == 'complete' and summary['protocol_sha256'] == PROTOCOL
    assert clearance['all_processes_exited'] is True and clearance['budget_sha256'] == sha(budget_path)
    assert not budget.get('running') and not budget.get('queued') and not budget.get('cleanup_error')
    assert p['confirmation']['labels'] == LABELS and p['confirmation']['seeds'][0] == SEED
    assert len(p['confirmation']['seeds']) == 512 and summary['seeds'] == p['confirmation']['seeds']
    for name, digest in p['production_pins'].items():
        assert sha(ROOT / name) == digest, name
    import numpy as np
    sys.path.insert(0, str(ROOT))
    from src.life import spec
    endpoint_path, genotype_path = base / 'confirmation/endpoints.json', base / 'confirmation/genotypes.npz'
    endpoints = read(endpoint_path)
    assert endpoints['labels'] == LABELS and endpoints['seeds'] == summary['seeds']
    assert endpoints['protocol_sha256'] == PROTOCOL
    for path in [endpoint_path, genotype_path, base / 'confirmation/row_index.json']:
        assert sha(path) == summary['input_pins'][str(path.relative_to(base))]
    with np.load(genotype_path, allow_pickle=False) as saved:
        raw = saved['genomes'].copy()
        assert saved['labels'].tolist() == LABELS
    assert raw.shape == (3, 875) and raw.dtype == np.float32
    atlas_path, engine_path = ROOT / 'results/atlas/play/bodies.json', ROOT / 'results/atlas/play/lifesim.js'
    atlas = read(atlas_path)
    assert sha(engine_path) == read(HERE / 'source_origins.json')['unchanged_engine']['sha256']
    world = {k: p['world'][k] for k in spec.V3.WORLD_KEYS}
    assert world['drag_exp'] == atlas['drag']['drag_exp'] and world['T'] == 1024
    packed = spec.V3.pack_genomes(raw, 'hexprism')
    bodies, truth = [], []
    paths = [authorization, protocol_path, summary_path, clear_path, budget_path, endpoint_path, genotype_path,
             base / 'confirmation/row_index.json', atlas_path, engine_path, ROOT / 'src/life/spec.py']
    row_index = read(base / 'confirmation/row_index.json')
    for i, role in enumerate(LABELS):
        digest = hashlib.sha256(raw[i].tobytes()).hexdigest()
        assert digest == endpoints['genotype_sha256'][role]
        bodies.append({'name': role, 'abi': 3, 'mode': 'grn', 'world': world,
                       'genome': packed[i].tolist(), 'genotype_sha256': digest})
        name = f'persistent/row_{i:04d}.npz'
        path = base / 'confirmation' / name
        assert sha(path) == row_index[name]['sha256'] == summary['input_pins']['confirmation/' + name]
        paths.append(path)
        with np.load(path, allow_pickle=False) as row:
            assert row['ledger'].shape == (512, 57) and row['ledger'].dtype == np.float64
            assert row['seeds'].tolist() == summary['seeds'] and int(row['genome_index']) == i
            assert json.loads(str(row['identity'])) == {'protocol_sha256': PROTOCOL, 'stage': 'confirmation',
                    'endpoints_sha256': sha(endpoint_path), 'role': role, 'genome_index': i,
                    'genome_sha256': digest, 'seeds': summary['seeds']}
            truth.append({'role': role, 'seed': SEED, 'ledger': row['ledger'][0].tolist(),
                          'ledger_hex': [float(x).hex() for x in row['ledger'][0]], 'source_sha256': sha(path)})
    doc = {'abi': 3, 'seed': SEED, 'bodies': bodies, 'drag': atlas['drag'], 'lattice': atlas['lattice'],
           'genome_slices': atlas['genome_slices'], 'summary': summary['contrasts'],
           'source_summary_sha256': sha(summary_path)}
    receipt = {'status': 'exported_without_simulation', 'source_pins': {str(x.resolve()): sha(x) for x in paths},
               'draft_source_pins': approved['source_pins'], 'seed_policy': 'Predetermined first confirmation seed; no outcome-based choice.',
               'labels': LABELS, 'seed': SEED, 'simulated_lives': 0, 'genetic_draws': 0, 'compiled_libraries': 0}
    for name, value in [('bodies.json', doc), ('truth.json', {'seed': SEED, 'cases': truth, 'ledger': list(spec.V3.LEDGER)}),
                        ('export_receipt.json', receipt)]:
        with (HERE / name).open('x') as stream:
            stream.write(json.dumps(value, separators=(',', ':'), allow_nan=False) + '\n')
    print(json.dumps({'status': 'exported', 'roles': LABELS, 'seed': SEED, 'simulated_lives': 0}))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--export', action='store_true')
    parser.add_argument('--study', type=Path)
    parser.add_argument('--authorization', type=Path)
    args = parser.parse_args()
    if not args.export:
        print(json.dumps({'status': 'source_only_unreleased', 'AI_outcomes_read': False, 'simulated_lives': 0}))
        return
    if args.study is None or args.authorization is None:
        parser.error('explicit completed --study and root --authorization are required')
    export(args.study.resolve(), args.authorization.resolve())


if __name__ == '__main__':
    main()
