from __future__ import annotations

from .initializer_core import initialize_project as core_initialize_project
from ..domain.models import InitializeProjectRequest, InitializeProjectResult


def install_project(request: InitializeProjectRequest) -> InitializeProjectResult:
    return core_initialize_project(
        request.project_path,
        selected_ai=request.selected_ai,
        here=request.here,
        no_git=request.no_git,
        should_init_git=request.should_init_git,
        skip_tls=request.skip_tls,
        debug=request.debug,
        github_token=request.github_token,
        tracker=request.tracker,
    )
