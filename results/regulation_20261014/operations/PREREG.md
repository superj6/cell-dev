# O: local gene-regulatory inputs with cell composition held constant

Prepared after H's completed result, before any O life. H found that broad freeze removes
0.914 ± 0.214 F of D51090's gain over row38, while D51089's corresponding effect is unresolved.
Freeze stops gene/phenotype updates as well as division and death. O separates these processes using
existing ABI 3 interventions. Both original D endpoints remain fixed, regardless of their H outcomes.

## Fixed comparison

Use the exact row38 founder and D51089/D51090 generation 16 population-rank0 genomes archived by H.
All three share 512 fresh block101 seeds, 52,010,000 through 52,010,511, in each of three arms:

1. **Structure held fixed:** division_off + apoptosis_off. Genes, phenotypes, effective weights,
   neural activity and chemicals continue updating under their existing local rules.
2. **Structure held fixed plus genes_blind:** the same, but five inputs to the GRN are set to zero.
   These are the own-spike trace, two incoming-spike traces, contact-count fraction and receptor trace
   (ABI inputs 18 through 22). Current genes, morphogens and plane cues remain available. Receptor events
   still drive neurons and spike messages still travel.
3. **Freeze:** the existing broad freeze flag, matching H's interpretation.

All worlds use fast POOL, T1536, d0=0.5, d_min=0.25, sigma=0.4 and lam_s=4, with unchanged prices.
The fork begins at 768 and accounting opens at 800. Every condition/genotype/seed is retained, in fixed
condition order and then founder/D51089/D51090 order. There is no candidate selection or tuning.
Three genotypes × three conditions × 512 seeds gives **4,608 research genome-lives**.

The independently reviewed namespace receipt checks this block against the enumerated historical pilot,
D/G/L training and diagnostic seeds, prior declared measurement ranges, and the prospective M/N ranges.
The same O seeds are intentionally shared across all nine arms.

## Estimands

The two primary contrasts are each endpoint's added dependence on the five masked GRN inputs:

`(D − row38)structure − (D − row38)structure+genes_blind`.

Subtract within each seed before computing mean and sample SE across 512 seed clusters. Report both signs
and both endpoints, with descriptive positive/negative 3-SE flags and no endpoint selection. There is no
multiplicity-adjusted discovery claim and no estimate of reliability across evolutionary searches.

Secondary contrasts retain every arm's endpoint-minus-founder gain, each genotype's own input-mask loss,
and structure-minus-freeze effects and their endpoint-versus-founder interactions. Report capture income,
all costs, guard/extinction charges, clicks, path, terminal cells and hidden cells alongside fitness.

The input mask removes static contact information as well as activity traces. A loss therefore does not
by itself show adaptation, memory or use of changing evidence. The structure-minus-freeze contrast also
includes phenotype and effective-weight updates. Different genotypes retain different footprints and
pre-fork states; this is not a matched-footprint comparison or a test of a copied gene's function.

## Checks and resources

All inputs, source/numerical identity, helpers, protocol and monitor are pinned before release. The three
interventions share pre-fork events. The settling interval exceeds the existing bounded pending claim,
notice and spike delays; it does not erase their earlier effects. Every scored arm must have zero births
and deaths during 800..1536 and last birth before 800. Complete triplets within each genotype must have
equal total and per-plane counts, t_end=1536, and cell-time equal to 736 times terminal count.

Valid guarded/extinct lives retain their ordinary production penalties in all fitness estimates. Only
the constant-composition checks condition on complete triplets. Capacity/accounting implementation errors,
changed structure or incomplete coverage prevent completed inference; retain all partial evidence.

Use at most **two simulation workers**, CPUs 0–11, after both M and N are complete with empty queues.
The **3,600 CPU-second cap includes monitor/waiting CPU, worker descendants and startup validation**.
Stop at 3,588, then TERM and bounded KILL; install remaining-budget RLIMIT and exact parent-death binding.
No automatic reset, seed substitution or extension. Existing two T200 startup golden lives are validation
inside the CPU cap and outside the 4,608 research count. Preparation and mock tests simulate no lives.

All work stays in `outputs/autonomous_regulation_20261014/`; publish preparation and complete or incomplete
results under `results/regulation_20261014/`. No organism behavior, ABI, price or selection world changes.
