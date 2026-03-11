from __future__ import annotations

from pathlib import Path
from typing import Any

from .semantic import checkpoint as _impl

CHECKPOINT_STAGES = _impl.CHECKPOINT_STAGES
consolidate_branch_memory = _impl.consolidate_branch_memory


def checkpoint_stage_memory(
    project_path: Path,
    branch_name: str,
    stage: str,
    summary: str,
    **kwargs: Any,
) -> dict[str, Any]:
    _impl.consolidate_branch_memory = consolidate_branch_memory
    return _impl.checkpoint_stage_memory(project_path, branch_name, stage, summary, **kwargs)
