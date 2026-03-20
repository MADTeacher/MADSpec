---
description: Pragmatic security/privacy audit после изменений - риски по коду, зависимостям, архитектуре и обработке ПД по 152-ФЗ
---

## Пользовательский ввод

```text
$ARGUMENTS
```

## Обязательный skill `madspec-cli-operator`

- Перед началом работы обязательно найди и прочитай skill `madspec-cli-operator`.
- Дальше работай, опираясь на `madspec-cli-operator` как на базовый operational layer для workflow `madspec.*`, branch-aware артефактов `.madspec/` и команд MADSpec CLI.

Ты **ОБЯЗАН** учитывать пользовательский ввод перед продолжением (если он не пустой).

## Structured Memory First (обязательно)

- Security audit работает в branch-aware memory-first режиме.
- Источник истины: `.madspec/<BRANCH>/memory/`, runtime progress implementation stages и security-stage records.
- `project-context.md` и `security-audit.md` считай generated views, а не canonical source of truth.
- Перед началом аудита используй `madspec memory retrieve --stage security --toon-output`, если этот контекст читает агент.
- Перед началом аудита дополнительно используй `madspec security status --toon-output`, если этот вывод читает агент, чтобы увидеть блокирующие, предупреждающие и ожидающие проверки, а также активные исключения.
- Если в ветке есть implementation workflow, дополнительно используй `madspec memory retrieve --stage mvp.implement --toon-output` или `madspec memory retrieve --stage feature.implement --toon-output`, если этот контекст читает агент.
- После каждого подтвержденного security finding, remediation decision, limitation или compliance constraint используй `madspec memory capture --stage security ...`.
- После завершения аудита ратифицируй этап через `madspec memory checkpoint --stage security --summary ...`.
- `madspec memory capture` и `madspec memory checkpoint` сами запускают `madspec memory consolidate` и `madspec memory validate`.
- **ОБЯЗАТЕЛЬНО**: для вызовов `madspec memory capture` и `madspec memory checkpoint` используй `--from-file`: записывай аргументы в JSON-файл и передавай путь через `--from-file <path>` (например, `madspec memory capture --from-file .madspec/.tmp/capture-args.json --json-output`). Ключи JSON соответствуют именам полей в `options` (например, `facts`, `decisions`, `questions`, `pending_actions`), плюс `stage`, `branch`, `json_output`, `status` на верхнем уровне.

## Правила диалога (обязательно)

- **Задавай вопросы строго по одному**: в каждом твоем сообщении должен быть **ровно 1 вопрос**, который требует ответа.
- **Не выдавай список вопросов заранее** (никаких длинных анкет/чек-листов вопросов за раз).
- Если нужен выбор, задай **один вопрос** и предложи **не больше 3-5 вариантов** (или попроси свободный ответ).
- **Дожидайся ответа** и только затем задавай следующий вопрос.
- Если ответ неполный, задай **один уточняющий вопрос**, а не несколько сразу.

## Описание

`madspec.security` выполняет pragmatic security/privacy audit текущего change set, codebase и branch context. Команда помогает найти риски в коде, зависимостях, архитектуре, интеграциях и обработке персональных данных в контексте 152-ФЗ.

Команда **не заменяет** полноценный юридический, сертификационный или внешний security audit. Она фиксирует практические риски, ограничения и remediation actions в structured memory.

## Предварительные условия

- Должен существовать реализованный код проекта или заметный набор изменений
- Должен быть доступен branch context через `madspec git current-branch`
- Желательно наличие `.madspec/<BRANCH>/tech-stack.md` и `.madspec/<BRANCH>/architecture.md`, но их отсутствие не должно автоматически блокировать аудит
- Если есть `.madspec/<BRANCH>/deployment.md`, его нужно учитывать
- Если кода нет, предложи сначала завершить `madspec.mvp.implement` или `madspec.feature.implement`

## Цель команды

Провести security/privacy audit текущего состояния по следующим категориям:

- authn/authz
- secrets и credentials handling
- input validation / injection risks
- dependencies и supply-chain hygiene
- storage / transport protection
- logging / monitoring / exposure of sensitive or personal data
- external integrations, file handling и SSRF-like risks
- обработка персональных данных в контексте 152-ФЗ

## Параметры команды

- `--scope` - определяет глубину и фокус проверки:
  - `default` (по умолчанию) - code + dependencies + architecture risks + обработка ПД
  - `release` - расширенная проверка перед релизом: code + dependencies + architecture + deployment context + observability + data handling
  - `privacy` - только риски обработки и защиты персональных данных по 152-ФЗ
  - `deep` - углубленный аудит по всем доступным направлениям с более широким поиском рисков
  - Можно комбинировать: `--scope default,privacy`

- `--skip-artifacts` - пропускает жесткую проверку наличия branch artifacts:
  - если флаг не указан, сначала проверь наличие ключевого контекста и сообщи об ограничениях
  - если флаг указан, работай только с доступным кодом, memory и файлами

**Примеры использования:**
- `/madspec.security` - стандартный security/privacy audit
- `/madspec.security --scope release` - расширенная проверка перед релизом
- `/madspec.security --scope privacy` - только обработка и защита ПД по 152-ФЗ
- `/madspec.security --scope deep` - углубленный аудит
- `/madspec.security --skip-artifacts` - анализ с доступным контекстом без жестких требований к артефактам

## Порядок работы

0. **Определи текущую ветку**
   - Выполни `madspec git current-branch` из корня проекта
   - Используй имя ветки как `<BRANCH>` для branch-aware путей
   - Если ветку определить не удалось, используй `main` и явно отметь это как limitation

1. **Разбери scope**
   - Если `--scope` не указан, используй `default`
   - Если scope комбинированный, выполни все указанные категории без дублирования
   - Не используй неописанные режимы и не ссылайся на `--jurisdiction`: privacy context всегда 152-ФЗ

2. **Загрузи memory, implementation и branch context**
   - Сначала выполни `madspec memory retrieve --stage security --toon-output`, если этот вывод читает агент
   - Затем выполни `madspec security status --toon-output`, если этот вывод читает агент
   - При наличии implementation workflow дополнительно изучи:
     - `.madspec/<BRANCH>/memory/progress.json`
     - `.madspec/<BRANCH>/memory/working/active-session.json`
     - `.madspec/<BRANCH>/implementation-plan.md`
     - `.madspec/<BRANCH>/steps/step-[NN]-[name]/implementation-context.md`
   - По мере наличия прочитай:
     - `.madspec/<BRANCH>/tech-stack.md`
     - `.madspec/<BRANCH>/architecture.md`
     - `.madspec/<BRANCH>/concept.md`
     - `.madspec/<BRANCH>/deployment.md`
     - `.madspec/<BRANCH>/security-audit.md`
   - Используй generated views для навигации, а structured memory и runtime state как источник истины

3. **Определи ограничения анализа**
   - Проверь, есть ли код, тесты, dependency manifests и deployment context
   - Если чего-то не хватает:
     - не останавливай аудит автоматически
     - явно зафиксируй limitation в findings
   - Если есть `deployment.md`, учитывай secrets, CI/CD, environment separation, observability и rollout risks
   - Если `deployment.md` нет, зафиксируй отсутствие deployment context как ограничение анализа

4. **Проведи аудит по стек-зависимым категориям**

   **A. Authn/Authz**
   - Проверь аутентификацию, авторизацию, разграничение ролей и доступ к чувствительным операциям
   - Ищи broken access control, слабые проверки прав и пропущенные guard rails

   **B. Secrets и credentials**
   - Ищи hardcoded secrets, токены, ключи, пароли и небезопасные конфигурации
   - Проверяй, используются ли environment variables, secret stores и безопасные defaults

   **C. Input validation / injection**
   - Ищи SQL/command/template/code injection risks
   - Проверяй валидацию пользовательского ввода, санитизацию и небезопасные sink points

   **D. Dependencies и supply chain**
   - Проверь manifests и lock-файлы
   - Определи, какие локальные или стандартные инструменты сканирования зависимостей подходят стеку проекта
   - Если сканирование не выполнялось, зафиксируй recommended action, а не выдумывай результат

   **E. Storage / transport / logging**
   - Проверь хранение и передачу чувствительных данных
   - Оцени, не попадают ли секреты, токены и персональные данные в логи, ошибки или debug output
   - Проверь, есть ли очевидные проблемы с cookies, sessions, TLS assumptions или защитой данных при хранении

   **F. External integrations / files / SSRF-like risks**
   - Проверь работу с внешними API, webhooks, URL из пользовательского ввода, файлами и фоновой обработкой
   - Ищи SSRF-like сценарии, небезопасную загрузку файлов и слабые ограничения на внешние ресурсы

5. **Отдельно проверь обработку ПД по 152-ФЗ**
   - Определи, где и какие персональные данные обрабатываются
   - Проверь, есть ли минимизация и явная цель обработки, если это можно вывести из кода и артефактов
   - Проверь защиту ПД при хранении и передаче
   - Проверь, не раскрываются ли ПД в логах, ошибках, аналитике или тестовых данных
   - Проверь, видны ли механизмы исправления, удаления, ограничения доступа или lifecycle handling
   - Если по коду и артефактам не видно policy/consent/process слоя, фиксируй это как compliance gap или limitation, а не как доказанное нарушение

6. **Фиксируй результаты в structured memory**
   - Findings о рисках, ограничениях и наблюдениях сохраняй через `--fact`
   - Remediation decisions, compensating controls и accepted tradeoffs сохраняй через `--decision`
   - Security/privacy constraints сохраняй через `--contract`
   - Незакрытые риски и спорные места сохраняй через `--question`
   - Конкретные действия по исправлению сохраняй через `--pending-action`
   - Gate status из `madspec security status` используй как процедурное подтверждение: блокирующие и ожидающие результаты, а также активные исключения должны быть явно отражены в findings, limitations или compensating controls

7. **Классифицируй риски по severity**
   - Используй severity buckets:
     - `critical`
     - `high`
     - `medium`
     - `low`
   - Не рассчитывай обязательный `Security Score 0-100`: current generated views строятся из records и не поддерживают надежную scorecard-модель

8. **Финализируй audit**
   - Выполни `madspec memory checkpoint --stage security --summary "<итог security audit>"`
   - Убедись, что `.madspec/<BRANCH>/security-audit.md` и `.madspec/<BRANCH>/project-context.md` пересобраны как generated views

9. **Вывод пользователю**
   - Покажи ключевые findings с severity
   - Покажи ограничения анализа
   - Покажи top remediation actions
   - Выведи путь к generated view:
     - `.madspec/<BRANCH>/security-audit.md`

## Правила

- **БУДЬ ПРАГМАТИЧНЫМ**: ищи реальные риски текущего стека и change set, а не формально проходись по чек-листам ради чек-листов
- **НЕ ВЫДАВАЙ ЛОЖНУЮ ТОЧНОСТЬ**: не обещай юридическую верификацию, сертификацию или числовой security score без отдельной модели
- **УЧИТЫВАЙ DEPLOYMENT CONTEXT**: если он есть, используй его; если нет, фиксируй ограничение явно
- **ПРИВЯЗЫВАЙСЯ К ДОСТУПНЫМ ФАКТАМ**: если evidence недостаточно, формулируй finding как risk, gap или unknown, а не как доказанное нарушение

## Выходные артефакты

- `.madspec/<BRANCH>/memory/` - canonical memory с security/privacy findings, constraints, decisions и remediation actions
- `.madspec/<BRANCH>/security-audit.md` - generated view security/privacy audit
- `.madspec/<BRANCH>/project-context.md` - generated view навигации и ссылок

## Следующие шаги

После завершения security audit пользователь может:
- исправить критичные и high severity проблемы
- обновить уязвимые зависимости
- устранить gaps по защите персональных данных
- доработать deployment context, secrets handling и observability
- повторить аудит после исправлений

---

**Важно**: `madspec.security` ориентирован на практический security/privacy hardening в контексте 152-ФЗ и текущего технологического стека. Если позже нужен richer compliance report или scorecard, это требует отдельной доработки memory schema и renderer-ов, а не только шаблона команды.
