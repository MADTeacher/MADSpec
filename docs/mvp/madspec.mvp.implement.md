# `madspec.mvp.implement`

## Назначение команды

`madspec.mvp.implement` выполняет запланированные шаги реализации через step runtime-state, TDD checkpoints и completion records.

## Когда запускать

- после появления step catalog в `mvp.plan`
- для выполнения очередного executable step
- при возобновлении работы над уже начатым шагом

## Preconditions / required context

- существуют `.madspec/<BRANCH>/implementation-plan.md` и `progress.json`
- шаги уже зарегистрированы через `mvp.plan`
- для code steps действует TDD discipline
- для UI-шагов утвержденные прототипы из `.madspec/<BRANCH>/ui-prototype/` считаются UI contract, а не необязательным референсом
- перед началом работы агент обязан прочитать и использовать skill `madspec-cli-operator`

## Источник истины

### Canonical runtime state

- `.madspec/<BRANCH>/memory/progress.json`
- `.madspec/<BRANCH>/memory/working/active-session.json`

### Step-level knowledge

- `events.jsonl`
- `facts.jsonl`
- `decisions.jsonl`
- `contracts.jsonl`

### Generated views

- `.madspec/<BRANCH>/implementation-plan.md`
- `.madspec/<BRANCH>/steps/<step-id>/implementation-context.md`
- `.madspec/<BRANCH>/project-context.md`

## Входы команды

- `madspec memory retrieve --stage mvp.implement --json-output`
- `madspec memory start-step --stage mvp.implement`
- `madspec memory checkpoint-step --stage mvp.implement`
- `madspec memory complete-step --stage mvp.implement`
- `madspec git commit --message ...`

Из `retrieve` агент обязан читать `policy_context.required`, `policy_context.advisory` и текущие policy validations. При неочевидных блокировках допускается отдельный `madspec policy validate --stage mvp.implement --step-id <step-id> --json-output`.

## Пошаговый runtime workflow

1. Агент читает implement context через `retrieve`.
2. Агент сверяет выбранный step с `policy_context` и active required policies.
3. Запускает step через `start-step`, явно или по `nextExecutableStep`.
4. Для code steps фиксирует `red`, `green`, `refactor` через `checkpoint-step`.
5. Для UI-step реализация сверяется с утвержденным storyboard из `ui-prototype/index.html` и связанных экранов.
6. `complete-step` закрывает шаг, пишет semantic records и продвигает `currentImplementStep`.
7. После успешного completion агент создает git commit.

## Canonical data model

Ключевые runtime поля:

- `plannedSteps[]`
- `completedSteps[]`
- `currentImplementStep`
- `stepStatus[stepId].status`
- `stepStatus[stepId].tddPhase`
- `stepStatus[stepId].redEvidence[]`
- `stepStatus[stepId].greenEvidence[]`
- `stepStatus[stepId].refactorNote`
- `stepMetadata[stepId]`

Completion rules:

- `summary` обязателен
- step должен существовать в `plannedSteps`
- dependencies шага должны быть завершены
- для `code + required` обязательны `redEvidence`, `greenEvidence`, `refactorNote`
- после completion step переходит в `completed`, а runtime выбирает следующий executable step

## Generated artifacts

- обновленный `implementation-plan.md`
- `steps/<step-id>/implementation-context.md`
- `project-context.md`

## Диаграммы

```mermaid
flowchart TD
    A["madspec.mvp.implement"] --> R["retrieve implement context"]
    A --> S["start-step"]
    A --> C["checkpoint-step"]
    A --> F["complete-step"]
    S --> P["progress.json"]
    C --> P
    F --> P
    F --> K["facts/decisions/contracts"]
    F --> G["generated views"]
```

```mermaid
sequenceDiagram
    participant A as Агент
    participant M as Memory API
    participant P as progress.json
    participant E as events/semantic records

    A->>M: retrieve(stage=mvp.implement)
    A->>M: start-step(step-id?)
    M->>P: set current step
    A->>M: checkpoint-step(red)
    A->>M: checkpoint-step(green)
    A->>M: checkpoint-step(refactor)
    A->>M: complete-step(summary, facts, decisions, contracts)
    M->>P: mark completed + advance next step
    M->>E: append records
```

```mermaid
stateDiagram-v2
    [*] --> Planned
    Planned --> InProgress: start-step
    InProgress --> Red: checkpoint red
    Red --> Green: checkpoint green
    Green --> Refactor: checkpoint refactor
    Refactor --> Completed: complete-step
    InProgress --> Completed: waived / non-code
```

```mermaid
flowchart LR
    M["stepMetadata.tddPolicy"] --> V["completion validator"]
    S["stepStatus"] --> V
    D["step dependencies"] --> V
    V --> C["complete-step accepted"]
    V --> X["error"]
```

## Типовые ошибки / drift / ограничения

- `progress.json` редактируется вручную
- step завершается без TDD evidence при `tddPolicy=required`
- шаг запускается до завершения зависимостей
- агент ориентируется на имя директории, а не на `retrieve/start-step` output
- UI реализуется "примерно похоже", но расходится с утвержденным storyboard без обновления `mvp.design`

## Соседние команды и handoff

- предыдущая команда: [`madspec.mvp.plan`](./madspec.mvp.plan.md)
- соседние quality-команды: [`madspec.review`](../other/madspec.review.md), [`madspec.security`](../other/madspec.security.md)

## Что не является источником истины

- `.madspec/<BRANCH>/implementation-plan.md`
- `.madspec/<BRANCH>/steps/<step-id>/implementation-context.md`
- ручные изменения runtime-state без step-команд
