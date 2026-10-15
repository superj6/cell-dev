"""AI source/input verification and recorded-addition replay; no fresh genetic draws or lives."""
from __future__ import annotations
import argparse
import ast
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys
os.environ.setdefault('ATEN_CPU_CAPABILITY','avx2')
sys.dont_write_bytecode=True
HERE=Path(__file__).resolve().parent
ANALYSIS=HERE/'analysis' if (HERE/'analysis/analyze.py').is_file() else HERE

def module(name,path):
    spec=importlib.util.spec_from_file_location(name,path)
    result=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--study',type=Path,required=True)
    args=parser.parse_args()
    study=args.study.resolve()
    A=module('AI_actual_input_reader',ANALYSIS/'analyze.py')
    protocol=A.verify_protocol(study)
    N=module('AI_actual_input_native',ANALYSIS/'native_audit.py')
    replay=N.initialization_audit(study,protocol,A.external)
    replay_path=HERE/'initialization_replay.json'
    if replay_path.exists():
        if replay_path.read_bytes()!=A.json_bytes(replay):raise ValueError('retained initialization replay differs')
    else:replay_path.write_bytes(A.json_bytes(replay))
    absent=['ready.json','attempt.json','budget.json','runs','confirmation','build-cache','logs']
    if any((study/name).exists() for name in absent) or list(study.rglob('*.so')):
        raise ValueError('prelaunch source/input review found runtime artifacts')
    summary,vectors=A.analyze(study)
    if summary['status']!='incomplete' or vectors or 'ready.json' not in summary.get('error',''):
        raise ValueError('prelaunch reader did not fail solely at missing release')
    original=ast.parse((ANALYSIS/'history/AI_analyze_unbound.py.txt').read_text())
    bound=ast.parse((ANALYSIS/'analyze.py').read_text())
    for tree in (original,bound):
        tree.body[0].value=ast.Constant('normalized docstring')
        for node in tree.body:
            if isinstance(node,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='PROTOCOL_SHA' for t in node.targets):
                node.value=ast.Constant(None)
    if ast.dump(original)!=ast.dump(bound):
        raise ValueError('bound reader changed beyond literal/docstring')
    forbidden=[name for name in sys.modules if name.startswith(('src.evolve','src.run','src.checkpoint','src.life.build','src.life.evaluate','src.life.reference'))]
    if forbidden:raise ValueError('engine/execution source imported: '+str(forbidden))
    receipt={'status':'passed_prepared_unreleased','protocol_sha256':sha(study/'protocol.json'),
             'reader_sha256':sha(ANALYSIS/'analyze.py'),'native_sha256':sha(ANALYSIS/'native_audit.py'),
             'local_pins':len(protocol['file_pins']),'production_pins':len(protocol['production_pins']),
             'recorded_initialization':replay,'initialization_replay_sha256':sha(HERE/'initialization_replay.json'),
             'world_abi':3,'world_values':len(protocol['world_packing']['values']),
             'historical_timing_rows':65,'configurations':2,'runs':protocol['runs'],
             'shared_initial_populations':1,'registered_native_unique':64,'confirmation_seeds':len(protocol['confirmation']['seeds']),
             'cost_projection':protocol['cost_projection'],'reader_only_literal_docstring_changed':True,
             'runtime_paths_absent':absent,'prelaunch_result':summary,'forbidden_modules':forbidden,
             'simulation_calls':0,'compilation_calls':0,'fresh_genetic_draws':0,
             'verification_source_sha256':sha(Path(__file__).resolve())}
    with (HERE/'actual_input_verification.json').open('xb') as stream:stream.write(A.json_bytes(receipt))
    print(json.dumps({'status':receipt['status'],'protocol_sha256':receipt['protocol_sha256'],
                      'receipt_sha256':sha(HERE/'actual_input_verification.json'),
                      'initialization_replay_sha256':receipt['initialization_replay_sha256'],
                      'local_pins':receipt['local_pins'],'production_pins':receipt['production_pins']},indent=2))

if __name__=='__main__':main()
