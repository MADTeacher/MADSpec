from __future__ import annotations

import re
from typing import Any

from ...shared.text_lists import normalize_plain_text_list
from ...shared.storage import now_iso, read_json, write_json

TECH_STAGE = "mvp.tech"
TECH_SCHEMA_VERSION = 1
TECH_KNOWN_SLOTS = (
    "language",
    "frontend",
    "backend",
    "database",
    "unit-testing",
    "integration-testing",
    "e2e-testing",
    "build",
    "deploy",
)


def _normalize_string(value: Any) -> str:
    if not isinstance(value, str):
        return ""
    return re.sub(r"\s+", " ", value).strip()


def _normalize_identifier(value: Any) -> str:
    normalized = _normalize_string(value).lower()
    if not normalized:
        return ""
    normalized = re.sub(r"[^a-z0-9]+", "-", normalized)
    return normalized.strip("-")


def _normalize_string_list(values: Any) -> list[str]:
    return normalize_plain_text_list(values, normalize_item=_normalize_string)


def _normalize_components(values: Any) -> list[dict[str, str]]:
    if not isinstance(values, list):
        return []
    result: list[dict[str, str]] = []
    seen: set[tuple[str, str, str, str]] = set()
    for item in values:
        if not isinstance(item, dict):
            continue
        normalized = {
            "slot": _normalize_identifier(item.get("slot", "")),
            "name": _normalize_string(item.get("name", "")),
            "version": _normalize_string(item.get("version", "")),
            "rationale": _normalize_string(item.get("rationale", "")),
        }
        if not all(normalized.values()):
            continue
        marker = tuple(normalized.values())
        if marker in seen:
            continue
        seen.add(marker)
        result.append(normalized)
    return result


def _normalize_libraries(values: Any) -> list[dict[str, str]]:
    if not isinstance(values, list):
        return []
    result: list[dict[str, str]] = []
    seen: set[tuple[str, str, str, str]] = set()
    for item in values:
        if not isinstance(item, dict):
            continue
        normalized = {
            "scope": _normalize_identifier(item.get("scope", "")),
            "name": _normalize_string(item.get("name", "")),
            "version": _normalize_string(item.get("version", "")),
            "purpose": _normalize_string(item.get("purpose", "")),
        }
        if not all(normalized.values()):
            continue
        marker = tuple(normalized.values())
        if marker in seen:
            continue
        seen.add(marker)
        result.append(normalized)
    return result


def _normalize_code_organization(value: Any) -> dict[str, str] | None:
    if not isinstance(value, dict):
        return None
    normalized = {
        "repoStrategy": _normalize_string(value.get("repoStrategy", "")),
        "sourceLayout": _normalize_string(value.get("sourceLayout", "")),
        "modularity": _normalize_string(value.get("modularity", "")),
        "rationale": _normalize_string(value.get("rationale", "")),
    }
    if not all(normalized.values()):
        return None
    return normalized


def _normalize_alternatives(values: Any) -> list[dict[str, str]]:
    if not isinstance(values, list):
        return []
    result: list[dict[str, str]] = []
    seen: set[tuple[str, str, str]] = set()
    for item in values:
        if not isinstance(item, dict):
            continue
        normalized = {
            "slot": _normalize_identifier(item.get("slot", "")),
            "option": _normalize_string(item.get("option", "")),
            "reasonRejected": _normalize_string(item.get("reasonRejected", "")),
        }
        if not all(normalized.values()):
            continue
        marker = tuple(normalized.values())
        if marker in seen:
            continue
        seen.add(marker)
        result.append(normalized)
    return result


def default_tech_state() -> dict[str, Any]:
    ts = now_iso()
    return {
        "schemaVersion": TECH_SCHEMA_VERSION,
        "revision": 0,
        "projectType": "",
        "stackOverview": "",
        "requirements": [],
        "preferences": [],
        "constraints": [],
        "components": [],
        "libraries": [],
        "codeOrganization": None,
        "alternatives": [],
        "nextActions": [],
        "checkpointSummary": "",
        "ratifiedAt": None,
        "updatedAt": ts,
    }


def normalize_tech_state(state: Any) -> tuple[dict[str, Any], bool]:
    default_state = default_tech_state()
    if not isinstance(state, dict):
        return default_state, True

    normalized = dict(default_state)
    changed = False

    normalized["schemaVersion"] = TECH_SCHEMA_VERSION
    if state.get("schemaVersion") != TECH_SCHEMA_VERSION:
        changed = True

    revision = state.get("revision", default_state["revision"])
    if not isinstance(revision, int) or revision < 0:
        revision = default_state["revision"]
        changed = True
    normalized["revision"] = revision
    if normalized["revision"] != state.get("revision"):
        changed = True

    for key in ("projectType", "stackOverview", "checkpointSummary"):
        normalized[key] = _normalize_string(state.get(key, default_state[key]))
        if normalized[key] != state.get(key):
            changed = True

    ratified_at = state.get("ratifiedAt", default_state["ratifiedAt"])
    if ratified_at is not None and not isinstance(ratified_at, str):
        ratified_at = default_state["ratifiedAt"]
        changed = True
    normalized["ratifiedAt"] = _normalize_string(ratified_at) if isinstance(ratified_at, str) else None
    if normalized["ratifiedAt"] != state.get("ratifiedAt"):
        changed = True

    updated_at = state.get("updatedAt", default_state["updatedAt"])
    if not isinstance(updated_at, str):
        updated_at = default_state["updatedAt"]
        changed = True
    normalized["updatedAt"] = _normalize_string(updated_at)
    if normalized["updatedAt"] != state.get("updatedAt"):
        changed = True

    for key in ("requirements", "preferences", "constraints", "nextActions"):
        normalized[key] = _normalize_string_list(state.get(key, default_state[key]))
        if normalized[key] != state.get(key):
            changed = True

    normalized["components"] = _normalize_components(state.get("components", default_state["components"]))
    if normalized["components"] != state.get("components"):
        changed = True

    normalized["libraries"] = _normalize_libraries(state.get("libraries", default_state["libraries"]))
    if normalized["libraries"] != state.get("libraries"):
        changed = True

    normalized["codeOrganization"] = _normalize_code_organization(
        state.get("codeOrganization", default_state["codeOrganization"])
    )
    if normalized["codeOrganization"] != state.get("codeOrganization"):
        changed = True

    normalized["alternatives"] = _normalize_alternatives(state.get("alternatives", default_state["alternatives"]))
    if normalized["alternatives"] != state.get("alternatives"):
        changed = True

    return normalized, changed


def load_tech_state(path) -> dict[str, Any]:
    state = read_json(path, default_tech_state())
    normalized, _ = normalize_tech_state(state)
    return normalized


def save_tech_state(path, state: dict[str, Any]) -> None:
    normalized, _ = normalize_tech_state(state)
    write_json(path, normalized)


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


def is_empty_tech_state(state: dict[str, Any]) -> bool:
    normalized, _ = normalize_tech_state(state)
    return not any(
        [
            normalized["projectType"],
            normalized["stackOverview"],
            normalized["requirements"],
            normalized["preferences"],
            normalized["constraints"],
            normalized["components"],
            normalized["libraries"],
            normalized["codeOrganization"],
            normalized["alternatives"],
            normalized["nextActions"],
            normalized["checkpointSummary"],
            normalized["revision"],
            normalized["ratifiedAt"],
        ]
    )


def parse_stack_component_value(value: str) -> dict[str, str] | None:
    parts = [segment.strip() for segment in value.split("::", 3)]
    if len(parts) != 4:
        return None
    normalized = {
        "slot": _normalize_identifier(parts[0]),
        "name": _normalize_string(parts[1]),
        "version": _normalize_string(parts[2]),
        "rationale": _normalize_string(parts[3]),
    }
    if not all(normalized.values()):
        return None
    return normalized


def parse_library_value(value: str) -> dict[str, str] | None:
    parts = [segment.strip() for segment in value.split("::", 3)]
    if len(parts) != 4:
        return None
    normalized = {
        "scope": _normalize_identifier(parts[0]),
        "name": _normalize_string(parts[1]),
        "version": _normalize_string(parts[2]),
        "purpose": _normalize_string(parts[3]),
    }
    if not all(normalized.values()):
        return None
    return normalized


def parse_code_organization_value(value: str) -> dict[str, str] | None:
    parts = [segment.strip() for segment in value.split("::", 3)]
    if len(parts) != 4:
        return None
    normalized = {
        "repoStrategy": _normalize_string(parts[0]),
        "sourceLayout": _normalize_string(parts[1]),
        "modularity": _normalize_string(parts[2]),
        "rationale": _normalize_string(parts[3]),
    }
    if not all(normalized.values()):
        return None
    return normalized


def parse_alternative_value(value: str) -> dict[str, str] | None:
    parts = [segment.strip() for segment in value.split("::", 2)]
    if len(parts) != 3:
        return None
    normalized = {
        "slot": _normalize_identifier(parts[0]),
        "option": _normalize_string(parts[1]),
        "reasonRejected": _normalize_string(parts[2]),
    }
    if not all(normalized.values()):
        return None
    return normalized


def update_tech_state(
    state: dict[str, Any],
    *,
    project_type: str | None = None,
    stack_overview: str | None = None,
    requirements: list[str] | None = None,
    preferences: list[str] | None = None,
    constraints: list[str] | None = None,
    components: list[dict[str, str]] | None = None,
    libraries: list[dict[str, str]] | None = None,
    code_organization: dict[str, str] | None = None,
    alternatives: list[dict[str, str]] | None = None,
    next_actions: list[str] | None = None,
    checkpoint_summary: str | None = None,
    ratify: bool = False,
) -> dict[str, Any]:
    normalized, _ = normalize_tech_state(state)
    if project_type and project_type.strip():
        normalized["projectType"] = _normalize_string(project_type)
    if stack_overview and stack_overview.strip():
        normalized["stackOverview"] = _normalize_string(stack_overview)

    normalized["requirements"] = append_unique_strings(normalized["requirements"], requirements or [])
    normalized["preferences"] = append_unique_strings(normalized["preferences"], preferences or [])
    normalized["constraints"] = append_unique_strings(normalized["constraints"], constraints or [])
    normalized["nextActions"] = append_unique_strings(normalized["nextActions"], next_actions or [])
    normalized["components"] = _append_unique_dicts(
        normalized["components"],
        components or [],
        ("slot", "name", "version", "rationale"),
    )
    normalized["libraries"] = _append_unique_dicts(
        normalized["libraries"],
        libraries or [],
        ("scope", "name", "version", "purpose"),
    )
    normalized["alternatives"] = _append_unique_dicts(
        normalized["alternatives"],
        alternatives or [],
        ("slot", "option", "reasonRejected"),
    )
    if code_organization is not None:
        normalized["codeOrganization"] = _normalize_code_organization(code_organization)

    ts = now_iso()
    normalized["updatedAt"] = ts
    if checkpoint_summary is not None:
        normalized["checkpointSummary"] = _normalize_string(checkpoint_summary)
    if ratify:
        normalized["ratifiedAt"] = ts
        normalized["revision"] = int(normalized.get("revision", 0)) + 1
    return normalized


def render_tech_stack_markdown(
    state: dict[str, Any],
    *,
    branch_name: str,
    project_name: str = "",
) -> str:
    normalized, _ = normalize_tech_state(state)
    project_label = project_name or "Не указано"
    grouped_components: dict[str, list[dict[str, str]]] = {}
    for component in normalized["components"]:
        grouped_components.setdefault(component["slot"], []).append(component)

    grouped_libraries: dict[str, list[dict[str, str]]] = {}
    for library in normalized["libraries"]:
        grouped_libraries.setdefault(library["scope"], []).append(library)

    def render_list(values: list[str]) -> list[str]:
        if not values:
            return ["- Пока не зафиксировано."]
        return [f"- {value}" for value in values]

    def render_component_group(slot: str, items: list[dict[str, str]]) -> list[str]:
        if not items:
            return []
        title = {
            "language": "Язык программирования",
            "frontend": "Frontend",
            "backend": "Backend",
            "database": "База данных",
            "unit-testing": "Unit Testing",
            "integration-testing": "Integration Testing",
            "e2e-testing": "E2E Testing",
            "build": "Build",
            "deploy": "Deploy",
        }.get(slot, slot or "unknown")
        lines = [f"### {title}", ""]
        for item in items:
            lines.extend(
                [
                    f"- **{item['name']}** `{item['version']}`",
                    f"  - Обоснование: {item['rationale']}",
                ]
            )
        lines.append("")
        return lines

    lines = [
        f"# Технологический стек: {project_label}",
        "",
        f"**Основано на**: `.madspec/{branch_name}/memory/stages/mvp.tech.json`",
        "",
        "## Обзор",
        "",
        f"**Тип проекта**: {normalized['projectType'] or 'Не указано'}",
        "",
        normalized["stackOverview"] or "Пока не зафиксировано.",
        "",
        "## Выбранные компоненты стека",
        "",
    ]

    rendered_any_component = False
    for slot in TECH_KNOWN_SLOTS:
        items = grouped_components.get(slot, [])
        if items:
            rendered_any_component = True
            lines.extend(render_component_group(slot, items))

    other_slots = sorted(slot for slot in grouped_components if slot not in TECH_KNOWN_SLOTS)
    for slot in other_slots:
        rendered_any_component = True
        lines.extend(render_component_group(slot, grouped_components[slot]))

    if not rendered_any_component:
        lines.extend(["Пока не зафиксировано.", ""])

    lines.extend(["## Дополнительные библиотеки", ""])
    if not grouped_libraries:
        lines.extend(["Пока не зафиксировано.", ""])
    else:
        for scope in sorted(grouped_libraries):
            lines.append(f"### {scope or 'unknown'}")
            lines.append("")
            for item in grouped_libraries[scope]:
                lines.append(f"- **{item['name']}** `{item['version']}`: {item['purpose']}")
            lines.append("")

    lines.extend(["## Организация кода", ""])
    if normalized["codeOrganization"]:
        lines.extend(
            [
                f"- **Repo strategy**: {normalized['codeOrganization']['repoStrategy']}",
                f"- **Source layout**: {normalized['codeOrganization']['sourceLayout']}",
                f"- **Modularity**: {normalized['codeOrganization']['modularity']}",
                f"- **Обоснование**: {normalized['codeOrganization']['rationale']}",
                "",
            ]
        )
    else:
        lines.extend(["Пока не зафиксировано.", ""])

    lines.extend(["## Требования", "", *render_list(normalized["requirements"]), ""])
    lines.extend(["## Предпочтения", "", *render_list(normalized["preferences"]), ""])
    lines.extend(["## Ограничения", "", *render_list(normalized["constraints"]), ""])

    lines.extend(["## Рассмотренные, но отклонённые альтернативы", ""])
    if not normalized["alternatives"]:
        lines.extend(["Пока не зафиксировано.", ""])
    else:
        for item in normalized["alternatives"]:
            lines.append(
                f"- **{item['slot']}**: {item['option']} — {item['reasonRejected']}"
            )
        lines.append("")

    lines.extend(
        [
            "## Следующие шаги",
            "",
            *render_list(
                normalized["nextActions"]
                or [
                    "Перейти к проектированию архитектуры",
                    "Проверить, что выбранный стек покрывает все обязательные сценарии MVP",
                ]
            ),
            "",
            "## Checkpoint",
            "",
            normalized["checkpointSummary"] or "Пока не зафиксировано.",
            "",
            f"Версия: {normalized['revision']} | Ратифицирована: {normalized['ratifiedAt'] or 'Не указано'} | Последнее изменение: {normalized['updatedAt'] or 'Не указано'}",
            "",
        ]
    )
    return "\n".join(lines)


def tech_completeness_errors(state: dict[str, Any]) -> list[str]:
    normalized, _ = normalize_tech_state(state)
    errors: list[str] = []
    if not normalized["projectType"]:
        errors.append("tech state must include a project type before checkpoint")
    if not normalized["stackOverview"]:
        errors.append("tech state must include a stack overview before checkpoint")
    slots = {item["slot"] for item in normalized["components"]}
    if "language" not in slots:
        errors.append("tech state must include at least one language component before checkpoint")
    if "build" not in slots:
        errors.append("tech state must include at least one build component before checkpoint")
    if not any(slot in slots for slot in {"unit-testing", "integration-testing", "e2e-testing", "testing"}):
        errors.append("tech state must include at least one testing component before checkpoint")
    if not normalized["codeOrganization"]:
        errors.append("tech state must include code organization before checkpoint")
    return errors


def tech_schema_errors(state: Any) -> list[str]:
    if not isinstance(state, dict):
        return ["tech state must be a JSON object"]
    normalized, _ = normalize_tech_state(state)
    errors: list[str] = []
    if normalized["schemaVersion"] != TECH_SCHEMA_VERSION:
        errors.append(f"tech state schemaVersion must equal {TECH_SCHEMA_VERSION}")
    if not isinstance(normalized["revision"], int) or normalized["revision"] < 0:
        errors.append("tech state field 'revision' must be a non-negative integer")
    for key in ("projectType", "stackOverview", "checkpointSummary", "updatedAt"):
        if not isinstance(normalized[key], str):
            errors.append(f"tech state field '{key}' must be a string")
    if normalized["ratifiedAt"] is not None and not isinstance(normalized["ratifiedAt"], str):
        errors.append("tech state field 'ratifiedAt' must be a string or null")
    for key in ("requirements", "preferences", "constraints", "components", "libraries", "alternatives", "nextActions"):
        if not isinstance(normalized[key], list):
            errors.append(f"tech state field '{key}' must be a list")
    if normalized["codeOrganization"] is not None and not isinstance(normalized["codeOrganization"], dict):
        errors.append("tech state field 'codeOrganization' must be an object or null")
    return errors


from madspec_cli.memory.shared.stage_registry import register_stage_default, register_stage_loader, register_stage_validators, register_stage_renderers

register_stage_default("mvp.tech", default_tech_state)
register_stage_loader("mvp.tech", load_tech_state)
register_stage_validators("mvp.tech", schema_errors=tech_schema_errors)
register_stage_renderers("mvp.tech", tech_stack=render_tech_stack_markdown)
