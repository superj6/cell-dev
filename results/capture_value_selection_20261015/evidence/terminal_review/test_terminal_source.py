"""Three pure AM terminal/schema deltas; no input, engine or runtime reads."""
import ast
import importlib.util
from pathlib import Path

import numpy as np

ROOT = next(p for p in Path(__file__).resolve().parents if (p / 'src/life/spec.py').is_file())
STUDY = ROOT / 'outputs/autonomous_capture_value_selection_20261015'
HERE = Path(__file__).resolve().parent


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


READER = load('AM_reader_terminal_schema', STUDY / 'analyze.py')
RAW = load('AM_literal_terminal_schema', HERE / 'verify_terminal_raw.py')


def funcs(path):
    return {n.name: n for n in ast.parse(path.read_text()).body if isinstance(n, ast.FunctionDef)}


def test_literal_arithmetic_exact_AL_except_vector_length():
    old = funcs(ROOT / 'outputs/audit_retention_selection_20261015/terminal_review/verify_terminal_raw.py')
    new = funcs(HERE / 'verify_terminal_raw.py')

    class SizeOnly(ast.NodeTransformer):
        def visit_Constant(self, node):
            if type(node.value) is int and node.value == 256:
                return ast.copy_location(ast.Constant(512), node)
            return node
    assert ast.dump(SizeOnly().visit(old['literal_row'])) == ast.dump(new['literal_row'])
    for name in ('read','sha','stat'):
        assert ast.dump(old[name]) == ast.dump(new[name])
    assert RAW.PROTOCOL_SHA is None
    # Terminal pin/clearance checks precede even canonical output reads.
    body = new['main']
    recount = next(n.lineno for n in ast.walk(body) if isinstance(n, ast.Call)
                   and isinstance(n.func, ast.Name) and n.func.id == 'recount')
    gates = [n.lineno for n in ast.walk(body) if isinstance(n, ast.Raise)]
    assert min(gates) < recount


def test_all_4064_literal_vectors_match_reader_formula_independently():
    names = (*READER.COLS, 'low_light_captures', 'bright_captures', 'capture_income',
             'ordinary_cost', 'guard_cost', 'extinction_cost',
             *['cost__'+n for n in ('living','spiking','twitching','messages','division','secretion',
                                   'missed_clicks','receptors','decoy_clicks')])
    assert len(names) == 75
    data = {world: {role: {metric: np.arange(512, dtype=float) * (1+i+j) + k*(i-j)
                          for k, metric in enumerate(names)}
                    for j, role in enumerate(READER.ROLES)} for i, world in enumerate(READER.WORLDS)}
    literal = RAW.all_vectors(data)
    _, actual = READER.contrasts(data)
    _, margins = READER.retention_diagnostics(data)
    actual.update(margins)
    assert len(actual) == len(literal) == 4064 and set(actual) == set(literal)
    assert all(np.array_equal(actual[k], literal[k]) for k in literal)


def test_actual_prepare_literal_contract_matches_reader():
    tree = ast.parse((STUDY/'prepare.py').read_text())
    prepare = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'prepare')
    value = next(n.value for n in ast.walk(prepare) if isinstance(n, ast.Assign)
                 and any(isinstance(t, ast.Name) and t.id == 'protocol' for t in n.targets))
    fields = {key.value: v for key, v in zip(value.keys, value.values)}
    namespace = {'ROLES':list(READER.ROLES), 'ARMS':list(READER.ARMS)}
    def evaluate(key):
        return eval(compile(ast.Expression(fields[key]), '<pure protocol field>', 'eval'), {'__builtins__':{}, **namespace})
    for key, expected in {'roles':list(READER.ROLES), 'runs':list(READER.ARMS),
                          'research_lives':28748, 'startup_lives':8, 'total_calls':28756,
                          'confirmation_lives':8192, 'confirmation_startup_lives':4,
                          'extinct_charge':True, 'retention_margin_fraction':.1}.items():
        assert evaluate(key) == expected
    assert evaluate('search') == {'arms':list(READER.ARMS), 'generations':4, 'research_lives_per_arm':10278,
                                  'startup_lives_per_arm':2, 'initial_lives':8,'recheck_lives':8,'parents':32,'offspring':224}
    assert evaluate('budget') == {'cpu_seconds':10800,'wall_seconds':5400,'search_cpu_seconds':7200,
                                 'confirmation_cpu_seconds':3600,'threads':2,'workers':1,'cleanup_margin_seconds':10,
                                 'rss_bytes':4*1024**3,'minimum_available_bytes':4*1024**3,'address_space_bytes':8*1024**3}
    assert evaluate('primary') == [{'world':w,'new':READER.ROLES[3],'old':READER.ROLES[2],'metric':'captures'}
                                   for w in ('pool','persistent')]
    for key, role, path in (('reference','AL_mixture_start','inputs/AL_mixture_start.json'),
                            ('ancestral_reference','AI_control_start','inputs/AI_control_start.json')):
        record = {k.value:v for k,v in zip(fields[key].keys, fields[key].values)}
        assert eval(compile(ast.Expression(record['role']), '<role>', 'eval'), {'__builtins__':{}, **namespace}) == role
        assert ast.literal_eval(record['path']) == path
