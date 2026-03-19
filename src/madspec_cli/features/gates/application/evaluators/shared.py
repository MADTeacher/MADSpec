from __future__ import annotations

import hashlib
import re
from typing import Any

from ...domain.models import GateResult
from ...domain.status import GATE_STATUSES


def build_gate(
    *,
    family: str,
    scope: str,
    subject_id: str,
    blocking: bool,
    waivable: bool,
    status: str,
    message: str,
    source_ids: list[str],
    stage: str,
    operation: str,
) -> dict[str, Any]:
    base = f"{family}|{scope}|{subject_id}|{stage}|{operation}|{message}"
    digest = hashlib.sha1(base.encode("utf-8")).hexdigest()[:12]
    gate = GateResult(
        gate_id=f"gate-{digest}",
        family=family,
        scope=scope,
        subject_id=subject_id,
        blocking=blocking,
        waivable=waivable,
        status=status if status in GATE_STATUSES else "failed",
        message=message,
        source_ids=source_ids,
    ).to_payload()
    return gate


def normalize_function_label(value: str) -> str:
    normalized = re.sub(r"\s+", " ", value).strip()
    while normalized.startswith("**") and normalized.endswith("**") and len(normalized) >= 4:
        normalized = normalized[2:-2].strip()
    return normalized


def known_function_samples(catalog: dict[str, list[str]], limit: int = 5) -> str:
    values: list[str] = []
    for priority in ("p1", "p2", "p3"):
        for item in catalog.get(priority, []):
            if item not in values:
                values.append(item)
            if len(values) >= limit:
                return ", ".join(values)
    return ", ".join(values)
