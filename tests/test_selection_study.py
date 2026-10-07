"""The forward runs of the selection study (results/selection_study/) are kept in the repo, and the numbers RESULTS.md
quotes from them ("Pilot preparation", part 1) follow from those files. Escaped = at least half of the final parents
are bodies (mean end size >= 1.5 cells); beats the lone cell = the parents' mean F exceeds 0.0328 + 0.0005."""
import json
from collections import defaultdict
from math import comb
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "results/selection_study/data"
LONE = 0.0328
CHOSEN, RECHECK_ONLY = "B1:64:4", "B2:64:4"  # the pilot's key (mean of all 7 lives) and ranking by the 4 rechecks


def fisher(a: int, n1: int, b: int, n2: int) -> float:
    """Two-sided Fisher exact p for a/n1 against b/n2."""
    k, n = a + b, n1 + n2
    p0 = comb(n1, a) * comb(n2, b) / comb(n, k)
    ps = [comb(n1, x) * comb(n2, k - x) / comb(n, k) for x in range(max(0, k - n2), min(k, n1) + 1)]
    return sum(p for p in ps if p <= p0 * (1 + 1e-9))


def test_the_study_data_is_kept():
    for name in ("fwd/esc_g12.json", "fwd/esc_g12_r16.json", "fwd/esc_g12_r32.json", "fwd/bodies_g30.json",
                 "fwd50/esc_g12_A_b.json", "fwd50/esc_g12_B1644_b.json", "fwd50/esc_g12_B2644.json",
                 "logs/fwd50_A.log", "logs/fwd50_B1644.log", "logs/fwd50_B2644.log", "pops/esc_hex_s0_g12.npz",
                 "pops/hex_s0_g30.npz"):
        assert (DATA / name).is_file(), name
    assert (ROOT / "results/selection_study/README.md").is_file()


def test_twenty_generations_from_the_escape():
    by = defaultdict(dict)
    for f in sorted(DATA.glob("fwd/esc_g12*.json")):
        for r in json.loads(f.read_text()):
            by[r["scheme"]][r["rep"]] = r
    assert {s: len(v) for s, v in by.items()} == {"A": 48, CHOSEN: 48, RECHECK_ONLY: 48}
    esc = {s: sum(r["body_share"] >= 0.5 for r in v.values()) for s, v in by.items()}
    assert esc == {"A": 20, CHOSEN: 12, RECHECK_ONLY: 5}
    assert round(fisher(12, 48, 20, 48), 2) == 0.13


def test_fifty_generations_from_the_escape():
    rows = defaultdict(dict)
    for f in sorted(DATA.glob("logs/fwd50_*.log")):
        for line in f.read_text().splitlines():
            r = json.loads(line)
            rows[r["scheme"]][(r["rep"], r["gens"])] = r
    reps = range(24)
    end = {s: [v[(rep, 50)] for rep in reps] for s, v in rows.items()}  # every scheme finished all 24
    body = {s: sum(r["body_share"] >= 0.5 for r in v) for s, v in end.items()}
    beat = {s: sum(r["mean_F"] > LONE + 0.0005 for r in v) for s, v in end.items()}
    mean_F = {s: round(sum(r["mean_F"] for r in v) / 24, 4) for s, v in end.items()}
    assert body == {"A": 19, CHOSEN: 12, RECHECK_ONLY: 5}
    assert beat == {"A": 13, CHOSEN: 12, RECHECK_ONLY: 5}
    assert mean_F == {"A": 0.0420, CHOSEN: 0.0418, RECHECK_ONLY: 0.0358}
    assert round(fisher(12, 24, 19, 24), 3) == 0.069  # bodies: the chosen key against one-stage
    assert round(fisher(5, 24, 13, 24), 3) == 0.036  # beating the lone cell: recheck-only against one-stage
    stored = [r for f in ("fwd50/esc_g12_A_b.json", "fwd50/esc_g12_B1644_b.json", "fwd50/esc_g12_B2644.json")
              for r in json.loads((DATA / f).read_text())]
    assert len(stored) == 18 + 9 + 72
    for r in stored:  # the JSON files hold the same rows as the logs
        assert {k: v for k, v in r.items() if k != "per_genome"} == rows[r["scheme"]][(r["rep"], r["gens"])]
