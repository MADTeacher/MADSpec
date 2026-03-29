# Дорожная карта развития семантического слоя в MADSpec Memory

> Статус: архивный документ. Основной цикл работ по семантическому слою закрыт; файл сохранён как исторический roadmap и не считается текущим execution-планом.

Этот документ фиксирует следующий этап развития семантического слоя после уже реализованных команд очистки:

- `madspec memory semantic retrieve`
- `madspec memory semantic prune`
- `madspec memory semantic replace`

На момент действия этого roadmap базовая очистка подтверждённых семантических знаний уже существует и покрывает:

- знания ветки в `semantic/facts.jsonl`, `semantic/decisions.jsonl`, `semantic/contracts.jsonl`;
- знания уровня проекта в `records` с branch `__project__`;
- очистку активного векторного пространства имён для удалённых semantic records;
- проверку ревизии перед записью;
- защитное ограничение для ветки в случае claimed session без proposal flow.

Ниже зафиксированы три следующих эпика. Документ специально разбит так, чтобы каждый эпик можно было отдать отдельному агенту как самостоятельный пакет работ с понятными границами, ожидаемыми изменениями и критериями приёмки.

## 1. Цель и не-цели

### Цель

MADSpec должен безопасно поддерживать семантический слой как полноценный управляемый слой знаний, а не только как набор validated records с базовой очисткой. Для этого нужны:

- поддерживаемый путь очистки для claimed Phase 2 branch sessions;
- полноценная диагностика целостности семантического слоя и знаний уровня проекта;
- управляемый жизненный цикл векторных пространств имён и служебных semantic streams;
- более строгие и понятные контракты чтения и поиска для знаний уровня проекта.

### Не-цели для этого roadmap

В рамках этих трёх эпиков не планируются:

- удаление по смысловой близости или эвристическое схлопывание "похожих" записей;
- автоматическое semantic merge двух несовместимых knowledge records;
- замена текущей модели exact selector в `semantic prune`;
- полный редизайн `memory search` за пределами semantic scope и namespace lifecycle;
- перенос всех merge/history потоков в новый storage format.

## 2. Текущее состояние

### Что уже есть

Сейчас семантический слой уже умеет:

- читать полный semantic artifact через `madspec memory semantic retrieve`;
- выполнять `prune` и `replace` для validated semantic knowledge;
- работать как по ветке, так и по project scope;
- удалять связанные записи из `records`, `records_fts` и `index_jobs`;
- очищать активное векторное пространство имён по `source_type=record` и `source_id`;
- пересобирать branch projections после branch-scoped cleanup.

### Что остаётся незакрытым

После внедрения базового cleanup API остаются четыре системных зазора:

- branch-scoped cleanup для claimed session блокируется guardrail и не имеет proposal-based apply path;
- `doctor` не умеет диагностировать нарушения целостности семантического слоя как отдельный класс проблем;
- неактивные векторные пространства имён не очищаются и продолжают хранить производный мусор;
- cleanup работает только для validated knowledge и не покрывает соседние semantic streams и UX чтения на project scope.

Именно эти зазоры закрывают три эпика ниже.

## 3. Целевое направление

После завершения всех трёх эпиков семантический слой должен выглядеть так:

- branch semantic cleanup доступен как direct write для обычных сессий и как proposal-based apply path для claimed Phase 2 session;
- `doctor` и смежные диагностические команды умеют явно находить semantic inconsistencies и объяснять их источник;
- активное и неактивные векторные пространства имён имеют понятный жизненный цикл и поддерживаемую очистку;
- operator может отдельно управлять validated knowledge, project-level знаниями и служебными semantic streams;
- search и retrieve для project scope дают предсказуемый и узко определённый результат без размывания branch-level контекстом.

## 4. Порядок исполнения

Рекомендуемый порядок передачи эпиков агентам:

1. `Epic 1` — сначала закрыть governance gap для claimed session.
2. `Epic 2` — затем добавить диагностику и наблюдаемость.
3. `Epic 3` — после этого расширить жизненный цикл семантического хранилища и область cleanup.

`Epic 2` можно начинать частично параллельно с концом `Epic 1`, но итоговую интеграцию лучше делать после стабилизации proposal path.

## 5. Epic Roadmap

### Epic 1 — Proposal Flow для semantic cleanup в Phase 2

**Зачем нужен этот эпик**

Сейчас branch-scoped `semantic prune/replace` работает только как direct write path. Если ветка находится в claimed Phase 2 session, команда блокируется guardrail. Это делает semantic cleanup неполным: оператор может увидеть проблему, но не может исправить её штатно в сценарии, где общий runtime уже переведён на proposal discipline.

**Цель эпика**

Добавить proposal-based путь для branch-scoped semantic cleanup без обхода существующих правил владения и commit discipline.

**Объём работ**

- расширить application-layer semantic cleanup так, чтобы он умел формировать proposal вместо прямой записи для claimed session;
- определить тип proposal для semantic cleanup и canonical apply path;
- обеспечить replay тех же exact cleanup-операций при применении proposal;
- сохранить текущий direct path для unclaimed session без изменения UX;
- добавить явное объяснение в CLI output, когда операция ушла в proposal flow, а не выполнилась напрямую.

**Ожидаемые изменения в коде**

- `src/madspec_cli/memory/application/semantic_cleanup.py`
- proposal/apply слой memory runtime
- `src/madspec_cli/memory/cli/semantic.py`
- связанные docs по proposal workflow и operator flow

**Что агент должен выдать**

- поддерживаемый proposal path для `madspec memory semantic prune` и `replace` на ветке;
- одинаковое поведение cleanup между direct и proposal apply;
- понятный CLI результат с идентификатором proposal и статусом apply path;
- обновлённую документацию и skill для operator workflow.

**Критерии приёмки**

- claimed branch session больше не получает тупиковый отказ для semantic cleanup;
- cleanup-операция может быть зафиксирована как proposal и затем применена штатным путём;
- direct branch session продолжает работать без регрессии;
- project scope по-прежнему не затягивается в proposal flow;
- полный набор связанных тестов зелёный.

**Минимальный набор тестов**

- e2e: claimed session вызывает `semantic prune` и получает proposal вместо direct write;
- e2e: apply proposal реально удаляет semantic record и обновляет projections;
- regression: unclaimed branch session по-прежнему делает direct write;
- regression: `scope=project` не требует proposal flow.

**Зависимости и риски**

- зависит от текущего proposal runtime и его ограничений по типам операций;
- главный риск — расхождение поведения между direct cleanup и proposal apply;
- нельзя дублировать бизнес-логику prune/replace в двух независимых ветках кода.

### Epic 2 — Semantic Integrity Doctor и Observability

**Зачем нужен этот эпик**

После появления cleanup API оператору всё ещё трудно понять, что именно сломано в семантическом слое и нужен ли cleanup вообще. Сейчас нет отдельной диагностики для dangling vector chunks, orphan records, расхождения между canonical records и materialized semantic projections и следов старых namespace.

**Цель эпика**

Сделать целостность семантического слоя проверяемой и объяснимой через стандартные диагностические команды и структурированный вывод.

**Объём работ**

- расширить `doctor` и связанные diagnostic paths проверками семантического слоя;
- добавить отдельные классы проблем: orphan record, orphan chunk, stale projection, stale project knowledge, inactive namespace residue;
- вернуть структурированный результат, пригодный для автоматического разбора и operator troubleshooting;
- связать диагностический вывод с рекомендуемыми действиями: `semantic prune`, `semantic replace`, `reindex`, namespace cleanup;
- улучшить наблюдаемость cleanup-операций в timeline/history.

**Ожидаемые изменения в коде**

- `src/madspec_cli/memory/application/doctor.py`
- retrieval/store/vector diagnostics
- возможно, `docs/cli/memory.md` и troubleshooting docs
- `skills/madspec-cli-operator/SKILL.md`

**Что агент должен выдать**

- новый диагностический раздел по целостности семантического слоя;
- машиночитаемые коды проблем;
- operator-friendly объяснение причин и безопасных next steps;
- документацию с примерами типовых поломок.

**Критерии приёмки**

- `doctor` явно показывает semantic inconsistencies как отдельный класс проблем;
- для branch и project scope можно увидеть, что именно рассинхронизировано;
- диагностический вывод различает проблему records, projections и vector namespace;
- cleanup и `reindex` после исправления убирают соответствующие предупреждения;
- регрессии в существующих диагностических командах отсутствуют.

**Минимальный набор тестов**

- unit/integration: orphan branch semantic record без projection;
- unit/integration: удалённый record с оставшимся active chunk;
- unit/integration: stale project-level knowledge в `__project__`;
- regression: healthy branch/project state не даёт ложных ошибок.

**Зависимости и риски**

- желательно опираться на уже стабилизированный cleanup flow из `Epic 1`, но большая часть диагностики может делаться независимо;
- главный риск — слишком шумная диагностика, которая мешает operator UX;
- нужно строго разделять warning и error, чтобы не блокировать рабочие сценарии без причины.

### Epic 3 — Lifecycle Vector Namespace и расширение semantic cleanup

**Зачем нужен этот эпик**

Даже после branch/project cleanup и диагностики остаётся технический долг по жизненному циклу семантического хранилища. Неактивные пространства имён копят производный мусор, а cleanup пока работает только с validated knowledge и не покрывает соседние semantic streams. Кроме того, project-scope чтение и поиск нужно сделать строже и предсказуемее.

**Цель эпика**

Завершить первую полноценную итерацию управления семантическим слоем: управляемый lifecycle namespace, cleanup соседних semantic streams и строгий UX для project-level search/retrieve.

**Объём работ**

- добавить поддерживаемую очистку или полную пересборку inactive vector namespace;
- определить policy хранения старых namespace: удаление, архивация или явный garbage-collect;
- расширить cleanup API на соседние semantic streams, если они относятся к semantic storage management;
- уточнить `search --scope project`, чтобы выдача была ограничена project-level знаниями без branch leakage;
- при необходимости добавить отдельные команды или флаги для namespace maintenance.

**Ожидаемые изменения в коде**

- `src/madspec_cli/memory/shared/system_store/vector.py`
- `src/madspec_cli/memory/shared/system_store/layout.py`
- `src/madspec_cli/memory/shared/system_store/retrieval.py`
- semantic cleanup/storage layer
- документация по operator runbook и lifecycle namespace

**Что агент должен выдать**

- поддерживаемый жизненный цикл для inactive namespace;
- cleanup path или maintenance path для дополнительных semantic streams;
- более строгий project-level search contract;
- обновлённый runbook для operator и maintainers.

**Критерии приёмки**

- удалённые или заменённые semantic records не продолжают всплывать из старых namespace в поддерживаемом рабочем сценарии;
- project-level search и retrieve не смешивают веточные знания без явного запроса;
- namespace cleanup не ломает active retrieval path;
- документация явно объясняет, когда нужен `reindex`, а когда достаточно targeted cleanup;
- тесты покрывают как branch, так и project scope.

**Минимальный набор тестов**

- integration: cleanup inactive namespace или rebuild-all workflow;
- integration: удалённый project record больше не находится в project search;
- integration: дополнительные semantic streams очищаются только в разрешённых пределах;
- regression: active namespace и обычный `memory search` не деградируют.

**Зависимости и риски**

- зависит от понимания текущего storage contract и допустимой стоимости `reindex`;
- главный риск — случайно превратить maintenance-команды в разрушительные операции без достаточного guardrail;
- отдельное внимание нужно уделить backward compatibility для уже существующих namespace на диске.

## 6. Рекомендации по передаче эпиков агентам

Чтобы агентам было проще исполнять работу без лишней координации, передавать эпики лучше так:

- одному агенту — только один эпик;
- вместе с эпиком передавать этот roadmap как источник архитектурного контракта;
- отдельно указывать, какие тесты нужно считать обязательными именно для этого эпика;
- не смешивать в одном агентском заходе `Epic 1` и `Epic 3`, потому что оба меняют mutation/storage path и могут конфликтовать по write scope.

Рекомендуемая последовательность handoff:

1. сначала `Epic 1`;
2. после стабилизации proposal path — `Epic 2`;
3. затем `Epic 3` как storage hardening и UX tightening.
