"""Present the completed fixed population panel; no simulation or endpoint selection."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
from pathlib import Path

STUDY = Path(__file__).resolve().parents[1]
GROUPS = ('G8', 'mean4', 'pareto4', 'AO')
WORLDS = ('patch', 'pool', 'persistent', 'blink80_20', 'transfer')


def read(path):
    return json.loads(path.read_text())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def display(stat):
    return f"{stat['mean']:.4f} ± {stat['se']:.4f}"


def generate():
    summary = read(STUDY / 'summary.json')
    terminal = read(STUDY / 'study_complete.json')
    assert summary['status'] == terminal['status'] == 'complete'
    assert terminal['summary_sha256'] == sha(STUDY / 'summary.json')
    targets = ('TABLES.md', 'population_rows.csv', 'population_acquisition.svg', 'population_acquisition.png',
               'cached_fresh_ranks.svg', 'cached_fresh_ranks.png', 'tables_receipt.json')
    assert not any((STUDY / name).exists() for name in targets)
    text = ['# All-survivor development panel', '',
            'All 97 fixed genomes, including repeated genotypes, on 32 shared fresh life seeds per world. '
            'Values are mean ± paired-life SE. Population SE uses the 32 shared-seed population means; '
            'genomes are not independent life replicates. All ranks and retention margins are exploratory. '
            'No historical reporting endpoint is replaced.', '',
            '## Population means', '',
            '| World | Population | Captures | Refilled packets | Ordinary F | Physical cost |',
            '|---|---|---:|---:|---:|---:|']
    metrics = ('captures', 'total_patch_refill_harvest', 'F', 'cost')
    for world in WORLDS:
        for group in GROUPS:
            row = summary['population_means'][world][group]
            text.append('| ' + ' | '.join((world, group, *(display(row[m]) for m in metrics))) + ' |')
    text += ['', '## Paired population contrasts', '',
             '| World | Contrast | Captures | Refilled packets | Ordinary F | Physical cost |',
             '|---|---|---:|---:|---:|---:|']
    for world in WORLDS:
        for contrast, row in summary['population_paired'][world].items():
            text.append('| ' + ' | '.join((world, contrast, *(display(row[m]) for m in metrics))) + ' |')
    text += ['', '## Fixed reporting endpoints', '',
             'Ranks below are one-based. The joint statistic is the minimum of the three capture fractions '
             'against the fixed historical AO scales; the tie breaker keeps the original 50/25/25 F weights. '
             'It has no naive linear SE.', '',
             '| Population | Fixed global row | Native ID | Cached rank | Fresh rank | Fresh joint minimum |',
             '|---|---:|---:|---:|---:|---:|']
    endpoints = {}
    for group in GROUPS:
        row = next(r for r in summary['descriptive_orders'][group]['rows'] if r['reported_endpoint'])
        endpoints[group] = row
        cached = row.get('cached16_rank')
        text.append(f"| {group} | {row['index']} | {row['native_id']} | "
                    f"{'unavailable' if cached is None else cached+1} | {row['fresh_descriptive_rank']+1} | "
                    f"{row['fresh_joint_minimum']:.4f} |")
    text += ['', '## Survivor variation', '',
             'The counts use point estimates from this same development panel. They are not confirmations '
             'of selected winners; inspecting 96 survivors creates selection optimism.', '',
             '| Population | Unique raw genomes | Joint minimum: lowest / median / highest | '
             'Rows with all three old-world point ratios ≥ 90% AO |',
             '|---|---:|---:|---:|']
    variations = {}
    for group in GROUPS[:3]:
        rows = summary['descriptive_orders'][group]['rows']
        minima = sorted(r['fresh_joint_minimum'] for r in rows)
        labels = [r['label'] for r in rows]
        count = sum(all(summary['old_world_retention'][w][label]['mean_capture_ratio'] >= .9
                        for w in ('pool', 'persistent', 'blink80_20')) for label in labels)
        unique = len({r['raw_sha256'] for r in summary['row_manifest'] if r['group'] == group})
        variations[group] = dict(unique_raw_genomes=unique, joint_minimum_range=[minima[0], minima[-1]],
                                 joint_minimum_median=(minima[15]+minima[16])/2,
                                 point_only_three_old_world_retention_rows=count)
        text.append(f"| {group} | {unique} | {minima[0]:.4f} / {(minima[15]+minima[16])/2:.4f} / "
                    f"{minima[-1]:.4f} | {count}/32 |")
    text += ['', 'The full per-row values are in `population_rows.csv` and `summary.json`. '
             'The scatterplot shows capture means only, with the fixed reporting genomes outlined. '
             'The second plot compares cached and fresh ranks without choosing replacement endpoints.', '']
    (STUDY / 'TABLES.md').write_text('\n'.join(text))
    with (STUDY / 'population_rows.csv').open('x', newline='') as stream:
        fields = ['group', 'local_row', 'native_id', 'raw_sha256', 'reported_endpoint', 'world']
        fields += [f'{m}_{suffix}' for m in metrics for suffix in ('mean', 'se')]
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        for row in summary['row_manifest']:
            for world in WORLDS:
                values = summary['absolute'][world][row['label']]
                writer.writerow(dict(group=row['group'], local_row=row['row'], native_id=row['native_id'],
                    raw_sha256=row['raw_sha256'], reported_endpoint=row['reported_endpoint'], world=world,
                    **{f'{m}_{suffix}': values[m][suffix] for m in metrics for suffix in ('mean', 'se')}))
    os.environ['MPLCONFIGDIR'] = str(STUDY / 'terminal_tables/matplotlib_cache')
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    colors = dict(G8='#31688e', mean4='#d17613', pareto4='#7b3294')
    fig, axes = plt.subplots(2, 2, figsize=(10, 8), constrained_layout=True)
    for axis, world in zip(axes.flat, WORLDS[1:], strict=True):
        ao_x = summary['absolute']['patch']['AO']['captures']['mean']
        ao_y = summary['absolute'][world]['AO']['captures']['mean']
        axis.axvline(ao_x, color='#777777', linestyle=':', linewidth=.8)
        axis.axhline(ao_y, color='#777777', linestyle=':', linewidth=.8)
        for group in GROUPS[:3]:
            rows = [r for r in summary['row_manifest'] if r['group'] == group]
            x = [summary['absolute']['patch'][r['label']]['captures']['mean'] for r in rows]
            y = [summary['absolute'][world][r['label']]['captures']['mean'] for r in rows]
            axis.scatter(x, y, s=20, alpha=.55, color=colors[group], label=group)
            fixed = next(i for i, r in enumerate(rows) if r['reported_endpoint'])
            axis.scatter([x[fixed]], [y[fixed]], s=110, facecolors='none', edgecolors=colors[group], linewidths=2)
        axis.scatter([ao_x], [ao_y], color='black', marker='*', s=100, label='AO')
        axis.set(xlabel='Patch captures per life', ylabel=f'{world} captures per life')
        axis.grid(alpha=.15)
    axes[0, 0].legend(fontsize=8)
    fig.suptitle('All fixed survivors: 32-life development means\nOutlined points are historical reporting genomes')
    for suffix in ('svg', 'png'):
        fig.savefig(STUDY / f'population_acquisition.{suffix}', dpi=130)
    plt.close(fig)
    fig, axes = plt.subplots(1, 2, figsize=(9, 4), constrained_layout=True)
    for axis, group in zip(axes, ('mean4', 'pareto4'), strict=True):
        rows = summary['descriptive_orders'][group]['rows']
        axis.plot([1, 32], [1, 32], color='#888888', linestyle=':', linewidth=1)
        axis.scatter([r['cached16_rank']+1 for r in rows], [r['fresh_descriptive_rank']+1 for r in rows],
                     color=colors[group], s=22)
        row = endpoints[group]
        axis.scatter([row['cached16_rank']+1], [row['fresh_descriptive_rank']+1], s=125,
                     facecolors='none', edgecolors='black', linewidths=1.5)
        axis.set(title=group, xlabel='Cached selection rank (1 is highest)',
                 ylabel='Fresh development rank (1 is highest)', xlim=(0, 33), ylim=(0, 33))
        axis.grid(alpha=.15)
    fig.suptitle('Different life samples; rank disagreement alone does not establish causation')
    for suffix in ('svg', 'png'):
        fig.savefig(STUDY / f'cached_fresh_ranks.{suffix}', dpi=130)
    plt.close(fig)
    receipt = dict(status='complete', summary_sha256=sha(STUDY / 'summary.json'),
                   source_sha256=sha(Path(__file__)), variations=variations,
                   files={name: sha(STUDY / name) for name in targets[:-1]},
                   new_lives=0, builds=0, random_draws=0)
    (STUDY / 'tables_receipt.json').write_text(json.dumps(receipt, indent=2)+'\n')
    print(json.dumps(receipt))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--write', action='store_true')
    args = parser.parse_args()
    if args.write:
        generate()
    else:
        print('Source only; presentation waits for the complete fixed panel.')
