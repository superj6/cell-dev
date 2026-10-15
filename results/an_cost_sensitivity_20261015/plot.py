"""Plot completed-data repricing; no evolution or simulations."""
import json
from pathlib import Path

import matplotlib

matplotlib.use('Agg')
import matplotlib.pyplot as plt

HERE = Path(__file__).resolve().parent
s = json.loads((HERE / 'summary.json').read_text())
assert s['status'] == 'complete' and s['new_lives'] == 0
fig, axes = plt.subplots(1, 2, figsize=(11, 4.4), constrained_layout=True, sharey=True)
for ax, price, label, color in zip(axes, ['c_live', 'c_miss'],
                                  ['Cell maintenance price', 'Missed-click price'], ['#087d8b', '#be7436']):
    rows = s['separate_price_grids'][price]
    values = [r['contexts']['mixed_25_25_50']['paired_F']['generation8_minus_generation4'] for r in rows]
    ax.errorbar([r['multiplier'] for r in rows], [v['mean'] for v in values],
                yerr=[3 * v['se'] for v in values], color=color, fmt='o-', capsize=4)
    ax.axhline(0, color='#555', lw=1)
    ax.axvline(1, color='#aaa', ls=':', label='Original price')
    ax.set(title=label, xlabel='Multiplier of original price', ylabel='Generation 8 − 4 mixed F, mean ± 3 SE')
    ax.spines[['top', 'right']].set_visible(False)
    ax.grid(axis='y', alpha=.15)
    ax.legend(frameon=False, fontsize=9)
fig.suptitle('AN: repricing the same trajectories changes the economy incentive', fontsize=13)
fig.supxlabel('Fixed 25% POOL / 25% persistent / 50% longer gaps; all captures unchanged. No altered evolution was run.', fontsize=10)
for ext in ['png', 'svg']:
    fig.savefig(HERE / f'price_sensitivity.{ext}', dpi=160)
