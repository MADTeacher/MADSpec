---
name: madspec-cli-operator
description: Операционный skill по MADSpec Framework и MADSpec CLI. Использовать, когда агент работает внутри проекта MADSpec, должен понимать staged workflow, branch-aware артефакты `.madspec`, команды CLI, а также типовые сбои и правила эскалации к пользователю.
---

# MADSpec CLI Operator

## Когда использовать

Используй этот skill, когда репозиторий использует MADSpec или пользователь просит:

- работать по workflow `madspec.mvp.*` или `madspec.feature.*`
- разобраться с артефактами в `.madspec/`
- использовать MADSpec CLI (`madspec init`, `madspec git`, `madspec memory`, `madspec check`, `madspec version`, `madspec migrate`)
- понять, какой этап следующий, каких артефактов не хватает, и как восстановить workflow после сбоя

## Что такое MADSpec

MADSpec управляет разработкой через агентные команды и branch-aware артефакты в `.madspec/<branch>/`.

- Шаблоны и процедуры живут в `.madspec/templates/` и `.madspec/procedures/`
- Рабочие артефакты привязаны к текущей ветке
- Ветка определяется через `madspec git current-branch`
- Structured memory в `.madspec/<branch>/memory/` является источником истины для состояния workflow
- Markdown-файлы контекста часто являются generated views, а не каноническими данными

## Карта команд

### Агентные slash-команды

Для нового продукта:

- `/madspec.mvp.concept` — зафиксировать идею, аудиторию, pain points, P1/P2/P3
- `/madspec.mvp.design` — сделать UI-видение и storyboard HTML/CSS-прототипы
- `/madspec.mvp.tech` — выбрать стек и обосновать его
- `/madspec.mvp.architecture` — определить архитектуру, модель данных, контракты
- `/madspec.deploy` — описать окружения, CI/CD, секреты, observability, rollout
- `/madspec.mvp.plan` — разбить реализацию на отдельные шаги
- `/madspec.mvp.implement` — выполнять шаги реализации с валидацией и тестами

Для доработки существующего проекта:

- `/madspec.feature.init` — зафиксировать цель фичи, function catalog и точки интеграции в `feature.init.json`
- `/madspec.feature.plan` — спланировать шаги реализации фичи через `feature.plan.json`
- `/madspec.feature.implement` — реализовать шаги фичи через implementation memory workflow

Сквозные команды:

- `/madspec.review` — change-aware quality review после реализации: fit-gap, code quality, architecture impact, improvements
- `/madspec.security` — pragmatic security/privacy аудит кода, зависимостей, архитектуры и обработки ПД по 152-ФЗ

### CLI-команды

- `madspec init` — развернуть шаблон проекта под выбранного агента (`cursor-agent`, `opencode`, `kilocode`, `roo`, `sourcecraft`, `qwen`, `copilot`)
- `madspec check` — проверить наличие git и поддерживаемых агентных инструментов
- `madspec version` — показать версию CLI и шаблона
- `madspec migrate` — перенести старую плоскую `.madspec/` структуру в branch-aware layout

Git-операции:

- `madspec git current-branch` — определить текущую ветку MADSpec
- `madspec git list-branches` — показать ветки, у которых уже есть MADSpec-артефакты
- `madspec git set-branch <name>` — вручную зафиксировать ветку для артефактов
- `madspec git ensure-gitignore` — добавить MADSpec-паттерны в `.gitignore`
- `madspec git init` — инициализировать git и стартовый commit
- `madspec git create-branch <name>` — создать git-ветку и синхронизировать `.madspec/<branch>/`
- `madspec git commit --message "..."` — закоммитить текущее состояние

Structured memory:

- `madspec memory init` — создать memory layout для ветки
- `madspec memory status` — проверить текущее состояние memory
- `madspec memory capture` — накапливать validated facts/decisions/contracts/questions по stage; поддерживает `--from-file`
- `madspec memory checkpoint` — завершить non-iterative stage и обновить derived state; поддерживает `--from-file`
- `madspec memory retrieve` — получить минимальный контекст stage/step; для `mvp.concept` по умолчанию возвращает краткий `concept_status`, для `mvp.design` — `design_status`, для `mvp.tech` — `tech_status`, для `mvp.plan` — `plan_status`, а полный stage artifact state отдает только по `--full-artifact`
- `madspec memory consolidate` — пересобрать markdown views из structured memory
- `madspec memory validate` — проверить согласованность памяти и generated views
- `madspec memory register-step` — зарегистрировать шаг планирования; поддерживает `--from-file`
- `madspec memory start-step` — запустить шаг реализации; поддерживает `--from-file`
- `madspec memory checkpoint-step` — зафиксировать промежуточное состояние шага; поддерживает `--from-file`
- `madspec memory complete-step` — завершить шаг реализации; поддерживает `--from-file`

## Рабочие инварианты

- Для команд `memory capture`, `memory checkpoint`, `memory register-step`, `memory start-step`, `memory checkpoint-step` и `memory complete-step` **ОБЯЗАТЕЛЬНО** используй `--from-file`: записывай аргументы в JSON-файл и передавай путь через `--from-file <path>`. Это гарантирует работу на всех платформах (Windows имеет лимит ~8191 символов для cmd.exe) и устраняет проблемы с экранированием спецсимволов в shell
- Начинай с чтения существующих артефактов в `.madspec/<branch>/`, а не с предположений о текущем этапе
- Для MVP соблюдай порядок `concept -> design -> tech -> architecture -> plan -> implement`
- Для `mvp.design` считай нормой длинную итеративную работу через много независимых чатов: новый чат должен восстанавливать состояние из `.madspec/<branch>/memory/`, `ui-design.md` и `ui-prototype/`, а не из истории предыдущего разговора
- Для `mvp.design` при проектировании UI/UX, storyboard и HTML/CSS-прототипов обязательно подключай skill `frontend-design` как основной design-skill; `ui-storyboard-contract` задает структуру и review-flow, а `frontend-design` отвечает за визуальное качество и характер решения
- Для `mvp.design` prototype files считай approved storyboard contract: они не обязаны быть сделаны по общей болванке, но обязаны быть кликабельны по основным review journeys
- Для `mvp.tech` работай так же memory-first: источник истины — `.madspec/<branch>/memory/stages/mvp.tech.json`, а `tech-stack.md` является generated artifact и не редактируется вручную
- Для `mvp.architecture` работай так же memory-first: источник истины — `.madspec/<branch>/memory/stages/mvp.architecture.json`, а `architecture.md`, `data-model.md` и `contracts/openapi.yaml` являются generated artifacts и не редактируются вручную
- Для `mvp.plan` работай так же memory-first: источник истины — `.madspec/<branch>/memory/stages/mvp.plan.json`, а `implementation-plan.md` и `planning-context-cache.md` являются generated artifacts и не редактируются вручную
- Для `mvp.implement` используй implementation memory workflow: перед каждой сессией запускай `madspec memory retrieve --stage mvp.implement --json-output`, стартуй шаг через `madspec memory start-step`, фиксируй `red/green/refactor` через `madspec memory checkpoint-step`, а завершай шаг только через `madspec memory complete-step`
- Для `mvp.implement` считай `.madspec/<branch>/memory/progress.json` и `.madspec/<branch>/memory/working/active-session.json` каноническим runtime-state; `implementation-context.md` и `project-context.md` — это generated views, которые не редактируются вручную как source of truth
- Для feature workflow не пропускай `feature.init` перед `feature.plan`
- Для `feature.init` источник истины — `.madspec/<branch>/memory/stages/feature.init.json`; `project-analysis.md`, `feature-context.md`, `tech-stack.md` и `architecture.md` являются generated views
- Для `feature.plan` источник истины — `.madspec/<branch>/memory/stages/feature.plan.json`; `implementation-plan.md`, `planning-context-cache.md` и `planning-context.md` являются generated views
- Для `feature.implement` работай так же, как для `mvp.implement`: перед каждой сессией запускай `madspec memory retrieve --stage feature.implement --json-output`, затем `start-step/checkpoint-step/complete-step`
- Для `review` считай команду кросс-сценарной: она может запускаться после `mvp.implement` или `feature.implement`, должна читать codebase, `memory/progress.json`, `active-session.json`, `implementation-plan.md`, relevant step contexts и branch artifacts по мере наличия; отсутствие части артефактов фиксируй как limitation, а не как автоматический отказ
- Для `review` сохраняй findings через `madspec memory capture --stage review` с маппингом: observations/problems -> `--fact`, improvement directions/tradeoffs -> `--decision`, open items -> `--question`, concrete follow-ups -> `--pending-action`
- Для `security` работай memory-first и branch-aware так же: читай codebase, progress/runtime state, `tech-stack.md`, `architecture.md`, `deployment.md` и previous `security` records по мере наличия
- Для `security` считай privacy/compliance контекстом только 152-ФЗ; не обещай универсальную multi-jurisdiction проверку и не используй `--jurisdiction`
- Для `security` классифицируй риски через severity buckets (`critical/high/medium/low`), а не через обязательный numeric score: текущие generated views рендерятся из records и не поддерживают надежную scorecard-модель
- Для `security` если есть `deployment.md`, учитывай secrets, CI/CD, environment separation, observability и rollout risks; если файла нет, фиксируй это как limitation анализа
- Если деплой влияет на архитектуру, интеграции, секреты, миграции или observability, учитывай `deployment.md` или инициируй `/madspec.deploy`
- Перед реализацией сверяйся с `implementation-plan.md`, `steps/`, `memory/progress.json` и relevant generated context
- Если работа идёт через structured memory, сначала обновляй memory, потом пересобирай views, потом валидируй
- Для `mvp.design` любой подтвержденный change в экране, потоке, навигации, platform-specific поведении, данных на экране или coverage функций обязан сопровождаться проверкой и актуализацией связанных design-артефактов и structured memory
- Для `mvp.design` не показывай пользователю `P1/P2/P3` как визуальные бейджи в прототипе; приоритеты нужны для internal coverage, а не для review storyboard
- Для изменений интерфейса соблюдай порядок `source artifacts -> canonical memory -> generated views -> validate`: сначала обнови прототипы и typed state, затем связанные описания, потом `madspec memory consolidate`, затем `madspec memory validate`

## Что агент должен проверять сам

Сначала исследуй локальную среду и только потом задавай вопросы пользователю.

Проверь сам:

- существует ли `.madspec/` и какая ветка активна
- есть ли обязательные артефакты для текущей стадии
- есть ли `memory/progress.json`, `active-session.json`, `implementation-plan.md`, `deployment.md`
- является ли missing-файл реальной ошибкой или этап просто ещё не выполнялся
- не устарела ли структура проекта и не нужен ли `madspec migrate`

Спрашивай пользователя только если:

- есть продуктовая неоднозначность, которую нельзя вывести из артефактов
- нужно выбрать один из нескольких валидных tradeoff
- отсутствует обязательный вход для следующего шага и его нельзя восстановить из репозитория

## Траблшутинг

### Нет `.madspec/` или отсутствует branch layout

- Если это новый проект, предложи `madspec init`
- Если `.madspec/` есть, но артефакты лежат в корне, предложи `madspec migrate`
- Если git-ветка не определяется, используй `madspec git current-branch` и при необходимости `madspec git set-branch <name>`

### Не хватает артефактов предыдущего этапа

- Не перескакивай через workflow молча
- Явно укажи, какого этапа или файла не хватает
- Направь пользователя к предыдущей slash-команде: например, `concept` перед `design`, `plan` перед `implement`

### Generated views расходятся с memory

- Не лечи это ручным редактированием generated markdown по умолчанию
- Сначала выполни `madspec memory consolidate`
- Затем выполни `madspec memory validate`
- Если validation падает, исправляй canonical memory/source artifacts, а не только производные файлы

### Реализация потеряла текущий шаг

- Смотри `memory/progress.json` и `active-session.json`
- Определи следующий шаг по `currentImplementStep`, planned/completed steps и step metadata
- Не придумывай новый шаг, если план уже существует и его можно продолжить

### Generated implementation context расходится с memory

- Не исправляй `implementation-context.md` вручную
- Сначала проверь step records в `decision-log.jsonl`, `events.jsonl` и semantic memory
- Затем выполни `madspec memory consolidate`
- После этого выполни `madspec memory validate`
- Если расхождение осталось, исправляй canonical memory и records, а не generated markdown

### Пользователь просит обойти workflow

- Можно адаптироваться, но нужно явно назвать, какие артефакты и решения тогда останутся непокрытыми
- Для ускорения допустимо делать минимальный проход, но не выдавай неподготовленный этап за полноценно завершённый

### Команда memory падает на Windows / слишком длинная командная строка

- Windows cmd.exe ограничивает командную строку ~8191 символами, PowerShell sandbox агентов может иметь ещё более жёсткие ограничения
- Команда `memory capture` с ~75 параметрами легко превышает этот лимит при заполнении данными архитектуры, дизайна или концепции
- Решение: используй `--from-file <path>` — запиши все аргументы в JSON-файл и передай путь к нему
- Пример: `madspec memory capture --from-file .madspec/.tmp/capture-args.json --json-output`
- JSON-файл содержит те же ключи, что и `options` dict соответствующей команды, плюс `stage`, `branch`, `json_output`, `status` и `summary` на верхнем уровне

## Практика работы

- Предпочитай чтение generated context для ориентации и memory-файлов для проверки истины
- Для branch-aware операций используй CLI MADSpec, а не ad-hoc shell-логику
- Если нужно менять сам MADSpec CLI, используй текущий internal layout: `src/madspec_cli/features/*/cli.py` для entrypoints `init/git/meta`, `src/madspec_cli/memory/cli/` для memory-команд, `application/` для orchestration и `shared/*` для общих адаптеров; legacy-модули допустимы только как compatibility/backend слой
- Если меняешь или документируешь CLI-поведение, сверяйся с текущим `README.md`, `AGENTS.md` и шаблонами команд
- Для `mvp.concept` используй краткий `madspec memory retrieve --json-output` в обычных ходах диалога, `--include-history` только при явной необходимости, а `--full-artifact` только перед финальной валидацией, итоговым обзором и `checkpoint`
- Для `mvp.design` в начале каждой новой сессии выполняй `madspec memory retrieve --stage mvp.design --json-output`, затем сверяй `ui-design.md`, `.madspec/templates/ui-storyboard-contract.md` и файлы в `ui-prototype/`; не считай дизайн завершенным, пока пользователь явно не утвердил текущее состояние
- Для `mvp.design` не подменяй skill `frontend-design` общими правилами storyboard contract: visual direction, typography, color, composition и ощущение интерфейса должны идти через этот skill, а structured memory фиксирует утвержденный state
- Для `mvp.design` у `--screen-data` используй только логический field id в формате `<screen-id>::<displayed|input>::<name>`; не добавляй туда описания и дополнительные `::` сегменты
- Для `mvp.architecture` в обычных ходах используй `madspec memory retrieve --stage mvp.architecture --json-output` и опирайся на `architecture_status`; `--full-artifact` запрашивай только перед итоговой валидацией и `checkpoint`
- Для `mvp.architecture` у `--endpoint-field` секция `response` допустима как shorthand для `response:200`; если нужен конкретный статус ответа, используй `response:<status>`
- Если архитектурная валидация выглядит ложной, не редактируй `.madspec/<branch>/memory/stages/*.json` вручную: сначала проверь `screen.data` и `endpoint-field`, затем исправляй state только через `madspec memory capture`/`checkpoint`
- Для `mvp.plan` в обычных ходах используй `madspec memory retrieve --stage mvp.plan --json-output` и опирайся на `plan_status`; `--full-artifact` запрашивай только перед итоговой валидацией и `checkpoint`
- Для `mvp.implement` в начале каждой новой сессии выполняй `madspec memory retrieve --stage mvp.implement --json-output`, затем запускай шаг через `madspec memory start-step`; после завершения TDD-цикла проверяй итог повторным `retrieve`, а `implementation-context.md` используй только как generated summary
- Если менялись HTML/CSS-прототипы, проверь, не устарели ли `ui-design.md`, navigation, review journeys, coverage функций и ссылки на prototype-файлы
- Для UI-реализации сверяй не только `ui-design.md`, но и реальный кликабельный путь из `ui-prototype/index.html`; если реализация хочет отойти от storyboard, сначала вернись к `mvp.design` или явно зафиксируй approval на drift
- Если менялась архитектура, модель данных или контракты, обновляй canonical architecture-state через `madspec memory capture`, затем пересобирай generated artifacts и валидируй memory
- Не расширяй этот skill до полной документации продукта; держи его как операторский слой
