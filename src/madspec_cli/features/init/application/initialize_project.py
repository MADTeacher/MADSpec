from __future__ import annotations

from ..infrastructure.initializer_core import initialize_project as core_initialize_project
from .contracts import InitProgressEvent, InitializeProjectRequest, InitializeProjectResult


def execute(request: InitializeProjectRequest) -> InitializeProjectResult:
    def emit_progress(action: str, step: str, detail: str | None = None) -> None:
        if request.progress_reporter is not None:
            request.progress_reporter.handle(
                InitProgressEvent(action=action, step=step, detail=detail)
            )

    result = core_initialize_project(
        request.project_path,
        selected_ai=request.selected_ai,
        memory_embeddings=request.memory_selection.to_config_payload(),
        here=request.here,
        no_git=request.no_git,
        should_init_git=request.should_init_git,
        skip_tls=request.skip_tls,
        debug=request.debug,
        github_token=request.github_token,
        emit_progress=emit_progress,
    )
    return InitializeProjectResult(
        project_path=result.project_path,
        selected_ai=result.selected_ai,
        branch_name=result.branch_name,
        git_error_message=result.git_error_message,
        config_error_message=result.config_error_message,
        memory_bootstrap=result.memory_bootstrap,
    )
