# Процесс MVP

Раздел описывает полный процесс разработки нового проекта с нуля. В режиме MVP каждая стадия добавляет новый слой канонического состояния, а производные артефакты только отражают уже ратифицированные данные.

Все MVP-команды должны начинать с чтения и применения навыка `madspec-cli-operator`. Для `mvp.design` дополнительно обязателен навык `frontend-design`.

## Рекомендуемый порядок

1. [`mvp.concept`](madspec.mvp.concept.md)
2. [`mvp.design`](madspec.mvp.design.md)
3. [`mvp.tech`](madspec.mvp.tech.md)
4. [`mvp.architecture`](madspec.mvp.architecture.md)
5. [`mvp.plan`](madspec.mvp.plan.md)
6. [`mvp.implement`](madspec.mvp.implement.md)

## Общие состояния стадий и артефакты

- `mvp.concept` — `.madspec/<BRANCH>/memory/stages/mvp.concept.json`, производный `concept.md`
- `mvp.design` — `.madspec/<BRANCH>/memory/stages/mvp.design.json`, производные `ui-design.md`, `ui-prototype/*`
- `mvp.tech` — `.madspec/<BRANCH>/memory/stages/mvp.tech.json`, производный `tech-stack.md`
- `mvp.architecture` — `.madspec/<BRANCH>/memory/stages/mvp.architecture.json`, производные `architecture.md`, `data-model.md`, `contracts/openapi.yaml`
- `mvp.plan` — `.madspec/<BRANCH>/memory/stages/mvp.plan.json` + `.madspec/<BRANCH>/memory/progress.json`, производные `implementation-plan.md`, `planning-context-cache.md`, `steps/*/planning-context.md`
- `mvp.implement` — текущее состояние выполнения в `progress.json` и `working/active-session.json`, производные `implementation-context.md`, `project-context.md`

## Ключевые зависимости

- `design` зависит от покрываемых функций из `concept`
- `architecture` зависит от экранов и покрытия данных из `design`
- `plan` зависит от состояния архитектуры и синхронизации `progress`
- `implement` зависит от каталога шагов и графа зависимостей из `plan`
