from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from ...shared.text_lists import normalize_plain_text_list
from ...shared.storage import PRIORITIES, now_iso, read_json, write_json

PLAN_STAGE = "mvp.plan"
PLAN_SCHEMA_VERSION = 1
STEP_ARTIFACT_FILES = ("description.md", "tasks.md", "tests.md", "validation.md")
STEP_SIZES = {"unknown", "small", "medium", "large"}
STEP_COMPLEXITIES = {"unknown", "low", "medium", "high"}


def default_plan_state() -> dict[str, Any]:
    ts = now_iso()
    return {
        "schemaVersion": PLAN_SCHEMA_VERSION,
        "planOverview": "",
        "planningPrinciples": [],
        "stepCatalog": [],
        "nextActions": [],
        "checkpointSummary": "",
        "createdAt": ts,
        "ratifiedAt": None,
        "updatedAt": ts,
        "revision": 0,
    }


def _normalize_string(value: Any) -> str:
    if not isinstance(value, str):
        return ""
    return re.sub(r"\s+", " ", value).strip()


def _normalize_string_list(values: Any) -> list[str]:
    return normalize_plain_text_list(values, normalize_item=_normalize_string)


def _normalize_step_covers(value: Any) -> dict[str, list[str]]:
    normalized = {priority: [] for priority in PRIORITIES}
    if not isinstance(value, dict):
        return normalized
    for priority in PRIORITIES:
        normalized[priority] = _normalize_string_list(value.get(priority, []))
    return normalized


def _normalize_related_artifacts(value: Any) -> list[str]:
    return _normalize_string_list(value)


def _normalize_step_entry(value: Any) -> dict[str, Any] | None:
    if not isinstance(value, dict):
        return None

    step_id = _normalize_string(value.get("stepId"))
    if not step_id:
        return None

    step_kind = _normalize_string(value.get("stepKind")).lower() or "code"
    if step_kind not in {"code", "non-code"}:
        step_kind = "code"

    tdd_policy = _normalize_string(value.get("tddPolicy")) or (
        "required" if step_kind == "code" else "not-applicable"
    )
    if tdd_policy not in {"required", "waived", "not-applicable"}:
        tdd_policy = "required" if step_kind == "code" else "not-applicable"

    waiver_reason = _normalize_string(value.get("waiverReason")) or None
    if tdd_policy != "waived":
        waiver_reason = None

    size = _normalize_string(value.get("size")).lower() or "unknown"
    if size not in STEP_SIZES:
        size = "unknown"

    complexity = _normalize_string(value.get("complexity")).lower() or "unknown"
    if complexity not in STEP_COMPLEXITIES:
        complexity = "unknown"

    normalized = {
        "stepId": step_id,
        "title": _normalize_string(value.get("title")) or _derive_step_title(step_id),
        "summary": _normalize_string(value.get("summary")),
        "stepKind": step_kind,
        "tddPolicy": tdd_policy,
        "waiverReason": waiver_reason,
        "covers": _normalize_step_covers(value.get("covers", {})),
        "dependsOn": _normalize_string_list(value.get("dependsOn", [])),
        "relatedArtifacts": _normalize_related_artifacts(value.get("relatedArtifacts", [])),
        "size": size,
        "complexity": complexity,
    }
    return normalized


def normalize_plan_state(state: Any) -> tuple[dict[str, Any], bool]:
    default_state = default_plan_state()
    if not isinstance(state, dict):
        return default_state, True

    normalized = dict(default_state)
    changed = False

    normalized["schemaVersion"] = PLAN_SCHEMA_VERSION
    if state.get("schemaVersion") != PLAN_SCHEMA_VERSION:
        changed = True

    for key in ("planOverview", "checkpointSummary", "createdAt"):
        normalized[key] = _normalize_string(state.get(key, default_state[key]))
        if normalized[key] != state.get(key):
            changed = True

    for key in ("ratifiedAt", "updatedAt"):
        value = state.get(key, default_state[key])
        if value is not None and not isinstance(value, str):
            value = default_state[key]
            changed = True
        normalized[key] = _normalize_string(value) if isinstance(value, str) else value
        if normalized[key] != state.get(key):
            changed = True

    revision = state.get("revision", default_state["revision"])
    if not isinstance(revision, int) or revision < 0:
        revision = default_state["revision"]
        changed = True
    normalized["revision"] = revision
    if normalized["revision"] != state.get("revision"):
        changed = True

    normalized["planningPrinciples"] = _normalize_string_list(state.get("planningPrinciples", []))
    if normalized["planningPrinciples"] != state.get("planningPrinciples"):
        changed = True

    normalized["nextActions"] = _normalize_string_list(state.get("nextActions", []))
    if normalized["nextActions"] != state.get("nextActions"):
        changed = True

    entries = state.get("stepCatalog", [])
    if not isinstance(entries, list):
        entries = []
        changed = True
    seen: set[str] = set()
    normalized_entries: list[dict[str, Any]] = []
    for item in entries:
        normalized_entry = _normalize_step_entry(item)
        if normalized_entry is None:
            changed = True
            continue
        if normalized_entry["stepId"] in seen:
            changed = True
            continue
        seen.add(normalized_entry["stepId"])
        normalized_entries.append(normalized_entry)
        if normalized_entry != item:
            changed = True
    normalized["stepCatalog"] = normalized_entries
    return normalized, changed


def load_plan_state(path: Path) -> dict[str, Any]:
    state = read_json(path, default_plan_state())
    normalized, _ = normalize_plan_state(state)
    return normalized


def save_plan_state(path: Path, state: dict[str, Any]) -> None:
    normalized, _ = normalize_plan_state(state)
    write_json(path, normalized)


def append_unique_strings(target: list[str], values: list[str]) -> list[str]:
    result = list(target)
    for value in values:
        if value not in result:
            result.append(value)
    return result


def migrate_legacy_plan_state(
    *,
    progress: dict[str, Any],
    implementation_plan_path: Path,
    steps_dir: Path,
) -> dict[str, Any]:
    state = default_plan_state()
    overview = ""
    if implementation_plan_path.exists():
        text = implementation_plan_path.read_text(encoding="utf-8")
        match = re.search(r"## Обзор\s+(.*?)(?:\n## |\Z)", text, flags=re.DOTALL)
        if match:
            overview = _normalize_string(match.group(1))
    if overview:
        state["planOverview"] = overview

    step_metadata = progress.get("stepMetadata", {})
    step_dependencies = progress.get("planningMetadata", {}).get("stepDependencies", {})
    covers_functions = progress.get("coversFunctions", {})
    for step_id in progress.get("plannedSteps", []):
        metadata = step_metadata.get(step_id, {})
        state = upsert_step_catalog_entry(
            state,
            step_id=step_id,
            title=_derive_step_title(step_id),
            summary="",
            step_kind=metadata.get("kind", "code"),
            tdd_policy=metadata.get("tddPolicy"),
            waiver_reason=metadata.get("waiverReason"),
            covers=covers_functions.get(step_id, {priority: [] for priority in PRIORITIES}),
            depends_on=step_dependencies.get(step_id, []),
            related_artifacts=[],
        )

    if steps_dir.exists():
        for step_dir in sorted(path for path in steps_dir.iterdir() if path.is_dir()):
            state = upsert_step_catalog_entry(state, step_id=step_dir.name)

    return state


def _derive_step_title(step_id: str) -> str:
    parts = step_id.split("-", 2)
    if len(parts) < 3:
        return step_id
    return parts[2].replace("-", " ").strip().title() or step_id


def upsert_step_catalog_entry(
    state: dict[str, Any],
    *,
    step_id: str,
    title: str | None = None,
    summary: str | None = None,
    step_kind: str = "code",
    tdd_policy: str | None = None,
    waiver_reason: str | None = None,
    covers: dict[str, list[str]] | None = None,
    depends_on: list[str] | None = None,
    related_artifacts: list[str] | None = None,
    size: str | None = None,
    complexity: str | None = None,
) -> dict[str, Any]:
    normalized, _ = normalize_plan_state(state)
    normalized_step_id = _normalize_string(step_id)
    if not normalized_step_id:
        return normalized

    entry = _normalize_step_entry(
        {
            "stepId": normalized_step_id,
            "title": title or _derive_step_title(normalized_step_id),
            "summary": summary or "",
            "stepKind": step_kind,
            "tddPolicy": tdd_policy,
            "waiverReason": waiver_reason,
            "covers": covers or {priority: [] for priority in PRIORITIES},
            "dependsOn": depends_on or [],
            "relatedArtifacts": related_artifacts or [],
            "size": size or "unknown",
            "complexity": complexity or "unknown",
        }
    )
    if entry is None:
        return normalized

    updated_catalog: list[dict[str, Any]] = []
    replaced = False
    for item in normalized["stepCatalog"]:
        if item.get("stepId") == normalized_step_id:
            updated_catalog.append(entry)
            replaced = True
        else:
            updated_catalog.append(item)
    if not replaced:
        updated_catalog.append(entry)
    normalized["stepCatalog"] = updated_catalog
    normalized["updatedAt"] = now_iso()
    return normalized


def update_plan_state(
    state: dict[str, Any],
    *,
    plan_overview: str | None = None,
    planning_principles: list[str] | None = None,
    next_actions: list[str] | None = None,
    checkpoint_summary: str | None = None,
    ratify: bool = False,
) -> dict[str, Any]:
    normalized, _ = normalize_plan_state(state)
    if plan_overview and plan_overview.strip():
        normalized["planOverview"] = _normalize_string(plan_overview)
    normalized["planningPrinciples"] = append_unique_strings(
        normalized["planningPrinciples"],
        planning_principles or [],
    )
    normalized["nextActions"] = append_unique_strings(normalized["nextActions"], next_actions or [])
    ts = now_iso()
    normalized["updatedAt"] = ts
    if checkpoint_summary is not None:
        normalized["checkpointSummary"] = _normalize_string(checkpoint_summary)
    if ratify:
        normalized["ratifiedAt"] = ts
        normalized["revision"] = int(normalized.get("revision", 0)) + 1
    return normalized


def is_empty_plan_state(state: dict[str, Any]) -> bool:
    normalized, _ = normalize_plan_state(state)
    return not any(
        [
            normalized["planOverview"],
            normalized["planningPrinciples"],
            normalized["stepCatalog"],
            normalized["nextActions"],
            normalized["checkpointSummary"],
            normalized["revision"],
            normalized["ratifiedAt"],
        ]
    )


def _step_catalog_errors(step_catalog: list[dict[str, Any]]) -> list[str]:
    errors: list[str] = []
    for item in step_catalog:
        step_id = item["stepId"]
        if not item["title"]:
            errors.append(f"plan step '{step_id}' must include a title")
        if item["stepKind"] not in {"code", "non-code"}:
            errors.append(f"plan step '{step_id}' has invalid stepKind")
        if item["stepKind"] == "code" and item["tddPolicy"] != "required":
            errors.append(f"plan step '{step_id}' must use tddPolicy='required' for code steps")
        if item["stepKind"] == "non-code" and item["tddPolicy"] == "required":
            errors.append(f"plan step '{step_id}' cannot use tddPolicy='required' for non-code steps")
        if item["tddPolicy"] == "waived" and not item["waiverReason"]:
            errors.append(f"plan step '{step_id}' requires waiverReason when tddPolicy='waived'")
        if item["size"] not in STEP_SIZES:
            errors.append(f"plan step '{step_id}' has invalid size")
        if item["complexity"] not in STEP_COMPLEXITIES:
            errors.append(f"plan step '{step_id}' has invalid complexity")
    return errors


def plan_schema_errors(state: Any) -> list[str]:
    normalized, changed = normalize_plan_state(state)
    errors = _step_catalog_errors(normalized["stepCatalog"])
    if changed and not isinstance(state, dict):
        errors.append("plan state must contain a JSON object")
    return errors


def plan_completeness_errors(state: dict[str, Any]) -> list[str]:
    normalized, _ = normalize_plan_state(state)
    errors: list[str] = []
    if not normalized["planOverview"]:
        errors.append("plan state must include a plan overview before checkpoint")
    if not normalized["stepCatalog"]:
        errors.append("plan state must include at least one step before checkpoint")
    errors.extend(_step_catalog_errors(normalized["stepCatalog"]))
    return errors


def plan_reference_errors(
    state: dict[str, Any],
    *,
    project_path: Path,
    branch_name: str,
    progress: dict[str, Any],
) -> list[str]:
    normalized, _ = normalize_plan_state(state)
    errors: list[str] = []
    step_catalog = {item["stepId"]: item for item in normalized["stepCatalog"]}
    planned_steps = progress.get("plannedSteps", [])
    step_metadata = progress.get("stepMetadata", {})
    step_dependencies = progress.get("planningMetadata", {}).get("stepDependencies", {})
    covers_functions = progress.get("coversFunctions", {})
    branch_dir = project_path / ".madspec" / branch_name

    for step_id in planned_steps:
        if step_id not in step_catalog:
            errors.append(f"mvp.plan.json is missing planned step '{step_id}' from progress.json")

    for step_id, item in step_catalog.items():
        step_dir = branch_dir / "steps" / step_id
        if not step_dir.exists():
            errors.append(f"plan step '{step_id}' is missing steps/{step_id}/ directory")
            continue
        for file_name in STEP_ARTIFACT_FILES:
            if not (step_dir / file_name).exists():
                errors.append(f"plan step '{step_id}' is missing steps/{step_id}/{file_name}")

        progress_metadata = step_metadata.get(step_id, {})
        if progress_metadata:
            if item["stepKind"] != progress_metadata.get("kind"):
                errors.append(f"plan step '{step_id}' stepKind is out of sync with progress.json")
            if item["tddPolicy"] != progress_metadata.get("tddPolicy"):
                errors.append(f"plan step '{step_id}' tddPolicy is out of sync with progress.json")
            if item["waiverReason"] != progress_metadata.get("waiverReason"):
                errors.append(f"plan step '{step_id}' waiverReason is out of sync with progress.json")

        if item["dependsOn"] != step_dependencies.get(step_id, []):
            errors.append(f"plan step '{step_id}' dependsOn is out of sync with progress.json")
        if item["covers"] != covers_functions.get(step_id, {priority: [] for priority in PRIORITIES}):
            errors.append(f"plan step '{step_id}' covers is out of sync with progress.json")
    return errors


def render_implementation_plan_markdown(
    state: dict[str, Any],
    *,
    branch_name: str,
    progress: dict[str, Any],
    project_name: str,
) -> str:
    normalized, _ = normalize_plan_state(state)
    step_status = progress.get("stepStatus", {})
    completed_steps = set(progress.get("completedSteps", []))
    step_dependencies = progress.get("planningMetadata", {}).get("stepDependencies", {})
    metrics = progress.get("planningMetadata", {}).get("progressMetrics", {})
    title_project_name = project_name or "Проект"
    lines = [
        f"# План реализации: {title_project_name}",
        "",
        "> Generated from structured memory. Do not treat this file as the canonical source of truth.",
        "",
        f"**Основано на**: `.madspec/{branch_name}/memory/stages/mvp.plan.json`, `.madspec/{branch_name}/memory/progress.json`",
        f"**Последнее обновление**: `{normalized.get('updatedAt') or 'N/A'}`",
        f"**Статус плана**: `{'ratified' if normalized.get('ratifiedAt') else 'draft'}`",
        "",
        "## Обзор",
        normalized["planOverview"] or "Пока не зафиксировано.",
        "",
        "## Принципы планирования",
    ]
    if normalized["planningPrinciples"]:
        lines.extend(f"- {item}" for item in normalized["planningPrinciples"])
    else:
        lines.append("- Пока не зафиксировано.")
    lines.extend(
        [
            "",
            "## Метрики покрытия",
            f"- `P1`: {metrics.get('p1Coverage', {}).get('covered', 0)}/{metrics.get('p1Coverage', {}).get('total', 0)} ({metrics.get('p1Coverage', {}).get('percentage', 0)}%)",
            f"- `P2`: {metrics.get('p2Coverage', {}).get('covered', 0)}/{metrics.get('p2Coverage', {}).get('total', 0)} ({metrics.get('p2Coverage', {}).get('percentage', 0)}%)",
            f"- `P3`: {metrics.get('p3Coverage', {}).get('covered', 0)}/{metrics.get('p3Coverage', {}).get('total', 0)} ({metrics.get('p3Coverage', {}).get('percentage', 0)}%)",
            f"- `Overall`: {metrics.get('overallProgress', 0)}%",
            "",
            "## Шаги реализации",
        ]
    )
    if not normalized["stepCatalog"]:
        lines.append("Пока не зафиксировано.")
    for item in normalized["stepCatalog"]:
        step_id = item["stepId"]
        status = step_status.get(step_id, {}).get("status", "planned")
        tdd_phase = step_status.get(step_id, {}).get("tddPhase", "unknown")
        lines.extend(
            [
                f"### {item['title']}",
                "",
                f"- `stepId`: `{step_id}`",
                f"- `status`: `{status}`" + (" [completed]" if step_id in completed_steps else ""),
                f"- `kind`: `{item['stepKind']}`",
                f"- `tddPolicy`: `{item['tddPolicy']}`",
                f"- `tddPhase`: `{tdd_phase}`",
                f"- `size`: `{item['size']}`",
                f"- `complexity`: `{item['complexity']}`",
                f"- `dependsOn`: {', '.join(f'`{dep}`' for dep in item['dependsOn']) if item['dependsOn'] else 'нет'}",
                f"- `covers`: "
                + (
                    ", ".join(
                        f"{priority.upper()}={', '.join(values)}"
                        for priority, values in item["covers"].items()
                        if values
                    )
                    or "не указано"
                ),
                f"- `artifacts`: {', '.join(f'`{path}`' for path in item['relatedArtifacts']) if item['relatedArtifacts'] else 'не указано'}",
                f"- `details`: `.madspec/{branch_name}/steps/{step_id}/`",
            ]
        )
        if item["summary"]:
            lines.extend(["", item["summary"]])
        if item["waiverReason"]:
            lines.extend(["", f"Waiver: {item['waiverReason']}"])
        lines.append("")
    lines.extend(["## Граф зависимостей"])
    if step_dependencies:
        for step_id in sorted(step_dependencies):
            deps = step_dependencies.get(step_id, [])
            lines.append(f"- `{step_id}` <- {', '.join(f'`{dep}`' for dep in deps) if deps else 'нет'}")
    else:
        lines.append("- Пока не зафиксировано.")
    lines.extend(["", "## Следующие действия"])
    if normalized["nextActions"]:
        lines.extend(f"- {item}" for item in normalized["nextActions"])
    else:
        lines.append("- Пока не зафиксировано.")
    lines.extend(["", "## Checkpoint"])
    lines.append(normalized["checkpointSummary"] or "Пока не зафиксировано.")
    return "\n".join(lines) + "\n"
