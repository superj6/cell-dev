"""Reducer runtime check using saved engineering rows and synthetic guards only.

Repeated rows exercise array shapes, not independent observations. No simulator,
build or random draw is invoked. No resulting payoff estimate is published.
"""
from pathlib import Path
import sys,json,hashlib
import numpy as np

HERE=Path(__file__).resolve().parent
STUDY=HERE.parent
sys.path.insert(0,str(STUDY/'prelaunch'))
import analyze
from common import ROLES

def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()

def main():
    protocol=json.loads((STUDY/'prelaunch/protocol.json').read_text())
    protocol['confirmation_seeds']=[42000000]*512
    index=[]
    analyze.STUDY=STUDY/'policy_engineering'
    for role in ROLES:
        cid={'I':10,'E':11,'P':12}.get(role,10)
        path=analyze.STUDY/f'42000000_{cid}.npz'
        digest=sha(path)
        for _ in range(512):
            index.append(dict(stage='confirmation',seed=42000000,role=role,path=path.name,sha256=digest))
    result=analyze.analyze(protocol,index)
    assert result['status']=='complete' and result['paired_life_clusters']==512
    assert set(result['roles'])==set(ROLES)
    with np.load(analyze.STUDY/'42000000_10.npz',allow_pickle=False) as row:
        ledger=row['ledger'][0];L=analyze.h.V.L
        expected=50.*(ledger[L['wrong_choices_narrow']]+ledger[L['wrong_choices_broad']])
    assert result['roles']['I']['physical_cost_component_means']['wrong_choices']==expected
    json.dumps(result,allow_nan=False)
    # Missing first opportunity/calibration labels remain explicit, including an all-missing sample.
    synthetic=np.zeros((1,70));synthetic[0,L['status']]=2.;synthetic[0,L['F']]=-1.
    target=HERE/'synthetic_guard.npz'
    np.savez(target,ledger=synthetic,diag=np.zeros((1,16)))
    analyze.STUDY=HERE
    for row in index:row.update(path=target.name,sha256=sha(target))
    result=analyze.analyze(protocol,index)
    assert result['sample_calibration']['n']==0 and result['sample_calibration']['missing']==512
    assert result['sample_calibration']['brier'] is None
    json.dumps(result,allow_nan=False)
    print('PASS saved-row cost reducer, all roles, paired array shapes, class readouts, missing guard labels, finite JSON')
    print('Zero new simulator calls, builds or random draws. Repeated/synthetic rows are not scientific evidence.')

if __name__=='__main__':main()
