# Next selection experiment, after the fixed endpoint

This updates the pre-outcome `NEXT_OPTIONS.md` without replacing it or registering a next protocol.

G8 patch fitness rose **0.596 ± 0.162 F**, of which **0.437 F (73%)** came from lower physical costs.
Patch capture gain was unresolved (**0.326 ± 0.329**); empty clicks increased **1.965 ± 0.298**.
POOL lost **1.861 ± 0.216** captures and reserved transfer lost **1.383 ± 0.268**, including
**0.930 ± 0.216** refill harvests. Transfer also declined from G4 to G8 (**0.857 ± 0.256** captures).
The POOL ratio is 88.4%, but its paired 90%-retention margin spans zero; the resolved finding is a
capture loss, not a demonstrated loss exceeding 10%. These are paired SEs over 512 lives, not search replicates.

**Recommend one matched four-generation, two-arm selection comparison from the entire G8 population.**
Compare current mean-F truncation with acquisition-aware Pareto survivor selection on four objectives:
mean captures in each of the three training domains, plus ordinary aggregate production F. Keep the
4/2/2 allocation, shared search seeds, 32+224 population structure, evaluation/recheck counts, operators,
worlds and physical prices fixed. Use the alternative rule for both the recheck shortlist and survivor
ranking; a mean-F-only shortlist would remove the variation the comparison is intended to preserve.
Two short arms have roughly the present search cost, avoiding a sequence of exposure and price sweeps.

The alternative gives useful partial acquisition improvements a chance to persist alongside economy.
It changes evolutionary selection, not an organism's actions or sensory inputs. Ordinary net fitness
remains an objective and an explicit reported consequence; this is an intentional acquisition/cost
tradeoff, not a claim that physical fitness alone now favors richer behavior.

Before implementation, specify one fixed compromise endpoint rule, such as the first Pareto-front
member maximizing its weakest training-domain capture ratio to fixed AO reference means, with ordinary
F and original order breaking ties. Apply the same prospective endpoint rule to both arms and retain
their native mean-F leaders in the saved search record, without substituting endpoints after confirmation.
The calibration uses completed development evidence; new confirmation seeds stay sealed. Confirm the
same individual across all five worlds, retaining AO as a reference; never select using transfer outcomes.

The main risk is preserving noisy specialists rather than one reusable organism: two old-domain lives
per initial evaluation are sparse, and Pareto diversity does not establish within-organism reuse.
This pilot would test local selection response, not search reliability. Report acquisition, refill food,
costs and net F together, including unfavorable outcomes. A positive result would justify deeper
continuation; a negative result would narrow the case for this selection rule.

I prefer this to immediate depth because the latest trajectory loses transferable food, and to another
exposure change because that mixes objective weighting with measurement precision. A renderer probe
can wait: there is no resolved new acquisition gain whose sensory dependence needs explaining first.
No next protocol, seed reservation, implementation or execution has been started.

Source: completed `summary.json` SHA256
`f819c039ddb9a8751148b73afb4bdb7445fe7a5ca2d755bf7118490b0598c554` and `TABLES.md`.
