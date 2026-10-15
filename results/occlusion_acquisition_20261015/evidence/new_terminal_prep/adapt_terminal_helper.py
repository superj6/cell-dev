"""Source-only AM→AN coverage/identity adaptation; does not execute the helper."""
import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
OLD = ROOT / 'outputs/audit_capture_value_selection_20261015/terminal_review/verify_terminal_raw.py'
DEST = Path(__file__).resolve().parent / 'verify_terminal_raw.py'
s = OLD.read_text()
s = s.replace('AM terminal-only', 'AN terminal-only')
s = s.replace('autonomous_capture_value_selection_20261015', 'autonomous_occlusion_acquisition_20261015')
s = s.replace('audit_capture_value_selection_20261015/terminal_review/independent', 'audit_occlusion_acquisition_20261015/terminal_review/independent')
s = s.replace('3c22015e7415467e273ace9cf8248b53b4ecf37f4584c406e73807fe196ed474', '7e4f67840047bf20cc3a872983483724b6b75cd2733487b5baa51126e101a922')
s = s.replace('PROTOCOL_SHA = None  # Explicit terminal command binds the root-reviewed protocol.', 'PROTOCOL_SHA = "ca277b17294bbce52a4fd6bde77e5847b6b5230c00d285ba8492538f7508b26b"')
s = s.replace('ROLES = ("AI_control_start", "AL_mixture_start", "current_value_final", "high_value_final")', 'ROLES = ("AM_current_start", "generation4", "generation8")')
s = s.replace('ARMS = ("current_value", "high_value")', 'ARMS = ("acquisition",)')
s = s.replace('WORLDS = ("pool", "persistent", "blink80_5", "turn100_blink80_5")', 'WORLDS = ("pool", "persistent", "blink80_5", "blink80_20", "turn100_blink80_20")')
s = s.replace('pairs = ((ROLES[1], ROLES[0]), (ROLES[2], ROLES[0]), (ROLES[3], ROLES[0]),\n             (ROLES[2], ROLES[1]), (ROLES[3], ROLES[1]), (ROLES[3], ROLES[2]))', 'pairs = ((ROLES[1], ROLES[0]), (ROLES[2], ROLES[0]), (ROLES[2], ROLES[1]))')
s = s.replace('for w in ("pool", "blink80_5", "turn100_blink80_5"):', 'for w in ("pool", "blink80_5", "blink80_20", "turn100_blink80_20"):')
s = s.replace('retention = ((1, 0, "persistent"), (2, 0, "persistent"), (3, 0, "persistent"),\n                 (2, 1, "pool"), (2, 1, "persistent"), (3, 1, "pool"), (3, 1, "persistent"))', 'retention = ((1, 0, "pool"), (1, 0, "persistent"), (2, 0, "pool"), (2, 0, "persistent"))')
s = s.replace('4064','2933').replace('28748','28214').replace('28756','28222').replace('20556','20534').replace('10278','20534').replace('8192','7680')
s = s.replace('"raw_rows": 16', '"raw_rows": 15')
s = s.replace('record["startup_lives"] != 2', 'record["startup_lives"] != 4')
s = s.replace('if len(args.protocol_sha256) != 64 or any(c not in "0123456789abcdef" for c in args.protocol_sha256):', 'if args.protocol_sha256 != PROTOCOL_SHA:')
s = s.replace('One paired evolution from one chosen lineage; confirmation seeds are not evolutionary repetitions.', 'One uninterrupted eight-generation acquisition trajectory; confirmation seeds are not evolutionary repetitions.')
s = s.replace('High-minus-current capture gains require both contexts for joint success; relative advantage alone is not improvement over the AL start.', 'The primary is generation8 minus the fixed AM start on blink80_20; generation4 cannot replace generation8 after confirmation.')
s = s.replace('Full native genetic and selection replay is a separate independent audit.', 'Full native genetic/selection replay, including the generation4 checkpoint, is a separate independent audit.')
old_nodes={n.name:ast.dump(n) for n in ast.parse(OLD.read_text()).body if isinstance(n,ast.FunctionDef)}
new_nodes={n.name:ast.dump(n) for n in ast.parse(s).body if isinstance(n,ast.FunctionDef)}
assert all(old_nodes[k]==new_nodes[k] for k in ('read','sha','stat','literal_row','recount'))
assert not DEST.exists()
DEST.write_text(s)
