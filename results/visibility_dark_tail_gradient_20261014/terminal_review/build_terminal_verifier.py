"""Narrowly adapt completed AE recount to AG, retaining AC's literal ABI4 arithmetic."""

import ast
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
ae = ROOT / "outputs/audit_prediction_gradient_20261014/new_ae/review_terminal.py"
ac = ROOT / "outputs/audit_visibility_flash_gradient_20261014/review_terminal.py"
old, physical_source = ae.read_text(), ac.read_text()


def segment(source, name):
    tree = ast.parse(source)
    for node in tree.body:
        if ((isinstance(node, ast.FunctionDef) and node.name == name) or
            (isinstance(node, ast.Assign) and isinstance(node.targets[0], ast.Name) and node.targets[0].id == name)):
            return ast.get_source_segment(source, node)
    raise ValueError(name)


text = old
for name in ("LEDGER", "COUNTS", "physical"):
    text = text.replace(segment(old, name), segment(physical_source, name))
text = text.replace("Independent AE raw recount", "Independent AG raw recount")
text = text.replace("0f5a591fbfb66fd29b5f9cd11d42b482eb8cb09e74613b17cc384ed2c3daa849",
                    "ff9af8c7fcb140bb4f09b6636e59df92272254851dfe1f33a4d6441be1a7955f")
text = text.replace("persistent", "flash5_dark")
text = text.replace('delta.update(\n            capture_income=',
                    'delta.update(\n            bright_captures=delta["captures"] - delta["low_light_captures"],\n            capture_income=')
text = text.replace('len(delta) == 64', 'len(delta) == 66').replace('all64 metric', 'all66 metric').replace('all64 worker', 'all66 worker')
text = text.replace('len(vectors) == 128', 'len(vectors) == 132').replace('complete128 paired', 'complete132 paired')
text = text.replace('"raw_ledger_columns": 57', '"raw_ledger_columns": 58')
text = text.replace('"paired_vectors_bitwise_checked": 128', '"paired_vectors_bitwise_checked": 132')
text = text.replace('"paired_vectors": 128', '"paired_vectors": 132')
text = text.replace('("F", "captures", "capture_income", "ordinary_cost", "guard_cost", "extinction_cost")',
                    '("F", "captures", "low_light_captures", "bright_captures", "capture_income", "ordinary_cost", "guard_cost", "extinction_cost", "n_end", "spikes", "path")')
path = HERE / "review_terminal.py"
assert not path.exists()
path.write_text(text)
assert ast.dump(ast.parse(segment(text, "physical"))) == ast.dump(ast.parse(segment(physical_source, "physical")))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


receipt = {
    "status": "source_prepared_before_raw_execution",
    "script_sha256": sha(path),
    "origins": {str(p.relative_to(ROOT)): sha(p) for p in (ae, ac)},
    "physical_function_AST_identical_to_completed_AC": True,
    "changes": ["AG protocol/world label", "AC58 literal columns, counts and unchanged physical arithmetic",
                "four-role one-world AE matrix retained", "bright-capture delta added for132 vectors",
                "compact receipt includes low/bright captures and cell/spike/path quantities"],
    "frozen_files_modified": False,
    "raw_artifacts_opened": 0,
    "engine_calls": 0,
}
(HERE / "terminal_verifier_preparation.json").write_text(json.dumps(receipt, indent=2) + "\n")
print(json.dumps(receipt, indent=2))
