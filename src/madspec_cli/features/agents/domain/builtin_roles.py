from __future__ import annotations

from typing import Any

from madspec_cli.config import AGENT_CONFIG


DEFAULT_PROFILE_ID = "default"
DEFAULT_SUBAGENT_IDS = (
    "architecture",
    "developer",
    "contracts-data",
    "testing",
    "security",
    "research",
    "docs",
)
ROLE_METADATA_FIELDS = (
    "title",
    "description",
    "purpose",
    "defaultStage",
    "executionModeHint",
    "dependencies",
    "toolPolicy",
    "outputContract",
)

_ROLE_TITLES = {
    "architecture": "Архитектурный специалист",
    "developer": "Специалист по разработке",
    "contracts-data": "Специалист по контрактам и данным",
    "testing": "Специалист по тестированию",
    "security": "Специалист по безопасности",
    "research": "Исследователь репозитория",
    "docs": "Специалист по документации",
}

_ROLE_DESCRIPTIONS = {
    "architecture": "Отвечает за архитектуру, границы системы, контракты и ключевые компромиссы текущего продукта и репозитория.",
    "developer": "Реализует запланированные изменения в коде, встраивает решения и подтверждает шаги разработки в текущем репозитории.",
    "contracts-data": "Отвечает за API-контракты, структуры данных, границы схем и согласованность данных на интеграциях.",
    "testing": "Сосредоточен на пробелах в покрытии, проектировании тестов, стратегии проверки и подтверждении реализации.",
    "security": "Проверяет безопасность, приватность, поверхность атаки, риски зависимостей и защитные меры.",
    "research": "Исследует контекст репозитория, неизвестные факторы и подтверждающие данные по текущему продукту и кодовой базе.",
    "docs": "Поддерживает техническую и процессную документацию в соответствии с текущим состоянием репозитория и сгенерированных артефактов.",
}

_ROLE_PURPOSES = {
    "architecture": "Формировать архитектурные решения и ограничения, которые соответствуют текущему продукту, репозиторию и правилам проекта.",
    "developer": "Реализовывать согласованные изменения в коде и тестах, не выходя за рамки текущего шага, плана и проектных ограничений.",
    "contracts-data": "Поддерживать внутреннюю согласованность контрактов, схем, сущностей и интеграционных моделей данных и доводить их до состояния, пригодного для реализации.",
    "testing": "Повышать уверенность в результате через практические тест-планы, новые тесты и заметки о проверке.",
    "security": "Выявлять значимые риски безопасности и приватности и предлагать практические меры снижения риска.",
    "research": "Собирать контекст, сравнивать варианты и кратко формулировать выводы, чтобы разблокировать следующую работу.",
    "docs": "Поддерживать пользовательскую и техническую документацию в синхронизации с реальным процессом, кодовой базой и сгенерированными результатами.",
}

_ROLE_DEFAULT_STAGES = {
    "architecture": "mvp.architecture",
    "developer": "feature.implement",
    "contracts-data": "mvp.architecture",
    "testing": "feature.implement",
    "security": "security",
    "research": "feature.plan",
    "docs": "review",
}

_ROLE_EXECUTION_HINTS = {
    "architecture": "sequential",
    "developer": "parallel",
    "contracts-data": "sequential",
    "testing": "parallel",
    "security": "parallel",
    "research": "parallel",
    "docs": "parallel",
}

_ROLE_DEPENDENCIES = {
    "architecture": [],
    "developer": ["architecture"],
    "contracts-data": ["architecture"],
    "testing": ["architecture"],
    "security": [],
    "research": [],
    "docs": [],
}

_ROLE_TOOL_POLICY = {
    "architecture": {"read": True, "search": True, "edit": False, "write": False, "bash": False},
    "developer": {"read": True, "search": True, "edit": True, "write": True, "bash": True},
    "contracts-data": {"read": True, "search": True, "edit": False, "write": False, "bash": False},
    "testing": {"read": True, "search": True, "edit": True, "write": True, "bash": True},
    "security": {"read": True, "search": True, "edit": False, "write": False, "bash": True},
    "research": {"read": True, "search": True, "edit": False, "write": False, "bash": False},
    "docs": {"read": True, "search": True, "edit": True, "write": True, "bash": False},
}

_ROLE_OUTPUT_CONTRACT = {
    "architecture": {"deliverable": "решения, ограничения, интерфейсы", "writeBack": "только через канонические команды CLI"},
    "developer": {"deliverable": "изменения в коде, тесты, заметки о проверке", "writeBack": "только через канонические команды CLI"},
    "contracts-data": {"deliverable": "контракты, схемы, решения по сущностям", "writeBack": "только через канонические команды CLI"},
    "testing": {"deliverable": "тесты, заметки о проверке, рекомендации по покрытию", "writeBack": "только через канонические команды CLI"},
    "security": {"deliverable": "риски, меры снижения, рекомендации по приоритетам", "writeBack": "только через канонические команды CLI"},
    "research": {"deliverable": "выводы, варианты, подтверждения", "writeBack": "только через канонические команды CLI"},
    "docs": {"deliverable": "обновления документации, найденные расхождения, уточняющие заметки", "writeBack": "только через канонические команды CLI"},
}


def role_catalog(*, environment_id: str) -> list[dict[str, Any]]:
    config = AGENT_CONFIG[environment_id]
    render_mode = "native" if config.supports_native_subagents else "fallback"
    return [
        {
            "subagentId": role_id,
            "title": _ROLE_TITLES[role_id],
            "description": _ROLE_DESCRIPTIONS[role_id],
            "purpose": _ROLE_PURPOSES[role_id],
            "defaultStage": _ROLE_DEFAULT_STAGES[role_id],
            "executionModeHint": _ROLE_EXECUTION_HINTS[role_id],
            "dependencies": list(_ROLE_DEPENDENCIES[role_id]),
            "toolPolicy": dict(_ROLE_TOOL_POLICY[role_id]),
            "outputContract": dict(_ROLE_OUTPUT_CONTRACT[role_id]),
            "origin": "builtin",
            "bodySource": f"template:{role_id}",
            "enabled": role_id in DEFAULT_SUBAGENT_IDS,
            "renderMode": render_mode,
        }
        for role_id in DEFAULT_SUBAGENT_IDS
    ]
