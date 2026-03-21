# Карта команд

## Агентные команды со слешем

Для нового продукта:

- `/madspec.mvp.concept` — зафиксировать идею, аудиторию, pain points, P1/P2/P3
- `/madspec.mvp.design` — сделать визуальное видение интерфейса и HTML/CSS-прототипы сценариев
- `/madspec.mvp.tech` — выбрать стек и обосновать его
- `/madspec.mvp.architecture` — определить архитектуру, модель данных, контракты
- `/madspec.deploy` — зафиксировать план развертывания ветки: окружения, единицы развертывания, CI/CD, секреты, наблюдаемость, релиз и откат
- `/madspec.mvp.plan` — разбить реализацию на отдельные шаги
- `/madspec.mvp.implement` — выполнять шаги реализации с валидацией и тестами

Для доработки существующего проекта:

- `/madspec.feature.init` — зафиксировать цель фичи, каталог функций и точки интеграции в `feature.init.json`
- `/madspec.feature.plan` — спланировать шаги реализации фичи через `feature.plan.json`
- `/madspec.feature.implement` — реализовать шаги фичи через процесс работы с памятью реализации

Сквозные команды:

- `/madspec.memory` — объяснение и диагностика структурированной памяти через канонические `madspec memory ...`
- `/madspec.merge` — разговорная подготовка слияния памяти между ветками и продвижения знаний на уровень проекта
- `/madspec.change` — разговорная работа с пакетом изменений ветки поверх канонических `madspec change ...`
- `/madspec.gate` — разговорная работа с контрольными проверками, блокировками переходов и предложениями на исключения
- `/madspec.agents` — разговорная работа с профилями субагентов, native/fallback-режимом и role-scoped context
- `/madspec.review` — анализ качества после реализации: соответствие замыслу, качество кода, влияние на архитектуру, направления улучшений
- `/madspec.security` — практический аудит безопасности и приватности кода, зависимостей, архитектуры и обработки ПД по 152-ФЗ

## CLI-команды

- `madspec init` — развернуть шаблон проекта под выбранного агента (`cursor-agent`, `opencode`, `kilocode`, `roo`, `sourcecraft`, `qwen`, `copilot`)
- `madspec check` — проверить наличие git и поддерживаемых агентных инструментов
- `madspec version` — показать версию CLI и шаблона
- `madspec migrate` — перенести старую плоскую `.madspec/` структуру в размещение, привязанное к веткам; не включает `parallelRuntime.phase2Enabled` и не меняет rollout policy

### Git-операции

- `madspec git current-branch` — определить текущую ветку MADSpec
- `madspec git list-branches` — показать ветки, у которых уже есть MADSpec-артефакты
- `madspec git set-branch <name>` — вручную зафиксировать ветку для артефактов
- `madspec git ensure-gitignore` — добавить MADSpec-паттерны в `.gitignore`
- `madspec git init` — инициализировать git и стартовый commit
- `madspec git create-branch <name>` — создать git-ветку и синхронизировать `.madspec/<branch>/`
- `madspec git commit --message "..."` — закоммитить текущее состояние

### Структурированная память

- `madspec memory init` — создать структуру памяти для ветки
- `madspec memory status` — проверить текущее состояние памяти
- `madspec memory db-status` — проверить состояние `SQLite` и векторного индекса
- `madspec memory capture` — накапливать проверенные факты, решения, контракты и вопросы по стадии; поддерживает `--from-file` и `--session-key`
- `madspec memory checkpoint` — завершить неитеративную стадию и обновить производное состояние; поддерживает `--from-file` и `--session-key`
- `madspec memory retrieve` — получить минимальный контекст стадии или шага; поддерживает `--session-key`, смешанный поиск через `--query`, `--disable-semantic`, `--recall-limit`, `--scope`; для `mvp.concept` по умолчанию возвращает краткий `concept_status`, для `mvp.design` — `design_status`, для `mvp.tech` — `tech_status`, для `mvp.plan` — `plan_status`, а полное состояние артефакта стадии отдает только по `--full-artifact`
- `madspec memory search` — посмотреть кандидатов из точного, полнотекстового и семантического поиска без полного контекста стадии; поддерживает `--session-key`
- `madspec memory doctor` — провести диагностическую проверку без изменения памяти ветки, слоя `SQLite`, векторного индекса и производных представлений
- `madspec memory explain` — объяснить контекст стадии, влияние правил и результатов поиска по смыслу
- `madspec memory timeline` — показать объединенную историю записей, снимков состояния и `retrieval_runs`
- `madspec memory why-next-step` — объяснить выбор следующего шага и блокировки остальных шагов
- `madspec memory conflicts` — показать явные записи со статусом `conflicted` и конфликты целостности
- `madspec memory inspect-record` — подробно показать каноническую запись, исходный файл и состояние индексирования
- `madspec memory compare-branches` — сравнить снимки стадий, progress и подтвержденные записи знаний двух веток
- `madspec memory propose-merge` — создать предложение на слияние из ветки-источника в целевую ветку
- `madspec memory preview-merge` — показать предварительный просмотр предложения на слияние
- `madspec memory resolve-conflict` — изменить решение по конфликту внутри предложения на слияние
- `madspec memory merge-branches` — применить ранее подготовленное предложение на слияние
- `madspec memory promote-branch-knowledge` — поднять подтвержденные знания из ветки на уровень проекта
- `madspec memory reindex` — обработать ожидающие задания индексирования и обновить векторные фрагменты
- `madspec memory consolidate` — пересобрать Markdown-представления из структурированной памяти
- `madspec memory validate` — проверить согласованность памяти и производных представлений
- `madspec memory register-step` — зарегистрировать шаг планирования; поддерживает `--from-file` и `--session-key`
- `madspec memory start-step` — запустить шаг реализации; поддерживает `--from-file` и `--session-key`
- `madspec memory checkpoint-step` — зафиксировать промежуточное состояние шага; поддерживает `--from-file` и `--session-key`
- `madspec memory complete-step` — завершить шаг реализации; поддерживает `--from-file` и `--session-key`
- `madspec memory tasks ...`, `madspec memory work-items ...`, `madspec memory proposals ...`, `madspec memory coordinator explain` — относятся к opt-in Phase 2 и требуют `parallelRuntime.phase2Enabled=true`

### Слой правил

- `madspec policy init` — создать единое проектное размещение правил в `.madspec/system/policy/`
- `madspec policy show` — показать действующие правила и ожидающие применения предложения
- `madspec policy propose` — создать предложение по правилу без изменения примененного состояния
- `madspec policy set` — сокращение для `propose` и `apply`
- `madspec policy apply` — применить ожидающее предложения и изменить действующий набор правил
- `madspec policy deprecate` — вывести правило из действующего набора через цикл предложений и применения
- `madspec policy validate` — выполнить проверку правил для стадии или шага
- `madspec policy history` — показать журнал изменений слоя правил
- `madspec policy explain` — объяснить результаты проверки правил и действующие правила для стадии
- `madspec policy export` — пересобрать `.madspec/system/policy.md` и связанные производные представления

### Слой изменений

- `madspec change init` — зафиксировать базовую точку сравнения ветки и подготовить хранилище изменений
- `madspec change propose` — собрать ожидающий применения пакет изменений из текущего состояния ветки
- `madspec change diff` — показать вычисленный набор различий относительно базовой точки сравнения
- `madspec change preview` — показать полное предложение перед применением
- `madspec change apply` — ратифицировать ожидающий применения пакет изменений без изменения кода и памяти ветки
- `madspec change export` — собрать переносимый пакет экспорта в `.madspec/<branch>/change/export/`
- `madspec change verify` — проверить расхождения между активным пакетом изменений и текущим состоянием ветки
- `madspec change summary` — показать активный пакет изменений и его краткую сводку

### Слой контрольных проверок

- `madspec gate status` — показать вычисленный gate status для ветки, стадии или шага
- `madspec gate run` — вычислить gates для конкретного transition context и записать audit event
- `madspec gate explain` — объяснить результаты проверок, историю и предложения на исключения
- `madspec gate propose-waiver` — создать ожидающее применения предложение на исключение
- `madspec gate apply-waiver` — применить ожидающее предложение и активировать исключение
- `madspec review status` — read-only алиас для ратификации review и связанных проверок
- `madspec security status` — read-only алиас для ратификации security и связанных проверок

### Слой субагентов

- `madspec agents profile` — показать активную среду, профиль ролей и размещение state-файлов
- `madspec agents recommend` — вернуть рекомендуемый базовый профиль ролей
- `madspec agents propose-profile` — создать proposal на изменение профиля ролей
- `madspec agents apply-profile` — применить proposal и перерендерить средовые agent/subagent-файлы или fallback-артефакты
- `madspec agents subagents list` — показать доступные роли и их текущее состояние
- `madspec agents subagents enable` — включить конкретную роль
- `madspec agents subagents disable` — отключить конкретную роль
- `madspec agents subagents context` — отдать канонический role-scoped context для выбранной роли; поддерживает `--session-key`, а coordinator payload добавляет только при `parallelRuntime.phase2Enabled=true`

## Когда обращаться к этому файлу

Открывай этот reference-файл, если нужно быстро вспомнить:

- какие команды существуют
- к какой подсистеме относится команда
- какие read-only и state-changing операции предусмотрены
