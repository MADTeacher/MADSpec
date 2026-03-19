#!/usr/bin/env bash
set -euo pipefail

# create-release-packages.sh (workflow-local)
# Build MADSpec template release archives for each supported AI assistant.
# Usage: .github/workflows/scripts/create-release-packages.sh <version>
#   Version argument should include leading 'v'.
#   Optionally set AGENTS env var to limit what gets built.
#     AGENTS  : space or comma separated subset of: cursor-agent opencode kilocode roo sourcecraft qwen copilot (default: all)

if [[ $# -ne 1 ]]; then
  echo "Usage: $0 <version-with-v-prefix>" >&2
  exit 1
fi
NEW_VERSION="$1"
if [[ ! $NEW_VERSION =~ ^v[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
  echo "Version must look like v0.0.0" >&2
  exit 1
fi

echo "Building release packages for $NEW_VERSION"

# Create and use .genreleases directory for all build artifacts
GENRELEASES_DIR=".genreleases"
mkdir -p "$GENRELEASES_DIR"
rm -rf "$GENRELEASES_DIR"/* || true

rewrite_paths() {
  sed -E \
    -e '/\.madspec\/templates\//!s@(^|[[:space:]]|`)(/?)templates/@\1.madspec/templates/@g'
}

copy_tree_preserving_paths() {
  local source_root=$1 target_root=$2
  while IFS= read -r -d '' file; do
    local relative_path=${file#"$source_root"/}
    mkdir -p "$target_root/$(dirname "$relative_path")"
    cp "$file" "$target_root/$relative_path"
  done < <(find "$source_root" -type f -print0)
}

generate_copilot_prompts() {
  local agents_dir=$1 prompts_dir=$2
  mkdir -p "$prompts_dir"

  # Generate a .prompt.md file for each .agent.md file
  for agent_file in "$agents_dir"/*.agent.md; do
    [[ -f "$agent_file" ]] || continue

    local basename=$(basename "$agent_file" .agent.md)
    local prompt_file="$prompts_dir/${basename}.prompt.md"

    # Create prompt file with agent frontmatter
    cat > "$prompt_file" <<EOF
---
agent: ${basename}
---
EOF
  done
}

render_subagent_frontmatter() {
  local agent=$1 role=$2
  case $agent in
    cursor-agent)
      case $role in
        architecture)
          cat <<EOF
---
description: Designs architecture, boundaries, contracts, and tradeoffs for the current product and repository.
execution_mode_hint: sequential
---
EOF
          ;;
        developer)
          cat <<EOF
---
description: Implements planned code changes, integrates solutions, and validates development steps in the current repository.
execution_mode_hint: parallel
dependencies: ["architecture"]
---
EOF
          ;;
        contracts-data)
          cat <<EOF
---
description: Owns API contracts, data structures, schema boundaries, and integration-facing data consistency.
execution_mode_hint: sequential
dependencies: ["architecture"]
---
EOF
          ;;
        testing)
          cat <<EOF
---
description: Сосредоточен на пробелах в покрытии, проектировании тестов, стратегии проверки и подтверждении реализации.
execution_mode_hint: parallel
dependencies: ["architecture"]
---
EOF
          ;;
        security)
          cat <<EOF
---
description: Проверяет безопасность, приватность, поверхность атаки, риски зависимостей и защитные меры.
execution_mode_hint: parallel
---
EOF
          ;;
        research)
          cat <<EOF
---
description: Исследует контекст репозитория, неизвестные факторы и подтверждающие данные по текущему продукту и кодовой базе.
execution_mode_hint: parallel
---
EOF
          ;;
        docs)
          cat <<EOF
---
description: Поддерживает техническую и процессную документацию в соответствии с текущим состоянием репозитория и сгенерированных артефактов.
execution_mode_hint: parallel
---
EOF
          ;;
      esac
      ;;
    opencode)
      case $role in
        architecture)
          cat <<EOF
---
name: Архитектурный специалист
description: Отвечает за архитектуру, границы системы, контракты и ключевые компромиссы текущего продукта и репозитория.
mode: subagent
hidden: true
tools:
  edit: false
  write: false
  bash: false
---
EOF
          ;;
        developer)
          cat <<EOF
---
name: Специалист по разработке
description: Реализует запланированные изменения в коде, встраивает решения и подтверждает шаги разработки в текущем репозитории.
mode: subagent
hidden: true
tools:
  edit: true
  write: true
  bash: true
---
EOF
          ;;
        contracts-data)
          cat <<EOF
---
name: Специалист по контрактам и данным
description: Отвечает за API-контракты, структуры данных, границы схем и согласованность данных на интеграциях.
mode: subagent
hidden: true
tools:
  edit: false
  write: false
  bash: false
---
EOF
          ;;
        testing)
          cat <<EOF
---
name: Специалист по тестированию
description: Сосредоточен на пробелах в покрытии, проектировании тестов, стратегии проверки и подтверждении реализации.
mode: subagent
hidden: true
tools:
  edit: true
  write: true
  bash: true
---
EOF
          ;;
        security)
          cat <<EOF
---
name: Специалист по безопасности
description: Проверяет безопасность, приватность, поверхность атаки, риски зависимостей и защитные меры.
mode: subagent
hidden: true
tools:
  edit: false
  write: false
  bash: true
---
EOF
          ;;
        research)
          cat <<EOF
---
name: Исследователь репозитория
description: Исследует контекст репозитория, неизвестные факторы и подтверждающие данные по текущему продукту и кодовой базе.
mode: subagent
hidden: true
tools:
  edit: false
  write: false
  bash: false
---
EOF
          ;;
        docs)
          cat <<EOF
---
name: Специалист по документации
description: Поддерживает техническую и процессную документацию в соответствии с текущим состоянием репозитория и сгенерированных артефактов.
mode: subagent
hidden: true
tools:
  edit: true
  write: true
  bash: false
---
EOF
          ;;
      esac
      ;;
    qwen)
      case $role in
        architecture)
          cat <<EOF
---
name: Архитектурный специалист
description: Отвечает за архитектуру, границы системы, контракты и ключевые компромиссы текущего продукта и репозитория.
tools: ["read_file", "glob", "grep_search"]
---
EOF
          ;;
        developer)
          cat <<EOF
---
name: Специалист по разработке
description: Реализует запланированные изменения в коде, встраивает решения и подтверждает шаги разработки в текущем репозитории.
tools: ["read_file", "glob", "grep_search", "edit", "write_file", "run_shell_command"]
---
EOF
          ;;
        contracts-data)
          cat <<EOF
---
name: Специалист по контрактам и данным
description: Отвечает за API-контракты, структуры данных, границы схем и согласованность данных на интеграциях.
tools: ["read_file", "glob", "grep_search"]
---
EOF
          ;;
        testing)
          cat <<EOF
---
name: Специалист по тестированию
description: Сосредоточен на пробелах в покрытии, проектировании тестов, стратегии проверки и подтверждении реализации.
tools: ["read_file", "glob", "grep_search", "edit", "write_file", "run_shell_command"]
---
EOF
          ;;
        security)
          cat <<EOF
---
name: Специалист по безопасности
description: Проверяет безопасность, приватность, поверхность атаки, риски зависимостей и защитные меры.
tools: ["read_file", "glob", "grep_search", "run_shell_command"]
---
EOF
          ;;
        research)
          cat <<EOF
---
name: Исследователь репозитория
description: Исследует контекст репозитория, неизвестные факторы и подтверждающие данные по текущему продукту и кодовой базе.
tools: ["read_file", "glob", "grep_search"]
---
EOF
          ;;
        docs)
          cat <<EOF
---
name: Специалист по документации
description: Поддерживает техническую и процессную документацию в соответствии с текущим состоянием репозитория и сгенерированных артефактов.
tools: ["read_file", "glob", "grep_search", "edit", "write_file"]
---
EOF
          ;;
      esac
      ;;
    copilot)
      case $role in
        architecture)
          cat <<EOF
---
name: Архитектурный специалист
description: Отвечает за архитектуру, границы системы, контракты и ключевые компромиссы текущего продукта и репозитория.
target: vscode
user-invocable: false
tools: ["read", "search"]
---
EOF
          ;;
        developer)
          cat <<EOF
---
name: Специалист по разработке
description: Реализует запланированные изменения в коде, встраивает решения и подтверждает шаги разработки в текущем репозитории.
target: vscode
user-invocable: false
tools: ["read", "search", "edit", "terminal"]
---
EOF
          ;;
        contracts-data)
          cat <<EOF
---
name: Специалист по контрактам и данным
description: Отвечает за API-контракты, структуры данных, границы схем и согласованность данных на интеграциях.
target: vscode
user-invocable: false
tools: ["read", "search"]
---
EOF
          ;;
        testing)
          cat <<EOF
---
name: Специалист по тестированию
description: Сосредоточен на пробелах в покрытии, проектировании тестов, стратегии проверки и подтверждении реализации.
target: vscode
user-invocable: false
tools: ["read", "search", "edit", "terminal"]
---
EOF
          ;;
        security)
          cat <<EOF
---
name: Специалист по безопасности
description: Проверяет безопасность, приватность, поверхность атаки, риски зависимостей и защитные меры.
target: vscode
user-invocable: false
tools: ["read", "search", "terminal"]
---
EOF
          ;;
        research)
          cat <<EOF
---
name: Исследователь репозитория
description: Исследует контекст репозитория, неизвестные факторы и подтверждающие данные по текущему продукту и кодовой базе.
target: vscode
user-invocable: false
tools: ["read", "search"]
---
EOF
          ;;
        docs)
          cat <<EOF
---
name: Специалист по документации
description: Поддерживает техническую и процессную документацию в соответствии с текущим состоянием репозитория и сгенерированных артефактов.
target: vscode
user-invocable: false
tools: ["read", "search", "edit"]
---
EOF
          ;;
      esac
      ;;
  esac
}

generate_subagents() {
  local agent=$1 output_dir=$2 ext=$3
  mkdir -p "$output_dir"
  for template in templates/subagents/*.md; do
    [[ -f "$template" ]] || continue
    local role body file_name
    role=$(basename "$template" .md)
    body=$(tr -d '\r' < "$template" | rewrite_paths)
    file_name="madspec-${role}.${ext}"
    {
      render_subagent_frontmatter "$agent" "$role"
      printf '\n%s\n' "$body"
    } > "$output_dir/$file_name"
  done
}

generate_commands() {
  local agent=$1 ext=$2 arg_format=$3 output_dir=$4
  mkdir -p "$output_dir"
  for template in templates/commands/*.md; do
    [[ -f "$template" ]] || continue
    local name body
    name=$(basename "$template" .md)

    # Normalize line endings
    file_content=$(tr -d '\r' < "$template")

    body="$file_content"

    # Apply other substitutions
    body=$(sed "s|{ARGS}|$arg_format|g; s|\\\$ARGUMENTS|$arg_format|g; s|__AGENT__|$agent|g" <<< "$body" | rewrite_paths)

    case $ext in
      md)
        echo "$body" > "$output_dir/$name.$ext" ;;
      agent.md)
        echo "$body" > "$output_dir/$name.$ext" ;;
    esac
  done
}

build_variant() {
  local agent=$1
  local base_dir="$GENRELEASES_DIR/madspec-${agent}-package"
  echo "Building $agent package..."
  mkdir -p "$base_dir"
  
  MADSPEC_DIR="$base_dir/.madspec"
  mkdir -p "$MADSPEC_DIR"
  
  [[ -d templates ]] && {
    mkdir -p "$MADSPEC_DIR/templates"
    while IFS= read -r -d '' template_file; do
      relative_path=${template_file#"templates/"}
      mkdir -p "$MADSPEC_DIR/templates/$(dirname "$relative_path")"
      cp "$template_file" "$MADSPEC_DIR/templates/$relative_path"
    done < <(find templates -type f ! -path "templates/commands/*" -print0)
    echo "Copied templates -> .madspec/templates"
  }
  [[ -d procedures ]] && { mkdir -p "$MADSPEC_DIR/procedures"; cp -rp procedures/* "$MADSPEC_DIR/procedures/"; echo "Copied procedures -> .madspec/procedures"; }

  case $agent in
    cursor-agent)
      mkdir -p "$base_dir/.cursor/commands"
      generate_commands cursor-agent md "\$ARGUMENTS" "$base_dir/.cursor/commands"
      mkdir -p "$base_dir/.cursor/agents"
      generate_subagents cursor-agent "$base_dir/.cursor/agents" "md"
      [[ -d skills ]] && { mkdir -p "$base_dir/.cursor/skills"; cp -r skills/* "$base_dir/.cursor/skills/"; echo "Copied skills -> .cursor/skills"; }
      ;;
    opencode)
      mkdir -p "$base_dir/.opencode/commands"
      generate_commands opencode md "\$ARGUMENTS" "$base_dir/.opencode/commands"
      mkdir -p "$base_dir/.opencode/agents"
      generate_subagents opencode "$base_dir/.opencode/agents" "md"
      [[ -d skills ]] && { mkdir -p "$base_dir/.opencode/skills"; cp -r skills/* "$base_dir/.opencode/skills/"; echo "Copied skills -> .opencode/skills"; }
      ;;
    kilocode)
      mkdir -p "$base_dir/.kilocode/rules"
      generate_commands kilocode md "\$ARGUMENTS" "$base_dir/.kilocode/rules"
      [[ -d skills ]] && { mkdir -p "$base_dir/.kilocode/skills"; cp -r skills/* "$base_dir/.kilocode/skills/"; echo "Copied skills -> .kilocode/skills"; }
      ;;
    roo)
      mkdir -p "$base_dir/.roo/rules"
      generate_commands roo md "\$ARGUMENTS" "$base_dir/.roo/rules"
      [[ -d skills ]] && { mkdir -p "$base_dir/.roo/skills"; cp -r skills/* "$base_dir/.roo/skills/"; echo "Copied skills -> .roo/skills"; }
      ;;
    sourcecraft)
      mkdir -p "$base_dir/.codeassistant/commands"
      generate_commands sourcecraft md "\$ARGUMENTS" "$base_dir/.codeassistant/commands"
      [[ -d skills ]] && { mkdir -p "$base_dir/.codeassistant/skills"; cp -r skills/* "$base_dir/.codeassistant/skills/"; echo "Copied skills -> .codeassistant/skills"; }
      ;;
    qwen)
      mkdir -p "$base_dir/.qwen/commands"
      generate_commands qwen md "{{args}}" "$base_dir/.qwen/commands"
      mkdir -p "$base_dir/.qwen/agents"
      generate_subagents qwen "$base_dir/.qwen/agents" "md"
      [[ -d skills ]] && { mkdir -p "$base_dir/.qwen/skills"; cp -r skills/* "$base_dir/.qwen/skills/"; echo "Copied skills -> .qwen/skills"; }
      ;;
    copilot)
      mkdir -p "$base_dir/.github/agents"
      generate_commands copilot agent.md "\$ARGUMENTS" "$base_dir/.github/agents"
      generate_subagents copilot "$base_dir/.github/agents" "agent.md"
      # Generate companion prompt files
      generate_copilot_prompts "$base_dir/.github/agents" "$base_dir/.github/prompts"
      # Create VS Code workspace settings
      mkdir -p "$base_dir/.vscode"
      [[ -f templates/vscode-settings.json ]] && cp templates/vscode-settings.json "$base_dir/.vscode/settings.json"
      [[ -d skills ]] && { mkdir -p "$base_dir/.github/skills"; cp -r skills/* "$base_dir/.github/skills/"; echo "Copied skills -> .github/skills"; }
      ;;
  esac

  ( cd "$base_dir" && zip -r "../madspec-template-${agent}-${NEW_VERSION}.zip" . )
  echo "Created $GENRELEASES_DIR/madspec-template-${agent}-${NEW_VERSION}.zip"
}

# Determine agent list
ALL_AGENTS=(cursor-agent opencode kilocode roo sourcecraft qwen copilot)

norm_list() {
  # convert comma+space separated -> line separated unique while preserving order of first occurrence
  tr ',\n' '  ' | awk '{for(i=1;i<=NF;i++){if(!seen[$i]++){printf((out?"\n":"") $i);out=1}}}END{printf("\n")}'
}

validate_subset() {
  local type=$1; shift; local -n allowed=$1; shift; local items=("$@")
  local invalid=0
  for it in "${items[@]}"; do
    local found=0
    for a in "${allowed[@]}"; do [[ $it == "$a" ]] && { found=1; break; }; done
    if [[ $found -eq 0 ]]; then
      echo "Error: unknown $type '$it' (allowed: ${allowed[*]})" >&2
      invalid=1
    fi
  done
  return $invalid
}

if [[ -n ${AGENTS:-} ]]; then
  mapfile -t AGENT_LIST < <(printf '%s' "$AGENTS" | norm_list)
  validate_subset agent ALL_AGENTS "${AGENT_LIST[@]}" || exit 1
else
  AGENT_LIST=("${ALL_AGENTS[@]}")
fi

echo "Agents: ${AGENT_LIST[*]}"

for agent in "${AGENT_LIST[@]}"; do
  build_variant "$agent"
done

echo "Archives in $GENRELEASES_DIR:"
ls -1 "$GENRELEASES_DIR"/madspec-template-*-"${NEW_VERSION}".zip
