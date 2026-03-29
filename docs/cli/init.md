# `madspec init`

`madspec init` инициализирует проект MADSpec из последнего шаблонного релиза. Команда может создать новую директорию или влить шаблон в текущую.

## Когда Использовать

- чтобы начать новый проект MADSpec с нуля
- чтобы добавить структуру MADSpec в существующий репозиторий
- чтобы сгенерировать файлы команд для агента и стартовую структуру проекта

## Синтаксис

```bash
madspec init <PROJECT_NAME> [OPTIONS]
madspec init . [OPTIONS]
madspec init --here [OPTIONS]
```

## Основные Опции

- `--ai <agent>`: явно выбрать поддерживаемого AI-агента
- `--ignore-agent-tools`: пропустить проверку обязательных CLI-инструментов агента
- `--no-git`: не инициализировать git во время установки
- `--here`: инициализировать проект в текущей директории
- `--force`: пропустить подтверждение при слиянии в непустую текущую директорию
- `--skip-tls`: пропустить SSL/TLS-проверку при загрузке релиза
- `--debug`: показать расширенную диагностику, если инициализация падает
- `--github-token <token>`: использовать GitHub-токен для API-запросов
- `--memory-provider <provider>`: зафиксировать embedding provider проекта в `.madspec/config.json`
- `--memory-model <model>`: указать ключ локальной семантической модели для `local-hf-onnx`
- `--memory-download-policy <policy>`: задать политику bootstrap модели (`none`, `on-init`, `on-first-use`)

Поддерживаемые значения `--ai` берутся из текущего CLI config:

- `cursor-agent`
- `opencode`
- `kilocode`
- `roo`
- `sourcecraft`
- `qwen`
- `copilot`

## Что Происходит Во Время Инициализации

- выбирается или подтверждается целевая AI-среда
- загружается последний релиз шаблона MADSpec
- шаблон распаковывается в целевую директорию
- создаются файлы команд и навыки для выбранного агента
- в `.madspec/config.json` записывается выбранная среда `agentEnvironment`
- в `.madspec/config.json` записывается блок `parallelRuntime` с текущим дефолтом `phase1Enabled=true`, `phase2Enabled=true`
- в `.madspec/config.json` записывается блок `memory.embeddings` с project-level выбором provider/model/policy
- создается проектное хранилище памяти в `.madspec/system/memory/` (`memory.sqlite`, `lancedb/` как корень векторного хранилища, `schema-version.json` с метаданными активного пространства индекса; для `revision = null` namespace нормализуется в сегмент `current`)
- создается проектный слой субагентов в `.madspec/system/agents/` (`state.json`, `proposals.jsonl`, `history.jsonl`, `agents.md`)
- создается структура памяти ветки в `.madspec/<branch>/memory/` и начальные производные представления
- создается снимок состояния этапа `deploy` и производный файл `deployment.md` для текущей ветки
- для сред с native subagents также создаются agent/subagent-файлы проекта; для остальных подготавливаются fallback-артефакты
- при наличии `git` и без `--no-git` выполняется инициализация репозитория
- выводятся рекомендуемые следующие команды для MVP и Feature режимов, включая `madspec.deploy` как рекомендуемый этап перед `mvp.plan` и как самостоятельную команду на более позднем этапе

Если команда запускается с `--here`, MADSpec объединяет файлы шаблона с содержимым текущей директории. Без `--force` CLI попросит подтверждение перед работой с непустой папкой.

## Выбор Семантической Модели Памяти

После выбора AI-среды `madspec init` может зафиксировать embedding provider проекта в `.madspec/config.json`.

- В интерактивном TTY-режиме без memory-флагов CLI показывает шаг выбора модели памяти
- Доступные варианты:
  - `hash` — стандартный compatibility mode без загрузки модели
- `multilingual-e5-small` — рекомендуемая локальная семантическая модель (`local-hf-onnx`, ~470 MB, 384 dim)
- `bge-m3` — продвинутый локальный вариант семантической модели (`local-hf-onnx`, ~2300 MB, 1024 dim)
- Для локальной семантической модели CLI дополнительно предлагает policy:
  - `on-init` — скачать модель сразу во время `madspec init` в локальный кэш проекта
  - `on-first-use` — отложить загрузку до первого runtime-сценария, которому реально понадобится bootstrap
- В неинтерактивном режиме без memory-флагов MADSpec записывает совместимое значение по умолчанию:

```json
{
  "memory": {
    "embeddings": {
      "provider": "hash",
      "model": null,
      "downloadPolicy": "none",
      "cacheDir": ".madspec/system/models",
      "revision": null
    }
  }
}
```

Текущее поведение:

- `on-init` сразу запускает bootstrap модели и завершает `madspec init` ошибкой, если загрузка не удалась
- `on-first-use` сохраняет policy в конфиге и оставляет bootstrap отложенным
- `none` не выполняет автоматическую загрузку модели: если кэш локальной семантической модели не подготовлен вручную, команды семантического поиска завершаются явной ошибкой
- для явной ручной подготовки выбранной локальной семантической модели после инициализации используй `madspec memory bootstrap-model`
- если у пользователя задан `HF_TOKEN` или `HUGGINGFACE_HUB_TOKEN`, MADSpec автоматически передаст его в `huggingface_hub`; если токена нет, загрузка идет в штатном анонимном режиме
- `madspec memory search` и `madspec memory retrieve` используют выбранный провайдер как основной путь семантического поиска и явно показывают состояние provider/model/bootstrap в своем payload
- успешная подготовка локальной семантической модели сама по себе не заменяет гибридное извлечение и не отменяет необходимость `madspec memory reindex` для активного пространства индекса

## Миграция существующего проекта на локальную модель

Для уже существующего проекта поддержанный путь такой:

1. Изменить `memory.embeddings` в `.madspec/config.json`.
2. Выполнить `madspec memory bootstrap-model`, чтобы подготовить локальный кэш проекта для выбранной модели.
3. Выполнить `madspec memory reindex`.
4. Проверить `madspec memory status`, `madspec memory db-status` или `madspec memory doctor`.

Важно:

- смена `provider` или `model` в конфиге сама по себе не делает новый индекс готовым;
- при `memory.embeddings.revision = null` MADSpec всё равно использует явный сегмент revision `current` и в кэше модели, и в пространстве индекса;
- пока не выполнен `madspec memory reindex`, CLI считает состояние индекса неполным и явно показывает это в статусе и диагностике;
- если для локальной семантической модели выбран `downloadPolicy = "none"`, подготовка кэша модели остается ручной операцией через `madspec memory bootstrap-model`.

## Типовые Сценарии

Создать новый проект:

```bash
madspec init my-project --ai cursor-agent
```

Инициализировать в текущем репозитории:

```bash
madspec init . --ai sourcecraft
```

Инициализировать в текущей директории и пропустить настройку git:

```bash
madspec init --here --ai opencode --no-git
```

Инициализировать проект для Qwen Code:

```bash
madspec init my-project --ai qwen
```

Инициализировать проект с локальной семантической моделью и отложенной загрузкой:

```bash
madspec init my-project --ai cursor-agent --memory-provider local-hf-onnx --memory-model multilingual-e5-small --memory-download-policy on-first-use
```

Инициализировать проект с локальной семантической моделью и немедленной загрузкой:

```bash
madspec init my-project --ai cursor-agent --memory-provider local-hf-onnx --memory-model multilingual-e5-small --memory-download-policy on-init
```

## Связанные Документы

- [Индекс CLI-документации](README.md)
- [Обзор процесса работы](../README.md)
- [Быстрый старт](../../QUICKSTART.md)
