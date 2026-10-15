"""Record independently checked AH outcomes without changing the frozen study."""
from pathlib import Path
import hashlib
import json

AUDIT = Path(__file__).resolve().parent
ROOT = AUDIT.parents[1]
STUDY = ROOT / 'outputs/autonomous_exploratory_reserve_20261014'
summary = STUDY / 'analysis_result/summary.json'
assert hashlib.sha256(summary.read_bytes()).hexdigest() == 'fc097ab9a104d0211351ab77bc88cce351dee8cba05f0f597c369de6d132aa26'
assert json.loads(summary.read_text())['status'] == 'complete'

p = ROOT / 'RESULTS.md'
text = p.read_text()
entry = (AUDIT / 'terminal_text.md').read_text()
assert entry.splitlines()[0] not in text
p.write_text(text + '\n' + entry)

p = ROOT / 'docs/HANDOFF.md'
text = p.read_text()
marker = '**Wrap-up complete (2026-10-14).**'
entry = '''**AH complete (2026-10-14).** One matched four-generation exploratory-reserve pair produces a relative
capture advantage: reserve minus ordinary control **+0.556641 ± 0.110184 captures** and
**+0.254917 ± 0.054269 F** on 512 fresh paired lives. Extra income (+0.271797 F) explains the advantage;
ordinary cost saving is −0.016880 F (unresolved). Reserve minus start captures **+0.337891 ± 0.115967**
narrowly misses three SE; control minus start is unresolved **−0.218750 ± 0.115289**. Both own-start F gains
are mostly economy. Mean terminal cells are about 109 at start and 61/60 at control/reserve endpoints.
All six protected offspring were outside their initial top64 and treatment pooled top32; both first256
candidate genomes/baseF and complete final populations replay exactly. This is one fixed-endpoint advantage,
not established search reliability, a necessary stepping stone, memory or a new algorithm. A separate post hoc
lineage check finds that the reserve winner descends from none of the six protected children; changed retention
can redirect later breeding without leaving protected ancestry in the winner.
All 9,804 research plus six golden calls finish in **862.767205 CPU-seconds**. All 1,536 confirmation statuses
are zero; native initial logs retain 12/18 guarded lives with penalties. All 219 paired vectors independently
reproduce. Four leaders/three groups exited; 208 local/35 production pins remain unchanged. Evidence:
`results/exploratory_reserve_20261014/`. Source-only AI now prepares one independent matched-pair replication
with the same AE L92 founder, policy, world and prices. No AI inputs, seeds, builds or lives are released.
A longer ordinary search after initial contraction remains deferred; no larger family or price change is authorized.

'''
assert marker in text
p.write_text(text.replace(marker, entry + marker, 1))

p = ROOT / 'docs/TASK_VARIATION_PLAN.md'
text = p.read_text()
marker = '*2026-10-14 post hoc capture-value sensitivity:*'
entry = '''*2026-10-14 AH complete:* the exploratory-reserve endpoint beats its matched ordinary-control endpoint by
**+0.556641 ± 0.110184 captures** and **+0.254917 ± 0.054269 F** on 512 fresh paired lives. Added capture income
explains that relative advantage. Its own-start capture gain (+0.337891 ± 0.115967) remains unresolved at three SE;
both own-start fitness gains are mainly economy. All six random protected offspring would miss their initial
ordinary top64 and treatment pooled top32. Exact first-cohort, full genetic/policy replay and independent raw
accounting pass, reproducing 219 vectors. All 9,810 calls complete in 862.767205 CPU-seconds; processes exited,
208/35 release pins unchanged. Evidence: `results/exploratory_reserve_20261014/`. The next source-only candidate,
AI, repeats the same matched comparison with an independent search seed and fresh confirmation. This follows a
positive pilot; it cannot treat 512 lives as evolutionary replicates or establish general reliability from one pair.
Task F, prices, world and organism rules remain fixed. No AI registration, scientific inputs or runtime release yet.

'''
assert marker in text
p.write_text(text.replace(marker, entry + marker, 1))

p = ROOT / 'README.md'
text = p.read_text()
old = '''costs. Dark-phase improvement is unresolved and memory remains unestablished. A small exploratory-selection
comparison is being prepared, with prices and local asynchronous rules unchanged.'''
new = '''costs. Dark-phase improvement is unresolved and memory remains unestablished. A subsequent
[selection pilot](results/exploratory_reserve_20261014/TERMINAL_README.md) briefly protected two randomly chosen
new offspring per generation. Its endpoint beats matched ordinary selection by **+0.557 ± 0.110 captures**
and **+0.255 ± 0.054 F**, chiefly through extra capture income. Its capture gain over the starting genome is
unresolved. This promising result comes from one search pair; an independent repeat is being prepared with the
same policy, prices and local asynchronous rules.'''
assert old in text
p.write_text(text.replace(old, new, 1))
