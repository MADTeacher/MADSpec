#!/usr/bin/env bash
set -euo pipefail

# create-release-packages.sh (workflow-local)
# Build MADSpec template release archives for each supported AI assistant.
# Usage: .github/workflows/scripts/create-release-packages.sh <version>
#   Version argument should include leading 'v'.
#   Optionally set AGENTS env var to limit what gets built.
#     AGENTS  : space or comma separated subset of: cursor-agent opencode kilocode roo sourcecraft copilot (default: all)

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
    body=$(sed "s/{ARGS}/$arg_format/g; s/__AGENT__/$agent/g" <<< "$body" | rewrite_paths)

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
      [[ -d skills ]] && { mkdir -p "$base_dir/.cursor/skills"; cp -r skills/* "$base_dir/.cursor/skills/"; echo "Copied skills -> .cursor/skills"; }
      ;;
    opencode)
      mkdir -p "$base_dir/.opencode/command"
      generate_commands opencode md "\$ARGUMENTS" "$base_dir/.opencode/command"
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
    copilot)
      mkdir -p "$base_dir/.github/agents"
      generate_commands copilot agent.md "\$ARGUMENTS" "$base_dir/.github/agents"
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
ALL_AGENTS=(cursor-agent opencode kilocode roo sourcecraft copilot)

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
