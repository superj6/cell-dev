import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.common import load_config  # noqa: E402


@pytest.fixture
def smoke_cfg():
    return load_config(str(ROOT / "configs/local_smoke.yaml"))
