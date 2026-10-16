"""Supplied-data integration only: no simulator, build or genetic/tie RNG draws."""
from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest
import torch
from omegaconf import OmegaConf

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE.parents[1]))
sys.path.insert(0, str(HERE))

import selection  # noqa: E402

import src.evolve as native  # noqa: E402
from src.life import spec  # noqa: E402
from src.life.evaluate import LifeDraw  # noqa: E402


@dataclass
class Eval:
    fitness: torch.Tensor
    trial_scores: torch.Tensor


class SuppliedEvaluator:
    """The actual adapter consumes literal ledger columns through its native method seams."""

    def __init__(self, configured, out, *, invalid=False):
        self.cfg = OmegaConf.create({'retention_selection': configured,
                                    'logging': {'output_dir': str(out)}})
        self.abi, self.lives = spec.V6, 8
        self.T_choices, self.has_envelope, self.envelope = (), False, {}
        self.extinct_charge = True
        self.invalid = invalid
        self.calls = []

    def world(self):
        return spec.World(**self.cfg.retention_selection.worlds.patch)

    def draw(self, purpose, index, lives=None, T=None, overrides=None, envelope=None):
        count = self.lives if lives is None else lives
        # Valid uint64 seeds above the signed boundary, supplied rather than sampled.
        offset = 0 if purpose == 'gen' else 10000
        seeds = tuple(2**63 + 100 + 32*index + offset + i for i in range(count))
        return LifeDraw(seeds, (self.world(),) * count)

    def columns(self, result, B, draw):
        return result

    def __call__(self, params, draw):
        rows = params[:, 0].numpy().astype(np.int64)
        new = (int(draw.seeds[0]) - 2**63 - 100) % 32 == 8
        # Specialists expose a real scalar-vs-Pareto difference without hidden ties.
        domains = np.stack((rows % 19, (255 - rows) % 17, rows % 7), axis=1)
        captures = domains[:, [0, 1, 0, 2, 0, 1, 0, 2]].astype(np.float64)
        if new:
            captures = captures + (rows[:, None] % 3)
        native_f = np.broadcast_to((rows % 31 - 15)[:, None], captures.shape).astype(np.float64).copy()
        charge = np.full_like(native_f, .25 if new else .125)
        invalid = np.zeros_like(captures, dtype=np.bool_)
        invalid[0, 0] = self.invalid
        data = {'captures': captures, 'F': native_f - charge, 'F_kernel': native_f,
                'status': np.full_like(captures, 2.), 'extinct_charge': charge,
                'invalid': invalid, 'mismatch': np.zeros_like(invalid)}
        self.calls.append((params.numpy().copy(), tuple(draw.seeds)))
        col = self.columns(data, len(params), draw)
        return Eval(torch.from_numpy(col['F'].mean(axis=1)), torch.from_numpy(col['F']))


def supplied_permutations(monkeypatch):
    values = [torch.arange(255, -1, -1), torch.roll(torch.arange(256), 19), torch.arange(63, -1, -1)]
    calls = []

    def draw(n, *, generator):
        assert generator is sentinel
        assert n == len(values[len(calls)])
        result = values[len(calls)].clone()
        calls.append(n)
        return result

    sentinel = object()
    monkeypatch.setattr(torch, 'randperm', draw)
    return sentinel, values, calls


def drive(arm, out, monkeypatch):
    configured = selection.selection_identity(arm, selection.expected_worlds())
    evaluator = SuppliedEvaluator(configured, out)
    params = torch.zeros((256, 875), dtype=torch.float32)
    params[:, 0] = torch.arange(256)
    generator, supplied, calls = supplied_permutations(monkeypatch)
    with selection.installed(native, SuppliedEvaluator, configured) as tracker:
        lineage = native.Lineage(out, 'all')
        lineage.write({'event': 'founders', 'ids': list(range(32)), 'copies': []})
        draw = evaluator.draw('gen', 0)
        result = evaluator(params, draw)
        before = result.trial_scores.numpy().copy()
        native.rank_desc(result.fitness, generator)
        rc = native.recheck(evaluator, params, result, 0, 32, 64, 8, 'all', generator)
        row = {'gen': 0, 'seeds': list(draw.seeds),
               'children': [{'id': i} for i in range(32, 256)], 'survivors': rc['order'].tolist(),
               'fitness': rc['chosen'].fitness.tolist(),
               'recheck': {'ids': rc['shortlist'].tolist(), 'seeds': list(rc['draw'].seeds)}}
        lineage.write(row)
        lineage.close()
        assert tracker['pending'] is None and not tracker['cache'] and tracker['pre'] is None
        assert len(tracker['records']) == 1
        np.testing.assert_array_equal(result.trial_scores.numpy(), before)
    with np.load(out / 'selection/g000.npz', allow_pickle=False) as file:
        arrays = {name: file[name] for name in file.files}
    return SimpleNamespace(rc=rc, arrays=arrays, supplied=supplied, calls=calls, evaluator=evaluator,
                           result=result, row=row, params=params)


@pytest.mark.parametrize('arm', ['mean', 'pareto'])
def test_capture_exact_unsigned_seeds_rows_all16_f_and_native_tie_call_inventory(arm, tmp_path, monkeypatch):
    data = drive(arm, tmp_path, monkeypatch)
    assert data.calls == [256, 256, 64]
    assert len(data.evaluator.calls) == 2
    a = data.arrays
    assert a['base_seeds'].dtype == np.uint64 and int(a['base_seeds'][0]) > 2**63
    assert a['recheck_seeds'].dtype == np.uint64
    np.testing.assert_array_equal(a['recheck_seeds'], a['base_seeds'] + 8)
    np.testing.assert_array_equal(a['base_genomes'], data.params.numpy())
    np.testing.assert_array_equal(a['recheck_genomes'], a['base_genomes'][a['shortlist']])
    for name, supplied in zip(('pre_permutation', 'shortlist_permutation', 'survivor_permutation'),
                              data.supplied, strict=True):
        np.testing.assert_array_equal(a[name], supplied.numpy())
    joined = np.concatenate((a['base_production_F'][a['shortlist']], a['recheck_production_F']), axis=1)
    assert data.rc['chosen'].trial_scores.shape == (32, 16)
    np.testing.assert_array_equal(data.rc['chosen'].trial_scores.numpy(), joined[a['pick']])
    np.testing.assert_array_equal(data.rc['chosen'].fitness.numpy(), joined.mean(axis=1)[a['pick']])
    np.testing.assert_array_equal(a['base_production_F'], a['base_native_F'] - a['base_extinct_charge'])
    line = json.loads((tmp_path / 'lineage.jsonl').read_text().splitlines()[-1])
    assert line['selection']['sha256'] == selection.sha(tmp_path / line['selection']['path'])
    assert line['selection']['extra_lives'] == line['selection']['extra_rng_draws'] == 0


def test_mean_arm_is_native_stable_torch_order_with_supplied_permutations(tmp_path, monkeypatch):
    data = drive('mean', tmp_path, monkeypatch)
    first = data.supplied[1]
    expected_short = first[data.result.fitness[first].argsort(descending=True, stable=True)][:64]
    np.testing.assert_array_equal(data.rc['shortlist'].numpy(), expected_short.numpy())
    combined = torch.from_numpy(np.concatenate((data.arrays['base_production_F'][expected_short.numpy()],
                                                data.arrays['recheck_production_F']), axis=1).mean(axis=1))
    final = data.supplied[2]
    expected_pick = final[combined[final].argsort(descending=True, stable=True)][:32]
    np.testing.assert_array_equal(data.rc['pick'].numpy(), expected_pick.numpy())


def test_endpoint_uses_final_native_row_order_and_exact_candidate_ids(tmp_path, monkeypatch):
    data = drive('pareto', tmp_path, monkeypatch)
    ids = data.arrays['candidate_ids'][data.rc['order'].numpy()]
    result = selection.endpoint_from_arrays(data.arrays, ids)
    assert result.audit()['selected_id'] == int(ids[result.selected])
    with pytest.raises(ValueError, match='IDs'):
        selection.endpoint_from_arrays(data.arrays, ids[::-1])


def test_invalid_native_result_fails_without_changing_capture_or_prices(tmp_path):
    configured = selection.selection_identity('pareto', selection.expected_worlds())
    evaluator = SuppliedEvaluator(configured, tmp_path, invalid=True)
    with selection.installed(native, SuppliedEvaluator, configured):
        with pytest.raises(ValueError, match='invalid'):
            evaluator(torch.zeros((256, 875)), evaluator.draw('gen', 0))


def test_all_hooks_restore_after_exception_and_nonselection_draw_unchanged(tmp_path):
    configured = selection.selection_identity('mean', selection.expected_worlds())
    evaluator = SuppliedEvaluator(configured, tmp_path)
    methods = (SuppliedEvaluator.draw, SuppliedEvaluator.__call__, SuppliedEvaluator.columns,
               native.rank_desc, native.recheck, native.Lineage.write)
    expected = evaluator.draw('valid', 2, lives=16)
    with pytest.raises(RuntimeError, match='supplied failure'):
        with selection.installed(native, SuppliedEvaluator, configured):
            assert evaluator.draw('valid', 2, lives=16) == expected
            raise RuntimeError('supplied failure')
    assert methods == (SuppliedEvaluator.draw, SuppliedEvaluator.__call__, SuppliedEvaluator.columns,
                       native.rank_desc, native.recheck, native.Lineage.write)
