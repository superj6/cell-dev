"""Plot complete AO acquisition, retention and cost evidence without simulations."""
import hashlib
import json
from pathlib import Path

import matplotlib

matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

HERE = Path(__file__).resolve().parent
path = HERE.parent / 'analysis_result/summary.json'
s = json.loads(path.read_text())
assert s['status'] == 'complete' and s['total_calls'] == 138488
worlds = ['pool', 'persistent', 'blink80_5', 'blink80_20', 'turn100_blink80_20']
labels = ['POOL', 'Persistent', 'Brief gaps', 'Longer gaps', 'Turns + longer gaps']
branches = [('unchanged', 'Unchanged allocation', '#c37b39'), ('balanced', 'More POOL trials', '#087d8b')]
absolute, contrasts = s['absolute'], s['contrasts']
fig, axes = plt.subplots(3, 2, figsize=(14, 12), constrained_layout=True)
plotted = {'summary_sha256': hashlib.sha256(path.read_bytes()).hexdigest(), 'trajectories': {}, 'paired': {}}
for ax, world, title in zip(axes.flat, ['pool', 'persistent', 'blink80_20'],
                            ['POOL: older task', 'Persistent: earlier moving target', 'Longer gaps: acquired challenge']):
    for arm, name, color in branches:
        values = [absolute[world][r]['captures'] for r in ['AN_start', arm + '8', arm + '24']]
        ax.errorbar([0, 8, 24], [v['mean'] for v in values], yerr=[v['se'] for v in values],
                    fmt='o-', color=color, capsize=4, label=name)
        plotted['trajectories'][world + '__' + arm] = values
    ax.axhline(absolute[world]['AM_reference']['captures']['mean'], color='#6d737b', ls='--', label='Earlier AM reference')
    ax.set(title=title, xlabel='Additional generations', ylabel='Mean captures per life ± SE', xticks=[0, 8, 24])
    if world == 'pool':
        ax.legend(frameon=False, fontsize=9)
ax = axes[1, 1]
x = np.arange(len(worlds))
for i, (arm, name, color) in enumerate(branches):
    vals = [contrasts[f'within__{w}__{arm}24_minus_AN_start']['captures'] for w in worlds]
    ax.errorbar(x + (i - .5) * .12, [v['mean'] for v in vals], yerr=[3 * v['se'] for v in vals],
                fmt='o', color=color, label=name, capsize=4)
    plotted['paired'][arm] = vals
ax.axhline(0, color='#444', lw=1)
ax.set_xticks(x, labels, fontsize=9)
ax.set(title='Final capture changes from AN start', ylabel='Paired change ± 3 SE')
ax.legend(frameon=False, fontsize=9)
ax = axes[2, 0]
vals = [contrasts[f'within__{w}__balanced24_minus_unchanged24']['captures'] for w in worlds]
ax.errorbar(x, [v['mean'] for v in vals], yerr=[3 * v['se'] for v in vals], fmt='o', color='#087d8b', capsize=4)
ax.axhline(0, color='#444', lw=1)
ax.set_xticks(x, labels, fontsize=9)
ax.set(title='More POOL trials minus unchanged allocation', ylabel='Actual final capture difference ± 3 SE')
plotted['actual_final_branch_differences'] = vals
ax = axes[2, 1]
keys = ['pool', 'persistent', 'blink80_20']
pos = np.arange(len(keys))
plotted['fitness_decomposition'] = {}
for i, (arm, name, color) in enumerate(branches):
    values = [contrasts[f'within__{w}__{arm}24_minus_AN_start'] for w in keys]
    income = [v['capture_income']['mean'] for v in values]
    saving = [sum(v[k]['mean'] for k in ('ordinary_cost', 'guard_cost', 'extinction_cost')) for v in values]
    total = [v['F'] for v in values]
    offset = (i - .5) * .34
    ax.bar(pos + offset, income, .14, color=color, label=name + ': capture income')
    ax.bar(pos + offset + .14, saving, .14, color=color, alpha=.35, label=name + ': cost saving')
    ax.errorbar(pos + offset + .07, [v['mean'] for v in total], yerr=[3 * v['se'] for v in total],
                fmt='o', color=color, capsize=3)
    plotted['fitness_decomposition'][arm] = {'worlds': keys, 'income': income, 'saving': saving, 'F': total}
ax.axhline(0, color='#444', lw=1)
ax.set_xticks(pos + .07, ['POOL', 'Persistent', 'Longer gaps'], fontsize=9)
ax.set(title='Final fitness change: income and savings; dots = total F', ylabel='Change from AN start; total F ± 3 SE')
ax.legend(frameon=False, fontsize=8)
for ax in axes.flat:
    ax.spines[['top', 'right']].set_visible(False)
    ax.grid(axis='y', alpha=.15)
fig.suptitle('AO: more evolution with two fixed task allocations', fontsize=16)
out = HERE / 'figures'
out.mkdir(exist_ok=False)
for suffix in ('png', 'svg'):
    fig.savefig(out / f'retained_depth.{suffix}', dpi=160)
(out / 'plotted_statistics.json').write_text(json.dumps(plotted, indent=2) + '\n')
print(json.dumps({'status': 'complete', 'summary_sha256': plotted['summary_sha256']}))
