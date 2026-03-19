from __future__ import annotations

from dataclasses import dataclass

from madspec_cli.config import AGENT_CONFIG
from madspec_cli.shared.infra.system_tools import check_tool
from madspec_cli.shared.kernel.result import PayloadResult


@dataclass(frozen=True)
class CheckToolsResult(PayloadResult):
    pass


def execute() -> CheckToolsResult:
    items: list[dict[str, object]] = []

    def add(tool_id: str, label: str, *, required_check: bool = True, skipped_reason: str | None = None) -> bool:
        available = check_tool(tool_id) if required_check else False
        items.append(
            {
                "id": tool_id,
                "label": label,
                "available": available,
                "skipped": skipped_reason is not None,
                "reason": skipped_reason,
            }
        )
        return available

    git_ok = add("git", "Git version control")
    agent_results: dict[str, bool] = {}
    for agent_key, agent_config in AGENT_CONFIG.items():
        if agent_config.requires_cli:
            agent_results[agent_key] = add(agent_key, agent_config.name)
        else:
            agent_results[agent_key] = add(
                agent_key,
                agent_config.name,
                required_check=False,
                skipped_reason="IDE-based, no CLI check",
            )

    code_ok = add("code", "Visual Studio Code")
    code_insiders_ok = add("code-insiders", "Visual Studio Code Insiders")
    return CheckToolsResult(
        payload={
            "items": items,
            "git_ok": git_ok,
            "agent_results": agent_results,
            "code_ok": code_ok,
            "code_insiders_ok": code_insiders_ok,
        }
    )
