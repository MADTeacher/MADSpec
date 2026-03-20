# `madspec.feature.init`

## Назначение команды

`madspec.feature.init` анализирует существующий проект и формализует цель новой функциональности, ее problem statement, expected outcome и точки интеграции в текущем codebase.

## Когда запускать

- при начале работы над новой функциональностью в существующей ветке
- до любого feature planning
- когда нужно понять, какие файлы, модули и контракты будут затронуты

## Preconditions / required context

- существует codebase для анализа
- доступен branch context
- агент готов фиксировать findings в `feature.init.json`, а не только в markdown notes
- перед началом работы агент обязан прочитать и использовать skill `madspec-cli-operator`

## Источник истины

### Canonical state

- `.madspec/<BRANCH>/memory/stages/feature.init.json`

### Runtime / working state

- `active-session.json`
- semantic stage records
- минимальный runtime-набор ветки: `progress.json`, `decision-log.jsonl`, `events.jsonl`, `semantic/*.jsonl`

### Generated views

- `.madspec/<BRANCH>/project-analysis.md`
- `.madspec/<BRANCH>/feature-context.md`
- `.madspec/<BRANCH>/tech-stack.md`
- `.madspec/<BRANCH>/architecture.md`
- `.madspec/<BRANCH>/project-context.md`

## Входы команды

- пользовательское описание новой функциональности
- `madspec memory retrieve --stage feature.init --toon-output`, если этот контекст читает агент
- `madspec memory capture --stage feature.init ...`
- `madspec memory checkpoint --stage feature.init --summary ...`

## Пошаговый runtime workflow

1. Агент получает `feature_init_status`.
2. Анализирует текущий проект, модифицируемые файлы, новые файлы, зависимости и risks.
3. Сохраняет результат через `capture`.
4. Повторно читает short status и, при необходимости, `--full-artifact`.
5. `checkpoint` ратифицирует `feature.init.json` и пересобирает только производные артефакты `feature.init` и сводку ветки.

## Canonical data model

Ключевые поля:

- `featureGoal`
- `problem`
- `expectedOutcome`
- `projectAnalysis.projectType`
- `projectAnalysis.framework`
- `projectAnalysis.structureNotes[]`
- `projectAnalysis.existingModules[]`
- `projectAnalysis.modifiedFiles[]`
- `projectAnalysis.newFiles[]`
- `projectAnalysis.interfaceContracts[]`
- `projectAnalysis.dependencies[]`
- `projectAnalysis.risks[]`
- `projectAnalysis.recommendations[]`
- `projectAnalysis.techNotes[]`
- `projectAnalysis.architectureNotes[]`
- `features.p1[]`, `features.p2[]`, `features.p3[]`

Обязательные условия checkpoint:

- `featureGoal`
- `problem`
- `expectedOutcome`
- `projectAnalysis.framework`
- хотя бы одна feature
- есть `modifiedFiles` или `newFiles`

## Generated artifacts

- `project-analysis.md`
- `feature-context.md`
- `tech-stack.md`, собранный из `feature.init`
- `architecture.md`, собранный из `feature.init`
- `project-context.md`

## Stage-aware materialization

- `feature.init` создает только минимальный runtime-набор ветки, `feature.init.json` и свои производные представления.
- `concept.md`, `ui-design.md`, `data-model.md`, `contracts/openapi.yaml`, `implementation-plan.md`, `planning-context-cache.md`, `review.md` и `security-audit.md` не должны появляться только из-за `feature.init`.
- Артефакты других стадий материализуются лениво при первом входе в соответствующую стадию или через команды полной пересборки `madspec memory init`, `madspec memory consolidate`, `madspec memory validate`.

## Диаграммы

```mermaid
flowchart TD
    A["madspec.feature.init"] --> R["retrieve feature_init_status"]
    A --> C["capture analysis"]
    C --> S["feature.init.json"]
    A --> K["checkpoint"]
    S --> P["project-analysis.md"]
    S --> F["feature-context.md"]
    S --> D["tech-stack.md / architecture.md"]
    S --> X["project-context.md"]
```

```mermaid
sequenceDiagram
    participant A as Агент
    participant M as Memory API
    participant S as feature.init.json
    participant G as Generated views

    A->>M: retrieve(stage=feature.init)
    M-->>A: feature_init_status
    loop Анализ codebase
        A->>M: capture(goal/problem/files/dependencies/features)
        M->>S: update
    end
    A->>M: checkpoint(summary)
    M->>G: regenerate
```

```mermaid
stateDiagram-v2
    [*] --> Empty
    Empty --> Draft
    Draft --> Scoped: goal/problem/outcome filled
    Scoped --> Integrating: files and dependencies mapped
    Integrating --> Ratified
```

```mermaid
flowchart LR
    S["feature.init.json"] --> A["project-analysis.md"]
    S --> C["feature-context.md"]
    S --> T["tech-stack.md"]
    S --> R["architecture.md"]
```

## Типовые ошибки / drift / ограничения

- feature IDs не используются дальше в planning
- изменяемые файлы обсуждены, но не записаны в `modifiedFiles/newFiles`
- `tech-stack.md` принимается за основной источник истины

## Соседние команды и handoff

- предыдущая команда: начало feature workflow
- следующая команда: [`madspec.feature.plan`](./madspec.feature.plan.md)

## Что не является источником истины

- `.madspec/<BRANCH>/project-analysis.md`
- `.madspec/<BRANCH>/feature-context.md`
- `tech-stack.md` и `architecture.md`
