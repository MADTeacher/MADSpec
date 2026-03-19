from __future__ import annotations

from pathlib import Path

import pytest

from tests.memory_runtime.support import MemoryProjectHarness, bootstrap_memory_project


@pytest.fixture()
def memory_project(tmp_path: Path) -> MemoryProjectHarness:
    return bootstrap_memory_project(tmp_path)

