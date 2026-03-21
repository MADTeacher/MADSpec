from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from madspec_cli.project_state import normalize_parallel_runtime_policy, read_madspec_config


PHASE2_OPT_IN_MESSAGE = "Phase 2 coordinator runtime is opt-in"
PHASE2_OPT_IN_GUIDANCE = "Enable parallelRuntime.phase2Enabled=true in .madspec/config.json"


@dataclass(frozen=True)
class ParallelRuntimePolicy:
    phase1_enabled: bool
    phase2_enabled: bool

    def to_payload(self) -> dict[str, bool]:
        return {
            "phase1Enabled": self.phase1_enabled,
            "phase2Enabled": self.phase2_enabled,
        }


def read_parallel_runtime_policy(project_path: Path) -> ParallelRuntimePolicy:
    payload = normalize_parallel_runtime_policy(
        read_madspec_config(project_path).get("parallelRuntime")
    )
    return ParallelRuntimePolicy(
        phase1_enabled=bool(payload["phase1Enabled"]),
        phase2_enabled=bool(payload["phase2Enabled"]),
    )


def is_phase2_enabled(project_path: Path) -> bool:
    return read_parallel_runtime_policy(project_path).phase2_enabled


def require_phase2_enabled(
    project_path: Path,
    *,
    command_name: str,
) -> dict[str, Any] | None:
    policy = read_parallel_runtime_policy(project_path)
    if policy.phase2_enabled:
        return None
    return {
        "accepted": False,
        "reason": "phase2_disabled",
        "message": PHASE2_OPT_IN_MESSAGE,
        "guidance": PHASE2_OPT_IN_GUIDANCE,
        "command": command_name,
        "parallel_runtime": policy.to_payload(),
    }
