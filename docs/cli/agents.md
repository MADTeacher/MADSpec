# `madspec agents`

`madspec agents` управляет каноническим слоем субагентов в MADSpec. Команда хранит активную среду, профиль ролей, проектный каталог субагентов, историю изменений и экспортирует role-scoped context для субагентов.

## Когда Использовать

- чтобы посмотреть, какая агентная среда считается активной для проекта
- чтобы получить рекомендацию по базовому профилю субагентов
- чтобы применить или изменить набор активных ролей
- чтобы включить или отключить конкретную роль
- чтобы отдать субагенту канонический срез контекста без ручного чтения нескольких файлов

## Синтаксис

```bash
madspec agents profile
madspec agents recommend
madspec agents propose-profile [OPTIONS]
madspec agents apply-profile --proposal-id <id>
madspec agents subagents list [OPTIONS]
madspec agents subagents show --subagent-id <id> [OPTIONS]
madspec agents subagents create --subagent-id <id> --from-file <json> --body-file <md> [OPTIONS]
madspec agents subagents update --subagent-id <id> --from-file <json> [--body-file <md>] [OPTIONS]
madspec agents subagents remove --subagent-id <id> [--force] [OPTIONS]
madspec agents subagents enable --subagent-id <id>
madspec agents subagents disable --subagent-id <id>
madspec agents subagents context --subagent-id <id> [OPTIONS]
```

## Что Хранится

Канонический источник истины:

- `.madspec/config.json`
- `.madspec/system/agents/state.json`
- `.madspec/system/agents/catalog.json`
- `.madspec/system/agents/bodies/`
- `.madspec/system/agents/proposals.jsonl`
- `.madspec/system/agents/history.jsonl`
- `.madspec/system/agents.md`

`state.json` задает:

- активную среду `agentEnvironment`
- текущий `profileId`
- revision и timestamps
- список `enabledSubagentIds`

`catalog.json` задает project-defined роли и project overrides встроенных ролей.

Каждая effective role получается как объединение:

- built-in каталога MADSpec
- project catalog из `catalog.json`
- текста роли из `.madspec/system/agents/bodies/<subagent-id>.md`, если для project role или override задан project body

`agentEnvironment` также определяет явный `subagentFrontmatterProfile` для нативных сред. Через этот профиль MADSpec:

- выбирает допустимые YAML-поля для subagent/agent-файлов
- фиксирует стратегию модели для среды
- строго переводит общий `toolPolicy` в environment-specific tools вместо копирования общих флагов как есть

## Основные Команды

### `madspec agents profile`

Показывает активную среду, текущий профиль и включенные роли.

### `madspec agents recommend`

Возвращает рекомендованный базовый профиль ролей для текущего проекта.

Во встроенный starter set сейчас входят:

- `architecture`
- `developer`
- `contracts-data`
- `testing`
- `security`
- `research`
- `docs`

### `madspec agents propose-profile`

Создает proposal на изменение профиля ролей.

Основные опции:

- `--profile-id <id>`
- `--environment <agent>`
- `--subagent <id>` — повторяемый флаг для явного набора ролей

### `madspec agents apply-profile`

Применяет pending proposal и перерендеривает средовые файлы.

### `madspec agents subagents list`

Показывает effective catalog ролей. С `--enabled-only` выводит только активные.

### `madspec agents subagents show`

Показывает одну effective role вместе с `origin`, `enabled` и `bodySource`.

### `madspec agents subagents create`

Создает новую project-defined роль.

Обязательные параметры:

- `--subagent-id <id>`
- `--from-file <json>`
- `--body-file <md>`

JSON-файл должен содержать:

- `title`
- `description`
- `purpose`
- `defaultStage`
- `executionModeHint`
- `dependencies`
- `toolPolicy`
- `outputContract`

### `madspec agents subagents update`

Обновляет project role или создает/обновляет project override встроенной роли.

Обязательные параметры:

- `--subagent-id <id>`
- `--from-file <json>`

Дополнительно:

- `--body-file <md>` — если нужно обновить project body роли

### `madspec agents subagents remove`

Удаляет project-defined роль или project override.

- Для enabled project-defined роли нужен `--force`
- Для built-in override удаление возвращает effective role к встроенному определению

### `madspec agents subagents enable` / `disable`

Точечно включает или отключает конкретную роль и перерендеривает средовые файлы.

### `madspec agents subagents context`

Экспортирует role-scoped context для конкретной роли.

Основные опции:

- `--subagent-id <id>`
- `--branch <name>`
- `--stage <stage>`
- `--step-id <id>`
- `--json-output`

Контекст собирается поверх:

- memory retrieve
- policy context
- gate status
- active change summary

## Native И Fallback

В v1 MADSpec не реализует собственный scheduler субагентов. Он управляет только каноническим состоянием и средовыми адаптерами.

- Native adapters: Cursor, GitHub Copilot, OpenCode, Qwen Code
- Fallback adapters: Kilo Code, Roo Code, SourceCraft

Fallback означает, что MADSpec по-прежнему хранит роли канонически, но выражает их через rules/commands/skills вместо нативных project-level subagent files.

Для native-адаптеров frontmatter не является универсальным:

- Cursor использует минимальный профиль с `description`, `execution_mode_hint` и `dependencies`
- OpenCode получает `mode: subagent`, `hidden: true` и строгую карту tools для поддерживаемых mutable/bash capabilities
- Qwen получает список Qwen-specific tools
- Copilot получает VS Code-specific tools и `user-invocable: false`

## Связанные Документы

- [Индекс CLI-документации](README.md)
- [Инициализация проекта](init.md)
- [Команды правил проекта](policy.md)
- [Команды структурированной памяти](memory.md)
