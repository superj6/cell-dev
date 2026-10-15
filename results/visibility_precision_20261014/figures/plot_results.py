"""Plot the registered fitness decomposition; no simulation or data selection."""
from pathlib import Path
import json

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

STUDY = Path(__file__).resolve().parents[1]
summary = json.loads((STUDY / 'analysis_result/summary.json').read_text())
assert summary['status'] == 'complete'
comparisons = [('gain', 'depth_', 'Depth endpoint − start'),
               ('gain', 'precision_', 'Precision endpoint − start'),
               ('primary', 'precision_', 'Precision − depth')]
metrics = [('Fitness change', lambda c: c['columns']['F']),
           ('Capture-income contribution', lambda c: c['fitness_pieces']['capture_income']),
           ('Ordinary cost saving', lambda c: c['total_cost_saving'])]
colors = ['#426a9e', '#b65b30', '#674a87']
fig, axes = plt.subplots(2, 3, figsize=(13, 6.1), sharey=True, constrained_layout=True)
for row, background in enumerate(['D90', 'L92']):
    for col, (title, extract) in enumerate(metrics):
        ax = axes[row, col]
        for i, (family, prefix, label) in enumerate(comparisons):
            item = extract(summary['contrasts'][family][prefix + background])
            ax.errorbar(item['mean'], 2-i, xerr=item['se'], fmt='o', color=colors[i],
                        capsize=4, markersize=6)
        ax.axvline(0, color='#777777', linewidth=.8)
        ax.grid(axis='x', alpha=.2)
        ax.set_yticks([2, 1, 0], [x[2] for x in comparisons])
        ax.set_ylim(-.6, 2.6)
        ax.set_xlabel('F units; mean ± paired SE')
        ax.set_title(f'{background}: {title}')
        for side in ['top', 'right']:
            ax.spines[side].set_visible(False)
fig.suptitle('Selection precision versus depth — 512 fresh paired lives', fontsize=15)
fig.supxlabel('Four generations at 3+4 lives versus one at 12+16. Equal selection calls, not equal CPU or isolated precision.',
              fontsize=10)
for suffix in ['png', 'svg']:
    fig.savefig(STUDY / 'figures' / f'confirmation.{suffix}', dpi=170)
plt.close(fig)
