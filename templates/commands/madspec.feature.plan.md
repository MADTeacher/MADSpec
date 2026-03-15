---
description: Feature - Инкрементальное планирование реализации через memory-first workflow
handoffs:
  - label: Начать реализацию
    agent: madspec.feature.implement
    prompt: Начни реализацию с шага [N]
---

## Пользовательский ввод

```text
$ARGUMENTS
```

## Обязательный skill `madspec-cli-operator`

- Перед началом работы обязательно найди и прочитай skill `madspec-cli-operator`.
- Дальше работай, опираясь на `madspec-cli-operator` как на базовый operational layer для workflow `madspec.*`, branch-aware артефактов `.madspec/` и команд MADSpec CLI.

## Structured Memory First

- Каноническое состояние этапа хранится в `.madspec/<BRANCH>/memory/stages/feature.plan.json`.
- Runtime state шагов хранится в `.madspec/<BRANCH>/memory/progress.json`.
- `implementation-plan.md`, `planning-context-cache.md`, `steps/*/planning-context.md` и `project-context.md` являются generated views.
- В обычных ходах сначала используй `madspec memory retrieve --stage feature.plan --json-output`.
- Strategy-level изменения сохраняй через `madspec memory capture --stage feature.plan --plan-overview ... --planning-principle ... --next-action ...`.
- Перед регистрацией шага обязательно проверь его через `madspec memory next-step --stage feature.plan --candidate-step ...`.
- Новый planned step записывай только через `madspec memory register-step --stage feature.plan ...`.
- Финальную ратификацию этапа делай через `madspec memory checkpoint --stage feature.plan --summary ...`.
- **ОБЯЗАТЕЛЬНО**: для вызовов `madspec memory capture`, `madspec memory checkpoint` и `madspec memory register-step` используй `--from-file`: записывай аргументы в JSON-файл и передавай путь через `--from-file <path>` (например, `madspec memory register-step --from-file .madspec/.tmp/register-args.json --json-output`). Ключи JSON соответствуют именам полей команды, плюс `stage`, `branch`, `json_output` на верхнем уровне.

## Цель этапа

Инкрементально добавлять по одному новому шагу реализации, сохраняя:

- step catalog в `feature.plan.json`;
- покрытие функций по explicit `ID`;
- зависимости шагов;
- TDD policy и metadata шага;
- generated implementation plan без ручного редактирования markdown.

## Предварительные условия

- Существует `.madspec/<BRANCH>/memory/stages/feature.init.json`.
- `madspec memory retrieve --stage feature.init --json-output` показывает достаточный `feature_init_status`.
- Если init ещё не завершён, направь пользователя на `/madspec.feature.init`.

## Порядок работы

1. Определи текущую ветку через `madspec git current-branch`.
2. Запроси `madspec memory retrieve --stage feature.plan --json-output`.
3. Прочитай generated references:
   - `.madspec/<BRANCH>/project-analysis.md`
   - `.madspec/<BRANCH>/feature-context.md`
   - `.madspec/<BRANCH>/tech-stack.md`
   - `.madspec/<BRANCH>/architecture.md`
4. Если стратегия ещё не зафиксирована, добавь её через `madspec memory capture --stage feature.plan --plan-overview ... --planning-principle ... --next-action ...`.
5. Выбери следующий шаг:
   - покрывает хотя бы одну функцию из `feature.init` catalog;
   - использует explicit function IDs в `--covers`;
   - имеет явный `step-kind`;
   - имеет корректные `depends-on`.
6. Создай source artifacts шага в `.madspec/<BRANCH>/steps/<step-id>/`:
   - `description.md`
   - `tasks.md`
   - `tests.md`
   - `validation.md`
7. Проверь кандидата:
   - `madspec memory next-step --stage feature.plan --candidate-step <step-id> --depends-on ...`
8. Зарегистрируй шаг:
   - `madspec memory register-step --stage feature.plan --step-id <step-id> --step-kind <code|non-code> --title ... --summary ... --covers <Fxx> ... --depends-on ...`
   - для `non-code` шага обязательно передай `--tdd-policy waived|not-applicable` и `--waiver-reason`, если нужен waiver
9. Повтори `madspec memory retrieve --stage feature.plan --json-output` и проверь `feature_plan_status`.
10. Когда стратегия и catalog шагов готовы, зафиксируй этап через `madspec memory checkpoint --stage feature.plan --summary "<validated summary>"`.

## Важные правила

- Не редактируй `currentImplementStep` вручную.
- Не редактируй `implementation-plan.md`, `planning-context-cache.md`, `planning-context.md` и `project-context.md` вручную как primary source.
- Для `code` шага TDD policy всегда `required`.
- Для feature coverage используй IDs из `feature.init.json`, а не свободные текстовые labels.

## Что считается результатом

- `.madspec/<BRANCH>/memory/stages/feature.plan.json` содержит strategy и step catalog.
- `progress.json` синхронизирован с `feature.plan.json`.
- `implementation-plan.md` и `planning-context-cache.md` пересобраны автоматически.
- Следующий executable step может быть запущен через `/madspec.feature.implement`.
