from __future__ import annotations

import os
import time
import uuid
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class RuntimeLeaseDescriptor:
    lease_name: str
    lease_scope: str
    owner_id: str
    ttl_seconds: int


def make_runtime_lease_owner_id(
    *,
    mutation_kind: str,
    session_key: str | None,
) -> str:
    resolved_session_key = str(session_key or "active")
    return f"runtime:{mutation_kind}:{resolved_session_key}:{os.getpid()}:{uuid.uuid4()}"


def build_plan_catalog_lease(*, branch_name: str, mutation_kind: str, session_key: str | None, ttl_seconds: int) -> RuntimeLeaseDescriptor:
    return RuntimeLeaseDescriptor(
        lease_name=f"plan-catalog:{branch_name}",
        lease_scope="plan-catalog",
        owner_id=make_runtime_lease_owner_id(mutation_kind=mutation_kind, session_key=session_key),
        ttl_seconds=ttl_seconds,
    )


def build_implementation_step_lease(
    *,
    branch_name: str,
    step_id: str,
    mutation_kind: str,
    session_key: str | None,
    ttl_seconds: int,
) -> RuntimeLeaseDescriptor:
    return RuntimeLeaseDescriptor(
        lease_name=f"implement-step:{branch_name}:{step_id}",
        lease_scope="step",
        owner_id=make_runtime_lease_owner_id(mutation_kind=mutation_kind, session_key=session_key),
        ttl_seconds=ttl_seconds,
    )


def build_stage_checkpoint_lease(
    *,
    branch_name: str,
    stage: str,
    mutation_kind: str,
    session_key: str | None,
    ttl_seconds: int,
) -> RuntimeLeaseDescriptor | None:
    normalized_stage = stage.strip().lower()
    if normalized_stage not in {"review", "security"}:
        return None
    return RuntimeLeaseDescriptor(
        lease_name=f"{normalized_stage}:{branch_name}",
        lease_scope=normalized_stage,
        owner_id=make_runtime_lease_owner_id(mutation_kind=mutation_kind, session_key=session_key),
        ttl_seconds=ttl_seconds,
    )


def normalize_writer_lease_row(row: dict[str, Any], *, now_epoch: int | None = None) -> dict[str, Any]:
    resolved_now = int(time.time()) if now_epoch is None else now_epoch
    payload = dict(row)
    payload["lease_name"] = str(payload.get("lease_name") or "")
    payload["owner_id"] = str(payload.get("owner_id") or "")
    payload["expires_at"] = int(payload.get("expires_at") or 0)
    payload["updated_at"] = str(payload.get("updated_at") or "")
    payload["expired"] = payload["expires_at"] <= resolved_now
    return payload

