"""AI source-only adaptation checks; no engine imports, genetic draws or file fixtures."""
import ast
import hashlib
import json
import math
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
AUDIT = HERE / 'release_review'
if not (AUDIT / 'producer_source_origins.json').is_file():
    AUDIT = ROOT / 'outputs/audit_exploratory_reserve_replication_20261014'
HISTORY = AUDIT / 'source_history/AH'
ORIGINS = json.loads((AUDIT / 'producer_source_origins.json').read_text())
REPLACEMENTS = [
    ('AH source-only draft', 'AI source-only replication draft'),
    ('AH three-role', 'AI three-role'), ('AH matched', 'AI matched'),
    ('AH_control', 'AI_control'), ('AH_reserve', 'AI_reserve'),
    ('AH fresh-offspring exploratory reserve', 'AI fresh-offspring exploratory reserve replication'),
    ('AG_terminal', 'AH_terminal'),
    ('outputs/autonomous_visibility_dark_tail_gradient_20261014/budget.json',
     'outputs/autonomous_exploratory_reserve_20261014/budget.json'),
    ('AG clean terminal', 'AH clean terminal'), ('AG must be cleanly', 'AH must be cleanly'),
    ('clean AG terminal', 'clean AH terminal'),
]


def normalized(path, undo=False):
    tree = ast.parse(path.read_text())
    if undo:
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                for old, new in REPLACEMENTS:
                    node.value = node.value.replace(new, old)
    return ast.dump(tree)


def test_entire_producer_AST_only_declared_metadata():
    for name in ('prepare.py', 'measure.py', 'run_budgeted.py'):
        assert normalized(HERE / name, True) == normalized(HISTORY / name)


def test_policy_search_and_scoring_helpers_are_exact_AH():
    for name in ('reserve_adapter.py', 'search.py', 'scoring.py', 'common.py', 'numerical.py',
                 'world_contract.py', 'test_source.py'):
        assert (HERE / name).read_bytes() == (HISTORY / name).read_bytes()
        assert hashlib.sha256((HERE / name).read_bytes()).hexdigest() == ORIGINS['source_pins'][name]
    assert 'cell-dev:AH:reserve:v1' in (HERE / 'reserve_adapter.py').read_text()


def test_role_study_and_prior_dependency_contract():
    for name in ('prepare.py', 'measure.py', 'run_budgeted.py'):
        tree = ast.parse((HERE / name).read_text())
        assignment = next(n for n in tree.body if isinstance(n, ast.Assign)
                          and any(isinstance(t, ast.Name) and t.id == 'LABELS' for t in n.targets))
        assert list(ast.literal_eval(assignment.value)) == ['AE_L92', 'AI_control', 'AI_reserve']
    for name in ('prepare.py', 'run_budgeted.py'):
        assert "'study': 'AI fresh-offspring exploratory reserve replication'" in (HERE / name).read_text()
    source = (HERE / 'prepare.py').read_text()
    assert "reg['AH_terminal']['file_pins']" in source
    assert 'outputs/autonomous_exploratory_reserve_20261014/budget.json' in source
    assert 'AG_terminal' not in source


def test_cost_formula_unchanged_and_bounded():
    tree = ast.parse((HERE / 'prepare.py').read_text())
    node = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'cost_projection')
    namespace = {'math': math}
    exec(compile(ast.Module(body=[node], type_ignores=[]), 'pure_cost_only', 'exec'), namespace)
    result = namespace['cost_projection']([.2] * 65)
    assert result['startup_search_projection'] == 180 + 1.5 * 8268 * .2
    assert result['confirmation_projection'] == 180 + 1.5 * 512 * 5 * .2
    assert result['feasible'] is True
    assert namespace['cost_projection']([1.] * 65)['feasible'] is False


def test_root_helpers_use_same_declared_contract():
    # Parse only: these scripts contain intentionally active root-only actions.
    paths = [AUDIT / n for n in ('register_study.py', 'release_study.py', 'clear_terminal.py')]
    for path in paths:
        ast.parse(path.read_text())
        assert 'autonomous_exploratory_reserve_replication_20261014' in path.read_text()
    register = paths[0].read_text()
    assert "'study': 'AI paired exploratory reserve replication'" in register
    assert "'AH_terminal':" in register
    assert "head == accepted['prior_published_milestone']" in register
    assert 'one_independent_replication_four_generation_pair_two_fresh_reserves' in register
