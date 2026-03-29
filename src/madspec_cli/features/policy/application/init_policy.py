from __future__ import annotations

import uuid
from dataclasses import dataclass
from pathlib import Path

from madspec_cli.shared.kernel.result import PayloadResult

from ..infrastructure.normalization import now_iso
from ..infrastructure.paths import get_policy_paths
from ..infrastructure.repository import list_policy_history, load_policy_state
from ..infrastructure.service import append_policy_history, ensure_policy_layout


@dataclass(frozen=True)
class InitPolicyRequest:
    project_path: Path


@dataclass(frozen=True)
class InitPolicyResult(PayloadResult):
    pass


def execute(request: InitPolicyRequest) -> InitPolicyResult:
    created = ensure_policy_layout(request.project_path)
    history = list_policy_history(request.project_path)
    if not history:
        append_policy_history(
            request.project_path,
            {
                "eventId": str(uuid.uuid4()),
                "eventType": "initialized",
                "policyId": None,
                "proposalId": None,
                "ts": now_iso(),
                "summary": "Policy store initialized",
                "payload": {},
            },
        )
    paths = get_policy_paths(request.project_path)
    state = load_policy_state(request.project_path)
    return InitPolicyResult(
        payload={
            "created": [str(path.relative_to(request.project_path)) for path in created],
            "state_file": str(paths.state_file.relative_to(request.project_path)),
            "artifact_file": str(paths.artifact_file.relative_to(request.project_path)),
            "revision": state.get("revision", 1),
        }
    )
