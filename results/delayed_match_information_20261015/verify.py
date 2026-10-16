"""Verify the frozen information study without importing or invoking the simulator."""
import hashlib
import json
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text())


def verify():
    manifest = read(HERE / "manifest.json")
    actual = {str(p.relative_to(HERE)) for p in HERE.rglob("*")
              if p.is_file() and p != HERE / "manifest.json" and "__pycache__" not in p.parts}
    assert actual == set(manifest["files"]), "archive inventory changed"
    for name, pin in manifest["files"].items():
        path = (HERE / name).resolve()
        assert path.is_relative_to(HERE) and not path.is_symlink()
        assert sha(path) == pin["sha256"] and path.stat().st_size == pin["bytes"], name
    study = HERE / "prelaunch"
    protocol = read(study / "protocol.json")
    ready = read(study / "READY.json")
    release = read(study / "release.json")
    assert ready["protocol_sha256"] == release["protocol_sha256"] == sha(study / "protocol.json")
    assert release["status"] == "released"
    assert ready["preparation_lives"] == ready["preparation_builds"] == ready["preparation_random_draws"] == 0
    for label in ("source_pins", "input_pins"):
        for name, expected in protocol[label].items():
            path = (study / name).resolve()
            assert path.is_relative_to(study) and sha(path) == expected, name
    assert sha(HERE / "seed_audit.json") == protocol["seed_audit_sha256"]
    assert sha(study / "reservation.json") == protocol["reservation_sha256"]
    assert protocol["development_seeds"] == list(range(52440000, 52440064))
    assert protocol["confirmation_seeds"] == list(range(52450000, 52450512))
    assert protocol["scientific_calls"] == 6656 and protocol["engineering_calls"] == 40
    assert protocol["development_calls"] == 16 * 64 and protocol["confirmation_calls"] == 11 * 512
    for name, expected in protocol["production_pins"].items():
        data = subprocess.check_output(["git", "show", protocol["source_revision"] + ":" + name], cwd=ROOT)
        assert hashlib.sha256(data).hexdigest() == expected, name
    for item in read(HERE / "namespace_references.json"):
        assert sha(ROOT / item["public_path"]) == item["sha256"], item["public_path"]
    return dict(status="passed", archive_files=len(actual), protocol_sha256=sha(study / "protocol.json"),
                planned_scientific_calls=6656, completed_engineering_calls=40, verifier_simulations=0)


if __name__ == "__main__":
    print(json.dumps(verify(), indent=2))
