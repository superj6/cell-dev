"""House style that ruff does not check: lines of at most 120 characters. pyproject.toml ignores E501 because older
files predate the limit, so ``LEGACY`` pins how many long lines each such file has (all from f2142c8 or earlier). A
file may lose long lines (then lower its count here), never gain one."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LIMIT = 120
LEGACY = {"src/develop.py": 1, "src/evolve.py": 3, "src/genome.py": 1, "src/life/build.py": 1, "src/run.py": 3,
          "scripts/census.py": 1, "scripts/life_census.py": 4, "scripts/life_gates.py": 3,
          "scripts/life_reference.py": 1, "scripts/replay.py": 1, "tests/test_lattice.py": 1,
          "tests/test_life_genome.py": 1, "tests/test_life_growth_death.py": 1,
          "tests/test_task_withdraw.py": 2}


def long_lines() -> dict[str, int]:
    """Lines over ``LIMIT`` characters per Python file under src, scripts and tests."""
    out = {}
    for d in ("src", "scripts", "tests"):
        for p in sorted((ROOT / d).rglob("*.py")):
            n = sum(len(line) > LIMIT for line in p.read_text(encoding="utf-8").splitlines())
            if n:
                out[p.relative_to(ROOT).as_posix()] = n
    return out


def test_no_new_lines_over_120_characters():
    found = long_lines()
    grown = {f: (n, LEGACY.get(f, 0)) for f, n in found.items() if n > LEGACY.get(f, 0)}
    assert not grown, f"files with more lines over {LIMIT} characters than allowed (found, allowed): {grown}"
    fixed = {f: (found.get(f, 0), n) for f, n in LEGACY.items() if found.get(f, 0) < n}
    assert not fixed, f"long lines were fixed: lower LEGACY to the found counts (found, listed): {fixed}"
