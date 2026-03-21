from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ..storage import _default_active_session, get_memory_paths, read_json
from .constants import SYSTEM_SESSION_KEY
from .layout import ensure_system_memory_layout
from .store import MemoryStore


def clone_session_payload(payload: dict[str, Any]) -> dict[str, Any]:
    return json.loads(json.dumps(payload))


def default_session_payload(*, branch_name: str, session_key: str) -> dict[str, Any]:
    payload = _default_active_session(branch_name)
    payload["session_key"] = session_key
    return payload


def load_runtime_session(
    project_path: Path,
    *,
    branch_name: str,
    session_key: str = SYSTEM_SESSION_KEY,
    create_if_missing: bool = True,
) -> dict[str, Any]:
    ensure_system_memory_layout(project_path)
    store = MemoryStore(project_path)
    payload = store.fetch_session(branch=branch_name, session_key=session_key)

    if payload is None and create_if_missing:
        payload = _bootstrap_session_payload(
            project_path,
            branch_name=branch_name,
            session_key=session_key,
        )
        store.upsert_session(branch=branch_name, session_key=session_key, payload=payload)
    elif payload is None:
        payload = default_session_payload(branch_name=branch_name, session_key=session_key)
    else:
        payload = normalize_session_payload(
            payload,
            branch_name=branch_name,
            session_key=session_key,
        )
        store.upsert_session(branch=branch_name, session_key=session_key, payload=payload)

    if session_key == SYSTEM_SESSION_KEY:
        project_active_session(project_path, branch_name=branch_name, payload=payload)
    return payload


def save_runtime_session(
    project_path: Path,
    *,
    branch_name: str,
    session_key: str = SYSTEM_SESSION_KEY,
    payload: dict[str, Any],
) -> dict[str, Any]:
    ensure_system_memory_layout(project_path)
    normalized = normalize_session_payload(
        payload,
        branch_name=branch_name,
        session_key=session_key,
    )
    store = MemoryStore(project_path)
    store.upsert_session(branch=branch_name, session_key=session_key, payload=normalized)
    if session_key == SYSTEM_SESSION_KEY:
        project_active_session(project_path, branch_name=branch_name, payload=normalized)
    return normalized


def project_active_session(
    project_path: Path,
    *,
    branch_name: str,
    payload: dict[str, Any] | None = None,
) -> Path:
    paths = get_memory_paths(project_path, branch_name)
    if payload is None:
        payload = load_runtime_session(
            project_path,
            branch_name=branch_name,
            session_key=SYSTEM_SESSION_KEY,
            create_if_missing=True,
        )
    paths.active_session.parent.mkdir(parents=True, exist_ok=True)
    paths.active_session.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return paths.active_session


def normalize_session_payload(
    payload: dict[str, Any] | None,
    *,
    branch_name: str,
    session_key: str,
) -> dict[str, Any]:
    normalized = default_session_payload(branch_name=branch_name, session_key=session_key)
    for key, value in dict(payload or {}).items():
        normalized[key] = value

    normalized["branch"] = branch_name
    normalized["session_key"] = session_key
    normalized["active_goal"] = str(normalized.get("active_goal") or "")

    stage = str(normalized.get("stage") or "").strip().lower()
    normalized["stage"] = stage or "idle"

    current_step = normalized.get("current_step")
    if isinstance(current_step, str):
        current_step = current_step.strip() or None
    else:
        current_step = None
    normalized["current_step"] = current_step

    for key in ("pending_actions", "open_questions", "current_hypotheses"):
        values = normalized.get(key)
        if isinstance(values, list):
            normalized[key] = [str(item).strip() for item in values if str(item).strip()]
        else:
            normalized[key] = []

    return normalized


def _bootstrap_session_payload(
    project_path: Path,
    *,
    branch_name: str,
    session_key: str,
) -> dict[str, Any]:
    if session_key != SYSTEM_SESSION_KEY:
        return default_session_payload(branch_name=branch_name, session_key=session_key)

    paths = get_memory_paths(project_path, branch_name)
    legacy_payload = read_json(paths.active_session, None)
    if isinstance(legacy_payload, dict):
        return normalize_session_payload(
            legacy_payload,
            branch_name=branch_name,
            session_key=session_key,
        )
    return default_session_payload(branch_name=branch_name, session_key=session_key)
