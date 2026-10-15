"""Plot all registered within-world effects and world interactions; no new lives."""
from pathlib import Path
import json
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
STUDY=Path(__file__).resolve().parents[1]
summary=json.loads((STUDY/'analysis_result/summary.json').read_text())
assert summary['status']=='complete'
comparisons=[('flash','H','P','Flash: H − P (primary)'),('blink','H','P','Blink: H − P'),
             ('flash','B','P','Flash: B − P'),('blink','B','P','Blink: B − P'),
             ('flash','H','B','Flash: H − B'),('blink','H','B','Blink: H − B')]
metrics=[('Fitness change',lambda c:c['columns']['F']),
         ('Capture-income contribution',lambda c:c['fitness_pieces']['capture_income']),
         ('Ordinary cost saving',lambda c:c['total_cost_saving'])]
colors={'flash':'#ac5832','blink':'#396d9a'}
fig,axes=plt.subplots(2,3,figsize=(14,8.1),sharey=True,constrained_layout=True)
for row,p in enumerate(['D90','L92']):
 for col,(title,extract) in enumerate(metrics):
  ax=axes[row,col]
  for i,(world,a,b,label) in enumerate(comparisons):
   item=extract(summary['contrasts']['within'][world][f'{a}_{p}_minus_{b}_{p}'])
   ax.errorbar(item['mean'],5-i,xerr=item['se'],fmt='o' if world=='flash' else 'D',
               color=colors[world],capsize=3,markersize=5)
  ax.axvline(0,color='#777777',linewidth=.8);ax.grid(axis='x',alpha=.2)
  ax.set_yticks(range(5,-1,-1),[x[3] for x in comparisons]);ax.set_ylim(-.6,5.6)
  ax.set_title(f'{p}: {title}');ax.set_xlabel('F units; mean ± paired SE')
  for side in ['top','right']:ax.spines[side].set_visible(False)
fig.suptitle('Flash-selected mutants across two visibility worlds — 512 fresh paired lives',fontsize=15)
fig.supxlabel('H = flash selection; B = previous blink selection; P = original parent. Same complete candidate panels; no new mutations.',fontsize=10)
for suffix in ['png','svg']:fig.savefig(STUDY/'figures'/f'confirmation.{suffix}',dpi=170)
plt.close(fig)
fig,axes=plt.subplots(2,2,figsize=(11,5.5),sharey=True,constrained_layout=True)
for row,p in enumerate(['D90','L92']):
 for col,(metric,title) in enumerate([('F','Fitness interaction'),('F__capture_income','Capture-income interaction')]):
  ax=axes[row,col]
  for i,b in enumerate(['P','B']):
   item=summary['contrasts']['interactions'][f'H_{p}_minus_{b}_{p}'][metric]
   ax.errorbar(item['mean'],1-i,xerr=item['se'],fmt='o',color='#6e4c87',capsize=4)
  ax.axvline(0,color='#777777',linewidth=.8);ax.grid(axis='x',alpha=.2)
  ax.set_yticks([1,0],['H − P','H − B']);ax.set_ylim(-.5,1.5)
  ax.set_title(f'{p}: {title}');ax.set_xlabel('Flash minus blink; F units, mean ± paired SE')
  for side in ['top','right']:ax.spines[side].set_visible(False)
fig.suptitle('World interactions formed within each shared life seed',fontsize=15)
fig.supxlabel('A positive interaction alone does not show that H beats B in flash, or establish memory.',fontsize=10)
for suffix in ['png','svg']:fig.savefig(STUDY/'figures'/f'interactions.{suffix}',dpi=170)
plt.close(fig)
