"""Pure independent check of the corrected persisted calibration interface."""
import ast
import hashlib
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
OUT=Path(__file__).resolve().parent
STUDY=ROOT/'outputs/autonomous_prediction_gradient_20261014'
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def functions(path,names,scope):
 tree=ast.parse(path.read_text());nodes=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in names]
 assert {n.name for n in nodes}==set(names)
 exec(compile(ast.Module(body=nodes,type_ignores=[]),str(path),'exec'),scope)
def main():
 scope={'PARENTS':('D90','L92'),'STUDY':OUT/'source_review_roundtrip','json':json,'Path':Path}
 scope['STUDY'].mkdir(exist_ok=True)
 functions(STUDY/'measure.py',['calibration_projection'],scope)
 functions(STUDY/'monitor.py',['initial_projection_values','check_initial_projection','read'],scope)
 historical={'D90':[.2]*65,'L92':[.15]*65}
 rows={'D90':{0:{'cpu_seconds':.4},1:{'cpu_seconds':.5}},'L92':{0:{'cpu_seconds':.2},1:{'cpu_seconds':.3}}}
 snapshot={f'screen/{p}':{f'calibration/row_{i:04d}.npz':rows[p][i] for i in (0,1)} for p in scope['PARENTS']}
 p={'historical_blink_cpu_per_life':historical};receipt={'row_snapshot':snapshot,'cpu_seconds':20}
 result=scope['calibration_projection'](rows,20,historical)
 path=scope['STUDY']/'calibration_projection.json';path.write_text(json.dumps(result,indent=2)+'\n')
 assert all(set(v)=={'0','1'} for v in result['calibration_cpu_per_life'].values())
 scope['check_initial_projection'](p,receipt)
 assert json.loads(path.read_text())==result
 expected=scope['initial_projection_values'](p,receipt)
 assert all(result[k]==v for k,v in expected.items())
 print(json.dumps({'status':'passed','check':'Actual JSON save/read passes independent monitor reconstruction with string row keys.','source_pins':{str((STUDY/n).relative_to(ROOT)):sha(STUDY/n) for n in ('measure.py','monitor.py')},'fixture_sha256':sha(path),'simulation_calls':0,'compiled_libraries':0},indent=2))
if __name__=='__main__':main()
