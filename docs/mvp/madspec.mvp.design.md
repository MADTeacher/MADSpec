# `madspec.mvp.design`

## Назначение команды

`madspec.mvp.design` описывает UX/UI проекта: платформы, зоны, экраны, пользовательские потоки, навигацию и покрытие concept features через design-state и prototype files.

## Когда запускать

- после ратификации `mvp.concept`
- когда нужно зафиксировать структуру интерфейса до выбора технологий
- при значимых изменениях экранов, flow или prototype coverage

## Preconditions / required context

- существует завершенный `mvp.concept`
- доступны prototype paths в `.madspec/<BRANCH>/ui-prototype/`
- design references должны указывать на существующие screens, zones и prototype files

## Источник истины

### Canonical state

- `.madspec/<BRANCH>/memory/stages/mvp.design.json`

### Runtime / working state

- `active-session.json`
- semantic records по stage
- feature coverage вычисляется из `screens[].covers`

### Generated views

- `.madspec/<BRANCH>/ui-design.md`
- `.madspec/<BRANCH>/project-context.md`

## Входы команды

- пользовательские требования к UX/UI
- `madspec memory retrieve --stage mvp.design --json-output`
- `madspec memory capture --stage mvp.design ...`
- `madspec memory checkpoint --stage mvp.design --summary ...`

Ключевые flags:

- `--design-overview`
- `--platform`
- `--zone`
- `--screen`
- `--screen-feature`
- `--flow`
- `--flow-step`
- `--flow-alternative`
- `--nav`
- `--platform-constraint`
- `--screen-data`
- `--next-action`

## Пошаговый runtime workflow

1. Агент читает `concept` и затем `design_status`.
2. По мере согласования экранов и потоков пишет `capture`.
3. Runtime обновляет `zones`, `screens`, `flows`, `navigation`, `platformConstraints`.
4. `design_completeness_errors()` проверяет platforms, screens, flows, navigation и coverage всех concept features.
5. `design_reference_errors()` проверяет links на неизвестные screen/zone и отсутствие prototype files.
6. После полного покрытия выполняется `checkpoint`.

## Canonical data model

Ключевые поля `mvp.design.json`:

- `designOverview`
- `platforms[]`
- `zones[]`
- `screens[]`
- `flows[]`
- `navigation[]`
- `platformConstraints[]`
- `nextActions[]`
- `checkpointSummary`
- `ratifiedAt`, `updatedAt`, `revision`

Обязательные условия checkpoint:

- есть `designOverview`
- есть хотя бы одна `platform`
- есть хотя бы один `screen`
- есть хотя бы один `flow`
- есть `navigation`
- все concept features покрыты через `screens[].covers`
- все prototype paths существуют

## Generated artifacts

- `ui-design.md`
- `project-context.md`
- prototype files в `.madspec/<BRANCH>/ui-prototype/` используются как reference inputs

## Диаграммы

```mermaid
flowchart TD
    A["madspec.mvp.design"] --> R["memory retrieve"]
    A --> C["memory capture"]
    A --> K["memory checkpoint"]
    C --> S["mvp.design.json"]
    S --> G["ui-design.md"]
    K --> V["design completeness + reference checks"]
    V --> G
```

```mermaid
sequenceDiagram
    participant A as Агент
    participant M as Memory API
    participant D as mvp.design.json
    participant P as ui-prototype/*
    participant G as ui-design.md

    A->>M: retrieve(stage=mvp.design)
    M-->>A: design_status
    loop Экраны и потоки
        A->>M: capture(screen/flow/nav/constraint)
        M->>D: upsert state
        M->>P: validate paths
    end
    A->>M: retrieve(--full-artifact)
    A->>M: checkpoint(summary)
    M->>G: regenerate
```

```mermaid
stateDiagram-v2
    [*] --> Empty
    Empty --> Draft
    Draft --> Covered: screens and flows exist
    Covered --> Ready: all concept features covered
    Ready --> Ratified: checkpoint accepted
    Ready --> Draft: reference/completeness error
```

```mermaid
flowchart LR
    C["mvp.concept.json"] --> F["concept feature list"]
    D["mvp.design.json"] --> S["screens.covers"]
    S --> V["coverage validator"]
    F --> V
    D --> U["ui-design.md"]
```

## Типовые ошибки / drift / ограничения

- экран ссылается на неизвестную `zone`
- flow step ссылается на неизвестный `screenId`
- `prototype` path отсутствует в репозитории
- часть concept features не покрыта design-state
- `ui-design.md` обновлен вручную и расходится с stage-state

## Соседние команды и handoff

- предыдущая команда: [`madspec.mvp.concept`](./madspec.mvp.concept.md)
- следующая команда: [`madspec.mvp.tech`](./madspec.mvp.tech.md)

## Что не является источником истины

- `.madspec/<BRANCH>/ui-design.md`
- HTML prototype как отдельный primary source без `mvp.design.json`
- устное описание экранов, не зафиксированное через `capture`
