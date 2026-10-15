from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
AUDIT=Path(__file__).resolve().parent
p=ROOT/'RESULTS.md'
text=p.read_text()
entry=(AUDIT/'preregister_text.md').read_text()
assert entry.splitlines()[0] not in text
p.write_text(text+'\n'+entry)
p=ROOT/'docs/HANDOFF.md';text=p.read_text()
marker='**Wrap-up complete (2026-10-14).**'
assert marker in text
entry='''**AF registered and prepared (2026-10-14).** Two ordinary four-generation searches retain both fixed AE
selections, D90 row54 and L92 row31, in the exact V/AE ABI3 persistent-target world. Each uses native 32+224
selection with 3+4 lives and one recorded 32-row initialization. Freeze both final rank-zero endpoints, then
confirm endpoints and starts together on 512 fresh lives. The scope is 8,268 native search/diagnostic plus 2,048
confirmation lives and six goldens, under 5,400 inclusive CPU-seconds; startup/search cap 3,400 preserves 2,000
for confirmation. Two two-thread searches precede one two-thread confirmation worker. Six AE timing rows
project 2,365.459/992.014 CPU-seconds with fixed margins; hard caps remain decisive. Runs 53224/53225 and
confirmation 52,310,000–52,310,511 are audited; all 34 prior process identities, 24 groups and twelve budgets are clear.
One-time input copying and both ordinary initializations are complete; no builds or lives ran in preparation.
Protocol `ebdc3f37…15b5e0` pins 50 local/35 production files. Independent actual-input/reader review and prospective
publication precede root release. Both capture contrasts and full cost decomposition are retained; no prediction,
memory or general reliability claim follows. Prices and local rules remain fixed. Evidence:
`results/prediction_continuation_20261014/`. First attempt only, no retry/resume or extension.

'''
p.write_text(text.replace(marker,entry+marker,1))
p=ROOT/'docs/TASK_VARIATION_PLAN.md';text=p.read_text()
marker='*2026-10-14 post hoc capture-value sensitivity:*'
assert marker in text
entry='''*2026-10-14 AF registered and prepared:* four ordinary generations from both fixed AE selections test whether
capture improvements accumulate in the exact existing persistent-target world. Both final rank-zero endpoints
and both starts receive 512 fresh paired lives, with capture income separated from economy. The fixed 10,322 calls
include six startup goldens and fit a 5,400 CPU-second ceiling, with 3,400 for startup/search and 2,000 reserved
for confirmation. Two two-thread searches precede one two-thread confirmation worker. Audited runs 53224/53225,
fresh confirmation block131, recorded initial populations and six exact AE timing rows are frozen. No builds or
lives occur during preparation; independent input/reader review, prospective publication and root release precede
measurement. `results/prediction_continuation_20261014/` preserves the contract. Prices, ABI3 and local rules
remain fixed, with no large rollout or claim of algorithmic sophistication.

'''
p.write_text(text.replace(marker,entry+marker,1))
