# Обзор модели MADSpec

## Что такое MADSpec

MADSpec управляет разработкой через агентные команды и артефакты в `.madspec/<branch>/`, привязанные к ветке.

- Шаблоны и процедуры живут в `.madspec/templates/` и `.madspec/procedures/`.
- Рабочие артефакты привязаны к текущей ветке.
- Ветка определяется через `madspec git current-branch`.
- Проектное хранилище памяти в `.madspec/system/memory/` является каноническим источником состояния, а `.madspec/<branch>/memory/` остается файловой структурой памяти ветки и слоем совместимости для команд процесса.
- Session-local runtime state канонически хранится в таблице `sessions` внутри `SQLite`; `.madspec/<branch>/memory/working/active-session.json` поддерживается только как проекция для session `active`.
- Единое проектное состояние правил живет в `.madspec/system/policy/state.json`, `.madspec/system/policy/proposals.jsonl`, `.madspec/system/policy/history.jsonl`, а `.madspec/system/policy.md` является производным представлением правил.
- Единое проектное состояние субагентных ролей живет в `.madspec/system/agents/state.json`, `.madspec/system/agents/proposals.jsonl`, `.madspec/system/agents/history.jsonl`, а `.madspec/system/agents.md` является производным представлением профиля среды и ролей.
- Каноническое состояние слоя изменений ветки живет в `.madspec/<branch>/change/state.json`, `.madspec/<branch>/change/proposals.jsonl` и `.madspec/<branch>/change/history.jsonl`, а `change-summary.md` и пакет экспорта являются производными представлениями.
- Каноническое состояние слоя контрольных проверок ветки живет в `.madspec/<branch>/gates/state.json`, `.madspec/<branch>/gates/proposals.jsonl` и `.madspec/<branch>/gates/history.jsonl`, а summaries внутри `project-context.md`, `review.md` и `security-audit.md` являются производными представлениями.
- Markdown-файлы контекста часто являются производными представлениями, а не каноническими данными.

## Как мыслить об источнике истины

- Сначала читай каноническое состояние, потом производные Markdown-файлы.
- Если состояние ветки хранится в структурированной памяти, не правь производные представления вручную.
- Если нужна проверка, сначала пересобери представления через соответствующие команды CLI, потом валидируй их.
- Для операций, привязанных к ветке, используй CLI MADSpec, а не собственную shell-логику.

## Когда обращаться к этому файлу

Открывай этот reference-файл, если нужно:

- понять, где каноническое состояние, а где производное
- разобраться, что хранится в `.madspec/system/` и что в `.madspec/<branch>/`
- восстановить ментальную модель перед работой с памятью, правилами, gates, change-пакетами или субагентами
