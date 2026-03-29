from __future__ import annotations

import json
from pathlib import Path

from madspec_cli.memory import get_memory_paths
from madspec_cli.memory.application.branch_state import (
    BootstrapBranchStateRequest,
    bootstrap_branch_state,
    refresh_branch_state,
)


def step_status(
    *,
    status: str,
    completed_at: str | None = None,
    tdd_phase: str = "not_started",
    red: list[str] | None = None,
    green: list[str] | None = None,
    refactor_note: str | None = None,
) -> dict[str, object]:
    return {
        "status": status,
        "completedAt": completed_at,
        "tddPhase": tdd_phase,
        "redEvidence": red or [],
        "greenEvidence": green or [],
        "refactorNote": refactor_note,
    }


def step_metadata(kind: str, policy: str, waiver_reason: str | None = None) -> dict[str, object]:
    return {
        "kind": kind,
        "tddPolicy": policy,
        "waiverReason": waiver_reason,
    }


def create_step_artifacts(branch_dir: Path, step_id: str) -> None:
    step_dir = branch_dir / "steps" / step_id
    step_dir.mkdir(parents=True, exist_ok=True)
    for file_name in ("description.md", "tasks.md", "tests.md", "validation.md"):
        (step_dir / file_name).write_text(f"# {step_id} {file_name}\n", encoding="utf-8")


def fake_download(
    project_path: Path,
    ai_assistant: str,
    is_current_dir: bool,
    verbose: bool = False,
    emit_progress=None,
    client=None,
    debug: bool = False,
    github_token: str | None = None,
):
    del ai_assistant, is_current_dir, verbose, emit_progress, client, debug, github_token
    project_path.mkdir(parents=True, exist_ok=True)
    (project_path / ".madspec" / "templates").mkdir(parents=True, exist_ok=True)
    (project_path / ".madspec" / "templates" / "project-context-template.md").write_text(
        "# template\n",
        encoding="utf-8",
    )
    (project_path / "README.md").write_text("# demo\n", encoding="utf-8")


def git_identity_env() -> dict[str, str]:
    return {
        "GIT_AUTHOR_NAME": "MADSpec Tests",
        "GIT_AUTHOR_EMAIL": "tests@example.com",
        "GIT_COMMITTER_NAME": "MADSpec Tests",
        "GIT_COMMITTER_EMAIL": "tests@example.com",
    }


def write_madspec_config(
    project_path: Path,
    branch: str = "main",
    version: str = "1.0.0",
    agent_environment: str | None = None,
    phase2_enabled: bool | None = True,
) -> Path:
    madspec_dir = project_path / ".madspec"
    madspec_dir.mkdir(parents=True, exist_ok=True)
    config_path = madspec_dir / "config.json"
    payload = {"currentBranch": branch, "version": version}
    if config_path.exists():
        payload.update(json.loads(config_path.read_text(encoding="utf-8")))
        payload["currentBranch"] = branch
        payload["version"] = version
    if agent_environment:
        payload["agentEnvironment"] = agent_environment
    if payload.get("agentEnvironment"):
        payload["agentsSchemaVersion"] = 1
    if phase2_enabled is not None:
        payload["parallelRuntime"] = {
            "phase1Enabled": True,
            "phase2Enabled": phase2_enabled,
        }
    config_path.write_text(
        json.dumps(payload) + "\n",
        encoding="utf-8",
    )
    return config_path


def bootstrap_project(tmp_path: Path, branch: str = "main", project_name: str = "project") -> dict[str, Path]:
    project_path = tmp_path / project_name
    project_path.mkdir()
    write_madspec_config(project_path, branch)
    bootstrap_branch_state(BootstrapBranchStateRequest(project_path=project_path, branch_name=branch))
    return get_memory_paths(project_path, branch)


def sync_branch_state(project_path: Path, branch: str = "main", *, stage: str | None = None, full: bool = True) -> None:
    refresh_branch_state(project_path, branch, stage=stage, full=full)


def write_concept_markdown(branch_dir: Path, variant: str = "default") -> Path:
    if variant == "default":
        content = """# Концепция проекта: Auth Demo

**Дата создания**: 2026-03-11

## Общее описание системы
Система помогает управлять аутентификацией пользователей и настройками их сессий.

## Основные функции разрабатываемого проекта

### Приоритет 1
- User authentication: sign in users
- Session persistence: keep users logged in

### Приоритет 2
- Profile customization: update display name

### Приоритет 3
- Export settings: download preferences
"""
    elif variant == "auth":
        content = """# Concept

### Приоритет 1
- Authentication: sign in users
"""
    elif variant == "auth_sessions":
        content = """# Concept

### Приоритет 1
- Authentication: sign in users
- Sessions: keep users logged in
"""
    elif variant == "auth_profile_export":
        content = """# Concept

### Приоритет 1
- Authentication: sign in users
- Sessions: keep users logged in

### Приоритет 2
- Profile: edit user profile

### Приоритет 3
- Export: download settings
"""
    elif variant == "auth_short":
        content = "# Concept\n\n### Приоритет 1\n- Auth: sign in users\n"
    elif variant == "auth_short_sign_in":
        content = "# Concept\n\n### Приоритет 1\n- Auth: sign in\n"
    else:
        raise ValueError(f"Unknown concept variant: {variant}")

    concept_path = branch_dir / "concept.md"
    concept_path.write_text(content, encoding="utf-8")
    return concept_path
