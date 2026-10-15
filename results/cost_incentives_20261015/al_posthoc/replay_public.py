"""Run the unchanged post hoc accountant against the committed AL archive."""
import importlib.util
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = next(p for p in HERE.parents if (p / 'src/life/spec.py').is_file())
spec = importlib.util.spec_from_file_location('AL_cost_sensitivity', HERE / 'analyze.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
module.STUDY = ROOT / 'results/retention_selection_20261015'
module.HELPER = module.STUDY / 'evidence/terminal_review/verify_terminal_raw.py'
module.main()
