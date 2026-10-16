"""Freeze deliberate development-seed reuse and isolated renderers; no builds or lives."""
from __future__ import annotations

import argparse
import hashlib
import shutil
import subprocess
import sys
from dataclasses import asdict, replace

from common import ROOT, STUDY, read, save, sha

sys.dont_write_bytecode = True
sys.path.insert(0, str(ROOT))
BASE = ROOT / 'results/resource_patch_baseline_20261015'
BASE_PROTOCOL = 'b1b4cbdb2c1d2d7f2e1eeac05d28a8944dc4ed8e0fc3fdd3efc5190d9ded55cc'
RUNTIME = ('common.py', 'monitor.py', 'renderer.py', 'worker.py', 'analyze.py', 'baseline_accounting.py',
           'prepare.py', 'PROTOCOL.md')


def prepare():
    import numpy as np
    from renderer import isolated_source

    from src.life import spec

    if any((STUDY / key).exists() for key in ('protocol.json', 'READY.json', 'release.json', 'attempt.json', 'raw')):
        raise ValueError('first preparation only')
    baseline, complete, budget = (read(BASE / name) for name in
                                  ('protocol.json', 'measurement_complete.json', 'budget.json'))
    if (sha(BASE / 'protocol.json') != BASE_PROTOCOL or complete['status'] != 'complete' or
            budget['status'] != 'complete' or complete['backend_calls'] != 456 or
            complete['row_index_sha256'] != sha(BASE / 'row_index.json') or
            complete['summary_sha256'] != sha(BASE / 'summary.json')):
        raise ValueError('exact completed baseline required')
    for name, digest in baseline['production_pins'].items():
        if sha(ROOT / name) != digest:
            raise ValueError('production changed since accepted baseline: ' + name)
    if sha(STUDY / 'baseline_accounting.py') != sha(BASE / 'analyze.py'):
        raise ValueError('reused accounting source differs from accepted baseline')
    inputs = STUDY / 'inputs'
    inputs.mkdir(parents=True, exist_ok=True)
    for name in ('protocol.json', 'measurement_complete.json', 'budget.json', 'row_index.json', 'summary.json'):
        shutil.copyfile(BASE / name, inputs / ('baseline_' + name))
    raw = np.load(BASE / 'inputs/raw_genomes.npy', allow_pickle=False)
    packed = np.load(BASE / 'inputs/packed_genomes.npy', allow_pickle=False)
    ancestry = read(BASE / 'inputs/ancestry.json')
    if raw.shape != (33, 875) or packed.shape != (33, 875) or raw.dtype != np.float32 or packed.dtype != np.float64:
        raise ValueError('baseline genome tables differ')
    for name in ('raw_genomes.npy', 'packed_genomes.npy', 'ancestry.json'):
        if sha(BASE / 'inputs' / name) != baseline['input_pins']['inputs/' + name]:
            raise ValueError('baseline genotype input pin differs')
    roles = {}
    for i, (role, row) in enumerate((('AO_rank0', 0), ('AM_reference', 32))):
        if (hashlib.sha256(raw[row].tobytes()).hexdigest() != ancestry['row_raw_sha256'][row] or
                hashlib.sha256(packed[row].tobytes()).hexdigest() != ancestry['row_packed_sha256'][row]):
            raise ValueError('fixed raw/packed genotype differs')
        roles[role] = dict(row=i, baseline_row=row, **ancestry['roles'][role])
    np.save(inputs / 'raw_genomes.npy', raw[[0, 32]], allow_pickle=False)
    np.save(inputs / 'packed_genomes.npy', packed[[0, 32]], allow_pickle=False)
    if spec.V6.pack_genomes(raw[[0, 32]], 'hexprism').tobytes() != packed[[0, 32]].tobytes():
        raise ValueError('unchanged genotype decoding differs')
    shutil.copyfile(ROOT / 'src/life/kernel.c', inputs / 'kernel.native.c')
    (inputs / 'renderer.c').write_text(isolated_source((inputs / 'kernel.native.c').read_text()))
    reused, native_engineering = [], []
    index = read(BASE / 'row_index.json')
    destination = inputs / 'baseline_rows'
    destination.mkdir()
    for item in baseline['schedule']:
        if item['group'] != 'engineering' and not (item['group'] == 'reference' and item['world'] == 'patch'):
            continue
        origin = BASE / item['path']
        if sha(origin) != index[item['path']]['sha256']:
            raise ValueError('baseline raw row changed')
        target = destination / origin.name
        shutil.copyfile(origin, target)
        record = dict(item, baseline_public_path=str(origin.relative_to(ROOT)),
                      copied_path=str(target.relative_to(STUDY)), sha256=sha(target))
        (native_engineering if item['group'] == 'engineering' else reused).append(record)
    if len(reused) != 64 or len(native_engineering) != 8:
        raise ValueError('exact64 native and8 engineering baseline rows required')
    seeds = list(range(52480000, 52480032))
    for role in roles:
        if sorted(x['seed'] for x in reused if x['role'] == role) != seeds:
            raise ValueError('paired development seed reuse differs')
    save(inputs / 'reuse.json', dict(status='deliberate_development_reuse', native_rows=reused,
        engineering_rows=native_engineering, baseline_protocol_sha256=BASE_PROTOCOL,
        baseline_manifest_sha256=sha(BASE / 'manifest.json'), source_roles=roles,
        seeds=seeds, confirmation_eligible=False, newly_reserved_blocks=[],
        interpretation='Same32 baseline reference seeds, not fresh confirmation; no namespace scan or random draw.'), exclusive=True)
    worlds = {name: spec.World(**record['world']) for name, record in baseline['worlds'].items()}
    worlds['patch256'] = replace(worlds['patch'], T=256)
    world_records = {name: dict(world=asdict(w), vector=spec.V6.pack_world(w).tolist(), abi=6)
                     for name, w in worlds.items()}
    schedule = []

    def add(group, role, mode, world, seed, backend, pair, comparison=None):
        schedule.append(dict(index=len(schedule), group=group, role=role, row=roles[role]['row'], mode=mode,
            world=world, seed=seed, backend=backend, pair=pair, comparison=comparison,
            path=f'raw/{len(schedule):03d}_{group}_{mode}_{role}_{seed}_{backend}.npz'))

    for item in native_engineering:
        add('native_equivalence', item['role'], 'native', item['world'], item['seed'],
            'C_fast' if item['fast'] else 'C_full', item['pair'], item['copied_path'])
    for mode in ('constant1', 'constant055'):
        for role, seed in (('AO_rank0', 42000000), ('AM_reference', 42000001)):
            for backend in ('C_full', 'C_fast', 'Python'):
                add('constant_parity', role, mode, 'patch256', seed, backend, mode + '_' + role)
    for mode in ('constant1', 'constant055'):
        for role in ('AO_rank0', 'AM_reference'):
            for seed in seeds:
                add('science', role, mode, 'patch', seed, 'C_fast', None)
    if len(schedule) != 148 or sum(x['group'] == 'science' for x in schedule) != 128:
        raise ValueError('fixed call inventory differs')
    protocol = dict(study='Whole-life removal of current-stock sensory modulation in fixed ancestors', abi=6,
        engine_revision=baseline['source_revision'], preparation_head=subprocess.check_output(
            ['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
        roles=roles, seeds=seeds, worlds=world_records, schedule=schedule,
        amplitudes={'native': None, 'constant1': 1.0, 'constant055': 0.55},
        reused_native_lives=64, reused_engineering_rows=8, scientific_lives=128, engineering_lives=20,
        backend_calls=148, call_breakdown=dict(C_full=8, C_fast=136, Python=4),
        startup_lives=0, raster_cap=0, fate_cap=0, extinct_charge=True,
        package_budget=dict(cpu_seconds=600, wall_seconds=1200),
        preparation_allowance=dict(cpu_seconds=90, wall_seconds=120),
        budget=dict(cpu_seconds=510, wall_seconds=1080, workers=1, threads=1, cleanup_margin_seconds=5,
            rss_bytes=2*1024**3, address_space_bytes=8*1024**3, minimum_available_bytes=4*1024**3),
        production_pins=baseline['production_pins'],
        source_pins={name: sha(STUDY / name) for name in RUNTIME},
        input_pins={str(p.relative_to(STUDY)): sha(p) for p in sorted(inputs.rglob('*')) if p.is_file()},
        interpretation=['Development reuse: no512-case admission, external controller, evolution, mutation or endpoint selection.',
            'Only patch-rate amplitude changes; source/capture laws, candidate envelope, action rules and prices remain fixed.',
            'Actions, tissue development, receptor events and stock/admission/spill trajectories may diverge causally.',
            'Two constant brightnesses do not isolate information from every signal-strength/confidence effect.',
            'Current-stock modulation removal is not complete stock blindness or a memory-specific lesion.',
            'FIFO initial/refill income is observed-trajectory provenance; aggregates do not establish revisits or rate learning.',
            'Report every planned row, status and component cost; valid guards/extinction remain, corruption invalidates completeness.'])
    save(STUDY / 'protocol.json', protocol, exclusive=True)
    save(STUDY / 'READY.json', dict(status='prepared_unreleased', protocol_sha256=sha(STUDY / 'protocol.json'),
        backend_calls_planned=148, reused_native_rows=64, builds=0, simulation_calls=0, random_draws=0), exclusive=True)
    print('Prepared128 scientific+20 engineering new calls; reused64 native science rows; zero execution.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--prepare', action='store_true')
    if parser.parse_args().prepare:
        prepare()
    else:
        print('source only; no materialization, build or life')
