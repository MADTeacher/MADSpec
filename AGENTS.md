# AGENTS.md

## About MADSpec and MADSpec CLI

**MADSpec (MADSpec Framework)** - is an experimental framework for software development using LLM agents.

**MADSpec CLI** - is a command-line interface that loads projects with MADSpec templates. It sets up the necessary directory structures, templates, and AI agent integrations.

The framework supports multiple AI agents, allowing teams to use their preferred tools while maintaining a consistent project structure and development practices.

---

## General practices

- Any changes to `__init__.py` for MADSpec CLI require updating the version in `pyproject.toml`
- All command changes require testing with each supported agent
- Any change to the content or workflow of any `madspec.*` framework command must update that command's documentation in the same change
- Any CLI change that affects commands, arguments, output shape, workflow behavior, or generated project structure must update the CLI documentation in `docs/cli/` in the same change
- If a `madspec.*` workflow command change also affects CLI usage or behavior, update both the workflow docs and the corresponding `docs/cli/` reference in the same change
- Any CLI change that affects commands, arguments, workflow, generated project structure, or agent-facing troubleshooting must update `skills/madspec-cli-operator/SKILL.md` in the same change

## Adding New Agent Support

This section explains how to add support for new AI agents/assistants to MADSpec CLI. Use this guide when integrating new AI tools.

### Overview

MADSpec supports multiple AI agents by generating agent-specific command files and directory structures when initializing projects. Each agent has its own conventions for:

- **Command file formats** (Markdown, TOML, etc.)
- **Directory structures** (`.cursor/commands/`, `.codeassistant/commands/`, etc.)
- **Command invocation patterns** (slash commands, CLI tools, etc.)
- **Argument passing conventions** (`$ARGUMENTS`, `{{args}}`, etc.)

### Current Supported Agents

| Agent                      | Directory              | Format   | CLI Tool        | Description                 |
| -------------------------- | ---------------------- | -------- | --------------- | --------------------------- |
| **Cursor**                 | `.cursor/commands/`    | Markdown | N/A (IDE-based) | Cursor IDE                  |
| **opencode**               | `.opencode/command/`   | Markdown | `opencode`      | opencode CLI                |
| **Kilo Code**              | `.kilocode/rules/`     | Markdown | N/A (IDE-based) | Kilo Code IDE               |
| **Roo Code**               | `.roo/rules/`          | Markdown | N/A (IDE-based) | Roo Code IDE                |
| **SourceCraft**            | `.codeassistant/commands/` | Markdown | N/A (IDE-based) | SourceCraft IDE         |
| **Qwen Code**              | `.qwen/commands/`      | Markdown | `qwen`          | Qwen Code CLI               |
| **GitHub Copilot**         | `.github/agents/`      | Markdown | N/A (IDE-based) | GitHub Copilot in VS Code   |

### Step-by-Step Integration Guide

Follow these steps to add a new agent (using a hypothetical new agent as an example):

#### 1. Add to AGENT_CONFIG

**IMPORTANT**: Use the actual CLI tool name as the key, not a shortened version.

Add the new agent to the `AGENT_CONFIG` dictionary in `src/madspec_cli/config.py`. This is the **single source of truth** for all agent metadata:

```python
AGENT_CONFIG = {
    # ... existing agents ...
    "new-agent-cli": AgentConfig(
        name="New Agent Display Name",
        folder=".newagent/",
        commands_subdir="commands",
        install_url="https://example.com/install",
        requires_cli=True,
    ),
}
```

**Key Design Principle**: The dictionary key should match the actual executable name that users install. For example:

- ✅ Use `"cursor-agent"` because the CLI tool is literally called `cursor-agent`
- ❌ Don't use `"cursor"` as a shortcut if the tool is `cursor-agent`

This eliminates the need for special-case mappings throughout the codebase.

**Field Explanations**:

- `name`: Human-readable display name shown to users
- `folder`: Directory where agent-specific files are stored (relative to project root)
- `commands_subdir`: Subdirectory under the agent folder where commands are generated
- `install_url`: Installation documentation URL (set to `None` for IDE-based agents)
- `requires_cli`: Whether the agent requires a CLI tool check during initialization

#### 2. Update CLI Help Text

Update the `--ai` parameter help text in the `init()` command to include the new agent:

```python
ai_assistant: str = typer.Option(None, "--ai", help="AI assistant to use: cursor-agent, opencode, kilocode, roo, sourcecraft, qwen, copilot, or new-agent-cli"),
```

Also update any function docstrings, examples, and error messages that list available agents.

#### 3. Update README Documentation

Update the **Supported AI Agents** section in `README.md` to include the new agent:

- Add the new agent to the table
- Include the agent's official website link
- Add any relevant notes about the agent's implementation
- Ensure the table formatting remains aligned and consistent

#### 4. Update Release Package Script

Modify `.github/workflows/scripts/create-release-packages.sh`:

##### Add to ALL_AGENTS array

```bash
ALL_AGENTS=(cursor-agent opencode kilocode roo sourcecraft qwen new-agent)
```

##### Add case statement for directory structure

```bash
case $agent in
  # ... existing cases ...
  new-agent)
    mkdir -p "$base_dir/.newagent/commands"
    generate_commands new-agent md "\$ARGUMENTS" "$base_dir/.newagent/commands" ;;
  qwen)
    mkdir -p "$base_dir/.qwen/commands"
    generate_commands qwen md "{{args}}" "$base_dir/.qwen/commands" ;;
esac
```

##### Generate MVP and Feature commands

**IMPORTANT**: The script must generate commands with prefixes `madspec.mvp.*` and `madspec.feature.*`:

- **MVP commands**: `madspec.mvp.concept`, `madspec.mvp.design`, `madspec.mvp.tech`, `madspec.mvp.architecture`, `madspec.mvp.plan`, `madspec.mvp.implement`
- **Feature commands**: `madspec.feature.init`, `madspec.feature.plan`, `madspec.feature.implement`
- **General commands**: `madspec.deploy`, `madspec.security`, `madspec.review`

All commands should rely on `madspec git current-branch` for branch detection instead of shipping shell/PowerShell helper scripts.

#### 5. Update GitHub Release Script

Modify `.github/workflows/scripts/create-github-release.sh` to include the new agent's packages:

```bash
gh release create "$VERSION" \
  # ... existing packages ...
  .genreleases/pldf-template-new-agent-"$VERSION".zip \
  # Add new agent packages here
```

#### 6. Update CLI Tool Checks (Optional)

For agents that require CLI tools, the checks are handled automatically based on the `requires_cli` field in AGENT_CONFIG. No additional code changes needed in the `check()` or `init()` commands - they automatically loop through AGENT_CONFIG and check tools as needed.

## Agent Categories

### CLI-Based Agents

Require a command-line tool to be installed:

- **opencode**: `opencode` CLI
- **Qwen Code**: `qwen` CLI

### IDE-Based Agents

Work within integrated development environments:

- **Cursor**: Built into Cursor IDE
- **Kilo Code**: Built into Kilo Code IDE
- **Roo Code**: Built into Roo Code IDE
- **SourceCraft**: Built into SourceCraft IDE

## Command File Formats

### Markdown Format

Used by: Cursor, opencode, Kilo Code, Roo Code, SourceCraft, Qwen Code

**Standard format:**

```markdown
---
description: "Command description"
---

Command content with the agent-specific arguments placeholder.
```

**Important:** Commands call MADSpec CLI directly for branch and git operations, for example `madspec git current-branch`, `madspec git init`, and `madspec git commit`.

## Directory Conventions

- **Cursor**: `.cursor/commands/`
- **opencode**: `.opencode/command/`
- **Kilo Code**: `.kilocode/rules/`
- **Roo Code**: `.roo/rules/`
- **SourceCraft**: `.codeassistant/commands/`
- **Qwen Code**: `.qwen/commands/`
- **GitHub Copilot**: `.github/agents/`  

## Argument Patterns

MADSpec uses `$ARGUMENTS` for most Markdown-based commands and `{{args}}` for Qwen Code.

## Testing New Agent Integration

1. **Build test**: Run package creation script locally
2. **CLI test**: Test `madspecinit --ai <agent>` command
3. **File generation**: Verify correct directory structure and files
4. **Command validation**: Ensure generated commands work with the agent
5. **Workflow test**: Test full MADSpec workflow with new agent

## Common Pitfalls

1. **Using shorthand keys instead of actual CLI tool names**: Always use the actual executable name as the AGENT_CONFIG key.
2. **Incorrect `requires_cli` value**: Set to `True` only for agents that actually have CLI tools to check; set to `False` for IDE-based agents.
3. **Wrong argument format**: Match the target agent's placeholder format (`$ARGUMENTS` for most Markdown agents, `{{args}}` for Qwen Code).
4. **Directory naming**: Follow agent-specific conventions exactly (check existing agents for patterns).
5. **Help text inconsistency**: Update all user-facing text consistently (help strings, docstrings, README, error messages).

## Future Considerations

When adding new agents:

- Consider the agent's native command/workflow patterns
- Ensure compatibility with the MADSpec workflow and command structure
- Document any special requirements or limitations
- Update this guide with lessons learned
- Verify the actual CLI tool name before adding to AGENT_CONFIG

---

*This documentation should be updated whenever new agents are added to maintain accuracy and completeness.*
