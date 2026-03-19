from __future__ import annotations

import json
from pathlib import Path

from madspec_cli.memory.shared.storage import get_memory_paths

from .shared import build_gate


def build_ratification_gate(*, project_path: Path, branch_name: str, stage: str) -> dict[str, object]:
    paths = get_memory_paths(project_path, branch_name)
    decision_log_path = paths.decision_log
    ratified = False
    if decision_log_path.exists():
        for line in decision_log_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                payload = json.loads(line)
            except Exception:
                continue
            if (
                payload.get("stage") == stage
                and payload.get("record_type") == "checkpoint"
                and payload.get("status") == "validated"
            ):
                ratified = True
    return build_gate(
        family="stage_ratification",
        scope="stage",
        subject_id=stage,
        blocking=False,
        waivable=True,
        status="passed" if ratified else "pending",
        message=f"{stage} checkpoint is {'ratified' if ratified else 'not ratified yet'}",
        source_ids=["memory.decision_log"],
        stage=stage,
        operation="validate",
    )
