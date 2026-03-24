# Configurable Local Embeddings Roadmap for MADSpec Memory

Этот документ служит одновременно дорожной картой и архитектурным решением уровня Epic 0 для перехода MADSpec от текущего hash-based semantic layer к конфигурируемой модели памяти с выбором embedding provider на уровне проекта.

До завершения Epics 1–6 именно этот файл фиксирует baseline по configuration contract, provider model, bootstrap strategy, index versioning, rollout order и compatibility policy.

## 1. Goal and Non-Goals

### Goal

MADSpec должен безопасно поддерживать:

- выбор режима памяти на уровне проекта через `.madspec/config.json`;
- сохранение текущего hash-based режима как совместимого дефолтного fallback;
- подключение локального dense embedding provider без внешнего API-провайдера;
- выбор одной из нескольких заранее поддержанных моделей при `madspec init`;
- автоматическую загрузку выбранной модели с Hugging Face в локальный проектный cache;
- полностью локальный inference после bootstrap, без отправки проектных данных на сторону;
- воспроизводимую индексацию и поиск по смыслу для русского и mixed RU/EN контента;
- совместимость с текущим CLI UX и способом установки через `uv tool install ... --from git+...`.

### Non-goals for Phase 1

На первой фазе не делаем:

- поддержку произвольных пользовательских Hugging Face моделей без внутреннего registry;
- удаленные embedding API-провайдеры;
- обязательный GPU runtime;
- мгновенную миграцию уже существующих индексов без `reindex`;
- reranker-layer и cross-encoder в базовом rollout;
- автоопределение лучшей модели по языку проекта;
- глобальную замену exact/FTS retrieval на dense-only retrieval.

### Success criteria

Считаем задачу успешной, когда выполняются все условия:

- новый проект может выбрать `hash` или `local-hf-onnx` прямо в `madspec init`;
- конфиг проекта хранит provider/model policy в `.madspec/config.json`;
- при выборе dense-модели MADSpec может скачать веса и запустить локальный inference;
- после `reindex` поиск действительно использует dense embeddings, а не hash fallback;
- существующие проекты продолжают работать без ручной миграции в режиме `hash`;
- смена модели приводит к явному пересозданию/переключению индекса, а не к silent corruption;
- в закрытом контуре модель можно предзагрузить и использовать полностью офлайн;
- пользователь всегда понимает, какой provider реально активен.

## 2. Current-State Diagnosis

### Текущее поведение

В текущей реализации memory semantic layer уже существует, но фактически работает через hash-based embedding provider:

- `EmbeddingProvider` строит вектор фиксированной размерности из токенов через hashing;
- текущая размерность задается как `DEFAULT_EMBEDDING_DIMENSION = 64`;
- `VectorMemoryIndex` принимает provider, но по умолчанию создает встроенный hash provider;
- chunk indexing уже существует и работает через `index_jobs`;
- `memory retrieve` и `memory search` уже умеют semantic lane и опцию `--disable-semantic`;
- semantic lane встроен в hybrid retrieval, но не опирается на dense semantic embeddings.

### Текущая конфигурация проекта

Сейчас `.madspec/config.json` хранит только базовые project/runtime настройки:

- `currentBranch`;
- `version`;
- `agentsSchemaVersion`;
- `parallelRuntime`;
- `agentEnvironment` при наличии.

Это означает, что project-level contract для memory provider пока отсутствует.

### Текущий init flow

`madspec init` уже содержит естественную точку расширения:

- есть интерактивный выбор AI-среды;
- есть отдельный шаг `Create MADSpec config`;
- `create_madspec_config(...)` уже собирает `.madspec/config.json`;
- после конфигурации выполняются `ensure_memory_layout(...)`, `consolidate_branch_memory(...)` и связанная инициализация.

Следовательно, добавить memory provider selection в `init` можно без отдельной команды и без ломки текущего UX.

### Текущая модель поставки CLI

Сейчас CLI устанавливается как единый инструмент через `uv tool install madspec-cli --from git+...`, а `pyproject.toml` содержит только базовые зависимости. Следовательно:

- решение не должно опираться на новый обязательный install flow через другой package manager;
- лучше избегать взрывного роста зависимостей и веса рантайма;
- bootstrap моделей должен быть отделен от bootstrap самого CLI.

### Основное архитектурное ограничение

Главная проблема не в retrieval orchestration и не в index storage. Главная проблема в том, что:

- semantic lane уже есть;
- provider abstraction уже есть;
- index jobs уже есть;
- но current provider не является dense semantic model.

Следовательно, migration path должен менять прежде всего provider layer, config contract и lifecycle модели, а не ломать всю retrieval architecture.

## 3. Target Architecture

### Architectural baseline

Целевая модель должна разделять:

- project-level config выбора embedding provider;
- runtime registry поддерживаемых моделей;
- bootstrap/download lifecycle модели;
- local inference provider;
- versioned vector index per provider/model/dimension/revision;
- совместимый hash fallback.

### Canonical configuration contract

В `.madspec/config.json` добавляется новый раздел:

```json
{
  "memory": {
    "embeddings": {
      "provider": "hash",
      "model": null,
      "downloadPolicy": "on-init",
      "cacheDir": ".madspec/system/models",
      "revision": null
    }
  }
}
```

### Configuration rules

- `provider = "hash"` означает текущий режим без model bootstrap;
- `provider = "local-hf-onnx"` означает локальный dense provider;
- `model` содержит stable internal model key, а не произвольный repo id;
- `downloadPolicy` контролирует момент bootstrap;
- `cacheDir` задает project-local каталог моделей;
- `revision` используется для pinned reproducible download.

### Supported model registry

Модели не должны описываться целиком в конфиге. Вместо этого MADSpec должен иметь встроенный registry вида:

```json
{
  "multilingual-e5-small": {
    "providerKind": "local-hf-onnx",
    "hfRepoId": "intfloat/multilingual-e5-small",
    "dimension": 384,
    "languages": ["ru", "en", "multilingual"],
    "queryPrefix": "query: ",
    "passagePrefix": "passage: ",
    "approxDownloadSizeMb": 470,
    "recommended": true,
    "status": "ga"
  },
  "bge-m3": {
    "providerKind": "local-hf-onnx",
    "hfRepoId": "BAAI/bge-m3",
    "dimension": 1024,
    "languages": ["ru", "en", "multilingual"],
    "queryPrefix": "",
    "passagePrefix": "",
    "approxDownloadSizeMb": 2300,
    "recommended": false,
    "status": "beta"
  }
}
```

### Контракт полей записи registry

Ключ верхнего уровня объекта registry — **stable internal model key** (совпадает с полем `model` в конфиге). Значение — объект со следующими полями:

| Поле | Тип | Назначение |
|------|-----|------------|
| `providerKind` | string | Должен совпадать с поддерживаемым видом провайдера (например `local-hf-onnx`). |
| `hfRepoId` | string | Идентификатор репозитория на Hugging Face для загрузки весов. |
| `dimension` | integer | Размерность выходного embedding-вектора. |
| `languages` | array of string | Ожидаемые языки контента (для UX и документации). |
| `queryPrefix` | string | Префикс текста запроса перед инференсом (может быть пустой строкой). |
| `passagePrefix` | string | Префикс текста фрагмента (passage) перед инференсом (может быть пустой строкой). |
| `approxDownloadSizeMb` | number | Ориентировочный объём загрузки для подсказок в `init` и диагностике. |
| `recommended` | boolean | Рекомендуемая модель для новых проектов (UX). |
| `status` | string | Стадия поддержки записи (например `ga`, `beta`); валидные значения задаёт CLI. |

Произвольные поля в конфиге проекта для описания модели не допускаются: весь провайдерский контракт для известных моделей живёт только в registry.

### Why registry-first model selection

Registry-first подход нужен по нескольким причинам:

- init UX показывает понятные варианты без произвольного ввода;
- можно заранее фиксировать dimension, tokenizer assumptions и prompt format;
- проще проводить security review;
- проще контролировать качество и поддерживаемость;
- проще встраивать future migrations и compatibility checks.

### Local inference model

Целевая runtime-модель:

- пользовательские project данные никогда не отправляются во внешний embedding API;
- Hugging Face используется только как source weights при bootstrap;
- inference выполняется локально на CPU;
- после скачивания модель грузится только из локального пути;
- при офлайн-режиме runtime отказывается от сети и требует локально доступные файлы.

### Retrieval model

Hybrid retrieval сохраняется.

Целевая схема поиска:

- `exact` lane — для точных id, step ids, contracts, status markers;
- `lexical` lane — для SQLite/FTS recall;
- `semantic` lane — для dense embeddings;
- `merge` / ranking layer — для финального объединения результатов.

Dense provider не заменяет exact и lexical lanes, а становится корректной реализацией semantic lane.

### Index versioning model

Vector index должен версионироваться как минимум по:

- provider kind;
- model key;
- revision;
- embedding dimension.

Пример:

```text
.madspec/system/memory/lancedb/
  hash/default/64/
  local-hf-onnx/multilingual-e5-small/<revision>/384/
  local-hf-onnx/bge-m3/<revision>/1024/
```

Сегмент `default` в пути `hash/default/64/` — **фиксированный namespace** для провайдера `hash`: отдельного model key у hash-режима нет, используется один согласованный профиль (размерность задаётся реализацией CLI, в примере `64`). Это не пользовательский идентификатор и не подлежит подстановке из конфига.

Это исключает silent corruption при смене модели и позволяет параллельно хранить старый и новый индекс.

### Канонический layout каталога моделей (`cacheDir`)

Пути ниже задаются относительно корня проекта; `<cacheDir>` — значение из `memory.embeddings.cacheDir` после нормализации (по умолчанию `.madspec/system/models`).

- Базовый каталог артефактов одной модели: `<cacheDir>/<model_key>/`, где `<model_key>` — stable internal key из registry.
- Если в конфиге задан непустой `revision` (pin на конкретный снимок весов), файлы этой закреплённой ревизии хранятся в `<cacheDir>/<model_key>/<revision>/` (строка revision должна быть безопасна для имени каталога; для Hugging Face обычно используется commit hash или идентификатор revision API).
- Если `revision` в конфиге равен `null`, runtime выбирает одну согласованную «текущую» выкладку внутри `<cacheDir>/<model_key>/` по правилам bootstrap (без смешивания разных ревизий в одном namespace).

Индекс векторов (дерево `lancedb` выше) и каталог весов ONNX — **разные деревья**: смена только файлов модели не должна перезаписывать путь индекса без согласования с `provider` / `model` / `revision` / `dimension`.

### Bootstrap model lifecycle

Поддерживаются два режима:

- `on-init` — скачать модель сразу в `madspec init`;
- `on-first-use` — скачать при первой реальной необходимости (`reindex`, `search`, `retrieve` с semantic lane).

Для production UX рекомендованный режим для dense provider — `on-init`.

### Failure policy

Если dense provider выбран, но модель недоступна:

- MADSpec не должен silently откатываться на `hash`;
- команда должна завершаться понятной ошибкой;
- пользователь должен увидеть, какой provider выбран и почему он не активирован;
- допустимый fallback — только явное изменение config или осознанное действие пользователя.

## 4. Recommended Product Default

### Phase-1 default recommendation

Для первого полноценного rollout рекомендуется:

- оставить `hash` как compatibility default для существующих проектов;
- сделать `multilingual-e5-small` рекомендуемой dense-моделью для новых проектов;
- поддержать `bge-m3` как advanced option;
- не добавлять третью модель на первом этапе.

### Why `multilingual-e5-small`

Эта модель лучше всего подходит как первый practical default, потому что:

- поддерживает русский и multilingual search;
- имеет умеренную размерность `384`;
- заметно легче тяжелых multilingual long-context alternatives;
- имеет понятный retrieval contract с `query:` / `passage:`;
- хорошо подходит для project memory, где важны заметки, решения, артефакты и короткие/средние chunks.

### Why not make `bge-m3` the default yet

`bge-m3` полезен как future advanced profile, но на первом rollout несет больше рисков:

- намного тяжелее при bootstrap;
- заметно тяжелее для CPU inference;
- требует более осторожного sizing и operational expectations;
- усложняет first-time UX без критичной необходимости для большинства проектов.

## 5. Phase Breakdown

### Phase 0: ADR and Contract Lock

Цель фазы:

- зафиксировать configuration contract;
- зафиксировать model registry format;
- зафиксировать failure policy;
- зафиксировать index versioning strategy.

Результат фазы:

- нет открытых решений по структуре `.madspec/config.json`;
- нет открытых решений по project-local cache layout;
- все следующие изменения могут идти без архитектурных споров о базовом направлении.

### Phase 1: Project Config and Init UX

Цель фазы:

- ввести `memory.embeddings` в config;
- встроить выбор provider/model в `madspec init`;
- показать пользователю размер модели до скачивания;
- добавить выбор bootstrap policy.

Результат фазы:

- инициализация проекта сразу формирует правильную memory strategy;
- конфиг становится source of truth для provider selection.

### Phase 2: Provider Abstraction and Bootstrap Runtime

Цель фазы:

- превратить текущий provider в явно именованный `HashEmbeddingProvider`;
- добавить `LocalHfOnnxEmbeddingProvider`;
- реализовать bootstrap/download manager;
- сделать загрузку модели из project-local cache.

Результат фазы:

- runtime умеет реально строить dense embeddings локально;
- hash provider остается как совместимый режим.

### Phase 3: Index Versioning and Reindex

Цель фазы:

- перевести vector index на versioned layout;
- добавить detection несовместимой размерности/модели;
- сделать безопасный rebuild path.

Результат фазы:

- смена модели становится контролируемой операцией;
- dense rollout не ломает существующие проекты.

### Phase 4: Query/Retrieve Cutover

Цель фазы:

- привязать retrieval semantic lane к project config;
- включать dense semantic search только когда provider действительно готов;
- улучшить observability по активному provider.

Результат фазы:

- `memory search` и `memory retrieve` прозрачно работают с project-selected provider;
- пользователь может увидеть, что реально используется.

### Phase 5: Migration, Docs, Offline and Hardening

Цель фазы:

- задокументировать migrate path для existing projects;
- добавить офлайн bootstrap сценарии;
- покрыть error cases, cache corruption, download retry и manual provisioning.

Результат фазы:

- dense mode становится production-usable, а не только experimental.

## 6. Epic Roadmap

### Epic 0 — Architecture Baseline and ADR Lock

**Objective**

Зафиксировать архитектурные решения до начала кода.

**Decisions to lock**

- project-level selection хранится в `.madspec/config.json`;
- конфиг хранит только stable ids, а не полный metadata catalog;
- model catalog встроен в CLI;
- dense provider по умолчанию работает только локально;
- silent fallback с dense на hash запрещен;
- vector index versioned by provider/model/revision/dimension.

**Deliverables**

- этот roadmap;
- ADR section внутри документа;
- config contract draft;
- registry contract draft.

**Acceptance criteria**

- не остается открытых решений по config shape, bootstrap policy и index layout.

### Epic 1 — Config Contract and Init Integration

**Objective**

Добавить provider selection на уровне инициализации проекта.

**Implementation scope**

- расширить `default_madspec_config(...)`;
- расширить `read_madspec_config(...)` нормализацией нового раздела;
- расширить `create_madspec_config(...)` и `update_madspec_config(...)`;
- встроить prompts выбора memory provider/model в `madspec init`;
- добавить отображение размера модели и download policy в init UX.

**Files likely affected**

- `src/madspec_cli/config.py`
- `src/madspec_cli/shared/infra/project_config.py`
- `src/madspec_cli/features/init/cli.py`
- `src/madspec_cli/features/init/application/contracts.py`
- `src/madspec_cli/features/init/infrastructure/initializer_core.py`

**Acceptance criteria**

- `madspec init` может создать проект с `hash` или `local-hf-onnx`;
- конфиг валиден и стабильно читается после повторного запуска.

### Epic 2 — Provider Registry and Bootstrap Manager

**Objective**

Ввести canonical registry поддерживаемых embedding models и lifecycle загрузки.

**Implementation scope**

- создать `embedding_registry.py`;
- описать supported models;
- реализовать `ensure_model_available(...)`;
- реализовать `downloadPolicy` handling;
- реализовать dry-run check размера/наличия модели.

**Files likely affected**

- `src/madspec_cli/memory/shared/system_store/embedding_registry.py`
- `src/madspec_cli/memory/shared/system_store/model_bootstrap.py`
- `src/madspec_cli/memory/shared/system_store/provider_factory.py`

**Acceptance criteria**

- runtime умеет проверить, скачана ли модель;
- bootstrap пишет модель в project-local cache;
- metadata модели доступны init UX и diagnostics.

### Epic 3 — Dense Local Provider Runtime

**Objective**

Добавить локальный dense provider и сохранить hash compatibility.

**Implementation scope**

- вынести текущий `EmbeddingProvider` в `HashEmbeddingProvider`;
- ввести base protocol/ABC для providers;
- реализовать `LocalHfOnnxEmbeddingProvider`;
- поддержать query/passage prefixing per model;
- обеспечить строго локальную загрузку модели по local path.

**Files likely affected**

- `src/madspec_cli/memory/shared/system_store/vector.py`
- `src/madspec_cli/memory/shared/system_store/provider_factory.py`
- `src/madspec_cli/memory/shared/system_store/text.py` (если потребуется общий preprocessing)

**Acceptance criteria**

- dense provider возвращает embeddings корректной размерности;
- search path больше не зависит от hash vectors в dense mode.

### Epic 4 — Versioned Index Layout and Reindex

**Objective**

Сделать индекс безопасным по отношению к смене provider/model.

**Implementation scope**

- перестроить `lancedb_dir` / index root layout;
- привязать path индекса к provider/model/revision/dimension;
- добавить явный detection несовместимого индекса;
- добавить команды или internal hooks для clean reindex.

**Files likely affected**

- `src/madspec_cli/memory/shared/system_store/vector.py`
- `src/madspec_cli/memory/shared/system_store/jobs.py`
- `src/madspec_cli/memory/shared/system_store/store.py`
- `src/madspec_cli/memory/shared/system_store/constants.py`
- CLI команды обслуживания индекса, если они уже существуют или будут расширены.

**Acceptance criteria**

- смена модели не приводит к mixed-dimension index;
- `reindex` rebuilds only the target index namespace.

### Epic 5 — Query/Retrieve Integration and Observability

**Objective**

Сделать provider selection видимым и диагностируемым в реальном retrieval flow.

**Implementation scope**

- semantic lane использует provider из config, а не default hash implicitly;
- observability показывает active provider/model;
- retrieval runs логируют provider metadata;
- ошибки bootstrap/provider loading имеют structured payload.

**Files likely affected**

- `src/madspec_cli/memory/cli/query.py`
- `src/madspec_cli/memory/application/memory_query.py`
- `src/madspec_cli/memory/application/retrieve_context.py`
- `src/madspec_cli/memory/application/observability.py`

**Acceptance criteria**

- пользователь видит, какой provider реально использован;
- semantic recall не маскирует отсутствие модели.

### Epic 6 — Migration and Operational Hardening

**Objective**

Сделать rollout безопасным для existing projects и закрытых контуров.

**Implementation scope**

- добавить migration notes;
- добавить offline bootstrap flow;
- добавить manual provisioning flow;
- покрыть retry и cache validation;
- документировать expected CPU cost и disk footprint.

**Acceptance criteria**

- existing project можно перевести на dense provider без ручной archaeology;
- offline deployment documented and testable.

## 7. Embedded ADR — Epic 0 Lock

### Status

- status: accepted
- scope: `docs + contracts`
- behavior change in Epic 0: none

### Accepted decisions

- provider selection хранится на уровне проекта, а не глобально на уровне пользователя;
- `hash` остается допустимым и поддерживаемым режимом;
- первая dense production recommendation — `multilingual-e5-small`;
- model metadata живет во встроенном registry;
- bootstrap weights отделен от bootstrap CLI;
- vector index versioned layout обязателен;
- retrieval остается hybrid.

### Rejected alternatives

- хранить полный Hugging Face repo id и всю metadata прямо в config;
- позволить silent fallback с dense на hash;
- заменить весь retrieval dense-only моделью;
- делать model bootstrap глобально вне проекта как единственный supported path;
- требовать другой способ установки CLI вместо существующего `uv` workflow.

### Architectural invariants

- существующий `hash` mode должен продолжать работать без миграции;
- `.madspec/config.json` остается project-level source of truth;
- dense model не может активироваться частично или неявно;
- несовместимый индекс не должен использоваться повторно;
- semantic lane не должен отправлять project content во внешний embedding API.

## 8. Proposed Config Contract

### Minimal normalized config

```json
{
  "currentBranch": "main",
  "version": "1.0.0",
  "agentsSchemaVersion": 1,
  "parallelRuntime": {
    "phase1Enabled": true,
    "phase2Enabled": false
  },
  "agentEnvironment": "cursor-agent",
  "memory": {
    "embeddings": {
      "provider": "local-hf-onnx",
      "model": "multilingual-e5-small",
      "downloadPolicy": "on-init",
      "cacheDir": ".madspec/system/models",
      "revision": null
    }
  }
}
```

### Поле `downloadPolicy` (допустимые значения)

Допустимые строковые значения:

| Значение | Смысл |
|----------|--------|
| `none` | Загрузка весов не выполняется автоматически по политике (актуально для `hash`; для dense — только если пользователь явно отключил отложенную загрузку и подготовил файлы вручную, см. операционные сценарии). |
| `on-init` | Загрузка при успешном завершении шага bootstrap в `madspec init` (если пользователь выбрал dense и согласился на загрузку сейчас). |
| `on-first-use` | Загрузка при первой операции, которой реально нужны веса (например `reindex`, `memory search` / `memory retrieve` с semantic lane). |

Недопустимое или неизвестное значение при чтении конфига должно приводить к явной ошибке валидации, а не к тихой подмене.

### Normalization rules

- если `memory` отсутствует, создается compatibility payload с `provider = "hash"`;
- если `provider = "hash"`, `model` принудительно нормализуется в `null`;
- если `provider = "local-hf-onnx"`, `model` обязателен;
- если `cacheDir` не задан, используется project-local default;
- если `downloadPolicy` не задан, default зависит от provider:
  - `hash` → `none`
  - `local-hf-onnx` → `on-init`
- если пользователь в `init` выбирает «Download on first use», в конфиг записывается `downloadPolicy: "on-first-use"` (перекрывает default `on-init` для dense).

## 9. Proposed Init UX

### Interactive flow

После выбора AI-среды `madspec init` должен добавить новый шаг:

`Choose memory embeddings`

Варианты:

1. `Standard hash (0 MB download, compatibility mode)`
2. `Local semantic: multilingual-e5-small (RU/EN/multilingual, 384 dim, ~470 MB)`
3. `Local semantic: bge-m3 (multilingual, 1024 dim, ~2300 MB, advanced)`

Далее:

- если выбран `hash`, init продолжает обычный flow;
- если выбрана dense-модель, init спрашивает:
  - `Download now`
  - `Download on first use`

### UX requirements

- размер загрузки должен быть показан до подтверждения;
- статус рекомендации (`recommended` / `advanced`) должен быть показан явно;
- если download падает, init не должен молча завершаться как будто dense mode готов;
- пользователь должен увидеть, где именно лежит cache модели.

## 10. Migration Strategy for Existing Projects

### Existing projects without config changes

Существующие проекты продолжают работать как раньше:

- конфиг без `memory.embeddings` нормализуется в `hash`;
- существующий hash index не трогается;
- никакой обязательный bootstrap модели не запускается.

### Existing projects opting into dense mode

Переход существующего проекта:

1. обновить CLI;
2. обновить `.madspec/config.json`;
3. скачать/подготовить модель;
4. выполнить `reindex`;
5. проверить diagnostics/observability;
6. только после этого считать dense mode активным.

### Cutover safety rule

Dense mode считается включенным только если одновременно истинны все условия:

- config provider указывает dense provider;
- model bootstrap завершен успешно;
- versioned index для этой модели существует;
- хотя бы один полноценный `reindex` завершен успешно.

## 11. Offline and Confidential Deployment Model

### Security baseline

Целевая security-модель:

- проектные memory records и artifacts не покидают локальную машину во время embedding inference;
- сеть используется только для однократного скачивания публичных model weights, если пользователь это разрешил;
- после bootstrap можно работать в offline mode;
- должна быть поддержана ручная предзагрузка модели в закрытом контуре.

### Offline support requirements

Нужно официально поддержать сценарии:

- `download on trusted machine -> copy model dir -> run in offline environment`;
- `download disabled, local files only`;
- `cache corruption detected -> explicit repair path`.

## 12. Risks and Mitigations

### Risk: install/runtime bloat

**Mitigation**

- не вшивать модельные веса в сам пакет;
- отделить runtime dependencies от model files;
- ограничить число поддерживаемых моделей на первом этапе.

### Risk: silent degradation to hash mode

**Mitigation**

- запретить неявный fallback;
- выводить active provider в observability и diagnostics.

### Risk: broken indexes after model switch

**Mitigation**

- versioned index layout;
- explicit `reindex required` state.

### Risk: weak RU quality with wrong default model

**Mitigation**

- сделать multilingual dense model first-class recommended option;
- не использовать English-only default для русского рынка.

### Risk: init becomes too heavy

**Mitigation**

- сохранить `hash` as zero-download path;
- дать выбор `download on first use`.

## 13. Recommended Rollout Order

1. architecture baseline and contract lock;
2. config schema and normalization;
3. init UX integration;
4. model registry;
5. local bootstrap manager;
6. dense provider runtime;
7. versioned index layout;
8. reindex and diagnostics;
9. query/retrieve integration;
10. migration docs and offline hardening.

## 14. Final Recommendation

Для первого production rollout рекомендуется следующий пакет решений:

- project-level memory config в `.madspec/config.json`;
- `hash` как compatibility mode;
- `local-hf-onnx` как dense provider kind;
- `multilingual-e5-small` как recommended model;
- `bge-m3` как advanced optional model;
- bootstrap модели в `.madspec/system/models`;
- versioned index layout;
- mandatory `reindex` after provider/model switch;
- no silent fallback;
- hybrid retrieval preserved.

Это дает MADSpec реалистичный и безопасный путь к настоящему локальному semantic search без внешнего embedding provider, без ломки текущего UX установки и без разрушения существующей memory architecture.
