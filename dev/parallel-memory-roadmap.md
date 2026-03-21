# Parallel Memory and Multi-Agent Runtime Roadmap

Этот документ одновременно служит дорожной картой и архитектурным решением уровня Epic 0 для parallel runtime в MADSpec. До завершения Epics 1–5 именно этот файл фиксирует baseline по canonical source, session model, ownership, conflict policy и rollout order.

## 1. Goal and Non-Goals

### Goal

MADSpec должен безопасно поддерживать:

- параллельную реализацию текущего шага и планирование следующего шага на одной ветке;
- несколько субагентов над одной задачей без порчи общего состояния памяти;
- сценарии с интенсивным чтением без блокировок;
- контролируемые конкурентные записи через сессии, ревизии, lease-механизмы и явные конфликты;
- совместимость с текущим single-agent режимом без обязательной ручной миграции проекта.

### Non-goals for Phase 1

На первой фазе не делаем:

- полноценный встроенный планировщик запуска субагентов;
- автоматическое слияние двух произвольных несовместимых изменений runtime-состояния;
- поддержку двух прямых writer-агентов в один и тот же `step_id`;
- сохранение file-first runtime как канонического источника истины;
- полный task/work-item runtime для многосубагентной оркестрации.

### Success criteria

Считаем задачу успешной, когда выполняются все условия:

- планирование `step-02` не ломает реализацию `step-01`;
- агент A и агент B видят разные `current_step` в своих session contexts;
- общее состояние ветки не теряет данные при конкурентных записях;
- несовместимые записи приводят к явному `conflict`, а не к silent overwrite;
- существующий single-agent сценарий продолжает работать с session key `active`;
- диагностические команды позволяют понять, почему запись была применена, отклонена, заблокирована lease-механизмом или помечена как конфликт.

## 2. Current-State Diagnosis

### Текущее поведение

В текущей реализации память ветки сочетает два разных назначения в одних и тех же runtime-файлах:

- `progress.json` хранит общее состояние хода работ;
- `active-session.json` фактически выступает глобальным курсором текущего контекста;
- planning и implementation оба пишут в общие branch files;
- `retrieve` опирается на global active session при выборе текущего шага;
- `write_json()` и `append_jsonl()` выполняют записи без compare-and-swap, без файлового lock и без общей транзакционной границы.

Проект уже использует `SQLite`, но сейчас он играет роль вторичного канонического зеркала:

- runtime-файлы ветки сначала изменяются напрямую;
- затем изменения синхронизируются в `SQLite`;
- таблица `sessions` уже умеет хранить несколько сессий;
- фактическая запись сейчас ведется только в системную session с ключом `active`;
- lease-механизм существует только для индексатора;
- branch merge/conflict primitives уже есть, но они применяются для межветочного merge, а не для внутриветочных конкурентных записей runtime.

### Ключевые ограничения по подсистемам

#### Memory shared storage

- branch JSON и JSONL являются фактическим write path;
- нет общего механизма сериализации writer-операций;
- rollback основан на восстановлении снимков файлов и может затереть параллельную успешную запись.

#### Planning workflow

- `register-step` обновляет и `progress`, и `active-session`;
- planning-команды могут перехватить runtime-фокус у агента, который в этот момент реализует шаг;
- derived поля пересчитываются внутри тех же операций, что повышает риск гонок и stale writes.

#### Implementation workflow

- `start-step`, `checkpoint-step` и `complete-step` тоже меняют общий `active-session`;
- несколько writer-операций над одной веткой не изолированы по session scope;
- восстановление снимков при ошибке не проверяет, не было ли новых коммитов после снятия снимка.

#### System store

- `SQLite` уже содержит таблицы для записей, снимков стадий, сессий, артефактов, очереди индексирования и lease-механизма;
- модель данных достаточно зрелая, чтобы стать каноническим слоем состояния;
- текущий код не использует эту возможность как основной write authority для runtime-переходов.

#### Branch merge and conflicts

- подсистема сравнения и слияния памяти уже умеет описывать конфликты;
- есть готовые сущности для conflict id, merge proposal, merge history и semantic fingerprints;
- эти механизмы пока не подключены к внутриветочным конкурентным runtime-записям.

#### Agents context and export layer

- слой субагентов уже знает про `executionModeHint` и `dependencies`;
- MADSpec пока не имеет собственного runtime-координатора субагентов;
- export контекста строится на общем branch context и не различает независимые рабочие сессии нескольких агентов.

## 3. Target Architecture

### Architectural baseline

Целевая модель должна разделять:

- каноническое общее состояние ветки;
- рабочие сессии отдельных агентов;
- materialized projections для совместимости и чтения;
- безопасный механизм конкурентных изменений.

### Canonical shared state

Каноническое состояние хранится только в `SQLite` и включает:

- branch runtime state;
- stage snapshots;
- semantic records;
- sessions;
- leases;
- revision metadata;
- proposal и work-item сущности второй фазы.

`SQLite` становится единственным источником истины для mutating memory-команд.

### Materialized projections

Файлы:

- `.madspec/<branch>/memory/*.json`;
- generated markdown views;
- step-level generated contexts;

остаются совместимыми проекциями. Они:

- пересобираются после успешного canonical commit;
- больше не являются authoritative write source;
- сохраняются ради обратной совместимости, диагностики и удобства чтения агентами.

### Shared branch state

Общее состояние ветки содержит:

- `plannedSteps`;
- `completedSteps`;
- `currentImplementStep`;
- `stepStatus`;
- `stepMetadata`;
- `coversFunctions`;
- stage snapshots;
- общую runtime revision;
- при необходимости дополнительные derived поля, которые всегда пересчитываются централизованно.

### Per-agent session state

Каждая рабочая сессия агента содержит:

- `session_key`;
- `stage`;
- `current_step`;
- `active_goal`;
- `pending_actions`;
- `open_questions`;
- `current_hypotheses`;
- служебные timestamps.

Session state:

- не должен перезаписывать session других агентов;
- не должен использоваться как глобальный курсор всех операций;
- должен быть доступен через `SQLite sessions`;
- должен проецироваться в `active-session.json` только для legacy session `active`.

### Ownership model

Ownership задается по scope и используется для writer-контроля:

- `plan-catalog`;
- `step`;
- `file-scope`;
- `artifact`;
- `work-item`.

Один и тот же scope не может одновременно иметь двух активных writer-owner без явного conflict path.

### Concurrency model

Целевая модель конкурентности:

- read operations работают без блокировок;
- write operations используют revision-aware optimistic concurrency;
- совместимые изменения автоматически merge'ятся по заранее зафиксированным правилам;
- несовместимые изменения возвращают структурированный `conflict`;
- hot scopes могут требовать scoped lease;
- derived поля не принимаются от callers как authoritative и пересчитываются централизованно после merge или commit.

### Coordinator model for multi-agent tasks

Во второй фазе многосубагентная работа над одной задачей строится через coordinator model:

- субагенты не должны напрямую менять shared task runtime;
- они формируют proposals;
- coordinator или apply path коммитит proposals в общее canonical state;
- `executionModeHint` и `dependencies` используются как policy hints, а не как единственный механизм безопасности.

## 4. Phase Breakdown

### Phase 1: Safe Parallel Runtime MVP

Цель первой фазы:

- безопасно поддержать параллельное planning + implementation на одной ветке;
- убрать главный источник гонок в runtime memory;
- ввести per-agent sessions;
- перевести runtime writes на SQLite-first path;
- добавить revisions и scoped leases для hot write paths.

Результат фазы:

- MADSpec официально поддерживает сценарий: реализуем текущий шаг и параллельно планируем следующий шаг;
- single-agent режим остается рабочим через `active`;
- многосубагентная работа над одной задачей пока ограничена read-heavy и coordination-lite сценариями.

### Phase 2: Multi-Agent Task Orchestration

Цель второй фазы:

- поддержать несколько субагентов над одной задачей через task/work-item модель;
- ввести proposal-based commit flow;
- добавить coordinator runtime;
- расширить контекст субагентов данными о задаче, work item и ownership.

Результат фазы:

- несколько субагентов могут безопасно сотрудничать над одной задачей;
- runtime поддерживает controlled apply path вместо direct shared writes;
- конфликты, ownership и зависимость работ становятся канонически описанными сущностями.

## 5. Epic Roadmap

### Epic 0 — Architecture Baseline and ADR Lock

**Objective**

Зафиксировать архитектурные решения до начала кода, чтобы следующие эпики не расходились по модели памяти и конкурентности.

**Decisions to lock**

- `SQLite` становится каноническим state layer.
- Branch JSON и markdown остаются projections.
- `active-session` становится per-session, а не global cursor.
- Модель конкурентности — optimistic, а не global mutex.
- Merge policy ограниченная, deterministic и типизированная по операциям.
- Полная многосубагентная запись в общее runtime-состояние задачи выполняется только через proposals и coordinator.

**Deliverables**

- встроенный ADR-блок в этом документе;
- mapping текущих подсистем в целевую архитектуру;
- список публичных CLI-изменений;
- список внутренних application-layer интерфейсов, которые придется изменить.

**Acceptance criteria**

- не остается открытых решений по canonical source, session model, ownership model, conflict policy и фазам rollout;
- каждый следующий эпик опирается на явно зафиксированные архитектурные инварианты;
- implementer не должен самостоятельно выбирать concurrency model.

**Dependencies**

- нет.

**Implementation notes**

- В этом эпике кода может быть мало или не быть вовсе, но документ и интерфейсные решения должны быть окончательно согласованы.

**Risks**

- Если пропустить этот эпик или оставить открытые решения, Phase 1 быстро распадется на несовместимые локальные правки.

#### Embedded ADR — Epic 0 Lock

##### Status

- status: accepted
- scope: `docs + contracts`
- behavior change in Epic 0: none

##### Accepted decisions

- `SQLite` — выбранный future canonical state layer для mutating memory-команд.
- Файлы в `.madspec/<branch>/memory/` и generated markdown остаются совместимыми projections и rebuildable views.
- В текущей реализации mutating runtime-команды все еще работают по file-first path и только затем синхронизируются в `SQLite`.
- `active-session` перестраивается в per-session model; session `active` остается compatibility default.
- Модель конкурентности — optimistic concurrency с revisions и типизированными merge rules, а не глобальный mutex.
- Горячие scopes дополнительно защищаются scoped lease-механизмом; reads остаются без блокировок.
- Полная многосубагентная запись в общее runtime-состояние одной задачи допускается только через proposals и coordinator model Phase 2.

##### Rejected alternatives

- Оставить file-first runtime каноническим источником истины.
- Сделать `active-session.json` глобальным курсором для всех writer-операций.
- Решать конкурентность единым branch-wide lock вместо revision-aware compare-and-apply.
- Разрешить нескольким direct writer-агентам писать в один и тот же `step_id` без ownership/conflict path.
- Считать текущий `madspec agents subagents context` эквивалентом готового coordinator runtime.

##### Architectural invariants

- В Epic 0 не меняется user-visible CLI behavior.
- `--session-key` и `--expected-revision` резервируются как future CLI surface, но не появляются в командах сейчас.
- structured payload kinds `conflict` и `scope_busy` резервируются как future response contract, но не включаются в текущий runtime.
- Derived runtime fields не должны становиться caller-authoritative в будущей модели.
- Single-agent совместимость через session key `active` обязательна на всем rollout path.

##### Current subsystem to target responsibility

| Current subsystem | Current responsibility | Target responsibility after rollout |
| --- | --- | --- |
| `madspec_cli.memory.shared.storage` | file-first runtime writes, layout bootstrap, legacy projections | legacy compatibility boundary и projection/file helpers |
| `madspec_cli.memory.shared.system_store` | secondary mirror, retrieval/indexing primitives, indexer lease | canonical persistence, sessions, revisions, leases, compare-and-apply |
| `madspec_cli.memory.projection` | materialization and retrieve views over branch files | projection-only layer rebuilt after canonical commits |
| `madspec_cli.features.agents.application.subagent_context` | role-scoped context export over current branch state | session/task/work-item aware export boundary для later epics |

##### Reserved public CLI contract

- Session-scoped commands, planned for future `--session-key` support:
  - `madspec memory retrieve`
  - `madspec memory search`
  - `madspec memory capture`
  - `madspec memory checkpoint`
  - `madspec memory register-step`
  - `madspec memory start-step`
  - `madspec memory checkpoint-step`
  - `madspec memory complete-step`
  - `madspec agents subagents context`
- Revision-aware mutating commands, planned for future `--expected-revision` support:
  - `madspec memory capture`
  - `madspec memory checkpoint`
  - `madspec memory register-step`
  - `madspec memory start-step`
  - `madspec memory checkpoint-step`
  - `madspec memory complete-step`
- Reserved flags:
  - `--session-key`
  - `--expected-revision`
- Reserved payload kinds:
  - `conflict`
  - `scope_busy`

##### Internal extension points

- First-wave session-aware request models:
  - `madspec_cli.memory.application.retrieve_context.RetrieveMemoryContextRequest`
  - `madspec_cli.memory.application.capture_stage.CaptureStageRequest`
  - `madspec_cli.memory.application.checkpoint_stage.CheckpointStageRequest`
  - `madspec_cli.memory.application.register_step.RegisterStepRequest`
  - `madspec_cli.memory.application.implementation_steps.ImplementationStepRequest`
  - `madspec_cli.features.agents.application.subagent_context.SubagentContextRequest`
- Future canonical write boundary:
  - `madspec_cli.memory.shared.system_store`
- Future projection-only boundary:
  - `madspec_cli.memory.projection`
- Legacy compatibility boundary:
  - `madspec_cli.memory.shared.storage`

##### Ownership scopes and lease scope patterns

- Ownership scopes:
  - `plan-catalog`
  - `step`
  - `file-scope`
  - `artifact`
  - `work-item`
- Lease scope patterns:
  - `plan-catalog:<branch>`
  - `implement-step:<branch>:<step-id>`
  - `artifact:<branch>:<path>`
  - `review:<branch>`
  - `security:<branch>`

##### Phase 1 compatibility matrix

- Allowed:
  - `madspec memory register-step(step-02)` + `madspec memory start-step(step-01)`
  - `madspec memory register-step(step-02)` + `madspec memory checkpoint-step(step-01)`
  - `madspec memory register-step(step-02)` + `madspec memory complete-step(step-01)`
- Conflict or busy:
  - `madspec memory register-step(step-02)` + `madspec memory register-step(step-02)`
  - `madspec memory checkpoint-step(step-01)` + `madspec memory checkpoint-step(step-01)`
  - dual writer on `implement-step:<branch>:<step-id>`

##### Glossary

- canonical state: authoritative mutable source of truth for runtime changes
- projection: rebuildable file or view materialized from canonical state
- session: рабочий контекст конкретного агента с собственным `current_step`
- ownership scope: область, внутри которой writer контролируется policy и conflicts
- scoped lease: временная блокировка только для горячего write scope

##### Rollout order

1. architecture baseline and ADR lock
2. session-scoped runtime
3. `SQLite`-first canonical writes
4. revision-aware optimistic concurrency
5. scoped leases and ownership
6. safe parallel planning and implementation
7. task/work-item model
8. proposal-based commits
9. coordinator runtime
10. diagnostics, migration and rollout hardening

---

### Epic 1 — Session-Scoped Runtime

**Objective**

Разделить общее состояние ветки и рабочий контекст конкретного агента.

**Changes**

- добавить `session_key` во все runtime application requests и CLI commands:
  - `retrieve`
  - `search`
  - `capture`
  - `checkpoint`
  - `register-step`
  - `start-step`
  - `checkpoint-step`
  - `complete-step`
- перевести session storage на `SQLite sessions`;
- оставить `active` как legacy default session key;
- обновить active-session projection:
  - projection по умолчанию показывает session `active`;
  - projection не используется как canonical write source;
- изменить step resolution order:
  - `explicit step_id`
  - `session.current_step`
  - `progress.currentImplementStep`
  - `next executable step`
- planning operations обновляют только session вызывающего агента;
- implementation operations обновляют:
  - shared `currentImplementStep`
  - session вызывающего агента
  - не трогают sessions других агентов.

**Deliverables**

- session-aware request/response models;
- session-aware retrieval behavior;
- session-aware projection behavior;
- backward-compatible CLI defaults;
- compatibility path для legacy session `active`.

**Acceptance criteria**

- planner session и implementation session видят разные `current_step`;
- planning `step-02` не меняет implementation context агента, работающего над `step-01`;
- legacy single-agent сценарии работают без дополнительных флагов;
- retrieve корректно выбирает шаг в новом порядке разрешения.

**Dependencies**

- Epic 0.

**Implementation notes**

- Сначала расширить внутренние request-модели и application layer.
- Затем протянуть `session_key` в CLI и projections.
- После этого убрать зависимости runtime-логики от global active session semantics.

**Risks**

- Частичное внедрение `session_key` только в части команд приведет к смешанному режиму и труднообъяснимому поведению.

**Test focus**

- retrieve с явным `step_id`;
- retrieve только с `session_key`;
- параллельное существование `planner` и `impl` sessions;
- legacy `active` session без регрессий.

---

### Epic 2 — SQLite-First Canonical Memory Writes

**Objective**

Убрать file-first write path как главный источник гонок и сделать каноническую запись транзакционной.

**Changes**

- вынести mutating write logic в canonical store layer;
- все mutating memory-команды сначала коммитят изменения в `SQLite`;
- после commit запускается projection and materialization pipeline;
- `write_json()` и `append_jsonl()` перестают быть authoritative runtime mutation API;
- branch memory files становятся rebuildable projections;
- rollback строится на canonical transaction + projection refresh/rollback, а не на blind file restore.

**Deliverables**

- canonical write application service;
- единый write path для runtime mutations;
- projection refresh pipeline после commit;
- явная граница между canonical tables и generated branch files.

**Acceptance criteria**

- ни одна runtime-команда не опирается на branch JSON как на канонический mutable source;
- projection rebuild после commit детерминирован и повторяем;
- ошибка в projection phase не приводит к потере уже подтвержденного canonical state без явно описанного rollback policy;
- слепое восстановление старых file snapshots больше не используется как основной rollback path.

**Dependencies**

- Epic 1.

**Implementation notes**

- Стоит начинать с progress/session/runtime write paths.
- Semantic records и generated artifacts можно переносить в canonical-first модель постепенно, но итоговый write contract должен быть единым.

**Risks**

- Неполный перенос write path создаст состояние, где часть операций canonical-first, а часть file-first, что опаснее текущей модели.

**Test focus**

- canonical commit + projection refresh;
- projection rebuild после сбоя в генерации;
- отсутствие прямой зависимости runtime mutations от branch JSON files;
- повторяемость materialization.

---

### Epic 3 — Revision-Aware Optimistic Concurrency

**Objective**

Сделать конкурентные записи безопасными, предсказуемыми и диагностируемыми.

**Changes**

- добавить shared branch runtime revision;
- все mutating memory commands принимают `expected_revision`;
- реализовать compare-and-apply path:
  - revision match -> commit
  - revision mismatch + compatible mutation -> merge + commit
  - revision mismatch + incompatible mutation -> `conflict`
- derived runtime fields не принимаются от callers как authoritative:
  - `progressMetrics`
  - `planningPhase`
  - `lastPlannedStep`
- после merge derived поля пересчитываются централизованно;
- добавить structured conflict payload:
  - conflict kind
  - scope
  - involved revisions
  - conflicting fields или `step_id`
  - retry guidance

**Deliverables**

- revision metadata model;
- compare-and-apply service;
- conflict response schema;
- centralized recomputation path для derived runtime fields.

**Acceptance criteria**

- concurrent compatible writes не теряют данные;
- concurrent incompatible writes возвращают явный conflict;
- stale write без conflict невозможен;
- derived поля после merge всегда валидны и не зависят от порядка поступления операций.

**Dependencies**

- Epic 2.

**Implementation notes**

- Модель merge должна быть строго типизированной по типу операции, а не универсальной по всем payload.
- Общая ревизия ветки должна быть удобна для диагностики и воспроизведения конфликтов.

**Risks**

- Слишком общий merge policy приведет к неочевидным авто-слияниям.
- Слишком жесткий conflict policy обесценит параллельную работу и сведет модель к глобальной сериализации.

**Test focus**

- stale revision write;
- compatible concurrent writes;
- incompatible concurrent writes;
- пересчет derived полей после merge.

---

### Epic 4 — Scoped Leases and Ownership for Hot Write Paths

**Objective**

Ограничить только действительно опасные конкурентные записи и не превращать всю ветку в единый lock.

**Changes**

- переиспользовать writer lease subsystem не только для indexer, но и для runtime writes;
- ввести scoped lease names:
  - `plan-catalog:<branch>`
  - `implement-step:<branch>:<step-id>`
  - `artifact:<branch>:<path>`
  - при необходимости `review:<branch>` и `security:<branch>`
- lease применяется только к mutation scopes с высокой вероятностью конфликта;
- read-only operations не требуют lease;
- ошибка lease acquisition возвращает structured `scope busy` payload.
- runtime writer owner id имеет формат `runtime:<mutation-kind>:<session-key>:<pid>:<uuid>`;
- `doctor` диагностирует active и expired writer lease по hot scopes ветки.

**Deliverables**

- scoped lease naming policy;
- lease acquisition/release path для runtime writes;
- policy table: какой тип операции требует какой lease;
- user-visible busy/conflict semantics.

**Acceptance criteria**

- два writer-а не могут одновременно модифицировать один и тот же hot scope;
- два writer-а могут параллельно работать в разных scopes одной ветки;
- retrieve и search не страдают от лишних блокировок;
- зависшие lease можно диагностировать и безопасно снимать по правилам.

**Dependencies**

- Epic 3.

**Implementation notes**

- Lease не должен заменять revisions; он только защищает самые горячие scope.
- Lease policy должна быть минимальной, иначе параллелизм снова превратится в последовательный runtime.

**Risks**

- Слишком широкие lease scopes убьют полезный параллелизм.
- Слишком узкие lease scopes оставят опасные перекрытия без защиты.

**Test focus**

- lease contention на одном step scope;
- отсутствие contention на разных scopes;
- stuck lease detection;
- release и повторное захватывание lease.

---

### Epic 5 — Safe Parallel Planning and Implementation

**Objective**

Формально поддержать главный сценарий: реализуем текущий шаг и параллельно планируем следующий.

**Changes**

- зафиксировать compatible write matrix:
  - `register-step(step-02)` + `checkpoint-step(step-01)` => allowed
  - `register-step(step-02)` + `complete-step(step-01)` => allowed
  - `register-step(step-02)` + `start-step(step-01)` => allowed
  - `register-step(step-02)` + `register-step(step-02)` => conflict
  - `checkpoint-step(step-01)` + `checkpoint-step(step-01)` => same-scope conflict, если это не один и тот же owner/session
- planning writes не меняют shared execution cursor, кроме централизованно пересчитываемых planning metadata;
- implementation writes не ломают plan catalog при завершении текущего шага;
- retrieve и explain показывают:
  - session-local focus
  - shared workflow state
  - next executable step
  - общий progress и текущие derived planning fields.

**Deliverables**

- compatibility matrix в документации;
- runtime merge rules для coexistence planning/implementation;
- updated policy/gate integration для session-aware operations;
- рабочий сценарий Phase 1 в CLI и тестах.

**Acceptance criteria**

- сценарий “`step-01` implementation + `step-02` planning” официально поддержан и покрыт тестами;
- shared workflow остается согласованным после конкурентных операций;
- implementation session всегда видит правильный active implementation context;
- planning session не перехватывает execution focus другого агента.

**Dependencies**

- Epic 4.

**Implementation notes**

- Этот эпик завершает Phase 1 и должен быть первым публично демонстрируемым результатом roadmap.

**Risks**

- Если compatibility matrix не будет реализована строго, часть разрешенных сценариев окажется псевдоподдержкой с неявными конфликтами.

**Test focus**

- planning next step while implementation is in progress;
- planning + start-step;
- planning + complete-step;
- same-step dual checkpoint conflict.

---

### Epic 6 — Work Item Model for One Task / Many Subagents

**Objective**

Поддержать несколько субагентов над одной задачей без прямых записей всех участников в общий runtime.

**Changes**

- добавить `task_id` как верхнеуровневый контейнер работы;
- добавить `work_item_id` с полями:
  - owner
  - session key
  - subagent id
  - title
  - type
  - status
  - optional `step_id`
  - scope descriptor
  - acceptance note
- один task может включать несколько work items:
  - research
  - architecture
  - implementation slice
  - testing
  - docs
  - security
- ownership work item определяет, кто может публиковать и применять изменения в соответствующий scope.

**Deliverables**

- task/work-item domain model;
- storage model для tasks и work items;
- CLI/API operations для create/list/claim/release;
- связь между session и work item.

**Acceptance criteria**

- два субагента над одной задачей работают через разные work items;
- ownership виден в runtime и в контексте субагента;
- work items можно привязывать к одному `step_id` с непересекающимися scopes;
- система умеет различать task coordination и branch runtime progression.

**Dependencies**

- Epic 5.

**Implementation notes**

- Work item не должен быть просто красивой меткой; он должен участвовать в ownership, proposal routing и diagnostics.

**Risks**

- Слишком абстрактная work-item модель не поможет в реальной оркестрации.
- Слишком тяжелая модель перегрузит MVP и затянет Phase 2.

**Test focus**

- создание task;
- несколько work items на один task;
- ownership claim/release;
- привязка work item к step и scope.

---

### Epic 7 — Proposal-Based Multi-Agent Commit Flow

**Objective**

Перевести multi-agent writes из direct runtime mutation в controlled proposal/apply flow.

**Changes**

- добавить proposal types:
  - `plan_change`
  - `runtime_step_update`
  - `semantic_update`
  - `artifact_update`
- субагент формирует proposal вместо прямого shared commit;
- proposal содержит:
  - target scope
  - base revision
  - owner
  - session key
  - payload
  - conflict hints
- apply path:
  - валидирует ownership
  - валидирует revision
  - выполняет merge или conflict
  - фиксирует applied или rejected state
- compatible proposals могут применяться автоматически;
- conflicting proposals переводятся в explicit conflict state.

**Deliverables**

- proposal schema;
- proposal storage and lifecycle;
- preview/list/apply CLI surface;
- integration proposals with revision and ownership checks.

**Acceptance criteria**

- субагенты могут сотрудничать над одной задачей без прямой порчи shared runtime;
- совместимые proposals применяются чисто;
- несовместимые proposals переходят в reviewable conflict state;
- proposal lifecycle отражается в diagnostics и timeline.

**Dependencies**

- Epic 6.

**Implementation notes**

- Proposal flow должен стать единственным рекомендованным write path для Phase 2 task collaboration.

**Risks**

- Если оставить альтернативный direct shared write path для многосубагентной работы, Phase 2 останется частично небезопасной.

**Test focus**

- publish proposal;
- apply compatible proposal;
- conflicting proposal;
- proposal ownership violation;
- proposal with stale base revision.

---

### Epic 8 — Coordinator Runtime for Multi-Agent Tasks

**Objective**

Дать MADSpec собственный orchestration layer для субагентов над одной задачей.

**Changes**

- ввести coordinator service/application layer:
  - создает work items
  - назначает ownership
  - выдает leases
  - принимает proposals
  - применяет или отклоняет proposals
  - обновляет task status
- использовать существующие subagent metadata как scheduling hints:
  - `executionModeHint`
  - `dependencies`
  - role default stage
- расширить `madspec agents subagents context`:
  - `task_id`
  - `work_item_id`
  - `session_key`
  - ownership info
  - related proposals
- coordinator не обязан сам запускать агентов;
- coordinator обязан хранить каноническое orchestration state и задавать безопасный execution protocol среде.

**Deliverables**

- coordinator application model;
- context export with task/work-item awareness;
- dependency-aware readiness model for work items;
- coordinator-facing diagnostics surface.

**Acceptance criteria**

- MADSpec официально поддерживает несколько субагентов над одной задачей через канонический orchestration protocol;
- контекст выдается не только по роли, но и по task/work-item/session;
- зависимость между субагентами и готовность work items вычисляются детерминированно;
- coordinator может объяснить, почему тот или иной subagent scope сейчас доступен или заблокирован.

**Dependencies**

- Epic 7.

**Implementation notes**

- Встроенный coordinator должен быть policy and state layer, а не обязательно встроенный process runner.

**Risks**

- Смешение ролей coordinator как state owner и как process runner усложнит архитектуру и затруднит интеграцию со средами.

**Test focus**

- coordinator creates task and work items;
- coordinator assigns ownership;
- context export with work item awareness;
- dependency ordering between work items.

---

### Epic 9 — Retrieval, Explainability, Diagnostics and UX

**Objective**

Сделать parallel runtime понятным, наблюдаемым и пригодным для поддержки.

**Changes**

- обновить:
  - `retrieve`
  - `search`
  - `explain`
  - `timeline`
  - `doctor`
  - `conflicts`
- показывать одновременно:
  - shared branch state
  - current session state
  - active leases
  - pending proposals
  - conflict list
  - work-item ownership
- `doctor` должен диагностировать:
  - stale projections
  - orphan sessions
  - stuck leases
  - unresolved proposal conflicts
  - revision drift
- `timeline` должен различать:
  - session events
  - shared branch commits
  - proposal lifecycle
  - auto-merged writes
  - conflicts

**Deliverables**

- updated diagnostics payloads;
- improved human-readable CLI output;
- observability section в документации parallel runtime.

**Acceptance criteria**

- инженер может объяснить, почему запись была merge'нута, заблокирована lease-механизмом, отклонена или переведена в conflict;
- diagnostics умеют локализовать наиболее вероятную причину застрявшей многосубагентной работы;
- session/task/work-item state можно инспектировать без прямого обращения к базе.

**Dependencies**

- Epic 8.

**Implementation notes**

- Этот эпик критичен для эксплуатационной пригодности. Без него новая concurrency model будет формально существовать, но останется трудноотлаживаемой.

**Risks**

- Нехватка объяснимости приведет к тому, что пользователи будут воспринимать runtime как непредсказуемый.

**Test focus**

- doctor on stale projection;
- doctor on stuck lease;
- explain on conflict;
- timeline for merged and conflicted writes;
- inspect session and work-item ownership.

---

### Epic 10 — Testing, Migration, Docs and Rollout

**Objective**

Довести новую модель до production-ready состояния без ломки текущих пользователей и операторов.

**Changes**

- расширить test matrix:
  - legacy single-agent behavior
  - session-aware behavior
  - concurrent compatible writes
  - concurrent conflicting writes
  - scoped lease handling
  - proposal flow
  - coordinator/task/work-item behavior
- добавить migration strategy:
  - existing projects continue to work with default session `active`
  - legacy file projections still produced
  - no forced manual migration for basic usage
- обновить документацию:
  - `docs/cli/memory.md`
  - `docs/cli/agents.md`
  - workflow docs
  - `skills/madspec-cli-operator/SKILL.md`
- добавить rollout policy:
  - Phase 1 может быть включаемой через feature flag или config toggle, если реализация рискованна;
  - Phase 2 может оставаться opt-in до стабилизации.

**Deliverables**

- полный acceptance test suite;
- обновленные docs и operator skill;
- migration notes;
- rollout checklist;
- release readiness checklist.

**Acceptance criteria**

- существующие single-agent flows остаются поддержанными;
- новый parallel runtime имеет понятную документацию и troubleshooting guidance;
- CI покрывает и legacy mode, и новый parallel mode;
- rollout strategy не требует разрушительной миграции существующих branch memory layouts.

**Dependencies**

- Epic 9.

**Implementation notes**

- Этот эпик закрывает roadmap и должен сделать новую модель безопасной для реального внедрения, а не только для разработки.

**Risks**

- Недостаточная миграционная стратегия приведет к скрытым регрессиям в уже существующих проектах MADSpec.

**Test focus**

- full regression suite;
- docs accuracy checks;
- migration compatibility checks;
- rollout feature-flag behavior.

## 6. Milestones

### Milestone A — Safe Parallel Runtime

Состав:

- Epics 0–5 complete

Поддерживаемый сценарий:

- реализуем текущий шаг и параллельно планируем следующий шаг на той же ветке.

Критерии готовности:

- Phase 1 acceptance criteria закрыты;
- single-agent compatibility подтверждена;
- сценарий planning + implementation покрыт тестами и документацией.

### Milestone B — Multi-Agent Task Collaboration

Состав:

- Epics 6–8 complete

Поддерживаемый сценарий:

- несколько субагентов сотрудничают над одной задачей через work items и proposals.

Критерии готовности:

- task/work-item/proposal/coordinator model работает end-to-end;
- ownership и conflicts диагностируются и управляются предсказуемо.

### Milestone C — Production Hardening

Состав:

- Epics 9–10 complete

Поддерживаемый сценарий:

- diagnosable, documented, migration-safe rollout новой модели.

Критерии готовности:

- parallel runtime пригоден для публичного использования в CLI и agent workflows;
- legacy compatibility и operator documentation подтверждены.

## 7. Cross-Epic Compatibility Matrix

### Разрешенные конкурентные сценарии после Phase 1

- `register-step(step-02)` и `start-step(step-01)`
- `register-step(step-02)` и `checkpoint-step(step-01)`
- `register-step(step-02)` и `complete-step(step-01)`
- `retrieve/search/explain` параллельно с любыми write-операциями
- разные writer-операции в разных hot scopes при наличии совместимой revision и без lease collision

### Сценарии, которые должны приводить к conflict или busy

- `register-step(step-02)` и `register-step(step-02)`
- два `checkpoint-step` в один и тот же `step-01`, если это не один owner/session
- два writer-а на один `implement-step:<branch>:<step-id>`
- proposal apply с устаревшей базовой ревизией и несовместимым payload
- попытка subagent-а коммитить в scope, которым он не владеет

## 8. Test Scenarios

В итоговую реализацию и тестовый план обязательно входят:

- single-agent legacy flow без `--session-key`
- planner session и implementer session на одной ветке
- parallel compatible writes в разных scopes
- parallel incompatible writes в один и тот же `step_id`
- lease contention в hot scopes
- projection rebuild after canonical commit
- session-scoped retrieve с разным `step` focus
- task с несколькими work items для разных субагентов
- compatible proposals auto-applied
- conflicting proposals requiring explicit resolution
- diagnostics for stale session
- diagnostics for stuck lease
- diagnostics for pending conflict
- diagnostics for stale projection

## 9. Migration and Rollout Strategy

### Migration defaults

- session key `active` остается значением по умолчанию;
- legacy `active-session.json` сохраняется как projection;
- существующие branch memory layouts не требуют ручной миграции для базовых сценариев;
- новые поля и сущности должны добавляться так, чтобы старые проекты могли работать без немедленного обновления всех артефактов.

### Rollout strategy

- сначала выпускать архитектурный baseline и session model;
- затем переводить canonical write path;
- после стабилизации включать optimistic concurrency и scoped leases;
- только потом открывать task/work-item/proposal/coordinator path;
- если риск высок, держать новые режимы за feature flag или config toggle до закрытия regression suite.

### Operational safeguards

- при rollout обязательно иметь `doctor`, `timeline` и `conflicts` с поддержкой новой модели;
- feature flag не должен ломать legacy behavior;
- документация для операторов и агентных workflows обновляется в тот же change set, что и behavior.

## 10. Assumptions and Defaults

- filename: `dev/parallel-memory-roadmap.md`
- document style: technical roadmap, а не чистый RFC и не raw backlog
- `SQLite`-first canonical memory — выбранное направление
- file projections остаются для совместимости и удобства чтения
- `active` остается default session key для backward compatibility
- same-step dual-writer behavior блокируется или переводится в `conflict`, но не merge'ится автоматически
- полная поддержка нескольких субагентов над одной задачей относится к Phase 2, а не к MVP
- `executionModeHint` и `dependencies` продолжают использоваться как policy hints и входные сигналы для coordinator layer
