# `madspec git`

Группа `madspec git` управляет состоянием git в MADSpec. Эти команды синхронизируют `.madspec` с текущей или целевой веткой и дают удобную обертку над типовыми git-задачами, которые нужны процессу работы.

## Когда Использовать

- чтобы понять, какую ветку MADSpec должен использовать для артефактов
- чтобы создать или переключить контекст ветки в MADSpec
- чтобы инициализировать git в свежесозданном проекте
- чтобы делать коммиты в ходе реализации

## Обзор Команд

| Команда | Назначение |
| --- | --- |
| `madspec git current-branch` | Определить активную ветку с запасным вариантом через `.madspec/config.json` |
| `madspec git list-branches` | Показать ветки, для которых уже есть артефакты MADSpec |
| `madspec git set-branch <name>` | Сохранить ветку в конфигурации MADSpec и подготовить ее структуру |
| `madspec git ensure-gitignore` | Создать или дополнить `.gitignore` MADSpec-паттернами |
| `madspec git init` | Инициализировать git, подготовить `.gitignore` и сделать первый commit |
| `madspec git create-branch <name>` | Создать git-ветку и синхронизировать состояние ветки в MADSpec |
| `madspec git commit --message <msg>` | Заиндексировать изменения и создать commit |

## Общие Опции

Большинство команд поддерживает:

- `--json-output`: вывести JSON вместо терминального интерфейса

У `madspec git init` также есть:

- `--commit-message`: переопределить сообщение для первого commit

## Типовое Использование

Посмотреть, какую ветку будет использовать MADSpec:

```bash
madspec git current-branch
```

Зафиксировать выбор ветки в конфигурации MADSpec:

```bash
madspec git set-branch feature/user-auth
```

Создать ветку и синхронизировать структуру MADSpec:

```bash
madspec git create-branch feature/billing
```

Инициализировать git в только что созданном проекте:

```bash
madspec git init
```

Создать commit из всех текущих изменений:

```bash
madspec git commit --message "feat: add billing flow"
```

## Что Эти Команды Обновляют

- `.madspec/config.json`, когда состояние ветки явно устанавливается или синхронизируется
- `.gitignore`, когда MADSpec создает или дописывает свои паттерны
- `.madspec/<branch>/`, когда нужно подготовить структуру конкретной ветки
- историю коммитов репозитория, когда `commit` или `init` создают commit

## Связанные Документы

- [Индекс CLI-документации](README.md)
- [Команды структурированной памяти](memory.md)
- [MVP-процесс](../mvp/README.md)
- [Feature-процесс](../feature/README.md)
