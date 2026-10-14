"""Plot completed, independently reconciled U results; no simulator imports."""
from pathlib import Path
import argparse
import json
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('study', type=Path)
    args = parser.parse_args()
    data = json.loads((args.study / 'summary.json').read_text())
    if data['status'] != 'complete':
        raise ValueError('Only a complete independently analyzed study may be plotted')
    roles = ['s53091_final_rank0', 's53092_final_rank0']
    labels = ['s5 descendant', 's7 descendant']
    colors = ['#1f77b4', '#c35b17']
    conditions = ['trained', 'width_swapped', 'frozen', 'frozen_lateral_off']
    names = ['Trained world\nwhole life', 'Glow widths swapped\nwhole life',
             'Tissue frozen\n544–1024', 'Frozen, lateral sends off\n544–1024']
    fig, axes = plt.subplots(1, 2, figsize=(12, 6), gridspec_kw={'width_ratios': [1.2, 1]})
    fig.suptitle('Ordinary evolution in the harmful-decoy world', fontsize=16, x=.05, ha='left')
    ax = axes[0]
    for i, role in enumerate(roles):
        estimates = [data['conditions'][condition][role]['vs_own_founder']['F'] for condition in conditions]
        y = np.arange(4) + (i - .5) * .22
        ax.errorbar([x['mean'] for x in estimates], y, xerr=[3*x['se'] for x in estimates],
                    fmt='o', color=colors[i], capsize=3, label=labels[i])
    ax.axvline(0, color='#888', lw=1)
    ax.set_yticks(range(4), names)
    ax.invert_yaxis()
    ax.set_xlabel('Descendant − own founder fitness (±3 SE)')
    ax.set_title('Fresh paired fitness effects', loc='left', fontsize=12)
    ax.legend(frameon=False, loc='best')
    ax.grid(axis='x', alpha=.2)
    ax = axes[1]
    components = [('capture_income', 'Capture income', '#3b8b75'),
                  ('poison_cost_saving', 'Harmful-click cost saving', '#7752a5'),
                  ('miss_cost_saving', 'Miss cost saving', '#dd9944'),
                  ('other_cost_saving', 'Other cost saving', '#969fa5'),
                  ('guard_charge_saving', 'Guard charge saving', '#444444'),
                  ('extinction_charge_saving', 'Extinction charge saving', '#b36083')]
    pos, neg = np.zeros(2), np.zeros(2)
    for key, label, color in components:
        values = np.array([data['conditions']['trained'][role]['fitness_contributions'][key]['mean'] for role in roles])
        if np.any(values != 0):
            ax.bar(range(2), values, bottom=np.where(values >= 0, pos, neg), width=.55, color=color, label=label)
        pos += np.maximum(values, 0)
        neg += np.minimum(values, 0)
    totals = [data['confirmation'][role]['trained_gain']['mean'] for role in roles]
    ax.scatter(range(2), totals, marker='D', color='black', s=35, label='Net fitness gain', zorder=3)
    ax.axhline(0, color='#888', lw=1)
    ax.set_xticks(range(2), labels)
    ax.set_ylabel('Fitness contribution')
    ax.set_title('What funds the trained-world change?', loc='left', fontsize=12)
    ax.legend(frameon=False, fontsize=8, loc='best')
    ax.grid(axis='y', alpha=.2)
    for ax in axes:
        ax.spines[['top', 'right']].set_visible(False)
    fig.text(.05, .025, '512 shared fresh seeds. Error bars are descriptive; frozen and whole-life windows differ.\n'
             'Width reversal changes signal geometry. Fitness and message dependence alone do not identify an algorithm.',
             fontsize=9, color='#444')
    fig.tight_layout(rect=[0, .09, 1, .94])
    for extension in ('png', 'svg'):
        fig.savefig(args.study / ('decoy_evolution.' + extension), dpi=150)
    plt.close(fig)


if __name__ == '__main__':
    main()
