"""Run sim.study on every meas/*.npz without a simres/ file (or the given files), a few processes at a time."""
from __future__ import annotations

import json
import os
import sys
from multiprocessing import Pool
from pathlib import Path

os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")

HERE = Path(__file__).resolve().parent


def one(path: str) -> str:
    import sim

    p = Path(path)
    r = sim.study(p)
    (HERE / "simres" / f"{p.stem}.json").write_text(json.dumps({p.stem: r}))
    return p.stem


def main() -> None:
    (HERE / "simres").mkdir(exist_ok=True)
    force = "--force" in sys.argv
    paths = [a for a in sys.argv[1:] if a != "--force"] or sorted(str(p) for p in (HERE / "meas").glob("*.npz"))
    todo = [p for p in paths if force or not (HERE / "simres" / f"{Path(p).stem}.json").exists()]
    with Pool(int(os.environ.get("SIM_PROCS", "3"))) as pool:
        for name in pool.imap_unordered(one, todo):
            print("done", name, flush=True)


if __name__ == "__main__":
    main()
