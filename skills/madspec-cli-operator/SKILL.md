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
- `/madspec.mvp.design` — сделать UI-видение и HTML/CSS-прототипы
- `/madspec.mvp.tech` — выбрать стек и обосновать его
- `/madspec.mvp.architecture` — определить архитектуру, модель данных, контракты
- `/madspec.deploy` — описать окружения, CI/CD, секреты, observability, rollout
- `/madspec.mvp.plan` — разбить реализацию на отдельные шаги
- `/madspec.mvp.implement` — выполнять шаги реализации с валидацией и тестами

Для доработки существующего проекта:

- `/madspec.feature.init` — зафиксировать цель и границы фичи
- `/madspec.feature.plan` — спланировать шаги реализации фичи
- `/madspec.feature.implement` — реализовать шаги фичи

Сквозные команды:

- `/madspec.review` — review артефактов, сильные/слабые стороны, improvements
- `/madspec.security` — security/privacy аудит артефактов и кода

### CLI-команды

- `madspec init` — развернуть шаблон проекта под выбранного агента
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
- `madspec memory capture` — накапливать validated facts/decisions/contracts/questions по stage
- `madspec memory checkpoint` — завершить non-iterative stage и обновить derived state
- `madspec memory retrieve` — получить минимальный контекст stage/step; для `mvp.concept` по умолчанию возвращает краткий `concept_status`, а полный `artifact_state.concept` отдает только по `--full-artifact`
- `madspec memory consolidate` — пересобрать markdown views из structured memory
- `madspec memory validate` — проверить согласованность памяти и generated views

## Рабочие инварианты

- Начинай с чтения существующих артефактов в `.madspec/<branch>/`, а не с предположений о текущем этапе
- Для MVP соблюдай порядок `concept -> design -> tech -> architecture -> plan -> implement`
- Для `mvp.design` считай нормой длинную итеративную работу через много независимых чатов: новый чат должен восстанавливать состояние из `.madspec/<branch>/memory/`, `ui-design.md` и `ui-prototype/`, а не из истории предыдущего разговора
- Для feature workflow не пропускай `feature.init` перед `feature.plan`
- Если деплой влияет на архитектуру, интеграции, секреты, миграции или observability, учитывай `deployment.md` или инициируй `/madspec.deploy`
- Перед реализацией сверяйся с `implementation-plan.md`, `steps/`, `memory/progress.json` и relevant generated context
- Если работа идёт через structured memory, сначала обновляй memory, потом пересобирай views, потом валидируй
- Для `mvp.design` любой подтвержденный change в экране, потоке, навигации, platform-specific поведении, данных на экране или coverage функций обязан сопровождаться проверкой и актуализацией связанных design-артефактов и structured memory
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

### Пользователь просит обойти workflow

- Можно адаптироваться, но нужно явно назвать, какие артефакты и решения тогда останутся непокрытыми
- Для ускорения допустимо делать минимальный проход, но не выдавай неподготовленный этап за полноценно завершённый

## Практика работы

- Предпочитай чтение generated context для ориентации и memory-файлов для проверки истины
- Для branch-aware операций используй CLI MADSpec, а не ad-hoc shell-логику
- Если меняешь или документируешь CLI-поведение, сверяйся с текущим `README.md`, `AGENTS.md` и шаблонами команд
- Для `mvp.concept` используй краткий `madspec memory retrieve --json-output` в обычных ходах диалога, `--include-history` только при явной необходимости, а `--full-artifact` только перед финальной валидацией, итоговым обзором и `checkpoint`
- Для `mvp.design` в начале каждой новой сессии выполняй `madspec memory retrieve --stage mvp.design --json-output`, затем сверяй `ui-design.md` и файлы в `ui-prototype/`; не считай дизайн завершенным, пока пользователь явно не утвердил текущее состояние
- Если менялись HTML/CSS-прототипы, проверь, не устарели ли `ui-design.md`, навигационное описание, user flows, coverage функций и ссылки на prototype-файлы
- Не расширяй этот skill до полной документации продукта; держи его как операторский слой
