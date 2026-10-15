"""Focused AI metadata/role checks; reuse AH math and no file-based science fixtures."""

import ast
import hashlib
import importlib.util
import json
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("AI_reader_tests", HERE / "analyze.py")
M = importlib.util.module_from_spec(spec)
spec.loader.exec_module(M)
ORIGINS_PATH = HERE / "reader_source_origins.json"
if not ORIGINS_PATH.is_file():
    ORIGINS_PATH = HERE.parent / "reader_source_origins.json"
ORIGINS = json.loads(ORIGINS_PATH.read_text())


def normalized(source, replacements):
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            for old, new in replacements:
                if not old.startswith("PROTOCOL_SHA"):
                    node.value = node.value.replace(new, old)
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(
            isinstance(t, ast.Name) and t.id == "PROTOCOL_SHA" for t in node.targets
        ):
            node.value = ast.Constant(None)
    return ast.dump(tree)


def test_entire_reader_AST_changes_only_declared_metadata():
    original = (HERE / "history/AH_analyze.py.txt").read_text()
    current = (HERE / "analyze.py").read_text()
    changes = ORIGINS["files"]["analyze.py"]["allowed_replacements"]
    assert normalized(original, []) == normalized(current, changes)


def test_scientific_helpers_and_policy_byte_exact():
    for name in ("native_audit.py", "selection.py", "offline_accounting.py", "helpers/genetics.py"):
        assert M.sha(HERE / name) == ORIGINS["files"][name]["sha256"]
    assert M.POLICY["domain"] == "cell-dev:AH:reserve:v1"
    assert (
        hashlib.sha256(M.canonical(M.POLICY).encode()).hexdigest()
        == "bc2cbccffe93a95a2a885bbad570020374801f27f592ca355a6601a7d89b669d"
    )
    assert M.LABELS == ["AE_L92", "AI_control", "AI_reserve"]
    assert M.PAIRS == {"primary": [[2, 1]], "gain": [[1, 0], [2, 0]]}


def test_unbound_reader_refuses_outcomes(monkeypatch):
    monkeypatch.setattr(M, "PROTOCOL_SHA", None)
    summary, vectors = M.analyze(Path("/nonexistent_AI_source_only_fixture"))
    assert summary["status"] == "incomplete" and summary["scientific_outcomes_emitted"] is False
    assert not vectors and "source-only AI" in summary["error"]


def test_new_study_and_operational_dependency():
    source = (HERE / "analyze.py").read_text()
    assert '"study": "AI fresh-offspring exploratory reserve replication"' in source
    assert 'reg["AH_terminal"]["file_pins"]' in source
    assert "outputs/autonomous_exploratory_reserve_20261014/budget.json" in source
    assert "AG_terminal" not in source
    assert '"contrast": "AI_reserve_minus_AI_control"' in source
    assert 'result["primary"]["AI_reserve"]["columns"]["captures"]' in source


def test_three_in_memory_rows_have_exact219_named_vectors():
    # Minimal full-life rows exercise the unchanged raw accountant without any
    # engine, genotype table, file fixture or reserved research seed.
    n = 512
    world = {
        "t0": 0,
        "t_open": 0,
        "T": 1024,
        "world_kind": 1,
        "b2_amp": 0,
        "b2_value": 0,
        "R_cap": 500,
        "n_max": 128,
        "c_live": 0.001,
        "c_spike": 0.02,
        "c_tw": 0.03,
        "c_msg": 0.04,
        "c_div": 0.05,
        "c_sec": 0.06,
        "c_miss": 0.07,
        "c_rec": 0.08,
    }
    rows = []
    for i in range(3):
        row = {key: np.zeros(n, dtype=np.float64) for key in M.A.COLS}
        for key, value in {
            "n_end": 1,
            "n_peak": 1,
            "n_S_end": 1,
            "live_time": 1024,
            "live_S": 1024,
            "t_end": 1024,
            "t_ext": -1,
            "window": 1024,
            "spikes": 2,
        }.items():
            row[key][:] = value
        row["captures"][:] = 2 + i + np.arange(n) % 3
        row["clicks"][:] = row["captures"]
        row["income"][:] = 500 * row["captures"]
        row["cost"][:] = M.A.physical_costs(row, world)[0]
        row["net"][:] = row["income"] - row["cost"]
        row["F_kernel"][:] = row["net"] / 1024
        row["F"][:] = row["F_kernel"]
        row["ledger"] = np.stack([row["F_kernel" if k == "F" else k] for k in M.A.LEDGER], axis=1)
        row["seeds"] = np.arange(n, dtype=np.uint64)  # Synthetic pairing only; no scientific IDs.
        row["cpu_seconds"] = np.asarray(0.01)
        row["wall_seconds"] = np.asarray(0.02)
        M.A.validate_row(row, world, n)
        rows.append(row)
    vectors = {}
    for category, pairs in M.PAIRS.items():
        for a, b in pairs:
            result, terms = M.A.paired_terms(rows[a], rows[b], world)
            assert result["columns"]["captures"]["mean"] == a - b
            vectors.update({category + "__" + M.LABELS[a] + "__" + k: v for k, v in terms.items()})
    assert len(vectors) == 219 and all(v.shape == (n,) for v in vectors.values())
    assert np.all(vectors["primary__AI_reserve__captures"] == 1)
    assert not any(
        n.startswith(("src.evolve", "src.run", "src.checkpoint", "src.life.build", "src.life.evaluate"))
        for n in sys.modules
    )
