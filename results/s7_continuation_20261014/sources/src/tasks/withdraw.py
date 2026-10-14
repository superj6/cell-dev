"""Withdraw: a brief poke lands on one side of the body; the activity must end up on the OTHER side.

A poke is a small, hard-edged light spot on channel 0 (every site within ``poke_radius`` of the poke centre gets the
same level, the rest gets nothing) for 1-2 ticks, at a random onset, landing in a random direction u at distance
2-2.7 from the fabric centre (bodies grow around the centre). The target is -u: away from the poke.

The window has two parts, both with weight 1:
- the *rest* ticks: every tick before the poke. The tissue should be still, so spontaneous (tonic) firing there counts
  as symmetric firing and dilutes the score. The poke never comes before tick 11, and tick 10 is the latest a quantized
  cell can first fire spontaneously, so any cell that could fire after the poke without being driven by it is forced
  to show its tonic firing inside the scored rest ticks;
- the *response* ticks, starting ``delay`` ticks after poke onset (at least two ticks after the poke has ended),
  when a wave started at the poke has had time to reach the far side of a small body.

Why no single cell can solve it (messages off):
- the poke is all-or-nothing per site and every lit site sees it at the same tick, so a cell only knows *whether* it
  was poked; "fire where poked" scores negative, and a cell that is not tonic cannot fire at all once its own input
  has ended (its potential only decays), so poke responses cannot leak into the response ticks;
- the only way to put firing far from the poke without messages is tonic firing that the poke silences ("withdraw
  by subtraction"). Unpoked cells cannot know when the poke happened (the onset is random and there is no cue), so
  they also fire in the rest ticks and the subtraction is diluted; timer cells that fire once, late, would need to
  wait past tick 10, which no quantized rule can do silently. A red team (exhaustive over all 8448 quantized rules,
  then a local search over body layouts) found no message-free organism above 0.04 held-out with this window
  (0.22 when the rest window covered only the 6 ticks before the poke).
With messages, a relay wave from the poked cells crosses the body in a few ticks: a 19-cell disk of one relay type
scores about 0.8 in training (about 0.47 held-out, where closer pokes make its wave arrive early), and a 13-cell
C-shaped ring of relays on ring 2 around a silent centre about 0.73 held-out.

Held-out: unseen directions (halfway between training ones) and a wider range of poke distance (1.5-3.0), which
shifts which cells are poked and so when the wave arrives on the far side.
"""
from __future__ import annotations

import torch

from src.tasks.base import Task, Trials, angles, unit


class WithdrawTask(Task):
    name = "withdraw"
    rung_id = 11
    poke_radius, poke_level = 1.0, 2.0
    train_dist, heldout_dist = (2.0, 2.7), (1.5, 3.0)  # poke centre's distance from the fabric centre
    poke_ticks = (1, 2)  # poke duration range
    onset = (11, 16)  # poke onset range (inclusive); after tick 10, the latest first spontaneous spike
    delay, response = 4, 3  # response window: ticks [onset + delay, onset + delay + response)
    ticks = 23  # onset[1] + delay + response

    def sample(self, pos, n, gen, heldout=False) -> Trials:
        lo, hi = self.heldout_dist if heldout else self.train_dist
        u = unit(angles(n, gen, heldout))
        dist = lo + (hi - lo) * torch.rand(n, generator=gen)
        centre = dist[:, None] * u  # [E, 2]
        lit = ((pos[None] - centre[:, None]).norm(dim=-1) <= self.poke_radius + 1e-3).float()  # [E, N]
        t0 = torch.randint(self.onset[0], self.onset[1] + 1, (n, 1), generator=gen)
        length = torch.randint(self.poke_ticks[0], self.poke_ticks[1] + 1, (n, 1), generator=gen)
        t = torch.arange(self.ticks)[None]  # [1, T]
        on = (t >= t0) & (t < t0 + length)  # [E, T]
        stim, _ = self._empty(n, self.ticks, pos.shape[0])
        stim[..., 0] = self.poke_level * on[..., None].float() * lit[:, None]
        rest = t < t0  # every tick before the poke
        resp = (t >= t0 + self.delay) & (t < t0 + self.delay + self.response)
        return Trials(stim=stim, window=(rest | resp).float(), target=-u, rung=torch.full((n,), self.rung_id))
