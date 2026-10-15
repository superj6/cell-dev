# Ordinary mutation in irregular blink: concrete plan, not a release

Prefer one irregular-blink pilot after the complete X2 information-payoff review. The question is whether ordinary mutations around already improved evolved bodies can buy more captures when target cues disappear. X2 supplies evidence about useful sensory information; this pilot supplies evidence about what mutation can reach. No constructed body or evolved founder must win before the world can be studied. No result here identifies a memory algorithm by itself.

The exact founders are now extracted under `founders/D90/` and `founders/L92/` as `genome.npy`, loadable `parent.json`, and unchanged source `config.yaml`. The extraction checks both archive labels and confirmation hashes, authenticates the ordered JSON field shapes against the archived ancestor, and proves float32 JSON round-trip equality. It imports no engine modules and generates no mutants.

| Founder | Confirmed source | Raw float32 SHA256 |
|---|---|---|
| D90 | `results/continuation_20261013/confirmation/genotypes.npz`, row 3, `s51090_final_rank0` | `1287ee4421f88fc108c073eae282f625bd0e340a5e4b12d590cd27cbc046bfac` |
| L92 | `results/s7_continuation_20261014/confirmation/genotypes.npz`, row 3, `s51892_final_rank0` | `8f14c79b8bea73c08dff7f6bc1094dc848534f9f2d45598c99c4351cf364cf27` |

These are confirmed final rank-zero genomes, not historical `best_genome.json` files. Both retain the unchanged 875-value BODY genome layout. `founders/manifest.json` pins source archives, field shapes, original configs, and extracted bytes.

Use exactly `catch_speck_blink20_20_l4`, T1024, from the frozen production world in X2. Its visibility tuple is `(2,20,20,0)`: irregular bright and dark intervals with mean duration 20 each. The world uses d0=1, d_min=.5, sigma=.6 and lam_s=2. Preserve all prices and other physical fields. `approved_blink_world.json` contains the entire world and ABI sizes `[4,875,129,70,58,5,23,1024,7,18]`, pinned to X2's protocol. Do not inherit the founders' old fast-conduction/POOL overrides.

After reviewed registration, call the existing `scripts/taskvar_gradient.py:make_mutants` once per founder: 64 ordinary mutants, n_mut=2, p_cell=.5, scaled mutation count, no duplication, deletion or split. Freeze all 65 rows and every recorded mutation operation before any scores. Preserve duplicate or no-op rows. Mutation RNG suggestions are D90=53117 and L92=53118; these are not reserved.

| Stage | Fixed work | Genome-lives |
|---|---|---:|
| Screen | Two backgrounds × 65 rows × 32 shared fresh seeds | 4,160 |
| Confirmation | Each selected mutant and its parent × 512 new shared seeds | 2,048 |
| Validation | Existing full/fast T200 numerical goldens once, plus eight fixed T1024 cost-calibration lives | 10 |
| Total | One world, one duration, no rescore | 6,218 |

Choose the largest whole screen mean production F among mutant rows 1–64, breaking exact ties by row number. Freeze both winners before either confirmation. Confirm the winner even when its screen mean is below its parent. Retain the full screen and negative or null confirmation effects. The 32-life screen can select noise; fresh confirmation estimates its consequence and does not establish that the best accessible mutation was found.

Suggested namespaces are block117 for screening (`52,170,000..52,170,031`), block118 for confirmation (`52,180,000..52,180,511`), and block119's first two IDs for calibration (`52,190,000..52,190,001`), using base51,000,000 and stride10,000. A read-only numeric scan covered43,224 JSON files and53,574 NPZ files, including7,666 seed arrays. Its480 numeric matches were all independently verified as the exclusive upper endpoint of old block116, not consumed seeds or overlapping intervals. No actual seed overlap was found. This live suggestion scan does not reserve anything; final text-formula and closed-study inventory review must precede registration. The numerical golden seed11 is deliberate replay, not fresh scientific evidence.

The implementation should be a small study-local adaptation of I, not a new framework:

- Reuse `make_mutants` unchanged. Do not call its old `run_screen`, which constructs the wrong world and explicitly uses V3.
- Copy I's orchestration and the existing `score_row`/`RowStore` helpers locally. Remove the top-four rescore stage. Change every V3 packing, run, `Lives`, and 57-column assumption to explicit V4/58 columns. The old `RowStore` imports the old scorer and column tuple directly, so it must explicitly bind the local replacements.
- Build derived configs from the archived originals with `life.abi=4`, the blink preset, T1024, no T choices or world/cost overrides, and `threads=2`. Keep `life.extinct_charge=true`. Verify the complete evaluator world equals the pinned snapshot before calls. Keep original configs unchanged.
- Preserve raw float64 `[lives,58]` ledgers, all production columns, explicit seeds and genome index, row timing and integrity receipts. Saved `F` is production-scored; raw ledger F and `F_kernel` retain kernel scoring. Append low-light and derived bright-capture diagnostics without adding a reward.
- Reuse the reviewed monitor's process identity, process-group cleanup and inclusive CPU accounting. A single two-thread measurement child performs the work. `RowStore`'s per-parent CPU checks cannot enforce an aggregate phase budget.

Propose a **5,400 CPU-second inclusive cap**, with startup, calibration and both screens stopped at3,400, preserving at least2,000 for confirmation and cleanup. Use a ten-second monitor stopping margin. Compilation, numerical goldens, failures and cleanup count. No automatic retry, resume, scope reduction or cap extension is part of this plan.

Calibration is four two-seed batches: parent and predetermined first mutant for each background, all at T1024. For each background let r be the larger of the two batch CPU times divided by two. Before screening, require measured startup/calibration CPU plus `1.5 × 2080 × sum(r)` to fit3,400, and `1.5 × 1024 × sum(r)` to fit2,000. Otherwise preserve an incomplete attempt for review. This is a fixed planning rule, not a runtime guarantee: unsampled mutations or a selected winner can be much slower, and the monitor must still stop incomplete at the hard phase/total limits. Calibration cannot alter the candidates, sample sizes or world.

Historical T1024 fast-POOL parent rates were .3174 CPU/life for D90 and .1791 for L92; applying those rates to this design gives about1,541 CPU-seconds. I's original s5/s7 screens plus corresponding four parent/winner confirmation rows cost1,749 CPU-seconds. Both are historical planning baselines, not visibility calibration. The original row paths and hashes are pinned in `concrete_plan.json`.

For each background separately, report the fresh paired mutant-minus-parent F mean, SE and n512. Reconcile capture income, every ordinary cost saving, guard charges and extinction charges with that effect. Also report captures, low-light captures, bright captures, cell-time, end/hidden cell counts, spikes, packets, clicks, path and health. Preserve natural death and valid guard-ended lives with the existing production penalties; implementation failures or unexplained incomplete lives block a complete verdict. Do not apply X2's static-controller no-extinction assumption to growing mutant bodies.

A confirmed gain that earns extra captures, especially low-light captures, would motivate a short ordinary evolutionary continuation. A gain explained by lower costs is useful evidence about accessible mutation directions, but weaker progress toward the user's goal. Neither low-light captures nor a fitness gain alone distinguishes memory from persistent motion or chance encounters. Flash, other durations, and mechanistic lesions remain separate later decisions.

Current status: exact old founders extracted; source and world references pinned; numeric seed suggestions reviewed. No engine call, compilation, mutant generation, seed reservation or research release occurred. The next steps are complete-X2 review, reviewed registration, one panel generation, the narrow local adapter, focused checks, and a concrete bounded-run report.
