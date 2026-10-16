"""Pinned external loader of all retained population rows; ordinary evolution is unchanged."""
from __future__ import annotations

import copy
import hashlib
import json
from contextlib import contextmanager
from pathlib import Path

STUDY = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def loader_identity(record):
    return {'version': 1, **copy.deepcopy(record),
            'source_pins': {name: sha(STUDY / name) for name in ('population_loader.py', 'search.py')}}


def extended_identity(base, configured):
    result = copy.deepcopy(base)
    if 'population_start' in result:
        raise ValueError('base identity already contains an external population loader')
    result['population_start'] = copy.deepcopy(configured)
    return result


def read_population(path, layout, record):
    """Decode only the exact retained row bytes, never scores, RNG or checkpoint state."""
    import torch

    if sha(path) != record['file_sha256']:
        raise ValueError('retained population file differs')
    saved = json.loads(Path(path).read_text())
    if (saved['dims'] != layout.dims.__dict__ or len(saved['genomes']) != 32
            or saved['ids'] != record['old_ids'] or len(set(saved['ids'])) != 32
            or record['new_ids'] != list(range(32)) or record['shape'] != [32, 875]):
        raise ValueError('exact full population layout/order/crosswalk required')
    population = torch.stack([layout.from_dict(row) for row in saved['genomes']])
    row_hashes = [hashlib.sha256(row.numpy().tobytes()).hexdigest() for row in population]
    if (population.shape != (32, 875) or population.dtype != torch.float32
            or not bool(torch.isfinite(population).all())
            or hashlib.sha256(population.numpy().tobytes()).hexdigest() != record['population_raw_sha256']
            or row_hashes != record['row_sha256']):
        raise ValueError('retained population bytes differ')
    expected = [{'old_id': old, 'new_id': i, 'row': i, 'raw_sha256': row_hashes[i]}
                for i, old in enumerate(saved['ids'])]
    if record['old_to_new'] != expected:
        raise ValueError('retained population crosswalk differs')
    return population


@contextmanager
def installed(native, configured):
    """Only replace founder loading, restoring it even after failure; no selection adapter."""
    from omegaconf import OmegaConf

    record = {key: value for key, value in configured.items() if key not in ('version', 'source_pins')}
    if configured != loader_identity(record):
        raise ValueError('configured loader/source identity differs')
    relative = Path(record['population_file'])
    if relative.is_absolute() or '..' in relative.parts:
        raise ValueError('population path must stay inside the study')
    path = (STUDY / relative).resolve()
    if not path.is_relative_to(STUDY.resolve()):
        raise ValueError('population path escapes study')
    original = native.seed_genome

    def load(cfg, layout):
        if (OmegaConf.to_container(cfg.population_start, resolve=True) != configured
                or Path(cfg.evolve.seed_genome).resolve() != path or int(cfg.evolve.mu) != 32):
            raise ValueError('native population-start configuration differs')
        return read_population(path, layout, record)

    native.seed_genome = load
    try:
        yield
    finally:
        native.seed_genome = original
