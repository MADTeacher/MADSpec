from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from madspec_cli.config import (
    DEFAULT_PARALLEL_RUNTIME_POLICY,
    MADSPEC_AGENTS_SCHEMA_VERSION,
    MADSPEC_CONFIG_VERSION,
)

DEFAULT_MEMORY_EMBEDDINGS_CACHE_DIR = ".madspec/system/models"
SUPPORTED_MEMORY_EMBEDDING_PROVIDERS = {"hash", "local-hf-onnx"}
SUPPORTED_MEMORY_DOWNLOAD_POLICIES = {"none", "on-init", "on-first-use"}

_MEMORY_EMBEDDINGS_UNSET = object()


def default_parallel_runtime_policy() -> dict[str, bool]:
    return dict(DEFAULT_PARALLEL_RUNTIME_POLICY)


def normalize_parallel_runtime_policy(payload: Any) -> dict[str, bool]:
    if not isinstance(payload, dict):
        return default_parallel_runtime_policy()
    return {
        "phase1Enabled": bool(payload.get("phase1Enabled", True)),
        "phase2Enabled": bool(payload.get("phase2Enabled", True)),
    }


def get_madspec_config_path(project_path: Path) -> Path:
    return project_path / ".madspec" / "config.json"


def default_memory_embeddings_config() -> dict[str, Any]:
    return {
        "provider": "hash",
        "model": None,
        "downloadPolicy": "none",
        "cacheDir": DEFAULT_MEMORY_EMBEDDINGS_CACHE_DIR,
        "revision": None,
    }


def normalize_memory_embeddings_config(payload: Any) -> dict[str, Any]:
    if payload is None:
        return default_memory_embeddings_config()
    if not isinstance(payload, dict):
        raise ValueError("Invalid memory.embeddings payload in .madspec/config.json")

    provider_value = payload.get("provider")
    provider = "hash" if provider_value in (None, "") else provider_value
    if not isinstance(provider, str) or provider not in SUPPORTED_MEMORY_EMBEDDING_PROVIDERS:
        allowed = ", ".join(sorted(SUPPORTED_MEMORY_EMBEDDING_PROVIDERS))
        raise ValueError(f"Unknown memory.embeddings provider '{provider_value}'. Expected one of: {allowed}")

    download_policy_value = payload.get("downloadPolicy")
    model = payload.get("model")
    cache_dir = payload.get("cacheDir") or DEFAULT_MEMORY_EMBEDDINGS_CACHE_DIR
    revision = payload.get("revision")

    if not isinstance(cache_dir, str):
        raise ValueError("memory.embeddings.cacheDir must be a string")
    if revision is not None and not isinstance(revision, str):
        raise ValueError("memory.embeddings.revision must be a string or null")

    if provider == "hash":
        if download_policy_value in (None, ""):
            download_policy = "none"
        else:
            download_policy = download_policy_value
        if download_policy != "none":
            raise ValueError("memory.embeddings provider 'hash' requires downloadPolicy 'none'")
        return {
            "provider": "hash",
            "model": None,
            "downloadPolicy": "none",
            "cacheDir": cache_dir,
            "revision": None,
        }

    if not isinstance(model, str) or not model.strip():
        raise ValueError("memory.embeddings provider 'local-hf-onnx' requires a non-empty model")

    if download_policy_value in (None, ""):
        download_policy = "on-init"
    else:
        download_policy = download_policy_value
    if not isinstance(download_policy, str) or download_policy not in SUPPORTED_MEMORY_DOWNLOAD_POLICIES:
        allowed = ", ".join(sorted(SUPPORTED_MEMORY_DOWNLOAD_POLICIES))
        raise ValueError(
            f"Unknown memory.embeddings downloadPolicy '{download_policy_value}'. Expected one of: {allowed}"
        )

    return {
        "provider": "local-hf-onnx",
        "model": model.strip(),
        "downloadPolicy": download_policy,
        "cacheDir": cache_dir,
        "revision": revision,
    }


def normalize_memory_config(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict):
        return {"embeddings": default_memory_embeddings_config()}
    return {"embeddings": normalize_memory_embeddings_config(payload.get("embeddings"))}


def default_madspec_config(
    branch_name: str,
    *,
    agent_environment: str | None = None,
    memory_embeddings: Any = None,
) -> dict[str, Any]:
    config: dict[str, Any] = {
        "currentBranch": branch_name,
        "version": MADSPEC_CONFIG_VERSION,
        "agentsSchemaVersion": MADSPEC_AGENTS_SCHEMA_VERSION,
        "parallelRuntime": default_parallel_runtime_policy(),
        "memory": {"embeddings": normalize_memory_embeddings_config(memory_embeddings)},
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
    payload["memory"] = normalize_memory_config(payload.get("memory"))
    return payload


def write_madspec_config(project_path: Path, payload: dict[str, Any]) -> dict[str, Any]:
    madspec_dir = project_path / ".madspec"
    madspec_dir.mkdir(exist_ok=True)
    config_file = get_madspec_config_path(project_path)
    normalized = dict(payload)
    normalized["parallelRuntime"] = normalize_parallel_runtime_policy(normalized.get("parallelRuntime"))
    normalized["memory"] = normalize_memory_config(normalized.get("memory"))
    config_file.write_text(
        json.dumps(normalized, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return normalized


def update_madspec_config(
    project_path: Path,
    *,
    memory_embeddings: Any = _MEMORY_EMBEDDINGS_UNSET,
    **updates: Any,
) -> dict[str, Any]:
    config = read_madspec_config(project_path)
    config.update({key: value for key, value in updates.items() if value is not None})
    if "version" not in config:
        config["version"] = MADSPEC_CONFIG_VERSION
    if "agentsSchemaVersion" not in config:
        config["agentsSchemaVersion"] = MADSPEC_AGENTS_SCHEMA_VERSION
    config["parallelRuntime"] = normalize_parallel_runtime_policy(config.get("parallelRuntime"))
    if memory_embeddings is _MEMORY_EMBEDDINGS_UNSET:
        config["memory"] = normalize_memory_config(config.get("memory"))
    else:
        config["memory"] = {"embeddings": normalize_memory_embeddings_config(memory_embeddings)}
    return write_madspec_config(project_path, config)


def create_madspec_config(
    project_path: Path,
    branch_name: str,
    *,
    agent_environment: str | None = None,
    memory_embeddings: Any = _MEMORY_EMBEDDINGS_UNSET,
) -> None:
    config = default_madspec_config(
        branch_name,
        agent_environment=agent_environment,
        memory_embeddings=None if memory_embeddings is _MEMORY_EMBEDDINGS_UNSET else memory_embeddings,
    )
    existing = read_madspec_config(project_path)
    if existing:
        config.update(existing)
        config["currentBranch"] = branch_name
        config["version"] = existing.get("version") or MADSPEC_CONFIG_VERSION
        config["agentsSchemaVersion"] = existing.get("agentsSchemaVersion") or MADSPEC_AGENTS_SCHEMA_VERSION
        if agent_environment is not None:
            config["agentEnvironment"] = agent_environment
    config["parallelRuntime"] = normalize_parallel_runtime_policy(config.get("parallelRuntime"))
    if memory_embeddings is _MEMORY_EMBEDDINGS_UNSET:
        config["memory"] = normalize_memory_config(config.get("memory"))
    else:
        config["memory"] = {"embeddings": normalize_memory_embeddings_config(memory_embeddings)}
    write_madspec_config(project_path, config)


def ensure_branch_dir(project_path: Path, branch_name: str) -> Path:
    branch_dir = project_path / ".madspec" / branch_name
    branch_dir.mkdir(parents=True, exist_ok=True)
    return branch_dir
