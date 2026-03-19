from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from madspec_cli.shared.kernel.result import PayloadResult

from .common import default_recommendation


@dataclass(frozen=True)
class RecommendAgentsRequest:
    project_path: Path


@dataclass(frozen=True)
class RecommendAgentsResult(PayloadResult):
    pass


def execute(request: RecommendAgentsRequest) -> RecommendAgentsResult:
    return RecommendAgentsResult(payload=default_recommendation(request.project_path))
