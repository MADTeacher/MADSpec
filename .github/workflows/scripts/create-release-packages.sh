#!/usr/bin/env bash
set -euo pipefail

# create-release-packages.sh (workflow-local)
# Build MADSpec template release archives for each supported AI assistant and script type.
# Usage: .github/workflows/scripts/create-release-packages.sh <version>
#   Version argument should include leading 'v'.
#   Optionally set AGENTS and/or SCRIPTS env vars to limit what gets built.
#     AGENTS  : space or comma separated subset of: cursor-agent opencode kilocode roo sourcecraft (default: all)
#     SCRIPTS : space or comma separated subset of: sh ps (default: both)

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
  # Skip lines that already have .madspec/ before the target directory to prevent duplication
  sed -E \
    -e '/\.madspec\/scripts\//!s@(^|[[:space:]]|`)(/?)scripts/@\1.madspec/scripts/@g' \
    -e '/\.madspec\/templates\//!s@(^|[[:space:]]|`)(/?)templates/@\1.madspec/templates/@g'
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
  local agent=$1 ext=$2 arg_format=$3 output_dir=$4 script_variant=$5
  mkdir -p "$output_dir"
  for template in templates/commands/*.md; do
    [[ -f "$template" ]] || continue
    local name description script_command body
    name=$(basename "$template" .md)
    
    # Normalize line endings
    file_content=$(tr -d '\r' < "$template")
    
    # Extract description and script command from YAML frontmatter
    # Use grep + sed instead of awk with pipe to avoid broken pipe errors
    description=$(grep -m1 '^description:' <<< "$file_content" | sed 's/^description:[[:space:]]*//' || true)
    script_command=$(grep -m1 "^[[:space:]]*${script_variant}:" <<< "$file_content" | sed "s/^[[:space:]]*${script_variant}:[[:space:]]*//" || true)
    
    if [[ -z $script_command ]]; then
      # Empty script command is OK for MADSpec (most commands don't use external scripts)
      script_command=""
    fi
    
    # Replace {SCRIPT} placeholder with the script command
    body=$(sed "s|{SCRIPT}|${script_command}|g" <<< "$file_content")
    
    # Remove the scripts: section from frontmatter while preserving YAML structure
    # Use here-string instead of pipe to avoid broken pipe errors
    body=$(awk '
      /^---$/ { print; if (++dash_count == 1) in_frontmatter=1; else in_frontmatter=0; next }
      in_frontmatter && /^scripts:$/ { skip_scripts=1; next }
      in_frontmatter && /^[a-zA-Z].*:/ && skip_scripts { skip_scripts=0 }
      in_frontmatter && skip_scripts && /^[[:space:]]/ { next }
      { print }
    ' <<< "$body")
    
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
  local agent=$1 script=$2
  local base_dir="$GENRELEASES_DIR/madspec-${agent}-package-${script}"
  echo "Building $agent ($script) package..."
  mkdir -p "$base_dir"
  
  # Copy base structure but filter scripts by variant
  MADSPEC_DIR="$base_dir/.madspec"
  mkdir -p "$MADSPEC_DIR"
  
  # Only copy the relevant script variant directory
  if [[ -d scripts ]]; then
    mkdir -p "$MADSPEC_DIR/scripts"
    case $script in
      sh)
        [[ -d scripts/bash ]] && { cp -r scripts/bash "$MADSPEC_DIR/scripts/"; echo "Copied scripts/bash -> .madspec/scripts"; }
        # Copy any script files that aren't in variant-specific directories
        find scripts -maxdepth 1 -type f -exec cp {} "$MADSPEC_DIR/scripts/" \; 2>/dev/null || true
        ;;
      ps)
        [[ -d scripts/powershell ]] && { cp -r scripts/powershell "$MADSPEC_DIR/scripts/"; echo "Copied scripts/powershell -> .madspec/scripts"; }
        # Copy any script files that aren't in variant-specific directories
        find scripts -maxdepth 1 -type f -exec cp {} "$MADSPEC_DIR/scripts/" \; 2>/dev/null || true
        ;;
    esac
  fi
  
  [[ -d templates ]] && { mkdir -p "$MADSPEC_DIR/templates"; find templates -type f -not -path "templates/commands/*" -exec cp --parents {} "$MADSPEC_DIR"/ \; ; echo "Copied templates -> .madspec/templates"; }

  case $agent in
    cursor-agent)
      mkdir -p "$base_dir/.cursor/commands"
      generate_commands cursor-agent md "\$ARGUMENTS" "$base_dir/.cursor/commands" "$script"
      [[ -d skills ]] && { mkdir -p "$base_dir/.cursor/skills"; cp -r skills/* "$base_dir/.cursor/skills/"; echo "Copied skills -> .cursor/skills"; }
      ;;
    opencode)
      mkdir -p "$base_dir/.opencode/command"
      generate_commands opencode md "\$ARGUMENTS" "$base_dir/.opencode/command" "$script"
      [[ -d skills ]] && { mkdir -p "$base_dir/.opencode/skills"; cp -r skills/* "$base_dir/.opencode/skills/"; echo "Copied skills -> .opencode/skills"; }
      ;;
    kilocode)
      mkdir -p "$base_dir/.kilocode/rules"
      generate_commands kilocode md "\$ARGUMENTS" "$base_dir/.kilocode/rules" "$script"
      [[ -d skills ]] && { mkdir -p "$base_dir/.kilocode/skills"; cp -r skills/* "$base_dir/.kilocode/skills/"; echo "Copied skills -> .kilocode/skills"; }
      ;;
    roo)
      mkdir -p "$base_dir/.roo/rules"
      generate_commands roo md "\$ARGUMENTS" "$base_dir/.roo/rules" "$script"
      [[ -d skills ]] && { mkdir -p "$base_dir/.roo/skills"; cp -r skills/* "$base_dir/.roo/skills/"; echo "Copied skills -> .roo/skills"; }
      ;;
    sourcecraft)
      mkdir -p "$base_dir/.codeassistant/commands"
      generate_commands sourcecraft md "\$ARGUMENTS" "$base_dir/.codeassistant/commands" "$script"
      [[ -d skills ]] && { mkdir -p "$base_dir/.codeassistant/skills"; cp -r skills/* "$base_dir/.codeassistant/skills/"; echo "Copied skills -> .codeassistant/skills"; }
      ;;
    copilot)
      mkdir -p "$base_dir/.github/agents"
      generate_commands copilot agent.md "\$ARGUMENTS" "$base_dir/.github/agents" "$script"
      # Generate companion prompt files
      generate_copilot_prompts "$base_dir/.github/agents" "$base_dir/.github/prompts"
      # Create VS Code workspace settings
      mkdir -p "$base_dir/.vscode"
      [[ -f templates/vscode-settings.json ]] && cp templates/vscode-settings.json "$base_dir/.vscode/settings.json"
      [[ -d skills ]] && { mkdir -p "$base_dir/.github/skills"; cp -r skills/* "$base_dir/.github/skills/"; echo "Copied skills -> .github/skills"; }
      ;;
  esac
  ( cd "$base_dir" && zip -r "../madspec-template-${agent}-${script}-${NEW_VERSION}.zip" . )
  echo "Created $GENRELEASES_DIR/madspec-template-${agent}-${script}-${NEW_VERSION}.zip"
}

# Determine agent list
ALL_AGENTS=(cursor-agent opencode kilocode roo sourcecraft copilot)
ALL_SCRIPTS=(sh ps)

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

if [[ -n ${SCRIPTS:-} ]]; then
  mapfile -t SCRIPT_LIST < <(printf '%s' "$SCRIPTS" | norm_list)
  validate_subset script ALL_SCRIPTS "${SCRIPT_LIST[@]}" || exit 1
else
  SCRIPT_LIST=("${ALL_SCRIPTS[@]}")
fi

echo "Agents: ${AGENT_LIST[*]}"
echo "Scripts: ${SCRIPT_LIST[*]}"

for agent in "${AGENT_LIST[@]}"; do
  for script in "${SCRIPT_LIST[@]}"; do
    build_variant "$agent" "$script"
  done
done

echo "Archives in $GENRELEASES_DIR:"
ls -1 "$GENRELEASES_DIR"/madspec-template-*-"${NEW_VERSION}".zip

