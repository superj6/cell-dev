"""Authorized AE input/replay verification only; no compiled library or life calls."""
from pathlib import Path
import ast
import hashlib
import importlib.util
import json
import sys

sys.dont_write_bytecode=True
HERE=Path(__file__).resolve().parent
ROOT=next(p for p in HERE.parents if (p/'src/life/spec.py').is_file())
STUDY=ROOT/'outputs/autonomous_prediction_gradient_20261014'

def module(name,path):
    spec=importlib.util.spec_from_file_location(name,path)
    value=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value

def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()

reader=module('AE_bound_reader',HERE/'analyze.py')
p,panels=reader.verify_protocol(STUDY)
replay=module('AE_bound_replay',HERE/'panel_replay.py').audit(STUDY,p,reader.external)
assert sum(x['rows'] for x in replay['backgrounds'].values())==130
assert sum(x['recorded_point_mutations'] for x in replay['backgrounds'].values())==256
for name in ('ready.json','attempt.json','budget.json','measurement','logs','build-cache'):
    assert not (STUDY/name).exists(),name
forbidden={'src.life.build','src.life.evaluate','src.checkpoint','src.run','src.evolve'}
assert not (forbidden & set(sys.modules)),forbidden & set(sys.modules)
# Check the entire reader AST after normalizing its single allowed literal/docstring changes.
def normalized(path):
    tree=ast.parse(path.read_text())
    tree.body.pop(0)
    for node in tree.body:
        if isinstance(node,ast.Assign) and isinstance(node.targets[0],ast.Name) and node.targets[0].id=='PROTOCOL_SHA':
            node.value=ast.Constant(value=None)
    return ast.dump(tree,include_attributes=False)
assert normalized(HERE/'analyze.py')==normalized(HERE/'history/analyze.py.unbound.txt')
# The full entrypoint must refuse results while unreleased; no prepared scope is silently run.
summary,vectors=reader.analyze(STUDY)
assert summary['status']=='incomplete' and summary['scientific_outcomes_emitted'] is False and not vectors
result={'status':'passed_prepared_unreleased','protocol_sha256':reader.PROTOCOL_SHA,
        'local_pins':len(p['file_pins']),'production_pins':len(p['production_pins']),
        'panel_rows':sum(len(x) for x in panels.values()),'historical_timing_rows':130,
        'world_keys':len(p['world_packing']['keys']),'abi':p['abi'],'derived_configs':2,
        'configuration_changes':p['configuration_changes'],'all_reader_function_AST_unchanged':True,
        'unreleased_entrypoint':summary,'retained_input_replay':replay,
        'activity':{'simulation_calls':0,'compilation_calls':0,'random_draws':0},
        'source_pins':{name:sha(HERE/name) for name in ('analyze.py','offline_accounting.py','panel_replay.py','helpers/genetics.py','check_bound_inputs.py')}}
(HERE/'actual_bound_input_review.json').write_text(json.dumps(result,indent=2)+'\n')
(HERE/'panel_replay.json').write_text(json.dumps(replay,indent=2)+'\n')
print(json.dumps({k:v for k,v in result.items() if k!='retained_input_replay'},indent=2))
