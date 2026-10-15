"""Deterministic first-cohort replay from saved parents and recorded operations only."""
from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
from pathlib import Path

import numpy as np
import torch

HERE = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def raw_sha(value):
    return hashlib.sha256(np.asarray(value).tobytes()).hexdigest()


def operations():
    path = HERE / 'replay_ops.py'
    spec = importlib.util.spec_from_file_location('AN_recorded_ops', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def definitions(base, protocol):
    """Use packaged definitions when present; bind the exact actually imported source bytes."""
    root = base / 'production' if (base / 'production/src/genome.py').exists() else base.parents[1]
    sys.path.insert(0, str(root))
    from src.genome import Layout

    for name, module in tuple(sys.modules.items()):
        if name in ('src', 'src.genome', 'src.lattice', 'src.life', 'src.life.spec'):
            path = Path(module.__file__).resolve()
            if not path.is_relative_to(root.resolve()):
                raise ValueError('loaded genome definition is outside the pinned source root')
            if sha(path) != protocol['production_pins'][str(path.relative_to(root.resolve()))]:
                raise ValueError('loaded genome definition source changed')
    return Layout


def initial_population(base, protocol):
    Layout = definitions(base, protocol)
    record = protocol['population_start']
    path = base / record['population_file']
    if sha(path) != record['file_sha256']:
        raise ValueError('imported population file changed')
    saved = json.loads(path.read_text())
    layout, reference = Layout.load(base / protocol['reference']['path'])
    table = torch.stack([layout.from_dict(row) for row in saved['genomes']])
    hashes = [raw_sha(row.numpy()) for row in table]
    if (saved['dims'] != layout.dims.__dict__ or table.shape != (32, 875)
            or table.dtype != torch.float32 or not bool(torch.isfinite(table).all())
            or saved['ids'] != record['old_ids'] or len(set(saved['ids'])) != 32
            or record['new_ids'] != list(range(32)) or record['shape'] != [32, 875]
            or raw_sha(table.numpy()) != record['population_raw_sha256'] or hashes != record['row_sha256']
            or raw_sha(reference.numpy()) != hashes[0]
            or record['old_to_new'] != [{'old_id': old, 'new_id': i, 'row': i, 'raw_sha256': hashes[i]}
                                        for i, old in enumerate(saved['ids'])]):
        raise ValueError('imported ordered population/reference/crosswalk differs')
    return layout, table


def replay_first(layout, initial, lines):
    """Reconstruct the original 32 parents plus all 224 recorded first-generation children."""
    ops = operations()
    if (lines[0]['event'] != 'founders' or lines[0]['sampled'] != 0
            or lines[0]['ids'] != list(range(32)) or lines[0]['copies'] != []
            or lines[1]['gen'] != 0):
        raise ValueError('exact imported founders and first generation required')
    children = lines[1]['children']
    if [child['id'] for child in children] != list(range(32, 256)):
        raise ValueError('all 224 ordered first offspring required')
    reconstructed, signature = [row.clone() for row in initial], []
    for child in children:
        pa, pb, mask = child['pa'], child['pb'], child['mask']
        if (pa not in range(32) or pb not in range(32)
                or not isinstance(mask, int) or mask < 0 or mask >= 1 << layout.n_units
                or set(child['ops']) != {'mut'}):
            raise ValueError('invalid recorded first-cohort parent/crossover/operator')
        units = torch.tensor([(mask >> i) & 1 for i in range(layout.n_units)], dtype=torch.bool)
        mixed = layout.silence(torch.where(units[layout.unit_of], initial[pa], initial[pb]))
        reconstructed.append(ops.point_mutation(layout, mixed, child['ops']))
        signature.append({key: child[key] for key in ('id', 'pa', 'pb', 'mask', 'ops')})
    table = torch.stack(reconstructed).numpy()
    return {'candidate_raw_sha256': raw_sha(table),
            'candidate_row_sha256': [raw_sha(row) for row in table],
            'genetic_signature_sha256': hashlib.sha256(json.dumps(signature, sort_keys=True,
                separators=(',', ':'), allow_nan=False).encode()).hexdigest()}


def first_cohort(study, protocol):
    base = Path(study).resolve()
    for name in ('native_replay.py', 'replay_ops.py'):
        if sha(HERE / name) != protocol['source_pins'][name]:
            raise ValueError('recorded replay helper source changed')
    layout, initial = initial_population(base, protocol)
    runs = {}
    for arm in ('acquisition',):
        folder = base / 'runs' / arm
        marker = json.loads((folder / 'search_complete.json').read_text())
        if (marker['status'] != 'complete' or marker['arm'] != arm
                or marker['protocol_sha256'] != sha(base / 'protocol.json')
                or sha(folder / 'lineage.jsonl') != marker['output_pins']['lineage.jsonl']):
            raise ValueError('completed native lineage binding differs')
        lines = [json.loads(line) for line in (folder / 'lineage.jsonl').read_text().splitlines()]
        runs[arm] = {**replay_first(layout, initial, lines), 'lineage_sha256': sha(folder / 'lineage.jsonl')}
    return {'status': 'passed', 'protocol_sha256': sha(base / 'protocol.json'),
            'initial_population_raw_sha256': raw_sha(initial.numpy()),
            'initial_row_sha256': [raw_sha(row.numpy()) for row in initial],
            'runs': runs, 'initial_rows': 32, 'offspring_per_arm': 224,
            'recorded_first_256_replayed': True,
            'simulated_lives': 0, 'random_draws': 0,
            'limits': ['Reconstructs recorded operations; it does not repeat genetic RNG draws.',
                       'No paired search is present; this proof covers only recorded first-generation bytes.']}
