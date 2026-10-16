"""Development-only all-survivor readouts, reusing the pinned ABI6 accounting reducer."""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path

import numpy as np

STUDY = Path(__file__).resolve().parent
GROUPS = ('G8', 'mean4', 'pareto4', 'AO')
WORLDS = ('patch', 'pool', 'persistent', 'blink80_20', 'transfer')
RANGES = {'G8': (0, 32), 'mean4': (32, 64), 'pareto4': (64, 96), 'AO': (96, 97)}
SCALES = (19.046875, 16.029296875, 5.919921875)
ACCOUNTING_SHA = '0ac39bb7b11a754f73acff2b77c0690ce4b525b688664da34cc6006b9da1373b'
METRICS = ('F', 'native_F', 'captures', 'income', 'cost', 'guard_charge', 'extinct_charge',
           'initial_income', 'refill_income', 'total_patch_initial_harvest', 'total_patch_refill_harvest',
           'total_patch_empty', 'patch_geometric_misses', 'total_patch_source', 'total_patch_supply',
           'total_patch_spill', 'total_patch_stock_end', 'misses', 'clicks', 'path', 'n_end', 'n_peak',
           'live_time', 'live_S', 'live_M', 'live_H', 'spikes', 'claims', 'births', 'rec_gain', 'rec_accept',
           'guarded', 'extinct', 'income_contribution', 'ordinary_cost_contribution',
           'guard_contribution', 'extinction_contribution', 'initial_income_contribution', 'refill_income_contribution')
METRICS += tuple('cost__' + name for name in
                 ('maintenance', 'spikes', 'twitch', 'messages', 'division', 'secretion', 'misses', 'receptors'))


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


def raw_sha(value):
    return hashlib.sha256(np.asarray(value).tobytes()).hexdigest()


def require(condition, message):
    if not condition:
        raise ValueError(message)


def accounting(study, protocol):
    path = study / protocol['accounting_input']
    require(sha(path) == ACCOUNTING_SHA == protocol['input_pins'][protocol['accounting_input']],
            'the unchanged validated accounting helper is required')
    descriptor = importlib.util.spec_from_file_location('population_pinned_accounting', path)
    module = importlib.util.module_from_spec(descriptor)
    descriptor.loader.exec_module(module)
    return module


def inputs(study, protocol):
    require(tuple(protocol['groups']) == GROUPS and tuple(protocol['worlds']) == WORLDS
            and protocol['seeds'] == list(range(52510000, 52510032)) and protocol['extinct_charge']
            and protocol['endpoint_reference_captures'] == list(SCALES)
            and protocol['endpoint_reference_worlds'] == list(WORLDS[:3]),
            'exact development population/world/seed scope required')
    for name, digest in protocol['input_pins'].items():
        require(sha(study / name) == digest, 'frozen input differs: ' + name)
    manifest = read(study / protocol['rows_input'])
    genomes = np.load(study / protocol['genome_input'], allow_pickle=False)
    require(genomes.shape == (97, 875) and genomes.dtype == np.float32 and np.isfinite(genomes).all(),
            '97 ordered finite raw float32 genomes required')
    require(manifest['shape'] == [97, 875] and manifest['dtype'] == 'float32'
            and manifest['groups'] == list(GROUPS) and manifest['raw_sha256'] == raw_sha(genomes),
            'population manifest packing differs')
    rows = manifest['rows']
    require(len(rows) == 97 and len({row['label'] for row in rows}) == 97, 'row labels must be unique')
    for group, (start, stop) in RANGES.items():
        require(sum(bool(row['reported_endpoint']) for row in rows[start:stop]) == 1,
                'one historical reporting endpoint annotation per group required')
        for local, i in enumerate(range(start, stop)):
            row = rows[i]
            require(row['index'] == i and row['group'] == group and row['row'] == local
                    and type(row['native_id']) is int and row['native_id'] >= 0
                    and type(row['reported_endpoint']) is bool and row['raw_sha256'] == raw_sha(genomes[i]),
                    'ordered input genotype/ID annotation differs')
    return manifest, genomes


def reconstruct_batch(native, definition, seeds, indices, helper, scored=None):
    """Split genotype-major native output; unchanged reducer checks each full 32-life row."""
    B, n = len(indices), len(seeds)
    require(native['ledger'].shape == (B*n, 107) and native['hashes'].shape == (B*n, 5),
            'complete genotype-major cohort ledger/hash arrays required')
    require(helper.identical(native['row_indices'], np.asarray(indices, dtype=np.int64)), 'cohort row order differs')
    if scored is not None:
        for name in ('production_F', 'native_F', 'extinct_charge'):
            require(scored[name].shape == (B, n), 'scored cohort dimensions differ')
    metrics, health = [], []
    for j in range(B):
        row = {key: native[key] for key in ('seeds', 'cpu_seconds', 'wall_seconds')}
        row.update(ledger=native['ledger'][j*n:(j+1)*n], hashes=native['hashes'][j*n:(j+1)*n])
        if scored is not None:
            row['production_F'] = scored['production_F'][j]
        values, checked = helper.reconstruct(row, definition, seeds)
        if scored is not None:
            require(helper.identical(scored['native_F'][j], values['native_F'])
                    and helper.identical(scored['extinct_charge'][j], values['extinct_charge']),
                    'native/extinction scoring differs')
        metrics.append(values)
        health.append(checked)
    return metrics, health


def descriptive_orders(study, rows, values, helper):
    """Fresh shared-panel ordering is descriptive and never exports a replacement genome."""
    result = {}
    for group, (start, stop) in RANGES.items():
        indices = list(range(start, stop))
        ids = [rows[i]['native_id'] for i in indices]
        require(len(set(ids)) == len(ids), 'native IDs must be unique within each retained population')
        fresh = []
        weighted = []
        for i in indices:
            f = .5*values['patch'][i]['F'] + .25*values['pool'][i]['F'] + .25*values['persistent'][i]['F']
            weighted.append(helper.describe(f))
            fresh.append([float(values[w][i]['captures'].mean()) for w in WORLDS[:3]] + [float(f.mean())])
        fresh = np.asarray(fresh, dtype=np.float64)

        def order(table, ids=tuple(ids)):
            fractions = table[:, :3] / np.asarray(SCALES)
            minima = fractions.min(axis=1)
            return sorted(range(len(table)), key=lambda j: (-float(minima[j]), -float(table[j, 3]), ids[j]))

        fresh_order = order(fresh)
        fresh_rank = {row: rank for rank, row in enumerate(fresh_order)}
        cached, cached_order, cache_pins = None, None, {}
        if group in ('mean4', 'pareto4'):
            folder = study / 'inputs' / 'cached' / group
            lines = [json.loads(line) for line in (folder / 'lineage.jsonl').read_text().splitlines()]
            last, endpoint = lines[-1], read(folder / 'endpoint_selection.json')
            require(last['gen'] == 3 and last['survivors'] == ids, 'cached final survivor IDs/order differ')
            require(sha(folder / 'g003.npz') == last['selection']['sha256']
                    == endpoint['selection_sha256'], 'cached final selection pin differs')
            with np.load(folder / 'g003.npz', allow_pickle=False) as a:
                short, pick = a['shortlist'], a['pick']
                require(a['candidate_ids'][short[pick]].tolist() == ids, 'cached scored-row IDs differ')
                require([raw_sha(row) for row in a['base_genomes'][short[pick]]]
                        == [rows[i]['raw_sha256'] for i in indices], 'cached genotype row bytes differ')
                cap = np.concatenate((a['base_captures'][short], a['recheck_captures']), axis=1)[pick]
                fit = np.concatenate((a['base_production_F'][short], a['recheck_production_F']), axis=1)[pick]
            require(cap.shape == fit.shape == (32, 16), 'cached pooled16 row dimensions differ')
            pattern = np.asarray((0, 1, 0, 2) * 4)
            cached = np.column_stack([cap[:, pattern == d].mean(axis=1) for d in range(3)] + [fit.mean(axis=1)])
            cached_order = order(cached)
            require(endpoint['selection']['objectives'] == cached.tolist()
                    and endpoint['selection']['order'] == cached_order
                    and rows[start + endpoint['rank']]['reported_endpoint'], 'cached reporting annotation differs')
            cache_pins = {str(p.relative_to(study)): sha(p) for p in
                          (folder / 'g003.npz', folder / 'lineage.jsonl', folder / 'endpoint_selection.json')}
        details = []
        for local, i in enumerate(indices):
            detail = dict(index=i, label=rows[i]['label'], native_id=ids[local],
                          reported_endpoint=rows[i]['reported_endpoint'], fresh_objectives=fresh[local].tolist(),
                          fresh_capture_fractions=(fresh[local, :3]/np.asarray(SCALES)).tolist(),
                          fresh_joint_minimum=float((fresh[local, :3]/np.asarray(SCALES)).min()),
                          fresh_descriptive_rank=fresh_rank[local], training_weighted_F=weighted[local])
            if cached is not None:
                detail.update(cached16_objectives=cached[local].tolist(), cached16_rank=cached_order.index(local),
                              rank_change=fresh_rank[local]-cached_order.index(local))
            details.append(detail)
        result[group] = dict(rows=details, fresh_order_local_rows=fresh_order,
                             cached16_order_local_rows=cached_order, cached_source_pins=cache_pins,
                             cached_capture_table_available=cached is not None,
                             cached_note=(None if cached is not None
                                          else 'No comparable cached capture table available.'),
                             replaces_reporting_endpoint=False)
    return result


def analyze(study):
    protocol = read(study / 'protocol.json')
    manifest, _ = inputs(study, protocol)
    helper = accounting(study, protocol)
    complete, index = read(study / 'measurement_complete.json'), read(study / 'row_index.json')
    require(complete['status'] == 'complete' and complete['research_lives'] == 15520
            and complete['startup_lives'] == 4 and complete['total_calls'] == 15524
            and complete['batches'] == 20 and complete['genomes'] == 97 and complete['genome_world_rows'] == 485
            and complete['lives_per_genome_world'] == 32
            and complete['protocol_sha256'] == sha(study / 'protocol.json')
            and complete['row_index_sha256'] == sha(study / 'row_index.json')
            and complete['rows_manifest_sha256'] == sha(study / protocol['rows_input'])
            and complete['startup_sha256'] == sha(study / 'startup.json'), 'complete matrix required')
    require(set(index) == {f'raw/{w}/{g}.npz' for w in WORLDS for g in GROUPS}, 'cohort batch matrix differs')
    rows = manifest['rows']
    values, absolute, paired, health, populations = {}, {}, {}, {}, {}
    for world in WORLDS:
        values[world], absolute[world], paired[world], health[world], populations[world] = {}, {}, {}, {}, {}
        for group, (start, stop) in RANGES.items():
            relative = f'raw/{world}/{group}.npz'
            entry = index[relative]
            require(entry['status'] == 'validated' and entry['group'] == group and entry['world'] == world
                    and entry['abi'] == 6 and entry['lives'] == (stop-start)*32
                    and entry['row_indices'] == list(range(start, stop)) and entry['sha256'] == sha(study / relative)
                    and entry['scored_path'] == f'scored/{world}/{group}.npz'
                    and entry['scored_sha256'] == sha(study / entry['scored_path']), 'cohort index differs')
            with np.load(study / relative, allow_pickle=False) as f:
                native = {key: f[key].copy() for key in f.files}
            with np.load(study / entry['scored_path'], allow_pickle=False) as f:
                scored = {key: f[key].copy() for key in f.files}
            for key, expected in (('world_name', world), ('group', group), ('raw_path', relative),
                                  ('protocol_sha256', sha(study / 'protocol.json')),
                                  ('rows_manifest_sha256', sha(study / protocol['rows_input']))):
                require(np.asarray(native[key]).shape == () and native[key].item() == expected,
                        'native cohort identity differs: ' + key)
            require(native['genome_raw_sha256'].tolist() == [r['raw_sha256'] for r in rows[start:stop]]
                    and scored['raw_sha256'].item() == entry['sha256'], 'raw genotype/scored pins differ')
            metrics, checked = reconstruct_batch(native, protocol['worlds'][world], protocol['seeds'],
                                                  list(range(start, stop)), helper, scored)
            require(checked == entry['health'], 'cohort health differs')
            for i, metric, row_health in zip(range(start, stop), metrics, checked, strict=True):
                values[world][i], health[world][rows[i]['label']] = metric, row_health
                absolute[world][rows[i]['label']] = {key: helper.describe(metric[key]) for key in METRICS}
        for i in range(96):
            paired[world][rows[i]['label']] = {
                key: helper.describe(values[world][i][key]-values[world][96][key]) for key in METRICS}
        for group, (start, stop) in RANGES.items():
            populations[world][group] = {
                key: helper.describe(np.stack([values[world][i][key] for i in range(start, stop)]).mean(axis=0))
                for key in METRICS}
    population_paired = {}
    for world in WORLDS:
        population_paired[world] = {}
        for new, old in (('mean4', 'G8'), ('pareto4', 'G8'), ('pareto4', 'mean4')):
            population_paired[world][new + '_minus_' + old] = {}
            for key in METRICS:
                panel = [np.stack([values[world][i][key] for i in range(*RANGES[g])]).mean(axis=0)
                         for g in (new, old)]
                population_paired[world][new + '_minus_' + old][key] = helper.describe(panel[0]-panel[1])
    retention = {}
    for world in ('pool', 'persistent', 'blink80_20'):
        reference = values[world][96]['captures']
        retention[world] = {rows[i]['label']: dict(
            mean_capture_ratio=None if reference.mean() == 0 else float(values[world][i]['captures'].mean()
                                                                       / reference.mean()),
            paired_90_percent_margin=helper.describe(values[world][i]['captures']-.9*reference),
            diagnostic_only_not_a_gate=True) for i in range(96)}
    return dict(status='complete', scope='DEVELOPMENT all-survivor diagnostic', research_lives=15520,
                startup_lives=4, genomes=97, paired_life_clusters=32, raw_batches=20, row_manifest=rows,
                absolute=absolute, paired_minus_AO=paired, health=health, population_means=populations,
                population_paired=population_paired, old_world_retention=retention,
                descriptive_orders=descriptive_orders(study, rows, values, helper),
                training_F_weights=dict(patch=.5, pool=.25, persistent=.25), joint_capture_scales=list(SCALES),
                protocol_sha256=sha(study / 'protocol.json'), row_index_sha256=sha(study / 'row_index.json'),
                rows_manifest_sha256=sha(study / protocol['rows_input']), accounting_source_sha256=ACCOUNTING_SHA,
                limitations=[
                    'All 97 fixed rows and duplicates retained; no endpoint is replaced or winner certified.',
                    'Thirty-two shared fresh lives are development diagnostics, not formal admission evidence.',
                    'Per-life SE and descriptive bounds do not estimate reliability across evolutionary searches.',
                    'Population SE uses 32 shared-seed population means; genomes are not independent replicates.',
                    'Fresh rank and minimum estimates can be noisy; low observed ranks do not prove absent capability.',
                    'Joint order uses three training worlds and fixed AO scales; F retains the 0.5/0.25/0.25 weights.',
                    'Cached16 and fresh32 scores use different samples; their rank changes are descriptive.',
                    'All five worlds are now development exposures, including the previous reserved transfer.',
                    'Food origin and physical costs do not establish switching, revisit strategies or memory.',
                    'Fast hashes are constants, not trajectory evidence; guards/extinction remain in accounting.'])


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--study', type=Path, default=STUDY)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    if args.output is None:
        print('source only: saved-data analysis requires --output')
    else:
        with args.output.open('x') as stream:
            json.dump(analyze(args.study), stream, indent=2, allow_nan=False)
            stream.write('\n')
