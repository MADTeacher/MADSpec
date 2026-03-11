---
description: Review после реализации или набора изменений - quality analysis, fit-gap review и backlog улучшений
---

## Пользовательский ввод

```text
$ARGUMENTS
```

Ты **ОБЯЗАН** учитывать пользовательский ввод перед продолжением (если он не пустой).

## Правила диалога (обязательно)

- **Задавай вопросы строго по одному**: в каждом твоем сообщении должен быть **ровно 1 вопрос**, который требует ответа.
- **Не выдавай список вопросов заранее** (никаких длинных анкет/чек-листов вопросов за раз).
- Если нужен выбор, задай **один вопрос** и предложи **не больше 3-5 вариантов** (или попроси свободный ответ).
- **Дожидайся ответа** и только затем задавай следующий вопрос.
- Если ответ неполный, задай **один уточняющий вопрос**, а не несколько сразу.

## Structured Memory First (обязательно)

- Review работает в branch-aware memory-first режиме.
- Источник истины: `.madspec/<BRANCH>/memory/`, runtime progress implementation stages и stage records.
- `review.md`, `improvements.md` и `project-context.md` считаются generated views, а не canonical source of truth.
- Перед началом анализа используй `madspec memory retrieve --stage review --json-output`.
- Для дополнительного runtime-контекста используй `madspec memory retrieve --stage mvp.implement --json-output` или `madspec memory retrieve --stage feature.implement --json-output`, если в ветке есть соответствующий workflow.
- После каждого подтвержденного finding, decision, open question или improvement используй `madspec memory capture --stage review ...`.
- После завершения анализа ратифицируй этап через `madspec memory checkpoint --stage review --summary ...`.
- `madspec memory capture` и `madspec memory checkpoint` сами запускают `madspec memory consolidate` и `madspec memory validate`.

## Описание

`madspec.review` выполняет quality review после реализации шага, набора шагов или заметного change set. Команда анализирует, насколько текущее состояние кода и артефактов соответствует целям ветки, implementation plan и принятым решениям, а затем фиксирует findings и backlog улучшений в structured memory.

## Когда использовать

- После `madspec.mvp.implement`
- После `madspec.feature.implement`
- После заметного изменения архитектуры, интеграций, UX или качества реализации
- Перед рефакторингом, hardening или подготовкой к релизу

## Предварительные условия

- Должен существовать codebase или заметный change set для анализа
- Должен быть доступен branch context через `madspec git current-branch`
- Generated views и предыдущие stage artifacts используй по мере наличия, но их отсутствие **не должно** автоматически блокировать review
- Если нет кода или branch context, сообщи об ограничении и предложи сначала завершить соответствующий implementation workflow

## Цель review

Провести change-aware анализ по четырем направлениям:

1. Соответствие реализации целям ветки, плану и ключевым решениям
2. Качество кода, тестов, обработки ошибок и поддерживаемости
3. Архитектурные, интеграционные и UX-последствия
4. Формирование backlog улучшений с приоритетом

## Порядок работы

0. **Определи текущую ветку**
   - Перед началом выполни `madspec git current-branch` из корня проекта
   - Используй результат как `<BRANCH>` для branch-aware артефактов
   - Если ветку определить не удалось, используй `main` и явно отметь это как ограничение анализа

1. **Загрузи memory и runtime context**
   - Сначала выполни `madspec memory retrieve --stage review --json-output`
   - Затем проверь, какой implementation workflow актуален для ветки:
     - `mvp.implement`
     - `feature.implement`
   - Если есть runtime progress, прочитай:
     - `.madspec/<BRANCH>/memory/progress.json`
     - `.madspec/<BRANCH>/memory/working/active-session.json`
     - `.madspec/<BRANCH>/implementation-plan.md` и контексты шагов в `.madspec/<BRANCH>/steps/`, если они существуют
   - Используй generated views для ориентации, а memory records и progress state как источник истины

2. **Собери доступный branch context**
   - По мере наличия прочитай:
     - `.madspec/<BRANCH>/concept.md`
     - `.madspec/<BRANCH>/ui-design.md`
     - `.madspec/<BRANCH>/tech-stack.md`
     - `.madspec/<BRANCH>/architecture.md`
     - `.madspec/<BRANCH>/deployment.md`
     - `.madspec/<BRANCH>/review.md`
     - `.madspec/<BRANCH>/improvements.md`
   - Если часть файлов отсутствует, не останавливай review. Зафиксируй это как limitation.
   - Проанализируй реализованный код, тесты и структуру проекта.

3. **Проведи review по четырем направлениям**

   **A. Fit-gap review**
   - Сравни текущее состояние с intent ветки, implementation plan и ключевыми решениями
   - Выяви расхождения между планом, generated context и фактической реализацией
   - Отдельно проверь, не остались ли незавершенные planned steps, технические компромиссы или пропущенные сценарии

   **B. Качество кода и тестов**
   - Оцени читаемость, связанность, дублирование, обработку ошибок и технический долг
   - Проверь качество тестов:
     - есть ли тесты на ключевые сценарии
     - покрыты ли негативные и edge cases
     - не расходятся ли тесты с текущим поведением системы
   - Проверяй локальные conventions проекта и принятые архитектурные решения, а не абстрактные "идеальные" эталоны

   **C. Архитектурные и интеграционные последствия**
   - Проверь, соответствует ли реализация ожидаемой архитектуре и структуре модулей
   - Оцени влияние изменений на контракты, данные, зависимости, deployment context и observability
   - Если интерфейс или пользовательский поток изменились, проверь, не устарели ли связанные design/generated artifacts

   **D. Improvement backlog**
   - Сформируй список улучшений и раздели его на:
     - критичные
     - важные
     - опциональные
   - Для каждого улучшения фиксируй, что именно нужно сделать и зачем

4. **Сохраняй выводы в structured memory**
   - Findings о проблемах, ограничениях и наблюдениях сохраняй через `--fact`
   - Decisions о направлении исправления, refactor strategy или accepted tradeoff сохраняй через `--decision`
   - Спорные места и неясности сохраняй через `--question`
   - Конкретные действия по улучшению сохраняй через `--pending-action`
   - Если improvement уже подтвержден как направление работ, можно дополнительно сохранить его через `--decision`

5. **Финализируй review**
   - Выполни `madspec memory checkpoint --stage review --summary "<итог review>"`
   - Убедись, что `.madspec/<BRANCH>/review.md`, `.madspec/<BRANCH>/improvements.md` и `.madspec/<BRANCH>/project-context.md` пересобраны как generated views

6. **Вывод пользователю**
   - Покажи основные findings и ограничения анализа
   - Покажи топ улучшений по приоритету
   - Выведи пути к generated views:
     - `.madspec/<BRANCH>/review.md`
     - `.madspec/<BRANCH>/improvements.md`

## Правила

- **БУДЬ КОНСТРУКТИВНЫМ**: критикуй решения и риски, а не автора изменений
- **ПРИВЯЗЫВАЙСЯ К КОНТЕКСТУ ВЕТКИ**: оценивай реализацию относительно branch intent, plan и local conventions
- **НЕ ПЕРЕОБЕЩАЙ**: generated views отражают records из structured memory и не являются полноформатным экспертным отчетом
- **ФИКСИРУЙ ACTIONABLE ВЫВОДЫ**: каждое существенное замечание должно приводить к clear next step, decision или open question

## Выходные артефакты

- `.madspec/<BRANCH>/memory/` - canonical memory с review findings, decisions, questions и improvement actions
- `.madspec/<BRANCH>/review.md` - generated view отчета review
- `.madspec/<BRANCH>/improvements.md` - generated view списка улучшений
- `.madspec/<BRANCH>/project-context.md` - generated view навигации и статуса

## Следующие шаги

После завершения review можно:
- выполнить targeted refactor
- запланировать новые implementation steps
- повторно запустить review после исправлений
- перейти к `madspec.security`, если нужен security/privacy аудит текущих изменений

---

**Важно**: `madspec.review` не ограничен только финальным MVP-этапом. Это рабочая quality-команда для branch-aware анализа после реализации или заметного change set.
