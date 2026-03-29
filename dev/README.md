# Dev Notes

## Архив Документов `dev`

Все roadmap-, RFC- и ADR-документы в этой директории переведены в архивный режим.

Их роль теперь историческая:

- они фиксируют уже принятые решения, этапы rollout и исторический контекст изменений;
- они больше не считаются источником текущего product/runtime-контракта;
- актуальная истина должна читаться из `README.md`, `docs/cli/`, `skills/` и из текущего кода.

## Состав Архива

- `dev/architecture-boundaries-roadmap.md` — архив дорожной карты по очистке архитектурных границ
- `dev/architecture-refactoring-next-steps.md` — архив второй волны архитектурного рефакторинга
- `dev/madspec-cli-agentic-refactor-rfc.md` — архив RFC по упрощению архитектуры `madspec_cli`
- `dev/memory-embedding-provider-roadmap.md` — архив roadmap/ADR по embedding provider и векторному слою
- `dev/parallel-memory-roadmap.md` — архив roadmap по parallel memory и multi-agent runtime
- `dev/phase2-cutover-roadmap.md` — архив rollout-перехода на `Phase 2` по умолчанию
- `dev/semantic-layer-roadmap.md` — архив roadmap по развитию семантического слоя памяти

## Локальное тестирование CLI через `uv`

Если нужно протестировать изменения в `madspec` локально, не публикуя их на GitHub, устанавливайте CLI прямо из текущего checkout репозитория.

### Рекомендуемый режим: editable install

```bash
cd /Users/madteacher/Documents/GitHub/MADSpec
uv tool install --force --editable .
```

Что это дает:

- `uv` устанавливает пакет `madspec-cli` из локальной директории
- команда `madspec` начинает ссылаться на текущий checkout
- изменения в `src/` обычно подхватываются без повторной установки

### Когда нужно переустанавливать заново

Повторно выполните:

```bash
uv tool install --force --editable .
```

если изменились:

- зависимости в `pyproject.toml`
- metadata пакета
- `project.scripts`
- build-конфигурация

### Проверка после установки

```bash
madspec --help
madspec version
madspec check
```

Если тестируете сценарий инициализации:

```bash
madspec init /tmp/madspec-test --ai cursor-agent
```

### Не-editable установка

Если нужно проверить поведение ближе к обычной установленной версии пакета:

```bash
cd /Users/madteacher/Documents/GitHub/MADSpec
uv tool install --force .
```

В этом режиме после изменений в коде нужно выполнять установку заново.

### Разовый запуск без установки

Для одноразовой проверки можно запускать CLI прямо из локального репозитория:

```bash
cd /Users/madteacher/Documents/GitHub/MADSpec
uvx --from . madspec --help
uvx --from . madspec check
```

### Если ранее был установлен релиз с GitHub

Обычно достаточно просто переустановить локальную версию поверх него:

```bash
uv tool install --force --editable .
```

Если хотите начать с чистого состояния:

```bash
uv tool uninstall madspec-cli
uv tool install --editable .
```
