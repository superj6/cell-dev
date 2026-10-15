from pathlib import Path
root=Path(__file__).resolve().parents[3]
audit=Path(__file__).resolve().parent
text=(audit/'preregister_text.md').read_text()
for name in ['RESULTS.md','results/taskvar/prereg.md']:
 p=root/name
 assert 'Persistent-target mutation accessibility registered (AE)' not in p.read_text()
 p.write_text(p.read_text().rstrip()+'\n\n'+text)
p=root/'docs/HANDOFF.md'
s=p.read_text()
needle='**Wrap-up complete (2026-10-14).**'
entry='''**AE registered and prepared (2026-10-14).** Both complete Y mutation panels now enter V's exact existing
fast persistent-target world (v_t=.3, tau_turn=200, continuous visibility, ABI3, T1024). Screen all 130 rows
on 32 shared fresh lives, select the best mutant per founder by production F, and confirm both selected mutants
and parents on 512 fresh paired lives. The 6,208 research plus ten validation calls have a 5,400 CPU-second
inclusive cap, with startup/screens capped at 3,400, confirmation reserve 2,000 and calibration ceiling 180;
one two-thread worker, first attempt only. Fresh seed blocks128/129/130 at base51M are audited and disjoint.
One-time preparation copied both entire panels and all 130 historical timings; independent replay reconstructs
all 130 genomes from 256 recorded point additions. Exact 66-field V packing and both configurations agree;
conduction remains d0=1/d_min=.5, as in Y. Protocol `0f5a591f…aa849` binds 167 local and 35 production files.
All 31 prior process identities and 22 groups are clear. The source review corrected a JSON dictionary-key
serialization mismatch before preparation; the scientific formulas and scope are unchanged. No AE builds or
lives ran during preparation. Prospective evidence: `results/prediction_gradient_20261014/`.
This tests accessible capture improvement versus economy; it cannot by itself establish prediction or general
evolvability, and it introduces no hand-built winning-body gate. Root runtime release follows publication.

'''
assert needle in s and '**AE registered and prepared' not in s
p.write_text(s.replace(needle,entry+needle))
p=root/'docs/TASK_VARIATION_PLAN.md';s=p.read_text()
needle='*2026-10-14 post hoc capture-value sensitivity:*'
entry='''*2026-10-14 AE registered and prepared:* the two complete retained Y panels are screened in V's exact
existing persistent-target world. Select one ordinary mutant per founder on 32 shared lives and confirm the
four fixed mutant/parent roles on 512 fresh lives, separating capture income from economy. Fixed scope is
6,208 research plus ten validation lives under 5,400 inclusive CPU-seconds, with 2,000 reserved for confirmation.
Exact genetic replay, V's ABI3 world packing, all 130 historical timing rows and fresh seed blocks128–130 pass
review. `results/prediction_gradient_20261014/` preserves prospective inputs; root release follows publication.
No preparation simulations ran. This is an accessibility diagnostic, without a prediction claim, world rejection
criterion or hand-built-body requirement; larger selection plans remain unreleased.

'''
assert needle in s and '*2026-10-14 AE registered and prepared:*' not in s
p.write_text(s.replace(needle,entry+needle))
