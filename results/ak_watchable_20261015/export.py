"""Export six retained AK illustrations only after explicit pinned authorization."""
import argparse
import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
PROTOCOL = '0b41f8f98d00536c2333389245c8866d568300c6151316801794200b5e5b56b3'
LABELS = ['L92', 'AE_L92', 'AI_control']
WORLDS = ['pool', 'persistent']
SEED = 52380000


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text())


def operation(base, name):
    return base / name if (base / name).exists() else base / 'operations' / name


def export(base, authorization):
    approved = read(authorization)
    assert approved['status'] == 'authorized_AK_viewer_export_and_six_JS_checks'
    assert approved['protocol_sha256'] == PROTOCOL
    required = ['export.py', 'viewer.js', 'template.html', 'check_replay.js', 'run_validation.py', 'build.py', 'test_viewer.js']
    assert set(required).issubset(approved['source_pins'])
    for name, digest in approved['source_pins'].items():
        assert (HERE / name).resolve().is_relative_to(HERE) and sha(HERE / name) == digest
    assert not any((HERE / n).exists() for n in ('bodies.json', 'truth.json', 'export_receipt.json'))
    protocol_path, summary_path = base / 'protocol.json', base / 'analysis/summary.json'
    clear_path, budget_path = operation(base, 'terminal_clearance.json'), operation(base, 'budget.json')
    assert sha(protocol_path) == PROTOCOL
    for path, key in [(summary_path, 'summary_sha256'), (clear_path, 'terminal_clearance_sha256'), (budget_path, 'budget_sha256')]:
        assert sha(path) == approved[key], key
    p, summary, clearance, budget = map(read, (protocol_path, summary_path, clear_path, budget_path))
    assert summary['status'] == budget['status'] == 'complete' and summary['protocol_sha256'] == PROTOCOL
    assert clearance['status'] == 'cleared' and clearance['budget_sha256'] == sha(budget_path)
    assert not clearance['remaining_identities'] and not clearance['remaining_group_members']
    assert not budget.get('running') and not budget.get('queued') and not budget.get('cleanup_error')
    assert p['roles'] == LABELS and p['seeds'] == list(range(SEED, SEED + 256))
    for name, digest in p['production_pins'].items():
        assert sha(ROOT / name) == digest, name
    import numpy as np
    sys.path.insert(0, str(ROOT))
    from src.genome import Layout
    from src.life import spec
    raw = []
    paths = [authorization, protocol_path, summary_path, clear_path, budget_path, base / 'row_index.json']
    for role, rec in zip(LABELS, p['genomes'], strict=True):
        path = base / rec['path']
        assert rec['role'] == role and sha(path) == rec['file_sha256'] == p['input_pins'][rec['path']]
        _, genome = Layout.load(path)
        values = genome.numpy()
        assert values.shape == (875,) and values.dtype == np.float32
        assert hashlib.sha256(values.tobytes()).hexdigest() == rec['raw_sha256']
        raw.append(values)
        paths.append(path)
    atlas_path, engine_path = ROOT / 'results/atlas/play/bodies.json', ROOT / 'results/atlas/play/lifesim.js'
    atlas = read(atlas_path)
    assert sha(engine_path) == read(HERE / 'source_origins.json')['unchanged_engine']['sha256']
    paths += [atlas_path, engine_path, ROOT / 'src/life/spec.py']
    packed = spec.V3.pack_genomes(np.stack(raw), 'hexprism')
    index = read(base / 'row_index.json')
    assert sha(base / 'row_index.json') == summary['input_pins']['row_index.json']
    bodies, truth, groups = [], [], {}
    for world_name in WORLDS:
        definition = p['worlds'][world_name]
        assert definition['abi'] == 3 and definition['ledger_columns'] == list(spec.V3.LEDGER)
        world = {k: definition['world'][k] for k in spec.V3.WORLD_KEYS}
        assert spec.V3.pack_world(spec.World(**definition['world'])).tolist() == definition['world_vector']
        assert world['T'] == 1024 and world['drag_exp'] == atlas['drag']['drag_exp']
        groups[world_name] = []
        for i, role in enumerate(LABELS):
            body_index = len(bodies)
            groups[world_name].append(body_index)
            digest = p['genomes'][i]['raw_sha256']
            bodies.append({'name': world_name + '__' + role, 'role': role, 'world_name': world_name,
                'abi': 3, 'mode': 'grn', 'world': world, 'genome': packed[i].tolist(), 'genotype_sha256': digest})
            name = f'raw/{world_name}/row_{i:02d}.npz'
            path = base / name
            assert sha(path) == index[name]['sha256'] == summary['input_pins'][name]
            paths.append(path)
            with np.load(path, allow_pickle=False) as row:
                assert row['ledger'].shape == (256, 57) and row['ledger'].dtype == np.float64
                assert row['seeds'].tolist() == p['seeds']
                assert str(row['role']) == role and str(row['world_name']) == world_name
                assert str(row['protocol_sha256']) == PROTOCOL and str(row['genome_raw_sha256']) == digest
                truth.append({'role': role, 'world_name': world_name, 'body_index': body_index, 'seed': SEED,
                    'ledger': row['ledger'][0].tolist(), 'source_sha256': sha(path)})
    doc = {'abi': 3, 'seed': SEED, 'bodies': bodies, 'world_groups': groups,
           'drag': atlas['drag'], 'lattice': atlas['lattice'], 'genome_slices': atlas['genome_slices'],
           'summary': {'absolute': summary['absolute'], 'contrasts': summary['contrasts']},
           'source_summary_sha256': sha(summary_path)}
    receipt = {'status': 'exported_without_simulation', 'source_pins': {str(x.resolve()): sha(x) for x in paths},
        'draft_source_pins': approved['source_pins'], 'seed_policy': 'First AK seed fixed for both worlds; no outcome-based choice.',
        'labels': LABELS, 'worlds': WORLDS, 'seed': SEED, 'simulated_lives': 0, 'genetic_draws': 0, 'compiled_libraries': 0}
    for name, value in [('bodies.json', doc), ('truth.json', {'seed': SEED, 'cases': truth, 'ledger': list(spec.V3.LEDGER)}),
                        ('export_receipt.json', receipt)]:
        with (HERE / name).open('x') as stream:
            stream.write(json.dumps(value, separators=(',', ':'), allow_nan=False) + '\n')
    print(json.dumps({'status': 'exported', 'roles': LABELS, 'worlds': WORLDS, 'seed': SEED, 'simulated_lives': 0}))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--export', action='store_true')
    parser.add_argument('--study', type=Path)
    parser.add_argument('--authorization', type=Path)
    args = parser.parse_args()
    if not args.export:
        print(json.dumps({'status': 'source_only_unreleased', 'AK_artifacts_read': False, 'simulated_lives': 0}))
        return
    if args.study is None or args.authorization is None:
        parser.error('explicit completed --study and root --authorization are required')
    export(args.study.resolve(), args.authorization.resolve())


if __name__ == '__main__':
    main()
