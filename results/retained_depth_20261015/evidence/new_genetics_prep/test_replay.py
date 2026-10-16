"""In-memory recorded-genetic replay tests; no new evolutionary draws or engines."""
import ast
import copy
import importlib.util
from pathlib import Path

import numpy as np
import pytest
import torch

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
STUDY=ROOT/'outputs/autonomous_retained_depth_20261015'

def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path)
    module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

G=load('AO_test_ops',STUDY/'replay_ops.py')
L=load('AO_test_selection',HERE/'selection_replay.py')
R=load('AO_test_first',STUDY/'native_replay.py')

class Layout:
    size = 4
    n_units = 1
    unit_of = torch.zeros(4, dtype=torch.long)
    block_of = torch.zeros(4, dtype=torch.long)
    slices = {"b": (0, 4, (4,))}

    class dims:
        genes_max = 2

    def active(self, p):
        return torch.ones((*p.shape[:-1], 2), dtype=torch.bool)

    def mutable(self, p):
        return torch.ones_like(p, dtype=torch.bool)

    def n_mut_of(self, p, n):
        return torch.full((len(p),), n, dtype=torch.long)

    def silence(self, p):
        return p.clone()

class Spec:
    @staticmethod
    def hash64(seed, kind, g, j):
        return seed + kind * 10000 + g * 100 + j

def fixture(duplicate=False, generations=24):
    initial = np.arange(128, dtype=np.float32).reshape(32, 4)
    if duplicate:
        initial[1] = initial[0]
    pop = {i: initial[i].copy() for i in range(32)}
    origins = {i: np.arange(2) + 2 * i for i in range(32)}
    lines = [{"event": "founders", "sampled": 0, "ids": list(range(32)), "copies": []}]
    curves = []
    for g in range(generations):
        parents = list(pop)
        allgen = dict(pop)
        allorg = dict(origins)
        kids = []
        ids = list(range(32 + 224 * g, 32 + 224 * (g + 1)))
        for j, cid in enumerate(ids):
            pa, pb = parents[j % 32], parents[(j + 1) % 32]
            mask = 1
            value = pop[pa if mask else pb].copy()
            value[0] += np.float32(0.25)
            value[1] += np.float32(-0.125)
            allgen[cid] = value
            allorg[cid] = origins[pa if mask else pb].copy()
            kids.append(
                {
                    "id": cid,
                    "pa": pa,
                    "pb": pb,
                    "mask": mask,
                    "ops": {"mut": [["b", [0], 0.25], ["b", [1], -0.125]]},
                    "kept": j < 32,
                }
            )
        survivors = ids[:32]
        pop = {i: allgen[i] for i in survivors}
        origins = {i: allorg[i] for i in survivors}
        matrix = np.stack(list(origins.values()))
        scores = (1000 - np.arange(64, dtype=np.float64)).tolist()
        lines.append(
            {
                "gen": g,
                "T": 1024,
                "seeds": [L.life_seed(Spec, 7, 1, g, j) for j in range(8)],
                "children": kids,
                "survivors": survivors,
                "fitness": scores[:32],
                "registry": G.registry(matrix),
                "n_active": 2.0,
                "recheck": {
                    "ids": ids[:64],
                    "key": "all",
                    "F_base": scores,
                    "F_recheck": scores,
                    "seeds": [L.life_seed(Spec, 7, 1, g, j) for j in range(8, 16)],
                },
            }
        )
        curves.append({"gen": g, "T": 1024, "best_id": survivors[0], "fitness": scores[0]})
    state = {
        "ids": torch.tensor(list(pop)),
        "fitness": torch.tensor(scores[:32], dtype=torch.float64),
        "population": torch.from_numpy(np.stack(list(pop.values()))),
        "origins": torch.from_numpy(np.stack(list(origins.values()))),
        "next_innov": 64,
        "next_id": 32 + 224 * generations,
    }
    return torch.from_numpy(initial), lines, curves, state

def test_twenty_four_generation_recorded_genetics_and_pooled_selection():
    initial, lines, curves, state=fixture(duplicate=True)
    out=L.audit_lineage(lines,curves,state,7,Spec)
    assert out['sexual_offspring']==5376
    replay=G.replay_genetics(lines,state,Layout(),initial[0],False,initial_population=initial)
    assert replay['raw_population_replay_bitwise']
    assert replay['point_mutations_including_initial_copies']==10752
    assert replay['duplication_events']==replay['deletion_events']==0


def test_first_cohort_uses_recorded_operations_not_outcomes():
    initial,lines,_,_=fixture(duplicate=True)
    first=R.replay_first(Layout(),initial,lines)
    other=copy.deepcopy(lines)
    other[1]['children'][0]['fitness']=-99999.
    other[1]['children'][0]['kept']=False
    assert R.replay_first(Layout(),initial,other)==first
    assert len(first['candidate_row_sha256'])==256
    assert first['candidate_row_sha256'][:32]==[R.raw_sha(x.numpy()) for x in initial]
    other[1]['children'][0]['ops']['mut'][0][2]=.5
    changed=R.replay_first(Layout(),initial,other)
    assert changed['candidate_raw_sha256']!=first['candidate_raw_sha256']
    assert changed['genetic_signature_sha256']!=first['genetic_signature_sha256']


@pytest.mark.parametrize('kind',['bad_ids','parent','mask','structural','wrong_points'])
def test_first_cohort_rejects_corruption(kind):
    initial,lines,_,_=fixture()
    if kind=='bad_ids': lines[1]['children'][0]['id']=0
    elif kind=='parent': lines[1]['children'][0]['pa']=1000
    elif kind=='mask': lines[1]['children'][0]['mask']=-1
    elif kind=='structural': lines[1]['children'][0]['ops']['dup']=[0,1]
    else: lines[1]['children'][0]['ops']['mut']=[]
    with pytest.raises(ValueError): R.replay_first(Layout(),initial,lines)


@pytest.mark.parametrize('kind',['raw','origins','mutation','selection'])
def test_complete_replay_rejects_corruption(kind):
    initial,lines,curves,state=fixture()
    if kind=='raw': state['population'][0,0]+=1
    elif kind=='origins': state['origins'][0,0]+=1
    elif kind=='mutation': lines[-1]['children'][0]['ops']['mut'][0][2]=.5
    else: lines[-1]['fitness'][0]-=1
    with pytest.raises(ValueError):
        if kind=='selection': L.audit_lineage(lines,curves,state,7,Spec)
        else: G.replay_genetics(lines,state,Layout(),initial[0],False,initial_population=initial)


def test_reviewed_genetics_functions_are_AST_identical():
    old=ast.parse((ROOT/'outputs/autonomous_retention_selection_20261015/replay_ops.py').read_text())
    new=ast.parse((STUDY/'replay_ops.py').read_text())
    definitions=lambda tree:{n.name:ast.dump(n) for n in tree.body if isinstance(n,ast.FunctionDef)}
    a,b=definitions(old),definitions(new)
    assert all(a[name]==value for name,value in b.items())


@pytest.mark.parametrize('stage', ['initial', 'recheck'])
def test_legacy_four_life_schedule_is_rejected(stage):
    _, lines, curves, state = fixture()
    if stage == 'initial':
        lines[1]['seeds'] = lines[1]['seeds'][:4]
    else:
        lines[1]['recheck']['seeds'] = [L.life_seed(Spec, 7, 1, 0, j) for j in range(4, 8)]
    with pytest.raises(ValueError, match='seeds'):
        L.audit_lineage(lines, curves, state, 7, Spec)


def test_pooled_means_use_both_eight_life_batches():
    _, lines, curves, state = fixture()
    for row, curve in zip(lines[1:], curves):
        base = np.asarray(row['recheck']['F_base'])
        row['recheck']['F_recheck'] = (base + 2).tolist()
        row['fitness'] = (base[:32] + 1).tolist()
        curve['fitness'] = row['fitness'][0]
    state['fitness'] = torch.tensor(lines[-1]['fitness'], dtype=torch.float64)
    assert L.audit_lineage(lines, curves, state, 7, Spec)['sexual_offspring'] == 5376
    lines[1]['fitness'] = lines[1]['recheck']['F_recheck'][:32]
    with pytest.raises(ValueError, match='pooled scores'):
        L.audit_lineage(lines, curves, state, 7, Spec)


@pytest.fixture(scope='module')
def midpoint_bundle(tmp_path_factory):
    """One small synthetic on-disk prefix fixture, shared by all midpoint checks."""
    import hashlib
    import json
    initial, lines, curves, _ = fixture(generations=24)
    _, _, _, middle = fixture(generations=8)
    base = tmp_path_factory.mktemp('midpoint')
    folder = base / 'runs/unchanged'
    (folder / 'generation8').mkdir(parents=True)
    pins = {}
    for name, all_rows, prefix_rows in (
            ('curves.jsonl', curves, curves[:8]), ('lineage.jsonl', lines, lines[:9]),
            ('clones.jsonl', [], [])):
        encode = lambda rows: ''.join(json.dumps(row) + '\n' for row in rows).encode()
        (folder / name).write_bytes(encode(all_rows))
        prefix = encode(prefix_rows)
        pins[name] = {'bytes': len(prefix), 'sha256': hashlib.sha256(prefix).hexdigest()}
    middle.update(generation=8, evals=2048, rc_lives=4096, curves=curves[:8])
    cfg, identity = {'evolve': {'generations': 24}}, {'synthetic': True}
    saved = {'format': 1, 'config': cfg, 'identity': identity, 'state': middle, 'logs': pins}
    for path in (base/'protocol.json', base/'release.json', folder/'generation8/checkpoint.pt',
                 folder/'generation8/best_genome.json', folder/'generation8/snapshot.json'):
        path.write_text('synthetic metadata\n')
    A = load('AO_test_audit', HERE/'audit_native.py')
    snapshot = {'status': 'complete', 'generation': 8, 'rank': 0,
        'rank_zero_id': int(middle['ids'][0]),
        'checkpoint_sha256': A.sha(folder/'generation8/checkpoint.pt'),
        'genome_file_sha256': A.sha(folder/'generation8/best_genome.json'),
        'genome_raw_sha256': R.raw_sha(middle['population'][0].numpy()),
        'population_raw_sha256': R.raw_sha(middle['population'].numpy()),
        'identity': identity, 'log_prefix_pins': pins,
        'protocol_sha256': A.sha(base/'protocol.json'), 'release_sha256': A.sha(base/'release.json'),
        'added_lives': 0, 'random_draws': 0}
    return A, base, folder, cfg, identity, initial, lines, curves, saved, snapshot


@pytest.mark.parametrize('corruption', [None, 'generation', 'raw', 'origins', 'prefix', 'snapshot'])
def test_midpoint_population_and_exact_final_log_prefix(monkeypatch, midpoint_bundle, corruption):
    A, base, folder, cfg, identity, initial, lines, curves, saved, snapshot = midpoint_bundle
    saved, snapshot = copy.deepcopy(saved), copy.deepcopy(snapshot)
    endpoint = saved['state']['population'][0].clone()
    if corruption == 'generation': saved['state']['generation'] = 9
    elif corruption == 'raw': saved['state']['population'][1, 0] += 1
    elif corruption == 'origins': saved['state']['origins'][1, 0] += 1
    elif corruption == 'prefix': saved['logs']['lineage.jsonl']['bytes'] += 1
    elif corruption == 'snapshot': snapshot['added_lives'] = 1
    monkeypatch.setattr(A.torch, 'load', lambda *args, **kwargs: saved)
    monkeypatch.setattr(Layout, 'load', staticmethod(lambda path: (Layout(), endpoint)), raising=False)
    monkeypatch.setattr(A, 'read', lambda path: snapshot if path.name == 'snapshot.json' else {'midpoint': snapshot})
    args = (base, folder, {'native_seed': 7}, cfg, identity, Layout(), initial,
            lines, curves, L, G, R, Spec)
    if corruption:
        with pytest.raises(ValueError): A.audit_midpoint(*args)
    else:
        result = A.audit_midpoint(*args)
        assert result['all_32_midpoint_rows_bound'] and result['uninterrupted_final_log_prefix_bound']
        assert result['selection']['sexual_offspring'] == 1792
        assert result['genetic_replay']['point_mutations_including_initial_copies'] == 3584
        assert result['added_lives'] == result['random_draws'] == 0
