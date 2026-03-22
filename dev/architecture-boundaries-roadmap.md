# Дорожная Карта Рефакторинга Архитектурных Границ

Этот документ фиксирует результаты анализа архитектурных границ в `src/madspec_cli/` и определяет последовательность рефакторинга для устранения выявленных нарушений.

## 1. Текущее Состояние

Кодовая база организована по принципу вертикальных срезов (feature-based architecture) с разделением на слои внутри каждого среза:

```
madspec_cli/
├── features/          ← вертикальные срезы (agents, change, gates, git, init, meta, policy)
│   └── <feature>/
│       ├── cli.py           ← представление
│       ├── application/     ← сценарии использования
│       ├── domain/          ← бизнес-правила
│       └── infrastructure/  ← внешние зависимости, хранение
├── memory/            ← отдельная вертикаль (структурированная память)
│   ├── cli/
│   ├── application/
│   ├── domain/
│   ├── projection/
│   ├── semantic/
│   ├── stages/
│   ├── workflow/
│   └── shared/        ← system_store, утилиты хранения
├── shared/            ← общие утилиты (cli, infra, kernel)
├── app.py             ← точка входа
├── config.py          ← конфигурация агентов
├── project_state.py   ← состояние проекта
├── ui.py              ← консоль, баннеры
└── github_api.py      ← HTTP-клиент GitHub
```

Разделение на слои заявлено, но на практике архитектурные границы нарушаются в нескольких направлениях.

## 2. Выявленные Нарушения

### 2.1 Нарушения Чистоты Доменного Слоя

Доменный слой должен зависеть только от стандартной библиотеки и собственных доменных модулей. Обнаружены прямые зависимости от внешних модулей.

| Файл | Импорт | Проблема |
|------|--------|----------|
| `features/agents/domain/builtin_roles.py` | `from madspec_cli.config import AGENT_CONFIG` | Домен зависит от корневой конфигурации |
| `features/agents/domain/frontmatter_profiles.py` | `from madspec_cli.config import AGENT_CONFIG` | Домен зависит от корневой конфигурации |
| `memory/domain/branch_layout.py` | `from madspec_cli.project_state import resolve_branch_name` | Домен зависит от `project_state`, который транзитивно тянет `ui` и `features.git.infrastructure` |

Косвенные зависимости: `domain/tool_translation.py` через `frontmatter_profiles` также зависит от `config`.

### 2.2 Межмодульные Зависимости features ↔ features

Вертикальные срезы должны быть изолированы друг от друга. Обнаружены прямые перекрёстные импорты.

| Источник | Зависит от | Количество импортов |
|----------|------------|---------------------|
| `features/agents` | change, gates, policy | 3 |
| `features/change` | git | 1 |
| `features/gates` | policy | 1 |
| `features/init` | agents, git, policy | 3 |
| `features/meta` | git | 1 |

Наиболее связанные модули: `agents` (3 внешних зависимости), `init` (3 внешних зависимости).

### 2.3 Двунаправленная Связь features ↔ memory

Модули `features` и `memory` имеют обширные взаимные зависимости, образуя запутанный граф.

| Направление | Файлов | Импортов |
|-------------|--------|----------|
| features → memory | 17 | >30 |
| memory → features | 11 | 17 |

Основные точки связи:

- `memory.shared.storage` (утилиты `now_iso`, `read_json`, `write_json`, `get_memory_paths`) используется практически во всех features.
- `memory.domain.branch_layout.resolve_target_branch` импортируется из CLI-слоёв шести features.
- `memory.shared.system_store` импортируется из application и CLI слоёв gates, agents, change.
- `memory` зависит от `features.gates`, `features.policy`, `features.change`, `features.agents`, `features.git`.

### 2.4 Нарушения Направления Зависимостей Внутри memory

Внутри модуля `memory` обнаружены нарушения послойной организации.

**CLI → shared/system_store (обход application):**

8 файлов в `memory/cli/` импортируют напрямую из `memory/shared/system_store/`, минуя слой application.

**CLI → domain (обход application):**

10 файлов в `memory/cli/` импортируют `resolve_target_branch` из `memory/domain/`, минуя application.

**shared → stages, workflow, features (обратное направление):**

| Файл | Зависит от | Проблема |
|------|------------|----------|
| `shared/system_store/canonical_state.py` | stages (7 стадий) | Общий модуль зависит от конкретных стадий |
| `shared/validation_views.py` | stages (все стадии) | Общий модуль зависит от конкретных стадий |
| `shared/validation_runtime.py` | workflow.planning | Общий модуль зависит от workflow |
| `shared/validation.py` | features.policy | Общий модуль зависит от features |
| `shared/storage.py` | features.git | Общий модуль зависит от features |

**semantic → projection (обратная связь):**

`semantic/capture.py` импортирует `consolidate_branch_memory` из `projection/materialize.py`.

### 2.5 project_state Как Объект С Избыточной Ответственностью

Модуль `project_state.py` объединяет несвязанные обязанности:

- чтение и запись конфигурации проекта (`.madspec/config.json`);
- работу с файловой структурой ветки (`ensure_branch_dir`);
- определение текущей ветки (через `features.git.infrastructure.operations`);
- вывод в UI (через `ui.console`);
- версионирование схем (`MADSPEC_CONFIG_VERSION`, `MADSPEC_AGENTS_SCHEMA_VERSION`);
- неиспользуемую функцию `emit_json`.

Используется из 7 модулей в разных слоях, включая домен (`memory/domain/branch_layout.py`).

### 2.6 Отсутствие Абстракций Для Межмодульного Взаимодействия

Между features и memory нет контрактов (интерфейсов, портов). Все зависимости реализованы прямыми импортами конкретных реализаций. Это делает невозможным:

- независимое тестирование модулей;
- замену реализации без правки всех зависимых модулей;
- контроль направления зависимостей статическими средствами.

## 3. Принципы Рефакторинга

1. **Домен не зависит ни от чего, кроме стандартной библиотеки и собственных доменных модулей.** Конфигурация, инфраструктура и UI получают доступ к домену, а не наоборот.

2. **Вертикальные срезы изолированы.** Общение между features происходит только через контракты (протоколы, интерфейсы) или через оркестратор уровня application.

3. **CLI → application → domain ← infrastructure.** Направление зависимостей соблюдается строго. CLI не обращается к domain и infrastructure напрямую.

4. **shared содержит только инварианты.** Утилиты в shared не зависят от конкретных features, stages или workflow.

5. **Каждое изменение обратно совместимо.** Рефакторинг выполняется пошагово без нарушения работоспособности CLI.

## 4. Дорожная Карта

### Фаза 1 — Чистота Домена (Критическая)

Устранение зависимостей доменного слоя от инфраструктуры, конфигурации и UI.

#### 1.1 Вынести `AGENT_CONFIG` из домена agents

**Текущее состояние:** `builtin_roles.py` и `frontmatter_profiles.py` импортируют `AGENT_CONFIG` напрямую.

**Целевое состояние:** доменные функции принимают необходимые данные через параметры. Привязка к `AGENT_CONFIG` происходит на уровне application.

**Шаги:**

1. Выделить из `AGENT_CONFIG` типы данных, необходимые домену (имя агента, имя папки, подкаталог команд), в доменную модель (dataclass или TypedDict) в `features/agents/domain/models.py`.
2. Изменить сигнатуры доменных функций: вместо чтения глобального `AGENT_CONFIG` принимать коллекцию доменных моделей через параметры.
3. В `features/agents/application/` добавить маппинг `AGENT_CONFIG` → доменные модели и передавать их в доменные функции.
4. Удалить импорты `madspec_cli.config` из `features/agents/domain/`.

**Затрагиваемые файлы:** `builtin_roles.py`, `frontmatter_profiles.py`, `tool_translation.py`, `models.py`, файлы в `application/`.

#### 1.2 Убрать зависимость memory/domain от project_state

**Текущее состояние:** `branch_layout.py` импортирует `resolve_branch_name` из `project_state`, который зависит от `ui` и `features.git.infrastructure`.

**Целевое состояние:** доменная функция `resolve_target_branch` принимает имя ветки как параметр. Разрешение ветки из конфигурации и git выполняется на уровне application.

**Шаги:**

1. Изменить `resolve_target_branch` в `memory/domain/branch_layout.py`: принимать `branch_name: str | None` и `fallback_branch: str` как параметры, без обращения к `project_state`.
2. Создать функцию-обёртку в `memory/application/` (или в каждом сценарии использования), которая вызывает `project_state.resolve_branch_name` и передаёт результат в доменную функцию.
3. Обновить все вызовы `resolve_target_branch` в `memory/cli/` (10 файлов) — они будут вызывать application-обёртку вместо доменной функции напрямую.
4. Удалить импорт `project_state` из `memory/domain/branch_layout.py`.

**Затрагиваемые файлы:** `branch_layout.py`, 10 файлов в `memory/cli/`, файлы в `memory/application/`.

#### 1.3 Удалить неиспользуемый `emit_json` из project_state

**Шаги:**

1. Убедиться, что `project_state.emit_json` не используется (поиск подтверждает).
2. Удалить определение функции и соответствующий импорт `json`.

**Затрагиваемые файлы:** `project_state.py`.

---

### Фаза 2 — Устранение Обратных Зависимостей В shared

Модуль `memory/shared/` зависит от `stages/`, `workflow/` и `features/`. Это нарушает принцип: общие модули не зависят от конкретных.

#### 2.1 Инвертировать зависимость shared/system_store → stages

**Текущее состояние:** `canonical_state.py` импортирует `default_*_state` из каждой стадии (7 штук).

**Целевое состояние:** каждая стадия регистрирует свою начальную конфигурацию через реестр (registry pattern), а `canonical_state.py` читает из реестра.

**Шаги:**

1. Создать `memory/shared/system_store/stage_registry.py` с простым реестром `{stage_key: default_state_factory}`.
2. В каждом `stages/<stage>/state.py` добавить регистрацию через вызов `register_stage(key, factory)` на уровне модуля.
3. В `canonical_state.py` заменить прямые импорты на чтение из реестра.
4. Аналогично обновить `shared/validation_views.py`.

**Затрагиваемые файлы:** `canonical_state.py`, `validation_views.py`, `stage_registry.py` (новый), 7 файлов в `stages/*/state.py`.

#### 2.2 Устранить зависимость shared → workflow

**Текущее состояние:** `validation_runtime.py` импортирует из `workflow/planning.py`.

**Целевое состояние:** необходимые функции (`_compute_progress_metrics`, `extract_function_catalog`) переносятся в shared или вызываются через параметры.

**Шаги:**

1. Проанализировать, являются ли `_compute_progress_metrics` и `extract_function_catalog` доменной логикой или утилитами.
2. Если утилиты — перенести в `shared/`. Если доменная логика — передавать результаты через параметры из application-слоя.
3. Обновить импорты.

**Затрагиваемые файлы:** `validation_runtime.py`, `workflow/planning.py`.

#### 2.3 Устранить зависимость shared → features

**Текущее состояние:** `shared/storage.py` импортирует `get_current_branch` из `features.git`, `shared/validation.py` импортирует из `features.policy`.

**Целевое состояние:** shared не импортирует из features. Имя ветки и результаты оценки политик передаются через параметры.

**Шаги:**

1. В `shared/storage.py` — функции, зависящие от `get_current_branch`, должны принимать имя ветки как параметр. Вызывающий код (application) передаёт значение.
2. В `shared/validation.py` — функция `evaluate_branch_policies` вызывается на уровне application, а результат передаётся в shared-валидатор через параметры.
3. Обновить все вызывающие модули.

**Затрагиваемые файлы:** `shared/storage.py`, `shared/validation.py`, вызывающие модули в `application/`.

---

### Фаза 3 — Контракты Между Модулями

Введение явных контрактов для межмодульного взаимодействия.

#### 3.1 Контракт для работы с git

**Текущее состояние:** пять features и memory импортируют `get_current_branch` и `is_git_repo` напрямую из `features/git/infrastructure/operations.py`.

**Целевое состояние:** определён протокол (интерфейс) `GitOperations` в `shared/kernel/` или в `features/git/domain/`. Зависимые модули используют протокол, а не конкретную реализацию.

**Шаги:**

1. Определить `Protocol` с методами `get_current_branch`, `is_git_repo` в `shared/kernel/ports.py` (или `features/git/domain/ports.py`).
2. Реализация в `features/git/infrastructure/operations.py` реализует этот протокол.
3. Зависимые модули получают реализацию через параметры (инъекция на уровне CLI или application).
4. Переход постепенный: сначала определить протокол, потом поэтапно переводить зависимых.

**Затрагиваемые файлы:** новый `ports.py`, `operations.py`, 5+ файлов в features, 2+ файла в memory.

#### 3.2 Контракт для утилит хранения

**Текущее состояние:** `memory/shared/storage.py` (функции `now_iso`, `read_json`, `write_json`, `append_jsonl`, `get_memory_paths`) используется из 17+ файлов в features.

**Целевое состояние:** утилиты общего назначения (`now_iso`, `read_json`, `write_json`) перенесены в `shared/infra/` или `shared/kernel/`. Специфичные для memory функции (`get_memory_paths`) остаются в memory, а features получают к ним доступ через явный контракт.

**Шаги:**

1. Перенести чистые утилиты (`now_iso`, `read_json`, `write_json`, `append_jsonl`) в `shared/infra/json_storage.py`.
2. Оставить в `memory/shared/storage.py` только memory-специфичные функции.
3. Обновить импорты во всех зависимых файлах.

**Затрагиваемые файлы:** `memory/shared/storage.py`, `shared/infra/json_storage.py` (новый), 17+ файлов в features.

#### 3.3 Контракт для межмодульных запросов (gates, policy, change)

**Текущее состояние:** `memory/` импортирует application-функции из `features/gates`, `features/policy`, `features/change` для оценки состояния гейтов и политик.

**Целевое состояние:** определены протоколы для запросов (`GateEvaluator`, `PolicyEvaluator`, `ChangeContextProvider`). Memory зависит от протоколов, features предоставляют реализации.

**Шаги:**

1. Определить протоколы в `shared/kernel/ports.py`.
2. Реализации — в соответствующих features.
3. Привязка реализаций к протоколам — на уровне CLI (композиционный корень в `app.py` или `memory/cli/`).
4. Переход поэтапный: начать с `evaluate_gate_context` (используется в 4 файлах memory).

**Затрагиваемые файлы:** `shared/kernel/ports.py`, файлы в `memory/application/`, `memory/projection/`, `memory/workflow/`, файлы в features.

---

### Фаза 4 — Разделение project_state

Устранение избыточной ответственности корневого модуля `project_state.py`.

#### 4.1 Разнести project_state по целевым модулям

**Текущее состояние:** `project_state.py` объединяет конфигурацию, файловую систему, git, UI и версионирование.

**Целевое состояние:**

| Ответственность | Целевой модуль |
|-----------------|----------------|
| Чтение и запись `config.json` | `shared/infra/project_config.py` |
| `ensure_branch_dir` | `memory/shared/storage.py` (уже частично там) |
| `resolve_branch_name` | `shared/infra/project_config.py` (без зависимости от UI) |
| Версии схем | `config.py` или отдельный `shared/kernel/versions.py` |
| `emit_json` | удалить (дубликат) |

**Шаги:**

1. Перенести функции чтения и записи конфигурации в `shared/infra/project_config.py`.
2. Перенести `resolve_branch_name` туда же, убрав зависимость от `ui.console`.
3. Перенести версии схем в `config.py`.
4. Обновить все импорты (7 модулей).
5. Удалить `project_state.py` или оставить как тонкий фасад для обратной совместимости.

**Затрагиваемые файлы:** `project_state.py`, `shared/infra/project_config.py` (новый), 7+ файлов с импортами.

---

### Фаза 5 — Направление Зависимостей В CLI

Стандартизация обращения CLI-слоя к нижележащим слоям.

#### 5.1 CLI memory → application (убрать прямые обращения к domain и shared/system_store)

**Текущее состояние:** 10 файлов в `memory/cli/` импортируют из `memory/domain/`, 8 файлов из `memory/shared/system_store/`.

**Целевое состояние:** CLI обращается только к application-слою. Application инкапсулирует взаимодействие с domain и system_store.

**Шаги:**

1. Для `resolve_target_branch` — создать application-обёртку (выполняется в рамках Фазы 1.2).
2. Для `SYSTEM_SESSION_KEY` — передавать через параметры application-функций или вынести константу в `shared/kernel/`.
3. Для `load_runtime_session`, `search_memory_store`, `build_db_status`, `run_reindex` — создать application-обёртки.
4. Поэтапно обновить CLI-файлы.

**Затрагиваемые файлы:** 10+ файлов в `memory/cli/`, файлы в `memory/application/`.

#### 5.2 CLI features → domain (аналогичная стандартизация)

**Текущее состояние:** CLI-модули features (`change/cli.py`, `gates/cli.py`, `policy/cli.py`, `agents/cli.py`) импортируют `resolve_target_branch` из `memory/domain/`.

**Целевое состояние:** CLI обращается к application-обёртке.

**Затрагиваемые файлы:** 4 файла `features/*/cli.py`.

---

### Фаза 6 — Изоляция Вертикальных Срезов features

#### 6.1 Устранить прямые импорты между features

**Текущее состояние:** 10 прямых импортов между features.

**Целевое состояние:** features взаимодействуют только через контракты (протоколы из Фазы 3) или через общие утилиты из shared.

**Приоритеты:**

1. `features/init` → agents, git, policy — самая крупная связка. `init` как оркестратор может использовать контракты.
2. `features/agents` → change, gates, policy — через контракты запросов.
3. `features/change` → git — через контракт git-операций (Фаза 3.1).
4. `features/gates` → policy — через контракт оценки политик.
5. `features/meta` → git — через контракт git-операций.

**Затрагиваемые файлы:** 5 файлов в features с межмодульными импортами.

## 5. Порядок Выполнения И Зависимости

```
Фаза 1 (Чистота Домена)
  ├── 1.1 AGENT_CONFIG из домена          ← независима
  ├── 1.2 branch_layout из project_state  ← независима
  └── 1.3 Удаление emit_json             ← независима

Фаза 2 (Обратные зависимости shared)
  ├── 2.1 shared → stages (реестр)        ← независима
  ├── 2.2 shared → workflow               ← независима
  └── 2.3 shared → features              ← зависит от Фазы 1.2

Фаза 3 (Контракты)
  ├── 3.1 Контракт git                    ← независима
  ├── 3.2 Контракт хранения              ← независима
  └── 3.3 Контракт gates/policy/change   ← зависит от Фаз 2.3

Фаза 4 (project_state)                   ← зависит от Фазы 1.2

Фаза 5 (CLI → application)
  ├── 5.1 memory/cli                      ← зависит от Фазы 1.2
  └── 5.2 features/cli                    ← зависит от Фазы 1.2

Фаза 6 (Изоляция features)               ← зависит от Фаз 3.1, 3.3
```

Фазы 1.1, 1.2, 1.3, 2.1, 2.2, 3.1, 3.2 могут выполняться параллельно.

## 6. Критерии Готовности Каждой Фазы

| Фаза | Критерий |
|------|----------|
| 1 | Ни один файл в `**/domain/` не импортирует модули за пределами domain и stdlib |
| 2 | Ни один файл в `memory/shared/` не импортирует из `stages/`, `workflow/` или `features/` |
| 3 | Протоколы определены; хотя бы один зависимый модуль переведён на использование протокола |
| 4 | `project_state.py` удалён или содержит только реэкспорты для обратной совместимости |
| 5 | Ни один файл `**/cli/*.py` не импортирует из `**/domain/` или `**/shared/system_store/` напрямую |
| 6 | Ни один файл `features/<A>/` не импортирует из `features/<B>/` напрямую |

## 7. Метрики До И После

### Текущие Метрики (до рефакторинга)

| Метрика | Значение |
|---------|----------|
| Нарушения чистоты домена | 3 файла (+ 1 косвенно) |
| Импорты features → features | 10 |
| Импорты features → memory | >30 |
| Импорты memory → features | 17 |
| CLI → domain напрямую | 14 файлов |
| CLI → shared/system_store напрямую | 8 файлов |
| shared → stages/workflow/features | 5 файлов |

### Целевые Метрики (после рефакторинга)

| Метрика | Значение |
|---------|----------|
| Нарушения чистоты домена | 0 |
| Импорты features → features | 0 |
| Импорты через контракты | все межмодульные |
| CLI → domain напрямую | 0 |
| CLI → shared/system_store напрямую | 0 |
| shared → stages/workflow/features | 0 |

## 8. Риски И Ограничения

| Риск | Вероятность | Смягчение |
|------|-------------|-----------|
| Разрыв работоспособности CLI при переносе функций | Средняя | Каждый шаг — отдельный коммит с проверкой `madspec --help`, `madspec check` |
| Увеличение количества файлов и уровней косвенности | Высокая | Вводить контракты только там, где есть реальные межмодульные зависимости |
| Регрессия в memory-подсистеме из-за изменений shared | Средняя | Прогон `madspec memory doctor` после каждого изменения в shared |
| Чрезмерная абстракция (over-engineering) | Средняя | Использовать протоколы Python (`typing.Protocol`), а не абстрактные классы с фабриками |

## 9. Критерии Продолжения Или Остановки

`Go`:

- каждая завершённая фаза уменьшает количество нарушений без регрессий;
- CLI проходит полный набор проверок после каждого шага;
- разработчики подтверждают, что новые контракты упрощают понимание зависимостей.

`Stop`:

- рефакторинг создаёт регрессии, которые не удаётся устранить в рамках текущей фазы;
- количество новых файлов и уровней косвенности превышает выигрыш от изоляции;
- изменения требуют одновременной правки более 30 файлов в одном шаге (признак неправильной декомпозиции).
