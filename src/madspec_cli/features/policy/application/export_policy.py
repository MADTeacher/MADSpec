from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from madspec_cli.shared.kernel.result import PayloadResult

from ..infrastructure.service import export_policy_artifact


@dataclass(frozen=True)
class ExportPolicyRequest:
    project_path: Path


@dataclass(frozen=True)
class ExportPolicyResult(PayloadResult):
    pass


def execute(request: ExportPolicyRequest) -> ExportPolicyResult:
    path = export_policy_artifact(request.project_path)
    return ExportPolicyResult(payload={"artifact_file": str(path.relative_to(request.project_path))})
