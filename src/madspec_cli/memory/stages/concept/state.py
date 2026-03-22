from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from ...shared.text_lists import normalize_plain_text_list
from ...shared.storage import PRIORITIES, now_iso, read_json, write_json

CONCEPT_STAGE = "mvp.concept"
FEATURE_SEPARATOR = "::"
CONCEPT_SCHEMA_VERSION = 1


def default_concept_state() -> dict[str, Any]:
    ts = now_iso()
    return {
        "schemaVersion": CONCEPT_SCHEMA_VERSION,
        "projectName": "",
        "systemOverview": "",
        "createdAt": ts,
        "ratifiedAt": None,
        "updatedAt": ts,
        "revision": 0,
        "audiences": [],
        "scenarios": [],
        "painPoints": [],
        "features": {priority: [] for priority in PRIORITIES},
        "constraints": [],
        "assumptions": [],
        "nextActions": [],
        "checkpointSummary": "",
    }


def _normalize_string_list(values: Any) -> list[str]:
    return normalize_plain_text_list(values, normalize_item=lambda value: re.sub(r"\s+", " ", value).strip() if isinstance(value, str) else "")


def _normalize_feature_list(values: Any) -> list[dict[str, str]]:
    if not isinstance(values, list):
        return []
    normalized: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for item in values:
        if not isinstance(item, dict):
            continue
        name = re.sub(r"\s+", " ", str(item.get("name", ""))).strip()
        description = re.sub(r"\s+", " ", str(item.get("description", ""))).strip()
        if not name and not description:
            continue
        pair = (name, description)
        if pair in seen:
            continue
        seen.add(pair)
        normalized.append({"name": name, "description": description})
    return normalized


def normalize_concept_state(state: Any) -> tuple[dict[str, Any], bool]:
    default_state = default_concept_state()
    if not isinstance(state, dict):
        return default_state, True

    normalized = dict(default_state)
    changed = False

    normalized["schemaVersion"] = CONCEPT_SCHEMA_VERSION
    if state.get("schemaVersion") != CONCEPT_SCHEMA_VERSION:
        changed = True

    for key in ("projectName", "systemOverview", "createdAt", "checkpointSummary"):
        value = state.get(key, default_state[key])
        if not isinstance(value, str):
            value = default_state[key]
            changed = True
        normalized[key] = value.strip() if isinstance(value, str) else value
        if normalized[key] != state.get(key):
            changed = True

    for key in ("ratifiedAt", "updatedAt"):
        value = state.get(key, default_state[key])
        if value is not None and not isinstance(value, str):
            value = default_state[key]
            changed = True
        normalized[key] = value.strip() if isinstance(value, str) else value
        if normalized[key] != state.get(key):
            changed = True

    revision = state.get("revision", default_state["revision"])
    if not isinstance(revision, int) or revision < 0:
        revision = default_state["revision"]
        changed = True
    normalized["revision"] = revision
    if normalized["revision"] != state.get("revision"):
        changed = True

    for key in ("audiences", "scenarios", "painPoints", "constraints", "assumptions", "nextActions"):
        normalized[key] = _normalize_string_list(state.get(key, default_state[key]))
        if normalized[key] != state.get(key):
            changed = True

    features = state.get("features", {})
    if not isinstance(features, dict):
        features = {}
        changed = True
    normalized_features: dict[str, list[dict[str, str]]] = {}
    for priority in PRIORITIES:
        normalized_features[priority] = _normalize_feature_list(features.get(priority, []))
        if normalized_features[priority] != features.get(priority):
            changed = True
    normalized["features"] = normalized_features
    return normalized, changed


def load_concept_state(path: Path) -> dict[str, Any]:
    state = read_json(path, default_concept_state())
    normalized, _ = normalize_concept_state(state)
    return normalized


def save_concept_state(path: Path, state: dict[str, Any]) -> None:
    normalized, _ = normalize_concept_state(state)
    write_json(path, normalized)


def parse_feature_value(value: str) -> dict[str, str] | None:
    normalized = value.strip()
    if not normalized or FEATURE_SEPARATOR not in normalized:
        return None
    name, description = normalized.split(FEATURE_SEPARATOR, 1)
    feature = {
        "name": re.sub(r"\s+", " ", name).strip(),
        "description": re.sub(r"\s+", " ", description).strip(),
    }
    if not feature["name"] or not feature["description"]:
        return None
    return feature


def append_unique_strings(target: list[str], values: list[str]) -> list[str]:
    result = list(target)
    for value in values:
        if value not in result:
            result.append(value)
    return result


def append_unique_features(target: list[dict[str, str]], values: list[dict[str, str]]) -> list[dict[str, str]]:
    result = list(target)
    seen = {(item.get("name", ""), item.get("description", "")) for item in result}
    for value in values:
        pair = (value.get("name", ""), value.get("description", ""))
        if pair in seen:
            continue
        seen.add(pair)
        result.append(value)
    return result


def is_empty_concept_state(state: dict[str, Any]) -> bool:
    normalized, _ = normalize_concept_state(state)
    return not any(
        [
            normalized["projectName"],
            normalized["systemOverview"],
            normalized["audiences"],
            normalized["scenarios"],
            normalized["painPoints"],
            normalized["features"]["p1"],
            normalized["features"]["p2"],
            normalized["features"]["p3"],
            normalized["constraints"],
            normalized["assumptions"],
            normalized["nextActions"],
            normalized["checkpointSummary"],
            normalized["revision"],
            normalized["ratifiedAt"],
        ]
    )


def update_concept_state(
    state: dict[str, Any],
    *,
    project_name: str | None = None,
    system_overview: str | None = None,
    audiences: list[str] | None = None,
    scenarios: list[str] | None = None,
    pain_points: list[str] | None = None,
    features: dict[str, list[dict[str, str]]] | None = None,
    constraints: list[str] | None = None,
    assumptions: list[str] | None = None,
    next_actions: list[str] | None = None,
    checkpoint_summary: str | None = None,
    ratify: bool = False,
) -> dict[str, Any]:
    normalized, _ = normalize_concept_state(state)
    if project_name and project_name.strip():
        normalized["projectName"] = re.sub(r"\s+", " ", project_name).strip()
    if system_overview and system_overview.strip():
        normalized["systemOverview"] = re.sub(r"\s+", " ", system_overview).strip()
    normalized["audiences"] = append_unique_strings(normalized["audiences"], audiences or [])
    normalized["scenarios"] = append_unique_strings(normalized["scenarios"], scenarios or [])
    normalized["painPoints"] = append_unique_strings(normalized["painPoints"], pain_points or [])
    normalized["constraints"] = append_unique_strings(normalized["constraints"], constraints or [])
    normalized["assumptions"] = append_unique_strings(normalized["assumptions"], assumptions or [])
    normalized["nextActions"] = append_unique_strings(normalized["nextActions"], next_actions or [])

    feature_updates = features or {}
    for priority in PRIORITIES:
        normalized["features"][priority] = append_unique_features(
            normalized["features"][priority],
            feature_updates.get(priority, []),
        )

    ts = now_iso()
    normalized["updatedAt"] = ts
    if checkpoint_summary is not None:
        normalized["checkpointSummary"] = checkpoint_summary.strip()
    if ratify:
        normalized["ratifiedAt"] = ts
        normalized["revision"] = int(normalized.get("revision", 0)) + 1
    return normalized


def render_concept_markdown(state: dict[str, Any]) -> str:
    normalized, _ = normalize_concept_state(state)

    def render_list(values: list[str], *, numbered: bool = False) -> list[str]:
        if not values:
            return ["Пока не зафиксировано."]
        if numbered:
            return [f"{index}. {value}" for index, value in enumerate(values, start=1)]
        return [f"- {value}" for value in values]

    def render_features(values: list[dict[str, str]]) -> list[str]:
        if not values:
            return ["Пока не зафиксировано."]
        lines: list[str] = []
        for item in values:
            name = item.get("name", "").strip() or "Без названия"
            description = item.get("description", "").strip()
            if description:
                lines.append(f"- {name}: {description}")
            else:
                lines.append(f"- {name}")
        return lines

    def render_date(value: str | None) -> str:
        if not value:
            return "Не указано"
        return value.split("T", 1)[0]

    lines = [
        f"# Концепция проекта: {normalized['projectName'] or 'Не указано'}",
        "",
        f"**Дата создания**: {render_date(normalized.get('createdAt'))}",
        "",
        "## Общее описание системы",
        normalized["systemOverview"] or "Пока не зафиксировано.",
        "",
        "## Целевая аудитория",
        "",
        "### Основные пользователи",
        *render_list(normalized["audiences"]),
        "",
        "### Сценарии использования (как пользователи будут использовать проект)",
        *render_list(normalized["scenarios"]),
        "",
        '## Решаемая "боль" целевой аудитории',
        *render_list(normalized["painPoints"]),
        "",
        "## Основные функции разрабатываемого проекта",
        "",
        "### Приоритет 1 (P1) - В первую очередь",
        *render_features(normalized["features"]["p1"]),
        "",
        "### Приоритет 2 (P2) - Реализуются после добавления критических функций",
        *render_features(normalized["features"]["p2"]),
        "",
        "### Приоритет 3 (P3) - Функции последней очереди",
        *render_features(normalized["features"]["p3"]),
        "",
        "## Ограничения и предположения",
        "",
        "### Технические ограничения",
        *render_list(normalized["constraints"]),
        "",
        "### Предположения",
        *render_list(normalized["assumptions"]),
        "",
        "",
        "## Следующие шаги",
        "",
        "После утверждения концепции переходим к:",
        *render_list(
            normalized["nextActions"]
            or [
                "Созданию дизайна пользовательского интерфейса",
                "Выбору технологического стека",
                "Проектированию архитектуры",
            ],
            numbered=True,
        ),
        "",
        "---",
        f"Версия: {normalized.get('revision', 0)} | Ратифицирована: {render_date(normalized.get('ratifiedAt'))} | Последнее изменение: {render_date(normalized.get('updatedAt'))}",
        "",
    ]
    return "\n".join(lines)


def concept_completeness_errors(state: dict[str, Any]) -> list[str]:
    normalized, _ = normalize_concept_state(state)
    errors: list[str] = []
    if not normalized["systemOverview"]:
        errors.append("concept state must include a system overview before checkpoint")
    if not normalized["audiences"]:
        errors.append("concept state must include at least one audience before checkpoint")
    if not normalized["scenarios"]:
        errors.append("concept state must include at least one scenario before checkpoint")
    if not normalized["painPoints"]:
        errors.append("concept state must include at least one pain point before checkpoint")
    if not normalized["features"]["p1"]:
        errors.append("concept state must include at least one P1 feature before checkpoint")
    return errors


def concept_schema_errors(state: Any) -> list[str]:
    if not isinstance(state, dict):
        return ["concept state must be a JSON object"]
    normalized, _ = normalize_concept_state(state)
    errors: list[str] = []
    if normalized["schemaVersion"] != CONCEPT_SCHEMA_VERSION:
        errors.append(f"concept state schemaVersion must equal {CONCEPT_SCHEMA_VERSION}")
    for key in ("projectName", "systemOverview", "createdAt", "checkpointSummary"):
        if not isinstance(normalized[key], str):
            errors.append(f"concept state field '{key}' must be a string")
    for key in ("ratifiedAt", "updatedAt"):
        value = normalized[key]
        if value is not None and not isinstance(value, str):
            errors.append(f"concept state field '{key}' must be a string or null")
    if not isinstance(normalized["revision"], int) or normalized["revision"] < 0:
        errors.append("concept state field 'revision' must be a non-negative integer")
    for key in ("audiences", "scenarios", "painPoints", "constraints", "assumptions", "nextActions"):
        if not isinstance(normalized[key], list):
            errors.append(f"concept state field '{key}' must be a list")
    if not isinstance(normalized.get("features"), dict):
        errors.append("concept state field 'features' must be an object")
    return errors


def migrate_legacy_concept_markdown(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    state = default_concept_state()
    current_section: str | None = None
    current_priority: str | None = None
    project_name_match = re.search(r"^# Концепция проекта:\s*(.+)$", text, re.MULTILINE)
    if project_name_match:
        state["projectName"] = project_name_match.group(1).strip()
    overview_match = re.search(
        r"^## Общее описание системы\s+(.+?)(?=^## |\Z)",
        text,
        re.MULTILINE | re.DOTALL,
    )
    if overview_match:
        overview = " ".join(line.strip() for line in overview_match.group(1).splitlines() if line.strip())
        if overview and overview != "Пока не зафиксировано.":
            state["systemOverview"] = overview
    created_match = re.search(r"^\*\*Дата создания\*\*:\s*(.+)$", text, re.MULTILINE)
    if created_match:
        state["createdAt"] = created_match.group(1).strip()
    footer_match = re.search(
        r"Версия:\s*([^\|]+)\|\s*Ратифицирована:\s*([^\|]+)\|\s*Последнее изменение:\s*(.+)$",
        text,
        re.MULTILINE,
    )
    if footer_match:
        revision_raw = footer_match.group(1).strip()
        try:
            state["revision"] = int(revision_raw)
        except ValueError:
            state["revision"] = 0
        ratified = footer_match.group(2).strip()
        updated = footer_match.group(3).strip()
        state["ratifiedAt"] = None if ratified == "Не указано" else ratified
        state["updatedAt"] = None if updated == "Не указано" else updated

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if line == "### Основные пользователи":
            current_section = "audiences"
            current_priority = None
            continue
        if line.startswith("### Сценарии использования"):
            current_section = "scenarios"
            current_priority = None
            continue
        if line == '## Решаемая "боль" целевой аудитории':
            current_section = "painPoints"
            current_priority = None
            continue
        if line == "### Технические ограничения":
            current_section = "constraints"
            current_priority = None
            continue
        if line == "### Предположения":
            current_section = "assumptions"
            current_priority = None
            continue
        if line.startswith("### Приоритет 1"):
            current_priority = "p1"
            current_section = None
            continue
        if line.startswith("### Приоритет 2"):
            current_priority = "p2"
            current_section = None
            continue
        if line.startswith("### Приоритет 3"):
            current_priority = "p3"
            current_section = None
            continue
        if line.startswith("## ") or line.startswith("### "):
            current_section = None
            current_priority = None
            continue
        if current_priority and line.startswith("- "):
            feature_text = line[2:].strip()
            if ":" in feature_text:
                name, description = feature_text.split(":", 1)
                state["features"][current_priority].append(
                    {"name": name.strip(), "description": description.strip()}
                )
            else:
                state["features"][current_priority].append(
                    {"name": feature_text, "description": ""}
                )
            continue
        if current_section and (line.startswith("- ") or re.match(r"^\d+\.\s+", line)):
            value = re.sub(r"^(- |\d+\.\s+)", "", line).strip()
            state[current_section].append(value)
            continue
        if current_section and line != "Пока не зафиксировано.":
            state[current_section].append(line)

    normalized, _ = normalize_concept_state(state)
    return normalized


from madspec_cli.memory.shared.stage_registry import register_stage_default, register_stage_loader, register_stage_validators, register_stage_renderers

register_stage_default("mvp.concept", default_concept_state)
register_stage_loader("mvp.concept", load_concept_state)
register_stage_validators("mvp.concept", schema_errors=concept_schema_errors)
register_stage_renderers("mvp.concept", concept=render_concept_markdown)
