"""Plot the complete frozen AM summary; no simulation or selection."""
import hashlib
import json
from pathlib import Path

import matplotlib

matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

HERE = Path(__file__).resolve().parent
STUDY = HERE.parent
path = STUDY / 'analysis_result/summary.json'
summary = json.loads(path.read_text())
assert summary['status'] == 'complete'
worlds = ['pool', 'persistent', 'blink80_5', 'turn100_blink80_5']
labels = ['Ancestral POOL', 'Persistent', 'Brief darkness', 'Turns + darkness']
roles = ['AI_control_start', 'AL_mixture_start', 'current_value_final', 'high_value_final']
names = ['AI ancestor', 'AL start', 'Capture value 500', 'Capture value 2000']
colors = ['#b5b8bd', '#6b7280', '#ce6b35', '#167a8b']
x = np.arange(4)
fig, axes = plt.subplots(2, 2, figsize=(13, 8), constrained_layout=True)
absolute, contrasts = summary['absolute'], summary['contrasts']
plotted = {'summary_sha256': hashlib.sha256(path.read_bytes()).hexdigest(), 'absolute': {}, 'paired': {}}
for index, (role, name, color) in enumerate(zip(roles, names, colors)):
    values = [absolute[w][role]['captures'] for w in worlds]
    axes[0, 0].bar(x + (index - 1.5) * .20, [v['mean'] for v in values], .19,
                   yerr=[v['se'] for v in values], label=name, color=color, capsize=3)
    cells = [absolute[w][role]['n_end'] for w in worlds]
    axes[1, 0].bar(x + (index - 1.5) * .20, [v['mean'] for v in cells], .19,
                   yerr=[v['se'] for v in cells], label=name, color=color, capsize=3)
    plotted['absolute'][role] = {'captures': values, 'terminal_cells': cells}
for index, (role, name, color) in enumerate(zip(roles[2:], names[2:], colors[2:])):
    values = [contrasts[f'within__{w}__{role}_minus_{roles[1]}']['captures'] for w in worlds]
    axes[0, 1].errorbar(x + (index - .5) * .16, [v['mean'] for v in values],
                       yerr=[3 * v['se'] for v in values], fmt='o', color=color, capsize=4, label=name)
    plotted['paired'][role] = values
axes[0, 1].axhline(0, color='#444', lw=1)
for ax in (axes[0, 0], axes[0, 1], axes[1, 0]):
    ax.set_xticks(x, labels, fontsize=9)
    ax.spines[['top', 'right']].set_visible(False)
    ax.grid(axis='y', alpha=.15)
axes[0, 0].set(title='Acquisition across tasks', ylabel='Mean captures per life ± SE')
axes[0, 0].legend(frameon=False, fontsize=9)
axes[0, 1].set(title='Capture change from the same AL start', ylabel='Paired change ± 3 SE')
axes[1, 0].set(title='Physical size', ylabel='Mean terminal cells ± SE')
ax = axes[1, 1]
keys = [(world, role) for world in worlds[:2] for role in roles[2:]]
income, saving, total = [], [], []
for world, role in keys:
    metrics = contrasts[f'within__{world}__{role}_minus_{roles[1]}']
    income.append(metrics['capture_income']['mean'])
    saving.append(sum(metrics[key]['mean'] for key in ('ordinary_cost', 'guard_cost', 'extinction_cost')))
    total.append(metrics['F'])
pos = np.arange(len(keys))
ax.bar(pos - .14, income, .28, color='#167a8b', label='Capture income')
ax.bar(pos + .14, saving, .28, color='#bd9a5b', label='Cost saving (incl. penalties)')
ax.errorbar(pos, [v['mean'] for v in total], yerr=[3 * v['se'] for v in total],
            fmt='o', color='#222', capsize=4, label='Total F ± 3 SE')
ax.axhline(0, color='#444', lw=1)
ax.set_xticks(pos, ['POOL\nvalue 500', 'POOL\nvalue 2000', 'Persistent\nvalue 500', 'Persistent\nvalue 2000'], fontsize=9)
ax.set(title='Where the training-task fitness change comes from', ylabel='Paired F change from AL start')
ax.legend(frameon=False, fontsize=8)
ax.spines[['top', 'right']].set_visible(False)
ax.grid(axis='y', alpha=.15)
fig.suptitle('AM: does a stronger capture incentive buy retained capability?', fontsize=15)
plotted['fitness_decomposition'] = {'keys': keys, 'capture_income': income, 'cost_saving': saving, 'total_F': total}
out = HERE / 'figures'
out.mkdir(exist_ok=False)
for suffix in ('png', 'svg'):
    fig.savefig(out / f'capture_value_selection.{suffix}', dpi=160)
(out / 'plotted_statistics.json').write_text(json.dumps(plotted, indent=2) + '\n')
print(json.dumps({'status': 'complete', 'summary_sha256': plotted['summary_sha256'], 'figure': str(out)}))
