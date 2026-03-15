# Dev Notes

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
