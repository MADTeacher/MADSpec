from __future__ import annotations

import re
import uuid
from datetime import datetime, timezone
from typing import Any

from .paths import (
    POLICY_ENFORCEMENTS,
    POLICY_ID_PATTERN,
    POLICY_KINDS,
    POLICY_SCHEMA_VERSION,
    POLICY_SOURCES,
    POLICY_STATUSES,
    STEP_KINDS,
    SUPPORTED_RULE_TYPES,
)


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _normalize_string(value: Any) -> str:
    if not isinstance(value, str):
        return ""
    return re.sub(r"\s+", " ", value).strip()


def _normalize_lower(value: Any) -> str:
    return _normalize_string(value).lower()


def _normalize_string_list(values: Any, *, lower: bool = False) -> list[str]:
    if not isinstance(values, list):
        return []
    result: list[str] = []
    for item in values:
        normalized = _normalize_lower(item) if lower else _normalize_string(item)
        if normalized and normalized not in result:
            result.append(normalized)
    return result


def _normalize_policy_id(value: Any, *, fallback: str = "policy") -> str:
    normalized = POLICY_ID_PATTERN.sub("-", _normalize_lower(value)).strip("-")
    return normalized or fallback


def _normalize_scope(value: Any) -> dict[str, list[str]]:
    if not isinstance(value, dict):
        value = {}
    step_kinds = [
        item for item in _normalize_string_list(value.get("stepKinds", []), lower=True) if item in STEP_KINDS
    ]
    return {
        "stages": _normalize_string_list(value.get("stages", []), lower=True),
        "operations": _normalize_string_list(value.get("operations", []), lower=True),
        "stepKinds": step_kinds,
    }


def _normalize_rule(value: Any) -> dict[str, Any] | None:
    if not isinstance(value, dict):
        return None
    rule_type = _normalize_lower(value.get("ruleType"))
    options = value.get("options", {})
    if not isinstance(options, dict):
        options = {}
    if not rule_type:
        return None
    return {"ruleType": rule_type, "options": dict(options)}


def _system_policy_definitions() -> list[dict[str, Any]]:
    ts = now_iso()
    return [
        {
            "policyId": "code-steps-require-required-tdd",
            "title": "Code steps require required TDD",
            "description": "Code steps must keep the required TDD policy during planning.",
            "kind": "rule",
            "enforcement": "required",
            "status": "active",
            "source": "system",
            "readonly": True,
            "scope": {
                "stages": ["mvp.plan", "feature.plan"],
                "operations": ["register-step", "validate"],
                "stepKinds": ["code"],
            },
            "rule": {"ruleType": "code_steps_require_required_tdd", "options": {}},
            "createdAt": ts,
            "updatedAt": ts,
            "deprecatedAt": None,
            "revision": 1,
        },
        {
            "policyId": "non-code-steps-forbid-required-tdd",
            "title": "Non-code steps forbid required TDD",
            "description": "Non-code steps cannot claim the required TDD policy.",
            "kind": "rule",
            "enforcement": "required",
            "status": "active",
            "source": "system",
            "readonly": True,
            "scope": {
                "stages": ["mvp.plan", "feature.plan"],
                "operations": ["register-step", "validate"],
                "stepKinds": ["non-code"],
            },
            "rule": {"ruleType": "non_code_steps_forbid_required_tdd", "options": {}},
            "createdAt": ts,
            "updatedAt": ts,
            "deprecatedAt": None,
            "revision": 1,
        },
        {
            "policyId": "non-required-tdd-requires-waived-phase",
            "title": "Non-required TDD requires waived phase",
            "description": "Steps with waived or not-applicable TDD must use the waived phase.",
            "kind": "rule",
            "enforcement": "required",
            "status": "active",
            "source": "system",
            "readonly": True,
            "scope": {
                "stages": ["mvp.implement", "feature.implement"],
                "operations": ["checkpoint-step", "complete-step", "validate"],
                "stepKinds": [],
            },
            "rule": {"ruleType": "non_required_tdd_requires_waived_phase", "options": {}},
            "createdAt": ts,
            "updatedAt": ts,
            "deprecatedAt": None,
            "revision": 1,
        },
        {
            "policyId": "completed-code-steps-require-tdd-evidence",
            "title": "Completed code steps require TDD evidence",
            "description": "Completed code steps must have a completed phase, red evidence, green evidence, and refactor note.",
            "kind": "rule",
            "enforcement": "required",
            "status": "active",
            "source": "system",
            "readonly": True,
            "scope": {
                "stages": ["mvp.implement", "feature.implement"],
                "operations": ["complete-step", "validate"],
                "stepKinds": ["code"],
            },
            "rule": {"ruleType": "completed_code_steps_require_tdd_evidence", "options": {}},
            "createdAt": ts,
            "updatedAt": ts,
            "deprecatedAt": None,
            "revision": 1,
        },
    ]


def default_policy_state() -> dict[str, Any]:
    ts = now_iso()
    return {
        "schemaVersion": POLICY_SCHEMA_VERSION,
        "revision": 1,
        "createdAt": ts,
        "updatedAt": ts,
        "policies": _system_policy_definitions(),
    }


def normalize_policy_payload(
    value: Any,
    *,
    existing: dict[str, Any] | None = None,
) -> tuple[dict[str, Any], list[str]]:
    existing = existing or {}
    warnings: list[str] = []
    ts = now_iso()
    source = (
        _normalize_lower(value.get("source") if isinstance(value, dict) else None)
        or _normalize_lower(existing.get("source"))
        or "user"
    )
    if source not in POLICY_SOURCES:
        source = "user"
    readonly = bool(value.get("readonly")) if isinstance(value, dict) else bool(existing.get("readonly"))
    if source == "system":
        readonly = True

    raw_policy_id = value.get("policyId") if isinstance(value, dict) else None
    policy_id = _normalize_policy_id(raw_policy_id or existing.get("policyId") or uuid.uuid4().hex[:12])
    title = (
        _normalize_string(value.get("title") if isinstance(value, dict) else None)
        or _normalize_string(existing.get("title"))
        or policy_id.replace("-", " ").title()
    )
    description = (
        _normalize_string(value.get("description") if isinstance(value, dict) else None)
        or _normalize_string(existing.get("description"))
    )
    status = (
        _normalize_lower(value.get("status") if isinstance(value, dict) else None)
        or _normalize_lower(existing.get("status"))
        or "active"
    )
    if status not in POLICY_STATUSES or source == "system":
        status = "active"

    kind = (
        _normalize_lower(value.get("kind") if isinstance(value, dict) else None)
        or _normalize_lower(existing.get("kind"))
        or "guideline"
    )
    if kind not in POLICY_KINDS:
        kind = "guideline"
    enforcement = (
        _normalize_lower(value.get("enforcement") if isinstance(value, dict) else None)
        or _normalize_lower(existing.get("enforcement"))
        or "advisory"
    )
    if enforcement not in POLICY_ENFORCEMENTS:
        enforcement = "advisory"

    scope = _normalize_scope(value.get("scope") if isinstance(value, dict) else existing.get("scope", {}))
    rule = _normalize_rule(value.get("rule") if isinstance(value, dict) else existing.get("rule"))

    if kind == "guideline":
        enforcement = "advisory"
        rule = None

    if kind == "rule" and rule is None:
        warnings.append("rule policy without supported ruleType was normalized to advisory guideline")
        kind = "guideline"
        enforcement = "advisory"

    if rule is not None and rule["ruleType"] not in SUPPORTED_RULE_TYPES:
        warnings.append(
            f"unsupported ruleType '{rule['ruleType']}' was normalized to advisory guideline"
        )
        kind = "guideline"
        enforcement = "advisory"
        rule = None

    created_at = _normalize_string(existing.get("createdAt")) or ts
    updated_at = _normalize_string(value.get("updatedAt") if isinstance(value, dict) else None) or ts
    deprecated_at = None
    if status == "deprecated" and source != "system":
        deprecated_at = (
            _normalize_string(value.get("deprecatedAt") if isinstance(value, dict) else None)
            or _normalize_string(existing.get("deprecatedAt"))
            or ts
        )

    revision = value.get("revision") if isinstance(value, dict) else existing.get("revision")
    if not isinstance(revision, int) or revision <= 0:
        revision = int(existing.get("revision") or 1)

    normalized = {
        "policyId": policy_id,
        "title": title,
        "description": description,
        "kind": kind,
        "enforcement": enforcement,
        "status": status,
        "source": source,
        "readonly": readonly,
        "scope": scope,
        "rule": rule,
        "createdAt": created_at,
        "updatedAt": updated_at,
        "deprecatedAt": deprecated_at,
        "revision": revision,
    }
    return normalized, warnings


def normalize_policy_state(state: Any) -> dict[str, Any]:
    default_state = default_policy_state()
    if not isinstance(state, dict):
        return default_state

    normalized = {
        "schemaVersion": POLICY_SCHEMA_VERSION,
        "revision": state.get("revision", default_state["revision"]),
        "createdAt": _normalize_string(state.get("createdAt")) or default_state["createdAt"],
        "updatedAt": _normalize_string(state.get("updatedAt")) or default_state["updatedAt"],
        "policies": [],
    }
    if not isinstance(normalized["revision"], int) or normalized["revision"] <= 0:
        normalized["revision"] = default_state["revision"]

    system_policies = {item["policyId"]: item for item in _system_policy_definitions()}
    user_entries = state.get("policies", [])
    if not isinstance(user_entries, list):
        user_entries = []

    seen: set[str] = set()
    for system_policy in system_policies.values():
        normalized_policy, _ = normalize_policy_payload(system_policy)
        normalized["policies"].append(normalized_policy)
        seen.add(normalized_policy["policyId"])

    for item in user_entries:
        if not isinstance(item, dict):
            continue
        normalized_policy, _ = normalize_policy_payload(item, existing=item)
        if normalized_policy["policyId"] in system_policies or normalized_policy["policyId"] in seen:
            continue
        normalized["policies"].append(normalized_policy)
        seen.add(normalized_policy["policyId"])

    return normalized


def policy_matches_scope(
    policy: dict[str, Any],
    *,
    stage: str | None = None,
    operation: str | None = None,
    step_kind: str | None = None,
) -> bool:
    stage = _normalize_lower(stage) if stage else None
    operation = _normalize_lower(operation) if operation else None
    step_kind = _normalize_lower(step_kind) if step_kind else None
    if policy.get("status") != "active":
        return False
    scope = policy.get("scope", {})
    stages = scope.get("stages", [])
    operations = scope.get("operations", [])
    step_kinds = scope.get("stepKinds", [])
    if stage and stages and stage not in stages:
        return False
    if operation and operations and operation not in operations:
        return False
    if step_kind and step_kinds and step_kind not in step_kinds:
        return False
    return True


__all__ = [
    "default_policy_state",
    "normalize_policy_payload",
    "normalize_policy_state",
    "now_iso",
    "policy_matches_scope",
]
