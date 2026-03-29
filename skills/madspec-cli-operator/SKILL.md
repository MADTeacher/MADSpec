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
4. Для текущей стадии восстанови контекст через `madspec memory retrieve --stage <stage> --session-key <key> --toon-output`, если ответ будет читать агент; если отдельный локальный контекст сеанса не нужен, используй значение по умолчанию `active`. `--json-output` оставляй для машинной интеграции и случаев, когда нужен именно JSON-контракт.
5. Если нужно понять различие между локальным фокусом сеанса и общим состоянием процесса в ветке, используй `madspec memory explain --stage <stage> --session-key <key> --json-output`.
6. Если дальше будет команда, меняющая состояние, возьми из `retrieve` текущее значение `runtime_revision` и, когда сценарий чувствителен к параллельным записям, передай его обратно через `--expected-revision`.
7. Если нужно понять блокировки перехода, сначала смотри `policy_context` и `gate status`, а не редактируй файлы вручную.
8. Перед изменением состояния используй канонические команды CLI, а не прямое редактирование `.json`, `.jsonl` и производных `.md`.
9. Если обязательного входа не хватает и его нельзя восстановить из репозитория, только тогда эскалируй вопрос пользователю.

## Что помнить всегда

- MADSpec привязывает рабочие артефакты к ветке в `.madspec/<branch>/`.
- Канонические данные и производные представления нельзя путать: Markdown-контекст часто является только проекцией.
- Каноническое состояние ветки теперь хранится в `SQLite`: `progress`, снимки стадий, локальное состояние сеансов и потоки записей сначала коммитятся туда, а файлы ветки остаются производными проекциями. Файл `active-session.json` поддерживается только как проекция для session `active`.
- Параллельный режим теперь разделен явно: базовый конфиг проекта содержит `parallelRuntime.phase1Enabled=true` и `parallelRuntime.phase2Enabled=true`, то есть полный `Phase 2` включен по умолчанию. Ключ `parallelRuntime.phase2Enabled` теперь служит ручным выключателем coordinator-flow, а отсутствие блока `parallelRuntime` трактуй как тот же дефолт с включенным `Phase 2`.
- Инициализация проекта теперь также фиксирует проектную конфигурацию памяти в `.madspec/config.json` через блок `memory.embeddings`. Если `madspec init` запускается без `--memory-provider/--memory-model/--memory-download-policy` и без TTY, считай это совместимым неинтерактивным режимом с `provider=hash`, `model=null`, `downloadPolicy=none`.
- Для пути с локальной семантической моделью `memory.embeddings` теперь может запускать реальную загрузку модели во время `madspec init`, если выбран `downloadPolicy=on-init`. Актуальное состояние семантического чтения проверяй не только через `madspec memory status` или `madspec memory db-status`, но прежде всего через `madspec memory search` и `madspec memory retrieve`: они возвращают `semantic_runtime`, где отдельно показаны выбранная конфигурация `memory.embeddings`, готовность модели, активное пространство индекса и итог `semantic_outcome`.
- Если `search` или `retrieve` возвращают `kind="embedding_provider_error"`, не трактуй это как допустимую деградацию до `hash`. Сначала разберись с загрузкой модели, `reindex` активного пространства индекса или конфигом `memory.embeddings`.
- Если пользователь поменял `memory.embeddings.provider`, `memory.embeddings.model` или `memory.embeddings.revision`, не считай новый индекс готовым автоматически. Сначала проверь `madspec memory status`, `madspec memory db-status` или `madspec memory doctor`, при необходимости подготовь кэш через `madspec memory bootstrap-model`, и только потом считай, требуется ли `madspec memory reindex`.
- `madspec memory doctor` теперь отдельно возвращает semantic diagnostics: top-level `semantic_integrity` в JSON, semantic-specific `checks` и краткую semantic summary в `observability`.
- Для semantic diagnostics считай `error` признаком реальной рассинхронизации каноники, branch projections или active semantic chunks. `warn` по коду `semantic_inactive_namespace_residue` трактуй как остаточный мусор в неактивном namespace, а не как поломку active semantic path.
- Если `doctor` показывает semantic issue про branch/project record shape или projection drift, сначала выбирай `madspec memory semantic prune|replace`; если проблема указывает на active namespace mismatch или orphan chunks, готовь `madspec memory reindex`; если проблема сводится только к residue в неактивных пространствах, используй `madspec memory gc vector-namespaces`.
- Если для локальной семантической модели выбран `downloadPolicy=none`, не ожидай автоматической загрузки кэша. В этом режиме отсутствие или повреждение локального кэша проекта считается штатной ошибкой конфигурации, а не поводом для неявной деградации поведения.
- Для многосубагентной координации поверх локального состояния сеанса теперь есть канонические `task` и `work-item`, но этот протокол относится к `Phase 2`. Их жизненный цикл ведется командами `madspec memory tasks ...` и `madspec memory work-items ...`, а `claim` расширяет данные сеанса полями `task_id`, `work_item_id`, `subagent_id`.
- Координационный слой теперь также хранит явные зависимости между `work-item` и подсказки для планировщика роли (`default_stage`, `execution_mode_hint`, `subagent_dependencies`). Эти данные используются для объяснения готовности, а не для автоматического запуска субагентов.
- Для claimed `work-item` команды прямой записи больше не считаются допустимым способом изменения состояния, если `parallelRuntime.phase2Enabled=true`: такой session должен использовать `madspec memory proposals publish ...`, затем `madspec memory proposals apply --proposal-id ...`.
- Если нужно понять, почему `work-item` нельзя `claim/apply` прямо сейчас, используй `madspec memory coordinator explain --work-item-id ...` или `--session-key ...`, но помни, что эта линия диагностики недоступна только если проект явно отключил `Phase 2`.
- Каноническое состояние ветки имеет общую ревизию `runtime_revision`; успешные команды записи возвращают `runtime_revision_before` и `runtime_revision_after`, а при устаревшей записи возможен структурированный `conflict`.
- Для самых горячих путей записи MADSpec использует ограниченную аренду записи. Если команда вернула `kind="scope_busy"`, это значит, что другой процесс временно держит ту же горячую область; сначала дождись освобождения аренды или истечения TTL, а уже потом повторяй запись.
- Для сценария Phase 1 “реализация текущего шага и параллельное планирование следующего” совместимыми считаются `register-step(step-02)` вместе с `start-step(step-01)`, `checkpoint-step(step-01)` или `complete-step(step-01)`. Повторная запись в тот же step/catalog должна трактоваться как `conflict` или `scope_busy`, а не как неявное перетирание состояния.
- Команды, привязанные к стадии, материализуют только артефакты текущей стадии; отсутствие несвязанных производных артефактов не считай признаком поломки, пока соответствующая стадия еще не запускалась.
- Для `mvp.plan` и `feature.plan` предпочитай минимально достаточное число шагов: легкую задачу планируй одним полным шагом, если нет реальной причины делить её дальше.
- Не превращай сам процесс планирования в длинный обязательный ритуал: базовый путь для простого проекта — `retrieve`, при необходимости один `capture`, затем `next-step`, `register-step` и один финальный `checkpoint`.
- `p1/p2/p3` обозначают приоритеты и покрытие функций, а не обязательное число шагов и не правило "по одному шагу на каждую функцию".
- Если в ветке существует `deployment.md`, учитывай его как официальный производный артефакт этапа `deploy` при планировании, review и security.
- `madspec.deploy` можно запускать как рекомендуемый этап перед `mvp.plan`, а также отдельно позже, когда схема развертывания уточнилась ближе к релизу.
- Для `memory capture`, `memory checkpoint`, `memory register-step`, `memory start-step`, `memory checkpoint-step` и `memory complete-step` обязательно используй `--from-file`.
- Для `madspec memory snapshots replace` и `madspec memory snapshots prune` тоже используй `--from-file`: это канонический путь очистки для снимков стадий без ручного редактирования `.madspec/<branch>/memory/stages/*.json`.
- Для `madspec memory semantic replace` и `madspec memory semantic prune` тоже используй `--from-file`: это канонический путь очистки для semantic knowledge со статусами `validated`, `obsolete`, `conflicted` и project-level знаний без ручного редактирования `semantic/*.jsonl` или `SQLite`.
- Временные JSON для `--from-file` по умолчанию пиши в `.madspec/.tmp/`: при успешной команде CLI удалит такой файл автоматически, а при ошибке сохранит его для правки и повторного запуска. Для внешних путей автоматическая очистка не предполагается.
- Для очистки дубликатов или полной замены снимка стадии действуй так: сначала прочитай полный артефакт стадии через `retrieve --full-artifact`, затем подготовь `.madspec/.tmp/<stage>-prune.json` или `<stage>-replace.json`, после этого выполни `madspec memory snapshots prune|replace --expected-revision <runtime_revision>` и при итоговой проверке при необходимости запусти `madspec memory consolidate` и `madspec memory validate`.
- Если session привязан к claimed `work-item` в `Phase 2`, `snapshots prune|replace` сейчас не имеют пути записи через `proposals`. В таком случае используй unclaimed session или сначала освободи claim.
- Для cleanup semantic knowledge сначала используй `madspec memory semantic retrieve --scope branch|project --json-output`, затем подготовь `.madspec/.tmp/semantic-prune.json` или `semantic-replace.json` и выполни `madspec memory semantic prune|replace --expected-revision <runtime_revision>`.
- Для `scope=project` не передавай `--branch`: этот путь работает с project-level знаниями в `records` с branch `__project__`.
- Для `scope=project` помни, что `retrieve/search` теперь работают строго по project-level knowledge из `__project__` и не подмешивают branch-level semantic records.
- Если branch-scoped `semantic prune|replace` запущен из claimed session `Phase 2`, команда сама публикует `semantic_cleanup` proposal вместо прямой записи. После этого отдельно выполни `madspec memory proposals apply --proposal-id <id>`. Для `scope=project` этот guardrail не применяется.
- После semantic cleanup active namespace очищается точечно для удалённых records, поэтому отдельный `madspec memory reindex` не обязателен; он нужен только для полной пересборки активного пространства индекса.
- Для residue в неактивных пространствах сначала смотри `madspec memory gc vector-namespaces --dry-run`, а затем удаляй их через `madspec memory gc vector-namespaces`; полный `reindex` для этого не обязателен.
- Для многосубагентной работы, автоматизаций и любых повторных попыток после чтения контекста передавай `--expected-revision`; если команда вернула `kind="conflict"`, сначала перечитай состояние через `retrieve` или `explain`, получи свежий `runtime_revision` и только потом повторяй запись. Если команда вернула `kind="scope_busy"`, сначала устрани конкуренцию за горячую область, а не перечитывай контекст по инерции.
- Для `mvp.design` источником утвержденного состояния служат память и связанные дизайн-артефакты; историю чата не считай источником истины.
- Для `mvp.design` считай `ui-prototype/index.html` реальной точкой входа приложения: это не обзорная страница, а входной экран primary flow.
- Для `mvp.implement` и `feature.implement` рабочий цикл идет через `retrieve -> start-step -> checkpoint-step -> complete-step`.
- Если несколько субагентов работают над одной задачей, сначала проверь, что проект не отключил `parallelRuntime.phase2Enabled`, затем создай `task`, отдельные `work-item` с непересекающимися областями и только после `claim` публикуй `proposals` от имени соответствующего session key. Прямую запись в каноническое состояние для claimed session считай ошибкой протокола, а не допустимым сокращением пути.
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
- Если задача связана с `madspec init`, `.madspec/config.json` или проектным выбором провайдера памяти, сначала проверь актуальный контракт `memory.embeddings` и не подменяй его рассуждениями про текущий векторный слой.

## Граница навыка

- Это операторский слой, а не полная документация продукта.
- Если меняется сам MADSpec CLI, сверяйся с `README.md`, `AGENTS.md`, `docs/cli/` и шаблонами команд.
- Если нужно проектировать интерфейс, этот навык не заменяет `frontend-design`.
