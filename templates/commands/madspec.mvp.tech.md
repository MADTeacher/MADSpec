---
description: MVP - Этап 2 - Выбор технологического стека через structured memory
handoffs:
  - label: Создать архитектуру
    agent: madspec.mvp.architecture
    prompt: Создай архитектуру проекта на основе утвержденного технологического стека
---

## Пользовательский ввод

```text
$ARGUMENTS
```

## Обязательный skill `madspec-cli-operator`

- Перед началом работы обязательно найди и прочитай skill `madspec-cli-operator`.
- Дальше работай, опираясь на `madspec-cli-operator` как на базовый operational layer для workflow `madspec.*`, branch-aware артефактов `.madspec/` и команд MADSpec CLI.

Ты **ОБЯЗАН** учитывать пользовательский ввод перед продолжением, если он не пустой.

## Правила диалога (обязательно)

- **Задавай вопросы строго по одному**: в каждом твоем сообщении должен быть **ровно 1 вопрос**, который требует ответа.
- **Не выдавай список вопросов заранее**.
- Если нужен выбор, задай **один вопрос** и предложи **не больше 3–5 вариантов**.
- **Дожидайся ответа** и только затем задавай следующий вопрос.
- Если ответ неполный, задай **один уточняющий вопрос**, а не несколько сразу.

## Structured Memory First (обязательно)

- Каноническое состояние этапа хранится в `.madspec/<BRANCH>/memory/stages/mvp.tech.json`.
- `.madspec/<BRANCH>/tech-stack.md` является **generated artifact**, а не primary source.
- Нельзя редактировать `tech-stack.md` вручную и нельзя использовать его как источник истины.
- Перед началом каждой сессии выполни `madspec memory retrieve --stage mvp.tech --toon-output`, если этот вывод читает агент.
- В обычной работе опирайся на `tech_status`, а не на полный artifact state.
- Полный `artifact_state.tech` запрашивай только перед итоговой валидацией и checkpoint через `madspec memory retrieve --stage mvp.tech --toon-output --full-artifact`, если этот вывод читает агент.
- После каждого подтвержденного tech trade-off или ограничения сразу фиксируй его через `madspec memory capture --stage mvp.tech ...`.
- Используй tech-specific flags:
  - `--project-type`
  - `--stack-overview`
  - `--requirement`
  - `--preference`
  - `--tech-constraint`
  - `--stack-component <slot>::<name>::<version>::<rationale>`
  - `--library <scope>::<name>::<version>::<purpose>`
  - `--code-organization <repo-strategy>::<source-layout>::<modularity>::<rationale>`
  - `--alternative <slot>::<option>::<reason-rejected>`
  - `--next-action`
- Для этапа tech **обязательно** заверши работу командой `madspec memory checkpoint --stage mvp.tech ...`.
- Минимальный payload checkpoint:
  - `--summary` — краткий итог выбранного стека
  - `--evidence .madspec/<BRANCH>/tech-stack.md`
  - `--fact/--decision/--contract` можно не дублировать, если они уже накоплены через `madspec memory capture --status validated`
- `madspec memory checkpoint` сам пересобирает generated views и запускает validation.
- **ОБЯЗАТЕЛЬНО**: для вызовов `madspec memory capture` и `madspec memory checkpoint` используй `--from-file`: записывай аргументы во временный JSON-файл в `.madspec/.tmp/` и передавай путь через `--from-file <path>` (например, `madspec memory capture --from-file .madspec/.tmp/capture-args.json --json-output`). При ошибке исправляй тот же файл и повторяй вызов; после успешной команды CLI удалит файл автоматически. Ключи JSON соответствуют именам полей в `options` (например, `stack_components`, `libraries`, `requirements`, `tech_constraints`), плюс `stage`, `branch`, `json_output`, `status` на верхнем уровне.

## Предварительные условия

- Должны существовать `.madspec/<BRANCH>/concept.md` и `.madspec/<BRANCH>/ui-design.md`.
- Если артефакты отсутствуют, предложи сначала выполнить `/madspec.mvp.concept` и `/madspec.mvp.design`.

## Цель этапа

Выбрать технологический стек, который:
- покрывает концепцию и утвержденный UI/UX
- имеет явное обоснование по каждому ключевому компоненту
- учитывает ограничения, предпочтения и отклоненные альтернативы
- подготавливает почву для `mvp.architecture`

## Рабочий порядок

0. **Определи ветку**:
   - Выполни `madspec git current-branch`.
   - Все пути формируй как `.madspec/<BRANCH>/...`.

1. **Восстанови контекст**:
   - Прочитай `.madspec/<BRANCH>/concept.md`.
   - Прочитай `.madspec/<BRANCH>/ui-design.md`.
   - Выполни `madspec memory retrieve --stage mvp.tech --toon-output`, если этот вывод читает агент.
   - Посмотри в `tech_status`, какие обязательные поля уже заполнены, а каких не хватает.

2. **Собери требования и ограничения**:
   - Сначала уточни project type.
   - Затем последовательно собери requirements, preferences и constraints.
   - Каждое подтвержденное требование или ограничение сразу фиксируй через `madspec memory capture --stage mvp.tech`.

3. **Выбери компоненты стека**:
   - Для каждого ключевого слота обсуждай 2-3 варианта и приводь краткое обоснование.
   - После утверждения фиксируй выбранный вариант через `--stack-component`.
   - Обсуждай как минимум: `language`, `frontend` или `backend` по ситуации, `database` при необходимости, testing slot, `build`, `deploy` при необходимости.
   - Если обсуждается полезная, но не выбранная технология, фиксируй ее через `--alternative`.

4. **Зафиксируй организацию кода**:
   - Обсуди repo strategy, source layout и modularity.
   - После утверждения сохрани решение через `--code-organization`.

5. **Валидация перед checkpoint**:
   - Выполни `madspec memory retrieve --stage mvp.tech --toon-output --full-artifact`, если этот вывод читает агент.
   - Проверь, что заполнены:
     - `projectType`
     - `stackOverview`
     - хотя бы один `language`
     - хотя бы один `build`
     - хотя бы один testing component
     - `codeOrganization`
   - Если чего-то не хватает, не переходи к checkpoint и продолжи диалог.

6. **Checkpoint**:
   - Выполни `madspec memory checkpoint --stage mvp.tech --summary "<итог>" --evidence .madspec/<BRANCH>/tech-stack.md`.
   - Если остались открытые вопросы, добавь `--question`.
   - Для следующих действий добавь `--pending-action`.

## Правила

- **НЕ** редактируй `tech-stack.md` вручную.
- **НЕ** предлагай стек без обоснования.
- **НЕ** переходи к `mvp.architecture`, пока `tech_status.is_complete != true` и пользователь явно не согласовал стек.
- Если пользователь меняет одно tech-решение, проверь, не устарели ли связанные компоненты, ограничения и отклоненные альтернативы, затем обнови structured memory.

## Выходные артефакты

- `.madspec/<BRANCH>/memory/stages/mvp.tech.json` — canonical state этапа
- `.madspec/<BRANCH>/tech-stack.md` — generated artifact технологического стека
- `.madspec/<BRANCH>/project-context.md` — regenerated view с tech summary

## Следующий этап

После утверждения и checkpoint переходи к `/madspec.mvp.architecture`.
