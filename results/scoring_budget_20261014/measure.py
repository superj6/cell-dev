"""Freeze completed P references, then confirm all fixed S/P/D endpoints; dry-run default."""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import shutil
import sys
from dataclasses import asdict
from pathlib import Path

os.environ.setdefault('ATEN_CPU_CAPABILITY', 'avx2')
ROOT = Path(__file__).resolve().parents[2]
STUDY = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from run_budgeted import check_protocol, check_ready, check_references, save, sha  # noqa: E402

RUNS = (52091, 52092)
MAPPING = {'52091': 51089, '52092': 51090}
LABELS = ['D51089', 'D51090', 'P52091', 'P52092', 'S52091_final_rank0', 'S52092_final_rank0']
PRIMARY = ((4, 2), (5, 3))
SECONDARY = ((4, 0), (5, 1), (2, 0), (3, 1))


def require_parent():
    if os.environ.get('CELLDEV_SCORING_BUDGET_MONITOR_PID') != str(os.getppid()):
        raise RuntimeError('measurement phases require their exact budget monitor parent')


def equal(actual, expected, message):
    if actual != expected:
        raise ValueError(message)


def load_p_auditor(protocol):
    path = STUDY / 'sources/P_analyze.py'
    equal(sha(path), protocol['P_analysis_sha256'], 'fixed pure P analyzer differs')
    loader = importlib.util.spec_from_file_location('S_completed_P_audit', path)
    module = importlib.util.module_from_spec(loader)
    loader.loader.exec_module(module)
    return module


def freeze_references():
    """No golden checks, compilation or lives: audit both completed P endpoints, freeze together."""
    require_parent()
    protocol, ready = check_protocol(), check_ready()
    destination, pending = STUDY / 'references', STUDY / 'references.pending'
    if destination.exists() or pending.exists():
        raise ValueError('reference preparation cannot resume or overwrite any existing artifact')
    p_study = ROOT / protocol['P_study']
    # Completion is checked before opening any P outcomes or importing its offline auditor.
    budget = json.loads((p_study / 'budget.json').read_text())
    if budget.get('status') != 'complete' or budget.get('running') or budget.get('queued'):
        raise ValueError('both P searches and all confirmation must be complete before reference freezing')
    for name, expected in protocol['P_pins'].items():
        equal(sha(p_study / name), expected, 'P protocol/monitor changed')
    auditor = load_p_auditor(protocol)
    summary, _ = auditor.analyze(p_study)
    if summary.get('status') != 'complete' or summary.get('completed_genome_lives') != 37548:
        raise ValueError('completed P independent audit did not cover the whole registered study')
    import numpy as np

    from src.genome import Layout

    pending.mkdir()
    copied = {}
    for old_seed in MAPPING.values():
        copied[f'genome_D{old_seed}.json'] = STUDY / f'inputs/founder_D{old_seed}.json'
    for seed in RUNS:
        copied[f'genome_P{seed}.json'] = p_study / f'runs/s{seed}/best_genome.json'
        for name in ('checkpoint.pt', 'best_genome.json', 'lineage.jsonl', 'curves.jsonl'):
            copied[f'P/runs/s{seed}/{name}'] = p_study / f'runs/s{seed}/{name}'
        for name in (f'configs/s{seed}.yaml', f'initialization/s{seed}.npy'):
            copied['P/' + name] = p_study / name
    for name in ('protocol.json', 'ready.json', 'budget.json', 'initialization.json',
                 'seed_audit.json', 'search_health.json'):
        copied['P/' + name] = p_study / name
    for relative, original in copied.items():
        target = pending / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(original, target)
        equal(sha(target), sha(original), 'copied P reference source differs')
    from src import checkpoint

    for seed in RUNS:
        evidence = summary['searches'][str(seed)]
        folder = pending / f'P/runs/s{seed}'
        equal(sha(folder / 'checkpoint.pt'), evidence['checkpoint_sha256'], 'P checkpoint changed after audit')
        saved = checkpoint.load(folder / 'checkpoint.pt')
        for name in ('lineage.jsonl', 'curves.jsonl'):
            equal(sha(folder / name), saved['logs'][name]['sha256'], 'P copied search log differs')
            equal((folder / name).stat().st_size, saved['logs'][name]['bytes'], 'P copied search log size differs')
        _, raw = Layout.load(pending / f'genome_P{seed}.json')
        equal(hashlib.sha256(raw.numpy().tobytes()).hexdigest(), evidence['raw_genome_sha256'],
              'P final genome changed after independent audit')
    equal(json.loads((pending / 'P/budget.json').read_text()), summary['resources'], 'P resource receipt changed')
    save(pending / 'P/completed_audit.json', summary)
    paths = [pending / name for name in protocol['reference_files']]
    equal([p.name for p in paths], [f'genome_{label}.json' for label in LABELS[:4]], 'reference roles differ')
    genomes = np.stack([Layout.load(path)[1].numpy() for path in paths])
    with (pending / 'genotypes.npy').open('wb') as stream:
        np.save(stream, genomes, allow_pickle=False)
    # No input may change between the audit and the atomic complete reference receipt.
    for relative, original in copied.items():
        equal(sha(pending / relative), sha(original), 'reference source changed after audit')
    equal(check_ready(), ready, 'release pins changed during reference audit')
    report = {'status': 'complete', 'simulated_lives': 0, 'runs': list(RUNS), 'mapping': MAPPING,
              'labels': LABELS[:4], 'P_completed_genome_lives': 37548,
              'P_checkpoint_sha256': {str(seed): sha(pending / f'P/runs/s{seed}/checkpoint.pt') for seed in RUNS},
              'genotype_sha256': {label: hashlib.sha256(row.tobytes()).hexdigest()
                                 for label, row in zip(LABELS[:4], genomes, strict=True)},
              'protocol_sha256': sha(STUDY / 'protocol.json'), 'ready': ready,
              'files': {str(path.relative_to(pending)): sha(path) for path in sorted(pending.rglob('*'))
                        if path.is_file()},
              'rule': 'Both fixed completed P generation16 rank0 endpoints; no outcome-based replacement or selection.'}
    save(pending / 'report.json', report)
    pending.rename(destination)
    check_references(protocol)


def duration_mixture(rows, candidate, reference):
    """Average durations within seed before measuring across-seed uncertainty."""
    import numpy as np

    if set(rows) != {'768', '1024', '1536'}:
        raise ValueError('need exactly the three registered durations')
    effects = [np.asarray(rows[str(t)][candidate]['F']) - np.asarray(rows[str(t)][reference]['F'])
               for t in (768, 1024, 1536)]
    values = np.stack(effects)
    if values.shape != (3, 256) or not np.isfinite(values).all():
        raise ValueError('duration effects must be finite and contain exactly 256 paired life arrays')
    return values.mean(axis=0)


def confirm_endpoints():
    require_parent()
    protocol, ready = check_protocol(), check_ready()
    reference_snapshot = check_references(protocol)
    out = STUDY / 'confirmation'
    if out.exists():
        raise ValueError('confirmation cannot restart or reuse existing artifacts')
    expected = {'labels': LABELS, 'primary_pairs': [list(pair) for pair in PRIMARY],
                'secondary_pairs': [list(pair) for pair in SECONDARY], 'seed_block': 105,
                'seeds': list(range(52_050_000, 52_050_256)), 'durations': [768, 1024, 1536], 'threads': 2}
    if any(protocol['confirmation'][key] != value for key, value in expected.items()):
        raise ValueError('fixed six-role S/P/D confirmation scope differs')
    import numpy as np
    from omegaconf import OmegaConf

    from scripts.taskvar_confirm import COLS, atomic_npz, compare_rows, score_row
    from scripts.taskvar_gates import paired
    from src import checkpoint
    from src.genome import Layout
    from src.life import spec
    from src.life.evaluate import LifeEvaluator

    # Golden engine validation is inside the released CPU cap; it never selects any endpoint.
    identity = checkpoint.numerical_identity()
    equal(identity, protocol['expected_numerical_identity'], 'confirmation numerical identity differs')
    paths = [STUDY / 'references' / name for name in protocol['reference_files']]
    checkpoint_hashes, search_health = {}, {}
    for seed in RUNS:
        folder = STUDY / f'runs/s{seed}'
        cfg = OmegaConf.load(ROOT / protocol['configs'][str(seed)]['path'])
        saved = checkpoint.load(folder / 'checkpoint.pt')
        checkpoint.validate(saved, cfg, identity)
        state = saved['state']
        equal(state['generation'], 8, 'incomplete S search endpoint')
        equal([r['gen'] for r in state['curves']], list(range(8)), 'incomplete S search history')
        search_health[str(seed)] = {key: max(float(row[key]) for row in state['curves'])
                                   for key in ('pop_invalid', 'pop_mismatch', 'recheck_invalid')}
        if any(search_health[str(seed)].values()):
            raise ValueError('invalid or mismatched S search lives stop endpoint inference')
        selected = folder / 'best_genome.json'
        _, genome = Layout.load(selected)
        equal(genome.numpy().tobytes(), state['population'][0].numpy().tobytes(), 'S final rank0 differs')
        paths.append(selected)
        checkpoint_hashes[str(seed)] = sha(folder / 'checkpoint.pt')
    save(STUDY / 'search_health.json', search_health)
    layout, _ = Layout.load(paths[0])
    genomes = np.stack([Layout.load(path)[1].numpy() for path in paths])
    references = np.load(STUDY / 'references/genotypes.npy', allow_pickle=False)
    equal(genomes[:4].tobytes(), references.tobytes(), 'frozen pre-search P/D reference genotypes differ')
    seeds = protocol['confirmation']['seeds']
    cfg = OmegaConf.load(ROOT / protocol['configs'][str(RUNS[0])]['path'])
    evaluator = LifeEvaluator(cfg, layout)
    worlds = {str(t): spec.world('catch_speck_l4', T=t, d0=.5, d_min=.25, sigma=.4, lam_s=4.)
              for t in (768, 1024, 1536)}
    manifest = {'format': 1, 'labels': LABELS, 'seeds': seeds, 'seed_block': 105,
                'genotype_sha256': {label: hashlib.sha256(row.tobytes()).hexdigest()
                                   for label, row in zip(LABELS, genomes, strict=True)},
                'checkpoint_sha256': checkpoint_hashes, 'search_health': search_health,
                'protocol_sha256': sha(STUDY / 'protocol.json'), 'numerical_identity': identity, 'ready': ready,
                'frozen_references': reference_snapshot, 'worlds': {key: asdict(w) for key, w in worlds.items()},
                'selection': 'Both P generation16 rank0 references frozen before S; '
                             'both S generation8 rank0; no reselection'}
    save(out / 'manifest.json', manifest)
    atomic_npz(out / 'genotypes.npz', genomes=genomes, labels=np.asarray(LABELS))
    all_rows, index, completed = {}, {}, 0
    report = {'report_only': True, 'status': 'incomplete', 'worlds': {}, 'primary': {},
              'planned_genome_lives': 4608, 'completed_genome_lives': 0, 'genome_lives': 0}
    for name, world in worlds.items():
        rows = {}
        for i in range(6):
            equal(check_ready(), ready, 'release changed during confirmation')
            check_references(protocol, reference_snapshot)
            rows[i] = score_row(out / name, i, genomes, world, seeds, evaluator, 2)
            completed += len(seeds)
            path = out / name / f'row_{i:04d}.npz'
            index[str(path.relative_to(out))] = sha(path)
            save(out / 'row_index.json', index)
            report.update(completed_genome_lives=completed, genome_lives=completed)
            save(out / 'report.json', report)
        atomic_npz(out / name / 'scores.npz', seeds=np.asarray(seeds, dtype=np.uint64),
                   genome_indices=np.arange(6), **{key: np.stack([rows[i][key] for i in range(6)]) for key in COLS})
        all_rows[name] = rows
        report['worlds'][name] = {LABELS[i] + '__vs__' + LABELS[j]: compare_rows(rows[i], rows[j], world)
                                  for i, j in PRIMARY + SECONDARY}
    for i, j in PRIMARY:
        effects = duration_mixture(all_rows, i, j)
        estimate = paired(effects, np.zeros_like(effects))
        report['primary'][LABELS[i]] = {**estimate, 'above_3se': estimate['mean'] > 3 * estimate['se'],
                                      'at_least_0p5': estimate['mean'] >= .5}
    report['secondary'] = {LABELS[i] + '__vs__' + LABELS[j]:
                           paired(duration_mixture(all_rows, i, j), np.zeros(len(seeds))) for i, j in SECONDARY}
    equal(completed, 4608, 'complete confirmation life count')
    equal(check_ready(), ready, 'release changed before final confirmation receipt')
    check_references(protocol, reference_snapshot)
    report.update(status='complete', independent_search_pairs=2,
                  interpretation='Fresh paired life SE describes fixed endpoints. Equal selection genome-lives do not '
                                 'equal actual CPU or duration-adjusted exposure. Both outcomes and signs retained.')
    save(out / 'report.json', report)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group()
    group.add_argument('--freeze-references', action='store_true')
    group.add_argument('--confirm-child', action='store_true')
    args = parser.parse_args()
    if args.freeze_references:
        freeze_references()
    elif args.confirm_child:
        confirm_endpoints()
    else:
        print(json.dumps({'status': 'dry_run', 'confirmation_genome_lives': 4608,
                          'planned_genome_lives': 37484, 'seed_block': 105, 'simulated_lives': 0}))


if __name__ == '__main__':
    main()
