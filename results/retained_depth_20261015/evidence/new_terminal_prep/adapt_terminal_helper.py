"""Source-only AN to AO terminal coverage adaptation; never reads AO observations."""
import ast
from pathlib import Path

ROOT = next(p for p in Path(__file__).resolve().parents if (p / 'src/life/spec.py').is_file())
OLD = ROOT / 'outputs/audit_occlusion_acquisition_20261015/new_terminal_prep/verify_terminal_raw.py'
DEST = Path(__file__).resolve().parent / 'verify_terminal_raw.py'
s = OLD.read_text()
s = s.replace('AN terminal-only', 'AO terminal-only')
s = s.replace('autonomous_occlusion_acquisition_20261015', 'autonomous_retained_depth_20261015')
s = s.replace('audit_occlusion_acquisition_20261015/terminal_review/independent',
              'autonomous_retained_depth_20261015/terminal_review/independent')
s = s.replace('7e4f67840047bf20cc3a872983483724b6b75cd2733487b5baa51126e101a922',
              'a701f500e8c87867c9d3e866ecc4abcba44529c6c72e0f5935b5f3d8566e0a91')
s = s.replace('ca277b17294bbce52a4fd6bde77e5847b6b5230c00d285ba8492538f7508b26b',
              '2cfc3ac9a6d41e2d3c49e630a7bc611ff9737962175def3d1eb89e6d8de6d68d')
s = s.replace('ROLES = ("AM_current_start", "generation4", "generation8")',
              'ROLES = ("AM_reference", "AN_start", "unchanged8", "unchanged24", "balanced8", "balanced24")')
s = s.replace('ARMS = ("acquisition",)', 'ARMS = ("unchanged", "balanced")')
s = s.replace('pairs = ((ROLES[1], ROLES[0]), (ROLES[2], ROLES[0]), (ROLES[2], ROLES[1]))',
              'pairs = tuple((ROLES[new], ROLES[old]) for old in range(6) for new in range(old + 1, 6))')
s = s.replace('retention = ((1, 0, "pool"), (1, 0, "persistent"), (2, 0, "pool"), (2, 0, "persistent"))',
              '''retention = tuple((new, old, world) for new in range(2, 6)
                      for old, worlds in ((1, ("pool", "persistent", "blink80_20")),
                                          (0, ("pool", "persistent"))) for world in worlds)
    retention += ((5, 3, "blink80_20"),)''')
s = s.replace('2933', '11967').replace('28214', '138476').replace('28222', '138488')
s = s.replace('marker["startup_lives"] != 8', 'marker["startup_lives"] != 12')
s = s.replace('record["research_lives"] != 20534', 'record["research_lives"] != 61558')
s = s.replace('"raw_rows": 15, "raw_confirmation_lives": 7680, "native_search_research_lives": 20534',
              '"raw_rows": 30, "raw_confirmation_lives": 15360, "native_search_research_lives": 123116')
s = s.replace('"startup_lives": 8, "total_calls": 138488', '"startup_lives": 12, "total_calls": 138488')
s = s.replace('One uninterrupted eight-generation acquisition trajectory; confirmation seeds are not evolutionary repetitions.',
              'One matched pair of 24-generation trajectories; confirmation seeds and checkpoints are not evolutionary repetitions.')
s = s.replace('Raw status coverage is all7680 confirmation lives;', 'Raw status coverage is all15360 confirmation lives;')
s = s.replace('The primary is generation8 minus the fixed AM start on blink80_20; generation4 cannot replace generation8 after confirmation.',
              'Joint success requires balanced24-minus-unchanged24 POOL capture gain and 90% blink80_20 noninferiority; the actual blink difference is also retained.')
s = s.replace('Full native genetic/selection replay, including the generation4 checkpoint, is a separate independent audit.',
              'Full native genetic/selection replay, including both generation8 checkpoints and final24 populations, is a separate independent audit.')
accuracy = '''def accuracy_counts(rows):
    """Literal aggregate counts; no per-click/binomial uncertainty or zero-click imputation."""
    if tuple(rows) != WORLDS or any(tuple(rows[w]) != ROLES for w in WORLDS):
        raise ValueError("complete 30-row accuracy matrix required")
    report = {}
    for world in WORLDS:
        report[world] = {}
        for role in ROLES:
            captures, misses, clicks = (rows[world][role][key] for key in ("captures", "misses", "clicks"))
            if (any(x.shape != (512,) or not np.isfinite(x).all() or np.any(x < 0)
                    or np.any(x != np.floor(x)) for x in (captures, misses, clicks))
                    or not np.array_equal(captures + misses, clicks)):
                raise ValueError("finite integer captures + misses = clicks required")
            totalcap, totalmiss, totalclick = (int(x.sum()) for x in (captures, misses, clicks))
            report[world][role] = {
                "lives": 512, "total_captures": totalcap, "total_misses": totalmiss, "total_clicks": totalclick,
                "aggregate_capture_fraction": totalcap / totalclick if totalclick else None,
                "mean_captures_per_life": float(captures.mean()), "mean_misses_per_life": float(misses.mean()),
                "mean_clicks_per_life": float(clicks.mean()), "clickless_lives": int(np.count_nonzero(clicks == 0)),
                "clickless_fraction": float(np.mean(clicks == 0))}
    return report


'''
s = s.replace('def main():', accuracy + 'def main():')
s = s.replace('if read(canonical / "summary.json")["status"] != "complete":',
              'canonical_summary = read(canonical / "summary.json")\n    if canonical_summary["status"] != "complete":')
s = s.replace('vectors = all_vectors(rows)\n    max_error',
              'vectors = all_vectors(rows)\n    accuracy = accuracy_counts(rows)\n'
              '    if accuracy != canonical_summary["capture_accuracy"]:\n'
              '        raise ValueError("literal aggregate accuracy differs from canonical summary")\n    max_error')
s = s.replace('"canonical_frozen_reanalysis_exact_bytes": True, "status_counts": statuses,',
              '"canonical_frozen_reanalysis_exact_bytes": True, "status_counts": statuses,\n'
              '        "accuracy_rows_checked": 30, "accuracy_exact": True, "capture_accuracy": accuracy,\n'
              '        "accuracy_limit": "Aggregate captures/clicks weights clicks; no binomial SE. No-click rows return null.",')
old_nodes = {n.name: ast.dump(n) for n in ast.parse(OLD.read_text()).body if isinstance(n, ast.FunctionDef)}
new_nodes = {n.name: ast.dump(n) for n in ast.parse(s).body if isinstance(n, ast.FunctionDef)}
assert all(old_nodes[k] == new_nodes[k] for k in ('read', 'sha', 'stat', 'literal_row', 'recount'))
assert not DEST.exists()
DEST.write_text(s)
