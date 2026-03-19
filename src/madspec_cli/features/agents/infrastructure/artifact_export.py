from __future__ import annotations

from pathlib import Path

from ..domain.builtin_roles import DEFAULT_PROFILE_ID
from .catalog_store import load_effective_subagents
from .state_store import get_agents_paths


def export_agents_artifact(project_path: Path, state: dict[str, object]) -> Path:
    paths = get_agents_paths(project_path)
    effective_roles = load_effective_subagents(project_path, state=state)
    lines = [
        "# Субагенты",
        "",
        f"- Среда: `{state.get('environmentId', 'unknown')}`",
        f"- Профиль: `{state.get('profileId', DEFAULT_PROFILE_ID)}`",
        f"- Ревизия: `{state.get('revision', 1)}`",
        f"- Каталог: `{paths.catalog_file.relative_to(project_path)}`",
        "",
        "## Роли",
        "",
    ]
    for item in effective_roles:
        if not isinstance(item, dict):
            continue
        lines.append(
            f"- `{item.get('subagentId')}` [{item.get('renderMode', 'fallback')}] origin={item.get('origin')} enabled={bool(item.get('enabled'))}: {item.get('description', '')}"
        )
    paths.artifact_file.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    return paths.artifact_file
