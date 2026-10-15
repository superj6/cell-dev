"""Re-score the SAVED controllers and knobs (no re-tuning) on any seed block:

    cd /home/jgon/project/ml/cell-dev && PYTHONPATH=.:outputs/openhr/harness:outputs/openhr/memory \
        .venv/bin/python outputs/openhr/memory/rescore.py --block 119 --n 512 --n2 256 [--worlds blink20,blink5_5] \
        [--threads 2]

For every world it runs t6_score.py on fresh_seeds(n, 43_000_000 + 10_000 * block) with
  - the reflex candidates: frozen reflex@hollow3 and memory/reflex_knobs_mem.json 'rt-mem' (best of the two);
  - C1 / M1 (privileged ceiling and its memory decomposition);
  - C5 with tuned/<world>_ring4.json on ring4 / disk4x4 / ring5 / hollow3, and its memory ablations
    (tuned/<world>_ring4_nodark.json when present);
  - the do-less reflex variants;
writing scores/<world>_b<block>.json, then results_b<block>.json via t7_summarize.py --tag _b<block>.
(--block 100 rewrites the main scores and results.json; rows already stored are not re-run.)"""
import argparse
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ap = argparse.ArgumentParser()
ap.add_argument("--block", type=int, required=True)
ap.add_argument("--n", type=int, default=512)
ap.add_argument("--n2", type=int, default=256)
ap.add_argument("--worlds", default="blink20_10,blink20,blink10_30,blink5_5,flash5_dim25,pool_blink20,base1")
ap.add_argument("--threads", type=int, default=2)
a = ap.parse_args()
env = dict(os.environ)
env["PYTHONPATH"] = os.pathsep.join([os.getcwd(), os.path.join(os.path.dirname(HERE), "harness"), HERE,
                                     env.get("PYTHONPATH", "")])
for wn in a.worlds.split(","):
    subprocess.run([sys.executable, os.path.join(HERE, "t6_score.py"), wn, "--n", str(a.n), "--n2", str(a.n2),
                    "--threads", str(a.threads), "--block", str(a.block)], check=True, env=env)
tag = "" if a.block == 100 else f"_b{a.block}"
subprocess.run([sys.executable, os.path.join(HERE, "t7_summarize.py"), "--tag", tag], check=True, env=env)
