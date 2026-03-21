---
name: madspec-cli-operator
description: Операционный навык по MADSpec Framework и MADSpec CLI. Использовать, когда агент работает внутри проекта MADSpec, должен понимать поэтапный процесс работы, артефакты `.madspec`, привязанные к ветке, команды CLI, а также типовые сбои и правила эскалации к пользователю.
---

# MADSpec CLI Operator

## Когда использовать

Используй этот навык, когда в репозитории уже есть структура MADSpec, например `.madspec/`, или когда пользователь просит:

- идти по процессу `madspec.mvp.*` или `madspec.feature.*`
- разобраться с артефактами в `.madspec/`
- использовать MADSpec CLI
- понять, какой этап следующий, каких артефактов не хватает и как восстановить процесс после сбоя

Все сгенерированные команды `madspec.*` должны начинать работу с чтения и применения этого навыка как базового операторского слоя.
Для `mvp.design` этот навык обязателен вместе с отдельным навыком `frontend-design`.

## Базовый алгоритм работы

1. Сначала исследуй локальную среду: есть ли `.madspec/`, какая ветка активна, какие артефакты уже существуют.
2. Определи ветку через `madspec git current-branch`, а не через разрозненную shell-логику.
3. Читай каноническое состояние и только потом производные Markdown-представления.
4. Для текущей стадии восстанови контекст через `madspec memory retrieve --stage <stage> --session-key <key> --toon-output`, если ответ будет читать агент; если отдельный session-local контекст не нужен, используй значение по умолчанию `active`. `--json-output` оставляй для машинной интеграции и случаев, когда нужен именно JSON-контракт.
5. Если нужно понять различие между session-local фокусом и общим workflow state ветки, используй `madspec memory explain --stage <stage> --session-key <key> --json-output`.
6. Если дальше будет mutating runtime-команда, возьми из `retrieve` текущее значение `runtime_revision` и, когда сценарий чувствителен к параллельным записям, передай его обратно через `--expected-revision`.
7. Если нужно понять блокировки перехода, сначала смотри `policy_context` и `gate status`, а не редактируй файлы вручную.
8. Перед изменением состояния используй канонические команды CLI, а не прямое редактирование `.json`, `.jsonl` и производных `.md`.
9. Если обязательного входа не хватает и его нельзя восстановить из репозитория, только тогда эскалируй вопрос пользователю.

## Что помнить всегда

- MADSpec привязывает рабочие артефакты к ветке в `.madspec/<branch>/`.
- Канонические данные и производные представления нельзя путать: Markdown-контекст часто является только проекцией.
- Runtime state ветки теперь канонически хранится в `SQLite`: `progress`, stage snapshots, session-local state и runtime record streams сначала коммитятся туда, а branch files остаются производными projections. Файл `active-session.json` поддерживается только как проекция для session `active`.
- Rollout parallel runtime теперь разделен явно: default-конфиг проекта содержит `parallelRuntime.phase1Enabled=true` и `parallelRuntime.phase2Enabled=false`. Ключ `parallelRuntime.phase2Enabled` определяет, остается ли проект в default Phase 1 или явно включает opt-in Phase 2. Отсутствие блока `parallelRuntime` в старом проекте считай legacy-safe эквивалентом того же default.
- Для многосубагентной координации поверх session-local runtime теперь есть канонические `task` и `work-item`, но этот протокол относится к opt-in Phase 2. Их жизненный цикл ведется командами `madspec memory tasks ...` и `madspec memory work-items ...`, а `claim` расширяет session payload полями `task_id`, `work_item_id`, `subagent_id`.
- Coordinator runtime теперь также хранит explicit зависимости между work items и scheduler hints роли (`default_stage`, `execution_mode_hint`, `subagent_dependencies`). Эти данные используются для readiness explain, а не для автоматического запуска субагентов.
- Для claimed `work-item` mutating runtime-команды больше не являются рекомендуемым write path только в том случае, если `parallelRuntime.phase2Enabled=true`: такой session должен использовать `madspec memory proposals publish ...`, затем `madspec memory proposals apply --proposal-id ...`.
- Если нужно понять, почему work item нельзя claim/apply прямо сейчас, используй `madspec memory coordinator explain --work-item-id ...` или `--session-key ...`, но помни, что эта линия диагностики доступна только в opt-in режиме Phase 2.
- Runtime state ветки имеет общую ревизию `runtime_revision`; успешные mutating команды возвращают `runtime_revision_before` и `runtime_revision_after`, а при устаревшей записи возможен structured `conflict`.
- Для горячих write paths MADSpec использует scoped writer lease. Если mutating команда вернула `kind="scope_busy"`, это значит, что другой writer временно держит тот же hot scope; сначала дождись освобождения lease или истечения TTL, а уже потом повторяй запись.
- Для сценария Phase 1 “реализация текущего шага и параллельное планирование следующего” совместимыми считаются `register-step(step-02)` вместе с `start-step(step-01)`, `checkpoint-step(step-01)` или `complete-step(step-01)`. Повторная запись в тот же step/catalog должна трактоваться как `conflict` или `scope_busy`, а не как неявное перетирание состояния.
- Команды, привязанные к стадии, материализуют только артефакты текущей стадии; отсутствие несвязанных производных артефактов не считай признаком поломки, пока соответствующая стадия еще не запускалась.
- Для `mvp.plan` и `feature.plan` предпочитай минимально достаточное число шагов: легкую задачу планируй одним полным шагом, если нет реальной причины делить её дальше.
- Для `memory capture`, `memory checkpoint`, `memory register-step`, `memory start-step`, `memory checkpoint-step` и `memory complete-step` обязательно используй `--from-file`.
- Временные JSON для `--from-file` по умолчанию пиши в `.madspec/.tmp/`: при успешной команде CLI удалит такой файл автоматически, а при ошибке сохранит его для правки и повторного запуска. Для внешних путей auto-cleanup не предполагается.
- Для multi-agent, automation и любых повторных попыток после чтения контекста передавай `--expected-revision`; если команда вернула `kind="conflict"`, сначала перечитай состояние через `retrieve` или `explain`, получи свежий `runtime_revision` и только потом повторяй запись. Если команда вернула `kind="scope_busy"`, сначала устрани contention по hot scope, а не перечитывай контекст по инерции.
- Для `mvp.design` источником утвержденного состояния служат память и связанные дизайн-артефакты; историю чата не считай источником истины.
- Для `mvp.implement` и `feature.implement` рабочий цикл идет через `retrieve -> start-step -> checkpoint-step -> complete-step`.
- Если несколько субагентов работают над одной задачей, сначала убедись, что в `.madspec/config.json` включен `parallelRuntime.phase2Enabled=true`, затем создай `task`, отдельные `work-item` с непересекающимися scopes и только после `claim` публикуй proposals от имени соответствующего session key. Direct runtime write для claimed session считай ошибкой протокола, а не shortcut.
- Если работа одного subagent должна ждать другой кусок внутри того же task, зафиксируй это через `--depends-on-work-item`, а не только через текстовое описание в задаче.
- Для `review` и `security` сначала проверяй статус соответствующих gate-проверок, затем формулируй выводы.

## Карта чтения

Открывай только нужный раздел, чтобы не загружать в контекст лишнее:

- [Обзор модели MADSpec](references/overview.md) — как устроены ветки, канонические состояния, производные представления и системные слои
- [Карта команд](references/commands.md) — слеш-команды и CLI-команды по подсистемам
- [Плейбуки по стадиям](references/stage-playbooks.md) — как работать с `mvp.*`, `feature.*`, `review`, `security` и связанными артефактами
- [Рабочие инварианты](references/invariants.md) — обязательный порядок действий, запреты на ручное редактирование и правила эскалации
- [Траблшутинг](references/troubleshooting.md) — что делать, если пропали артефакты, расходятся представления, ломается шаг или упираемся в лимиты Windows

## Быстрый выбор следующего чтения

- Если нужно понять, что считать источником истины, читай [references/overview.md](references/overview.md).
- Если пользователь просит конкретную команду или спрашивает, что есть в CLI, читай [references/commands.md](references/commands.md).
- Если работа идет внутри конкретной стадии процесса, читай [references/stage-playbooks.md](references/stage-playbooks.md).
- Если собираешься менять состояние памяти, правил, gates, change-пакета или профиля субагентов, сначала открой [references/invariants.md](references/invariants.md).
- Если что-то выглядит сломанным или неполным, сначала открой [references/troubleshooting.md](references/troubleshooting.md).

## Граница навыка

- Это операторский слой, а не полная документация продукта.
- Если меняется сам MADSpec CLI, сверяйся с `README.md`, `AGENTS.md`, `docs/cli/` и шаблонами команд.
- Если нужно проектировать интерфейс, этот навык не заменяет `frontend-design`.
