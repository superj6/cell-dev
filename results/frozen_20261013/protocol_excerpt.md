# E. Lateral dependence with tissue held fixed


- Fix original pilot s5 and the archived row38 mutant in POOL-fast, independent of B/D outcomes. Use the existing
  ABI-3 interventions only. Four conditions per genotype: normal, freeze, lateral_off, freeze+lateral_off.
  All lives have T1536, fork at768 and fitness accounting from800 to1536 (a736-unit window).
- The freeze stops further gene/phenotype updates and new division/death decisions. Membrane dynamics, receptor
  inputs, spikes and chemical transport continue. Lateral_off suppresses creation of new in-plane spike messages;
  already emitted messages still arrive. Vertical spikes continue. Neither intervention enters selection.
- A32-unit settling interval excludes pending pre-fork claims and spike deliveries from the measurement window;
  it does not erase earlier membrane, chemical, movement or world history. At these fixed settings claims resolve
  by768.25 and their notices by768.75; the bounded spike-delay formula puts pre-fork deliveries before771.003.
  Assert zero post-open births/deaths and last_birth<800 in frozen arms. For complete guard-free pairs, also assert
  equal final cell count between the two frozen arms and cell-time equal to736 times the constant cell count.
- Use512 common fresh block92 seeds for all eight arms:4,096 genome-lives. Preserve guard/extinction penalties and
  reject capacity/mismatch/corrupt or unexplained incomplete lives. Report structural checks and guard incidence.
- Primary contrast: `(winner-parent)freeze - (winner-parent)freeze+lateral_off`, paired per seed before mean/SE.
  Also report the analogous unfrozen interaction, all four winner-parent contrasts, their difference under freeze,
  each genotype's lateral loss, and gain lost under freeze. Report raw effects with descriptive3-SE signs; do not
  extend lives, replace genotypes or change the measurement window after scores. Keep all income/cost components.
- A positive primary contrast supports increased lateral dependence in tissue held fixed after this intervention.
  The genotypes' footprints differ, so it does not establish a new algorithm or matched-footprint information use.
  A loss of gain under freeze cannot by itself distinguish developmental benefit from computation by gene activity.
  End size, path, n_peak and last_birth remain whole-life descriptors; the F/capture/cost contrast uses800..1536.
- Cap this study at one CPU-hour with two workers, never exceeding four concurrent simulation workers across all
  studies. Save atomic rows, full production ledgers and source/numerical/genome pins under
  `outputs/autonomous_frozen_20261013/`. Archive and report both positive and negative results.
