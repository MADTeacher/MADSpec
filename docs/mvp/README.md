# MVP Workflow

Раздел описывает полный workflow разработки нового проекта с нуля. В MVP-режиме каждая стадия добавляет новый слой canonical state, а generated artifacts только отражают уже ратифицированные данные.

Все MVP-команды должны начинать с чтения и применения skill `madspec-cli-operator`. Для `mvp.design` дополнительно обязателен skill `frontend-design`.

## Рекомендуемый порядок

1. [`mvp.concept`](madspec.mvp.concept.md)
2. [`mvp.design`](madspec.mvp.design.md)
3. [`mvp.tech`](madspec.mvp.tech.md)
4. [`mvp.architecture`](madspec.mvp.architecture.md)
5. [`mvp.plan`](madspec.mvp.plan.md)
6. [`mvp.implement`](madspec.mvp.implement.md)

## Общие stage-state и артефакты

- `mvp.concept` — `.madspec/<BRANCH>/memory/stages/mvp.concept.json`, generated `concept.md`
- `mvp.design` — `.madspec/<BRANCH>/memory/stages/mvp.design.json`, generated `ui-design.md`, `ui-prototype/*`
- `mvp.tech` — `.madspec/<BRANCH>/memory/stages/mvp.tech.json`, generated `tech-stack.md`
- `mvp.architecture` — `.madspec/<BRANCH>/memory/stages/mvp.architecture.json`, generated `architecture.md`, `data-model.md`, `contracts/openapi.yaml`
- `mvp.plan` — `.madspec/<BRANCH>/memory/stages/mvp.plan.json` + `.madspec/<BRANCH>/memory/progress.json`, generated `implementation-plan.md`, `planning-context-cache.md`, `steps/*/planning-context.md`
- `mvp.implement` — runtime-state в `progress.json` и `working/active-session.json`, generated `implementation-context.md`, `project-context.md`

## Ключевые зависимости

- `design` зависит от покрываемых функций из `concept`
- `architecture` зависит от экранов и data coverage из `design`
- `plan` зависит от architecture-state и progress-sync
- `implement` зависит от step catalog и dependency graph из `plan`
