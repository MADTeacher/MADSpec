# `madspec agents`

`madspec agents` управляет каноническим слоем субагентов в MADSpec. Команда хранит активную среду, профиль ролей, проектный каталог субагентов, историю изменений и экспортирует контекст, подготовленный для конкретной роли.

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
- ревизию и временные метки
- список `enabledSubagentIds`

`catalog.json` задает проектные роли и проектные переопределения встроенных ролей.

Каждая итоговая роль получается как объединение:

- встроенного каталога MADSpec
- проектного каталога из `catalog.json`
- текста роли из `.madspec/system/agents/bodies/<subagent-id>.md`, если для проектной роли или переопределения задан собственный текст

`agentEnvironment` также определяет явный `subagentFrontmatterProfile` для встроенных сред. Через этот профиль MADSpec:

- выбирает допустимые YAML-поля для файлов агентов и субагентов
- фиксирует стратегию модели для среды
- строго переводит общий `toolPolicy` в набор инструментов, принятый в конкретной среде, вместо прямого копирования общих флагов

## Основные Команды

### `madspec agents profile`

Показывает активную среду, текущий профиль и включенные роли.

### `madspec agents recommend`

Возвращает рекомендованный базовый профиль ролей для текущего проекта.

Во встроенный начальный набор сейчас входят:

- `architecture`
- `developer`
- `contracts-data`
- `testing`
- `security`
- `research`
- `docs`

### `madspec agents propose-profile`

Создает предложение на изменение профиля ролей.

Основные опции:

- `--profile-id <id>`
- `--environment <agent>`
- `--subagent <id>` — повторяемый флаг для явного набора ролей

### `madspec agents apply-profile`

Применяет ожидающее предложение и заново формирует файлы выбранной среды.

### `madspec agents subagents list`

Показывает итоговый каталог ролей. С `--enabled-only` выводит только активные.

### `madspec agents subagents show`

Показывает одну итоговую роль вместе с `origin`, `enabled` и `bodySource`.

### `madspec agents subagents create`

Создает новую проектную роль.

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

Обновляет проектную роль или создает либо обновляет проектное переопределение встроенной роли.

Обязательные параметры:

- `--subagent-id <id>`
- `--from-file <json>`

Дополнительно:

- `--body-file <md>` — если нужно обновить собственный текст роли

### `madspec agents subagents remove`

Удаляет проектную роль или проектное переопределение.

- Для включенной проектной роли нужен `--force`
- Для переопределения встроенной роли удаление возвращает итоговую роль к встроенному определению

### `madspec agents subagents enable` / `disable`

Точечно включает или отключает конкретную роль и перерендеривает средовые файлы.

### `madspec agents subagents context`

Экспортирует контекст, подготовленный для конкретной роли.

Основные опции:

- `--subagent-id <id>`
- `--branch <name>`
- `--stage <stage>`
- `--step-id <id>`
- `--session-key <key>` — выбрать session-local runtime-контекст; по умолчанию используется `active`
- `--task-id <id>` — явно выбрать task coordination вместо автодетекта по session
- `--work-item-id <id>` — явно выбрать work item вместо автодетекта по session
- `--json-output`
- `--toon-output` — отдать тот же контекст в TOON-представлении для прямого чтения агентом

Контекст собирается на основе:

- результата `madspec memory retrieve`
- контекста правил
- статуса gate-проверок
- краткой сводки активного пакета изменений

Для сценария “реализация текущего шага и параллельное планирование следующего” ориентируйся на session-aware пару команд: `madspec memory retrieve --session-key ...` для минимального контекста и `madspec memory explain --session-key ...` для объяснения локального session focus и общего workflow state.

Флаг `--session-key` нужен только для выбора session-local runtime-контекста. Он не превращает команду в диспетчер задач и не добавляет отдельный протокол координации.

В top-level payload команда также возвращает `session_key`, а поле `active_session` пока остается совместимым псевдонимом для уже разрешенной session payload.

Если у сеанса уже есть активный claim на work item, команда автоматически добавляет в payload блок `coordination`:

- `task`
- `work_item`
- `claim`
- `session_binding`
- `proposal_summary`

При необходимости этот же координационный контекст можно жестко зафиксировать через `--task-id` и `--work-item-id`.

Если claimed session уже работает внутри task coordination, summary proposals помогает понять, есть ли pending apply, последний статус и какие `proposal_id` сейчас связаны с work item. Это read-only срез, а не coordinator runtime.

Так как `madspec memory retrieve` теперь возвращает также `runtime_revision`, субагент может использовать этот номер как основу для последующих mutating memory-команд. Если после чтения контекста роль должна вызвать `capture`, `checkpoint`, `register-step`, `start-step`, `checkpoint-step` или `complete-step`, в automation- и multi-agent сценариях стоит передавать `--expected-revision`, чтобы запись не затерла более свежее состояние ветки.

Если роли нужно не только прочитать контекст, но и понять расхождение между своим session-local focus и общим execution cursor ветки, используй `madspec memory explain --session-key <key>`. В том числе полезен буквальный вызов `madspec memory explain --session-key` с нужным значением сеанса. Эта команда показывает session-local `current_step`, общий `currentImplementStep`, следующий исполнимый шаг и planning-derived поля в одном payload.

Для hot write paths одного `--expected-revision` теперь недостаточно: `register-step`, `start-step`, `checkpoint-step`, `complete-step`, а также `checkpoint --stage review|security` могут вернуть `kind="scope_busy"`, если другой writer уже удерживает scoped lease на тот же runtime scope. Это временная занятость scope, а не ревизионный конфликт, и именно поэтому в контракте фигурирует payload kind `` `scope_busy` ``.

В текущей реализации это по-прежнему граница экспорта контекста для конкретной роли и текущего runtime state ветки. Команда умеет читать уже существующую привязку `task` / `work-item`, но жизненный цикл состояния координации создается и изменяется не здесь, а через `madspec memory tasks ...` и `madspec memory work-items ...`.

## Встроенные И Запасные Адаптеры

В v1 MADSpec не реализует собственный диспетчер субагентов. Он управляет только каноническим состоянием и адаптерами среды.

Базовый слой координации с `task` и `work-item` уже реализован в `madspec memory`, и proposal-based commit flow тоже уже доступен через `madspec memory proposals ...`. Следующей отдельной фазой roadmap остается coordinator runtime и более широкий orchestration protocol.

- Встроенные адаптеры: Cursor, GitHub Copilot, OpenCode, Qwen Code
- Запасные адаптеры: Kilo Code, Roo Code, SourceCraft

Запасный режим означает, что MADSpec по-прежнему хранит роли канонически, но выражает их через `rules`, `commands` и `skills` вместо встроенных файлов субагентов уровня проекта.

Для встроенных адаптеров блок frontmatter не является универсальным:

- Cursor использует минимальный профиль с `description`, `execution_mode_hint` и `dependencies`
- OpenCode получает `mode: subagent`, `hidden: true` и строгую карту `tools` для поддерживаемых изменяющих операций и команд оболочки
- Qwen получает список инструментов, принятых в среде Qwen
- Copilot получает инструменты, принятые в VS Code, и `user-invocable: false`

## Связанные Документы

- [Индекс CLI-документации](README.md)
- [Инициализация проекта](init.md)
- [Команды правил проекта](policy.md)
- [Команды структурированной памяти](memory.md)
