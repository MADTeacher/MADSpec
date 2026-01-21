#!/usr/bin/env bash
# Определение текущей ветки MADSpec и вывод в stdout
BRANCH=""
# Сначала проверяем текущую ветку Git (как наиболее актуальный источник)
if command -v git >/dev/null 2>&1; then
  BRANCH=$(git branch --show-current 2>/dev/null || echo "")
fi
# Если Git недоступен или не может определить ветку, используем config.json
if [ -z "$BRANCH" ] && [ -f .madspec/config.json ]; then
  BRANCH=$(grep -o '"currentBranch"[[:space:]]*:[[:space:]]*"[^"]*"' .madspec/config.json | cut -d'"' -f4)
fi
# Последний fallback на main
if [ -z "$BRANCH" ]; then
  BRANCH="main"
fi
echo "$BRANCH"
