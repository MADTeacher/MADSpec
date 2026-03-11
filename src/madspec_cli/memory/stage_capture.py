from __future__ import annotations

from pathlib import Path
from typing import Any

from .semantic import capture as _impl

CAPTURE_STAGES = _impl.CAPTURE_STAGES
consolidate_branch_memory = _impl.consolidate_branch_memory


def capture_stage_memory(
    project_path: Path,
    branch_name: str,
    stage: str,
    **kwargs: Any,
) -> dict[str, Any]:
    _impl.consolidate_branch_memory = consolidate_branch_memory
    return _impl.capture_stage_memory(project_path, branch_name, stage, **kwargs)
