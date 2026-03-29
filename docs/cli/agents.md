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

Если metadata JSON лежит в проектной `.madspec/.tmp/`, после успешного `create` CLI удалит такой временный файл автоматически. При ошибке файл сохраняется, чтобы можно было исправить его и повторить вызов. Для путей вне `.madspec/.tmp/` автоочистки нет.

### `madspec agents subagents update`

Обновляет проектную роль или создает либо обновляет проектное переопределение встроенной роли.

Обязательные параметры:

- `--subagent-id <id>`
- `--from-file <json>`

Дополнительно:

- `--body-file <md>` — если нужно обновить собственный текст роли

Тот же lifecycle действует и здесь: временный metadata JSON из `.madspec/.tmp/` удаляется только после успешного `update`, а при ошибке сохраняется для повторной правки.

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
- `--session-key <key>` — выбрать локальный контекст выполнения для сеанса; по умолчанию используется `active`
- `--task-id <id>` — явно выбрать координацию через `task` вместо автоопределения по сеансу
- `--work-item-id <id>` — явно выбрать `work item` вместо автоопределения по сеансу
- `--json-output`
- `--toon-output` — отдать тот же контекст в TOON-представлении для прямого чтения агентом

Для режима включения важно различать два варианта:

- при конфигурации по умолчанию с `parallelRuntime.phase2Enabled=true` команда может читать `task/work-item` binding, related proposals и coordinator readiness;
- при явном `parallelRuntime.phase2Enabled=false` команда остается чувствительной к сеансу, но не подгружает автоматически `coordinator`-данные и не обещает coordinator-семантику.

Контекст собирается на основе:

- результата `madspec memory retrieve`
- контекста правил
- статуса gate-проверок
- краткой сводки активного пакета изменений

Для сценария "реализация текущего шага и параллельное планирование следующего" ориентируйся на пару команд, учитывающих сеанс: `madspec memory retrieve --session-key ...` для минимального контекста и `madspec memory explain --session-key ...` для объяснения локального фокуса сеанса и общего состояния процесса.

Базовая форма диагностического вызова: `madspec memory explain --session-key`.

Флаг `--session-key` нужен только для выбора локального контекста выполнения для сеанса. Он не превращает команду в диспетчер задач и не добавляет отдельный протокол координации.

В корневом `payload` команда также возвращает `session_key`, а поле `active_session` пока остается совместимым псевдонимом для уже разрешенного содержимого сеанса.

Если `parallelRuntime.phase2Enabled=true` и у сеанса уже есть активный claim на work item, команда автоматически добавляет в payload блок `coordination`:

- `task`
- `work_item`
- `claim`
- `session_binding`
- `proposal_summary`
- `coordinator`
- `ownership`
- `readiness`
- `related_proposals`
- `scheduler_hints`
- `dependency_state`

При необходимости этот же координационный контекст можно жестко зафиксировать через `--task-id` и `--work-item-id`, если в проекте не отключен `Phase 2`.

Если занятый сеанс уже работает внутри координации по `task`, сводка по `proposals` помогает понять, есть ли ожидающее применение, каков последний статус и какие `proposal_id` сейчас связаны с `work item`. Блок `coordinator` дополнительно объясняет готовность, владение и жесткие зависимости. Это слой чтения и объяснения поверх координационного состояния, а не исполнитель процесса.

Так как `madspec memory retrieve` теперь возвращает также `runtime_revision`, субагент может использовать этот номер как основу для последующих изменяющих команд `memory`. Если после чтения контекста роль должна вызвать `capture`, `checkpoint`, `register-step`, `start-step`, `checkpoint-step` или `complete-step`, в сценариях автоматизации и работы нескольких агентов стоит передавать `--expected-revision`, чтобы запись не затерла более свежее состояние ветки.

Если роли нужно не только прочитать контекст, но и понять расхождение между собственным локальным фокусом сеанса и общим указателем выполнения ветки, используй `madspec memory explain --session-key <key>`. Эта команда показывает локальный `current_step`, общий `currentImplementStep`, следующий исполнимый шаг и производные поля планирования в одном `payload`.

Для самых горячих путей записи одного `--expected-revision` теперь недостаточно: `register-step`, `start-step`, `checkpoint-step`, `complete-step`, а также `checkpoint --stage review|security` могут вернуть payload kind `scope_busy`, если другой процесс уже удерживает ограниченную аренду записи на ту же область состояния. Это временная занятость области, а не конфликт ревизий.

В текущей реализации это по-прежнему граница экспорта контекста для конкретной роли и текущего состояния выполнения ветки. Команда умеет читать уже существующую привязку `task` / `work-item` и готовность `coordinator`, если в проекте не отключен `parallelRuntime.phase2Enabled`, а жизненный цикл координационного состояния создается и изменяется не здесь, а через `madspec memory tasks ...`, `madspec memory work-items ...`, `madspec memory proposals ...` и `madspec memory coordinator explain`.

## Встроенные И Запасные Адаптеры

В v1 MADSpec не реализует собственный диспетчер субагентов. Он управляет только каноническим состоянием и адаптерами среды.

Базовый слой координации с `task` и `work-item` уже реализован в `madspec memory`, и теперь он расширен до координационного состояния с явными зависимостями, объяснением готовности и потоком применения через `proposal`. Сейчас этот слой считается `Phase 2`, включен по умолчанию, не запускает субагентов сам и остается каноническим протоколом оркестрации для внешней среды.

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
