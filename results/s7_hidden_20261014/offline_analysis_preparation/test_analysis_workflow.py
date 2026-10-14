"""Complete synthetic Q12-row accounting/export checks; no engine imports, outcome reads or lives."""
import importlib.util
import json
import sys
from pathlib import Path

import numpy as np
import pytest

HERE = Path(__file__).resolve().parent
COUNT_KEYS = ('F', 'F_kernel', 'n_end', 'n_H_end', 'live_time', 'spikes', 'packets', 'misses', 'clicks',
              'captures', 'path', 'zone_samples', 'samples')


def module():
    spec = importlib.util.spec_from_file_location('Q_synthetic_workflow', HERE / 'analyze.py')
    run = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(run)
    return run


def estimate(values, flags=False):
    values = np.asarray(values, dtype=np.float64)
    result = {'mean': float(values.mean()), 'se': float(values.std(ddof=1) / np.sqrt(len(values))), 'n': len(values)}
    if flags:
        result.update(positive_above_3se=result['mean'] > 3 * result['se'],
                      negative_below_minus_3se=result['mean'] < -3 * result['se'])
    return result


def raw_effects(run, fitness):
    output = {}
    for i, label in enumerate(run.LABELS[1:], 1):
        gain = {key: value[i] - value[0] for key, value in fitness.items()}
        for key, value in gain.items():
            output[label + '__gain__' + key] = value
        output[label + '__added_hidden_dependence'] = gain['freeze'] - gain['freeze+hidden_off']
        output[label + '__added_lateral_dependence'] = gain['freeze'] - gain['freeze+lateral_off']
        output[label + '__gain_lost_under_freeze'] = gain['normal'] - gain['freeze']
    for i, label in enumerate(run.LABELS):
        for lesion in ('hidden', 'lateral'):
            output[label + '__frozen_' + lesion + '_loss'] = (
                fitness['freeze'][i] - fitness['freeze+' + lesion + '_off'][i])
    return output


def refresh(run, base):
    """Write independent expected production reports from the fixture's existing raw rows."""
    protocol = run.read(base / 'protocol.json')
    manifest = run.read(base / 'measurement/manifest.json')
    seeds = np.asarray(protocol['seeds'], dtype=np.uint64)
    report = {'status': 'complete', 'genome_lives': 6144, 'planned_genome_lives': 6144,
              'completed_genome_lives': 6144, 'limitations': protocol['limitations'],
              'conditions': {}, 'row_cpu_seconds': 0.0}
    data = {}
    for condition in run.CONDITIONS:
        folder = base / 'measurement' / condition
        rows = [run.arrays(folder / 'rows' / f'row_{i:04d}.npz') for i in range(3)]
        aggregate = {key: np.stack([row[key] for row in rows]) for key in run.COLS}
        np.savez_compressed(folder / 'scores.npz', seeds=seeds, genome_indices=np.arange(3), **aggregate)
        index = {}
        for i, row in enumerate(rows):
            name = f'rows/row_{i:04d}.npz'
            index[name] = {'sha256': run.sha(folder / name), 'cpu_seconds': float(row['cpu_seconds'])}
            report['row_cpu_seconds'] += float(row['cpu_seconds'])
        run.save(folder / 'row_index.json', index)
        world = manifest['worlds'][condition]
        report['conditions'][condition] = {}
        for i, label in enumerate(run.LABELS[1:], 1):
            pieces = {
                'income': (aggregate['income'][i] - aggregate['income'][0]) / 736,
                'cost_saving': (aggregate['cost'][0] - aggregate['cost'][i]) / 736,
                'guard_charge_saving': (aggregate['guard_charge'][0] - aggregate['guard_charge'][i]) / 736,
                'extinction_charge_saving': aggregate['extinct_charge'][0] - aggregate['extinct_charge'][i]}
            pieces['accounting_residual'] = aggregate['F'][i] - aggregate['F'][0] - sum(pieces.values())
            report['conditions'][condition][label] = {
                **{key: estimate(aggregate[key][i] - aggregate[key][0]) for key in COUNT_KEYS},
                'fitness_contributions': {key: estimate(value) for key, value in pieces.items()},
                'cost_saving_components': {
                    name: estimate(price * aggregate[column][0] / 736 - price * aggregate[column][i] / 736)
                    for name, column, price in run.prices(world)}}
        data[condition] = aggregate
    vectors = raw_effects(run, {key: value['F'] for key, value in data.items()})
    report['contrasts'] = {key: estimate(value, True) for key, value in vectors.items()}
    triplets = [int(np.logical_and.reduce([
        (data[key]['status'][i].astype(np.int64) & 7) == 0 for key in run.CONDITIONS[1:]]).sum())
        for i in range(3)]
    report['frozen_tissue_validation'] = {'complete_three_arm_lives_by_genotype': triplets,
        'post_open_births_and_deaths': 0, 'window': [800, 1536], 'all_fitness_rows_retained': True}
    run.save(base / 'measurement/report.json', report)
    np.savez_compressed(base / 'measurement/contrasts.npz', seeds=seeds, **vectors)
    return vectors


@pytest.fixture
def completed(tmp_path, monkeypatch):
    run = module()
    base = tmp_path / 'Q'
    (base / 'measurement').mkdir(parents=True)
    (base / 'inputs').mkdir()
    worlds = json.loads((HERE / 'protocol.json').read_text())['worlds']
    seeds = list(range(52_030_000, 52_030_512))
    protocol = {'seeds': seeds, 'source_identity': {}, 'helpers': {}, 'limitations': ['synthetic limitations']}
    ready = {'release': 'synthetic'}
    manifest = {'worlds': worlds, 'ready': ready}
    run.save(base / 'protocol.json', protocol)
    run.save(base / 'measurement/manifest.json', manifest)
    run.save(base / 'ready.json', ready)
    run.save(base / 'budget.json', {'status': 'complete', 'exit_code': 0, 'cpu_seconds': 100.0,
        'cap_cpu_seconds': 3600, 'running': {}, 'queued': [], 'ready': ready})
    for name in run.READY_FILES | {'run.log'}:
        if name != 'protocol.json':
            (base / name).write_text('# synthetic archived operation\n')
    for name in ('protocol.json', 'run_budgeted.py', 'budget.json'):
        path = base / 'dependency/P' / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text('{}\n')
    parity = (np.arange(512) % 2).astype(float)
    shifts = {'normal': (0, 6, -1), 'freeze': (0, 3, 1),
              'freeze+lateral_off': (0, 1, 1), 'freeze+hidden_off': (0, 1, 3)}
    for condition in run.CONDITIONS:
        world = worlds[condition]
        folder = base / 'measurement' / condition / 'rows'
        folder.mkdir(parents=True)
        for i in range(3):
            row = {key: np.zeros(512, dtype=np.float64) for key in run.COLS}
            row['captures'][:] = 20 + parity + shifts[condition][i] + i * parity
            for key, value in {'window': 736, 't_end': 1536, 'last_birth': 500, 'n_end': 100 + i * 10,
                               'n_S_end': 30, 'n_M_end': 40, 'n_H_end': 30 + i * 10,
                               'live_time': 736 * (100 + i * 10), 'spikes': 500}.items():
                row[key][:] = value
            row['income'] = world['R_cap'] * row['captures']
            row['cost'] = sum(price * row[column] for _, column, price in run.prices(world))
            row['net'] = row['income'] - row['cost']
            row['F_kernel'] = row['net'] / 736
            row['F'] = row['F_kernel'] - row['extinct_charge']
            row['ledger'] = np.stack([row['F_kernel' if key == 'F' else key] for key in run.LEDGER], axis=1)
            row.update(seeds=np.asarray(seeds, dtype=np.uint64), genome_index=np.asarray(i),
                       cpu_seconds=np.asarray(1.0), wall_seconds=np.asarray(.5))
            np.savez_compressed(folder / f'row_{i:04d}.npz', **row)
    expected = refresh(run, base)
    monkeypatch.setattr(run, 'audit_inputs', lambda folder: (
        run.read(folder / 'protocol.json'), run.read(folder / 'measurement/manifest.json')))
    monkeypatch.setattr(run, 'plot', lambda *args: None)
    return run, base, expected


def test_twelve_raw_rows_recompute_both_signed_hidden_effects(completed):
    run, base, expected = completed
    summary, vectors = run.analyze(base)
    assert summary['status'] == 'complete' and summary['scientific_genome_lives'] == 6144
    assert summary['seed_block'] == 103 and summary['paired_seeds'] == 512
    assert summary['audit']['raw_checkpoints'] == 12
    assert summary['primary'][run.LABELS[1]]['mean'] > 0
    assert summary['primary'][run.LABELS[2]]['mean'] < 0
    assert len(summary['contrasts']) == 20
    assert all(row['complete_triplets'] == 512 for row in summary['frozen_tissue'])
    assert summary['budget']['row_cpu_seconds'] == 12
    for key, value in expected.items():
        assert run.identical(vectors[key], value)


@pytest.mark.parametrize('change', ['aggregate', 'ledger', 'contrast', 'report', 'count', 'seed', 'missing_row'])
def test_completed_receipt_cannot_hide_corrupted_scientific_data(completed, change):
    run, base, _ = completed
    folder = base / 'measurement/normal'
    if change in ('aggregate', 'seed'):
        data = run.arrays(folder / 'scores.npz')
        if change == 'aggregate':
            data['F'][0, 0] += 1
        else:
            data['seeds'][0] += 1
        np.savez_compressed(folder / 'scores.npz', **data)
    elif change == 'ledger':
        path = folder / 'rows/row_0000.npz'
        row = run.arrays(path)
        row['ledger'][0, run.L['path']] += 1
        np.savez_compressed(path, **row)
        index = run.read(folder / 'row_index.json')
        index['rows/row_0000.npz']['sha256'] = run.sha(path)
        run.save(folder / 'row_index.json', index)
    elif change == 'contrast':
        path = base / 'measurement/contrasts.npz'
        data = run.arrays(path)
        data[run.LABELS[1] + '__added_hidden_dependence'][0] += 1
        np.savez_compressed(path, **data)
    elif change in ('report', 'count'):
        path = base / 'measurement/report.json'
        report = run.read(path)
        if change == 'report':
            report['contrasts'][run.LABELS[1] + '__added_hidden_dependence']['mean'] += 1
        else:
            report['completed_genome_lives'] = 5632
        run.save(path, report)
    else:
        (base / 'measurement/freeze+hidden_off/rows/row_0002.npz').unlink()
    with pytest.raises((ValueError, FileNotFoundError)):
        run.analyze(base)


def public_preparation(run, target):
    target.mkdir()
    (target / 'README.md').write_text('Original prospective Q preparation\n')
    manifest = {'status': 'prospective_preparation_not_released', 'artifacts': {'README.md': {
        'sha256': run.sha(target / 'README.md'), 'bytes': (target / 'README.md').stat().st_size}}}
    run.save(target / 'provenance.json', manifest)
    return manifest


def test_export_preserves_preparation_and_reaudits_every_raw_row(completed, tmp_path, monkeypatch):
    run, base, _ = completed
    target = tmp_path / 'public'
    previous = public_preparation(run, target)
    summary, vectors = run.analyze(base)
    run.export(base, target, summary, vectors)
    assert run.read(target / 'prelaunch/provenance.json') == previous
    assert (target / 'prelaunch/README.md').read_text() == 'Original prospective Q preparation\n'
    assert len(list((target / 'measurement').rglob('row_*.npz'))) == 12
    for condition in run.CONDITIONS:
        for i in range(3):
            relative = f'measurement/{condition}/rows/row_{i:04d}.npz'
            assert run.sha(base / relative) == run.sha(target / relative)
    checked, recomputed = run.analyze(target)
    assert checked == summary and set(recomputed) == set(vectors)
    assert all(run.identical(recomputed[k], v) for k, v in vectors.items())
    monkeypatch.setattr(sys, 'argv', ['analyze.py', '--study', str(target), '--check'])
    run.main()
    (target / 'README.md').write_text('tampered public summary\n')
    with pytest.raises(ValueError):
        run.main()


def test_export_rejects_corrupt_preparation_before_copying(completed, tmp_path):
    run, base, _ = completed
    target = tmp_path / 'public'
    public_preparation(run, target)
    (target / 'README.md').write_text('changed preparation\n')
    summary, vectors = run.analyze(base)
    with pytest.raises(ValueError, match='prelaunch artifact'):
        run.export(base, target, summary, vectors)
    assert not (target / 'prelaunch').exists()


def test_export_rejects_existing_prelaunch_and_same_directory(completed, tmp_path):
    run, base, _ = completed
    summary, vectors = run.analyze(base)
    target = tmp_path / 'public'
    public_preparation(run, target)
    (target / 'prelaunch').mkdir()
    with pytest.raises(ValueError, match='prelaunch already exists'):
        run.export(base, target, summary, vectors)
    with pytest.raises(ValueError, match='separate public'):
        run.export(base, base, summary, vectors)
