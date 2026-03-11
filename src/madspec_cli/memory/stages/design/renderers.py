from __future__ import annotations

from typing import Any

from ...shared.storage import PRIORITIES
from .validators import design_main_prototype_path


def render_ui_design_markdown(
    state: dict[str, Any],
    *,
    branch_name: str,
    project_name: str = "",
) -> str:
    from .state import normalize_design_state

    normalized, _ = normalize_design_state(state)
    main_prototype = design_main_prototype_path(branch_name).as_posix()
    project_label = project_name or "Без названия"
    zone_titles = {
        zone.get("id", ""): zone.get("title", "") or zone.get("id", "")
        for zone in normalized["zones"]
    }

    def render_list(values: list[str]) -> list[str]:
        if not values:
            return ["- Пока не зафиксировано."]
        return [f"- {value}" for value in values]

    def render_date(value: str | None) -> str:
        return value or "Не указано"

    lines = [
        f"# Дизайн пользовательского интерфейса: {project_label}",
        "",
        f"**Основано на**: `.madspec/{branch_name}/concept.md`",
        "",
        "## Обзор",
        "",
        normalized["designOverview"] or "Пока не зафиксировано.",
        "",
        "## Прототип интерфейса",
        "",
        f"**Главный файл прототипа**: `{main_prototype}`",
        "",
        "## Платформы",
        "",
        *render_list(normalized["platforms"]),
        "",
        "## Основные экраны",
        "",
    ]

    if not normalized["screens"]:
        lines.append("Пока не зафиксировано.")
        lines.append("")
    else:
        for screen in normalized["screens"]:
            lines.extend(
                [
                    f"### {screen.get('id', 'screen')}: {screen.get('title', 'Без названия')}",
                    "",
                    f"**Файл прототипа**: `{screen.get('prototype', 'Не указан')}`",
                    f"**Функциональная зона**: {zone_titles.get(screen.get('zone', ''), screen.get('zone', '') or 'Не указана')}",
                    f"**Назначение**: {screen.get('purpose', '') or 'Пока не зафиксировано.'}",
                    "",
                    "**Покрытие функций**:",
                    *(
                        [
                            f"- {priority.upper()}: "
                            + (", ".join(screen.get("covers", {}).get(priority, [])) or "Пока не зафиксировано.")
                            for priority in PRIORITIES
                        ]
                    ),
                    "",
                    "**Платформы**:",
                    *render_list(screen.get("platforms", [])),
                    "",
                    "**Данные на экране**:",
                    "- Отображаемые данные: "
                    + (", ".join(screen.get("data", {}).get("displayed", [])) or "Пока не зафиксировано."),
                    "- Вводимые данные: "
                    + (", ".join(screen.get("data", {}).get("input", [])) or "Пока не зафиксировано."),
                    "",
                ]
            )

    lines.extend(["## Пользовательские потоки", ""])
    if not normalized["flows"]:
        lines.append("Пока не зафиксировано.")
        lines.append("")
    else:
        for flow in normalized["flows"]:
            lines.extend(
                [
                    f"### {flow.get('id', 'flow')}: {flow.get('title', 'Без названия')}",
                    "",
                    f"**Цель пользователя**: {flow.get('goal', '') or 'Пока не зафиксировано.'}",
                    "",
                    "**Шаги**:",
                ]
            )
            if flow.get("steps"):
                lines.extend(
                    [
                        f"{index}. `{step.get('screenId', '')}` -> {step.get('action', '')} -> {step.get('result', '')}"
                        for index, step in enumerate(flow["steps"], start=1)
                    ]
                )
            else:
                lines.append("1. Пока не зафиксировано.")
            lines.extend(
                [
                    "",
                    "**Альтернативные пути**:",
                    *render_list(flow.get("alternatives", [])),
                    "",
                ]
            )

    lines.extend(["## Навигация", ""])
    if not normalized["navigation"]:
        lines.append("Пока не зафиксировано.")
    else:
        for item in normalized["navigation"]:
            lines.append(
                f"- `{item.get('from', '')}` -> `{item.get('to', '')}` через {item.get('trigger', '')}"
            )

    lines.extend(
        [
            "",
            "## Ограничения платформ",
            "",
            *render_list(normalized["platformConstraints"]),
            "",
            "## Следующие шаги",
            "",
            *render_list(normalized["nextActions"]),
            "",
            "---",
            (
                f"Версия: {normalized.get('revision', 0)} | "
                f"Ратифицирована: {render_date(normalized.get('ratifiedAt'))} | "
                f"Последнее изменение: {render_date(normalized.get('updatedAt'))}"
            ),
            "",
        ]
    )
    return "\n".join(lines)
