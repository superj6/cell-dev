from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
AUDIT=Path(__file__).resolve().parent
p=ROOT/'RESULTS.md';text=p.read_text();entry=(AUDIT/'terminal_result_text.md').read_text()
assert entry.splitlines()[0] not in text;p.write_text(text+'\n'+entry)
p=ROOT/'docs/HANDOFF.md';text=p.read_text();marker='**Wrap-up complete (2026-10-14).**'
entry='''**AF complete (2026-10-14).** Both four-generation persistent-target continuations improve fitness through
cost savings, without further capture improvement. D90/L92 gain **+.73529 ± .06459 / +1.43758 ± .05065 F**;
captures change **−.34180 ± .13345 / −1.92969 ± .10146**, with only the L92 loss beyond three SE. Ordinary costs
save **+.90218 ± .01283 / +2.37981 ± .01221 F**. L92 mean captures halve from 3.85938 to 1.92969, terminal cells
fall from 108.96094 to 13.06250 and spikes from 2,517.89063 to 84.01563. This is economy, without demonstrated
prediction or a richer algorithm. All 10,316 research/diagnostic plus six golden lives complete in
**1,191.290362 CPU-seconds**; search uses 1,012.253396. Both final populations and recorded genetics replay;
independent raw/full analysis matches all **146 paired vectors** exactly. All 2,048 confirmation statuses are zero;
27 initial-search guarded lives retain penalties, with incomplete raw search-ledger coverage acknowledged.
Four process leaders/three groups exited; all 117 local/35 production pins remain unchanged. Evidence:
`results/prediction_continuation_20261014/`. Source-only AG prepares a bounded dark-flash mutation-accessibility
test instead of automatically extending these searches; no AG seeds, inputs, builds or lives are released.

'''
assert marker in text;p.write_text(text.replace(marker,entry+marker,1))
p=ROOT/'docs/TASK_VARIATION_PLAN.md';text=p.read_text();marker='*2026-10-14 post hoc capture-value sensitivity:*'
entry='''*2026-10-14 AF complete:* four more ordinary generations increase fitness but do not accumulate captures.
D90/L92 gain **+.73529 ± .06459 / +1.43758 ± .05065 F** through cost savings, while captures change
**−.34180 ± .13345 / −1.92969 ± .10146** on 512 fresh paired lives. L92 shrinks to a mean 13.06250 terminal
cells and halves mean captures; its loss exceeds three SE. All 10,322 calls complete in 1,191.290362 CPU-seconds;
all processes exit, genetics replay and independent full/raw analysis matches all 146 paired vectors. Evidence:
`results/prediction_continuation_20261014/`. These are economy gains, not richer computation. Source-only AG
prepares one fully dark flash accessibility test using complete retained Y panels, unchanged prices and AD's
measured information payoff. It is unregistered and unreleased; no hand-built-body or local-success world gate.

'''
assert marker in text;p.write_text(text.replace(marker,entry+marker,1))
p=ROOT/'README.md';text=p.read_text()
text=text.replace('The current research batch is closed. A further pair of searches finished, but fresh confirmation hit its fixed',
                  'That earlier research batch is closed. A further pair of searches finished, but fresh confirmation hit its fixed',1)
marker='Read the [continuation results](results/continuation_20261013/README.md),'
entry='''The resumed work now includes approved flash/blink environments and a faster persistent target. Nearby ordinary
mutants have produced small capture gains, but short continuations have mostly improved economy. In the latest
[persistent-target continuation](results/prediction_continuation_20261014/TERMINAL_README.md), both lineages gain
fitness without gaining captures; L92 halves its mean captures while shrinking from about 109 to 13 terminal
cells. This makes capture performance and richer use of information the central research questions; a higher
fitness score alone is insufficient evidence of a more sophisticated algorithm. A bounded test in fully dark
flash is being prepared, with prices and local asynchronous rules unchanged.

'''
assert marker in text;p.write_text(text.replace(marker,entry+marker,1))
