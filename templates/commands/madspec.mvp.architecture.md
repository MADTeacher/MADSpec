---
description: MVP - Этап 3 - Проектирование архитектуры, структуры проекта, модели данных и API контрактов
handoffs:
  - label: Создать план реализации
    agent: madspec.mvp.plan
    prompt: Создай план реализации на основе архитектуры
---

## Пользовательский ввод

```text
$ARGUMENTS
```

## Обязательный skill `madspec-cli-operator`

- Перед началом работы обязательно найди и прочитай skill `madspec-cli-operator`.
- Дальше работай, опираясь на `madspec-cli-operator` как на базовый operational layer для workflow `madspec.*`, branch-aware артефактов `.madspec/` и команд MADSpec CLI.

Ты **ОБЯЗАН** учитывать пользовательский ввод перед продолжением (если он не пустой).

## Правила диалога (обязательно)

- **Задавай вопросы строго по одному**: в каждом твоем сообщении должен быть **ровно 1 вопрос**, который требует ответа.
- **Не выдавай список вопросов заранее**.
- Если нужен выбор, задай **один вопрос** и предложи **не больше 3–5 вариантов**.
- **Дожидайся ответа** и только затем задавай следующий вопрос.
- Если ответ неполный — задай **один уточняющий вопрос**.

## Structured Memory First (обязательно)

- Каноническое состояние этапа хранится в `.madspec/<BRANCH>/memory/stages/mvp.architecture.json`.
- `.madspec/<BRANCH>/architecture.md`, `.madspec/<BRANCH>/data-model.md`, `.madspec/<BRANCH>/contracts/openapi.yaml` и `project-context.md` являются generated artifacts/views и не редактируются вручную как primary source.
- Перед началом и после каждого подтвержденного блока используй `madspec memory retrieve --stage mvp.architecture --toon-output`, если этот контекст читает агент.
- В обычных ходах диалога опирайся на `architecture_status`: каких обязательных полей не хватает, сколько уже есть директорий, сущностей, endpoint'ов и есть ли reference errors.
- Полный `artifact_state.architecture` запрашивай только перед финальной валидацией, итоговым обзором и `checkpoint`, используя `madspec memory retrieve --stage mvp.architecture --toon-output --full-artifact`, если этот вывод читает агент.
- По мере согласования структуры проекта, модели данных, API-контрактов, интеграций и архитектурных принципов фиксируй их через `madspec memory capture --stage mvp.architecture ...`, а не откладывай в финальный checkpoint.
- Считай `screen.data` из design-state списком логических field id: если нужно описать поле, держи описание в UI/design narrative или в `--endpoint-field`, а не в `--screen-data`.
- Для architecture-specific canonical state используй stage-specific flags:
  - `--architecture-overview`
  - `--project-structure <strategy::rationale>`
  - `--directory <path::purpose>`
  - `--entity <name::description>`
  - `--entity-field <entity::field::type::required|optional::description>`
  - `--entity-relationship <entity::target::kind::description>`
  - `--entity-state <entity::state::description>`
  - `--endpoint <operation-id::METHOD::/path::summary>`
  - `--endpoint-screen <operation-id::screen-id>`
  - `--endpoint-field <operation-id::section::name::type::required|optional::description>` where `section` is `path`, `query`, `request`, `response`, or `response:<status>`
  - `--endpoint-error <operation-id::status::code::description>`
  - `--integration <name::kind::purpose::touchpoints>`
  - `--code-principle`
  - `--pattern <name::rationale>`
  - `--security-note`
  - `--performance-note`
  - `--next-action`
- Для этапа architecture **обязательно** заверши работу командой `madspec memory checkpoint --stage mvp.architecture ...`.
- Минимальный payload checkpoint:
  - `--summary` — итоговое архитектурное решение
  - `--fact/--decision/--contract` можно не дублировать, если они уже накоплены через `madspec memory capture --status validated`
  - `--evidence` — ссылки на `.madspec/<BRANCH>/architecture.md`, `.madspec/<BRANCH>/data-model.md`, `.madspec/<BRANCH>/contracts/openapi.yaml`
- `madspec memory checkpoint` сам обновляет structured memory, затем выполняет `madspec memory consolidate` и `madspec memory validate`.
- **ОБЯЗАТЕЛЬНО**: для вызовов `madspec memory capture` и `madspec memory checkpoint` используй `--from-file`: записывай аргументы во временный JSON-файл в `.madspec/.tmp/` и передавай путь через `--from-file <path>` (например, `madspec memory capture --from-file .madspec/.tmp/capture-args.json --json-output`). При ошибке исправляй тот же файл и повторяй вызов; после успешной команды CLI удалит файл автоматически. Ключи JSON соответствуют именам полей в `options` (например, `entities`, `entity_fields`, `endpoints`, `endpoint_fields`, `directories`), плюс `stage`, `branch`, `json_output`, `status` на верхнем уровне.

## Описание

На этом этапе создается детальная архитектура MVP на основе:

- концепции проекта;
- утвержденного дизайна UI;
- выбранного технологического стека.

Этот этап определяет, **как** будут организованы код, данные и контракты интеграции.

## Предварительные условия

- Должны существовать `.madspec/<BRANCH>/concept.md`, `.madspec/<BRANCH>/ui-design.md`, `.madspec/<BRANCH>/tech-stack.md`.
- Если их нет, предложи выполнить предыдущие этапы: `/madspec.mvp.concept`, `/madspec.mvp.design`, `/madspec.mvp.tech`.

## Цель этапа

Зафиксировать:

- структуру проекта;
- модель данных;
- API контракты;
- внешние интеграции;
- архитектурные принципы, паттерны, security/performance notes.

0. **Определение текущей ветки**:
   - Перед началом работы определи текущую ветку через `madspec git current-branch`.
   - Все пути к артефактам используй в формате `.madspec/<BRANCH>/...`.

1. **Загрузка контекста**:
   - Прочитай `.madspec/<BRANCH>/concept.md`, `.madspec/<BRANCH>/ui-design.md`, `.madspec/<BRANCH>/tech-stack.md`, `.madspec/<BRANCH>/project-context.md`.
   - Открой HTML-прототипы в `.madspec/<BRANCH>/ui-prototype/` и извлеки:
     - какие данные пользователь вводит;
     - какие данные система отображает;
     - какие действия выполняются на экранах;
     - какие переходы есть между экранами.

2. **Проектирование структуры проекта**:
   - Зафиксируй архитектурный overview через `--architecture-overview`.
   - Зафиксируй общую стратегию структуры проекта через `--project-structure`.
   - Добавляй каталоги через `--directory`, указывая назначение каждого.

3. **Проектирование модели данных**:
   - Определи сущности на основе UI и стека.
   - Для каждой сущности фиксируй:
     - саму сущность через `--entity`;
     - поля через `--entity-field`;
     - связи через `--entity-relationship`;
     - состояния через `--entity-state`, если применимо.

4. **Проектирование API контрактов**:
   - Для каждого пользовательского действия из прототипов фиксируй endpoint через `--endpoint`.
   - Для связи endpoint ↔ экран используй `--endpoint-screen`.
   - Для request/path/query/response полей используй `--endpoint-field`.
   - `response` можно использовать как shorthand для `response:200`, а `response:<status>` оставляй для явных кодов ответа.
   - Для ошибок используй `--endpoint-error`.
   - **КРИТИЧНО**: не создавай endpoint'ы, которых нет в дизайне и прототипах.

5. **Внешние интеграции и правила кода**:
   - Интеграции фиксируй через `--integration`.
   - Кодовые принципы фиксируй через `--code-principle`.
   - Паттерны фиксируй через `--pattern`.
   - Security/performance observations фиксируй через `--security-note` и `--performance-note`.

6. **Валидация архитектуры**:

   Перед финальным checkpoint проверь:

   - [ ] Есть `architectureOverview`
   - [ ] Есть `projectStructure.strategy` и `projectStructure.rationale`
   - [ ] Есть хотя бы одна directory
   - [ ] Есть хотя бы одна entity и хотя бы одно entity field
   - [ ] Есть хотя бы один endpoint
   - [ ] Каждый экран из design связан минимум с одним endpoint
   - [ ] Все `screenData.input` покрыты `path/query/request` fields linked endpoint'ов
   - [ ] Все `screenData.displayed` покрыты `response:*` fields linked endpoint'ов
   - [ ] Есть хотя бы один `codePrinciple` или `pattern`

   Если валидация не проходит:
   - укажи, чего не хватает;
   - задай следующий уточняющий вопрос;
   - не переходи дальше до прохождения проверки.

7. **Checkpoint в structured memory**:
   - После успешной валидации выполни `madspec memory checkpoint --stage mvp.architecture`.
   - Если stage memory уже накоплена инкрементально, достаточно:
     - `--summary`
     - `--evidence .madspec/<BRANCH>/architecture.md`
     - `--evidence .madspec/<BRANCH>/data-model.md`
     - `--evidence .madspec/<BRANCH>/contracts/openapi.yaml`
   - При наличии незакрытых вопросов добавь `--question`, а для следующих действий — `--pending-action`.

8. **Сохранение артефактов**:
   - Не записывай `.madspec/<BRANCH>/architecture.md`, `.madspec/<BRANCH>/data-model.md` и `.madspec/<BRANCH>/contracts/openapi.yaml` вручную: они должны быть пересобраны из structured memory.
   - Не редактируй `.madspec/<BRANCH>/memory/stages/mvp.architecture.json` вручную, даже если validation кажется ложным: исправляй canonical state только через memory CLI.
   - Убедись, что `project-context.md` был пересобран командой `madspec memory checkpoint`.

## Правила

- **СЛЕДУЙ** UI-дизайну и прототипам.
- **НАЧИНАЙ ПРОСТО**: не добавляй лишние сущности и endpoint'ы без наблюдаемой причины.
- **ДОКУМЕНТИРУЙ** решения по мере появления через `memory capture`, а не в одном финальном сжатии.
- Используй выбранные на этапе tech подходы к организации кода.

## Выходные артефакты

- `.madspec/<BRANCH>/memory/stages/mvp.architecture.json` — основной файл данных этапа architecture
- `.madspec/<BRANCH>/architecture.md` — generated artifact архитектуры
- `.madspec/<BRANCH>/data-model.md` — generated artifact модели данных
- `.madspec/<BRANCH>/contracts/openapi.yaml` — generated OpenAPI контракт
- `.madspec/<BRANCH>/memory/` — canonical memory с checkpoint этапа architecture
- `.madspec/<BRANCH>/project-context.md` — regenerated view контекста проекта

## Следующий этап

После утверждения и checkpoint переходи к `/madspec.mvp.plan`.
