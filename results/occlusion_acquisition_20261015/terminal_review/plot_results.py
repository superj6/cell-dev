"""Plot complete AN acquisition/retention evidence without simulations or selection."""
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
assert s['status'] == 'complete'
worlds = ['pool','persistent','blink80_5','blink80_20','turn100_blink80_20']
labels = ['POOL','Persistent','Brief gaps','Longer gaps','Turns + longer gaps']
roles = ['AM_current_start','generation4','generation8']
names = ['AM start','Generation 4','Generation 8']
colors = ['#7b818a','#d47b3c','#087d8b']
absolute, contrasts = s['absolute'], s['contrasts']
fig, axes = plt.subplots(2,2,figsize=(14,8),constrained_layout=True)
x = np.arange(len(worlds))
plotted = {'summary_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'absolute':{},'paired':{}}
for i,(role,name,color) in enumerate(zip(roles,names,colors)):
    vals = [absolute[w][role]['captures'] for w in worlds]
    axes[0,0].bar(x+(i-1)*.25,[v['mean'] for v in vals],.24,
                  yerr=[v['se'] for v in vals],color=color,label=name,capsize=3)
    plotted['absolute'][role] = vals
for i,(role,name,color) in enumerate(zip(roles[1:],names[1:],colors[1:])):
    vals = [contrasts[f'within__{w}__{role}_minus_{roles[0]}']['captures'] for w in worlds]
    axes[0,1].errorbar(x+(i-.5)*.14,[v['mean'] for v in vals],yerr=[3*v['se'] for v in vals],
                       fmt='o',color=color,label=name,capsize=4)
    dark = [contrasts[f'within__{w}__{role}_minus_{roles[0]}']['low_light_captures'] for w in worlds[2:]]
    axes[1,0].errorbar(np.arange(3)+(i-.5)*.14,[v['mean'] for v in dark],
                       yerr=[3*v['se'] for v in dark],fmt='o',color=color,label=name,capsize=4)
    plotted['paired'][role] = {'captures':vals,'dark_captures':dark}
for ax in axes.flat:
    ax.spines[['top','right']].set_visible(False)
    ax.grid(axis='y',alpha=.15)
for ax in axes[0]:
    ax.set_xticks(x,labels,fontsize=9)
for ax in (axes[0,1],axes[1,0],axes[1,1]):
    ax.axhline(0,color='#444',lw=1)
axes[0,0].set(title='Acquisition and retained tasks',ylabel='Mean captures per life ± SE')
axes[0,0].legend(frameon=False,fontsize=9)
axes[0,1].set(title='Capture change from AM start',ylabel='Paired change ± 3 SE')
axes[1,0].set_xticks(np.arange(3),labels[2:],fontsize=9)
axes[1,0].set(title='Captures while the cue is dark',ylabel='Paired change from start ± 3 SE')
axes[1,0].legend(frameon=False,fontsize=9)
keys = ['pool','persistent','blink80_20']
income,saving,total=[],[],[]
for w in keys:
    metrics = contrasts[f'within__{w}__generation8_minus_AM_current_start']
    income.append(metrics['capture_income']['mean'])
    saving.append(sum(metrics[k]['mean'] for k in ('ordinary_cost','guard_cost','extinction_cost')))
    total.append(metrics['F'])
ax=axes[1,1];pos=np.arange(3)
ax.bar(pos-.14,income,.28,color='#087d8b',label='Capture income')
ax.bar(pos+.14,saving,.28,color='#bd9a5b',label='Cost saving, including penalties')
ax.errorbar(pos,[v['mean'] for v in total],yerr=[3*v['se'] for v in total],
             fmt='o',color='#222',capsize=4,label='Total F ± 3 SE')
ax.set_xticks(pos,['POOL','Persistent','Longer gaps'],fontsize=9)
ax.set(title='Final fitness change on the three selected tasks',ylabel='Paired F change from AM start')
ax.legend(frameon=False,fontsize=8)
fig.suptitle('AN: can the same lineage acquire longer-gap performance?',fontsize=15)
plotted['fitness_decomposition']={'worlds':keys,'capture_income':income,'cost_saving':saving,'total_F':total}
out=HERE/'figures';out.mkdir(exist_ok=False)
for suffix in ('png','svg'):
    fig.savefig(out/f'occlusion_acquisition.{suffix}',dpi=160)
(out/'plotted_statistics.json').write_text(json.dumps(plotted,indent=2)+'\n')
print(json.dumps({'status':'complete','summary_sha256':plotted['summary_sha256']}))
