"""Record independently verified AI results; leave frozen study files untouched."""
from pathlib import Path
import hashlib
import json

AUDIT = Path(__file__).resolve().parent
ROOT = AUDIT.parents[1]
STUDY = ROOT / 'outputs/autonomous_exploratory_reserve_replication_20261014'
summary = STUDY / 'analysis_result/summary.json'
assert hashlib.sha256(summary.read_bytes()).hexdigest() == 'a070f5b95edd37d95fc8d6cc9a5a87203cac3edc65baf6f18105dc36ccc3f2f9'
assert json.loads(summary.read_text())['status'] == 'complete'

p = ROOT / 'RESULTS.md'
text = p.read_text()
entry = (AUDIT / 'terminal_text.md').read_text()
assert entry.splitlines()[0] not in text
p.write_text(text + '\n' + entry)

p = ROOT / 'docs/HANDOFF.md'
text = p.read_text()
start = text.index('**Current work (2026-10-15).**')
end = text.index('\n\n', start)
text = text[:start] + '''**Current work (2026-10-15).** AI is complete and independently verified: its reserve endpoint loses to
ordinary control by 0.514 ± 0.119 captures per life, reversing AH's advantage. There is no consistent reserve
benefit across the two pairs. AI ordinary control improves on its start by 0.695 ± 0.128 captures; most fitness
gain still comes from economy. Terminal publication and a watchable comparison are being completed. A longer
ordinary continuation is the next design candidate; it is not yet registered or released.''' + text[end:]
marker = '**Wrap-up complete (2026-10-14).**'
entry = '''**AI complete (2026-10-15).** The independent repeat reverses AH: reserve minus ordinary control is
**−0.513672 ± 0.119015 captures** and **−0.274444 ± 0.057401 F** on 512 fresh paired lives. Both losses exceed
three SE. The two pairs give no consistent reserve advantage; life-level uncertainty is not search reliability.
Ordinary control gains **+0.695313 ± 0.127998 captures** and **+1.477951 ± 0.063427 F** over its start; reserve's
own-start capture gain (+0.181641 ± 0.126883) is unresolved. Most own-start fitness gain remains ordinary cost
savings (+1.138443 / +1.114815 F). Mean captures are 4.027344 → 4.722656 / 4.208984 for start → control / reserve.
This is modest capture adaptation, without identified prediction, memory or a new algorithm.
All 9,804 research plus six golden calls complete in **1,068.361098 CPU-seconds**. All 1,536 confirmation statuses
are zero; native initial logs retain three guarded lives per arm with penalties. First cohorts, final populations,
all genetic/policy operations and all 219 paired vectors independently reproduce. Five of six protected children
missed the initial ordinary top64; all six missed their treatment pooled top32. Four leaders/three groups exited;
210 local/35 production pins remain unchanged. Evidence: `results/exploratory_reserve_replication_20261014/`.
A longer ordinary continuation is being assessed, with fixed prices and local rules; no new run is released.

'''
assert marker in text
p.write_text(text.replace(marker, entry + marker, 1))

p = ROOT / 'docs/TASK_VARIATION_PLAN.md'
text = p.read_text()
marker = '*2026-10-14 post hoc capture-value sensitivity:*'
entry = '''*2026-10-15 AI complete:* the unchanged reserve policy loses to its matched ordinary control by
**−0.513672 ± 0.119015 captures / −0.274444 ± 0.057401 F** on 512 fresh paired lives, reversing AH's result.
There is no consistent reserve-policy advantage across the two search pairs on this chosen background.
Ordinary control gains **+0.695313 ± 0.127998 captures** over its start; reserve's own-start capture gain is
unresolved. Both own-start F gains remain mainly economy. All 9,810 calls finish in 1,068.361098 CPU-seconds,
with 1,536 healthy confirmation ledgers, three native initial-search guards per arm and all 219 paired vectors
independently reproduced. Processes exited and release pins remain unchanged. Full evidence:
`results/exploratory_reserve_replication_20261014/`. A longer ordinary continuation is the next design candidate,
without changing prices or prescribing organism behavior. No new study is registered or released here, and
neither the capture gain nor these two search pairs establish a richer algorithm or broad search reliability.

'''
assert marker in text
p.write_text(text.replace(marker, entry + marker, 1))

p = ROOT / 'README.md'
text = p.read_text()
old = '''unresolved. This promising result comes from one search pair; an independent repeat is being prepared with the
same policy, prices and local asynchronous rules.'''
new = '''unresolved. An [independent repeat](results/exploratory_reserve_replication_20261014/TERMINAL_README.md)
reversed that advantage: reserve loses **0.514 ± 0.119 captures** to ordinary selection, so the two pairs give no
consistent policy benefit. Ordinary selection in the repeat gains **0.695 ± 0.128 captures** over its start,
although most of its fitness gain remains cost savings. Longer ordinary evolution is the next candidate;
prices and local asynchronous rules stay fixed.'''
assert old in text
p.write_text(text.replace(old, new, 1))
