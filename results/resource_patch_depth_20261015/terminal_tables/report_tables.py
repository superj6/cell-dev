"""Render completed, independently checked depth-study summaries without new simulations."""
from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path

STUDY = Path(__file__).resolve().parents[1]
ROLES = ('AO', 'G8_joint', 'Pareto4_joint', 'depth8_joint')
LABELS = ('Original AO', 'Earlier G8', 'Starting Pareto4', 'New descendant')
WORLDS = ('patch', 'pool', 'persistent', 'blink80_20', 'transfer', 'reserved_capacity3')
WORLD_LABELS = ('Trained patches', 'Pooled food', 'Persistent pursuit', 'Longer cue gaps',
                'Revealed patch layout', 'Reserved capacity-three layout')
METRICS = ('captures', 'total_patch_initial_harvest', 'total_patch_refill_harvest', 'physical_cost', 'F', 'n_end')


def read(path):
    return json.loads(path.read_text())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def cell(stat):
    return f"{stat['mean']:.6f} ± {stat['se']:.6f}"


def main():
    summary = read(STUDY / 'summary.json')
    complete = read(STUDY / 'study_complete.json')
    if (summary['status'] != 'complete' or complete['status'] != 'complete'
            or complete['summary_sha256'] != sha(STUDY / 'summary.json')
            or complete['total_calls'] != 97342):
        raise ValueError('complete protocol-bound study required')
    outputs = ('TABLES.md', 'confirmation_rows.csv', 'acquisition.png', 'acquisition.svg',
               'primary_differences.png', 'primary_differences.svg')
    if any((STUDY / name).exists() for name in outputs):
        raise ValueError('first rendering refuses existing outputs')
    rows = []
    for world in WORLDS:
        for role in ROLES:
            row = dict(world=world, role=role)
            for metric in METRICS:
                stat = summary['absolute'][world][role][metric]
                row.update({f'{metric}_{key}': stat[key] for key in ('mean', 'se', 'lower_3se', 'upper_3se')})
            rows.append(row)
    with (STUDY / 'confirmation_rows.csv').open('x', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]), lineterminator='\n')
        writer.writeheader()
        writer.writerows(rows)
    lines = ['# Fresh confirmation tables', '',
             'Means ± SE over 512 shared lives per world. The primary contrast compares the new descendant',
             'with the fixed development-selected starting Pareto4 genome. These are life uncertainties,',
             'not replication of the evolutionary search. Initial stock and refill harvest remain separate.', '',
             '| World | AO captures | G8 captures | Starting Pareto4 | New descendant |',
             '|---|---:|---:|---:|---:|']
    for world, label in zip(WORLDS, WORLD_LABELS, strict=True):
        lines.append('| ' + label + ' | ' + ' | '.join(
            cell(summary['absolute'][world][role]['captures']) for role in ROLES) + ' |')
    lines += ['', '| World | Capture difference | Refill difference | Physical-cost difference | Fitness difference |',
              '|---|---:|---:|---:|---:|']
    for world, label in zip(WORLDS, WORLD_LABELS, strict=True):
        paired = summary['paired'][world][summary['primary_contrast']]
        lines.append('| ' + label + ' | ' + ' | '.join(cell(paired[metric]) for metric in
            ('captures', 'total_patch_refill_harvest', 'physical_cost', 'F')) + ' |')
    lines += ['', '| Older world | Relative to | Capture ratio | 90% retention margin | Lower 3 SE > 0 |',
              '|---|---|---:|---:|---|']
    for world, records in summary['old_world_retention'].items():
        for comparison, row in records.items():
            ratio = row['mean_capture_ratio']
            ratio_text = 'undefined' if ratio is None else f'{100*ratio:.2f}%'
            lines.append(f"| {world} | {comparison.removeprefix('depth8_joint_vs_')} | {ratio_text} | "
                         f"{cell(row['retained_90_percent_margin'])} | {row['lower_3se_positive']} |")
    lines += ['', 'A positive 90% margin permits up to 10% loss; it does not establish lossless retention.',
              'The reserved layout is one new physical combination, with more initial food than training.', '']
    (STUDY / 'TABLES.md').write_text('\n'.join(lines))
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt

    colors = ('#637381', '#4485b5', '#db923c', '#21866d')
    fig, axes = plt.subplots(2, 3, figsize=(12, 6.5), constrained_layout=True)
    for ax, world, label in zip(axes.flat, WORLDS, WORLD_LABELS, strict=True):
        stats = [summary['absolute'][world][role]['captures'] for role in ROLES]
        for i, (stat, color) in enumerate(zip(stats, colors, strict=True)):
            ax.errorbar(i, stat['mean'], yerr=3*stat['se'], fmt='o', color=color, capsize=4)
        ax.set(title=label, xticks=range(4), xticklabels=('AO', 'G8', 'Start', 'New'), ylabel='Food captures / life')
        ax.grid(axis='y', alpha=.2)
        ax.set_ylim(bottom=0)
    fig.suptitle('Same four genomes across six worlds — mean ± 3 SE on 512 fresh shared lives')
    fig.savefig(STUDY / 'acquisition.svg')
    fig.savefig(STUDY / 'acquisition.png', dpi=150)
    plt.close(fig)
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.5), constrained_layout=True)
    for ax, metric, label in zip(axes, ('captures', 'F'), ('Capture difference', 'Ordinary fitness difference'),
                               strict=True):
        stats = [summary['paired'][world][summary['primary_contrast']][metric] for world in WORLDS]
        ax.errorbar([stat['mean'] for stat in stats], range(6),
                    xerr=[3*stat['se'] for stat in stats], fmt='o', color=colors[3], capsize=4)
        ax.axvline(0, color='#999999', linewidth=1)
        ax.set(yticks=range(6), yticklabels=WORLD_LABELS, xlabel=label)
        ax.invert_yaxis()
        ax.grid(axis='x', alpha=.2)
    fig.suptitle('New descendant minus fixed starting reference — paired means ± 3 SE')
    fig.savefig(STUDY / 'primary_differences.svg')
    fig.savefig(STUDY / 'primary_differences.png', dpi=150)
    plt.close(fig)
    receipt = dict(status='complete', source_sha256=sha(Path(__file__)),
                   summary_sha256=sha(STUDY / 'summary.json'),
                   output_pins={name: sha(STUDY / name) for name in outputs}, new_lives=0)
    with (STUDY / 'reviews/tables_receipt.json').open('x') as stream:
        json.dump(receipt, stream, indent=2)
        stream.write('\n')
    print(json.dumps(dict(status='complete', output_files=len(outputs), new_lives=0)))


if __name__ == '__main__':
    main()
