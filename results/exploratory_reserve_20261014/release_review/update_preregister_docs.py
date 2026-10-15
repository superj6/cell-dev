"""Record the actual AH preparation before any runtime release."""
from pathlib import Path
import hashlib
import json

AUDIT = Path(__file__).resolve().parent
ROOT = AUDIT.parents[1]
STUDY = ROOT / 'outputs/autonomous_exploratory_reserve_20261014'
p = STUDY / 'protocol.json'
assert hashlib.sha256(p.read_bytes()).hexdigest() == '0a9e505969ed11cd8f240f9404bbff2adf9a91d91d5387252fd9595874c61be4'
protocol = json.loads(p.read_text())
assert len(protocol['file_pins']) == 102 and len(protocol['production_pins']) == 35
assert not any((STUDY / name).exists() for name in ['ready.json', 'attempt.json', 'budget.json', 'runs'])

entry = (AUDIT / 'preregister_text_draft.md').read_text()
old = '''One-time preparation may generate exactly one shared native initialization with recorded operations, copy
fixed inputs and freeze both configs. It runs no life or compiler. Actual-input and independent reader review,
prospective publication and separate root release precede measurement. The completed AG resource state is a
dependency; its scientific sign is not.'''
new = '''One-time preparation has generated exactly one shared 32-row native initialization: the fixed founder plus
31 ordinary two-point mutants, with all 62 additions recorded. Both configurations and fixed inputs are frozen.
It ran no life or compiler. Actual-input and independent reader review, prospective publication and separate root
release precede measurement. The completed AG resource state is a dependency; its scientific sign is not.'''
assert old in entry
entry = entry.replace(old, new)
entry += '''
The audited shared native run seed is **53226**. Its 64 unique native life IDs are intentionally reused across
the two arms; fresh confirmation uses **52,350,000–52,350,511** (block 135). The 576 combined unique IDs exclude
prior study IDs and standard golden seed 11. All 40 prior process identities, 28 groups and fourteen terminal
budgets are clear. Actual protocol `0a9e5059…4c61be4` pins **102 local and 35 production files**, with exact
66-coordinate ABI3 world packing. The source reviews include 20 producer and 47 reader checks plus one focused
archive-portability check. No runtime release is implied by registration or successful genetic preparation.
'''

handoff_entry = '''**AH registered and prepared (2026-10-14).** One matched four-generation pair from fixed AE L92
row31 compares ordinary selection with a two-slot fresh-offspring reserve. L92 is deliberately chosen after
AE's capture gain and AF's later loss, not a representative background. In treatment generations 0–2, two random
fresh offspring join the recheck shortlist and breeder population regardless of F; the other slots use unchanged
F ranking. The final generation is ordinary. Both arms share their initial cohort/native seed and must match
their first 256 candidate genotypes byte-for-byte. The start and both fixed final rank-zero endpoints then receive 512 fresh paired
lives. Reserve-minus-control captures leads the report, with both gains versus start and full F/cost accounting.
The 9,804 research plus six golden calls have a 5,400 CPU-second cap, startup/search at 3,400 and confirmation
reserve 2,000; historical timing projections are 2,690.125/957.204 seconds. Shared native seed 53226 and fresh
block 135 are audited. One shared 32-row initialization with 62 recorded point additions is prepared; no lives
or builds ran. Protocol `0a9e5059…4c61be4` pins 102 local/35 production files. Actual-input/reader review and
prospective publication precede separate root release. Evidence: `results/exploratory_reserve_20261014/`.
Prices, task F, ABI3 world, local rules and production defaults stay fixed. A single paired search cannot establish
policy reliability, a necessary stepping stone, memory or a new algorithm.

'''
plan_entry = '''*2026-10-14 AH registered and prepared:* a small external-selection pilot compares ordinary selection
with two uniformly chosen fresh offspring protected through recheck and breeding in generations 0–2, followed
by ordinary final selection. Both four-generation arms share fixed AE L92, their initial cohort and native seed.
This deliberately chosen background motivates a targeted pilot, not a reliability claim. Confirm the start and
both final endpoints on 512 fresh shared lives; lead with reserve-minus-control captures and retain both own-start
gains plus full net-F accounting. Task F, prices, world and local asynchronous rules are unchanged. All 9,810 calls
fit a fixed 5,400 CPU-second ceiling, with 2,000 reserved for confirmation; actual costs may exceed the historical
planning assumptions. Seed 53226 supplies intentionally shared native IDs; block 135 provides fresh confirmation.
One shared initialization with 62 recorded additions is prepared without compilation or lives. Protocol
`0a9e5059…4c61be4` pins 102 local/35 production files. Actual-input/reader review and public preparation precede
runtime release. Evidence: `results/exploratory_reserve_20261014/`. This tests exploration access, without new
organism behavior or a secondary capture reward; it cannot make persistently uneconomic behavior competitive.

'''
results_path = ROOT / 'RESULTS.md'
handoff_path = ROOT / 'docs/HANDOFF.md'
plan_path = ROOT / 'docs/TASK_VARIATION_PLAN.md'
results = results_path.read_text()
handoff = handoff_path.read_text()
plan = plan_path.read_text()
handoff_marker = '**Wrap-up complete (2026-10-14).**'
plan_marker = '*2026-10-14 post hoc capture-value sensitivity:*'
assert entry.splitlines()[0] not in results
assert handoff_marker in handoff and plan_marker in plan
with (AUDIT / 'preregister_text.md').open('x') as stream:
    stream.write(entry)
results_path.write_text(results + '\n' + entry)
handoff_path.write_text(handoff.replace(handoff_marker, handoff_entry + handoff_marker, 1))
plan_path.write_text(plan.replace(plan_marker, plan_entry + plan_marker, 1))
