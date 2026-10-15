"""Independent descriptive recount of all15 AN aggregate capture/click fractions."""
import hashlib
import json
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[3]
STUDY=ROOT/'outputs/autonomous_occlusion_acquisition_20261015'
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def read(path):return json.loads(path.read_text())
review=read(STUDY/'terminal_review/independent/independent_raw_review.json')
assert review['status']=='passed' and review['literal_vectors_checked']==2933
summary=read(STUDY/'analysis_result/summary.json'); index=read(STUDY/'row_index.json')
assert sha(STUDY/'analysis_result/summary.json')==review['canonical_summary_sha256']
roles=('AM_current_start','generation4','generation8')
worlds=('pool','persistent','blink80_5','blink80_20','turn100_blink80_20')
result={}; pins={}
for world in worlds:
    result[world]={}
    for i,role in enumerate(roles):
        name=f'raw/{world}/row_{i:02d}.npz';path=STUDY/name
        assert sha(path)==index[name]['sha256'];pins[name]=sha(path)
        with np.load(path,allow_pickle=False) as raw:
            captures,misses,clicks=(raw['ledger'][:,i].copy() for i in (35,36,37))
            assert str(raw['role'])==role and str(raw['world_name'])==world
        assert all(x.shape==(512,) and np.isfinite(x).all() and np.all(x>=0) and np.all(x==np.floor(x)) for x in (captures,misses,clicks))
        np.testing.assert_array_equal(captures+misses,clicks)
        totalcap,totalmiss,totalclick=(int(v.sum()) for v in (captures,misses,clicks))
        actual={'lives':512,'total_captures':totalcap,'total_misses':totalmiss,'total_clicks':totalclick,
                'aggregate_capture_fraction':totalcap/totalclick if totalclick else None,
                'mean_captures':float(captures.mean()),'mean_misses':float(misses.mean()),'mean_clicks':float(clicks.mean()),
                'clickless_lives':int(np.count_nonzero(clicks==0)), 'clickless_fraction':float(np.mean(clicks==0))}
        expected=summary['capture_accuracy'][world][role]
        assert actual==expected,(world,role,actual,expected)
        result[world][role]=actual
out={'status':'passed','rows_verified':15,'lives_verified':7680,'canonical_accuracy_exact':True,
     'canonical_summary_sha256':sha(STUDY/'analysis_result/summary.json'),
     'literal_review_sha256':sha(STUDY/'terminal_review/independent/independent_raw_review.json'),
     'script_sha256':sha(Path(__file__)),'raw_pins':pins,'accuracy':result,
     'limits':'Aggregate fraction weights clicks; descriptive only, no binomial SE. Zero-click rows use null.','new_simulations':0}
path=STUDY/'terminal_review/independent/accuracy_review.json'
with path.open('x') as stream:stream.write(json.dumps(out,indent=2)+'\n')
print(json.dumps({'status':'passed','rows':15,'receipt_sha256':sha(path)}))
