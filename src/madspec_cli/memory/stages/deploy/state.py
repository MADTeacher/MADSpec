from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from ...shared.text_lists import normalize_plain_text_list
from ...shared.storage import now_iso, read_json, write_json

DEPLOY_STAGE = "deploy"
DEPLOY_SCHEMA_VERSION = 1
DEPLOY_SEPARATOR = "::"


def default_deploy_state() -> dict[str, Any]:
    ts = now_iso()
    return {
        "schemaVersion": DEPLOY_SCHEMA_VERSION,
        "deployOverview": "",
        "goals": [],
        "environments": [],
        "deploymentUnits": [],
        "configNotes": [],
        "secretNotes": [],
        "cicdTriggers": [],
        "cicdSteps": [],
        "releaseArtifacts": [],
        "migrationNotes": [],
        "backupNotes": [],
        "recoveryChecks": [],
        "observabilityNotes": [],
        "securityControls": [],
        "constraints": [],
        "releaseStrategy": "",
        "rollbackStrategy": "",
        "nextActions": [],
        "checkpointSummary": "",
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


def _normalize_environment_list(values: Any) -> list[dict[str, str]]:
    if not isinstance(values, list):
        return []
    normalized: list[dict[str, str]] = []
    seen: set[tuple[str, str, str]] = set()
    for item in values:
        if not isinstance(item, dict):
            continue
        entry = {
            "name": _normalize_string(item.get("name", "")),
            "purpose": _normalize_string(item.get("purpose", "")),
            "notes": _normalize_string(item.get("notes", "")),
        }
        if not all(entry.values()):
            continue
        marker = (entry["name"], entry["purpose"], entry["notes"])
        if marker in seen:
            continue
        seen.add(marker)
        normalized.append(entry)
    return normalized


def _normalize_deployment_unit_list(values: Any) -> list[dict[str, str]]:
    if not isinstance(values, list):
        return []
    normalized: list[dict[str, str]] = []
    seen: set[tuple[str, str, str, str]] = set()
    for item in values:
        if not isinstance(item, dict):
            continue
        entry = {
            "name": _normalize_string(item.get("name", "")),
            "kind": _normalize_string(item.get("kind", "")),
            "runtime": _normalize_string(item.get("runtime", "")),
            "notes": _normalize_string(item.get("notes", "")),
        }
        if not all(entry.values()):
            continue
        marker = (entry["name"], entry["kind"], entry["runtime"], entry["notes"])
        if marker in seen:
            continue
        seen.add(marker)
        normalized.append(entry)
    return normalized


def normalize_deploy_state(state: Any) -> tuple[dict[str, Any], bool]:
    default_state = default_deploy_state()
    if not isinstance(state, dict):
        return default_state, True

    normalized = dict(default_state)
    changed = False

    normalized["schemaVersion"] = DEPLOY_SCHEMA_VERSION
    if state.get("schemaVersion") != DEPLOY_SCHEMA_VERSION:
        changed = True

    for key in ("deployOverview", "releaseStrategy", "rollbackStrategy", "checkpointSummary"):
        normalized[key] = _normalize_string(state.get(key, default_state[key]))
        if normalized[key] != state.get(key):
            changed = True

    for key in ("ratifiedAt", "updatedAt"):
        value = state.get(key, default_state[key])
        normalized[key] = _normalize_string(value) if isinstance(value, str) else None
        if normalized[key] != state.get(key):
            changed = True

    revision = state.get("revision", 0)
    if not isinstance(revision, int) or revision < 0:
        revision = 0
        changed = True
    normalized["revision"] = revision
    if normalized["revision"] != state.get("revision"):
        changed = True

    for key in (
        "goals",
        "configNotes",
        "secretNotes",
        "cicdTriggers",
        "cicdSteps",
        "releaseArtifacts",
        "migrationNotes",
        "backupNotes",
        "recoveryChecks",
        "observabilityNotes",
        "securityControls",
        "constraints",
        "nextActions",
    ):
        normalized[key] = _normalize_string_list(state.get(key, default_state[key]))
        if normalized[key] != state.get(key):
            changed = True

    normalized["environments"] = _normalize_environment_list(state.get("environments", []))
    if normalized["environments"] != state.get("environments"):
        changed = True

    normalized["deploymentUnits"] = _normalize_deployment_unit_list(state.get("deploymentUnits", []))
    if normalized["deploymentUnits"] != state.get("deploymentUnits"):
        changed = True

    return normalized, changed


def load_deploy_state(path: Path) -> dict[str, Any]:
    state = read_json(path, default_deploy_state())
    normalized, _ = normalize_deploy_state(state)
    return normalized


def save_deploy_state(path: Path, state: dict[str, Any]) -> None:
    normalized, _ = normalize_deploy_state(state)
    write_json(path, normalized)


def parse_environment_value(value: str) -> dict[str, str] | None:
    parts = [part.strip() for part in value.split(DEPLOY_SEPARATOR, 2)]
    if len(parts) != 3 or not all(parts):
        return None
    return {
        "name": _normalize_string(parts[0]),
        "purpose": _normalize_string(parts[1]),
        "notes": _normalize_string(parts[2]),
    }


def parse_deployment_unit_value(value: str) -> dict[str, str] | None:
    parts = [part.strip() for part in value.split(DEPLOY_SEPARATOR, 3)]
    if len(parts) != 4 or not all(parts):
        return None
    return {
        "name": _normalize_string(parts[0]),
        "kind": _normalize_string(parts[1]),
        "runtime": _normalize_string(parts[2]),
        "notes": _normalize_string(parts[3]),
    }


def append_unique_strings(target: list[str], values: list[str]) -> list[str]:
    result = list(target)
    for value in values:
        if value not in result:
            result.append(value)
    return result


def _append_unique_dicts(target: list[dict[str, str]], values: list[dict[str, str]], keys: tuple[str, ...]) -> list[dict[str, str]]:
    result = list(target)
    seen = {tuple(item.get(key, "") for key in keys) for item in result}
    for value in values:
        marker = tuple(value.get(key, "") for key in keys)
        if marker in seen:
            continue
        seen.add(marker)
        result.append(value)
    return result


def update_deploy_state(
    state: dict[str, Any],
    *,
    deploy_overview: str | None = None,
    goals: list[str] | None = None,
    environments: list[dict[str, str]] | None = None,
    deployment_units: list[dict[str, str]] | None = None,
    config_notes: list[str] | None = None,
    secret_notes: list[str] | None = None,
    cicd_triggers: list[str] | None = None,
    cicd_steps: list[str] | None = None,
    release_artifacts: list[str] | None = None,
    migration_notes: list[str] | None = None,
    backup_notes: list[str] | None = None,
    recovery_checks: list[str] | None = None,
    observability_notes: list[str] | None = None,
    security_controls: list[str] | None = None,
    constraints: list[str] | None = None,
    release_strategy: str | None = None,
    rollback_strategy: str | None = None,
    next_actions: list[str] | None = None,
    checkpoint_summary: str | None = None,
    ratify: bool = False,
) -> dict[str, Any]:
    normalized, _ = normalize_deploy_state(state)
    if deploy_overview and deploy_overview.strip():
        normalized["deployOverview"] = _normalize_string(deploy_overview)
    if release_strategy and release_strategy.strip():
        normalized["releaseStrategy"] = _normalize_string(release_strategy)
    if rollback_strategy and rollback_strategy.strip():
        normalized["rollbackStrategy"] = _normalize_string(rollback_strategy)

    normalized["goals"] = append_unique_strings(normalized["goals"], goals or [])
    normalized["configNotes"] = append_unique_strings(normalized["configNotes"], config_notes or [])
    normalized["secretNotes"] = append_unique_strings(normalized["secretNotes"], secret_notes or [])
    normalized["cicdTriggers"] = append_unique_strings(normalized["cicdTriggers"], cicd_triggers or [])
    normalized["cicdSteps"] = append_unique_strings(normalized["cicdSteps"], cicd_steps or [])
    normalized["releaseArtifacts"] = append_unique_strings(normalized["releaseArtifacts"], release_artifacts or [])
    normalized["migrationNotes"] = append_unique_strings(normalized["migrationNotes"], migration_notes or [])
    normalized["backupNotes"] = append_unique_strings(normalized["backupNotes"], backup_notes or [])
    normalized["recoveryChecks"] = append_unique_strings(normalized["recoveryChecks"], recovery_checks or [])
    normalized["observabilityNotes"] = append_unique_strings(normalized["observabilityNotes"], observability_notes or [])
    normalized["securityControls"] = append_unique_strings(normalized["securityControls"], security_controls or [])
    normalized["constraints"] = append_unique_strings(normalized["constraints"], constraints or [])
    normalized["nextActions"] = append_unique_strings(normalized["nextActions"], next_actions or [])
    normalized["environments"] = _append_unique_dicts(normalized["environments"], environments or [], ("name", "purpose", "notes"))
    normalized["deploymentUnits"] = _append_unique_dicts(
        normalized["deploymentUnits"],
        deployment_units or [],
        ("name", "kind", "runtime", "notes"),
    )

    ts = now_iso()
    normalized["updatedAt"] = ts
    if checkpoint_summary is not None:
        normalized["checkpointSummary"] = _normalize_string(checkpoint_summary)
    if ratify:
        normalized["ratifiedAt"] = ts
        normalized["revision"] = int(normalized.get("revision", 0)) + 1
    return normalized


def is_empty_deploy_state(state: dict[str, Any]) -> bool:
    normalized, _ = normalize_deploy_state(state)
    return not any(
        [
            normalized["deployOverview"],
            normalized["goals"],
            normalized["environments"],
            normalized["deploymentUnits"],
            normalized["configNotes"],
            normalized["secretNotes"],
            normalized["cicdTriggers"],
            normalized["cicdSteps"],
            normalized["releaseArtifacts"],
            normalized["migrationNotes"],
            normalized["backupNotes"],
            normalized["recoveryChecks"],
            normalized["observabilityNotes"],
            normalized["securityControls"],
            normalized["constraints"],
            normalized["releaseStrategy"],
            normalized["rollbackStrategy"],
            normalized["nextActions"],
            normalized["checkpointSummary"],
            normalized["revision"],
            normalized["ratifiedAt"],
        ]
    )


def deploy_completeness_errors(state: dict[str, Any]) -> list[str]:
    normalized, _ = normalize_deploy_state(state)
    errors: list[str] = []
    if not normalized["deployOverview"]:
        errors.append("deploy state must include a deployment overview before checkpoint")
    if not normalized["goals"]:
        errors.append("deploy state must include at least one deployment goal before checkpoint")
    if not normalized["environments"]:
        errors.append("deploy state must include at least one environment before checkpoint")
    if not normalized["deploymentUnits"]:
        errors.append("deploy state must include at least one deployment unit before checkpoint")
    if not normalized["releaseStrategy"]:
        errors.append("deploy state must include a release strategy before checkpoint")
    if not normalized["rollbackStrategy"]:
        errors.append("deploy state must include a rollback strategy before checkpoint")
    return errors


def deploy_schema_errors(state: Any) -> list[str]:
    _, changed = normalize_deploy_state(state)
    errors: list[str] = []
    if changed and not isinstance(state, dict):
        errors.append("deploy state must contain a JSON object")
    return errors


def render_deployment_markdown(
    state: dict[str, Any],
    *,
    branch_name: str,
    project_name: str = "",
) -> str:
    normalized, _ = normalize_deploy_state(state)
    project_label = project_name or "Проект"

    def render_plain_list(values: list[str]) -> list[str]:
        if not values:
            return ["- Пока не зафиксировано."]
        return [f"- {value}" for value in values]

    lines = [
        f"# План развертывания: {project_label}",
        "",
        f"**Основано на**: `.madspec/{branch_name}/memory/stages/deploy.json`",
        "",
        "## Обзор",
        "",
        normalized["deployOverview"] or "Пока не зафиксировано.",
        "",
        "## Цели развертывания",
        "",
        *render_plain_list(normalized["goals"]),
        "",
        "## Окружения",
        "",
    ]
    if normalized["environments"]:
        for item in normalized["environments"]:
            lines.append(f"- **{item['name']}**: {item['purpose']}")
            lines.append(f"  - Особенности: {item['notes']}")
    else:
        lines.append("- Пока не зафиксировано.")

    lines.extend(["", "## Единицы развертывания", ""])
    if normalized["deploymentUnits"]:
        for item in normalized["deploymentUnits"]:
            lines.append(f"- **{item['name']}**")
            lines.append(f"  - Тип: {item['kind']}")
            lines.append(f"  - Среда выполнения: {item['runtime']}")
            lines.append(f"  - Примечания: {item['notes']}")
    else:
        lines.append("- Пока не зафиксировано.")

    lines.extend(["", "## Конфигурация", ""])
    lines.extend(render_plain_list(normalized["configNotes"]))
    lines.extend(["", "## Секреты", ""])
    lines.extend(render_plain_list(normalized["secretNotes"]))
    lines.extend(["", "## CI/CD", ""])
    lines.append("### Триггеры")
    lines.extend(render_plain_list(normalized["cicdTriggers"]))
    lines.extend(["", "### Шаги конвейера"])
    lines.extend(render_plain_list(normalized["cicdSteps"]))
    lines.extend(["", "### Артефакты релиза"])
    lines.extend(render_plain_list(normalized["releaseArtifacts"]))
    lines.extend(["", "## Миграции и резервное копирование", ""])
    lines.append("### Миграции")
    lines.extend(render_plain_list(normalized["migrationNotes"]))
    lines.extend(["", "### Резервное копирование"])
    lines.extend(render_plain_list(normalized["backupNotes"]))
    lines.extend(["", "### Проверка восстановления"])
    lines.extend(render_plain_list(normalized["recoveryChecks"]))
    lines.extend(["", "## Наблюдаемость", ""])
    lines.extend(render_plain_list(normalized["observabilityNotes"]))
    lines.extend(["", "## Безопасность и доступ", ""])
    lines.extend(render_plain_list(normalized["securityControls"]))
    lines.extend(
        [
            "",
            "## Стратегия релиза и отката",
            "",
            f"- **Стратегия релиза**: {normalized['releaseStrategy'] or 'Пока не зафиксировано.'}",
            f"- **Стратегия отката**: {normalized['rollbackStrategy'] or 'Пока не зафиксировано.'}",
            "",
            "## Ограничения",
            "",
            *render_plain_list(normalized["constraints"]),
            "",
            "## Следующие действия",
            "",
            *render_plain_list(normalized["nextActions"]),
            "",
            "## Checkpoint",
            "",
            normalized["checkpointSummary"] or "Пока не зафиксировано.",
            "",
            f"Версия: {normalized['revision']} | Ратифицирована: {normalized['ratifiedAt'] or 'Не указано'} | Последнее изменение: {normalized['updatedAt'] or 'Не указано'}",
            "",
        ]
    )
    return "\n".join(lines) + "\n"


from madspec_cli.memory.shared.stage_registry import register_stage_default, register_stage_loader, register_stage_validators, register_stage_renderers

register_stage_default("deploy", default_deploy_state)
register_stage_loader("deploy", load_deploy_state)
register_stage_validators("deploy", schema_errors=deploy_schema_errors)
register_stage_renderers("deploy", deployment=render_deployment_markdown)
