"""Plot the three fixed AI contrasts, with an exact summary pin and three-SE bars."""
from pathlib import Path
import argparse
import hashlib
import json

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--summary', type=Path, required=True)
parser.add_argument('--sha256', required=True)
args = parser.parse_args()
assert hashlib.sha256(args.summary.read_bytes()).hexdigest() == args.sha256
summary = json.loads(args.summary.read_text())
assert summary['status'] == 'complete'
rows = [summary['contrasts'][kind][label] for kind, label in
        [('primary', 'AI_reserve'), ('gain', 'AI_control'), ('gain', 'AI_reserve')]]
labels = ['Reserve − control', 'Control − start', 'Reserve − start']
metrics = ['captures', 'F', 'n_end', 'total_cost_saving']
titles = ['Extra captures per life', 'Fitness difference', 'Terminal cell difference', 'Ordinary cost saving in F']
colors = ['#167d8d', '#747a83', '#b15d2d']
y = np.arange(3)
plt.rcParams.update({'font.size': 11, 'svg.hashsalt': 'AI completed paired contrasts'})
fig, axes = plt.subplots(1, 4, figsize=(15, 4.8), sharey=True)
for ax, metric, title in zip(axes, metrics, titles):
    values = [r[metric] if metric == 'total_cost_saving' else r['columns'][metric] for r in rows]
    ax.barh(y, [r['mean'] for r in values], xerr=[3 * r['se'] for r in values], color=colors,
            height=.48, capsize=4, error_kw={'linewidth': 1})
    ax.axvline(0, color='#333333', linewidth=.8)
    ax.set_title(title, loc='left', fontsize=11, fontweight='bold')
    ax.set_xlabel('Paired difference')
    ax.grid(axis='x', alpha=.18)
    ax.set_axisbelow(True)
    ax.spines[['top', 'right']].set_visible(False)
axes[0].set_yticks(y, labels)
axes[0].invert_yaxis()
fig.suptitle('Repeating the offspring-reserve comparison', x=.025, ha='left',
             fontsize=15, fontweight='bold')
fig.text(.025, .865, 'AI · one matched four-generation search pair · fixed persistent-target world and prices',
         color='#444444')
fig.text(.025, .08, 'Error bars: three paired SE across 512 fresh lives. Both endpoints were fixed before confirmation.',
         fontsize=9, color='#444444')
fig.text(.025, .04, 'One chosen background and one search pair; uncertainty across evolutionary repeats remains unmeasured.',
         fontsize=9, color='#444444')
fig.subplots_adjust(left=.15, right=.98, top=.77, bottom=.23, wspace=.36)
output = Path(__file__).resolve().parent
fig.savefig(output / 'capture_and_economy.png', dpi=150)
fig.savefig(output / 'capture_and_economy.svg', metadata={'Date': None})
plt.close(fig)
