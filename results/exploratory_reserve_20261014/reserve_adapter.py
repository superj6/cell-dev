"""AH external selection adapter; no organism, kernel, or production-source edits."""
from __future__ import annotations

import hashlib
import json
import time
from contextlib import contextmanager
from pathlib import Path

POLICY = {
    'version': 1, 'domain': 'cell-dev:AH:reserve:v1', 'mu': 32, 'offspring': 224,
    'reserved': 2, 'active_generations': [0, 1, 2], 'ordinary_final_generation': 3,
    'initial_lives': 3, 'recheck_k': 64, 'recheck_lives': 4, 'recheck_key': 'all',
    'eligibility': 'all fresh offspring, independent of scores or phenotype',
    'lottery': 'SHA256 ASCII domain|seed|generation|counter, first8 little-endian, rejection modulo shrinking list',
    'shortlist': 'protected2 plus top62 nonprotected by initial F, ordered by full initial rank',
    'survivors': 'protected2 plus top30 nonprotected by pooled F, ordered by full pooled rank',
}
HERE = Path(__file__).resolve().parent


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def reserve_indices(seed, generation):
    """Uniform two-of-224 rejection sampling, with no mutable RNG or native draw consumption."""
    if type(seed) is not int or not 0 <= seed < 2**64 or type(generation) is not int or generation not in range(4):
        raise ValueError('unsigned run seed and generation 0 through 3 required')
    remaining = list(range(32, 256))
    picked, counter = [], 0
    while len(picked) < 2:
        message = f"{POLICY['domain']}|{seed}|{generation}|{counter}".encode('ascii')
        number = int.from_bytes(hashlib.sha256(message).digest()[:8], 'little')
        counter += 1
        bound = len(remaining)
        if number >= (2**64 // bound) * bound:
            continue
        picked.append(remaining.pop(number % bound))
    return picked


def selection_identity(mode):
    if mode not in ('control', 'reserve'):
        raise ValueError('unknown selection arm')
    return {'mode': mode, 'policy': POLICY, 'policy_sha256': digest(POLICY),
            'source_pins': {name: hashlib.sha256((HERE / name).read_bytes()).hexdigest()
                            for name in ('reserve_adapter.py', 'search.py')}}


def extended_identity(base_identity, configured, mode):
    """Bind the output-directory adapter despite native identity only hashing src/."""
    expected = selection_identity(mode)
    if configured != expected:
        raise ValueError('adapter/config selection identity differs')
    if 'external_selection' in base_identity:
        raise ValueError('numerical identity was already extended')
    return dict(base_identity, external_selection=expected)


def state_sha(generator):
    return None if generator is None else hashlib.sha256(generator.get_state().numpy().tobytes()).hexdigest()


@contextmanager
def installed(native, seed, mode, *, parent_ids=None):
    """Wrap only this process's module functions and durable lineage writer.

    parent_ids supports a synthetic interrupted/restarted check. The scientific
    entrypoint deliberately permits no resume or partial run.
    """
    if mode not in ('control', 'reserve'):
        raise ValueError('unknown selection arm')
    original_rank, original_recheck, original_write = native.rank_desc, native.recheck, native.Lineage.write
    ranking, pending = [], {}
    parents = list(range(32)) if parent_ids is None else list(parent_ids)
    if len(parents) != 32 or len(set(parents)) != 32:
        raise ValueError('32 unique parent identities required')

    def rank(fitness, tie_gen=None):
        before = state_sha(tie_gen)
        answer = original_rank(fitness, tie_gen)
        ranking.append({'size': len(fitness), 'fitness': [float(x) for x in fitness], 'order': answer.tolist(),
                        'tie_before_sha256': before, 'tie_after_sha256': state_sha(tie_gen)})
        return answer

    def recheck(ev, everyone, res, g, mu, k, lives, key, tie_gen=None):
        if ((mu, k, lives, key, len(everyone), res.trial_scores.shape[1]) != (32, 64, 4, 'all', 256, 3)
                or g not in range(4) or tie_gen is None or len(ranking) != 1 or ranking[0]['size'] != 256):
            raise ValueError('AH requires the exact native three-ranking-call schedule')
        active = mode == 'reserve' and g in POLICY['active_generations']
        protected = reserve_indices(seed, g) if active else []
        if not active:
            result = original_recheck(ev, everyone, res, g, mu, k, lives, key, tie_gen)
        else:
            ranked = native.rank_desc(res.fitness, tie_gen)
            ordinary = [int(i) for i in ranked.tolist() if int(i) not in protected][:62]
            members = set(ordinary + protected)
            short = ranked[[j for j, i in enumerate(ranked.tolist()) if int(i) in members]]
            draw = native.recheck_draw(ev, g, 3, 4)
            t0 = time.perf_counter()
            rres = ev(everyone[short], draw)
            elapsed = time.perf_counter() - t0
            both = native.pooled(native.rows(res, short), rres)
            pooled_rank = native.rank_desc(both.fitness, tie_gen)
            protected_positions = {j for j, i in enumerate(short.tolist()) if int(i) in protected}
            ordinary_positions = [int(i) for i in pooled_rank.tolist() if int(i) not in protected_positions][:30]
            chosen_positions = set(ordinary_positions) | protected_positions
            pick = pooled_rank[[j for j, i in enumerate(pooled_rank.tolist()) if int(i) in chosen_positions]]
            order = short[pick]
            result = dict(order=order, chosen=native.rows(both, pick), shortlist=short, draw=draw,
                          res=rres, pick=pick, changed=mu - len(set(order.tolist()) & set(ranked[:mu].tolist())), t=elapsed)
        if len(ranking) != 3 or [r['size'] for r in ranking] != [256, 256, 64] or pending:
            raise ValueError('ranking schedule or durable generation boundary differs')
        pending.update(generation=g, mode=mode, active=active, policy_sha256=digest(POLICY),
                       reserve_indices=protected, base_F=[float(x) for x in res.fitness],
                       ranking_calls=list(ranking), shortlist_indices=result['shortlist'].tolist(),
                       pick_positions=result['pick'].tolist(), survivor_indices=result['order'].tolist())
        ranking.clear()
        return result

    def write(lineage, row):
        if 'gen' not in row:
            return original_write(lineage, row)
        if pending.get('generation') != row['gen'] or len(row['children']) != 224:
            raise ValueError('complete policy metadata and all child records required')
        child_ids = [x['id'] for x in row['children']]
        expected = list(range(32 + 224 * row['gen'], 32 + 224 * (row['gen'] + 1)))
        if child_ids != expected:
            raise ValueError('native fresh offspring identifiers differ')
        candidate_ids = parents + child_ids
        if [candidate_ids[i] for i in pending['survivor_indices']] != row['survivors']:
            raise ValueError('policy and native survivors differ')
        metadata = dict(pending, candidate_ids=candidate_ids,
                        reserve_ids=[candidate_ids[i] for i in pending['reserve_indices']])
        result = original_write(lineage, dict(row, exploratory_reserve=metadata))
        parents[:] = row['survivors']
        pending.clear()
        return result

    native.rank_desc, native.recheck, native.Lineage.write = rank, recheck, write
    try:
        yield
        if ranking or pending:
            raise ValueError('selection metadata was not durably written')
    finally:
        native.rank_desc, native.recheck, native.Lineage.write = original_rank, original_recheck, original_write
