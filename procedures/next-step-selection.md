# Выбор следующего шага

1. Прочитай `.madspec/<BRANCH>/memory/progress.json`.
2. Получи семантические ограничения для текущей стадии.
3. Для планирования проверь идентификатор кандидата в шаг и его зависимости через `madspec memory next-step`.
4. Регистрируй принятые плановые шаги только через `madspec memory register-step`.
5. Для реализации используй `madspec memory next-step --stage <implement-stage>`, чтобы выбрать следующий исполнимый шаг.
6. Зафиксируй принятое решение в `memory/working/decision-log.jsonl`.
