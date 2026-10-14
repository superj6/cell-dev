"""Pure offline checks for the prepared F archive; no simulator imports or life executions."""
import importlib.util
import json
import shutil
from pathlib import Path

import pytest


def validator():
    path = Path(__file__).with_name("validate.py")
    spec = importlib.util.spec_from_file_location("discrimination_archive", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_prepared_archive_validates_without_simulation():
    result = validator().validate_archive(Path(__file__).parent)
    assert result["scientific_candidate_lives"] == 0
    assert result["planned_candidate_lives"] == 3584
    assert result["saved_replay_comparisons_checked"] == 12
    assert result["simulation_executed"] is False


def test_changed_archive_bytes_are_rejected(tmp_path):
    source = Path(__file__).parent
    shutil.copytree(source, tmp_path / "archive", ignore=shutil.ignore_patterns("__pycache__", ".pytest_cache"))
    protocol = tmp_path / "archive/protocol.json"
    protocol.write_text(protocol.read_text() + " ")
    with pytest.raises(ValueError, match="archive artifact differs"):
        validator().validate_archive(tmp_path / "archive")


def test_changed_budget_is_rejected_even_with_updated_file_receipt(tmp_path):
    run = validator()
    source = Path(__file__).parent
    base = tmp_path / "archive"
    shutil.copytree(source, base, ignore=shutil.ignore_patterns("__pycache__", ".pytest_cache"))
    path = base / "protocol.json"
    protocol = json.loads(path.read_text())
    protocol["max_cpu_seconds"] = 3600
    path.write_text(json.dumps(protocol))
    provenance_path = base / "provenance.json"
    provenance = json.loads(provenance_path.read_text())
    provenance["artifacts"]["protocol.json"] = {"sha256": run.sha(path), "bytes": path.stat().st_size}
    provenance_path.write_text(json.dumps(provenance))
    with pytest.raises(ValueError, match="dimensions or budget differ"):
        run.validate_archive(base)
