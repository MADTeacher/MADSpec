# `madspec.feature.plan`

## Назначение команды

`madspec.feature.plan` строит step catalog для feature-ветки и синхронизирует его с `progress.json`, используя feature IDs и integration analysis из `feature.init`.

Команда должна стремиться к минимально достаточному числу шагов: для небольшой feature или легкого изменения агент выбирает один полный шаг, а не серию микро-шагов без реальной необходимости.

## Когда запускать

- после завершения `feature.init`
- при добавлении новых шагов реализации feature
- до начала `feature.implement`

## Preconditions / required context

- существует ratified `feature.init.json`
- planning coverage использует feature IDs из `feature.init`
- generated planning files не редактируются вручную
- перед началом работы агент обязан прочитать и использовать skill `madspec-cli-operator`

## Источник истины

### Canonical state

- `.madspec/<BRANCH>/memory/stages/feature.plan.json`
- `.madspec/<BRANCH>/memory/progress.json`

### Runtime / working state

- `stepMetadata`
- `stepStatus`
- `planningMetadata.stepDependencies`
- `coversFunctions`

### Generated views

- `.madspec/<BRANCH>/implementation-plan.md`
- `.madspec/<BRANCH>/planning-context-cache.md`
- `.madspec/<BRANCH>/steps/<step-id>/planning-context.md`
- `.madspec/<BRANCH>/project-context.md`

## Входы команды

- `madspec memory retrieve --stage feature.plan --toon-output`, если этот контекст читает агент
- `madspec memory capture --stage feature.plan --plan-overview ... --planning-principle ...`
- `madspec memory next-step --stage feature.plan --candidate-step ...`
- `madspec memory register-step --stage feature.plan ...`
- `madspec memory checkpoint --stage feature.plan --summary ...`

Из `retrieve` агент обязан читать `policy_context.required`, `policy_context.advisory` и `policy_context.pending_proposals_count`, чтобы feature plan не расходился с project-global active policies.

## Пошаговый runtime workflow

1. Агент читает `feature.init_status` и `feature_plan_status`.
   Первый вход в стадию лениво материализует `feature.plan.json`, `implementation-plan.md`, `planning-context-cache.md` и `project-context.md`, если их еще нет.
2. Агент читает `policy_context` и учитывает active policies при выборе `stepKind`, `tddPolicy` и зависимостей.
3. Определяет максимально крупный безопасный шаг для текущей feature-итерации.
4. Фиксирует planning strategy для feature.
5. Проверяет candidate step через `next-step`.
6. Регистрирует шаг через `register-step`, связывая `covers` с feature IDs.
7. Runtime обновляет `feature.plan.json`, `progress.json` и generated planning views.
8. `checkpoint` ратифицирует feature plan.

## Правила гранулярности шага

- Предпочитай максимально крупный безопасный шаг, который можно реализовать и проверить за один проход `feature.implement`.
- Если изменение маленькое и ведет к одному результату, оформляй его одним шагом даже при затрагивании нескольких файлов и видов работ.
- Не выделяй в отдельные шаги подготовку, тесты, документацию, мелкие правки контрактов и валидацию, если они нужны только для завершения того же самого изменения.
- Делить feature на несколько шагов нужно только при реальных зависимостях, отдельных пользовательских проверках, заметно разных рисках или явной просьбе пользователя получить подробный план.
- Если нет убедительной причины дробить, выбирай меньшее число шагов.

## Canonical data model

`feature.plan.json` использует ту же форму, что и `mvp.plan.json`:

- `planOverview`
- `planningPrinciples[]`
- `stepCatalog[]`
- `nextActions[]`
- `checkpointSummary`

Обязательные условия checkpoint:

- есть `planOverview`
- есть хотя бы один step
- step catalog валиден по `stepKind`, `tddPolicy`, `size`, `complexity`

Reference rules:

- каждый planned step из `progress.json` присутствует в `feature.plan.json`
- у каждого шага есть обязательные step files
- `covers` синхронизирован с feature IDs из `feature.init`

## Generated artifacts

- `implementation-plan.md`
- `planning-context-cache.md`
- `steps/<step-id>/planning-context.md`
- `project-context.md`

## Stage-aware materialization

- До первого реального входа в `feature.plan` файлы `feature.plan.json`, `implementation-plan.md` и `planning-context-cache.md` могут отсутствовать.
- Их отсутствие после `feature.init` не считается drift.
- `madspec memory init`, `madspec memory consolidate` и `madspec memory validate` по-прежнему могут собрать полный набор артефактов ветки.

## Диаграммы

```mermaid
flowchart TD
    I["feature.init.json"] --> A["madspec.feature.plan"]
    A --> R["retrieve feature_plan_status"]
    A --> C["capture strategy"]
    A --> N["next-step"]
    A --> G["register-step"]
    G --> P["feature.plan.json"]
    G --> PR["progress.json"]
    A --> K["checkpoint"]
```

```mermaid
sequenceDiagram
    participant A as Агент
    participant M as Memory API
    participant F as feature.init.json
    participant P as feature.plan.json
    participant R as progress.json

    A->>M: retrieve(stage=feature.plan)
    M->>F: read feature context
    M-->>A: feature_plan_status
    loop Каждый шаг
        A->>M: next-step(candidate)
        A->>M: register-step(covers=Fxx)
        M->>P: update
        M->>R: sync
    end
    A->>M: checkpoint(summary)
```

```mermaid
stateDiagram-v2
    [*] --> Empty
    Empty --> Strategy
    Strategy --> Cataloged
    Cataloged --> Synced
    Synced --> Ratified
```

```mermaid
flowchart LR
    F["feature IDs"] --> C["coversFunctions"]
    C --> R["progress metrics"]
    P["stepCatalog"] --> I["implementation-plan.md"]
    R --> I
```

## Типовые ошибки / drift / ограничения

- `covers` использует свободный текст вместо feature IDs
- шаги есть в `progress.json`, но отсутствуют в `feature.plan.json`
- агент использует generated plan view как primary source

## Соседние команды и handoff

- предыдущая команда: [`madspec.feature.init`](./madspec.feature.init.md)
- следующая команда: [`madspec.feature.implement`](./madspec.feature.implement.md)

## Что не является источником истины

- `.madspec/<BRANCH>/implementation-plan.md`
- `.madspec/<BRANCH>/planning-context-cache.md`
- ручные правки `progress.json`
