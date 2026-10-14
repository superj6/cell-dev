"""Describe copied-gene connectivity in completed G search logs; no simulation."""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
from collections import Counter
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
HELPER = ROOT / 'results/weight_updates_20261014/offline_analysis_preparation/genome_audit.py'
HELPER_SHA = '4a2d38965d87ec5bdabb7ab39947e99da35a49a7d827a025291def659b5c91ab'
ARCHIVE_SHA = '412c53ce2a6c2baa8a7816eb3c8db24b01188fb4bebea78e9ed512ec9db0e59a'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load_helper():
    if sha(HELPER) != HELPER_SHA:
        raise ValueError('genetic replay helper changed')
    spec = importlib.util.spec_from_file_location('copy_audit_genetics', HELPER)
    helper = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(helper)
    return helper


def connectivity(active, w, a, slot):
    """Exact nonzero coefficient paths, with inactive genes masked; no activation inference."""
    if not active[slot]:
        raise ValueError('copy must be active')
    direct = np.flatnonzero(a[:, slot] != 0).tolist()
    outgoing = [int(k) for k in np.flatnonzero(active & (w[:, slot] != 0)) if k != slot]
    reached, pending = {slot}, [slot]
    while pending:
        source = pending.pop()
        for target in np.flatnonzero(active & (w[:, source] != 0)):
            target = int(target)
            if target not in reached:
                reached.add(target)
                pending.append(target)
    readouts = np.flatnonzero(np.any(a[:, sorted(reached)] != 0, axis=1)).tolist()
    return {'direct_readout_rows': direct, 'other_gene_targets': outgoing,
            'reachable_active_genes': sorted(reached), 'reachable_readout_rows': readouts,
            'has_readout_path': bool(readouts)}


def observe(helper, genome, origins, generation, individual, retained):
    active = helper.view(genome, 'act') > .5
    return [dict(generation=generation, individual=individual, slot=int(slot), origin=int(origins[slot]),
                 retained=retained, **connectivity(active, helper.view(genome, 'W')[:, :16],
                                                   helper.view(genome, 'A'), int(slot)))
            for slot in np.flatnonzero(origins >= 16)]


def run_archive(archive, run, helper):
    folder = archive / f'runs/s{run}'
    lines = [json.loads(line) for line in (folder / 'lineage.jsonl').read_text().splitlines()]
    founder = helper.from_json(json.loads((archive / 'inputs/founder_row38.json').read_text()))
    expected_population, expected_origins, replay = helper.replay(lines, founder)
    stored = json.loads((folder / 'population.json').read_text())
    actual = np.stack([helper.from_json({'dims': stored['dims'], 'params': p}) for p in stored['genomes']])
    if (not helper.same(expected_population, actual) or replay['final_ids'] != stored['ids']
            or not np.array_equal(expected_origins, stored['origins'])):
        raise ValueError('independent replay differs from saved final population/origins')
    population = {0: founder.copy()}
    origin = np.where(helper.view(founder, 'act') > .5, np.arange(16), -1)
    origins = {0: origin.copy()}
    for item in lines[0]['copies']:
        population[item['id']] = helper.point(founder, item['ops'])
        origins[item['id']] = origin.copy()
    next_origin, observations, survivor_observations, mutations = 16, [], [], []
    innovations = []
    for row in lines[1:]:
        generation = row['gen']
        candidates, ancestry = dict(population), dict(origins)
        for item in row['children']:
            pa, pb, mask, ops = item['pa'], item['pb'], item['mask'], item['ops']
            bits = np.asarray([(mask >> k) & 1 for k in range(17)], dtype=bool)
            mixed = helper.silence(np.where(bits[helper.UNITS], population[pa], population[pb]))
            gene_origin = np.where(bits[:16], origins[pa], origins[pb]).copy()
            for slot in np.flatnonzero(gene_origin >= 16):
                kinds = Counter()
                for field, indices, _delta in ops['mut']:
                    if field == 'A' and indices[1] == slot:
                        kinds['direct_readout'] += 1
                    if field == 'W' and indices[1] == slot and indices[0] != slot:
                        kinds['other_gene_outgoing'] += 1
                    if ((field == 'W' and indices[0] == slot)
                            or (field in ('b', 'lam', 's0', 'Q') and indices[0] == slot)):
                        kinds['private_or_incoming'] += 1
                mutations.append({'generation': generation, 'individual': item['id'], 'slot': int(slot),
                                  'origin': int(gene_origin[slot]), 'counts': dict(kinds)})
            child = helper.point(mixed, ops)
            if 'dup' in ops:
                source, destination = ops['dup']
                child = helper.duplicate(child, source, destination)
                innovations.append({'origin': next_origin, 'generation': generation, 'individual': item['id'],
                                    'slot': destination, 'source_origin': int(gene_origin[source]),
                                    'birth_child_retained': item['id'] in row['survivors']})
                gene_origin[destination] = next_origin
                next_origin += 1
            if 'del' in ops:
                child = helper.delete(child, ops['del'])
                gene_origin[ops['del']] = -1
            candidates[item['id']], ancestry[item['id']] = child, gene_origin
            observations += observe(helper, child, gene_origin, generation, item['id'], item['id'] in row['survivors'])
        population = {k: candidates[k] for k in row['survivors']}
        origins = {k: ancestry[k] for k in row['survivors']}
        matrix = np.stack(list(origins.values()))
        if helper.registry(matrix) != row['registry']:
            raise ValueError('per-generation origin registry differs')
        for individual in population:
            survivor_observations += observe(helper, population[individual], origins[individual],
                                             generation, individual, True)
    if not helper.same(np.stack(list(population.values())), expected_population):
        raise ValueError('observed replay differs from independent replay')
    summaries = []
    for innovation in innovations:
        oid = innovation['origin']
        offspring = [r for r in observations if r['origin'] == oid]
        survivors = [r for r in survivor_observations if r['origin'] == oid]
        trials = [r for r in mutations if r['origin'] == oid]
        counts = Counter()
        for record in trials:
            counts.update(record['counts'])
        summaries.append({**innovation, 'offspring_carriers': len(offspring),
                          'offspring_with_readout_path': sum(r['has_readout_path'] for r in offspring),
                          'retained_offspring_with_path': sum(
                              r['has_readout_path'] and r['retained'] for r in offspring),
                          'survivor_carrier_observations': len(survivors),
                          'survivor_observations_with_path': sum(r['has_readout_path'] for r in survivors),
                          'post_crossover_carrier_mutation_opportunities': len(trials),
                          'recorded_mutations': dict(counts),
                          'final_rank0': bool(np.any(expected_origins[0] == oid)),
                          'last_retained_generation': max((r['generation'] for r in survivors), default=None)})
    return {'run': run, 'genetic_replay_verified': True, 'generations': 16, 'offspring': 3584,
            'innovations': summaries, 'offspring_carriers': observations, 'survivor_carriers': survivor_observations,
            'carrier_mutation_opportunities': mutations,
            'final_rank0': observe(helper, expected_population[0], expected_origins[0], 15, stored['ids'][0], True),
            'totals': {'duplication_events': len(innovations),
                       'origins_retained_at_birth': sum(r['birth_child_retained'] for r in innovations),
                       'origins_with_any_offspring_readout_path': sum(
                           r['offspring_with_readout_path'] > 0 for r in summaries),
                       'origins_with_retained_readout_path': sum(
                           r['survivor_observations_with_path'] > 0 for r in summaries),
                       'offspring_carrier_observations': len(observations),
                       'offspring_carriers_with_path': sum(r['has_readout_path'] for r in observations),
                       'survivor_carrier_observations': len(survivor_observations),
                       'survivor_carriers_with_path': sum(r['has_readout_path'] for r in survivor_observations)}}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--archive', type=Path, default=ROOT / 'results/structural_20261013')
    parser.add_argument('--out', type=Path, default=Path(__file__).resolve().parent)
    args = parser.parse_args()
    provenance = args.archive / 'provenance.json'
    if sha(provenance) != ARCHIVE_SHA:
        raise ValueError('original structural archive manifest changed')
    for relative, info in json.loads(provenance.read_text())['artifacts'].items():
        path = args.archive / relative
        if sha(path) != info['sha256'] or path.stat().st_size != info['bytes']:
            raise ValueError('structural archive artifact changed: ' + relative)
    helper = load_helper()
    runs = [run_archive(args.archive, run, helper) for run in (51089, 51090)]
    result = {'status': 'exploratory_completed_data', 'simulated_lives': 0,
              'archive_provenance_sha256': sha(provenance), 'helper_sha256': sha(HELPER), 'runs': runs,
              'limits': ['Exact nonzero coefficient paths describe potential coupling, '
                         'not reachable activity or fitness use.',
                         'Paths can be erased, transferred or combined by crossover; '
                         'origins do not label individual edges.',
                         'Mutation opportunities are post-crossover carriers before structural operations; '
                         'later deletion can remove them.',
                         'Repeated related candidates and shared environments are not independent replicates.',
                         'Only two fixed completed searches and16 generations are covered; '
                         'no policy comparison follows.']}
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / 'summary.json').write_text(json.dumps(result, indent=2, allow_nan=False) + '\n')
    print(json.dumps({str(r['run']): {'totals': r['totals'], 'final_rank0': r['final_rank0'],
                                    'final_origins': [i for i in r['innovations'] if i['final_rank0']]}
                      for r in runs}, indent=2))


if __name__ == '__main__':
    main()
