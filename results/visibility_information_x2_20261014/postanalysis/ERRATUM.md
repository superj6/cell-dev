# Postanalysis accounting correction

The preregistered offline analyzer rejected the first complete X2 validation ledger before returning scientific outcomes. Its census checks incorrectly counted the supplied initial cells as births. The synthetic fixtures repeated that assumption, so the prelaunch tests did not detect it. The original analyzer, tests, ready marker, protocol and raw records remain unchanged.

The pinned C implementation gives initial birth records `u3 = (init_index >= 0)`. Every birth record increments the cell census, but `acc_record` increments the `births` ledger only when `!r->u3`. Thus these fixed, static candidates must have **zero recorded births**, and their supplied initial count plus subsequent births minus deaths and kills equals the final count. The corrected analyzer retains the original fixed footprint and cell-time checks and rejects any birth, death, kill, claim or rejected division.

The source audit also found two unsupported inequalities in the original accountant. `rejects` and `rejects_wall` count different resolution outcomes. Likewise `arrivals` counts delivered spike arrivals and `arrivals_dropped` counts undelivered arrivals. Neither second counter is a subset of the first. Those inequalities are removed; both counters still must be finite, integral and nonnegative, and all fixed-body rejection counters still must be zero.

No fitness, price, contrast, seed, candidate, world, selection criterion, resource threshold or completeness requirement changes. The raw score remains `(income − ordinary costs − guard charge) / window`, without an additional extinction penalty for this static information study. Unexpected extinction and guards still invalidate a complete verdict. Scratch columns 21/22 remain explicitly labelled dark/late captures.

The regression fixture is the first blink R0 validation life named in the original failure, `validation/blink20_R0_0_scratch.npz`, SHA256 `d069c9022e83ee215433ffb092d9b2dfde4b84d4f83afdc3ea43299489d80248`. It has 56 initial and final cells, zero births and zero deaths. It was selected to reproduce the implementation error, before inspecting research outcomes. No simulation, recompilation, new seed or research retry is involved.

Corrected files are separate from the released `analysis/` bundle. Review receipts and the exact diff document this postanalysis correction. Full scientific analysis is permitted only after the corrected source, regression tests and independent validation-only review pass.
