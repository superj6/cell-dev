"""Jump (apparent motion): a small spot flashes at A, then an identical spot flashes at B; point the way it jumped.

A = c - (d/2) u and B = c + (d/2) u, where c is uniform in a disk of radius 1 around the fabric centre, d is the jump
length and u (the target) is a balanced direction. Each flash is a hard-edged spot (every site within 1.0 of the flash
point gets the same level; d > 2, so no site gets both flashes) lasting 2 ticks. B's onset comes D ticks after A's.

The window counts only these ticks, all with weight 1:
- *rest*: the 11 ticks before A's onset (the tissue should be still; tonic firing there only dilutes the score);
- each flash's *onset* tick, and the tick D ticks after each onset: {t0, t0+D, t0+2D}. Both flashes are therefore
  read at the same two latencies, 0 and D (A's latency 2D is the only extra tick).
Trials come in pairs inside every block of 12: directions u and -u share c, d, D and the onset, so the pair flashes the
same two spots in opposite orders (a block cut short, e.g. on a ladder, keeps whole pairs).

Why it needs messages (information has to travel from A's neighbourhood to B's):
- A cell sees at most one flash, and its response depends only on its own rule, its own position and when the flash
  came. If a tissue's response to each flash ignores the other flash (any tissue with messages off; with messages on,
  any tissue in which one flash's activity never reaches the other flash's cells) and does not depend on the clock,
  the two trials of a pair count the same spikes with opposite targets and cancel exactly. "Fire where lit" scores
  exactly 0, and so do local echoes at any latency, edge effects of the body and unequal spot shapes.
- A non-tonic cell cannot fire once its own input has ended (its potential only decays), so its response to a flash
  falls inside the flash's two ticks.
- Clocks. B always comes D ticks after A, so a tissue whose readiness to fire at an onset depends on absolute time
  (time since the trial started) can tell them apart without any A-to-B traffic. Whatever that clock is, it can only
  split a pair of onsets t0 < t0 + D in the trials where its readiness changes between them; summed over a uniform
  onset range of W ticks, the net gain telescopes to at most D/W of the trials. So D is short and the onset range
  wide: D = 3 with W = 22 (onsets 12-33) in training, D = 4 with W = 20 (onsets 12-31) held-out. A perfect clock
  (every lit body cell fires on its onset tick iff the onset comes after a chosen tick) scores about 0.14 train /
  0.20 held-out; the best real clock found (an unlit tonic cell at the body centre priming a ring of senders that
  emit nothing) about 0.13, and the 7-cell version that scored 0.50 held-out when onsets were 15-22 and D = 5-6 now
  scores 0.03 held-out / 0.09 train. A single cell's own clock is its potential settling from 0 at the start of the
  trial: non-tonic ramps have settled before tick 12, and tonic cells fire in the rest ticks (the best single-type
  tissue with messages off scores 0.07).
- The light level 2.1 is not a multiple of 1/8, so a lit cell's onset potential never settles exactly at threshold
  (at level 2.0 float32 rounding flipped a leak-1/2 cell to firing at late onsets only: a hidden clock).
- A relay wave from the first flash that crosses a small body and sits on the far side at B's onset ("withdraw from
  A") is cancelled by the second flash's wave at latency D, unless the first wave reaches B and blocks it, which is
  again an interaction between the flashes.

A Reichardt-style solution: lit "sender" cells (gain 3/8) fire on the flash's second tick, which is never counted;
relay cells pass that spike on once, and the relayed spike primes cells up to 2 hops away (a slow leak holds the prime).
At B's onset, primed lit cells cross threshold on the first tick, which is counted; at A's onset nothing has primed
them yet. A 19-cell disk of senders with relays on one sublattice scores about 0.69 train / 0.67 held-out and 0
without messages, and its score vanishes when its responses to A alone and B alone are added (see
tests/test_task_jump.py).

Held-out: unseen directions (halfway between training ones) and a longer gap (D = 4 instead of 3), so the prime has to
be held longer.
"""
from __future__ import annotations

import math

import torch

from src.tasks.base import ANGLES, Task, Trials, angles, unit


def paired_angles(n: int, gen: torch.Generator, heldout: bool = False) -> torch.Tensor:
    """``angles``, each block of 12 reordered so u and -u sit side by side (a cut-off last block keeps whole pairs)."""
    theta = angles(math.ceil(n / ANGLES) * ANGLES, gen, heldout)
    axis = torch.round(theta / (2 * math.pi / ANGLES) - (0.5 if heldout else 0.0)).long() % (ANGLES // 2)
    order = []
    for b in range(0, len(theta), ANGLES):
        first = {}
        for i, a in enumerate(axis[b:b + ANGLES].tolist()):
            first.setdefault(a, i)
        order += sorted(range(b, b + ANGLES), key=lambda i: (first[int(axis[i])], i))
    return theta[order][:n]


class JumpTask(Task):
    name = "jump"
    rung_id = 12
    spot_radius, level, flash = 1.0, 2.1, 2  # hard-edged spot of `level` on channel 0 for `flash` ticks
    centre_radius = 1.0  # c (the jump's midpoint) is uniform in this disk around the fabric centre
    train_dist, heldout_dist = (2.2, 2.6), (2.2, 2.6)  # jump length d (> 2 * spot_radius: spots never overlap)
    train_gaps, heldout_gaps = (3,), (4,)  # D: ticks from A's onset to B's onset
    train_onset, heldout_onset = (12, 33), (12, 31)  # A's onset range (inclusive); wide, so time says little
    rest = 11  # window ticks just before A's onset

    @property
    def ticks(self) -> int:  # the last window tick is t0 + 2D
        last = [self.train_onset[1] + 2 * max(self.train_gaps), self.heldout_onset[1] + 2 * max(self.heldout_gaps)]
        return max(last) + 1

    def sample(self, pos, n, gen, heldout=False) -> Trials:
        theta = paired_angles(n, gen, heldout)
        u = unit(theta)
        # trials with direction index k and k + 6 in the same block of 12 share one draw of c, d, D and onset
        k = torch.round(theta / (2 * math.pi / ANGLES) - (0.5 if heldout else 0.0)).long() % ANGLES
        key = (torch.arange(n) // ANGLES) * (ANGLES // 2) + k % (ANGLES // 2)
        m = int(key.max()) + 1
        lo, hi = self.heldout_dist if heldout else self.train_dist
        gaps = torch.tensor(self.heldout_gaps if heldout else self.train_gaps)
        first, last = self.heldout_onset if heldout else self.train_onset
        rad = self.centre_radius * torch.sqrt(torch.rand(m, generator=gen))
        phi = 2 * math.pi * torch.rand(m, generator=gen)
        c = torch.stack([rad * torch.cos(phi), rad * torch.sin(phi)], -1)[key]  # [E, 2]
        d = (lo + (hi - lo) * torch.rand(m, generator=gen))[key]
        gap = gaps[torch.randint(len(gaps), (m,), generator=gen)][key, None]  # [E, 1]
        t0 = torch.randint(first, last + 1, (m,), generator=gen)[key, None]

        def spot(centre):  # [E, N] sites lit by a flash at `centre`
            return ((pos[None] - centre[:, None]).norm(dim=-1) <= self.spot_radius + 1e-3).float()

        t = torch.arange(self.ticks)[None]  # [1, T]
        on_a = ((t >= t0) & (t < t0 + self.flash)).float()  # [E, T]
        on_b = ((t >= t0 + gap) & (t < t0 + gap + self.flash)).float()
        stim, _ = self._empty(n, self.ticks, pos.shape[0])
        stim[..., 0] = self.level * (on_a[..., None] * spot(c - 0.5 * d[:, None] * u)[:, None]
                                     + on_b[..., None] * spot(c + 0.5 * d[:, None] * u)[:, None])
        rest = (t >= t0 - self.rest) & (t < t0)
        read = (t == t0) | (t == t0 + gap) | (t == t0 + 2 * gap)
        return Trials(stim=stim, window=(rest | read).float(), target=u, rung=torch.full((n,), self.rung_id))
