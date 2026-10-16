"""Task registry and the curriculum ladder (default: light -> brightness -> memory -> motion -> flicker).

A task named ``foo`` that is not listed here is looked up in ``src/tasks/foo.py`` (the Task subclass with name "foo"),
so new tasks work without touching this file.
"""
from __future__ import annotations

import importlib

import torch

from src.tasks.base import Task, Trials, concat
from src.tasks.brightness import BrightnessTask
from src.tasks.flicker import FlickerTask
from src.tasks.light import LightTask
from src.tasks.memory import MemoryTask
from src.tasks.motion import MotionTask

RUNGS = [LightTask, BrightnessTask, MemoryTask, MotionTask, FlickerTask]
BY_NAME = {cls.name: cls for cls in RUNGS}


class Ladder(Task):
    """Trains on the current rung while revisiting an earlier rung, so nothing is forgotten.

    Each sample has ``n`` trials of the current rung (balanced by its own sampler) plus ``round(n * keep_earlier)``
    extra trials, rounded up to an even number, from one randomly chosen earlier rung. Even counts keep the paired
    samplers (context's cued/uncued twins, jump's u/-u pairs) paired.
    """

    name = "ladder"

    def __init__(self, start: int = 0, keep_earlier: float = 0.25, length: float = 4.0, rungs=None):
        super().__init__(length)
        self.rungs = [task_class(r)(length) for r in rungs] if rungs else [cls(length) for cls in RUNGS]
        self.rung = start
        self.keep_earlier = keep_earlier

    @property
    def rung_id(self) -> int:
        return self.rung

    def advance(self) -> bool:
        if self.rung + 1 < len(self.rungs):
            self.rung += 1
            return True
        return False

    def sample(self, pos, n, gen, heldout=False) -> Trials:
        current = self.rungs[self.rung]
        n_old = round(n * self.keep_earlier)
        if heldout or self.rung == 0 or n_old == 0:
            return current.sample(pos, n, gen, heldout)
        n_old += n_old % 2
        earlier = self.rungs[int(torch.randint(0, self.rung, (1,), generator=gen))]
        return concat([current.sample(pos, n, gen), earlier.sample(pos, n_old, gen)])


def task_class(name: str) -> type[Task]:
    if name in BY_NAME:
        return BY_NAME[name]
    module = importlib.import_module(f"src.tasks.{name}")
    for obj in vars(module).values():
        if isinstance(obj, type) and issubclass(obj, Task) and getattr(obj, "name", None) == name:
            return obj
    raise ValueError(f"no Task named {name!r} in src/tasks/{name}.py")


def build_task(name: str, length: float = 4.0, start: int = 0, keep_earlier: float = 0.25, rungs=None) -> Task:
    if name == "ladder":
        return Ladder(start=start, keep_earlier=keep_earlier, length=length, rungs=list(rungs) if rungs else None)
    return task_class(name)(length)


__all__ = ["RUNGS", "Ladder", "Task", "Trials", "build_task", "task_class"]
