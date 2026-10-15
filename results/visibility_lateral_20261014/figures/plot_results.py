"""Plot all registered lateral capture-income comparisons; no simulation."""
from pathlib import Path
import json

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

STUDY = Path(__file__).resolve().parents[1]
summary = json.loads((STUDY / 'analysis_result/summary.json').read_text())
assert summary['status'] == 'complete'
contrasts = summary['contrasts']
colors = ['#426a9e', '#b65b30', '#674a87']
fig, axes = plt.subplots(2, 2, figsize=(12, 7.4), sharex='row', constrained_layout=True)
for col, background in enumerate(['D90', 'L92']):
    own = [('own_lateral__' + background, 'Original'),
           ('own_lateral__Y_' + background, 'Y mutant'),
           ('own_lateral__Z_' + background, 'Z endpoint')]
    changes = [('start__Y_' + background + '__added_lateral', 'Y mutant − original'),
               ('primary__Z_' + background + '__added_lateral', 'Z endpoint − Y mutant'),
               ('cumulative__Z_' + background + '__added_lateral', 'Z endpoint − original')]
    for row, items in enumerate([own, changes]):
        ax = axes[row, col]
        for i, (key, label) in enumerate(items):
            item = contrasts[key]['capture_income']
            ax.errorbar(item['mean'], 2-i, xerr=item['se'], fmt='o', color=colors[i],
                        capsize=4, markersize=6)
        ax.axvline(0, color='#777777', linewidth=.8)
        ax.grid(axis='x', alpha=.2)
        ax.set_yticks([2, 1, 0], [label for _, label in items])
        ax.set_ylim(-.6, 2.6)
        title = 'capture income from lateral sends' if row == 0 else 'change in that lateral contribution'
        ax.set_title(background + ': ' + title, fontsize=11)
        ax.set_xlabel('F units; mean ± paired SE')
        for side in ['top', 'right']:
            ax.spines[side].set_visible(False)
fig.suptitle('Lateral communication in frozen tissue — 128 paired lives', fontsize=15)
fig.supxlabel('Window 544–1024. Freeze also clamps regulation and weights; different genomes retain different bodies.\n'
              'These effects are conditional on freezing and do not establish memory or a new algorithm.', fontsize=10)
for suffix in ['png', 'svg']:
    fig.savefig(STUDY / 'figures' / f'lateral_effects.{suffix}', dpi=170)
plt.close(fig)
