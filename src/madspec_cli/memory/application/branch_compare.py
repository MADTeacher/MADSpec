from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

from madspec_cli.memory.domain.conflicts import (
    make_conflict_id,
    semantic_content_hash,
    semantic_fingerprint,
)
from madspec_cli.memory.shared.storage import (
    _default_progress_state,
    get_memory_paths,
    normalize_progress_state,
    read_json,
    read_jsonl,
)
from madspec_cli.shared.kernel.result import PayloadResult

if TYPE_CHECKING:
    from madspec_cli.shared.kernel.ports import DefaultBaseBranchResolver

BRANCH_STAGE_KEYS = (
    "mvp.concept",
    "mvp.design",
    "mvp.tech",
    "deploy",
    "mvp.architecture",
    "mvp.plan",
    "feature.init",
    "feature.plan",
)

SEMANTIC_KIND_PATHS = {
    "fact": "facts",
    "decision": "decisions",
    "contract": "contracts",
}

EMPTY_STEP_STATE = {
    "planned": False,
    "completed": False,
    "status": {},
    "metadata": {},
    "covers": {},
    "dependencies": [],
}


@dataclass(frozen=True)
class CompareBranchesRequest:
    project_path: Path
    source_branch: str
    target_branch: str
    base_branch: str | None


@dataclass(frozen=True)
class CompareBranchesResult(PayloadResult):
    pass


def execute(request: CompareBranchesRequest) -> CompareBranchesResult:
    base_branch = resolve_base_branch(
        request.project_path,
        source_branch=request.source_branch,
        target_branch=request.target_branch,
        explicit_base_branch=request.base_branch,
    )
    payload = compare_branch_memory(
        request.project_path,
        source_branch=request.source_branch,
        target_branch=request.target_branch,
        base_branch=base_branch,
    )
    return CompareBranchesResult(payload=payload)


def resolve_base_branch(
    project_path: Path,
    *,
    source_branch: str,
    target_branch: str,
    explicit_base_branch: str | None,
    _resolve_default_base_branch: DefaultBaseBranchResolver | None = None,
) -> str | None:
    if explicit_base_branch:
        candidate_dir = project_path / ".madspec" / explicit_base_branch
        if not candidate_dir.exists():
            raise ValueError(f"base branch '{explicit_base_branch}' does not have MADSpec artifacts")
        return explicit_base_branch

    if _resolve_default_base_branch is None:
        from madspec_cli.features.change.infrastructure.storage import resolve_default_base_branch
        _resolve_default_base_branch = resolve_default_base_branch
    candidates: list[str] = []
    try:
        candidates.append(_resolve_default_base_branch(project_path))
    except Exception:
        pass
    candidates.extend(["main", "master"])
    seen: set[str] = set()
    for candidate in candidates:
        if not candidate or candidate in seen:
            continue
        seen.add(candidate)
        if candidate in {source_branch, target_branch}:
            continue
        if (project_path / ".madspec" / candidate).exists():
            return candidate
    return None


def compare_branch_memory(
    project_path: Path,
    *,
    source_branch: str,
    target_branch: str,
    base_branch: str | None,
) -> dict[str, Any]:
    source_state = load_branch_memory_state(project_path, source_branch)
    target_state = load_branch_memory_state(project_path, target_branch)
    base_state = load_branch_memory_state(project_path, base_branch) if base_branch else None

    warnings: list[str] = []
    if base_branch is None:
        warnings.append("base branch was not resolved; comparison falls back to a conservative two-way diff")

    auto_actions: list[dict[str, Any]] = []
    conflicts: list[dict[str, Any]] = []

    snapshot_diff = _compare_snapshots(source_state, target_state, base_state)
    progress_diff = _compare_progress(source_state, target_state, base_state)
    semantic_diff = _compare_semantic(source_state, target_state, base_state)

    auto_actions.extend(snapshot_diff["auto_actions"])
    auto_actions.extend(progress_diff["auto_actions"])
    auto_actions.extend(semantic_diff["auto_actions"])
    conflicts.extend(snapshot_diff["conflicts"])
    conflicts.extend(progress_diff["conflicts"])
    conflicts.extend(semantic_diff["conflicts"])

    return {
        "sourceBranch": source_branch,
        "targetBranch": target_branch,
        "baseBranch": base_branch,
        "summary": {
            "autoActionCount": len(auto_actions),
            "conflictCount": len(conflicts),
            "blockingConflictCount": sum(1 for item in conflicts if item.get("blocking")),
            "snapshotActions": len(snapshot_diff["auto_actions"]),
            "progressActions": len(progress_diff["auto_actions"]),
            "semanticActions": len(semantic_diff["auto_actions"]),
        },
        "differences": {
            "stageSnapshots": snapshot_diff["differences"],
            "progress": progress_diff["differences"],
            "semantic": semantic_diff["differences"],
        },
        "autoActions": auto_actions,
        "conflicts": conflicts,
        "warnings": warnings,
    }


def load_branch_memory_state(project_path: Path, branch_name: str | None) -> dict[str, Any]:
    if not branch_name:
        return {
            "branch": None,
            "progress": _default_progress_state(),
            "stage_snapshots": {},
            "semantic": {kind: {} for kind in SEMANTIC_KIND_PATHS},
            "excluded_counts": {kind: {} for kind in SEMANTIC_KIND_PATHS},
        }
    branch_dir = project_path / ".madspec" / branch_name
    if not branch_dir.exists():
        raise ValueError(f"branch '{branch_name}' does not have MADSpec artifacts")

    paths = get_memory_paths(project_path, branch_name)
    progress = read_json(paths.progress, _default_progress_state())
    if not isinstance(progress, dict):
        progress = _default_progress_state()
    progress, _ = normalize_progress_state(progress)

    stage_snapshot_paths = {
        "mvp.concept": paths.concept_state,
        "mvp.design": paths.design_state,
        "mvp.tech": paths.tech_state,
        "deploy": paths.deploy_state,
        "mvp.architecture": paths.architecture_state,
        "mvp.plan": paths.plan_state,
        "feature.init": paths.feature_init_state,
        "feature.plan": paths.feature_plan_state,
    }
    stage_snapshots: dict[str, dict[str, Any]] = {}
    for stage_name, path in stage_snapshot_paths.items():
        payload = read_json(path, {}) if path.exists() else {}
        if not isinstance(payload, dict):
            payload = {}
        comparison_payload = _snapshot_comparison_payload(payload)
        stage_snapshots[stage_name] = {
            "exists": path.exists(),
            "payload": payload,
            "hash": _hash_json(comparison_payload) if comparison_payload else None,
        }

    semantic: dict[str, dict[str, dict[str, Any]]] = {kind: {} for kind in SEMANTIC_KIND_PATHS}
    excluded_counts: dict[str, dict[str, int]] = {kind: {} for kind in SEMANTIC_KIND_PATHS}
    for semantic_kind, path_attr in SEMANTIC_KIND_PATHS.items():
        for record in read_jsonl(getattr(paths, path_attr)):
            if not isinstance(record, dict):
                continue
            status = str(record.get("status") or "proposed")
            if status != "validated":
                excluded_counts[semantic_kind][status] = excluded_counts[semantic_kind].get(status, 0) + 1
                continue
            fingerprint = semantic_fingerprint(record)
            semantic[semantic_kind][fingerprint] = {
                "record": record,
                "fingerprint": fingerprint,
                "content_hash": semantic_content_hash(record),
            }

    return {
        "branch": branch_name,
        "progress": progress,
        "stage_snapshots": stage_snapshots,
        "semantic": semantic,
        "excluded_counts": excluded_counts,
    }


def _snapshot_comparison_payload(payload: dict[str, Any]) -> dict[str, Any]:
    def _normalize(value: Any) -> Any:
        if isinstance(value, dict):
            normalized: dict[str, Any] = {}
            for key, item in value.items():
                if key in {"createdAt", "updatedAt", "ratifiedAt", "revision", "schemaVersion"}:
                    continue
                normalized_item = _normalize(item)
                if normalized_item in (None, "", [], {}):
                    continue
                normalized[key] = normalized_item
            return normalized
        if isinstance(value, list):
            normalized_items = [_normalize(item) for item in value]
            return [item for item in normalized_items if item not in (None, "", [], {})]
        return value

    normalized = _normalize(payload)
    return normalized if isinstance(normalized, dict) else {}


def _compare_snapshots(
    source_state: dict[str, Any],
    target_state: dict[str, Any],
    base_state: dict[str, Any] | None,
) -> dict[str, Any]:
    auto_actions: list[dict[str, Any]] = []
    conflicts: list[dict[str, Any]] = []
    differences = {"incoming": [], "conflicts": []}
    for stage_name in BRANCH_STAGE_KEYS:
        source_item = source_state["stage_snapshots"].get(stage_name, {})
        target_item = target_state["stage_snapshots"].get(stage_name, {})
        base_item = (base_state or {}).get("stage_snapshots", {}).get(stage_name, {})
        source_hash = source_item.get("hash")
        target_hash = target_item.get("hash")
        base_hash = base_item.get("hash")
        if not source_hash or source_hash == target_hash:
            continue

        source_changed = source_hash != base_hash
        target_changed = target_hash != base_hash
        action = {
            "actionId": f"snapshot:{stage_name}",
            "kind": "snapshot_merge",
            "section": "stageSnapshots",
            "subject": stage_name,
            "sourceHash": source_hash,
            "targetHash": target_hash,
            "baseHash": base_hash,
        }
        if base_state is not None and not source_changed:
            continue
        if (base_state is not None and not target_changed and source_changed) or (base_state is None and not target_hash):
            merged = {**action, "operation": "take_source"}
            auto_actions.append(merged)
            differences["incoming"].append(merged)
            continue

        conflict = {
            "conflictId": make_conflict_id("snapshot_conflict", "stageSnapshots", stage_name),
            "kind": "snapshot_conflict",
            "section": "stageSnapshots",
            "subject": stage_name,
            "blocking": True,
            "allowedResolutions": ["keep_target", "take_source", *([] if base_state is None else ["take_base"])],
            "resolution": None,
            "sourceHash": source_hash,
            "targetHash": target_hash,
            "baseHash": base_hash,
        }
        conflicts.append(conflict)
        differences["conflicts"].append(conflict)
    return {"auto_actions": auto_actions, "conflicts": conflicts, "differences": differences}


def _compare_progress(
    source_state: dict[str, Any],
    target_state: dict[str, Any],
    base_state: dict[str, Any] | None,
) -> dict[str, Any]:
    source_progress = source_state["progress"]
    target_progress = target_state["progress"]
    base_progress = (base_state or {}).get("progress", _default_progress_state())
    auto_actions: list[dict[str, Any]] = []
    conflicts: list[dict[str, Any]] = []
    differences = {"incoming": [], "conflicts": []}

    step_ids = sorted(
        set(source_progress.get("plannedSteps", []))
        | set(source_progress.get("completedSteps", []))
        | set(source_progress.get("stepStatus", {}))
        | set(source_progress.get("stepMetadata", {}))
        | set(source_progress.get("coversFunctions", {}))
        | set(source_progress.get("planningMetadata", {}).get("stepDependencies", {}))
        | set(target_progress.get("plannedSteps", []))
        | set(target_progress.get("completedSteps", []))
        | set(target_progress.get("stepStatus", {}))
        | set(target_progress.get("stepMetadata", {}))
        | set(target_progress.get("coversFunctions", {}))
        | set(target_progress.get("planningMetadata", {}).get("stepDependencies", {}))
    )
    for step_id in step_ids:
        source_step = _extract_step_state(source_progress, step_id)
        target_step = _extract_step_state(target_progress, step_id)
        base_step = _extract_step_state(base_progress, step_id)
        if _hash_json(source_step) == _hash_json(target_step) or _is_empty_step_state(source_step):
            continue

        source_changed = _hash_json(source_step) != _hash_json(base_step)
        target_changed = _hash_json(target_step) != _hash_json(base_step)
        allowed_resolutions = ["keep_target", "take_source", *([] if base_state is None else ["take_base"])]
        if _progress_union_safe(source_step, target_step):
            allowed_resolutions.append("union")

        action = {
            "actionId": f"progress:{step_id}",
            "kind": "progress_step_merge",
            "section": "progress",
            "subject": step_id,
            "sourceState": source_step,
            "targetState": target_step,
            "baseState": base_step,
        }
        if base_state is not None and not source_changed:
            continue
        if (base_state is not None and not target_changed and source_changed) or (
            base_state is None and _is_empty_step_state(target_step)
        ):
            merged = {**action, "operation": "take_source"}
            auto_actions.append(merged)
            differences["incoming"].append(merged)
            continue
        if base_state is not None and _progress_union_safe(source_step, target_step):
            merged = {**action, "operation": "union"}
            auto_actions.append(merged)
            differences["incoming"].append(merged)
            continue

        conflict = {
            "conflictId": make_conflict_id("progress_conflict", "progress", step_id),
            "kind": "progress_conflict",
            "section": "progress",
            "subject": step_id,
            "blocking": True,
            "allowedResolutions": allowed_resolutions,
            "resolution": None,
            "sourceState": source_step,
            "targetState": target_step,
            "baseState": base_step,
        }
        conflicts.append(conflict)
        differences["conflicts"].append(conflict)

    current_step_action = _compare_current_step(source_progress, target_progress, base_progress, base_state is not None)
    if current_step_action is not None:
        if current_step_action.get("operation"):
            auto_actions.append(current_step_action)
            differences["incoming"].append(current_step_action)
        else:
            conflict = current_step_action["conflict"]
            conflicts.append(conflict)
            differences["conflicts"].append(conflict)
    return {"auto_actions": auto_actions, "conflicts": conflicts, "differences": differences}


def _compare_current_step(
    source_progress: dict[str, Any],
    target_progress: dict[str, Any],
    base_progress: dict[str, Any],
    has_base: bool,
) -> dict[str, Any] | None:
    source_step = source_progress.get("currentImplementStep")
    target_step = target_progress.get("currentImplementStep")
    base_step = base_progress.get("currentImplementStep")
    if not source_step or source_step == target_step:
        return None
    source_changed = source_step != base_step
    target_changed = target_step != base_step
    base_resolutions = ["keep_target", "take_source", *(["take_base"] if has_base else [])]
    if not has_base and not target_step:
        return {
            "actionId": "progress:__current_step__",
            "kind": "progress_current_step",
            "section": "progress",
            "subject": "currentImplementStep",
            "operation": "take_source",
            "sourceValue": source_step,
            "targetValue": target_step,
            "baseValue": base_step,
        }
    if has_base and source_changed and not target_changed:
        return {
            "actionId": "progress:__current_step__",
            "kind": "progress_current_step",
            "section": "progress",
            "subject": "currentImplementStep",
            "operation": "take_source",
            "sourceValue": source_step,
            "targetValue": target_step,
            "baseValue": base_step,
        }
    allowed = list(base_resolutions)
    if not source_step or not target_step:
        allowed.append("union")
    return {
        "conflict": {
            "conflictId": make_conflict_id("progress_conflict", "progress", "currentImplementStep"),
            "kind": "progress_conflict",
            "section": "progress",
            "subject": "currentImplementStep",
            "blocking": True,
            "allowedResolutions": allowed,
            "resolution": None,
            "sourceValue": source_step,
            "targetValue": target_step,
            "baseValue": base_step,
        }
    }


def _compare_semantic(
    source_state: dict[str, Any],
    target_state: dict[str, Any],
    base_state: dict[str, Any] | None,
) -> dict[str, Any]:
    auto_actions: list[dict[str, Any]] = []
    conflicts: list[dict[str, Any]] = []
    differences = {
        "facts": {"incoming": [], "conflicts": [], "excluded": source_state["excluded_counts"]["fact"]},
        "decisions": {"incoming": [], "conflicts": [], "excluded": source_state["excluded_counts"]["decision"]},
        "contracts": {"incoming": [], "conflicts": [], "excluded": source_state["excluded_counts"]["contract"]},
    }
    for semantic_kind, label in (("fact", "facts"), ("decision", "decisions"), ("contract", "contracts")):
        source_records = source_state["semantic"][semantic_kind]
        target_records = target_state["semantic"][semantic_kind]
        base_records = (base_state or {}).get("semantic", {}).get(semantic_kind, {})
        for fingerprint, source_entry in source_records.items():
            target_entry = target_records.get(fingerprint)
            base_entry = base_records.get(fingerprint)
            if target_entry and source_entry["content_hash"] == target_entry["content_hash"]:
                continue

            source_changed = base_entry is None or source_entry["content_hash"] != base_entry["content_hash"]
            target_changed = target_entry is not None and (
                base_entry is None or target_entry["content_hash"] != base_entry["content_hash"]
            )
            action = {
                "actionId": f"semantic:{semantic_kind}:{fingerprint}",
                "kind": "semantic_merge",
                "section": "semantic",
                "semanticKind": semantic_kind,
                "subject": fingerprint,
                "summary": source_entry["record"].get("summary"),
                "sourceHash": source_entry["content_hash"],
                "targetHash": target_entry["content_hash"] if target_entry else None,
                "baseHash": base_entry["content_hash"] if base_entry else None,
            }
            if target_entry is None:
                merged = {**action, "operation": "take_source"}
                auto_actions.append(merged)
                differences[label]["incoming"].append(merged)
                continue
            if base_state is not None and not source_changed:
                continue
            if base_state is not None and source_changed and not target_changed:
                merged = {**action, "operation": "take_source"}
                auto_actions.append(merged)
                differences[label]["incoming"].append(merged)
                continue

            conflict = {
                "conflictId": make_conflict_id("semantic_conflict", semantic_kind, fingerprint),
                "kind": "semantic_conflict",
                "section": "semantic",
                "semanticKind": semantic_kind,
                "subject": fingerprint,
                "blocking": True,
                "allowedResolutions": [
                    "keep_target",
                    "take_source",
                    *([] if base_state is None else ["take_base"]),
                    "union",
                ],
                "resolution": None,
                "summary": source_entry["record"].get("summary"),
                "sourceHash": source_entry["content_hash"],
                "targetHash": target_entry["content_hash"],
                "baseHash": base_entry["content_hash"] if base_entry else None,
            }
            conflicts.append(conflict)
            differences[label]["conflicts"].append(conflict)
    return {"auto_actions": auto_actions, "conflicts": conflicts, "differences": differences}


def _extract_step_state(progress: dict[str, Any], step_id: str) -> dict[str, Any]:
    dependencies = progress.get("planningMetadata", {}).get("stepDependencies", {}).get(step_id, [])
    return {
        "planned": step_id in progress.get("plannedSteps", []),
        "completed": step_id in progress.get("completedSteps", []),
        "status": dict(progress.get("stepStatus", {}).get(step_id, {})),
        "metadata": dict(progress.get("stepMetadata", {}).get(step_id, {})),
        "covers": dict(progress.get("coversFunctions", {}).get(step_id, {})),
        "dependencies": list(dependencies) if isinstance(dependencies, list) else [],
    }


def _is_empty_step_state(value: dict[str, Any]) -> bool:
    return value == EMPTY_STEP_STATE


def _progress_union_safe(source_state: dict[str, Any], target_state: dict[str, Any]) -> bool:
    if source_state["status"] and target_state["status"] and source_state["status"] != target_state["status"]:
        return False
    if source_state["metadata"] and target_state["metadata"] and source_state["metadata"] != target_state["metadata"]:
        return False
    return True


def _hash_json(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, ensure_ascii=False, sort_keys=True).encode("utf-8")
    ).hexdigest()
