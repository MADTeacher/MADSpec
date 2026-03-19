---
description: Feature - Пошаговая реализация через implementation memory workflow
---

## Пользовательский ввод

```text
$ARGUMENTS
```

## Обязательный skill `madspec-cli-operator`

- Перед началом работы обязательно найди и прочитай skill `madspec-cli-operator`.
- Дальше работай, опираясь на `madspec-cli-operator` как на базовый operational layer для workflow `madspec.*`, branch-aware артефактов `.madspec/` и команд MADSpec CLI.

## Structured Memory First

- Канонический runtime-state этапа implement хранится в `.madspec/<BRANCH>/memory/progress.json` и `.madspec/<BRANCH>/memory/working/active-session.json`.
- `decision-log.jsonl`, `events.jsonl` и `semantic/*.jsonl` являются каноническими record streams реализации.
- `implementation-context.md` и `project-context.md` являются generated views.
- В начале каждой сессии сначала используй `madspec memory retrieve --stage feature.implement --json-output`.
- Из ответа `madspec memory retrieve` **обязательно** прочитай `policy_context.required`, `policy_context.advisory` и policy validations для текущего шага.
- Для запуска шага используй `madspec memory start-step --stage feature.implement`.
- Для TDD checkpoint используй `madspec memory checkpoint-step --stage feature.implement`.
- Для завершения шага используй `madspec memory complete-step --stage feature.implement`.
- **ОБЯЗАТЕЛЬНО**: для вызовов `madspec memory start-step`, `madspec memory checkpoint-step` и `madspec memory complete-step` используй `--from-file`: записывай аргументы в JSON-файл и передавай путь через `--from-file <path>` (например, `madspec memory complete-step --from-file .madspec/.tmp/complete-args.json --json-output`). Ключи JSON соответствуют именам полей в `options` (например, `step_id`, `summary`, `tdd_phase`, `facts`, `decisions`), плюс `stage`, `branch`, `json_output` на верхнем уровне.

## Предварительные условия

- Feature init и feature plan завершены.
- Есть `.madspec/<BRANCH>/steps/<step-id>/` с `description.md`, `tasks.md`, `tests.md`, `validation.md`.
- Если шаги ещё не спланированы, направь пользователя на `/madspec.feature.plan`.

## Порядок работы

1. Определи ветку через `madspec git current-branch`.
2. Запроси `madspec memory retrieve --stage feature.implement --json-output`.
3. Используй ответ как основной workflow state:
   - `workflow.currentImplementStep`
   - `workflow.nextExecutableStep`
   - `step.metadata`
   - `step.status`
   - `policy_context.required`
   - `policy_context.advisory`
4. Прочитай generated references:
   - `.madspec/<BRANCH>/project-analysis.md`
   - `.madspec/<BRANCH>/feature-context.md`
   - `.madspec/<BRANCH>/implementation-plan.md`
5. Прочитай source artifacts текущего шага:
   - `.madspec/<BRANCH>/steps/<step-id>/description.md`
   - `.madspec/<BRANCH>/steps/<step-id>/tasks.md`
   - `.madspec/<BRANCH>/steps/<step-id>/tests.md`
   - `.madspec/<BRANCH>/steps/<step-id>/validation.md`
6. Запусти шаг:
   - если пользователь указал шаг, `madspec memory start-step --stage feature.implement --step-id <step-id>`
   - иначе `madspec memory start-step --stage feature.implement --json-output`
7. Выполни шаг:
   - для `code` шага следуй циклу `red -> green -> refactor`
   - для `non-code` шага используй только путь waiver/not-applicable
   - не нарушай active required policies; если шаг конфликтует с policy_context, сначала скорректируй step intent или policy set
8. Сохраняй промежуточное состояние через:
   - `madspec memory checkpoint-step --stage feature.implement --tdd-phase red ...`
   - `madspec memory checkpoint-step --stage feature.implement --tdd-phase green ...`
   - `madspec memory checkpoint-step --stage feature.implement --tdd-phase refactor ...`
9. После валидации заверши шаг:
   - `madspec memory complete-step --stage feature.implement --step-id <step-id> --summary ...`
   - при необходимости добавь `--fact`, `--decision`, `--contract`
10. Повтори `madspec memory retrieve --stage feature.implement --json-output` и проверь следующий executable step.
    - При сомнении дополнительно выполни `madspec policy validate --stage feature.implement --step-id <step-id> --json-output`.
11. После успешного `complete-step` создай git commit через `madspec git commit --message "..."`

## Важные запреты

- Не редактируй `progress.json` вручную.
- Не изменяй `currentImplementStep` вручную.
- Не создавай и не обновляй `implementation-context.md` или `project-context.md` вручную как source of truth.
- Не считай `project-analysis.md` primary source; это generated reference поверх `feature.init.json`.

## Что считается результатом

- Шаг закрыт через `memory complete-step`.
- TDD state и evidence сохранены в structured memory.
- Generated views пересобраны автоматически.
- Прогресс feature workflow можно безопасно продолжить в новом чате.
