# Preparation wording correction

The preregistration, protocol and preparation describe fast event hashes as zero. The existing LIFE_FAST
kernel instead skips hash folds and leaves all five hash families at HASH_INIT, 0x243f6a8885a308d3.
Every recorded candidate-life hash has that constant value. Neither a constant initializer nor zero
contains event replay evidence. File SHA256 receipts continue to protect saved evidence.

This corrects a documentation error, with no change to a simulation, result, source pin or protocol choice.
The frozen preparation bytes and their validator remain intact under prelaunch/.
