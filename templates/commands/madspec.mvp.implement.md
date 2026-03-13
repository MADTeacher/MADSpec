---
description: MVP - Этап 5 - Пошаговая реализация проекта с memory-first workflow, TDD и валидацией
---

## Пользовательский ввод

```text
$ARGUMENTS
```

Ты **ОБЯЗАН** учитывать пользовательский ввод перед продолжением (если он не пустой).

## Правила диалога (обязательно)

- **Задавай вопросы строго по одному**: в каждом твоем сообщении должен быть **ровно 1 вопрос**, который требует ответа.
- **Не выдавай список вопросов заранее** (никаких длинных анкет/чек-листов вопросов за раз).
- Если нужен выбор, задай **один вопрос** и предложи **не больше 3–5 вариантов** (или попроси свободный ответ).
- **Дожидайся ответа** и только затем задавай следующий вопрос.
- Если ответ неполный — задай **один уточняющий вопрос**, а не несколько сразу.

## Structured Memory First (обязательно)

- `progress.json` и `active-session.json` — канонический runtime-state этапа implement.
- `decision-log.jsonl`, `events.jsonl` и `semantic/*.jsonl` — канонические записи о ходе реализации, знаниях и результатах.
- `implementation-context.md` и `project-context.md` являются generated views поверх structured memory и **не редактируются вручную как primary source**.
- Перед началом работы сначала получай контекст через `madspec memory retrieve --stage mvp.implement --json-output`.
- Для старта шага используй `madspec memory start-step --stage mvp.implement`, а не ручную установку `currentImplementStep`.
- Для промежуточных TDD checkpoint используй `madspec memory checkpoint-step --stage mvp.implement`.
- Для завершения шага, продвижения workflow и записи step-level knowledge используй `madspec memory complete-step --stage mvp.implement`.
- Не редактируй `memory/progress.json`, `implementation-context.md` или `project-context.md` вручную, если то же изменение должно быть выражено через memory-команды и step records.

## Описание

Этот этап **MADSpec (MADSpec Framework)** выполняет пошаговую реализацию **MVP (Minimum Viable Product)** проекта согласно плану.

**Режим MVP**: эта команда предназначена для разработки нового проекта с нуля. Все артефакты сохраняются в `.madspec/<BRANCH>/`, где `<BRANCH>` - имя текущей ветки разработки.

Каждый шаг:
- выполняется последовательно с учетом зависимостей;
- валидируется через автоматические и ручные тесты;
- фиксируется в structured memory;
- может быть возобновлен с любого шага.

## Предварительные условия

- Должен существовать `.madspec/<BRANCH>/implementation-plan.md`.
- Должна существовать директория `.madspec/<BRANCH>/steps/` с описаниями шагов.
- Должен существовать `.madspec/<BRANCH>/memory/progress.json`.
- Если файлы отсутствуют, предложи выполнить `/madspec.mvp.plan`.

## Цель этапа

Реализовать проект пошагово, обеспечивая:
- выполнение каждого шага согласно плану;
- обязательную валидацию через тесты и checklist шага;
- детерминированное обновление workflow state через memory-команды;
- возможность безопасно продолжать работу в новом чате без потери контекста.

0. **Определение текущей ветки**:
   - Перед началом работы определи текущую ветку через `madspec git current-branch` из корня проекта.
   - Все пути к артефактам используй в формате `.madspec/<BRANCH>/...`.
   - Если ни команда, ни файл недоступны, используй значение по умолчанию `main`.

1. **Загрузка контекста**:
   - **Сначала выполни** `madspec memory retrieve --stage mvp.implement --json-output`.
   - Используй JSON-ответ как основной источник workflow state: `workflow.currentImplementStep`, `workflow.nextExecutableStep`, `step.status`, `step.metadata`, `step.dependencies`, `semantic.*`, `stage_memory.*`.
   - Прочитай `.madspec/<BRANCH>/implementation-plan.md` как generated plan overview.
   - Прочитай предыдущие stage artifacts из `.madspec/<BRANCH>/` для product и architecture context: `concept.md`, `ui-design.md`, `tech-stack.md`, `architecture.md`, `data-model.md`, `contracts/openapi.yaml`.
   - Прочитай source artifacts текущего шага:
     - `.madspec/<BRANCH>/steps/<step-id>/description.md`
     - `.madspec/<BRANCH>/steps/<step-id>/tasks.md`
     - `.madspec/<BRANCH>/steps/<step-id>/tests.md`
     - `.madspec/<BRANCH>/steps/<step-id>/validation.md`
   - Если есть предыдущие шаги, используй `planning-context.md` и `implementation-context.md` только как generated context для ориентации, а не как первичный источник истины.
   - Если шаг связан с UI, используй HTML storyboard-прототипы из `.madspec/<BRANCH>/ui-prototype/` как утвержденный UI contract при реализации.

2. **Определение и запуск текущего шага**:
   - Если пользователь явно указал конкретный шаг в `$ARGUMENTS`, проверь его зависимости и запусти `madspec memory start-step --stage mvp.implement --step-id <step-id>`.
   - Иначе запусти `madspec memory start-step --stage mvp.implement --json-output` и используй выбранный шаг из ответа.
   - После `start-step` считай structured memory источником текущего шага, а не локальные догадки по имени директории.
   - Если `start-step` возвращает ошибку о зависимостях или отсутствии executable step, остановись и объясни причину пользователю.

3. **Проверка шага перед реализацией**:
   - Проверь, что шаг присутствует в `plannedSteps` и его зависимости завершены.
   - Определи `step kind` и `tddPolicy` через `step.metadata`:
     - `code + required` -> шаг выполняется строго по циклу `red -> green -> refactor`.
     - `non-code + waived|not-applicable` -> кодовые TDD gates не применяются, но `waiverReason` должен быть сохранен в metadata шага.
   - Если step source artifacts противоречат structured memory, доверяй memory как workflow state, а source artifacts используй как задающий intent и acceptance criteria.

4. **Выполнение шага**:
   - Следуй `description.md`, `tasks.md`, `tests.md` и `validation.md`.
   - Создавай или изменяй код и другие source files согласно задачам шага.
   - Отмечай выполненные задачи в `tasks.md`, если файл доступен для редактирования.
   - Для UI-шагов проверяй соответствие `.madspec/<BRANCH>/ui-prototype/` и `ui-design.md`.
   - Если реализация должна отойти от утвержденного storyboard, сначала обнови `mvp.design` или получи явное одобрение drift от пользователя.

5. **TDD и checkpoint discipline**:

   **Для `code` шага порядок обязателен:**
   1. Подготовь focused test из секции `Red`.
   2. Запусти failing test и сразу сохрани checkpoint:
      `madspec memory checkpoint-step --stage mvp.implement --step-id <step-id> --tdd-phase red --red-evidence "<command>"`
   3. Сделай минимальную реализацию только для перехода в green.
   4. Повтори прогон и сохрани checkpoint:
      `madspec memory checkpoint-step --stage mvp.implement --step-id <step-id> --tdd-phase green --green-evidence "<command>"`
   5. Выполни refactor без изменения поведения и сохрани итог:
      `madspec memory checkpoint-step --stage mvp.implement --step-id <step-id> --tdd-phase refactor --refactor-note "<note>"`
   6. Повтори focused test и `Relevant Suite`.
   7. Только после этого завершай шаг через `madspec memory complete-step --stage mvp.implement ...`.

   **Для `non-code` шага:**
   - Не редактируй `progress.json` вручную.
   - Убедись, что `step.metadata.tddPolicy` и `step.metadata.waiverReason` согласованы с типом шага.
   - Завершай шаг только через `madspec memory complete-step`; `tddPhase=waived` будет валидирован на основе metadata.

6. **⚠️ КРИТИЧЕСКИ ВАЖНО: Использование официальных команд создания проектов**:

   **ЗАПРЕЩЕНО** создавать проекты вручную, добавляя файлы и директории самостоятельно. **ОБЯЗАТЕЛЬНО** используй официальные команды создания проектов для соответствующих технологий.

   - **Flutter**: `flutter create <project_name>`
   - **React**: `npx create-react-app <project_name>` или `npm create vite@latest <project_name>`
   - **Next.js**: `npx create-next-app@latest <project_name>`
   - **Vue.js**: `npm create vue@latest <project_name>` или `vue create <project_name>`
   - **Angular**: `ng new <project_name>`
   - **Go**: `go mod init <module_name>`
   - **Python (uv)**: `uv init`, `uv init --lib`, `uv init --package`, `uv add`, `uv sync`, `uv lock`, `uv run`
   - **Python (традиционные инструменты)**: `python -m venv`, `pip install`, framework-specific init commands
   - **Node.js**: `npm init` или `npm init -y`
   - **Rust**: `cargo new <project_name>`
   - **Java**: соответствующие команды Maven/Gradle
   - **C#/.NET**: `dotnet new <template>`
   - **Ruby**: `rails new <project_name>`
   - **PHP**: `composer create-project`

   Правила:
   - Сначала проверь, установлен ли нужный инструмент.
   - Если инструмент не установлен, сообщи пользователю о необходимости его установки.
   - Выполняй команды создания проекта из корневой директории проекта или директории, указанной в `tasks.md`.
   - После выполнения команды проверь, что все нужные файлы и директории действительно были созданы.
   - **НЕ СОЗДАВАЙ** вручную `package.json`, `go.mod`, `pubspec.yaml`, `Cargo.toml`, `pyproject.toml`, `.python-version`, `uv.lock` и аналогичные bootstrap files.
   - **НЕ СОЗДАВАЙ** вручную структуру директорий проекта, если для стека есть официальный initializer.

7. **Валидация шага**:

   Перед завершением шага выполни полный checklist:

   - [ ] Все задачи из `tasks.md` выполнены.
   - [ ] Файлы, указанные в шаге, созданы или изменены.
   - [ ] Автоматические тесты из `tests.md` существуют и проходят, если они требуются для шага.
   - [ ] Ручные тесты/чек-листы из `tests.md` выполнены, если они требуются для шага.
   - [ ] Критерии завершения из `validation.md` выполнены.
   - [ ] Реализация соответствует `description.md`.
   - [ ] Код соответствует `architecture.md`, `data-model.md` и контрактам проекта.
   - [ ] UI-реализация соответствует утвержденному storyboard-прототипу, если шаг касается интерфейса.

   **Отдельно проверь structured memory:**
   - Выполни `madspec memory retrieve --stage mvp.implement --step-id <step-id> --json-output`.
   - Для `code + required` после `complete-step` должны быть выполнены условия:
     - `step.status.tddPhase = completed`
     - `step.status.redEvidence` заполнен
     - `step.status.greenEvidence` заполнен
     - `step.status.refactorNote` заполнен или содержит `No refactor needed`
   - Для `non-code` шага:
     - `step.status.tddPhase = waived`
     - при `tddPolicy=waived` заполнен `step.metadata.waiverReason`

   Если валидация не пройдена:
   - укажи конкретные невыполненные пункты;
   - предложи конкретные исправления;
   - **не переходи** к завершению шага и **не создавай коммит** до успешной валидации.

8. **Завершение шага через structured memory**:

   После успешной валидации **не редактируй** `.madspec/<BRANCH>/memory/progress.json` вручную.

   Вместо этого выполни:

   ```bash
   madspec memory complete-step \
     --stage mvp.implement \
     --step-id <step-id> \
     --summary "<что завершено>" \
     --red-evidence "<focused red command>" \
     --green-evidence "<focused green command>" \
     --refactor-note "<что было отрефакторено>"
   ```

   Если в ходе шага появились устойчивые знания, сразу сохрани их в memory:

   ```bash
   madspec memory complete-step \
     --stage mvp.implement \
     --step-id <step-id> \
     --summary "<что завершено>" \
     --fact "<validated fact>" \
     --decision "<validated decision>" \
     --contract "<validated constraint>"
   ```

   Команда сама:
   - обновит `completedSteps`, `stepStatus` и `currentImplementStep`;
   - переведет `tddPhase` в `completed` или `waived`;
   - запишет step-level records в episodic и semantic memory;
   - пересоберет generated views и завершится ошибкой, если state невалиден.

9. **Проверка результата после completion**:
   - Повтори `madspec memory retrieve --stage mvp.implement --step-id <step-id> --json-output` и проверь итоговый статус шага.
   - Используй generated `implementation-context.md` и `project-context.md` как read-only подтверждение того, что consolidated views обновились.
   - Если generated views расходятся с фактами, исправляй memory/records и повторяй `madspec memory consolidate` + `madspec memory validate`, а не редактируй markdown вручную.

10. **Коммит изменений в GIT**:
   - После успешной валидации и успешного `complete-step` создай коммит в GIT:
     `madspec git commit --message "feat(step-NN): реализован шаг [название шага]"`
   - Коммит создается только после успешной валидации шага.
   - Не обещай ручное обновление generated views после коммита: commit metadata не является отдельным canonical artifact для этого этапа.
   - Все изменения шага должны быть включены в коммит: код, тесты, source artifacts шага и обновленный structured memory state.

11. **Отчет о прогрессе**:
   - Сообщи:
     - какой шаг завершен;
     - какой следующий executable step выбран memory workflow;
     - каков общий прогресс (`completedSteps` из `plannedSteps`).
   - Если все шаги завершены, предложи переход к финальной проверке проекта.

## Правила выполнения

- **СЛЕДУЙ** плану и не пропускай шаги без явного основания.
- **ВАЛИДИРУЙ** каждый шаг перед `complete-step` и коммитом.
- **НЕ ОБНОВЛЯЙ** `currentImplementStep` и `progress.json` вручную.
- **ИСПОЛЬЗУЙ** `madspec memory retrieve/start-step/checkpoint-step/complete-step` как обязательный API этапа.
- **КОММИТЬ** изменения только после успешной валидации и `complete-step`.
- **НЕ РЕДАКТИРУЙ** `implementation-context.md` и `project-context.md` вручную как source of truth.
- **ДОКУМЕНТИРУЙ** устойчивые факты, решения и контракты через `memory complete-step`.

## Обработка ошибок

- Если шаг не может быть выполнен, остановись и сообщи о проблеме.
- Предложи варианты решения.
- Если workflow state или generated views расходятся, сначала исправляй canonical memory и step records.

## Выходные артефакты

- Реализованный код проекта.
- Обновленный `.madspec/<BRANCH>/memory/progress.json` через memory workflow.
- Обновленные `decision-log`, `events` и semantic records по шагу.
- `.madspec/<BRANCH>/steps/step-[NN]-[name]/implementation-context.md` — generated view контекста реализации.
- `.madspec/<BRANCH>/project-context.md` — regenerated navigation/context view.
- История коммитов GIT с коммитом для каждого завершенного шага.

## Завершение

После завершения всех шагов предложи:
- финальную проверку всех функций;
- демонстрацию проекта;
- review или security-проверку, если это уместно.
