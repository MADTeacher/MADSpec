from __future__ import annotations

from pathlib import Path
from typing import Any

from ..projection.materialize import consolidate_branch_memory
from ..shared.system_store.constants import SYSTEM_SESSION_KEY
from .capture_inputs import build_capture_inputs
from .capture_persistence import persist_capture
from .capture_prepare import prepare_capture
from .capture_stage_bundles import build_parsed_stage_bundle

CAPTURE_STAGES = {
    "mvp.concept",
    "mvp.design",
    "mvp.tech",
    "mvp.architecture",
    "mvp.plan",
    "feature.init",
    "feature.plan",
    "review",
    "security",
}


def capture_stage_memory(
    project_path: Path,
    branch_name: str,
    stage: str,
    *,
    session_key: str = SYSTEM_SESSION_KEY,
    **kwargs: Any,
) -> dict[str, Any]:
    normalized_stage = stage.strip().lower()
    if normalized_stage not in CAPTURE_STAGES:
        return {
            "accepted": False,
            "branch": branch_name,
            "stage": normalized_stage,
            "errors": ["stage must be one of: " + ", ".join(sorted(CAPTURE_STAGES))],
        }

    raw_status = kwargs.pop("status", "validated")
    normalized_status = raw_status.strip().lower()
    if normalized_status not in {"proposed", "validated", "conflicted", "obsolete"}:
        return {
            "accepted": False,
            "branch": branch_name,
            "stage": normalized_stage,
            "errors": ["status must be one of: conflicted, obsolete, proposed, validated"],
        }

    inputs = build_capture_inputs(
        stage=normalized_stage,
        status=normalized_status,
        **kwargs,
    )
    parsed = build_parsed_stage_bundle(inputs)
    prepared = prepare_capture(branch_name=branch_name, inputs=inputs, parsed=parsed)
    if isinstance(prepared, dict):
        return prepared
    return persist_capture(
        project_path=project_path,
        branch_name=branch_name,
        session_key=session_key,
        prepared=prepared,
        consolidate_fn=consolidate_branch_memory,
    )
