"""Four native generations with ordinary/Pareto selection and a cached common joint endpoint."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import sys
from pathlib import Path

os.environ.setdefault('ATEN_CPU_CAPABILITY', 'avx2')
sys.dont_write_bytecode = True
STUDY = Path(__file__).resolve().parent
os.environ['CELL_DEV_CACHE'] = str(STUDY / 'build-cache')
ROOT = STUDY.parents[1]
sys.path.insert(0, str(ROOT))


def raw_sha(value):
    return hashlib.sha256(value.numpy().tobytes()).hexdigest()


def one_identity(original, expected, population, selection, on_capture=None):
    from population_loader import extended_identity as population_identity
    from selection import extended_identity as selection_identity
    calls = 0

    def capture():
        nonlocal calls
        if calls:
            raise ValueError('exactly one numerical identity invocation per search worker')
        calls += 1
        capture.calls = calls
        value = original()
        if value != expected:
            raise ValueError('native numerical identity differs from the frozen current source/binary record')
        if on_capture is not None:
            on_capture(value)
        return selection_identity(population_identity(value, population), selection)

    capture.calls = 0
    return capture


def _endpoint_record(out, cfg, identity, *, write_genome=False):
    """Derive from the already evaluated final32; no backend, evaluator or RNG invocation."""
    import numpy as np

    from common import read, sha
    from selection import ENDPOINT_RULE, endpoint_from_arrays
    from src import checkpoint
    from src.genome import Layout

    out = Path(out)
    saved = checkpoint.load(out / 'checkpoint.pt')
    checkpoint.validate(saved, cfg, identity)
    state = saved['state']
    if (state['generation'] != 4 or state['evals'] != 1024 or state['rc_lives'] != 2048
            or tuple(state['population'].shape) != (32, 875)):
        raise ValueError('joint endpoint requires the exact completed generation4 checkpoint')
    pin = saved['logs']['lineage.jsonl']
    data = (out / 'lineage.jsonl').read_bytes()
    if len(data) != pin['bytes'] or hashlib.sha256(data).hexdigest() != pin['sha256']:
        raise ValueError('endpoint lineage does not match checkpoint')
    rows = [json.loads(line) for line in data.splitlines()]
    last = rows[-1]
    record = last['selection']
    if (last['gen'] != 3 or last['survivors'] != state['ids'].tolist()
            or record['path'] != 'selection/g003.npz' or sha(out / record['path']) != record['sha256']
            or record['arm'] != cfg.retention_selection.arm):
        raise ValueError('endpoint selection arrays do not match terminal lineage')
    with np.load(out / record['path'], allow_pickle=False) as file:
        arrays = {name: file[name] for name in file.files}
    indices = arrays['shortlist'][arrays['pick']]
    expected_population = arrays['base_genomes'][indices]
    if (expected_population.dtype != state['population'].numpy().dtype
            or expected_population.tobytes() != state['population'].numpy().tobytes()):
        raise ValueError('endpoint captured selection genomes differ from final checkpoint rows')
    selected = endpoint_from_arrays(arrays, state['ids'].numpy())
    rank = selected.selected
    layout, _ = Layout.load(out / 'best_genome.json')
    path = out / 'joint_genome.json'
    if write_genome:
        if path.exists():
            raise ValueError('joint endpoint output already exists')
        layout.save(state['population'][rank], path)
    _, genome = Layout.load(path)
    if raw_sha(genome) != raw_sha(state['population'][rank]):
        raise ValueError('joint genome is not the cached-rule selected final row')
    result = {'status': 'complete', 'arm': str(cfg.retention_selection.arm), 'generation': 4,
              'rank': rank, 'id': int(state['ids'][rank]), 'genome_file_sha256': sha(path),
              'genome_raw_sha256': raw_sha(genome), 'population_raw_sha256': raw_sha(state['population']),
              'checkpoint_sha256': sha(out / 'checkpoint.pt'), 'selection_path': record['path'],
              'selection_sha256': record['sha256'], 'rule': ENDPOINT_RULE, 'selection': selected.audit(),
              'protocol_sha256': sha(STUDY / 'protocol.json'), 'added_lives': 0, 'random_draws': 0}
    if not write_genome and read(out / 'endpoint_selection.json') != result:
        raise ValueError('joint endpoint receipt differs from exact cached selection')
    return result


def write_endpoint(out, cfg, identity):
    from common import save

    receipt = _endpoint_record(out, cfg, identity, write_genome=True)
    save(Path(out) / 'endpoint_selection.json', receipt, exclusive=True)
    return receipt


def verify_endpoint(out, cfg, identity):
    """Return the exact rederived endpoint receipt, suitable for the confirmation reader."""
    return _endpoint_record(out, cfg, identity)


def complete_search(cfg, arm, identity):
    """Bind completed ordinary native outputs without a further numerical identity call."""
    import torch
    from omegaconf import OmegaConf

    from common import read, sha
    from src import checkpoint
    from src.genome import Layout

    out = Path(cfg.logging.output_dir)
    saved = checkpoint.load(out / 'checkpoint.pt')
    checkpoint.validate(saved, cfg, identity)
    if (arm not in ('mean', 'pareto') or saved['state']['generation'] != 4 or saved['state']['evals'] != 1024
            or saved['state']['rc_lives'] != 2048):
        raise ValueError('native search checkpoint counts differ')
    if read(out / 'determinism.json') != identity:
        raise ValueError('native recorded identity differs')
    for name, meta in saved['logs'].items():
        data = (out / name).read_bytes()
        if len(data) != meta['bytes'] or checkpoint.sha(data) != meta['sha256']:
            raise ValueError('native completed log differs from checkpoint')
    if checkpoint.config_identity(OmegaConf.load(out / 'config.yaml')) != checkpoint.config_identity(cfg):
        raise ValueError('native saved configuration differs')
    curves = [json.loads(line) for line in (out / 'curves.jsonl').read_text().splitlines()]
    lineage = [json.loads(line) for line in (out / 'lineage.jsonl').read_text().splitlines()]
    generations = [row for row in lineage if 'gen' in row]
    if ([row['gen'] for row in curves] != list(range(4))
            or [row['gen'] for row in generations] != list(range(4))
            or [row['gen'] for row in curves if 'valid' in row] != [0, 3]):
        raise ValueError('native generation/validation schedule differs')
    for g, row in enumerate(curves):
        if (row['evals'] != 320 * (g + 1) or row['recheck_k'] != 64
                or any(not math.isfinite(float(row[key])) or float(row[key]) != 0
                       for key in ('pop_invalid', 'pop_mismatch', 'recheck_invalid'))
                or not all(math.isfinite(float(row[key])) for key in ('fitness', 'mean_fitness', 'pop_guard'))):
            raise ValueError('native count, finiteness or invalid/mismatch failure')
    if any(row.get('event') == 'ledger_mismatch' for row in lineage):
        raise ValueError('native ledger mismatch recorded')
    founders = [row for row in lineage if row.get('event') == 'founders']
    if len(founders) != 1 or founders[0]['ids'] != list(range(32)) or founders[0]['copies'] != []:
        raise ValueError('native full-population import differs')
    for row in generations:
        if (len(row['children']) != 224 or len(row['seeds']) != 8
                or len(row['recheck']['seeds']) != 8 or len(row['recheck']['ids']) != 64
                or row['selection']['arm'] != arm
                or row['selection']['path'] != f'selection/g{row["gen"]:03d}.npz'
                or sha(out / row['selection']['path']) != row['selection']['sha256']):
            raise ValueError('native lineage evaluation dimensions differ')
    results = [json.loads(line) for line in (out / 'results.jsonl').read_text().splitlines()]
    if len(results) != 1:
        raise ValueError('one native final result required')
    final = results[0]
    if (final['generations'] != 4 or final['evals'] != 1280 or final['lives'] != 2
            or final['founders_sampled'] != 0 or final['top_best_rank'] != 0
            or final['invalid_lives'] != 0 or final['mismatch_lives'] != 0
            or not math.isfinite(float(final['F']))):
        raise ValueError('native final result scope or health differs')
    layout, best = Layout.load(out / 'best_genome.json')
    population = read(out / 'population.json')
    table = torch.stack([layout.from_dict(row) for row in population['genomes']])
    state = saved['state']
    if (population['ids'] != state['ids'].tolist() or table.shape != (32, 875)
            or table.numpy().tobytes() != state['population'].numpy().tobytes()
            or best.numpy().tobytes() != table[0].numpy().tobytes()):
        raise ValueError('native endpoint/population differs from checkpoint rank order')
    endpoint = verify_endpoint(out, cfg, identity)
    startup = read(out / 'search_startup.json')
    base_identity = {key: value for key, value in identity.items()
                     if key not in ('population_start', 'retention_selection')}
    if (startup['identity'] != base_identity or startup['startup_lives'] != 4
            or startup['patches']['lives'] != 2
            or startup['protocol_sha256'] != sha(STUDY / 'protocol.json')):
        raise ValueError('four-call search startup proof differs')
    names = ('checkpoint.pt', 'config.yaml', 'determinism.json', 'curves.jsonl', 'lineage.jsonl',
             'population.json', 'best_genome.json', 'results.jsonl', 'search_startup.json',
             'joint_genome.json', 'endpoint_selection.json',
             *(f'selection/g{g:03d}.npz' for g in range(4)))
    return {'status': 'complete', 'arm': arm, 'research_lives': 10278, 'startup_lives': 4,
            'protocol_sha256': sha(STUDY / 'protocol.json'), 'release_sha256': sha(STUDY / 'release.json'),
            'count_proof': {'selection': 10240, 'valid': 32, 'final': 6, 'growth_half': 2,
                            'native_evals': 1280, 'generations': 4, 'children_per_generation': 224},
            'endpoint': endpoint,
            'health': {'pop_invalid': [row['pop_invalid'] for row in curves],
                       'pop_mismatch': [row['pop_mismatch'] for row in curves],
                       'recheck_invalid': [row['recheck_invalid'] for row in curves],
                       'pop_guard': [row['pop_guard'] for row in curves],
                       'final_guard_rate': final['guard_rate'],
                       'guard_scope': 'First8/recheck8 statuses and F retained; guards keep ordinary penalties.'},
            'output_pins': {name: sha(out / name) for name in names}, 'checkpoint_log_pins': saved['logs']}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--arm', choices=('mean', 'pareto'))
    args = parser.parse_args()
    if args.arm is None:
        print(json.dumps({'status': 'dry_run', 'scope': 'one named arm only after explicit release'}))
        return
    from common import checked_release, parent_check, save, sha
    protocol = checked_release()
    release_sha = sha(STUDY / 'release.json')
    parent_check()
    if Path(os.environ['CELLDEV_ATTEMPT_PATH']) != STUDY / 'execution' / args.arm / 'attempt.json':
        raise ValueError('search arm does not match the owned monitor phase')
    from omegaconf import OmegaConf
    from population_loader import installed as population_installed
    from population_loader import loader_identity
    from selection import installed as selection_installed
    from selection import selection_identity

    import src.evolve as native
    from measure import check_patch_truth
    from src import checkpoint, run
    from src.life.evaluate import LifeEvaluator

    cfg = OmegaConf.load(STUDY / protocol['configs'][args.arm]['path'])
    population = OmegaConf.to_container(cfg.population_start, resolve=True)
    selection = OmegaConf.to_container(cfg.retention_selection, resolve=True)
    if (population != loader_identity(protocol['population_start'])
            or selection != selection_identity(args.arm, protocol['selection_worlds'])
            or cfg.seed != protocol['native_seed']):
        raise ValueError('configured population/selection identity or native seed differs')
    if Path(cfg.logging.output_dir) != STUDY / 'runs' / args.arm or Path(cfg.logging.output_dir).exists():
        raise ValueError('first attempt refuses previous search output')
    from population_loader import extended_identity as population_identity
    from selection import extended_identity as extend_selection
    identity = extend_selection(population_identity(protocol['expected_numerical_identity'], population), selection)
    patches = check_patch_truth()

    def record_startup(base):
        save(Path(cfg.logging.output_dir) / 'search_startup.json',
             {'identity': base, 'patches': patches, 'startup_lives': 4,
              'protocol_sha256': sha(STUDY / 'protocol.json')}, exclusive=True)

    original = checkpoint.numerical_identity
    capture = one_identity(original, protocol['expected_numerical_identity'], population, selection, record_startup)
    checkpoint.numerical_identity = capture
    try:
        with (population_installed(native, population),
              selection_installed(native, LifeEvaluator, selection) as tracker):
            run.main(cfg)
    finally:
        checkpoint.numerical_identity = original
    if (capture.calls != 1 or len(tracker['records']) != 4 or tracker['cache']
            or tracker['pending'] is not None or tracker['pre'] is not None):
        raise ValueError('search numerical identity or four complete selection records differ')
    if checked_release() != protocol or sha(STUDY / 'release.json') != release_sha:
        raise ValueError('source or release changed during search')
    write_endpoint(Path(cfg.logging.output_dir), cfg, identity)
    receipt = complete_search(cfg, args.arm, identity)
    save(Path(cfg.logging.output_dir) / 'search_complete.json', receipt, exclusive=True)


if __name__ == '__main__':
    main()
