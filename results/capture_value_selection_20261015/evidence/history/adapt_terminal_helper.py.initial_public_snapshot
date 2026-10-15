"""Build a source-only AM verifier from the completed AL literal audit."""
from pathlib import Path
ROOT = Path(__file__).resolve().parents[3]
OLD = ROOT / 'outputs/audit_retention_selection_20261015/terminal_review/verify_terminal_raw.py'
OUT = Path(__file__).resolve().parent / 'verify_terminal_raw.py'
s = OLD.read_text().replace('AL terminal-only','AM terminal-only')
s = s.replace('autonomous_retention_selection_20261015','autonomous_capture_value_selection_20261015')
s = s.replace('audit_retention_selection_20261015','audit_capture_value_selection_20261015')
s = s.replace('1152fbef215aad60f09b010fb8308f3b908aa36fc995dcbab7921a1e5dc05302',
              '3c22015e7415467e273ace9cf8248b53b4ecf37f4584c406e73807fe196ed474')
s = s.replace('PROTOCOL_SHA = "25575f9ef690d00741fea0c62570d15aeb526d66a13a42025a91c5cd2fad19bf"',
              'PROTOCOL_SHA = None  # Explicit terminal command binds the root-reviewed protocol.')
s = s.replace('"AI_control_start", "persistent_control_final", "mixture_final"',
              '"AI_control_start", "AL_mixture_start", "current_value_final", "high_value_final"')
s = s.replace('"persistent_control", "balanced_mixture"', '"current_value", "high_value"')
# Only raw vector length changes; all literal physics and arithmetic retain exact order.
s = s.replace('(256,', '(512,').replace('np.zeros(256,', 'np.zeros(512,').replace('np.full(256,', 'np.full(512,')
s = s.replace('for i in range(3)}', 'for i in range(len(ROLES))}')
s = s.replace('pairs = ((ROLES[1], ROLES[0]), (ROLES[2], ROLES[0]), (ROLES[2], ROLES[1]))',
'''pairs = ((ROLES[1], ROLES[0]), (ROLES[2], ROLES[0]), (ROLES[3], ROLES[0]),
             (ROLES[2], ROLES[1]), (ROLES[3], ROLES[1]), (ROLES[3], ROLES[2]))''')
start=s.index('    for role in ROLES[1:]:')
end=s.index('    if len(vectors)',start)
s=s[:start]+'''    retention = ((1, 0, "persistent"), (2, 0, "persistent"), (3, 0, "persistent"),
                 (2, 1, "pool"), (2, 1, "persistent"), (3, 1, "pool"), (3, 1, "persistent"))
    for new_index, old_index, world in retention:
        role, ancestor = ROLES[new_index], ROLES[old_index]
        key = f"retention__{role}_vs_{ancestor}__{world}"
        new, previous = rows[world][role]["captures"], rows[world][ancestor]["captures"]
        vectors[key + "__capture_difference"] = new - previous
        vectors[key + "__ninety_percent_reference"] = new - .9 * previous
''' + s[end:]
for old,new in [('2254','4064'),('13388','28748'),('13396','28756'),('5158','10278'),('3072','8192'),('10316','20556')]:
    s=s.replace(old,new)
s=s.replace('"raw_rows": 12','"raw_rows": 16')
s=s.replace('def main():\n', 'def main():\n    global PROTOCOL_SHA\n')
s=s.replace('    parser.add_argument("--budget-sha256", required=True)',
'''    parser.add_argument("--protocol-sha256", required=True)
    parser.add_argument("--budget-sha256", required=True)''')
s=s.replace('    study = args.study.resolve()',
'''    if len(args.protocol_sha256) != 64 or any(c not in "0123456789abcdef" for c in args.protocol_sha256):
        raise ValueError("exact root-reviewed protocol SHA256 required")
    PROTOCOL_SHA = args.protocol_sha256
    study = args.study.resolve()''')
s=s.replace('A positive mixture-control POOL difference alone is not recovery relative to AI start or ancestral L92.',
            'High-minus-current capture gains require both contexts for joint success; relative advantage alone is not improvement over the AL start.')
OUT.write_text(s)
