from __future__ import annotations

import shutil
import sys
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"

if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

sys.dont_write_bytecode = True

for pycache_dir in SRC_ROOT.rglob("__pycache__"):
    shutil.rmtree(pycache_dir, ignore_errors=True)


@pytest.fixture()
def repo_root() -> Path:
    return REPO_ROOT
