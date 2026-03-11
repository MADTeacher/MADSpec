from __future__ import annotations

from ..domain.models import InitializeProjectRequest, InitializeProjectResult
from ..infrastructure.project_installer import install_project


def execute(request: InitializeProjectRequest) -> InitializeProjectResult:
    return install_project(request)
