"""Rung 2, any brightness: face the light while overall brightness varies 25x between trials.

"Fire where lit" now saturates in bright trials and goes silent in dim ones, so cells must compare themselves with
their neighbours (contrast by lateral inhibition, as in the retina).
"""
from __future__ import annotations

from src.tasks.base import log_uniform
from src.tasks.light import LightTask


class BrightnessTask(LightTask):
    name = "brightness"
    rung_id = 1
    train_range, heldout_range = (0.2, 5.0), (0.1, 10.0)

    def brightness(self, n, gen, heldout):
        lo, hi = self.heldout_range if heldout else self.train_range
        return log_uniform(n, lo, hi, gen)
