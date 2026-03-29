# `madspec memory`

Группа `madspec memory` — это рабочий интерфейс структурированной памяти в MADSpec. Через нее создается проектное хранилище памяти, читается контекст стадий, фиксируются решения, продвигается состояние планирования и реализации и проверяются производные представления.

Для изменяющих состояние переходов этот интерфейс теперь опирается на общий слой контрольных проверок: предварительные проверки планирования и реализации, а также `checkpoint` для `review` и `security`, выполняются через `madspec gate`.

Команды, привязанные к стадии (`retrieve`, `capture`, `checkpoint`, операции планирования и реализации), материализуют только минимально необходимый набор артефактов ветки для текущей стадии. Полная пересборка всех производных файлов ветки остается задачей `madspec memory init`, `madspec memory consolidate` и `madspec memory validate`.

Начиная с `Memory v2`, MADSpec использует смешанную модель хранения:

- `SQLite` в `.madspec/system/memory/memory.sqlite` — проектное хранилище записей, снимков стадий, сеансов, полнотекстового индекса и очереди индексирования
- `lancedb/` в `.madspec/system/memory/lancedb/` — корень векторного хранилища; внутри него MADSpec хранит активное пространство индекса вида `provider/model/revision/dimension`, а при `revision = null` использует нормализованный сегмент `current`
- `.madspec/<branch>/memory/` — структура памяти, привязанная к ветке, и служебные производные файлы для совместимости и материализации контекста ветки

Отдельно от векторного слоя теперь действует проектный контракт `memory.embeddings` в `.madspec/config.json`:

- он определяет выбранный provider, model, cacheDir, revision и downloadPolicy;
- подготовленная локальная семантическая модель хранится в локальном кэше проекта `.madspec/system/models/` или в кастомном `cacheDir`; при `revision = null` структура кэша тоже использует явный сегмент `current`
- `memory status` и `memory db-status` показывают выбранную конфигурацию `memory.embeddings` отдельно от корня векторного хранилища, активного пространства индекса, фактического текущего векторного движка и состояния `reindex required`;
- `memory search` и `memory retrieve` дополнительно возвращают `semantic_runtime`, где отдельно показаны выбранная конфигурация `memory.embeddings`, активное пространство индекса, итог семантического поиска и структурированная ошибка провайдера при проблемах с локальной семантической моделью.

Важно для текущего состояния реализации:

- все mutating runtime-команды теперь сначала коммитят изменения в `SQLite`, а уже потом пересобирают файловые проекции ветки;
- все изменяющие команды состояния теперь сначала фиксируют изменения в `SQLite`, а уже потом пересобирают файловые проекции ветки;
- branch `memory/*.json`, `memory/*.jsonl` и generated markdown остаются rebuildable projections;
- `SQLite` считается каноническим источником для `progress`, снимков стадий, состояния конкретной сессии и потоков записей состояния;
- для состояния выполнения ветки ведется единая верхнеуровневая ревизия `runtime_revision`, которая увеличивается после каждой успешной изменяющей записи;
- для самых горячих путей записи система дополнительно использует ограниченные аренды записи и может вернуть `kind="scope_busy"`, если другой процесс уже держит ту же горячую область;
- файл `.madspec/<branch>/memory/working/active-session.json` больше не считается источником истины и поддерживается только как производная проекция для session `active`;
- для `retrieve`, `search`, `explain`, `capture`, `checkpoint`, `register-step`, `start-step`, `checkpoint-step`, `complete-step` и связанных вызовов субагентного контекста доступен `--session-key`, по умолчанию используется `active`;
- изменяющие команды `capture`, `checkpoint`, `register-step`, `start-step`, `checkpoint-step` и `complete-step` принимают необязательный `--expected-revision`; если флаг не передан, команда использует ревизию, которую увидела в начале собственного выполнения;
- веточные `memory/*.json`, `memory/*.jsonl` и производные Markdown-представления остаются пересобираемыми проекциями и могут быть восстановлены через `madspec memory consolidate`;
- успешный изменяющий ответ теперь возвращает `runtime_revision_before` и `runtime_revision_after`, а при конфликте возвращается структурированный `payload` с `kind="conflict"` и полем `conflict.retry_guidance`;
- самые горячие пути записи `register-step`, `start-step`, `checkpoint-step`, `complete-step`, а также `checkpoint --stage review|security` используют ограниченную аренду записи вместо глобальной блокировки всей ветки;
- если обновление проекций после записи падает, каноническая запись не откатывается: команда возвращает `projection_status="stale"` и `projection_refresh_required=true`, а последующий `madspec memory consolidate` восстанавливает проекции из `SQLite`.
- Phase 1 теперь официально поддерживает сценарий: реализация текущего шага и параллельное планирование следующего, если операции попадают в совместимую матрицу `register-step(step-02)` + `start/checkpoint/complete-step(step-01)`.
- полный протокол `Phase 2` теперь включен по умолчанию через `parallelRuntime.phase2Enabled=true` в `.madspec/config.json`;
- явное `parallelRuntime.phase2Enabled=false` остается допустимым ручным переключателем для проекта, которому временно не нужен coordinator-flow;
- для базового многосубагентного сценария появился отдельный слой координации: `task` как контейнер работы и `work-item` как каноническая единица владения поверх локального состояния сеанса.
- Каноническое состояние координации тоже хранится в `SQLite`: таблицы `tasks`, `work_items`, `work_item_claims`, а их lifecycle events попадают в `records` со scope `work-item`.
- Для координационного состояния также используется явный граф зависимостей: `work_item_dependencies` хранит жесткие зависимости между `work items` внутри одного `task`.
- `claim` привязывает `session_key` к `work_item_id`, записывает канонический owner вида `work-item:<subagent-id>:<session-key>` и расширяет session payload полями `task_id`, `work_item_id`, `subagent_id`.
- Каждый work item теперь хранит snapshot scheduling hints в каноническом состоянии: `default_stage`, `execution_mode_hint`, `subagent_dependencies`.
- Если runtime-сеанс привязан к work item, `start-step`, `checkpoint-step` и `complete-step` валидируют совпадение `step_id` с ownership binding и продвигают статус work item в `claimed`, `in_progress`, `completed`.
- Для claimed `work-item` direct mutating runtime-команды больше не считаются допустимым write path: вместо `capture`, `checkpoint`, `register-step`, `start-step`, `checkpoint-step` и `complete-step` такой session должен публиковать proposal и затем применять его через отдельный apply flow.
- Жизненный цикл `proposal` теперь канонически хранится в `SQLite`: `runtime_proposals` и `runtime_proposal_events`, а связанная сводка попадает в `retrieve`, `explain`, `agents subagents context`, `timeline` и `doctor`.
- Готовность `coordinator` не хранится как отдельный постоянный статус: она вычисляется детерминированно при чтении на основе явных зависимостей, состояния `claim`, владения и контекста `proposal`.
- Для объяснимости и удобства оператора поверх канонического состояния теперь строится единая модель чтения `observability`: она объединяет общее состояние ветки, локальное состояние сеанса, аренды записи, `proposals`, владение, конфликты и здоровье пересобираемых проекций.
- `retrieve`, `search`, `explain`, `timeline`, `doctor` и `conflicts` теперь возвращают дополнительные данные `observability`, чтобы состояние `session`, `task` и `work-item` можно было инспектировать без прямого SQL-доступа.
- `doctor` теперь отдельно диагностирует `stale_projections`, `orphan_sessions`, `stuck_leases`, `unresolved_proposal_conflicts`, `revision_drift` и semantic integrity, а также сообщает `probable_cause` и `repair_hint`.
- `doctor` также проверяет готовность кэша локальной семантической модели и подтверждено ли текущее активное пространство индекса полной переиндексацией.
- `timeline` теперь нормализует жизненный цикл выполнения в типизированные события с полями `event_type`, `category`, `reason`, `owner_id`, `session_key`, `task_id`, `work_item_id`, `proposal_id` и `scope`.

Политика runtime для текущей версии:

- новые проекты получают в `.madspec/config.json` блок `parallelRuntime` со значениями по умолчанию `phase1Enabled=true` и `phase2Enabled=true`;
- если блок `parallelRuntime` отсутствует, MADSpec нормализует конфигурацию к тому же значению по умолчанию: `phase1Enabled=true`, `phase2Enabled=true`;
- команды CLI для coordinator-flow остаются видимыми в `help`, а при явном `parallelRuntime.phase2Enabled=false` завершаются структурированным `payload` с `reason="phase2_disabled"`;
- `madspec migrate` переносит layout и при нормализации конфигурации приводит проект к текущему контракту runtime по умолчанию.

## Когда Использовать

- чтобы посмотреть текущее состояние процесса в ветке
- чтобы зафиксировать факты, решения, контракты и состояние конкретной стадии
- чтобы ратифицировать неитеративную стадию
- чтобы регистрировать и продвигать шаги планирования или реализации
- чтобы пересобирать и валидировать производные файлы
- чтобы понять, почему выбран следующий шаг и какие записи влияют на контекст
- чтобы диагностировать дрейф производных представлений, проблемы индексирования и явные конфликты памяти

## Группы Команд

### Инициализация И Обслуживание Ветки

| Команда | Назначение |
| --- | --- |
| `madspec memory init` | Создать структуру памяти и производные представления для ветки |
| `madspec memory status` | Показать, существуют ли ключевые файлы памяти, выбранная конфигурация `memory.embeddings` и активное пространство индекса |
| `madspec memory db-status` | Показать состояние проектного `SQLite`, корня векторного хранилища, активного пространства индекса и выбранной конфигурации `memory.embeddings` |
| `madspec memory bootstrap-model` | Подготовить выбранную локальную семантическую модель в локальном кэше проекта без изменения конфига и без автоматического `reindex` |
| `madspec memory reindex` | Полностью пересобрать активное пространство индекса и обработать очередь индексирования для него |
| `madspec memory gc vector-namespaces` | Удалить неактивные пространства индекса целиком или показать кандидатов на удаление через `--dry-run` |
| `madspec memory consolidate` | Пересобрать производные Markdown-файлы из основного состояния памяти |
| `madspec memory validate` | Проверить основное состояние памяти и производные файлы |
| `madspec memory promote` | Перенести подтвержденные записи в семантическую память |
| `madspec memory learn --input ...` | Превратить результаты тестов или ревью в обучающие записи |

### Диагностика И Объяснение

| Команда | Назначение |
| --- | --- |
| `madspec memory doctor` | Провести диагностическую проверку без изменения памяти ветки, слоя `SQLite`, векторного индекса и производных представлений |
| `madspec memory explain --stage ...` | Объяснить текущий контекст стадии, влияние правил и результатов поиска по смыслу |
| `madspec memory timeline` | Показать объединенную историю записей, снимков состояния и `retrieval_runs` |
| `madspec memory why-next-step --stage ...` | Показать, почему выбран следующий шаг и почему остальные заблокированы |
| `madspec memory conflicts` | Показать явные записи со статусом `conflicted` и конфликты целостности |
| `madspec memory inspect-record --id ...` | Подробно показать каноническую запись, ее исходный файл и состояние индексирования |

### Межветочное Сравнение И Merge

| Команда | Назначение |
| --- | --- |
| `madspec memory compare-branches` | Сравнить снимки стадий, progress и подтвержденные записи знаний двух веток |
| `madspec memory propose-merge` | Подготовить предложение на слияние из ветки-источника в целевую ветку |
| `madspec memory preview-merge` | Показать предварительный просмотр предложения на слияние перед применением |
| `madspec memory resolve-conflict` | Зафиксировать решение по конфликту внутри предложения на слияние |
| `madspec memory merge-branches` | Применить ранее подготовленное предложение на слияние |
| `madspec memory promote-branch-knowledge` | Поднять подтвержденные знания из ветки на уровень проекта |

### Команды Для Состояния Стадии

| Команда | Назначение |
| --- | --- |
| `madspec memory retrieve --stage ...` | Получить минимальный контекст для стадии или шага |
| `madspec memory search --stage ... --query ...` | Посмотреть кандидатов из точного, полнотекстового и семантического поиска без полного контекста стадии |
| `madspec memory capture --stage ...` | Добавить факты и обновить основное состояние стадии |
| `madspec memory checkpoint --stage ... --summary ...` | Ратифицировать неитеративную стадию и пересобрать производные файлы |

### Команды Очистки Снимков Стадий

Эта группа работает только для канонических снимков стадий: `mvp.concept`, `mvp.design`, `mvp.tech`, `deploy`, `mvp.architecture`, `mvp.plan`, `feature.init`, `feature.plan`.

| Команда | Назначение |
| --- | --- |
| `madspec memory snapshots replace --stage ... --from-file ...` | Полностью заменить содержимое одного снимка стадии через канонический путь записи |
| `madspec memory snapshots prune --stage ... --from-file ...` | Точечно удалить элементы из списков снимка стадии по явным селекторам |

### Команды Semantic Knowledge

Эта группа работает с каноническим semantic knowledge двух типов:

- знания ветки в `semantic/facts.jsonl`, `semantic/decisions.jsonl`, `semantic/contracts.jsonl`
- знания уровня проекта в `records` с branch `__project__`, появляющиеся после `promote-branch-knowledge`

| Команда | Назначение |
| --- | --- |
| `madspec memory semantic retrieve --scope ...` | Получить полный semantic artifact для ветки или project scope |
| `madspec memory semantic replace --scope ... --from-file ...` | Полностью заменить semantic knowledge со статусами `validated`, `obsolete`, `conflicted` в выбранном scope |
| `madspec memory semantic prune --scope ... --from-file ...` | Точечно удалить semantic records со статусами `validated`, `obsolete`, `conflicted` по `record_id`, `fingerprint` или точному `match` |

### Команды Планирования

| Команда | Назначение |
| --- | --- |
| `madspec memory next-step --stage ...` | Выбрать следующий исполнимый шаг или проверить кандидата |
| `madspec memory register-step --stage ...` | Зарегистрировать запланированный шаг и обновить метаданные покрытия |

### Команды Выполнения Для Реализации

| Команда | Назначение |
| --- | --- |
| `madspec memory start-step --stage ...` | Запустить шаг реализации |
| `madspec memory checkpoint-step --stage ...` | Зафиксировать промежуточное состояние шага, включая контрольные точки TDD |
| `madspec memory complete-step --stage ... --summary ...` | Завершить текущий шаг и продвинуть текущее состояние выполнения |

### Команды Координации `Task` / `Work-Item`

Эта группа относится к Phase 2 и доступна по умолчанию. Если в проекте явно выставлен `parallelRuntime.phase2Enabled=false`, команда вернет отказ с `reason="phase2_disabled"` и guidance включить Phase 2 в `.madspec/config.json`.

| Команда | Назначение |
| --- | --- |
| `madspec memory tasks create --title ...` | Создать task как контейнер координации над общей веткой |
| `madspec memory tasks list` | Показать tasks ветки и их канонический status |
| `madspec memory work-items create --task-id ... --subagent-id ...` | Создать work item с канонической областью владения для конкретного субагента |
| `madspec memory coordinator explain` | Объяснить readiness, ownership, зависимости и связанные proposals для task/work item/session |
| `madspec memory work-items list` | Показать work items ветки, task или session |
| `madspec memory work-items claim --work-item-id ... --session-key ...` | Привязать session к work item и назначить канонический owner |
| `madspec memory work-items release --work-item-id ... --session-key ...` | Снять активный claim и очистить привязку сеанса |

### Команды Потока `Proposal`

Эта группа тоже относится к `Phase 2` и доступна по умолчанию. Если проект явно отключил `parallelRuntime.phase2Enabled`, команды остаются зарегистрированными в CLI, но не считаются доступным путем записи.

| Команда | Назначение |
| --- | --- |
| `madspec memory proposals publish --type ... --payload-json ...` | Опубликовать типизированное `proposal` вместо прямой записи для занятого `work item` |
| `madspec memory proposals list` | Показать `proposals` ветки, `task`, `work item` или сеанса |
| `madspec memory proposals preview --proposal-id ...` | Показать `proposal`, состояние владения, базовую ревизию и события жизненного цикла |
| `madspec memory proposals apply --proposal-id ...` | Применить `proposal` к каноническому состоянию выполнения или перевести его в `conflict` / `rejected` |

Базовые точки входа потока `proposal`: `madspec memory proposals publish` и `madspec memory proposals apply`.

Для semantic cleanup в claimed `Phase 2` session используется отдельный тип proposal:

- `semantic_cleanup` — proposal для branch-scoped `madspec memory semantic prune` и `replace`

Минимальный синтаксис:

Базовые точки входа: `madspec memory tasks create` и `madspec memory work-items claim`.

```bash
madspec memory tasks create --title "Coordinate auth"
madspec memory work-items claim --work-item-id <id> --session-key <key> --subagent-id <id>
```

Для explicit зависимостей между work items:

```bash
madspec memory work-items create --task-id <task> --subagent-id developer --depends-on-work-item <work-item-id> ...
```

## Рекомендуемая Схема Использования

Для разных фаз MADSpec использует разные наборы команд:

- неитеративные стадии вроде `mvp.concept`, `mvp.design`, `mvp.tech`, `deploy`, `mvp.architecture`, `mvp.plan`, `feature.init`, `feature.plan`, `review` и `security` используют `retrieve`, `capture` и `checkpoint`
- если нужно убрать накопившиеся дубли или пересобрать один снимок стадии без ручного редактирования `.madspec/<branch>/memory/stages/*.json`, используй `madspec memory snapshots prune` или `madspec memory snapshots replace`
- если нужно убрать дубли или заменить semantic knowledge, сначала прочитай его через `madspec memory semantic retrieve`, затем используй `madspec memory semantic prune` или `madspec memory semantic replace`
- если branch-scoped `semantic prune|replace` запущен из claimed `Phase 2` session, команда не делает прямую запись, а автоматически публикует `semantic_cleanup` proposal; после этого отдельно выполни `madspec memory proposals apply --proposal-id <id>`
- если `doctor` показывает residue в неактивных пространствах индекса, сначала посмотри кандидатов через `madspec memory gc vector-namespaces --dry-run`, затем при необходимости удали их через `madspec memory gc vector-namespaces`
- Процесс планирования использует `next-step` и `register-step` для поддержки каталога шагов и состояния покрытия
- Процесс реализации использует `start-step`, `checkpoint-step` и `complete-step` для управления текущим состоянием шага и TDD-доказательствами
- `consolidate` и `validate` поддерживают синхронность производных файлов и основных записей
- stage-scoped операции не обязаны заранее создавать несвязанные артефакты других стадий
- если меняется `memory.embeddings.provider`, `memory.embeddings.model`, `memory.embeddings.revision` или размерность текущего профиля, сначала подготовь кэш через `madspec memory bootstrap-model`, затем выполни `madspec memory reindex`; до этого состояние индекса считается неполным

Политика использования `Phase 2`:

- конфигурация по умолчанию уже включает протокол `task/work-item/proposals/coordinator`;
- если нужен только локальный session-flow без coordinator-path, проект может явно выставить `parallelRuntime.phase2Enabled=false` в `.madspec/config.json`;
- при миграции не требуется пересоздавать `.madspec/`, заново переносить структуру памяти ветки или отказываться от сеанса `active`.

## Общие Опции

У многих команд группы `memory` есть:

- `--branch <name>`: явно выбрать ветку для операции
- `--session-key <key>`: выбрать локальный контекст выполнения для сеанса; по умолчанию используется `active`
- `--expected-revision <n>`: для изменяющих команд состояния проверить, что запись делается поверх ожидаемой ревизии ветки
- `--json-output`: вывести JSON в удобном для автоматической обработки виде
- `--from-file <path>`: прочитать все аргументы из JSON-файла вместо командной строки

### Передача аргументов через файл (`--from-file`)

Команды `capture`, `checkpoint`, `register-step`, `start-step`, `checkpoint-step`, `complete-step`, `snapshots replace`, `snapshots prune`, `semantic replace` и `semantic prune` поддерживают опцию `--from-file <path>`. Когда она указана, CLI читает аргументы из JSON-файла вместо разбора командной строки.

Если путь находится внутри проектной `.madspec/.tmp/`, CLI считает такой файл временным рабочим входом: после успешного выполнения команды файл автоматически удаляется, а при ошибке чтения, валидации или отклонении команды файл сохраняется, чтобы агент мог поправить его и повторить вызов.

Для любых путей вне `.madspec/.tmp/` CLI никогда не удаляет файл автоматически и не берет на себя его жизненный цикл.

Это решает проблему ограничения длины командной строки на Windows (~8191 символов в cmd.exe), которая возникает при большом количестве параметров (например, `memory capture` для архитектуры).

**Формат JSON-файла:**

```json
{
  "stage": "mvp.concept",
  "summary": "Концепция утверждена",
  "facts": ["факт 1", "факт 2"],
  "decisions": ["решение 1"],
  "project_name": "MyProject",
  "system_overview": "Краткое описание системы",
  "audiences": ["разработчики"],
  "status": "validated"
}
```

Предпочтительный формат - канонические внутренние ключи, которые соответствуют именам полей в словаре `options` конкретной команды. Поля верхнего уровня (`stage`, `branch`, `json_output`, `status`, `summary`) извлекаются отдельно.

Для session-scoped операций в JSON также можно передать верхнеуровневый ключ `session_key`. Если он не указан, команда использует session `active`.
Для mutating runtime-команд в JSON также можно передать верхнеуровневый ключ `expected_revision`. Это полезно для multi-agent и automation-сценариев, когда запись должна опираться на заранее прочитанную ревизию.

CLI также принимает ключи-псевдонимы в стиле флагов, включая `snake_case` и `hyphen-case`. Например:

- `audience` -> `audiences`
- `pain` -> `pain_points`
- `pending-action` -> `pending_actions`
- `related-artifact` -> `related_artifacts`

Если в JSON одновременно указаны канонический ключ и его псевдоним, канонический ключ имеет приоритет. Неизвестные поля CLI отклоняет с понятной ошибкой вместо трассировки исключения.

**Пример использования:**

```bash
madspec memory capture --from-file .madspec/.tmp/capture-args.json --json-output
```

Для очистки снимков стадий используй отдельные JSON-контракты:

`snapshots replace`:

```json
{
  "stage": "mvp.architecture",
  "summary": "Заменить снимок архитектуры очищенной версией без дублей",
  "evidence": [".madspec/main/architecture.md"],
  "snapshot": {
    "architectureOverview": "Сервис на Go разделен на точку входа и прикладные слои.",
    "projectStructure": {
      "strategy": "feature-first",
      "rationale": "Изолировать игровую логику от точки входа",
      "directories": [
        {"path": "cmd/server", "purpose": "Основная HTTP-точка входа"}
      ]
    }
  }
}
```

`snapshots prune`:

```json
{
  "stage": "mvp.architecture",
  "summary": "Удалить дублирующиеся записи архитектуры",
  "operations": [
    {
      "path": "projectStructure.directories",
      "match": {"path": "cmd/server", "purpose": "Запуск CLI и HTTP"}
    },
    {
      "path": "codePrinciples",
      "equals": "Применять SOLID на границах прикладных сервисов."
    },
    {
      "path": "patterns",
      "match": {"name": "Repository", "rationale": "Не смешивать хранение данных с игровыми сервисами"}
    }
  ]
}
```

Контракт `snapshots replace`:

- верхний уровень: `stage`, `branch`, `session_key`, `expected_revision`, `json_output`, `summary`, `evidence`
- ключ `snapshot`: полное содержимое стадии в канонической форме
- системные поля снимка стадии вроде `revision`, `updatedAt` и `ratifiedAt` не считаются входом, которому CLI доверяет как источнику истины; они сохраняются и пересчитываются каноническим путём записи

Контракт `snapshots prune`:

- верхний уровень: `stage`, `branch`, `session_key`, `expected_revision`, `json_output`, `summary`, `evidence`
- ключ `operations`: список операций удаления
- для `list[str]` используй `{ "path": "<dot.path>", "equals": "<exact string>" }`
- для `list[object]` используй `{ "path": "<dot.path>", "match": { "<field>": "<exact value>", ... } }`

Если снимок стадии уже ратифицирован, `snapshots replace/prune` не позволят сохранить результат, который ломает обязательные поля checkpoint или ссылочную целостность стадии.

Рекомендуемый рабочий паттерн: писать временные JSON-файлы именно в `.madspec/.tmp/`. Тогда успешный вызов очистит их сам, а после неуспеха можно отредактировать тот же файл и повторить команду.

При использовании `--from-file` CLI-параметры, переданные в командной строке, служат значениями по умолчанию — значения из файла имеют приоритет.

Для `mvp.architecture` безопасный операторский сценарий выглядит так:

1. Прочитай текущее состояние через `madspec memory retrieve --stage mvp.architecture --full-artifact --json-output`.
2. Подготовь `.madspec/.tmp/architecture-prune.json` или `.madspec/.tmp/architecture-replace.json`.
3. Выполни `madspec memory snapshots prune --from-file ... --expected-revision <runtime_revision>` или `replace`.
4. При итоговой проверке запусти `madspec memory consolidate` и `madspec memory validate`, если нужно убедиться, что все производные представления пересобраны из `SQLite`.

Важно для `Phase 2`: если session уже привязан к claimed `work-item`, `snapshots replace/prune` завершаются явным отказом. Для этих команд пока нет пути записи через `proposals`; используй свободный session или освободи claim.

Для semantic knowledge используй отдельные контракты:

`semantic replace`:

```json
{
  "scope": "branch",
  "branch": "main",
  "summary": "Заменить semantic knowledge очищенной версией",
  "semantic": {
    "facts": [
      {
        "id": "fact-1",
        "semantic_kind": "fact",
        "summary": "Keep current leaderboard snapshot for replay",
        "stage": "mvp.plan",
        "scope": "branch",
        "status": "validated",
        "source": "memory.promote",
        "evidence": ["mvp.plan:fact"],
        "metadata": {"topic": "leaderboard"}
      }
    ],
    "decisions": [],
    "contracts": []
  }
}
```

`semantic prune`:

```json
{
  "scope": "project",
  "summary": "Удалить лишнее project-level решение",
  "operations": [
    {
      "semantic_kind": "decision",
      "fingerprint": "<fingerprint>"
    }
  ]
}
```

Контракт `semantic retrieve`:

- требует `--scope branch|project`
- для `scope=branch` использует выбранную ветку и возвращает её `runtime_revision`
- для `scope=project` читает знания из branch `__project__` и возвращает ревизию этого логического scope
- `--include-obsolete` и `--include-conflicted` явно добавляют записи со статусами `obsolete` и `conflicted`; без этих флагов команда возвращает только `validated`
- полный artifact возвращается как `semantic.facts[]`, `semantic.decisions[]`, `semantic.contracts[]`
- каждая запись включает как минимум `id`, `semantic_kind`, `summary`, `stage`, `step_id`, `scope`, `status`, `source`, `metadata`, `evidence`, `fingerprint`, `content_hash`

Контракт `semantic replace`:

- верхний уровень: `scope`, `branch`, `session_key`, `expected_revision`, `json_output`, `summary`, `evidence`
- ключ `semantic`: объект с массивами `facts`, `decisions`, `contracts`
- системные поля `branch`, `record_stream`, `content_hash` всегда пересчитываются
- для каждой semantic record разрешён `status` из набора `validated`, `obsolete`, `conflicted`
- для `scope=project` поле `id` пересчитывается по тому же правилу, что и в `promote-branch-knowledge`

Контракт `semantic prune`:

- верхний уровень: `scope`, `branch`, `session_key`, `expected_revision`, `json_output`, `summary`, `evidence`
- ключ `operations`: список операций удаления
- каждая операция обязана содержать `semantic_kind` и ровно один селектор:
  - `record_id`
  - `fingerprint`
  - `match`
- `match` в v1 поддерживает только точное сравнение по известным полям записи

Для branch scope безопасный операторский сценарий выглядит так:

1. Прочитай текущее знание через `madspec memory semantic retrieve --scope branch --branch <branch> --json-output`.
2. Подготовь `.madspec/.tmp/semantic-prune.json` или `.madspec/.tmp/semantic-replace.json`.
3. Выполни `madspec memory semantic prune --from-file ... --expected-revision <runtime_revision>` или `replace`.
4. Если команда вернула `proposal_mode=true`, примени proposal через `madspec memory proposals apply --proposal-id <id>`.
5. При необходимости проверь итог через `madspec memory semantic retrieve`, используй `madspec memory gc vector-namespaces --dry-run` для диагностики residue в неактивных пространствах, а полный `madspec memory reindex` запускай только если нужна полная пересборка active namespace.

Для project scope сценарий такой же, но без `--branch`:

1. `madspec memory semantic retrieve --scope project --json-output`
2. подготовка `.madspec/.tmp/project-semantic-prune.json` или `project-semantic-replace.json`
3. `madspec memory semantic prune|replace --scope project --from-file ... --expected-revision <runtime_revision>`

Важно для `Phase 2`: если session уже привязан к claimed `work-item`, branch-scoped `semantic prune/replace` автоматически публикуют `semantic_cleanup` proposal вместо прямой записи. Применение остаётся отдельным шагом через `madspec memory proposals apply`. Для `scope=project` session/proposal guardrail не применяется.

Контракт `semantic_cleanup` proposal:

- `proposal_type`: `semantic_cleanup`
- `target_scope`: `{"scope": "semantic-knowledge"}`
- payload верхнего уровня: `scope`, `operation`, `summary`, `evidence`
- `scope` в v1: только `branch`
- `operation`: `prune` или `replace`
- для `prune` обязателен `operations`
- для `replace` обязателен `semantic`

У `retrieve` дополнительно есть:

- `--session-key`
- `--step-id`
- `--limit`
- `--query`
- `--disable-semantic`
- `--recall-limit`
- `--scope <step|stage|branch|project>`
- `--include-obsolete`
- `--include-conflicted`
- `--full-artifact`
- `--include-history`

Ответ `retrieve` теперь также содержит:

- top-level `runtime_revision`
- top-level `session_key`
- `observability.shared_branch_state`
- `observability.current_session_state`
- `observability.active_leases`
- `observability.proposal_state`
- `observability.conflict_state`
- `observability.ownership_state`
- `observability.embeddings`
- `observability.projection_health`
- `observability.orphan_sessions`
- `observability.semantic_integrity`

## Semantic Integrity В `doctor`

`madspec memory doctor --json-output` теперь дополнительно возвращает top-level блок `semantic_integrity` со структурой:

- `status`
- `summary`
- `branch`
- `project`
- `active_vector_namespace`
- `inactive_vector_namespaces`

Каждый подраздел содержит:

- агрегированный `status`
- счётчики релевантных records/chunks/namespaces
- `issues[]`

Формат semantic issue:

- `code`
- `status`
- `scope`
- `summary`
- `details`
- `related_ids`
- `probable_cause`
- `repair_hint`

Основные issue codes текущей версии:

- `semantic_branch_projection_drift`
- `semantic_branch_record_shape_mismatch`
- `semantic_project_id_mismatch`
- `semantic_project_scope_mismatch`
- `semantic_project_record_shape_mismatch`
- `semantic_active_chunk_orphan`
- `semantic_active_chunk_scope_mismatch`
- `semantic_inactive_namespace_residue`

Severity по умолчанию:

- `error` для рассинхрона каноники/проекций и dangling active semantic chunks
- `warn` для residue в inactive namespace, если active namespace и canonical semantic records согласованы

Если `doctor` показывает semantic issue со статусом `error`, сначала исправляй канонический semantic layer через `semantic prune|replace` или `reindex` по подсказке `repair_hint`. Если semantic issue имеет статус `warn` и относится только к inactive namespace residue, это ещё не означает повреждение active semantic path: сначала проверь кандидатов через `madspec memory gc vector-namespaces --dry-run`.
- `observability.summary`
- `workflow.currentImplementStep`, `workflow.nextExecutableStep`, `workflow.lastPlannedStep`, `workflow.planningPhase`, `workflow.progressMetrics`
- `policy_context.required[]`
- `policy_context.advisory[]`
- `policy_context.pending_proposals_count`
- `coordination.task`
- `coordination.work_item`
- `coordination.claim`
- `coordination.session_binding`
- `coordination.proposal_summary`
- `coordination.coordinator`
- `coordination.ownership`
- `coordination.readiness`
- `coordination.related_proposals`
- `coordination.scheduler_hints`
- `coordination.dependency_state`
- `artifact_state.policy` при `--full-artifact`
- `recall.semantic_runtime`

`recall.semantic_runtime` показывает:

- `configured_embeddings`
- `active_vector_namespace`
- `semantic_requested`
- `semantic_used`
- `semantic_outcome`
- `runtime_provider`
- `provider_error`

Если выбранный провайдер локальной семантической модели не готов, а семантический путь действительно понадобился, `retrieve` завершается структурированным payload с `kind="embedding_provider_error"` и кодом выхода `1` вместо тихой деградации в режим exact/FTS-only.

Поле `active_session` пока остается в ответе как совместимый псевдоним для уже разрешенной session payload, чтобы не ломать существующих потребителей.

У `explain` теперь также есть:

- `--session-key` — выбрать локальный контекст выполнения для сеанса при объяснении

Ответ `madspec memory explain` по-прежнему возвращает верхнеуровневый `runtime_revision`, а в `summary` теперь явно показывает:

- `session_key`
- `session_current_step`
- `shared_current_implement_step`
- `next_executable_step`
- `last_planned_step`
- `planning_phase`
- `progress_metrics`
- `latest_runtime_outcome`

Дополнительно `madspec memory explain` теперь возвращает:

- top-level `observability`
- top-level `latest_runtime_outcome`
- `context.observability`

`latest_runtime_outcome` нужен для сценариев, когда нужно быстро объяснить, почему последняя запись была merge'нута, заблокирована lease-механизмом, отклонена или переведена в conflict.

У `search` теперь также есть:

- additive блок `observability`, чтобы оператор мог понять, связано ли отсутствие нужного результата с текущим runtime состоянием, pending proposals, conflicts или stuck leases.
- top-level `semantic_runtime`, чтобы было видно выбранный провайдер, готовность модели, активное пространство индекса и итог `semantic_outcome`.

Если выбранный провайдер локальной семантической модели не готов, а семантический путь был запрошен, `search --json-output` возвращает структурированный payload с `kind="embedding_provider_error"` и завершает команду с кодом `1`.

У `timeline` теперь каждый item дополнительно содержит:

- `event_type`
- `category`
- `reason`
- `owner_id`
- `session_key`
- `task_id`
- `work_item_id`
- `proposal_id`
- `scope`

Ключевые категории timeline:

- `session_event`
- `shared_commit`
- `proposal_event`
- `auto_merge`
- `conflict`

У `conflicts` теперь кроме legacy списков также есть:

- `conflict_dashboard.record_conflicts`
- `conflict_dashboard.proposal_conflicts`
- `conflict_dashboard.integrity_conflicts`
- `conflict_dashboard.projection_conflicts`
- `conflict_dashboard.coordinator_conflicts`
- `conflict_dashboard.summary`

Каждый dashboard conflict теперь возвращает:

- `kind`
- `scope`
- `summary`
- `related_ids`
- `probable_cause`
- `repair_hint`

## Observability И Диагностика

Новый observability read-model нужен для того, чтобы parallel runtime не выглядел как “черный ящик”.

Что можно увидеть без прямого обращения к базе:

- какой сейчас `runtime_revision` и какой shared branch state считается каноническим;
- какой session привязан к текущей работе и есть ли у него active claim;
- кто держит hot-scope lease и не выглядит ли lease застрявшим;
- какие proposals pending, conflicted или уже были auto-merged;
- где конфликт находится на самом деле: в record stream, в proposal flow, в coordinator ownership или в rebuildable projections;
- не отстают ли branch files и generated markdown от canonical `SQLite` state.

Если `doctor` сообщает `revision_drift` или `stale_projections`, это означает, что canonical state уже продвинулся, а rebuildable views не были успешно обновлены. В этом случае safe path - пересобрать projections из `SQLite`, а не пытаться вручную править branch memory files.
- `task_id`
- `work_item_id`
- `pending_proposals_count`
- `last_proposal_status`
- `related_proposal_ids`

В `context` команда также возвращает блок `coordination` с активными `task`, `work_item`, `claim` и привязкой сеанса, если текущий `session_key` уже связан с каноническим состоянием координации.
Если session привязан к claimed work item, тот же блок теперь включает `proposal_summary` с pending count, последним статусом и связанными proposal id.
Если coordinator runtime уже знает work item, тот же блок дополнительно содержит ownership/readiness/dependency details и scheduler hints, чтобы было видно, почему scope доступен, активен или заблокирован.

У `madspec memory coordinator explain` есть:

- `--task-id`
- `--work-item-id`
- `--session-key`
- `--json-output`

Команда возвращает coordinator-facing explain payload:

- `task`
- `work_item`
- `coordinator.readiness`
- `coordinator.ownership_state`
- `coordinator.dependency_state`
- `coordinator.related_proposals`
- `coordinator.scheduler_hints`

У `search` есть:

- `--session-key` — выбрать сеанс, из которого берутся `active_goal`, `open_questions` и `current_hypotheses` для автодополнения запроса
- `--query` — обязательный поисковый запрос
- `--scope <step|stage|branch|project>` — область поиска
- `--recall-limit` — сколько кандидатов брать из каждого канала поиска
- `--disable-semantic` — отключить семантический поиск по векторному индексу и оставить только `SQLite` с точным и полнотекстовым поиском

Ответ `search` также содержит верхнеуровневый `runtime_revision`, чтобы вызывающая сторона могла понять, на каком каноническом состоянии выполнения был собран результат.

## Ревизии И Конфликты Runtime

Для runtime-операций MADSpec использует optimistic concurrency на уровне ветки. Это значит:

- `retrieve`, `search` и `explain` возвращают верхнеуровневый `runtime_revision`;
- изменяющие команды могут принять `--expected-revision`, чтобы явно зафиксировать, поверх какой ревизии должна выполняться запись;
- если флаг не указан, CLI по-прежнему остается совместимым со старым сценарием одного агента и использует ревизию, прочитанную в начале команды;
- после успешного коммита ответ включает `runtime_revision_before` и `runtime_revision_after`.

Если между чтением и записью произошли конкурентные изменения, система пытается безопасно переиграть намерение на свежем каноническом состоянии только для совместимых случаев. Для несовместимых случаев команда возвращает конфликт и завершает выполнение с кодом `1`.

Для hot scopes, защищенных lease-механизмом, команда может завершиться раньше с `kind="scope_busy"`. Это не конфликт ревизий, а признак того, что другой writer сейчас держит lease на тот же scope.

Форма conflict-ответа:

```json
{
  "accepted": false,
  "kind": "conflict",
  "conflict": {
    "kind": "progress_conflict",
    "scope": "plan-catalog",
    "expected_revision": 3,
    "actual_revision": 4,
    "step_id": "step-02-session-persistence",
    "conflicting_fields": ["plannedSteps", "stepStatus"],
    "retry_guidance": "Run retrieve or explain to refresh runtime state, then retry with the latest runtime_revision."
  }
}
```

Практически это означает:

- перед цепочкой нескольких mutating команд стоит сделать `madspec memory retrieve --stage <stage> --json-output` и взять из ответа `runtime_revision`;
- затем эту ревизию можно передавать через `--expected-revision`;
- если команда вернула `kind="conflict"`, нужно перечитать состояние, взять свежий `runtime_revision` и повторить операцию уже на обновленном контексте.

Форма `scope_busy`-ответа:

```json
{
  "accepted": false,
  "kind": "scope_busy",
  "scope_busy": {
    "scope": "step",
    "lease_name": "implement-step:main:step-01-authentication",
    "owner_id": "runtime:checkpoint-step:impl:12345:uuid",
    "expires_at": 1770000000,
    "retry_guidance": "Retry after the active writer releases the lease or after the lease TTL expires."
  }
}
```

Практически это означает:

- `scope_busy` не равен `conflict`: он говорит о временной занятости hot scope, а не о несовместимости ревизий;
- после `scope_busy` можно повторить ту же операцию без нового `retrieve`, если контекст еще актуален и нужно только дождаться освобождения scope;
- `madspec memory doctor` теперь показывает active и expired writer lease для диагностики зависших hot scopes.

Для сценария Phase 1 это означает следующую матрицу:

- `register-step(step-02)` + `start-step(step-01)` => allowed
- `register-step(step-02)` + `checkpoint-step(step-01)` => allowed
- `register-step(step-02)` + `complete-step(step-01)` => allowed
- `register-step(step-02)` + `register-step(step-02)` => `conflict`
- `checkpoint-step(step-01)` + `checkpoint-step(step-01)` => `scope_busy` при одновременном hot writer и `conflict` для stale replay после чужого коммита

## Слои Памяти

`madspec memory` использует несколько слоев памяти с разной ролью. Это помогает отделить каноническое проектное хранилище от памяти, привязанной к ветке, и от разных типов знаний.

## Stage-aware materialization

- Общий минимальный runtime-набор ветки включает `progress.json`, проекцию `active-session.json`, `decision-log.jsonl`, `events.jsonl` и `semantic/*.jsonl`.
- Операции, привязанные к стадии, дополнительно создают каноническое состояние и производные представления только для текущей стадии.
- Отсутствие нерелевантных производных артефактов не считается ошибкой, пока соответствующая стадия еще не была инициализирована.
- `madspec memory validate` в своем полном сценарии по-прежнему проверяет полный набор материализованных артефактов ветки.

## Связь с контрольными проверками

- `register-step`, `start-step`, `checkpoint-step`, `complete-step` и `checkpoint --stage review|security` сначала вычисляют общий `gate_summary`
- если общий статус равен `blocked`, команда завершается ошибкой до изменения памяти
- `madspec memory explain --json-output` возвращает top-level `gate_summary` и включает его в `context`
- `madspec memory retrieve --toon-output` и `madspec memory explain --toon-output` возвращают тот же канонический payload в TOON-представлении для прямой передачи агенту
- `madspec memory why-next-step --json-output` возвращает `gate_summary` для каждого шага вместо прежнего `policy_notes`
- `project-context.md`, `implementation-context.md`, `review.md` и `security-audit.md` показывают производную сводку проверок и активных исключений

| Слой | Что хранит | Кто пишет | Когда читается | Роль |
| --- | --- | --- | --- | --- |
| `.madspec/system/memory/memory.sqlite` | записи, снимки стадий, сеансы, задания индексирования, истории извлечения, FTS | все `memory`-команды через общий слой хранения | при каждом чтении и изменении | Каноническое проектное состояние |
| `.madspec/system/memory/lancedb/` | корень векторного хранилища и изолированные пространства индекса вида `provider/model/revision/dimension`; при `revision = null` используется сегмент `current` | `memory reindex`, фоновое индексирование при извлечении | при семантическом поиске | Семантическое расширение контекста |
| `episodes/events.jsonl` | События хода работы | `start-step`, `checkpoint-step`, `complete-step`, `memory learn` | `memory retrieve` для стадий реализации, `review` и `security`; для ранних стадий планирования только с `--include-history` | Операционная история |
| `working/decision-log.jsonl` | Кандидаты решений, заметки контрольных точек, процедурные подсказки | `memory capture`, `memory checkpoint`, `memory learn` | `memory retrieve`, `memory promote` | Буфер решений и кандидатов на обучение |
| `working/active-session.json` | Производная проекция канонического session state только для session `active` | session access layer поверх `SQLite` | совместимость веточного runtime-контекста и производных представлений | Совместимость и материализация |
| `semantic/facts.jsonl` | Подтвержденные факты | `complete-step` и `memory promote` | извлечение контекста и сборка производных представлений | Каноническое знание |
| `semantic/decisions.jsonl` | Подтвержденные решения | `complete-step` и `memory promote` | извлечение контекста и сборка производных представлений | Каноническое знание |
| `semantic/contracts.jsonl` | Подтвержденные контракты и обязательства | `complete-step` и `memory promote` | извлечение контекста и сборка производных представлений | Каноническое знание |

Знания уровня проекта после `promote-branch-knowledge` хранятся в таблице `records` проектного `SQLite` с branch `__project__`. При `retrieve/search --scope project` используются только эти project-level записи без подмешивания branch-level semantic knowledge.

Практически это означает:

- `SQLite` отвечает на вопросы "какое состояние сейчас каноническое", "что индексировать дальше" и "что подходит под точный и полнотекстовый поиск"
- `SQLite` также хранит локальное состояние выполнения для всех `session_key`, а файловая проекция поддерживается только для `active`
- активное пространство индекса внутри `lancedb/` отвечает на вопрос "что еще семантически похоже и стоит подтянуть в рабочий контекст"
- `episodes` отвечает на вопрос "что происходило по ходу работы"
- `decision_log` отвечает на вопрос "что еще нужно осмыслить, утвердить или продвинуть"
- `semantic/*` отвечает на вопрос "что уже считается подтвержденной истиной для ветки и стадии"

## Как Двигаются Записи Между Слоями

Типичный поток выглядит так:

1. `start-step`, `checkpoint-step` и `complete-step` пишут операционные события в `episodes`.
2. `capture`, `checkpoint` и `memory learn` добавляют заметки и кандидаты в `decision_log`.
3. `complete-step` может сразу записать подтвержденные `facts`, `decisions` и `contracts` в `semantic/*`.
4. Все эти операции сначала коммитят canonical state в `SQLite`, а затем пересобирают projections ветки; изменившиеся записи, снимки и артефакты ставятся в `index_jobs`.
5. `memory reindex` пересобирает только активное пространство индекса, определенное текущей конфигурацией `memory.embeddings`, а фоновое индексирование при извлечении работает в своем служебном пространстве и не удаляет соседние пространства. Для удаления неактивных пространств используй `madspec memory gc vector-namespaces`.
6. `memory promote` просматривает проверенные записи из `episodes` и `decision_log` и переносит их в `semantic/*`, если они еще не были продвинуты.

Из этого следуют два правила чтения:

- Для `mvp.concept`, `mvp.design`, `mvp.tech`, `deploy`, `mvp.architecture`, `mvp.plan`, `feature.init` и `feature.plan` история по умолчанию не подмешивается в `retrieve`; используйте `--include-history`, если нужен `episodes` и `decision_log`.
- Для стадий реализации, `review` и `security` история обычно важна для продолжения работы, поэтому `retrieve` включает ее автоматически.
- `retrieve` всегда может дополнительно собрать найденный контекст: точный и полнотекстовый поиск из `SQLite` и семантический поиск из векторного индекса, если сработали триггеры или передан `--query`

## Типовые Сценарии Использования

### Посмотреть состояние стадии перед продолжением

```bash
madspec memory retrieve --stage mvp.plan --json-output
madspec memory retrieve --stage mvp.plan --session-key planner --json-output
```

В JSON-ответе этой команды теперь есть `runtime_revision`, который можно использовать для последующей записи с `--expected-revision`.
В этом же ответе `recall.semantic_runtime` показывает выбранный провайдер, готовность модели и итог семантического пути (`used`, `disabled`, `skipped`, `provider_error`).

Если этот контекст должен читать агент, можно сразу использовать TOON:

```bash
madspec memory retrieve --stage mvp.plan --toon-output
```

### Зафиксировать запись поверх ожидаемой ревизии

```bash
madspec memory register-step \
  --stage mvp.plan \
  --step-id step-02-session-persistence \
  --covers "Session persistence" \
  --step-kind code \
  --expected-revision 7 \
  --json-output
```

Если за время между чтением и записью другая команда уже изменила состояние выполнения ветки, ответ вернет `kind="conflict"` и подскажет повторить операцию после чтения свежего `runtime_revision`.

### Посмотреть результаты поиска по явному запросу

```bash
madspec memory search --stage mvp.plan --query "billing step dependencies" --json-output
madspec memory search --stage mvp.plan --session-key impl --query "billing step dependencies" --json-output
```

В успешном ответе `search` теперь также содержит `semantic_runtime`, а при проблеме провайдера локальной семантической модели возвращает структурированный payload вместо тихого отключения семантического пути.

### Зафиксировать состояние стадии и ратифицировать его

```bash
madspec memory capture --stage mvp.tech --stack-overview "Веб-стек для быстрой поставки MVP"
madspec memory checkpoint --stage mvp.tech --summary "Технологический стек утвержден"
```

### Зарегистрировать шаг планирования

```bash
madspec memory next-step --stage mvp.plan
madspec memory register-step \
  --stage mvp.plan \
  --step-id step-01-auth \
  --step-kind code \
  --covers "Аутентификация пользователя"
```

### Продвинуть шаг реализации

```bash
madspec memory start-step --stage feature.implement
madspec memory checkpoint-step --stage feature.implement --tdd-phase red --red-evidence "Добавлен падающий тест"
madspec memory complete-step --stage feature.implement --summary "Форма биллинга реализована"
```

### Пересобрать и провалидировать производные файлы

```bash
madspec memory consolidate
madspec memory validate
```

### Обновить векторный индекс и посмотреть состояние хранилища

```bash
madspec memory db-status --json-output
madspec memory reindex --json-output
```

Ручная подготовка выбранной локальной семантической модели:

```bash
madspec memory bootstrap-model --json-output
```

### Сравнить ветки и подготовить слияние памяти

```bash
madspec memory compare-branches \
  --source-branch feature/auth \
  --target-branch main \
  --json-output

madspec memory propose-merge \
  --source-branch feature/auth \
  --target-branch main \
  --json-output

madspec memory preview-merge --proposal-id <PROPOSAL_ID> --json-output
madspec memory resolve-conflict --proposal-id <PROPOSAL_ID> --conflict-id <CONFLICT_ID> --resolution take_source --json-output
madspec memory merge-branches --proposal-id <PROPOSAL_ID> --json-output
```

### Продвинуть подтвержденные знания на уровень проекта

```bash
madspec memory promote-branch-knowledge --source-branch feature/auth --json-output
```

### Проверить здоровье памяти и объяснить контекст

```bash
madspec memory doctor --json-output
madspec memory explain --stage mvp.plan --json-output
madspec memory why-next-step --stage mvp.implement --json-output
madspec gate status --stage mvp.implement --operation complete-step --json-output
```

Для агентского чтения того же контекста:

```bash
madspec memory explain --stage mvp.plan --toon-output
madspec gate status --stage mvp.implement --operation complete-step --toon-output
```

### Посмотреть историю, конфликты и конкретную запись

```bash
madspec memory timeline --stage mvp.plan --json-output
madspec memory conflicts --json-output
madspec memory inspect-record --id <RECORD_ID> --json-output
```

## Что Обновляют Эти Команды

В зависимости от команды CLI обновляет:

- `.madspec/system/memory/memory.sqlite`
- `.madspec/system/memory/lancedb/` как корень векторного хранилища и активное пространство индекса внутри него
- `.madspec/system/memory/schema-version.json`
- `.madspec/<branch>/memory/stages/*.json`
- `.madspec/<branch>/memory/progress.json`
- `.madspec/<branch>/memory/working/active-session.json`
- `.madspec/<branch>/memory/working/decision-log.jsonl`
- `.madspec/<branch>/memory/episodes/events.jsonl`
- `.madspec/<branch>/memory/semantic/*.jsonl`
- производные файлы вроде `concept.md`, `architecture.md`, `implementation-plan.md`, `review.md` и `security-audit.md`

## Связанные Документы

- [Индекс CLI-документации](README.md)
- [Обзор процесса работы](../README.md)
- [MVP-процесс](../mvp/README.md)
- [Feature-процесс](../feature/README.md)
- [Команда `madspec.memory`](../other/madspec.memory.md)
- [Процессы review и security](../other/README.md)
