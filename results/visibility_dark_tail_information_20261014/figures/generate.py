"""Plot the completed, frozen AD paired contrasts; no simulation."""
from pathlib import Path
import hashlib
import json

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

HERE = Path(__file__).resolve().parent
SOURCE = HERE.parent / 'analysis_result/summary.json'
assert hashlib.sha256(SOURCE.read_bytes()).hexdigest() == '7f8bd355cc6cdc6417c351a5be381f226e712a37865673cc102fad1a63ae52ea'
summary = json.loads(SOURCE.read_text())
assert summary['status'] == 'complete'
world = summary['worlds']['flash5_dark']
names = ['I_minus_R0', 'I_minus_R1', 'I_minus_A', 'I_minus_B'] + [f'D{i}_minus_R1' for i in range(8)]
labels = ['Full − reference R0', 'Full − reference R1', 'Full − model ablation A',
          'Full − action ablation B'] + [f'Control D{i} − reference R1' for i in range(8)]
colors = ['#167d8d'] * 2 + ['#a75b19'] * 2 + ['#65728a'] * 8
y = np.arange(len(names))
plt.rcParams.update({'font.size': 10, 'svg.hashsalt': 'AD completed paired contrasts'})
fig, axes = plt.subplots(1, 2, figsize=(12, 7), sharey=True)
for ax, metric, title in zip(axes, ['F', 'captures'], ['Fitness difference', 'Extra captures per life']):
    rows = [world['contrasts'][name]['columns'][metric] for name in names]
    ax.barh(y, [row['mean'] for row in rows], xerr=[row['se'] for row in rows], color=colors,
            height=.62, capsize=3, error_kw={'linewidth': 1})
    ax.axvline(0, color='#333333', linewidth=.8)
    ax.axhline(3.5, color='#cccccc', linewidth=.7)
    ax.set_title(title, loc='left', fontweight='bold')
    ax.set_xlabel('Mean paired difference ± one SE')
    ax.grid(axis='x', alpha=.18)
    ax.set_axisbelow(True)
    ax.spines[['top', 'right']].set_visible(False)
axes[0].set_yticks(y, labels)
axes[0].invert_yaxis()
fig.suptitle('Information still pays after the flash becomes fully dark', x=.03, ha='left',
             fontsize=15, fontweight='bold')
fig.text(.03, .915, 'AD · 512 paired lives per instrument · T = 1,024 · target cue multiplier after flash = 0',
         color='#444444')
fig.text(.03, .045, 'External instruments with free central computation; no evolved-memory claim. R0/R1 were retained, not retuned for darkness.',
         fontsize=9, color='#444444')
fig.text(.03, .020, 'R1 is the better whole-mean reference. Both ablations are broad. All eight do-less controls are shown.',
         fontsize=9, color='#444444')
fig.subplots_adjust(left=.245, right=.98, top=.85, bottom=.14, wspace=.2)
fig.savefig(HERE / 'information_payoff.png', dpi=150)
fig.savefig(HERE / 'information_payoff.svg', metadata={'Date': None})
plt.close(fig)
