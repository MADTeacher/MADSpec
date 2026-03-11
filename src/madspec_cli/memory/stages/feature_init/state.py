from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from ...shared.storage import PRIORITIES, now_iso, read_json, write_json

FEATURE_INIT_STAGE = "feature.init"
FEATURE_INIT_SCHEMA_VERSION = 1
FEATURE_SEPARATOR = "::"


def default_feature_init_state() -> dict[str, Any]:
    ts = now_iso()
    return {
        "schemaVersion": FEATURE_INIT_SCHEMA_VERSION,
        "featureGoal": "",
        "problem": "",
        "expectedOutcome": "",
        "createdAt": ts,
        "ratifiedAt": None,
        "updatedAt": ts,
        "revision": 0,
        "projectAnalysis": {
            "projectType": "",
            "framework": "",
            "structureNotes": [],
            "existingModules": [],
            "modifiedFiles": [],
            "newFiles": [],
            "interfaceContracts": [],
            "dependencies": [],
            "risks": [],
            "recommendations": [],
            "techNotes": [],
            "architectureNotes": [],
        },
        "features": {priority: [] for priority in PRIORITIES},
        "nextActions": [],
        "checkpointSummary": "",
    }


def _normalize_string(value: Any) -> str:
    if not isinstance(value, str):
        return ""
    return re.sub(r"\s+", " ", value).strip()


def _normalize_string_list(values: Any) -> list[str]:
    if not isinstance(values, list):
        return []
    normalized: list[str] = []
    for value in values:
        item = _normalize_string(value)
        if item and item not in normalized:
            normalized.append(item)
    return normalized


def _normalize_feature_list(values: Any) -> list[dict[str, str]]:
    if not isinstance(values, list):
        return []
    normalized: list[dict[str, str]] = []
    seen: set[str] = set()
    for item in values:
        if not isinstance(item, dict):
            continue
        feature = {
            "id": _normalize_string(item.get("id", "")).upper(),
            "title": _normalize_string(item.get("title", "")),
            "description": _normalize_string(item.get("description", "")),
        }
        if not feature["id"] or not feature["title"]:
            continue
        if feature["id"] in seen:
            continue
        seen.add(feature["id"])
        normalized.append(feature)
    return normalized


def _normalize_module_list(values: Any) -> list[dict[str, str]]:
    if not isinstance(values, list):
        return []
    normalized: list[dict[str, str]] = []
    seen: set[tuple[str, str, str]] = set()
    for item in values:
        if not isinstance(item, dict):
            continue
        entry = {
            "name": _normalize_string(item.get("name", "")),
            "path": _normalize_string(item.get("path", "")),
            "description": _normalize_string(item.get("description", "")),
        }
        if not entry["name"]:
            continue
        marker = (entry["name"], entry["path"], entry["description"])
        if marker in seen:
            continue
        seen.add(marker)
        normalized.append(entry)
    return normalized


def _normalize_file_list(values: Any) -> list[dict[str, Any]]:
    if not isinstance(values, list):
        return []
    normalized: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in values:
        if not isinstance(item, dict):
            continue
        entry = {
            "path": _normalize_string(item.get("path", "")),
            "reason": _normalize_string(item.get("reason", "")),
            "functionIds": _normalize_string_list(item.get("functionIds", [])),
        }
        if not entry["path"]:
            continue
        if entry["path"] in seen:
            continue
        seen.add(entry["path"])
        normalized.append(entry)
    return normalized


def _normalize_named_summary_list(values: Any) -> list[dict[str, str]]:
    if not isinstance(values, list):
        return []
    normalized: list[dict[str, str]] = []
    seen: set[tuple[str, str, str]] = set()
    for item in values:
        if not isinstance(item, dict):
            continue
        entry = {
            "scope": _normalize_string(item.get("scope", "")),
            "name": _normalize_string(item.get("name", "")),
            "description": _normalize_string(item.get("description", "")),
        }
        if not entry["name"]:
            continue
        marker = (entry["scope"], entry["name"], entry["description"])
        if marker in seen:
            continue
        seen.add(marker)
        normalized.append(entry)
    return normalized


def normalize_feature_init_state(state: Any) -> tuple[dict[str, Any], bool]:
    default_state = default_feature_init_state()
    if not isinstance(state, dict):
        return default_state, True

    normalized = dict(default_state)
    changed = False

    normalized["schemaVersion"] = FEATURE_INIT_SCHEMA_VERSION
    if state.get("schemaVersion") != FEATURE_INIT_SCHEMA_VERSION:
        changed = True

    for key in ("featureGoal", "problem", "expectedOutcome", "createdAt", "checkpointSummary"):
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

    analysis = state.get("projectAnalysis", {})
    if not isinstance(analysis, dict):
        analysis = {}
        changed = True
    normalized["projectAnalysis"] = {
        "projectType": _normalize_string(analysis.get("projectType", "")),
        "framework": _normalize_string(analysis.get("framework", "")),
        "structureNotes": _normalize_string_list(analysis.get("structureNotes", [])),
        "existingModules": _normalize_module_list(analysis.get("existingModules", [])),
        "modifiedFiles": _normalize_file_list(analysis.get("modifiedFiles", [])),
        "newFiles": _normalize_file_list(analysis.get("newFiles", [])),
        "interfaceContracts": _normalize_string_list(analysis.get("interfaceContracts", [])),
        "dependencies": _normalize_named_summary_list(analysis.get("dependencies", [])),
        "risks": _normalize_string_list(analysis.get("risks", [])),
        "recommendations": _normalize_string_list(analysis.get("recommendations", [])),
        "techNotes": _normalize_string_list(analysis.get("techNotes", [])),
        "architectureNotes": _normalize_string_list(analysis.get("architectureNotes", [])),
    }
    if normalized["projectAnalysis"] != analysis:
        changed = True

    features = state.get("features", {})
    if not isinstance(features, dict):
        features = {}
        changed = True
    normalized["features"] = {
        priority: _normalize_feature_list(features.get(priority, [])) for priority in PRIORITIES
    }
    if normalized["features"] != features:
        changed = True

    normalized["nextActions"] = _normalize_string_list(state.get("nextActions", []))
    if normalized["nextActions"] != state.get("nextActions"):
        changed = True

    return normalized, changed


def load_feature_init_state(path: Path) -> dict[str, Any]:
    state = read_json(path, default_feature_init_state())
    normalized, _ = normalize_feature_init_state(state)
    return normalized


def save_feature_init_state(path: Path, state: dict[str, Any]) -> None:
    normalized, _ = normalize_feature_init_state(state)
    write_json(path, normalized)


def parse_feature_init_feature_value(value: str) -> dict[str, str] | None:
    parts = [part.strip() for part in value.split(FEATURE_SEPARATOR, 2)]
    if len(parts) != 3 or not all(parts):
        return None
    return {"id": parts[0].upper(), "title": parts[1], "description": parts[2]}


def parse_existing_module_value(value: str) -> dict[str, str] | None:
    parts = [part.strip() for part in value.split(FEATURE_SEPARATOR, 2)]
    if len(parts) != 3 or not parts[0]:
        return None
    return {"name": parts[0], "path": parts[1], "description": parts[2]}


def parse_file_change_value(value: str) -> dict[str, Any] | None:
    parts = [part.strip() for part in value.split(FEATURE_SEPARATOR, 2)]
    if len(parts) != 3 or not parts[0]:
        return None
    function_ids = [item.strip().upper() for item in parts[2].split(",") if item.strip()]
    return {"path": parts[0], "reason": parts[1], "functionIds": function_ids}


def parse_dependency_value(value: str) -> dict[str, str] | None:
    parts = [part.strip() for part in value.split(FEATURE_SEPARATOR, 2)]
    if len(parts) != 3 or not parts[1]:
        return None
    return {"scope": parts[0], "name": parts[1], "description": parts[2]}


def _append_unique_dicts(target: list[dict[str, Any]], values: list[dict[str, Any]], key: str) -> list[dict[str, Any]]:
    result = list(target)
    seen = {str(item.get(key, "")) for item in result}
    for value in values:
        marker = str(value.get(key, ""))
        if not marker or marker in seen:
            continue
        seen.add(marker)
        result.append(value)
    return result


def update_feature_init_state(
    state: dict[str, Any],
    *,
    feature_goal: str | None = None,
    problem: str | None = None,
    expected_outcome: str | None = None,
    project_type: str | None = None,
    framework: str | None = None,
    structure_notes: list[str] | None = None,
    existing_modules: list[dict[str, str]] | None = None,
    modified_files: list[dict[str, Any]] | None = None,
    new_files: list[dict[str, Any]] | None = None,
    interface_contracts: list[str] | None = None,
    dependencies: list[dict[str, str]] | None = None,
    risks: list[str] | None = None,
    recommendations: list[str] | None = None,
    tech_notes: list[str] | None = None,
    architecture_notes: list[str] | None = None,
    features: dict[str, list[dict[str, str]]] | None = None,
    next_actions: list[str] | None = None,
    checkpoint_summary: str | None = None,
    ratify: bool = False,
) -> dict[str, Any]:
    normalized, _ = normalize_feature_init_state(state)
    if feature_goal:
        normalized["featureGoal"] = _normalize_string(feature_goal)
    if problem:
        normalized["problem"] = _normalize_string(problem)
    if expected_outcome:
        normalized["expectedOutcome"] = _normalize_string(expected_outcome)

    analysis = normalized["projectAnalysis"]
    if project_type:
        analysis["projectType"] = _normalize_string(project_type)
    if framework:
        analysis["framework"] = _normalize_string(framework)
    analysis["structureNotes"] = _normalize_string_list(analysis["structureNotes"] + (structure_notes or []))
    analysis["existingModules"] = _append_unique_dicts(analysis["existingModules"], existing_modules or [], "name")
    analysis["modifiedFiles"] = _append_unique_dicts(analysis["modifiedFiles"], modified_files or [], "path")
    analysis["newFiles"] = _append_unique_dicts(analysis["newFiles"], new_files or [], "path")
    analysis["interfaceContracts"] = _normalize_string_list(analysis["interfaceContracts"] + (interface_contracts or []))
    analysis["dependencies"] = _append_unique_dicts(analysis["dependencies"], dependencies or [], "name")
    analysis["risks"] = _normalize_string_list(analysis["risks"] + (risks or []))
    analysis["recommendations"] = _normalize_string_list(analysis["recommendations"] + (recommendations or []))
    analysis["techNotes"] = _normalize_string_list(analysis["techNotes"] + (tech_notes or []))
    analysis["architectureNotes"] = _normalize_string_list(analysis["architectureNotes"] + (architecture_notes or []))

    feature_updates = features or {}
    for priority in PRIORITIES:
        normalized["features"][priority] = _append_unique_dicts(
            normalized["features"][priority],
            feature_updates.get(priority, []),
            "id",
        )

    normalized["nextActions"] = _normalize_string_list(normalized["nextActions"] + (next_actions or []))
    ts = now_iso()
    normalized["updatedAt"] = ts
    if checkpoint_summary is not None:
        normalized["checkpointSummary"] = _normalize_string(checkpoint_summary)
    if ratify:
        normalized["ratifiedAt"] = ts
        normalized["revision"] = int(normalized.get("revision", 0)) + 1
    return normalized


def feature_init_completeness_errors(state: dict[str, Any]) -> list[str]:
    normalized, _ = normalize_feature_init_state(state)
    errors: list[str] = []
    if not normalized["featureGoal"]:
        errors.append("feature init state must include a feature goal before checkpoint")
    if not normalized["problem"]:
        errors.append("feature init state must include a problem before checkpoint")
    if not normalized["expectedOutcome"]:
        errors.append("feature init state must include an expected outcome before checkpoint")
    if not normalized["projectAnalysis"]["framework"]:
        errors.append("feature init state must include a framework before checkpoint")
    if not any(normalized["features"][priority] for priority in PRIORITIES):
        errors.append("feature init state must include at least one feature before checkpoint")
    if not normalized["projectAnalysis"]["modifiedFiles"] and not normalized["projectAnalysis"]["newFiles"]:
        errors.append("feature init state must include integration file mappings before checkpoint")
    return errors


def feature_init_schema_errors(state: Any) -> list[str]:
    _, changed = normalize_feature_init_state(state)
    errors: list[str] = []
    if changed and not isinstance(state, dict):
        errors.append("feature init state must contain a JSON object")
    return errors


def build_feature_id_priority_map(state: dict[str, Any]) -> dict[str, str]:
    normalized, _ = normalize_feature_init_state(state)
    return {
        item["id"]: priority
        for priority in PRIORITIES
        for item in normalized["features"][priority]
    }


def render_project_analysis_markdown(state: dict[str, Any]) -> str:
    normalized, _ = normalize_feature_init_state(state)
    analysis = normalized["projectAnalysis"]
    lines = [
        "# Анализ проекта и точки интеграции",
        "",
        "> Generated from structured memory. Do not treat this file as the canonical source of truth.",
        "",
        "## Функциональные требования",
        "",
    ]
    for priority in PRIORITIES:
        lines.append(f"### {priority.upper()} ({'Критично' if priority == 'p1' else 'Важно' if priority == 'p2' else 'Желательно'})")
        lines.append("")
        features = normalized["features"][priority]
        if not features:
            lines.append("- Пока не зафиксировано.")
            lines.append("")
            continue
        for feature in features:
            lines.append(f"- **{feature['id']}**: {feature['title']}")
            lines.append(f"  - Описание: {feature['description'] or 'Не указано'}")
            related = [
                item["path"]
                for item in analysis["modifiedFiles"] + analysis["newFiles"]
                if feature["id"] in item.get("functionIds", [])
            ]
            lines.append(f"  - Связанные файлы: {', '.join(related) if related else 'Не указано'}")
            lines.append("")
    lines.extend(
        [
            "## Обзор проекта",
            "",
            f"- **Тип**: {analysis['projectType'] or 'Не указано'}",
            f"- **Фреймворк**: {analysis['framework'] or 'Не указано'}",
            f"- **Структура**: {'; '.join(analysis['structureNotes']) if analysis['structureNotes'] else 'Не указано'}",
            "",
            "## Существующие модули",
            "",
        ]
    )
    if analysis["existingModules"]:
        for module in analysis["existingModules"]:
            lines.append(f"- {module['name']}: {module['path']} — {module['description'] or 'Без описания'}")
    else:
        lines.append("- Пока не зафиксировано.")
    lines.extend(["", "## Точки интеграции для новой функциональности", "", "### Файлы для модификации", ""])
    if analysis["modifiedFiles"]:
        for item in analysis["modifiedFiles"]:
            lines.append(f"- `{item['path']}`:")
            lines.append(f"  - Причина модификации: {item['reason'] or 'Не указано'}")
            lines.append(f"  - Связанные функции: {', '.join(item['functionIds']) if item['functionIds'] else 'Не указано'}")
    else:
        lines.append("- Пока не зафиксировано.")
    lines.extend(["", "### Новые файлы для создания", ""])
    if analysis["newFiles"]:
        for item in analysis["newFiles"]:
            lines.append(f"- `{item['path']}`:")
            lines.append(f"  - Назначение: {item['reason'] or 'Не указано'}")
            lines.append(f"  - Связанные функции: {', '.join(item['functionIds']) if item['functionIds'] else 'Не указано'}")
    else:
        lines.append("- Пока не зафиксировано.")
    lines.extend(["", "### Интерфейсы и контракты", ""])
    lines.extend([f"- {item}" for item in analysis["interfaceContracts"]] or ["- Пока не зафиксировано."])
    lines.extend(["", "### Зависимости", ""])
    if analysis["dependencies"]:
        for item in analysis["dependencies"]:
            scope = f"{item['scope']}: " if item["scope"] else ""
            lines.append(f"- {scope}{item['name']} — {item['description'] or 'Без описания'}")
    else:
        lines.append("- Пока не зафиксировано.")
    lines.extend(["", "## Влияние на существующий код", ""])
    lines.extend([f"- {item}" for item in analysis["risks"]] or ["- Пока не зафиксировано."])
    lines.extend(["", "## Рекомендации по интеграции", ""])
    lines.extend([f"- {item}" for item in analysis["recommendations"]] or ["- Пока не зафиксировано."])
    return "\n".join(lines) + "\n"


def render_feature_context_markdown(state: dict[str, Any]) -> str:
    normalized, _ = normalize_feature_init_state(state)
    lines = [
        "# Контекст Feature",
        "",
        "> Generated from structured memory. Do not treat this file as the canonical source of truth.",
        "",
        "## Описание функциональности",
        normalized["featureGoal"] or "Пока не зафиксировано.",
        "",
        "## Проблема",
        normalized["problem"] or "Пока не зафиксировано.",
        "",
        "## Ожидаемый результат",
        normalized["expectedOutcome"] or "Пока не зафиксировано.",
        "",
        "## Функции",
    ]
    for priority in PRIORITIES:
        features = normalized["features"][priority]
        feature_labels = ", ".join(f"{item['id']} {item['title']}" for item in features) if features else "не зафиксировано"
        lines.append(f"- `{priority.upper()}`: {feature_labels}")
    return "\n".join(lines) + "\n"


def render_feature_tech_stack_markdown(state: dict[str, Any], *, branch_name: str) -> str:
    normalized, _ = normalize_feature_init_state(state)
    analysis = normalized["projectAnalysis"]
    lines = [
        "# Технологический стек",
        "",
        "> Generated from structured memory. Do not treat this file as the canonical source of truth.",
        "",
        f"**Основано на**: `.madspec/{branch_name}/memory/stages/feature.init.json`",
        "",
        f"- **Тип проекта**: {analysis['projectType'] or 'Не указано'}",
        f"- **Фреймворк**: {analysis['framework'] or 'Не указано'}",
        "",
        "## Технические заметки",
    ]
    lines.extend([f"- {item}" for item in analysis["techNotes"]] or ["- Пока не зафиксировано."])
    lines.extend(["", "## Зависимости"])
    if analysis["dependencies"]:
        for item in analysis["dependencies"]:
            scope = f"{item['scope']}: " if item["scope"] else ""
            lines.append(f"- {scope}{item['name']} — {item['description'] or 'Без описания'}")
    else:
        lines.append("- Пока не зафиксировано.")
    return "\n".join(lines) + "\n"


def render_feature_architecture_markdown(state: dict[str, Any], *, branch_name: str) -> str:
    normalized, _ = normalize_feature_init_state(state)
    analysis = normalized["projectAnalysis"]
    lines = [
        "# Архитектура",
        "",
        "> Generated from structured memory. Do not treat this file as the canonical source of truth.",
        "",
        f"**Основано на**: `.madspec/{branch_name}/memory/stages/feature.init.json`",
        "",
        "## Цель изменений",
        normalized["featureGoal"] or "Пока не зафиксировано.",
        "",
        "## Изменения в архитектуре",
    ]
    lines.extend([f"- {item}" for item in analysis["architectureNotes"]] or ["- Пока не зафиксировано."])
    lines.extend(["", "## Точки интеграции"])
    for section_name, items in (("Изменяемые файлы", analysis["modifiedFiles"]), ("Новые файлы", analysis["newFiles"])):
        lines.append(f"### {section_name}")
        if items:
            for item in items:
                lines.append(f"- `{item['path']}` — {item['reason'] or 'Без описания'}")
        else:
            lines.append("- Пока не зафиксировано.")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def is_empty_feature_init_state(state: dict[str, Any]) -> bool:
    normalized, _ = normalize_feature_init_state(state)
    return not any(
        [
            normalized["featureGoal"],
            normalized["problem"],
            normalized["expectedOutcome"],
            any(normalized["features"][priority] for priority in PRIORITIES),
            normalized["projectAnalysis"]["framework"],
            normalized["projectAnalysis"]["modifiedFiles"],
            normalized["projectAnalysis"]["newFiles"],
            normalized["nextActions"],
            normalized["checkpointSummary"],
        ]
    )


def migrate_legacy_project_analysis_markdown(path: Path) -> dict[str, Any]:
    state = default_feature_init_state()
    if not path.exists():
        return state
    current_priority: str | None = None
    current_feature: dict[str, str] | None = None
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if line.startswith("### P1"):
            current_priority = "p1"
            current_feature = None
            continue
        if line.startswith("### P2"):
            current_priority = "p2"
            current_feature = None
            continue
        if line.startswith("### P3"):
            current_priority = "p3"
            current_feature = None
            continue
        if line.startswith("## ") or line.startswith("### "):
            current_priority = None
            current_feature = None
            continue
        feature_match = re.match(r"- \*\*([^*]+)\*\*:?\s*(.*)$", line)
        if current_priority and feature_match:
            feature_id = feature_match.group(1).strip().upper()
            title = feature_id
            description = feature_match.group(2).strip()
            current_feature = {"id": feature_id, "title": title, "description": description}
            state["features"][current_priority].append(current_feature)
            continue
        if current_feature and line.startswith("- Описание:"):
            current_feature["description"] = line.split(":", 1)[1].strip()
            continue
        mod_match = re.match(r"- `([^`]+)`:\s*$", line)
        if mod_match:
            current_feature = None
            path_value = mod_match.group(1).strip()
            state["projectAnalysis"]["modifiedFiles"].append(
                {"path": path_value, "reason": "", "functionIds": []}
            )
            continue
        if line.startswith("- **Фреймворк**:"):
            state["projectAnalysis"]["framework"] = line.split(":", 1)[1].strip()
            continue
        if line.startswith("- **Тип**:"):
            state["projectAnalysis"]["projectType"] = line.split(":", 1)[1].strip()
            continue
    return normalize_feature_init_state(state)[0]
