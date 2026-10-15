"""Plot complete AF contrasts with exact summary identity and descriptive three-SE bars."""
from pathlib import Path
import argparse
import hashlib
import json
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--summary',type=Path,required=True)
parser.add_argument('--sha256',required=True)
args=parser.parse_args()
assert hashlib.sha256(args.summary.read_bytes()).hexdigest()==args.sha256
summary=json.loads(args.summary.read_text())
assert summary['status']=='complete'
names=['AF_D90','AF_L92']
labels=['D90 continuation','L92 continuation']
rows=[summary['contrasts']['primary'][name] for name in names]
series=[[r['columns']['F'] for r in rows],[r['columns']['captures'] for r in rows],
        [r['total_cost_saving'] for r in rows]]
titles=['Fitness gain','Extra captures per life','Ordinary cost saving in F']
colors=['#167d8d','#b15d2d']
y=np.arange(2)
plt.rcParams.update({'font.size':11,'svg.hashsalt':'AF completed paired contrasts'})
fig,axes=plt.subplots(1,3,figsize=(12,4.2),sharey=True)
for ax,values,title in zip(axes,series,titles):
 ax.barh(y,[v['mean'] for v in values],xerr=[3*v['se'] for v in values],color=colors,
         height=.48,capsize=4,error_kw={'linewidth':1})
 ax.axvline(0,color='#333333',linewidth=.8)
 ax.set_title(title,loc='left',fontsize=12,fontweight='bold')
 ax.set_xlabel('Paired difference from own start')
 ax.grid(axis='x',alpha=.18);ax.set_axisbelow(True)
 ax.spines[['top','right']].set_visible(False)
axes[0].set_yticks(y,labels);axes[0].invert_yaxis()
fig.suptitle('Four generations in a persistent-target world',x=.025,ha='left',fontsize=15,fontweight='bold')
fig.text(.025,.865,'AF · two fixed starts · 512 fresh paired lives · unchanged prices and local rules',color='#444444')
fig.text(.025,.065,'Error bars: three paired SE, matching the descriptive criterion. All fixed endpoint/start contrasts are shown.',fontsize=9,color='#444444')
fig.text(.025,.025,'These continuations do not estimate search repeatability or establish prediction, memory or a new algorithm.',fontsize=9,color='#444444')
fig.subplots_adjust(left=.18,right=.98,top=.76,bottom=.23,wspace=.34)
out=Path(__file__).resolve().parent
fig.savefig(out/'capture_and_economy.png',dpi=150)
fig.savefig(out/'capture_and_economy.svg',metadata={'Date':None})
plt.close(fig)
