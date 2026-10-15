from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
AUDIT=Path(__file__).resolve().parent
p=ROOT/'RESULTS.md';text=p.read_text();entry=(AUDIT/'preregister_text.md').read_text()
assert entry.splitlines()[0] not in text;p.write_text(text+'\n'+entry)
p=ROOT/'docs/HANDOFF.md';text=p.read_text();marker='**Wrap-up complete (2026-10-14).**'
entry='''**AG registered and prepared (2026-10-14).** Both complete retained Y panels enter AD's exact fully dark
flash ABI4 world: target cues end after five time units, while background sensing continues. Screen all 130 rows
on 32 shared lives; freeze both highest-F mutant rows, then confirm them and both parents on 512 fresh paired
lives. Report captures and native dark captures alongside capture income, costs and penalties; neither fitness
nor dark captures alone establish memory or a new algorithm. The 6,208 research plus ten startup calls have a
5,400 CPU-second cap, startup/screens at 3,400, confirmation reserve 2,000 and calibration ceiling 180, with one
two-thread worker. All 130 AC timing rows supply historical floors; actual fixed calibration must support the
unchanged scope before screening. Fresh blocks 132/133/134 and all 38 prior identities/27 groups/thirteen budgets
are clear. One-time retained-input copying is complete; protocol `ff9af8c7…a7955f` pins 170 local/35 production
files and exact 70-field world packing. No new genetics, builds or lives ran in preparation. Actual-input/reader
review, prospective publication and root release precede measurement. Evidence:
`results/visibility_dark_tail_gradient_20261014/`. Prices and local rules remain fixed; no automatic larger rollout.

'''
assert marker in text;p.write_text(text.replace(marker,entry+marker,1))
p=ROOT/'docs/TASK_VARIATION_PLAN.md';text=p.read_text();marker='*2026-10-14 post hoc capture-value sensitivity:*'
entry='''*2026-10-14 AG registered and prepared:* all 130 retained Y parent/mutant rows now enter AD's exact fully
dark flash world. Select one mutant per founder on 32 shared screen lives, freeze both, then confirm four roles
on 512 fresh paired lives. Captures and dark-phase captures accompany production fitness and cost accounting;
coasting and delayed signals remain alternatives to memory. The fixed 6,218 calls have a 5,400 CPU-second ceiling,
with 2,000 reserved for confirmation and a 180-second startup/calibration limit. All 130 AC timing rows, both
complete panels and fresh seed blocks 132–134 are retained. Protocol `ff9af8c7…a7955f` pins 170 local/35 production
files. No preparation builds or lives ran; independent actual-input/reader review, prospective publication and root
release precede measurement. `results/visibility_dark_tail_gradient_20261014/` preserves this bounded accessibility
test, with unchanged prices and local rules and no hand-built-body or local-success world gate.

'''
assert marker in text;p.write_text(text.replace(marker,entry+marker,1))
