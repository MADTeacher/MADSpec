#!/usr/bin/env bash
# Определение текущей ветки MADSpec и вывод в stdout
BRANCH=""
if [ -f .madspec/config.json ]; then
  BRANCH=$(grep -o '"currentBranch"[[:space:]]*:[[:space:]]*"[^"]*"' .madspec/config.json | cut -d'"' -f4)
fi
if [ -z "$BRANCH" ] && command -v git >/dev/null 2>&1; then
  BRANCH=$(git branch --show-current 2>/dev/null || echo "")
fi
if [ -z "$BRANCH" ]; then
  BRANCH="main"
fi
echo "$BRANCH"
