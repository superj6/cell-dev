"""Reader matrix and endpoint-interface checks only; never import a simulator or draw randomness."""
from __future__ import annotations

import importlib.util
import json
import math
import shutil
import sys
import types
from pathlib import Path

import numpy as np
import pytest

STUDY = Path(__file__).resolve().parents[1]
ROOT = STUDY.parents[1]
PRIOR = ROOT / 'results/resource_patch_evolution_20261015'
ROLES = ('AO_start', 'patch8_start', 'mean4', 'pareto4')
PAIRS = (('pareto4', 'mean4'), ('mean4', 'patch8_start'), ('pareto4', 'patch8_start'),
         ('mean4', 'AO_start'), ('pareto4', 'AO_start'), ('patch8_start', 'AO_start'))


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


analyze = load('patch_selection_reader_analyze', STUDY / 'analyze.py')
_common = sys.modules.get('common')
sys.modules['common'] = load('patch_selection_reader_common', STUDY / 'common.py')
try:
    measure = load('patch_selection_reader_measure', STUDY / 'measure.py')
finally:
    if _common is None:
        sys.modules.pop('common', None)
    else:
        sys.modules['common'] = _common


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value) + '\n')


def moments(values):
    values = list(map(float, values))
    mean = math.fsum(values) / len(values)
    se = math.sqrt(math.fsum((value - mean)**2 for value in values) / (len(values) - 1) / len(values))
    return mean, se


def supplied_transfer(world, harvested):
    """Algebraic single-cell/initial-food fixture; it is not a simulated trajectory."""
    ledger = np.zeros((512, 107), dtype=np.float64)
    cost, income = world['c_live'] * world['T'], world['R_cap'] * harvested
    for key, value in dict(live_time=world['T'], live_S=world['T'], n_end=1, n_peak=1, n_S_end=1,
                           t_end=world['T'], t_ext=-1, cost=cost, income=income, net=income-cost,
                           F=(income-cost)/world['T'], captures=harvested, clicks=harvested).items():
        ledger[:, analyze.L[key]] = value
    for slot in range(2):
        hit = max(0, min(2, harvested - 2*slot))
        for key, value in dict(stock_open=2, stock_end=2-hit, source=10, spill=10,
                               harvest=hit, initial_harvest=hit).items():
            ledger[:, analyze.L[f'patch_{key}_{slot}']] = value
    return ledger


@pytest.fixture(scope='module')
def matrix(tmp_path_factory):
    """Reuse old raw bytes as reader inputs; relabeled seeds/roles are explicitly test metadata."""
    base = tmp_path_factory.mktemp('supplied_reader_matrix')
    prior = analyze.read(PRIOR / 'protocol.json')
    worlds = {name: dict(definition, world=dict(definition['world'])) for name, definition in prior['worlds'].items()}
    worlds['transfer']['world'] = dict(worlds['patch']['world'], patch_count=2, R_min=3.5, R_max=5.5,
                                        patch_refill_fast=60., patch_refill_slow=180.)
    worlds['transfer'].pop('world_vector')  # The algebraic reader fixture makes no packed-world claim.
    seeds = list(range(52500000, 52500512))
    protocol = dict(roles=list(ROLES), worlds=worlds, seeds=seeds, extinct_charge=True)
    save(base / 'protocol.json', protocol)
    protocol_pin = analyze.sha(base / 'protocol.json')
    endpoints = dict(roles=list(ROLES), protocol_sha256=protocol_pin,
                     genomes=[dict(role=role, raw_sha256='supplied_' + role) for role in ROLES])
    save(base / 'endpoints.json', endpoints)
    endpoint_pin = analyze.sha(base / 'endpoints.json')
    index, vectors = {}, {}
    for world, definition in worlds.items():
        vectors[world] = {}
        for i, role in enumerate(ROLES):
            if world == 'transfer':
                ledger = supplied_transfer(definition['world'], i)
            else:
                with np.load(PRIOR / f'raw/{world}/row_{(0, 2, 1, 2)[i]:02d}.npz', allow_pickle=False) as old:
                    ledger = old['ledger'].copy()
            raw_path = f'raw/{world}/row_{i:02d}.npz'
            native = dict(ledger=ledger, seeds=np.asarray(seeds, dtype=np.uint64),
                hashes=np.full((512, 5), 0x243F6A8885A308D3, dtype=np.uint64),
                cpu_seconds=np.asarray(0.), wall_seconds=np.asarray(0.), raw_path=np.asarray(raw_path),
                world_name=np.asarray(world), role=np.asarray(role), protocol_sha256=np.asarray(protocol_pin),
                endpoints_sha256=np.asarray(endpoint_pin), genome_raw_sha256=np.asarray('supplied_' + role))
            measure.atomic_npz(base / raw_path, **native)
            metrics, health = analyze.reconstruct(native, definition, seeds)
            scored = f'scored/{world}/row_{i:02d}.npz'
            measure.atomic_npz(base / scored, raw_sha256=np.asarray(analyze.sha(base / raw_path)),
                production_F=metrics['F'], native_F=metrics['native_F'], extinct_charge=metrics['extinct_charge'])
            index[raw_path] = dict(status='validated', lives=512, requested_lives=512, abi=6, role=role, world=world,
                sha256=analyze.sha(base / raw_path), scored_path=scored, scored_sha256=analyze.sha(base / scored),
                health=health)
            # Existing rows have no extinction. Read the native columns independently of the new reducer.
            assert np.all(ledger[:, analyze.L['status']] == 0)
            vectors[world][role] = {key: ledger[:, analyze.L[key]] for key in ('F', 'captures', 'cost')}
    save(base / 'row_index.json', index)
    save(base / 'measurement_complete.json', dict(status='complete', research_lives=10240, startup_lives=4,
        rows=20, protocol_sha256=protocol_pin, row_index_sha256=analyze.sha(base / 'row_index.json'),
        endpoints_sha256=endpoint_pin))
    return base, vectors


def test_twenty_batches_six_contrasts_and_final_retention(matrix):
    base, vectors = matrix
    result = analyze.analyze(base)
    assert result['research_lives'] == 10240 and result['primary_contrast'] == 'pareto4_minus_mean4'
    assert len(result['absolute']) == 5 and len(analyze.read(base / 'row_index.json')) == 20
    for world, roles in vectors.items():
        assert tuple(result['absolute'][world]) == ROLES
        assert set(result['paired'][world]) == {new + '_minus_' + old for new, old in PAIRS}
        for new, old in PAIRS:
            for metric in ('F', 'captures', 'cost'):
                expected = moments(roles[new][metric] - roles[old][metric])
                actual = result['paired'][world][new + '_minus_' + old][metric]
                assert (actual['mean'], actual['se']) == pytest.approx(expected, rel=1e-12, abs=1e-12)
        if world in ('pool', 'persistent', 'blink80_20'):
            retained = result['old_world_retention'][world]
            assert set(retained) == {'mean4_vs_AO_start', 'pareto4_vs_AO_start'}
            for candidate in ('mean4', 'pareto4'):
                expected = moments(roles[candidate]['captures'] - .9 * roles['AO_start']['captures'])
                actual = retained[candidate + '_vs_AO_start']['retained_90_percent_margin']
                assert (actual['mean'], actual['se']) == pytest.approx(expected, rel=1e-12, abs=1e-12)
                assert retained[candidate + '_vs_AO_start']['diagnostic_only_not_a_gate']
    assert result['absolute']['transfer']['pareto4']['total_patch_stock_open']['mean'] == 4
    with np.load(base / 'raw/patch/row_03.npz', allow_pickle=False) as row:
        assert row['raw_path'].item() == 'raw/patch/row_03.npz'
        assert np.any(row['ledger'][:, analyze.L['path']] > 0)  # Metadata never replaces native path distance.


@pytest.mark.parametrize('corruption', ('missing_batch', 'wrong_role', 'wrong_seed_block', 'wrong_raw_path'))
def test_new_matrix_schema_rejects_corruption(matrix, tmp_path, corruption):
    base = tmp_path / 'matrix'
    shutil.copytree(matrix[0], base)
    index = analyze.read(base / 'row_index.json')
    path = 'raw/patch/row_03.npz'
    if corruption == 'missing_batch':
        index.pop(path)
    elif corruption == 'wrong_role':
        index[path]['role'] = 'mean4'
    elif corruption == 'wrong_seed_block':
        protocol = analyze.read(base / 'protocol.json')
        protocol['seeds'] = list(range(52490000, 52490512))
        save(base / 'protocol.json', protocol)
    else:
        with np.load(base / path, allow_pickle=False) as row:
            fields = {key: row[key].copy() for key in row.files}
        fields['raw_path'] = np.asarray('raw/patch/row_02.npz')
        with (base / path).open('wb') as stream:
            np.savez_compressed(stream, **fields)
        index[path]['sha256'] = analyze.sha(base / path)
        scored = base / index[path]['scored_path']
        with np.load(scored, allow_pickle=False) as row:
            fields = {key: row[key].copy() for key in row.files}
        fields['raw_sha256'] = np.asarray(index[path]['sha256'])
        with scored.open('wb') as stream:
            np.savez_compressed(stream, **fields)
        index[path]['scored_sha256'] = analyze.sha(scored)
    save(base / 'row_index.json', index)
    complete = analyze.read(base / 'measurement_complete.json')
    complete.update(protocol_sha256=analyze.sha(base / 'protocol.json'),
                    row_index_sha256=analyze.sha(base / 'row_index.json'))
    save(base / 'measurement_complete.json', complete)
    with pytest.raises(ValueError):
        analyze.analyze(base)


class Tensor:
    """Only the saved tensor interface read by the endpoint binder; no Torch or simulator."""
    def __init__(self, value):
        self.value = np.asarray(value)
        self.shape = self.value.shape

    def numpy(self):
        return self.value

    def tolist(self):
        return self.value.tolist()

    def __getitem__(self, index):
        value = self.value[index]
        return Tensor(value) if isinstance(value, np.ndarray) else value


class Layout:
    dims = (875,)

    @staticmethod
    def load(path):
        return Layout(), Tensor(np.asarray(analyze.read(path)['genome'], dtype=np.float32))

    @staticmethod
    def from_dict(value):
        return Tensor(np.asarray(value, dtype=np.float32))


@pytest.fixture
def endpoint_fixture(tmp_path, monkeypatch):
    """Interface stubs test the binder; separate selector tests establish the actual ranking math."""
    base, identity = tmp_path / 'endpoints', {'stub_identity': True}
    base.mkdir()
    save(base / 'protocol.json', {'fixture': 'endpoint interface only'})
    save(base / 'release.json', {'fixture': 'no release or execution'})
    protocol = dict(references=[], configs={}, population_start={'fixture': True}, selection_worlds={'fixture': True})
    saved, configurations, calls = {}, {}, []
    for i, role in enumerate(ROLES[:2]):
        path = base / 'inputs' / (role + '.json')
        genome = np.full(875, i, dtype=np.float32)
        save(path, {'genome': genome.tolist()})
        protocol['references'].append(dict(role=role, path=str(path.relative_to(base)),
            file_sha256=analyze.sha(path), raw_sha256=measure.raw_sha(genome)))
    for arm_index, arm in enumerate(('mean', 'pareto')):
        folder = base / 'runs' / arm
        folder.mkdir(parents=True)
        selected = (7, 11)[arm_index]  # Deliberately distinct from native rank zero in both arms.
        population = np.repeat((100*arm_index + np.arange(32, dtype=np.float32))[:, None], 875, axis=1)
        ids, fitness = np.arange(100, 132), np.arange(32, dtype=np.float64)
        selection = dict(arm=arm, worlds=protocol['selection_worlds'])
        extended = dict(identity, population_start=protocol['population_start'], retention_selection=selection)
        cfg = types.SimpleNamespace(population_start=protocol['population_start'], retention_selection=selection)
        cfg_path = base / 'configs' / (arm + '.yaml')
        save(cfg_path, {})
        configurations[str(cfg_path)] = cfg
        protocol['configs'][arm] = dict(path=str(cfg_path.relative_to(base)))
        save(folder / 'determinism.json', extended)
        save(folder / 'checkpoint.pt', {'stub': arm})
        save(folder / 'results.jsonl', {'stub': arm})
        save(folder / 'population.json', dict(genomes=population.tolist(), ids=ids.tolist(), fitness=fitness.tolist()))
        save(folder / 'joint_genome.json', {'genome': population[selected].tolist()})
        logs = {}
        for name in ('curves.jsonl', 'lineage.jsonl', 'clones.jsonl'):
            (folder / name).write_text('')
            logs[name] = dict(bytes=0, sha256=analyze.sha(folder / name))
        saved[str(folder / 'checkpoint.pt')] = dict(identity=extended, logs=logs, state=dict(generation=4,
            evals=1024, rc_lives=2048, population=Tensor(population), ids=Tensor(ids), fitness=Tensor(fitness),
            curves=[dict(gen=g, pop_invalid=0, pop_mismatch=0, recheck_invalid=0) for g in range(4)]))
        receipt = dict(status='complete', arm=arm, generation=4, rank=selected, id=int(ids[selected]),
            genome_file_sha256=analyze.sha(folder / 'joint_genome.json'),
            genome_raw_sha256=measure.raw_sha(population[selected]), population_raw_sha256=measure.raw_sha(population),
            checkpoint_sha256=analyze.sha(folder / 'checkpoint.pt'), added_lives=0, random_draws=0)
        save(folder / 'endpoint_selection.json', receipt)
        marker = dict(status='complete', arm=arm, research_lives=10278, startup_lives=4,
            protocol_sha256=analyze.sha(base / 'protocol.json'), release_sha256=analyze.sha(base / 'release.json'),
            count_proof=dict(selection=10240, valid=32, final=6, growth_half=2, native_evals=1280,
                             generations=4, children_per_generation=224), endpoint=receipt,
            output_pins={path.name: analyze.sha(path) for path in folder.iterdir() if path.is_file()})
        save(folder / 'search_complete.json', marker)

    def verify_endpoint(folder, cfg, expected):
        calls.append(folder.name)
        assert saved[str(folder / 'checkpoint.pt')]['identity'] == expected
        assert cfg.retention_selection['arm'] == folder.name
        return analyze.read(folder / 'endpoint_selection.json')

    def validate(record, cfg, expected):
        assert record['identity'] == expected and cfg.population_start == protocol['population_start']

    modules = {
        'omegaconf': dict(OmegaConf=types.SimpleNamespace(load=lambda path: configurations[str(path)],
                                                        to_container=lambda value, resolve: value)),
        'population_loader': dict(loader_identity=lambda value: value,
            extended_identity=lambda value, population: dict(value, population_start=population)),
        'selection': dict(selection_identity=lambda arm, worlds: dict(arm=arm, worlds=worlds),
            extended_identity=lambda value, selection: dict(value, retention_selection=selection)),
        'search': dict(verify_endpoint=verify_endpoint),
        'src.checkpoint': dict(load=lambda path: saved[str(path)], validate=validate),
        'src.genome': dict(Layout=Layout),
    }
    for name, fields in modules.items():
        module = types.ModuleType(name)
        module.__dict__.update(fields)
        monkeypatch.setitem(sys.modules, name, module)
    source = types.ModuleType('src')
    source.__path__ = []
    source.checkpoint = sys.modules['src.checkpoint']
    monkeypatch.setitem(sys.modules, 'src', source)
    monkeypatch.setattr(measure, 'STUDY', base)
    return base, protocol, identity, saved, calls


def test_joint_endpoints_bind_nonzero_checkpoint_rows(endpoint_fixture):
    base, protocol, identity, _, calls = endpoint_fixture
    _, genomes, manifest = measure.freeze_endpoints(protocol, identity)
    assert calls == ['mean', 'pareto'] and genomes.shape == (4, 875)
    np.testing.assert_array_equal(genomes[:, 0], [0, 1, 7, 111])
    assert [manifest['searches'][arm]['selected_rank'] for arm in ('mean', 'pareto')] == [7, 11]
    assert [item['path'] for item in manifest['genomes'][2:]] == [
        'runs/mean/joint_genome.json', 'runs/pareto/joint_genome.json']
    assert analyze.read(base / 'endpoints.json') == manifest


@pytest.mark.parametrize('corruption', ('joint_row', 'selected_id', 'marker_receipt', 'call_count', 'reference_order'))
def test_joint_endpoint_binder_rejects_schema_mismatch(endpoint_fixture, corruption):
    base, protocol, identity, _, _ = endpoint_fixture
    folder = base / 'runs/mean'
    receipt = analyze.read(folder / 'endpoint_selection.json')
    marker = analyze.read(folder / 'search_complete.json')
    if corruption == 'joint_row':
        wrong = np.zeros(875, dtype=np.float32)
        save(folder / 'joint_genome.json', {'genome': wrong.tolist()})
        receipt.update(genome_file_sha256=analyze.sha(folder / 'joint_genome.json'),
                       genome_raw_sha256=measure.raw_sha(wrong))
    elif corruption == 'selected_id':
        receipt['id'] = 999
    elif corruption == 'call_count':
        marker['count_proof']['valid'] = 31
    elif corruption == 'reference_order':
        protocol['references'].reverse()
    save(folder / 'endpoint_selection.json', receipt)
    marker['endpoint'] = dict(receipt)
    if corruption == 'marker_receipt':
        marker['endpoint']['rank'] = 6
    marker['output_pins'] = {name: analyze.sha(folder / name) for name in marker['output_pins']}
    save(folder / 'search_complete.json', marker)
    with pytest.raises(ValueError):
        measure.freeze_endpoints(protocol, identity)
