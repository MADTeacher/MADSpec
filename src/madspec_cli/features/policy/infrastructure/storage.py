from __future__ import annotations

import json
import re
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

POLICY_SCHEMA_VERSION = 1
SYSTEM_POLICY_BRANCH = "__system__"
SYSTEM_POLICY_STAGE = "policy"
POLICY_KINDS = {"guideline", "rule"}
POLICY_ENFORCEMENTS = {"advisory", "required"}
POLICY_SOURCES = {"system", "user"}
POLICY_STATUSES = {"active", "deprecated"}
PROPOSAL_ACTIONS = {"set", "deprecate"}
PROPOSAL_STATUSES = {"pending", "applied"}
SUPPORTED_RULE_TYPES = {
    "code_steps_require_required_tdd",
    "non_code_steps_forbid_required_tdd",
    "non_required_tdd_requires_waived_phase",
    "completed_code_steps_require_tdd_evidence",
}
STEP_KINDS = {"code", "non-code"}
POLICY_ID_PATTERN = re.compile(r"[^a-z0-9]+")


@dataclass(frozen=True)
class PolicyPaths:
    system_dir: Path
    policy_dir: Path
    state_file: Path
    proposals_file: Path
    history_file: Path
    artifact_file: Path


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def get_policy_paths(project_path: Path) -> PolicyPaths:
    system_dir = project_path / ".madspec" / "system"
    policy_dir = system_dir / "policy"
    return PolicyPaths(
        system_dir=system_dir,
        policy_dir=policy_dir,
        state_file=policy_dir / "state.json",
        proposals_file=policy_dir / "proposals.jsonl",
        history_file=policy_dir / "history.jsonl",
        artifact_file=system_dir / "policy.md",
    )


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
    step_kinds = [item for item in _normalize_string_list(value.get("stepKinds", []), lower=True) if item in STEP_KINDS]
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


def normalize_policy_payload(value: Any, *, existing: dict[str, Any] | None = None) -> tuple[dict[str, Any], list[str]]:
    existing = existing or {}
    warnings: list[str] = []
    ts = now_iso()
    source = _normalize_lower(value.get("source") if isinstance(value, dict) else None) or _normalize_lower(existing.get("source")) or "user"
    if source not in POLICY_SOURCES:
        source = "user"
    readonly = bool(value.get("readonly")) if isinstance(value, dict) else bool(existing.get("readonly"))
    if source == "system":
        readonly = True

    raw_policy_id = value.get("policyId") if isinstance(value, dict) else None
    policy_id = _normalize_policy_id(raw_policy_id or existing.get("policyId") or uuid.uuid4().hex[:12])
    title = _normalize_string(value.get("title") if isinstance(value, dict) else None) or _normalize_string(existing.get("title")) or policy_id.replace("-", " ").title()
    description = _normalize_string(value.get("description") if isinstance(value, dict) else None) or _normalize_string(existing.get("description"))
    status = _normalize_lower(value.get("status") if isinstance(value, dict) else None) or _normalize_lower(existing.get("status")) or "active"
    if status not in POLICY_STATUSES or source == "system":
        status = "active" if source == "system" else "active"

    kind = _normalize_lower(value.get("kind") if isinstance(value, dict) else None) or _normalize_lower(existing.get("kind")) or "guideline"
    if kind not in POLICY_KINDS:
        kind = "guideline"
    enforcement = _normalize_lower(value.get("enforcement") if isinstance(value, dict) else None) or _normalize_lower(existing.get("enforcement")) or "advisory"
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
        warnings.append(f"unsupported ruleType '{rule['ruleType']}' was normalized to advisory guideline")
        kind = "guideline"
        enforcement = "advisory"
        rule = None

    created_at = _normalize_string(existing.get("createdAt")) or ts
    updated_at = _normalize_string(value.get("updatedAt") if isinstance(value, dict) else None) or ts
    deprecated_at = None
    if status == "deprecated" and source != "system":
        deprecated_at = _normalize_string(value.get("deprecatedAt") if isinstance(value, dict) else None) or _normalize_string(existing.get("deprecatedAt")) or ts

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
        if normalized_policy["policyId"] in system_policies:
            continue
        if normalized_policy["policyId"] in seen:
            continue
        normalized["policies"].append(normalized_policy)
        seen.add(normalized_policy["policyId"])

    return normalized


def read_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    records: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        records.append(json.loads(line))
    return records


def append_jsonl(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(payload, ensure_ascii=False) + "\n")


def ensure_policy_layout(project_path: Path) -> list[Path]:
    paths = get_policy_paths(project_path)
    created: list[Path] = []
    if not paths.system_dir.exists():
        paths.system_dir.mkdir(parents=True, exist_ok=True)
        created.append(paths.system_dir)
    if not paths.policy_dir.exists():
        paths.policy_dir.mkdir(parents=True, exist_ok=True)
        created.append(paths.policy_dir)

    if not paths.state_file.exists():
        write_json(paths.state_file, default_policy_state())
        created.append(paths.state_file)
    else:
        state = normalize_policy_state(read_json(paths.state_file, default_policy_state()))
        write_json(paths.state_file, state)

    for path in (paths.proposals_file, paths.history_file):
        if not path.exists():
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("", encoding="utf-8")
            created.append(path)

    export_policy_artifact(project_path, refresh_branches=False)
    return created


def load_policy_state(project_path: Path, *, create_if_missing: bool = True) -> dict[str, Any]:
    if create_if_missing:
        ensure_policy_layout(project_path)
    paths = get_policy_paths(project_path)
    return normalize_policy_state(read_json(paths.state_file, default_policy_state()))


def save_policy_state(project_path: Path, state: dict[str, Any]) -> dict[str, Any]:
    normalized = normalize_policy_state(state)
    normalized["updatedAt"] = now_iso()
    write_json(get_policy_paths(project_path).state_file, normalized)
    _sync_policy_snapshot(project_path, normalized)
    export_policy_artifact(project_path)
    return normalized


def list_policy_proposals(project_path: Path, *, create_if_missing: bool = True) -> list[dict[str, Any]]:
    if create_if_missing:
        ensure_policy_layout(project_path)
    proposals: dict[str, dict[str, Any]] = {}
    for item in read_jsonl(get_policy_paths(project_path).proposals_file):
        proposal_id = _normalize_string(item.get("proposalId"))
        if not proposal_id:
            continue
        proposals[proposal_id] = item
    return sorted(
        proposals.values(),
        key=lambda item: (item.get("requestedAt", ""), item.get("proposalId", "")),
        reverse=True,
    )


def list_policy_history(project_path: Path, *, create_if_missing: bool = True) -> list[dict[str, Any]]:
    if create_if_missing:
        ensure_policy_layout(project_path)
    return sorted(
        read_jsonl(get_policy_paths(project_path).history_file),
        key=lambda item: (item.get("ts", ""), item.get("eventId", "")),
        reverse=True,
    )


def append_policy_proposal(project_path: Path, proposal: dict[str, Any]) -> None:
    ensure_policy_layout(project_path)
    append_jsonl(get_policy_paths(project_path).proposals_file, proposal)
    _sync_policy_record(
        project_path,
        {
            "id": proposal["proposalId"],
            "ts": proposal["requestedAt"],
            "branch": SYSTEM_POLICY_BRANCH,
            "stage": SYSTEM_POLICY_STAGE,
            "status": "validated" if proposal.get("status") == "applied" else "proposed",
            "source": "policy.proposal",
            "summary": proposal["summary"],
            "scope": "project",
            "record_type": "policy_proposal",
            "metadata": {
                "policyId": proposal["policyId"],
                "action": proposal["action"],
                "status": proposal["status"],
                "diff": proposal.get("diff", {}),
                "warnings": proposal.get("warnings", []),
            },
            "evidence": [],
        },
    )


def append_policy_history(project_path: Path, event: dict[str, Any]) -> None:
    ensure_policy_layout(project_path)
    append_jsonl(get_policy_paths(project_path).history_file, event)
    _sync_policy_record(
        project_path,
        {
            "id": event["eventId"],
            "ts": event["ts"],
            "branch": SYSTEM_POLICY_BRANCH,
            "stage": SYSTEM_POLICY_STAGE,
            "status": "validated",
            "source": "policy.history",
            "summary": event["summary"],
            "scope": "project",
            "record_type": "policy_event",
            "metadata": {
                "eventType": event["eventType"],
                "policyId": event.get("policyId"),
                "proposalId": event.get("proposalId"),
                "payload": event.get("payload", {}),
            },
            "evidence": [],
        },
    )


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


def effective_policies(
    project_path: Path,
    *,
    stage: str | None = None,
    operation: str | None = None,
    step_kind: str | None = None,
    create_if_missing: bool = True,
) -> list[dict[str, Any]]:
    state = load_policy_state(project_path, create_if_missing=create_if_missing)
    return [
        policy
        for policy in state.get("policies", [])
        if policy_matches_scope(policy, stage=stage, operation=operation, step_kind=step_kind)
    ]


def policy_summary(project_path: Path, *, stage: str | None = None, create_if_missing: bool = True) -> dict[str, Any]:
    state = load_policy_state(project_path, create_if_missing=create_if_missing)
    proposals = list_policy_proposals(project_path, create_if_missing=create_if_missing)
    effective = effective_policies(project_path, stage=stage, create_if_missing=create_if_missing)
    required = [item for item in effective if item.get("enforcement") == "required"]
    advisory = [item for item in effective if item.get("enforcement") == "advisory"]
    return {
        "revision": state.get("revision", 1),
        "activeCount": len([item for item in state.get("policies", []) if item.get("status") == "active"]),
        "deprecatedCount": len([item for item in state.get("policies", []) if item.get("status") == "deprecated"]),
        "pendingProposalsCount": len([item for item in proposals if item.get("status") == "pending"]),
        "required": required,
        "advisory": advisory,
    }


def render_policy_markdown(
    state: dict[str, Any],
    proposals: list[dict[str, Any]],
) -> str:
    lines = [
        "# Project Policies",
        "",
        "> Generated from `.madspec/system/policy/state.json`. Do not edit this file as canonical state.",
        "",
        f"- Revision: `{state.get('revision', 1)}`",
        f"- Updated: `{state.get('updatedAt') or state.get('createdAt') or now_iso()}`",
        f"- Pending proposals: `{len([item for item in proposals if item.get('status') == 'pending'])}`",
        "",
        "## Active Policies",
    ]
    active = [item for item in state.get("policies", []) if item.get("status") == "active"]
    if not active:
        lines.append("- No active policies")
    for policy in active:
        rule = policy.get("rule") or {}
        lines.extend(
            [
                f"### {policy['title']} (`{policy['policyId']}`)",
                "",
                f"- Kind: `{policy['kind']}`",
                f"- Enforcement: `{policy['enforcement']}`",
                f"- Source: `{policy['source']}`",
                (
                    "- Scope: `all`"
                    if not policy.get("scope", {}).get("stages")
                    else "- Scope stages: `"
                    + ", ".join(policy.get("scope", {}).get("stages", []))
                    + "`"
                ),
            ]
        )
        if rule.get("ruleType"):
            lines.append(f"- Rule type: `{rule['ruleType']}`")
        lines.extend(["", policy.get("description") or "_No description_", ""])

    deprecated = [item for item in state.get("policies", []) if item.get("status") == "deprecated"]
    lines.extend(["## Deprecated Policies", ""])
    if not deprecated:
        lines.append("- No deprecated policies")
    for policy in deprecated:
        lines.extend(
            [
                f"- `{policy['policyId']}` — {policy['title']} (deprecated at `{policy.get('deprecatedAt') or 'unknown'}`)",
            ]
        )

    lines.extend(["", "## Pending Proposals", ""])
    pending = [item for item in proposals if item.get("status") == "pending"]
    if not pending:
        lines.append("- No pending proposals")
    for proposal in pending:
        lines.append(
            f"- `{proposal['proposalId']}` `{proposal['action']}` -> `{proposal['policyId']}`: {proposal['summary']}"
        )
    return "\n".join(lines) + "\n"


def export_policy_artifact(project_path: Path, *, refresh_branches: bool = True) -> Path:
    paths = get_policy_paths(project_path)
    state = load_policy_state(project_path, create_if_missing=False)
    proposals = list_policy_proposals(project_path, create_if_missing=False)
    content = render_policy_markdown(state, proposals)
    paths.artifact_file.parent.mkdir(parents=True, exist_ok=True)
    paths.artifact_file.write_text(content, encoding="utf-8")
    _sync_policy_snapshot(project_path, state)
    _sync_policy_artifact(project_path, content)
    if refresh_branches:
        _refresh_branch_policy_views(project_path)
    return paths.artifact_file


def build_policy_context(project_path: Path, *, stage: str | None = None, create_if_missing: bool = True) -> dict[str, Any]:
    summary = policy_summary(project_path, stage=stage, create_if_missing=create_if_missing)
    return {
        "revision": summary["revision"],
        "pending_proposals_count": summary["pendingProposalsCount"],
        "required": summary["required"],
        "advisory": summary["advisory"],
        "artifact": str(get_policy_paths(project_path).artifact_file.relative_to(project_path)),
    }


def _sync_policy_snapshot(project_path: Path, state: dict[str, Any]) -> None:
    from madspec_cli.memory.shared.system_store.layout import ensure_system_memory_layout
    from madspec_cli.memory.shared.system_store.store import MemoryStore

    ensure_system_memory_layout(project_path)
    store = MemoryStore(project_path)
    paths = get_policy_paths(project_path)
    store.upsert_stage_snapshot(
        branch=SYSTEM_POLICY_BRANCH,
        snapshot_key="policy",
        payload=state,
        source_path=str(paths.state_file.relative_to(project_path)),
    )


def _sync_policy_artifact(project_path: Path, content: str) -> None:
    from madspec_cli.memory.shared.system_store.layout import ensure_system_memory_layout
    from madspec_cli.memory.shared.system_store.store import MemoryStore

    ensure_system_memory_layout(project_path)
    store = MemoryStore(project_path)
    paths = get_policy_paths(project_path)
    store.upsert_artifact(
        artifact_id=str(paths.artifact_file.relative_to(project_path)),
        branch=SYSTEM_POLICY_BRANCH,
        stage=SYSTEM_POLICY_STAGE,
        path=str(paths.artifact_file.relative_to(project_path)),
        content=content,
        updated_at=now_iso(),
    )


def _sync_policy_record(project_path: Path, record: dict[str, Any]) -> None:
    from madspec_cli.memory.shared.system_store.layout import ensure_system_memory_layout
    from madspec_cli.memory.shared.system_store.store import MemoryStore

    ensure_system_memory_layout(project_path)
    store = MemoryStore(project_path)
    store.upsert_record(record)


def _refresh_branch_policy_views(project_path: Path) -> None:
    from madspec_cli.memory.views import consolidate_branch_memory

    madspec_dir = project_path / ".madspec"
    if not madspec_dir.exists():
        return
    for path in madspec_dir.iterdir():
        if not path.is_dir() or path.name == "system":
            continue
        consolidate_branch_memory(project_path, path.name)
