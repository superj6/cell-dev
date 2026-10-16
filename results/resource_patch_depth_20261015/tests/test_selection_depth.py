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

import pareto  # noqa: E402
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
        self.abi, self.lives = spec.V6, 32
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
        seeds = tuple(2**63 + 100 + 128*index + offset + i for i in range(count))
        return LifeDraw(seeds, (self.world(),) * count)

    def columns(self, result, B, draw):
        return result

    def __call__(self, params, draw):
        rows = params[:, 0].numpy().astype(np.int64)
        new = (int(draw.seeds[0]) - 2**63 - 100) % 128 == 32
        # Specialists expose a real scalar-vs-Pareto difference without hidden ties.
        domains = np.stack((rows % 19, (255 - rows) % 17, rows % 7), axis=1)
        captures = domains[:, list(pareto.PATTERN)].astype(np.float64)
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


def drive(out, monkeypatch, generation):
    configured = selection.selection_identity('pareto', selection.expected_worlds())
    evaluator = SuppliedEvaluator(configured, out)
    params = torch.zeros((256, 875), dtype=torch.float32)
    params[:, 0] = torch.arange(256)
    generator, supplied, calls = supplied_permutations(monkeypatch)
    with selection.installed(native, SuppliedEvaluator, configured) as tracker:
        lineage = native.Lineage(out, 'all')
        lineage.write({'event': 'founders', 'ids': list(range(32)), 'copies': []})
        draw = evaluator.draw('gen', generation)
        result = evaluator(params, draw)
        before = result.trial_scores.numpy().copy()
        native.rank_desc(result.fitness, generator)
        rc = native.recheck(evaluator, params, result, generation, 32, 64, 32, 'all', generator)
        row = {'gen': generation, 'seeds': list(draw.seeds),
               'children': [{'id': i} for i in range(32, 256)], 'survivors': rc['order'].tolist(),
               'fitness': rc['chosen'].fitness.tolist(),
               'recheck': {'ids': rc['shortlist'].tolist(), 'seeds': list(rc['draw'].seeds)}}
        lineage.write(row)
        lineage.close()
        assert tracker['pending'] is None and not tracker['cache'] and tracker['pre'] is None
        assert len(tracker['records']) == 1
        np.testing.assert_array_equal(result.trial_scores.numpy(), before)
    with np.load(out / f'selection/g{generation:03d}.npz', allow_pickle=False) as file:
        arrays = {name: file[name] for name in file.files}
    return SimpleNamespace(rc=rc, arrays=arrays, supplied=supplied, calls=calls, evaluator=evaluator,
                           result=result, row=row, params=params)


@pytest.mark.parametrize('generation', [0, 7])
def test_adapter_preserves32_plus32_rows_unsigned_seeds_and_native_three_tie_draws(
        generation, tmp_path, monkeypatch):
    data = drive(tmp_path, monkeypatch, generation)
    assert data.calls == [256, 256, 64]
    assert len(data.evaluator.calls) == 2
    a = data.arrays
    assert a['base_captures'].shape == (256, 32) and a['recheck_captures'].shape == (64, 32)
    assert a['base_seeds'].dtype == np.uint64 and int(a['base_seeds'][0]) > 2**63
    assert a['recheck_seeds'].dtype == np.uint64
    np.testing.assert_array_equal(a['recheck_seeds'], a['base_seeds'] + 32)
    np.testing.assert_array_equal(a['base_genomes'], data.params.numpy())
    np.testing.assert_array_equal(a['recheck_genomes'], a['base_genomes'][a['shortlist']])
    for name, supplied in zip(('pre_permutation', 'shortlist_permutation', 'survivor_permutation'),
                              data.supplied, strict=True):
        np.testing.assert_array_equal(a[name], supplied.numpy())
    joined = np.concatenate((a['base_production_F'][a['shortlist']], a['recheck_production_F']), axis=1)
    assert data.rc['chosen'].trial_scores.shape == (32, 64)
    np.testing.assert_array_equal(data.rc['chosen'].trial_scores.numpy(), joined[a['pick']])
    np.testing.assert_array_equal(data.rc['chosen'].fitness.numpy(), joined.mean(axis=1)[a['pick']])
    np.testing.assert_array_equal(a['base_production_F'], a['base_native_F'] - a['base_extinct_charge'])
    line = json.loads((tmp_path / 'lineage.jsonl').read_text().splitlines()[-1])
    assert line['selection']['sha256'] == selection.sha(tmp_path / line['selection']['path'])
    assert line['selection']['base_shape'] == [256, 32]
    assert line['selection']['recheck_shape'] == [64, 32]
    assert line['selection']['survivor_lives'] == 64
    assert line['selection']['extra_lives'] == line['selection']['extra_rng_draws'] == 0


def test_later_base_cycles_contribute_all_three_capture_means_and_ordinary_f():
    cap = np.zeros((256, 32), dtype=np.float64)
    cap[:, 8:] = np.asarray([7., 11., 7., 13.] * 6)
    fit = np.broadcast_to(np.arange(32, dtype=np.float64), cap.shape).copy()
    ties = np.arange(255, -1, -1)
    result = pareto.select_shortlist(cap, fit, ties)
    np.testing.assert_array_equal(result.ranking.objectives, np.tile([5.25, 8.25, 9.75, 15.5], (256, 1)))
    np.testing.assert_array_equal(result.selected, ties[:64])
    assert result.lives_per_candidate == 32


def test_last_recheck_cycle_can_change_survivor_front_after_pooling_all64_lives():
    base = np.zeros((256, 32), dtype=np.float64)
    new_cap, new_f = np.zeros((64, 32)), np.zeros((64, 32))
    new_cap[0, -8:] = 10.
    new_f[0, -8:] = 16.
    result = pareto.select_survivors(base, base, np.arange(64), new_cap, new_f, np.arange(63, -1, -1))
    np.testing.assert_array_equal(result.ranking.objectives[0], [1.25, 1.25, 1.25, 2.])
    assert result.ranking.ranks[0] == 0 and (result.ranking.ranks[1:] == 1).all()
    assert result.selected[0] == 0 and result.lives_per_candidate == 64


@pytest.mark.parametrize('width', [8, 16])
def test_old_short_selection_panels_are_rejected(width):
    values = np.zeros((256, width), dtype=np.float64)
    with pytest.raises(ValueError, match='32'):
        pareto.select_shortlist(values, values, np.arange(256))


def test_gen8_outside_registered_search_rejected_without_evaluation(tmp_path):
    configured = selection.selection_identity('pareto', selection.expected_worlds())
    evaluator = SuppliedEvaluator(configured, tmp_path)
    with selection.installed(native, SuppliedEvaluator, configured):
        with pytest.raises(ValueError, match='eight-generation'):
            evaluator.draw('gen', 8)
    assert evaluator.calls == []
