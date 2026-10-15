"""Record actual AI inputs and current status before runtime release."""
from pathlib import Path
import hashlib
import json

AUDIT = Path(__file__).resolve().parent
ROOT = AUDIT.parents[1]
STUDY = ROOT / 'outputs/autonomous_exploratory_reserve_replication_20261014'
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
protocol = json.loads((STUDY / 'protocol.json').read_text())
registration = json.loads((STUDY / 'registration.json').read_text())
assert sha(STUDY / 'registration.json') == '3c020f3ea897224388e4e4b156a0941b3dd1952628a1db5c327c9a3ef911cd4c'
assert protocol['paired_native_seed'] == 53227 and protocol['generations'] == 4
assert protocol['confirmation']['seeds'] == list(range(52360000, 52360512))
assert protocol['planned_genome_lives'] == 9804 and protocol['startup_validation_genome_lives'] == 6
assert not any((STUDY / name).exists() for name in ['ready.json', 'attempt.json', 'budget.json', 'runs'])
for name, digest in protocol['file_pins'].items():
    assert sha(STUDY / name) == digest, name
for name, digest in protocol['production_pins'].items():
    assert sha(ROOT / name) == digest, name
pin = sha(STUDY / 'protocol.json')
local, production = len(protocol['file_pins']), len(protocol['production_pins'])
entry = (AUDIT / 'preregister_text_draft.md').read_text()
entry = entry.replace('2026-10-14 — AI registered:', '2026-10-15 — AI registered and prepared:', 1)
old = '''One-time preparation may copy the fixed inputs and generate exactly one shared initialization with recorded
operations. It runs no compiler or life.'''
new = '''One-time preparation copied the fixed inputs and generated exactly one shared 32-row initialization with
62 recorded ordinary point additions. It ran no compiler or life.'''
assert old in entry
entry = entry.replace(old, new, 1)
entry += f'''
The audited native seed is **53227**, with 64 native life IDs intentionally shared across the arms. Confirmation
uses **52,360,000–52,360,511** in fresh block 136; the 576 combined unique IDs exclude prior allocations and
standard golden seed 11. All 44 prior process identities, 31 groups and fifteen terminal budgets are clear.
Protocol `{pin}` pins **{local} local / {production} production files**. Five focused producer and five reader checks
pass; complete-module comparisons preserve AH's scientific logic and reuse its substantive tests. Actual-input,
bound-reader and prospective-publication checks precede runtime release. The initial shared-path collision
between two administrative helper-review receipts was resolved by recovering the original bytes exactly;
both reviews and their recovery record are preserved, with no scientific source change or engine execution.
'''
with (AUDIT / 'preregister_text.md').open('x') as f:
    f.write(entry)
p = ROOT / 'RESULTS.md'
text = p.read_text()
assert entry.splitlines()[0] not in text
p.write_text(text + '\n' + entry)

handoff = f'''**AI registered and prepared (2026-10-15).** A second independent matched four-generation pair repeats
AH's exact two-slot reserve policy, including its SHA lottery domain, from the same AE L92 founder. The new
native seed 53227 and block 136 confirmation IDs are audited; one shared 32-row initialization with 62 recorded
point additions is prepared. Both final rank-zero endpoints and the start will receive 512 fresh paired lives.
The primary contrast is reserve minus control captures, with F, both own-start contrasts and all cost/penalty
terms. AI is motivated by AH's positive relative result; AH is not the new control and its 512 lives are not
512 evolutionary repetitions. All 9,810 calls retain the 5,400 total / 3,400 search / 2,000 reserve CPU limits.
Protocol `{pin[:8]}…{pin[-7:]}` pins {local} local / {production} production files. Actual-input review and public
preparation precede separate runtime release; no compiler or life ran during preparation. Prices, world,
local asynchronous rules, genetic operators and production code remain unchanged. Evidence:
`results/exploratory_reserve_replication_20261014/`. One further pair on this selected background cannot establish
general policy reliability, memory or a richer algorithm. Longer ordinary depth remains a separate candidate.

'''
p = ROOT / 'docs/HANDOFF.md'
text = p.read_text()
marker = '**Wrap-up complete (2026-10-14).**'
assert marker in text
text = text.replace(marker, handoff + marker, 1)
text = text.replace('# Handoff: cell-dev (2026-10-14)', '# Handoff: cell-dev (2026-10-15)', 1)
current_marker = '**Primary objective, clarified by the user (2026-10-14):**'
current = '''**Current work (2026-10-15).** AH is complete and pushed (`b46aca9`): one reserve endpoint beats its matched
control in capture performance, without protected-offspring ancestry. AI repeats the unchanged comparison with
an independent search seed. It is registered and prepared, with no simulation yet; actual-input checks and
prospective publication precede runtime release. Detailed evidence and limitations appear in the entries below.

'''
assert current_marker in text
text = text.replace(current_marker, current + current_marker, 1)
p.write_text(text)

p = ROOT / 'docs/TASK_VARIATION_PLAN.md'
text = p.read_text()
marker = '*2026-10-14 post hoc capture-value sensitivity:*'
entry = f'''*2026-10-15 AI registered and prepared:* repeat AH's exact four-generation matched reserve/control
comparison from the fixed AE L92 founder, with independent native seed 53227 and fresh block 136. One shared
32-row initialization is recorded; no compiler or life ran. Both endpoints and the start receive 512 paired
confirmation lives, led by reserve-minus-control captures. Policy, fitness, prices, world and local rules are
unchanged. All 9,810 calls retain the 5,400 CPU-second cap with 2,000 reserved for confirmation. Protocol
`{pin[:8]}…{pin[-7:]}` pins {local}/{production} local/production files. AI is explicitly motivated by the positive
AH pilot; report it separately and do not pool life-level precision as search replication. Actual-input and
bound-reader review plus public preparation precede runtime release. Evidence:
`results/exploratory_reserve_replication_20261014/`. No larger family, paid compute or new organism rule is released.

'''
assert marker in text
p.write_text(text.replace(marker, entry + marker, 1))
