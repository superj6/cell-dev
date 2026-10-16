"""Study-local Pareto ordering of unchanged native mixed-world lives, using32+32 samples."""
from __future__ import annotations

import copy
import hashlib
import json
import os
import time
from contextlib import contextmanager
from dataclasses import asdict, replace
from pathlib import Path

import numpy as np

STUDY = Path(__file__).resolve().parent
ARMS = ('pareto',)
PATTERN = ('patch', 'pool', 'patch', 'persistent') * 8
RULE = ('gen fixed patch16/pool8/persistent8 per32 repeated for recheck; '
        'base32 shortlist64 then pooled64 survivors32; ordinary production F unchanged; '
        'pareto maximizes three within-domain capture means and aggregate F; '
        'native tie permutations256 diagnostic/256 shortlist/64 final; '
        'diagnostics=patchT1024 and ordinary growthT512; no cached reporting endpoint')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def expected_worlds():
    from src.life import spec

    return {
        'patch': asdict(spec.world('catch_resource_patches_l4', T=1024.)),
        'pool': asdict(spec.world('catch_speck_l4', T=1024., d0=.5, d_min=.25,
                                 sigma=.4, lam_s=4., v_t=.1, tau_turn=20.)),
        'persistent': asdict(spec.world('catch_speck_l4', T=1024., d0=1., d_min=.5,
                                       v_t=.3, tau_turn=200.)),
    }


def selection_identity(arm, worlds):
    if arm not in ARMS or worlds != expected_worlds():
        raise ValueError('exact fixed ABI6 patch / AO POOL / AO persistent worlds required')
    return {'version': 3, 'arm': arm, 'worlds': copy.deepcopy(worlds), 'rule': RULE,
            'pattern': list(PATTERN),
            'source_pins': {name: sha(STUDY / name) for name in ('selection.py', 'pareto.py')}}


def extended_identity(base, configured):
    result = copy.deepcopy(base)
    if 'retention_selection' in result:
        raise ValueError('base identity already contains selection adapter')
    result['retention_selection'] = copy.deepcopy(configured)
    return result


def _same(a, b):
    a, b = np.asarray(a), np.asarray(b)
    return a.shape == b.shape and a.dtype == b.dtype and a.tobytes() == b.tobytes()


@contextmanager
def installed(native, evaluator_class, configured):
    """Scope every observer and ordering hook; native life, genetics and checkpoints remain intact.

    Captures are copied before LifeEval collapses the per-life ledger. Raw arrays enter a
    generation NPZ whose hash is in lineage.jsonl, so native checkpoint log pins cover it.
    Every cache entry is consumed within its generation; resume needs no hidden cache state.
    """
    import pareto
    import torch
    from omegaconf import OmegaConf

    from src.life import spec

    if configured != selection_identity(configured['arm'], configured['worlds']):
        raise ValueError('selection configuration/source identity differs')
    worlds = {name: spec.World(**values) for name, values in configured['worlds'].items()}
    for world in worlds.values():
        spec.V6.validate_world(world)
    original_draw, original_call = evaluator_class.draw, evaluator_class.__call__
    original_columns, original_rank = evaluator_class.columns, native.rank_desc
    original_recheck, original_write = native.recheck, native.Lineage.write
    tracker = {'draws': {}, 'cache': {}, 'active': None, 'pending': None, 'pre': None,
               'records': [], 'parents': None}

    def draw(self, purpose, index, lives=None, T=None, overrides=None, envelope=None):
        if OmegaConf.to_container(self.cfg.retention_selection, resolve=True) != configured:
            raise ValueError('evaluator selection configuration differs')
        count = self.lives if lives is None else int(lives)
        if purpose != 'gen':
            return original_draw(self, purpose, index, lives=lives, T=T, overrides=overrides, envelope=envelope)
        if (self.abi.version != 6 or count not in (32, 64) or int(index) != index or index not in range(8)
                or (T is not None and T != 1024.) or overrides is not None or envelope not in (None, False)
                or self.T_choices or self.has_envelope or self.envelope.get('enabled', False)
                or not self.extinct_charge or asdict(self.world()) != configured['worlds']['patch']):
            raise ValueError('fixed eight-generation 32+32 ABI6 selection and ordinary extinction charge required')
        result = original_draw(self, purpose, index, lives=lives, T=T, overrides=overrides, envelope=envelope)
        if result.n != count or len(result.worlds) != count:
            raise ValueError('native draw length differs')
        result = replace(result, worlds=tuple(worlds[PATTERN[i % 32]] for i in range(count)))
        for offset in range(0, count, 32):
            key = tuple(int(s) for s in result.seeds[offset:offset + 32])
            value = (int(index), 'base' if offset == 0 else 'recheck')
            if key in tracker['draws'] and tracker['draws'][key] != value:
                raise ValueError('selection seed identity collision')
            tracker['draws'][key] = value
        return result

    def columns(self, result, B, draw):
        col = original_columns(self, result, B, draw)
        active = tracker['active']
        if active is not None:
            if tuple(draw.seeds) != active['seeds'] or draw.n != 32:
                raise ValueError('nested or mismatched selection result')
            active['parts'].append({name: np.ascontiguousarray(col[key]).copy() for name, key in (
                ('captures', 'captures'), ('production_F', 'F'), ('native_F', 'F_kernel'),
                ('status', 'status'), ('extinct_charge', 'extinct_charge'),
                ('invalid', 'invalid'), ('mismatch', 'mismatch'))})
        return col

    def evaluate(self, params, draw):
        stage = tracker['draws'].get(tuple(int(s) for s in draw.seeds))
        if stage is None:
            return original_call(self, params, draw)
        if (tracker['active'] is not None or stage in tracker['cache'] or draw.n != 32
                or [asdict(w) for w in draw.worlds] != [configured['worlds'][name] for name in PATTERN]
                or tuple(params.shape) != (256 if stage[1] == 'base' else 64, 875)):
            raise ValueError('selection evaluation identity, dimensions or call order differs')
        active = {'seeds': tuple(draw.seeds), 'parts': []}
        tracker['active'] = active
        try:
            result = original_call(self, params, draw)
        finally:
            tracker['active'] = None
        if not active['parts']:
            raise ValueError('selection observer received no native result')
        data = {key: np.concatenate([part[key] for part in active['parts']], axis=0)
                for key in active['parts'][0]}
        if (not _same(data['production_F'], result.trial_scores.numpy())
                or data['invalid'].any() or data['mismatch'].any()
                or not all(np.isfinite(value).all() for value in data.values())):
            raise ValueError('selection native result invalid or disagrees with production LifeEval')
        data.update(genomes=params.numpy().copy(), seeds=np.asarray(draw.seeds, dtype=np.uint64),
                    worlds=np.stack([spec.V6.pack_world(w) for w in draw.worlds]))
        tracker['cache'][stage] = data
        return result

    def permutation(n, generator):
        if generator is None:
            raise ValueError('registered native random tie stream is required')
        return torch.randperm(n, generator=generator)

    def rank_desc(fitness, tie_gen=None):
        # Native evolve's first diagnostic ranking precedes the recheck's two rankings.
        if fitness.shape != (256,) or tracker['pre'] is not None:
            raise ValueError('unexpected native ranking call')
        perm = permutation(256, tie_gen)
        tracker['pre'] = perm.numpy().copy()
        return perm[fitness[perm].argsort(descending=True, stable=True)]

    def recheck(ev, everyone, res, g, mu, k, lives, key, tie_gen=None):
        if ((mu, k, lives, key) != (32, 64, 32, 'all') or g not in range(8)
                or tracker['pending'] is not None or tracker['pre'] is None):
            raise ValueError('unexpected registered native recheck')
        base = tracker['cache'].pop((g, 'base'))
        if not _same(base['genomes'], everyone.numpy()):
            raise ValueError('base capture rows differ from current native candidates')
        perm0 = permutation(256, tie_gen).numpy()
        stage0 = pareto.select_shortlist(base['captures'], base['production_F'], perm0)
        order0 = stage0.ranking.order
        short = torch.from_numpy(order0[:64].copy())
        redraw = native.recheck_draw(ev, g, 32, 32)
        t0 = time.perf_counter()
        rres = ev(everyone[short], redraw)
        elapsed = time.perf_counter() - t0
        new = tracker['cache'].pop((g, 'recheck'))
        if not _same(new['genomes'], base['genomes'][short.numpy()]):
            raise ValueError('recheck capture rows differ from shortlist order')
        both = native.pooled(native.rows(res, short), rres)
        perm1 = permutation(64, tie_gen).numpy()
        stage1 = pareto.select_survivors(base['captures'], base['production_F'], short.numpy(),
                                         new['captures'], new['production_F'], perm1)
        if not _same(stage1.ranking.objectives[:, 3], both.fitness.numpy()):
            raise ValueError('pooled64 ordinary F aggregation differs')
        order1 = stage1.ranking.order
        pick = torch.from_numpy(order1[:32].copy())
        order = short[pick]
        changed = mu - len(set(order.tolist()) & set(order0[:mu].tolist()))
        arrays = {f'{prefix}_{name}': value for prefix, data in (('base', base), ('recheck', new))
                  for name, value in data.items()}
        arrays.update(shortlist=short.numpy(), pick=pick.numpy(), pre_permutation=tracker['pre'],
                      shortlist_permutation=perm0, survivor_permutation=perm1,
                      shortlist_order=order0, survivor_order=order1,
                      base_objectives=stage0.ranking.objectives, pooled_objectives=stage1.ranking.objectives)
        tracker['pending'] = {'gen': g, 'arrays': arrays,
                              'stage0': stage0.ranking.audit(), 'stage1': stage1.ranking.audit(),
                              'out': Path(ev.cfg.logging.output_dir)}
        tracker['pre'] = None
        return dict(order=order, chosen=native.rows(both, pick), shortlist=short, draw=redraw,
                    res=rres, pick=pick, changed=changed, t=elapsed)

    def write(self, row):
        if row.get('event') == 'founders':
            if row['ids'] != list(range(32)) or row['copies']:
                raise ValueError('exact full population import required')
            tracker['parents'] = list(row['ids'])
        if 'gen' in row:
            pending = tracker['pending']
            if pending is None or pending['gen'] != row['gen']:
                raise ValueError('selection record missing at native lineage write')
            arrays = pending['arrays']
            if tracker['parents'] is None:
                # Native run already verifies/truncates this log to its checkpoint prefix.
                previous = [json.loads(line) for line in Path(self.fh.name).read_text().splitlines()]
                if not previous or previous[-1].get('gen') != row['gen'] - 1:
                    raise ValueError('resume lineage prefix lacks preceding native parents')
                tracker['parents'] = list(previous[-1]['survivors'])
            ids = np.asarray(tracker['parents'] + [child['id'] for child in row['children']], dtype=np.int64)
            short, pick = arrays['shortlist'], arrays['pick']
            if (ids.shape != (256,) or len(np.unique(ids)) != 256
                    or ids[short].tolist() != row['recheck']['ids']
                    or ids[short[pick]].tolist() != row['survivors']):
                raise ValueError('native lineage IDs do not match captured candidate order')
            arrays['candidate_ids'] = ids
            target = pending['out'] / 'selection' / f'g{row["gen"]:03d}.npz'
            target.parent.mkdir(exist_ok=True)
            # A resumed checkpoint may leave an uncommitted future-generation file; only
            # byte-identical recomputation can reuse it. No committed evidence is replaced.
            if target.exists():
                with np.load(target, allow_pickle=False) as old:
                    if set(old.files) != set(arrays) or any(not _same(old[k], v) for k, v in arrays.items()):
                        raise ValueError('uncommitted selection file differs on deterministic replay')
            else:
                temporary = target.with_suffix('.npz.tmp')
                with temporary.open('wb') as stream:
                    np.savez_compressed(stream, **arrays)
                    stream.flush()
                    os.fsync(stream.fileno())
                temporary.replace(target)
            record = {'arm': configured['arm'], 'path': str(target.relative_to(pending['out'])),
                      'sha256': sha(target), 'base_shape': [256, 32], 'recheck_shape': [64, 32],
                      'survivor_lives': 64, 'candidate_raw_sha256': hashlib.sha256(
                          arrays['base_genomes'].tobytes()).hexdigest(),
                      'stage0_pareto': pending['stage0'], 'stage1_pareto': pending['stage1'],
                      'selection_order': short[pick].tolist(), 'extra_lives': 0, 'extra_rng_draws': 0}
            row = {**row, 'selection': record}
            tracker['records'].append(record)
            tracker['parents'] = list(row['survivors'])
            tracker['pending'] = None
        return original_write(self, row)

    evaluator_class.draw, evaluator_class.__call__ = draw, evaluate
    evaluator_class.columns, native.rank_desc = columns, rank_desc
    native.recheck, native.Lineage.write = recheck, write
    try:
        yield tracker
    finally:
        evaluator_class.draw, evaluator_class.__call__ = original_draw, original_call
        evaluator_class.columns, native.rank_desc = original_columns, original_rank
        native.recheck, native.Lineage.write = original_recheck, original_write
