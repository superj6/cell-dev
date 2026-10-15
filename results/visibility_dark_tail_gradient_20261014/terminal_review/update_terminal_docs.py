"""Apply the independently checked AG outcome to the current project narrative."""
from pathlib import Path
import hashlib
import json

AUDIT = Path(__file__).resolve().parent
ROOT = AUDIT.parents[1]
STUDY = ROOT / 'outputs/autonomous_visibility_dark_tail_gradient_20261014'
summary = STUDY / 'analysis_result/summary.json'
assert hashlib.sha256(summary.read_bytes()).hexdigest() == '0395a7f2e8f182b656b64298071d363252b1abc8d59c437a12d7e7740ce7db57'
assert json.loads(summary.read_text())['status'] == 'complete'

p = ROOT / 'RESULTS.md'
text = p.read_text()
entry = (AUDIT / 'terminal_text.md').read_text()
assert entry.splitlines()[0] not in text
p.write_text(text + '\n' + entry)

p = ROOT / 'docs/HANDOFF.md'
text = p.read_text()
marker = '**Wrap-up complete (2026-10-14).**'
entry = '''**AG complete (2026-10-14).** In dark flash, D90 row54 gains **+1.82930 ± .03953 F** with unresolved
capture change **+.04883 ± .06928**; cost savings supply +1.80546 F. L92 row61 gains **+.55148 ± .03692 F** and
**+.22070 ± .07114 captures**, narrowly beyond the fixed three-SE criterion. Its dark-phase gain
**+.20703 ± .06956** narrowly misses that criterion; cost savings (+.44372 F) exceed extra capture income
(+.10777 F). L92 mean captures rise 1.58984→1.81055, with mean F still negative. Each new target placement
starts a five-unit flash; target cues then vanish while background sensing continues. This is one modest
accessible capture gain, without memory, new-algorithm or evolutionary-repeatability evidence.
All 6,208 research plus ten startup calls complete in **1,204.022071 CPU-seconds**. All 6,216 raw ABI4 statuses
are zero; two identity goldens complete the count. Independent raw/full analysis reproduces all **132 paired
vectors**. Both leaders/one owned group exited; 232 local/35 production release pins remain unchanged.
Evidence: `results/visibility_dark_tail_gradient_20261014/`. Source-only AH now drafts one matched ordinary
versus two-slot exploratory-reserve pilot from AE L92 in the persistent-target world. The reserve changes
external selection only; prices, F and local rules stay fixed. No AH inputs, seeds, builds or lives are released.

'''
assert marker in text
p.write_text(text.replace(marker, entry + marker, 1))

p = ROOT / 'docs/TASK_VARIATION_PLAN.md'
text = p.read_text()
marker = '*2026-10-14 post hoc capture-value sensitivity:*'
entry = '''*2026-10-14 AG complete:* in fully dark flash, L92 row61 gains **+.22070 ± .07114 captures** and
**+.55148 ± .03692 F** on 512 fresh paired lives; cost savings (+.44372 F) provide most of the fitness gain.
Its dark-phase capture gain (+.20703 ± .06956) narrowly misses three SE. D90 row54 gains +1.82930 ± .03953 F
almost entirely through economy, with unresolved captures. A five-unit bright interval starts at each target
placement; background cues continue afterward. This is modest accessible adaptation without demonstrated
memory or a richer algorithm. All 6,218 calls complete in 1,204.022071 CPU-seconds; all 132 paired vectors and
raw accounting independently reproduce. Processes exited and release pins remain unchanged. Full evidence:
`results/visibility_dark_tail_gradient_20261014/`. A small source-only AH comparison now prepares ordinary
selection versus two temporarily protected fresh offspring in the existing persistent-target world. It tests
exploration under unchanged F and prices, not a new organism rule or reward, and is not yet registered or run.

'''
assert marker in text
p.write_text(text.replace(marker, entry + marker, 1))

p = ROOT / 'README.md'
text = p.read_text()
old = '''fitness score alone is insufficient evidence of a more sophisticated algorithm. A bounded test in fully dark
flash is being prepared, with prices and local asynchronous rules unchanged.'''
new = '''fitness score alone is insufficient evidence of a more sophisticated algorithm. The completed
[dark-flash test](results/visibility_dark_tail_gradient_20261014/TERMINAL_README.md) finds another modest capture
gain (**+0.221 ± 0.071 per life**) in one selected mutant, with most fitness improvement again coming from lower
costs. Dark-phase improvement is unresolved and memory remains unestablished. A small exploratory-selection
comparison is being prepared, with prices and local asynchronous rules unchanged.'''
assert old in text
p.write_text(text.replace(old, new, 1))
