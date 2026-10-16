"""Bounded pure-array pytest command; no life/backend imports or RNG calls."""
import os
import resource
import runpy
import sys
from pathlib import Path

available_kib = next(int(line.split()[1]) for line in Path("/proc/meminfo").read_text().splitlines()
                     if line.startswith("MemAvailable:"))
if available_kib < 4 * 1024 * 1024:
    raise SystemExit("host available memory below 4 GiB floor")
os.sched_setaffinity(0, {min(os.sched_getaffinity(0))})
resource.setrlimit(resource.RLIMIT_CPU, (30, 30))
resource.setrlimit(resource.RLIMIT_AS, (1024**3, 1024**3))
sys.argv = ["pytest", "-q", "-p", "no:cacheprovider", "outputs/resource_patch_selection_20261015/tests/test_pareto.py"]
runpy.run_module("pytest", run_name="__main__")
