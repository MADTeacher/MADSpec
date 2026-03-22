from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from madspec_cli.config import (
    DEFAULT_PARALLEL_RUNTIME_POLICY,
    MADSPEC_AGENTS_SCHEMA_VERSION,
    MADSPEC_CONFIG_VERSION,
)
from madspec_cli.features.git.infrastructure.operations import get_current_branch


def resolve_branch_name(project_path: Path, branch_name: str | None) -> str:
    return branch_name or get_current_branch(project_path)


def default_parallel_runtime_policy() -> dict[str, bool]:
    return dict(DEFAULT_PARALLEL_RUNTIME_POLICY)


def normalize_parallel_runtime_policy(payload: Any) -> dict[str, bool]:
    if not isinstance(payload, dict):
        return default_parallel_runtime_policy()
    return {
        "phase1Enabled": bool(payload.get("phase1Enabled", True)),
        "phase2Enabled": bool(payload.get("phase2Enabled", False)),
    }


def get_madspec_config_path(project_path: Path) -> Path:
    return project_path / ".madspec" / "config.json"


def default_madspec_config(branch_name: str, *, agent_environment: str | None = None) -> dict[str, Any]:
    config: dict[str, Any] = {
        "currentBranch": branch_name,
        "version": MADSPEC_CONFIG_VERSION,
        "agentsSchemaVersion": MADSPEC_AGENTS_SCHEMA_VERSION,
        "parallelRuntime": default_parallel_runtime_policy(),
    }
    if agent_environment:
        config["agentEnvironment"] = agent_environment
    return config


def read_madspec_config(project_path: Path) -> dict[str, Any]:
    config_path = get_madspec_config_path(project_path)
    if not config_path.exists():
        return {}
    try:
        payload = json.loads(config_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    if not isinstance(payload, dict):
        return {}
    payload = dict(payload)
    payload["parallelRuntime"] = normalize_parallel_runtime_policy(payload.get("parallelRuntime"))
    return payload


def write_madspec_config(project_path: Path, payload: dict[str, Any]) -> dict[str, Any]:
    madspec_dir = project_path / ".madspec"
    madspec_dir.mkdir(exist_ok=True)
    config_file = get_madspec_config_path(project_path)
    config_file.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return payload


def update_madspec_config(project_path: Path, **updates: Any) -> dict[str, Any]:
    config = read_madspec_config(project_path)
    config.update({key: value for key, value in updates.items() if value is not None})
    if "version" not in config:
        config["version"] = MADSPEC_CONFIG_VERSION
    if "agentsSchemaVersion" not in config:
        config["agentsSchemaVersion"] = MADSPEC_AGENTS_SCHEMA_VERSION
    config["parallelRuntime"] = normalize_parallel_runtime_policy(config.get("parallelRuntime"))
    return write_madspec_config(project_path, config)


def create_madspec_config(project_path: Path, branch_name: str, *, agent_environment: str | None = None) -> None:
    config = default_madspec_config(branch_name, agent_environment=agent_environment)
    existing = read_madspec_config(project_path)
    if existing:
        config.update(existing)
        config["currentBranch"] = branch_name
        config["version"] = existing.get("version") or MADSPEC_CONFIG_VERSION
        config["agentsSchemaVersion"] = existing.get("agentsSchemaVersion") or MADSPEC_AGENTS_SCHEMA_VERSION
        if agent_environment is not None:
            config["agentEnvironment"] = agent_environment
    config["parallelRuntime"] = normalize_parallel_runtime_policy(config.get("parallelRuntime"))
    write_madspec_config(project_path, config)


def ensure_branch_dir(project_path: Path, branch_name: str) -> Path:
    branch_dir = project_path / ".madspec" / branch_name
    branch_dir.mkdir(parents=True, exist_ok=True)
    return branch_dir
