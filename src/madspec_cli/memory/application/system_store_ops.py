from __future__ import annotations

from pathlib import Path
from typing import Any

from ..shared.system_store.model_bootstrap import ensure_model_available
from ..shared.system_store.provider_factory import resolve_configured_embeddings
from ..shared.system_store import build_db_status as _build_db_status
from ..shared.system_store import run_reindex as _run_reindex


def build_db_status(project_path: Path, branch_name: str | None = None) -> dict[str, Any]:
    return _build_db_status(project_path, branch_name)


def run_reindex(project_path: Path, branch_name: str | None = None, *, limit: int = 200) -> dict[str, Any]:
    return _run_reindex(project_path, branch_name, limit=limit)


def bootstrap_configured_model(project_path: Path, *, force: bool = False) -> dict[str, Any]:
    selection = resolve_configured_embeddings(project_path)
    payload = selection.to_status_payload(project_path)
    payload["download_policy"] = selection.download_policy

    if selection.provider == "hash":
        payload.update(
            {
                "downloaded": False,
                "next_action": None,
                "message": "Configured provider does not require dense model bootstrap.",
            }
        )
        return payload

    if selection.bootstrap_status.status == "corrupted" and not force:
        raise RuntimeError(
            "Configured model cache is corrupted. Re-run `madspec memory bootstrap-model --force` "
            "to rebuild the cache root safely."
        )

    result = ensure_model_available(
        project_path,
        selection.to_config_payload(),
        allow_download=True,
        force_repair=force,
    )
    resolved_payload = resolve_configured_embeddings(project_path).to_status_payload(project_path)
    resolved_payload["download_policy"] = selection.download_policy
    resolved_payload["downloaded"] = result.downloaded

    if not result.ready:
        bootstrap = resolved_payload.get("bootstrap") or {}
        message = None
        if isinstance(bootstrap, dict):
            message = bootstrap.get("message")
        raise RuntimeError(
            str(message or "Configured embeddings provider is not ready after bootstrap.")
        )

    resolved_payload["message"] = (
        "Configured dense model is ready in the project-local cache."
        if result.downloaded
        else "Configured dense model was already ready in the project-local cache."
    )
    resolved_payload["next_action"] = "Run `madspec memory reindex` to rebuild the active vector namespace."
    return resolved_payload
