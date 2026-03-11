# Security/Privacy Audit: [НАЗВАНИЕ_ПРОЕКТА / CHANGE SET]

**Дата аудита**: [ДАТА]
**Ветка**: [ВЕТКА]
**Scope**: [default / release / privacy / deep]

> Используй этот шаблон как структуру мышления для pragmatic security/privacy audit. Источник истины находится в structured memory, а итоговый `security-audit.md` в MADSpec считается generated view.

## 1. Scope И Ограничения

- **Что проверялось**: [код / зависимости / deployment context / data handling]
- **Использованный контекст**: [tech-stack.md / architecture.md / deployment.md / progress.json / manifests]
- **Ограничения анализа**:
  - [отсутствует deployment context]
  - [не выполнено dependency scan]
  - [нехватка evidence по policy/process слою]

## 2. Severity Summary

- **Critical**: [кол-во]
- **High**: [кол-во]
- **Medium**: [кол-во]
- **Low**: [кол-во]

## 3. Findings По Категориям

### Authn/Authz
- **[Severity] [Finding]**
  - **Где**: `[путь/к/файлу]`
  - **Описание**: [что найдено]
  - **Риск**: [к чему может привести]
  - **Рекомендуемое исправление**: [что сделать]

### Secrets И Credentials
- [Finding]

### Input Validation / Injection
- [Finding]

### Dependencies / Supply Chain
- [Finding]

### Storage / Transport / Logging
- [Finding]

### External Integrations / Files / SSRF-like Risks
- [Finding]

## 4. Персональные Данные И 152-ФЗ

- **Какие ПД обрабатываются**: [email / phone / name / etc]
- **Где проходит обработка**: [модули / endpoints / storage]
- **Наблюдаемые меры защиты**: [шифрование / ограничение доступа / masking]
- **Gaps или limitations**:
  - [отсутствует явная цель обработки]
  - [ПД видны в логах]
  - [не видны механизмы удаления или ограничения доступа]

## 5. Remediation Plan

### Срочно
- [Действие 1]
- [Действие 2]

### В Ближайшее Время
- [Действие 1]
- [Действие 2]

### Позже
- [Действие 1]
- [Действие 2]

## 6. Следующие Шаги

- [Какие исправления сделать первыми]
- [Нужно ли обновить deployment context]
- [Нужно ли повторить audit после изменений]
