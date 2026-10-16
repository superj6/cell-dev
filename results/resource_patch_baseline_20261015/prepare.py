"""Materialize exact inherited inputs after the ABI6 milestone; no engine builds, lives or draws."""
from __future__ import annotations

import argparse
import hashlib
import shutil
import subprocess
import sys
from dataclasses import asdict

from common import ROOT, STUDY, read, save, sha

sys.dont_write_bytecode = True
sys.path.insert(0, str(ROOT))
AO = ROOT / 'results/retained_depth_20261015'
POPULATION_RAW = 'd9e04d3a38a9f236e5a450ac869b514d67d143e31573360d8779bb9534cbdc87'
RUNTIME = ('common.py', 'monitor.py', 'worker.py', 'analyze.py', 'prepare.py', 'PROTOCOL.md')


def prepare(revision):
    import numpy as np

    from src.life import spec

    if any((STUDY / n).exists() for n in ('protocol.json', 'READY.json', 'release.json', 'attempt.json', 'raw')):
        raise ValueError('first preparation only')
    actual = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
    if actual != revision or len(revision) != 40 or spec.V6.WORLD_SIZE != 82 or spec.V6.LEDGER_SIZE != 107:
        raise ValueError('explicit final ABI6 milestone required')
    production = {str(p.relative_to(ROOT)): sha(p) for p in sorted((ROOT / 'src').rglob('*'))
                  if p.suffix in ('.py', '.c')}
    for name, digest in production.items():
        committed = subprocess.check_output(['git', 'show', revision + ':' + name], cwd=ROOT)
        if hashlib.sha256(committed).hexdigest() != digest:
            raise ValueError('uncommitted production source: ' + name)
    audit, reservation = read(STUDY / 'namespace/seed_audit.json'), read(STUDY / 'namespace/reservation.json')
    if audit['status'] != 'passed' or reservation['status'] != 'reserved_development_only':
        raise ValueError('accepted development-only namespace required')
    if (reservation['population_seeds'] != list(range(52470000, 52470008)) or
            reservation['reference_seeds'] != list(range(52480000, 52480032))):
        raise ValueError('seed schedule differs')
    endpoints, population = read(AO / 'endpoints.json'), read(AO / 'runs/balanced/population.json')
    ancestor = endpoints['searches']['balanced']
    if (ancestor['generation'], ancestor['rank'], ancestor['rank_zero_id']) != (24, 0, 5336):
        raise ValueError('wrong inherited endpoint')
    if len(population['genomes']) != 32 or len(set(population['ids'])) != 32 or population['ids'][0] != 5336:
        raise ValueError('all32 ordered survivors required')

    def decode(params):
        raw = np.concatenate([np.asarray(params[f.name], dtype=np.float32).reshape(-1)
                              for f in spec.V6.GENOME_FIELDS])
        if raw.shape != (875,) or not np.isfinite(raw).all():
            raise ValueError('finite875-parameter raw genome required')
        return raw

    raw_population = np.stack([decode(row) for row in population['genomes']])
    if hashlib.sha256(raw_population.tobytes()).hexdigest() != POPULATION_RAW or ancestor['population_raw_sha256'] != POPULATION_RAW:
        raise ValueError('ordered population raw bytes differ')
    records = {}
    for role, public_role in (('AO_rank0', 'balanced24'), ('AM_reference', 'AM_reference')):
        item = next(row for row in endpoints['genomes'] if row['role'] == public_role)
        path = AO / item['path']
        raw = decode(read(path)['params'])
        if sha(path) != item['file_sha256'] or hashlib.sha256(raw.tobytes()).hexdigest() != item['raw_sha256']:
            raise ValueError('fixed endpoint raw/file bytes differ')
        records[role] = dict(public_path=str(path.relative_to(ROOT)), file_sha256=sha(path),
                             raw_sha256=item['raw_sha256'], table_row=0 if role == 'AO_rank0' else 32)
        if role == 'AO_rank0' and raw.tobytes() != raw_population[0].tobytes():
            raise ValueError('rank0 is not population row0')
        if role == 'AM_reference':
            raw_am = raw
    inputs = STUDY / 'inputs'
    inputs.mkdir(parents=True, exist_ok=True)
    for target, source in {
        'population.json': AO / 'runs/balanced/population.json',
        'AO_rank0.json': ROOT / records['AO_rank0']['public_path'],
        'AM_reference.json': ROOT / records['AM_reference']['public_path'],
    }.items():
        shutil.copyfile(source, inputs / target)
    raw_table = np.concatenate([raw_population, raw_am[None]])
    packed = spec.V6.pack_genomes(raw_table, 'hexprism')
    np.save(inputs / 'raw_genomes.npy', raw_table, allow_pickle=False)
    np.save(inputs / 'packed_genomes.npy', packed, allow_pickle=False)
    save(inputs / 'ancestry.json', dict(population_shape=[32, 875], table_shape=[33, 875],
        population_raw_sha256=POPULATION_RAW, ids=population['ids'], roles=records,
        row_raw_sha256=[hashlib.sha256(row.tobytes()).hexdigest() for row in raw_table],
        row_packed_sha256=[hashlib.sha256(row.tobytes()).hexdigest() for row in packed],
        sources={str(p.relative_to(ROOT)): sha(p) for p in
                 (AO / 'endpoints.json', AO / 'protocol.json', AO / 'runs/balanced/population.json')}), exclusive=True)
    worlds = {'patch': spec.world('catch_resource_patches_l4')}
    old_worlds = read(AO / 'protocol.json')['worlds']
    for name in ('pool', 'persistent'):
        worlds[name] = spec.World(**old_worlds[name]['world'])
    if any(w.T != 1024 or w.t_open != 0 or w.t0 != 0 or w.flags or w.fork_flags for w in worlds.values()):
        raise ValueError('unmodified full-life ordinary worlds required')
    prices = tuple(spec.COSTS) + ('c_rec', 'c_miss', 'R_cap')
    if any(getattr(worlds['patch'], k) != getattr(worlds['persistent'], k) for k in prices):
        raise ValueError('patch physical prices differ from ancestral persistent world')
    world_records = {name: dict(world=asdict(w), vector=spec.V6.pack_world(w).tolist(), abi=6)
                     for name, w in worlds.items()}
    save(inputs / 'worlds.json', world_records, exclusive=True)
    schedule = []

    def append(group, role, row, world, seed, fast, pair=None):
        schedule.append(dict(index=len(schedule), group=group, role=role, row=row, world=world, seed=seed,
            fast=fast, pair=pair, path=f'raw/{len(schedule):04d}_{group}_{world}_{role}_{seed}.npz'))

    for pair, (role, world, seed) in enumerate((('AO_rank0', 'patch', 42000000),
            ('AM_reference', 'patch', 42000001), ('AO_rank0', 'pool', 42000002),
            ('AM_reference', 'persistent', 42000003))):
        for fast in (False, True):
            append('engineering', role, records[role]['table_row'], world, seed, fast, pair)
    for row in range(32):
        for seed in reservation['population_seeds']:
            append('population', f'row{row:02d}', row, 'patch', seed, True)
    for world in ('patch', 'pool', 'persistent'):
        for role in ('AO_rank0', 'AM_reference'):
            for seed in reservation['reference_seeds']:
                append('reference', role, records[role]['table_row'], world, seed, True)
    if len(schedule) != 456 or sum(row['group'] != 'engineering' for row in schedule) != 448:
        raise ValueError('call inventory differs')
    save(inputs / 'schedule.json', schedule, exclusive=True)
    protocol = dict(study='Inherited pursuit in persistent resource patches', abi=6,
        source_revision=revision, roles=['AO_rank0', 'AM_reference'], worlds=world_records,
        schedule=schedule, population_ids=population['ids'], scientific_lives=448, engineering_lives=8,
        backend_calls=456, startup_lives=0, extinct_charge=True, raster_cap=0, fate_cap=0,
        package_budget=dict(cpu_seconds=450, wall_seconds=900),
        preparation_allowance=dict(cpu_seconds=90, wall_seconds=120,
            includes='namespace audit, materialization, source-only tests/review; no builds or lives'),
        budget=dict(cpu_seconds=360, wall_seconds=780, workers=1, threads=1, cleanup_margin_seconds=5,
                    rss_bytes=2*1024**3, address_space_bytes=8*1024**3, minimum_available_bytes=4*1024**3),
        production_pins=production,
        input_pins={str(p.relative_to(STUDY)): sha(p) for p in sorted(inputs.iterdir())},
        source_pins={name: sha(STUDY / name) for name in RUNTIME},
        seed_audit_sha256=sha(STUDY / 'namespace/seed_audit.json'),
        reservation_sha256=sha(STUDY / 'namespace/reservation.json'),
        interpretation=['All seeds are development-only; no information admission, mutation, evolution or endpoint selection.',
            'Report every row and guard/extinction outcome; fail completeness on accounting/capacity corruption.',
            'FIFO initial/refill provenance is an accounting decomposition, not a source-off counterfactual.',
            'Aggregate food does not establish revisits, switching, memory or learned source rates.',
            'Eight population lives are imprecise screening descriptions; population rows are not independent searches.',
            'Paired AO-minus-AM contrasts use32 shared seeds per world; they are not a new evolutionary causal experiment.'])
    save(STUDY / 'protocol.json', protocol, exclusive=True)
    save(STUDY / 'READY.json', dict(status='prepared_unreleased', protocol_sha256=sha(STUDY / 'protocol.json'),
        source_revision=revision, backend_calls_planned=456, simulation_calls=0, builds=0, random_draws=0), exclusive=True)
    print('Prepared448 scientific+8 engineering calls; no builds or lives.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-revision', required=True)
    prepare(parser.parse_args().source_revision)
