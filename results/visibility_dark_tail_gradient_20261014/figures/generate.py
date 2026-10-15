"""Plot both fixed AG contrasts with an exact summary pin and three-SE bars."""
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
names = ['H_D90_minus_P_D90', 'H_L92_minus_P_L92']
labels = ['D90 selected mutant', 'L92 selected mutant']
metrics = ['F', 'captures', 'low_light_captures', 'ordinary_cost']
titles = ['Fitness gain', 'Extra captures per life', 'Extra dark-phase captures', 'Ordinary cost saving in F']
colors = ['#167d8d', '#b15d2d']
y = np.arange(2)
plt.rcParams.update({'font.size': 11, 'svg.hashsalt': 'AG completed paired contrasts'})
fig, axes = plt.subplots(1, 4, figsize=(15, 4.2), sharey=True)
for ax, metric, title in zip(axes, metrics, titles):
    rows = [summary['contrasts'][name][metric] for name in names]
    ax.barh(y, [r['mean'] for r in rows], xerr=[3 * r['se'] for r in rows], color=colors,
            height=.48, capsize=4, error_kw={'linewidth': 1})
    ax.axvline(0, color='#333333', linewidth=.8)
    ax.set_title(title, loc='left', fontsize=11, fontweight='bold')
    ax.set_xlabel('Paired difference from parent')
    ax.grid(axis='x', alpha=.18)
    ax.set_axisbelow(True)
    ax.spines[['top', 'right']].set_visible(False)
axes[0].set_yticks(y, labels)
axes[0].invert_yaxis()
fig.suptitle('Retained mutations after target cues disappear', x=.025, ha='left',
             fontsize=15, fontweight='bold')
fig.text(.025, .865, 'AG · 512 fresh paired lives · five bright time units after each target placement · then no target cues',
         color='#444444')
fig.text(.025, .065, 'Error bars: three paired SE. Selection used separate 32-life screens; both fixed confirmations are shown.',
         fontsize=9, color='#444444')
fig.text(.025, .025, 'Two fixed mutation neighborhoods; dark-phase captures alone do not establish memory or a new algorithm.',
         fontsize=9, color='#444444')
fig.subplots_adjust(left=.15, right=.98, top=.76, bottom=.23, wspace=.36)
output = Path(__file__).resolve().parent
fig.savefig(output / 'capture_and_economy.png', dpi=150)
fig.savefig(output / 'capture_and_economy.svg', metadata={'Date': None})
plt.close(fig)
