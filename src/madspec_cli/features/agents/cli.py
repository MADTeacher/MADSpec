from __future__ import annotations

from pathlib import Path

import typer

from madspec_cli.shared.cli.banners import console, show_banner
from madspec_cli.shared.cli.file_input import read_args_file
from madspec_cli.shared.cli.json_output import emit_json
from madspec_cli.shared.cli.presenters import emit_error
from madspec_cli.shared.cli.toon_output import emit_toon, ensure_structured_output_mode
from madspec_cli.memory.shared.system_store.constants import SYSTEM_SESSION_KEY

from .application.apply_profile import ApplyProfileRequest, execute as apply_profile
from .application.create_subagent import CreateSubagentRequest, execute as create_subagent
from .application.list_subagents import ListSubagentsRequest, execute as list_subagents
from .application.profile_agents import AgentProfileRequest, execute as profile_agents
from .application.propose_profile import ProposeProfileRequest, execute as propose_profile
from .application.recommend_agents import RecommendAgentsRequest, execute as recommend_agents
from .application.remove_subagent import RemoveSubagentRequest, execute as remove_subagent
from .application.show_subagent import ShowSubagentRequest, execute as show_subagent
from .application.subagent_context import SubagentContextRequest, execute as subagent_context
from .application.toggle_subagent import ToggleSubagentRequest, execute as toggle_subagent
from .application.update_subagent import UpdateSubagentRequest, execute as update_subagent


agents_app = typer.Typer(help="Профили субагентов, рекомендации и адаптеры сред")
subagents_app = typer.Typer(help="Состояние ролей субагентов и контекст для конкретной роли")

SUBAGENT_FROM_FILE_ALLOWED_KEYS = {
    "title",
    "description",
    "purpose",
    "defaultStage",
    "executionModeHint",
    "dependencies",
    "toolPolicy",
    "outputContract",
}
SUBAGENT_FROM_FILE_ALIASES = {
    "default_stage": "defaultStage",
    "execution_mode_hint": "executionModeHint",
    "tool_policy": "toolPolicy",
    "output_contract": "outputContract",
}


@agents_app.command("profile")
def profile(
    json_output: bool = typer.Option(False, "--json-output", help="Вывести машиночитаемый JSON"),
) -> None:
    payload = profile_agents(AgentProfileRequest(project_path=Path.cwd())).to_payload()
    if json_output:
        emit_json(payload)
        return
    show_banner()
    console.print(f"[cyan]Среда:[/cyan] {payload['environment']['environmentId']}")
    console.print(f"[cyan]Профиль:[/cyan] {payload['profile']['profileId']}")
    console.print(f"[cyan]Состояние:[/cyan] {payload['state_file']}")
    enabled = [item["subagentId"] for item in payload["profile"]["subagents"] if item.get("enabled")]
    console.print(f"[cyan]Включенные субагенты:[/cyan] {', '.join(enabled) if enabled else 'нет'}")


@agents_app.command("recommend")
def recommend(
    json_output: bool = typer.Option(False, "--json-output", help="Вывести машиночитаемый JSON"),
) -> None:
    payload = recommend_agents(RecommendAgentsRequest(project_path=Path.cwd())).to_payload()
    if json_output:
        emit_json(payload)
        return
    show_banner()
    console.print(f"[cyan]Среда:[/cyan] {payload['environment']['environmentId']}")
    console.print(f"[cyan]Профиль:[/cyan] {payload['profileId']}")
    console.print(payload["summary"])
    for item in payload["recommendedSubagents"]:
        console.print(f"- `{item['subagentId']}` [{item['renderMode']}] {item['description']}")


@agents_app.command("propose-profile")
def propose_profile_command(
    profile_id: str = typer.Option("default", "--profile-id", help="Идентификатор профиля"),
    environment: str = typer.Option(None, "--environment", help="Необязательная замена среды"),
    subagent: list[str] = typer.Option(None, "--subagent", help="Включить субагент в предлагаемом профиле; флаг можно повторять"),
    json_output: bool = typer.Option(False, "--json-output", help="Вывести машиночитаемый JSON"),
) -> None:
    payload = propose_profile(
        ProposeProfileRequest(
            project_path=Path.cwd(),
            environment_id=environment,
            profile_id=profile_id,
            enabled_subagents=subagent or None,
            requested_by="agents.propose-profile",
        )
    ).to_payload()
    if json_output:
        emit_json(payload)
        return
    show_banner()
    console.print(f"[green]Создано предложение:[/green] {payload['proposalId']}")
    console.print(f"[cyan]Среда:[/cyan] {payload['environmentId']}")
    console.print(f"[cyan]Измененные поля:[/cyan] {', '.join(payload['diff']['changedFields']) or 'нет'}")


@agents_app.command("apply-profile")
def apply_profile_command(
    proposal_id: str = typer.Option(..., "--proposal-id", help="Идентификатор ожидающего предложения"),
    json_output: bool = typer.Option(False, "--json-output", help="Вывести машиночитаемый JSON"),
) -> None:
    try:
        payload = apply_profile(
            ApplyProfileRequest(project_path=Path.cwd(), proposal_id=proposal_id)
        ).to_payload()
    except Exception as exc:
        emit_error(exc, json_output=json_output, toon_output=toon_output)
        raise typer.Exit(1) from exc
    if json_output:
        emit_json(payload)
        return
    show_banner()
    console.print(f"[green]Предложение применено:[/green] {proposal_id}")
    console.print(f"[cyan]Сформировано файлов:[/cyan] {len(payload['rendered']['created'])}")


@subagents_app.command("list")
def list_command(
    enabled_only: bool = typer.Option(False, "--enabled-only", help="Показывать только включенных субагентов"),
    json_output: bool = typer.Option(False, "--json-output", help="Вывести машиночитаемый JSON"),
) -> None:
    payload = list_subagents(
        ListSubagentsRequest(project_path=Path.cwd(), enabled_only=enabled_only)
    ).to_payload()
    if json_output:
        emit_json(payload)
        return
    show_banner()
    console.print(f"[cyan]Среда:[/cyan] {payload['environmentId']}")
    for item in payload["subagents"]:
        console.print(f"- `{item['subagentId']}` включен={item['enabled']} [{item['renderMode']}] {item['description']}")


@subagents_app.command("show")
def show_command(
    subagent_id: str = typer.Option(..., "--subagent-id", help="Идентификатор субагента"),
    json_output: bool = typer.Option(False, "--json-output", help="Вывести машиночитаемый JSON"),
) -> None:
    try:
        payload = show_subagent(
            ShowSubagentRequest(project_path=Path.cwd(), subagent_id=subagent_id)
        ).to_payload()
    except Exception as exc:
        emit_error(exc, json_output=json_output)
        raise typer.Exit(1) from exc
    if json_output:
        emit_json(payload)
        return
    show_banner()
    console.print(f"[cyan]Субагент:[/cyan] {payload['subagentId']}")
    console.print(f"[cyan]Источник:[/cyan] {payload.get('origin')}")
    console.print(f"[cyan]Включен:[/cyan] {payload.get('enabled')}")
    console.print(f"[cyan]Источник текста:[/cyan] {payload.get('bodySource')}")
    console.print(payload["description"])


@subagents_app.command("create")
def create_command(
    subagent_id: str = typer.Option(..., "--subagent-id", help="Идентификатор субагента"),
    from_file: str = typer.Option(..., "--from-file", help="Путь к JSON-файлу с метаданными субагента"),
    body_file: str = typer.Option(..., "--body-file", help="Путь к Markdown-файлу с текстом субагента"),
    json_output: bool = typer.Option(False, "--json-output", help="Вывести машиночитаемый JSON"),
) -> None:
    try:
        payload_data = read_args_file(
            from_file,
            aliases=SUBAGENT_FROM_FILE_ALIASES,
            allowed_keys=SUBAGENT_FROM_FILE_ALLOWED_KEYS,
        )
        body_text = Path(body_file).read_text(encoding="utf-8")
        payload = create_subagent(
            CreateSubagentRequest(
                project_path=Path.cwd(),
                subagent_id=subagent_id,
                payload=payload_data,
                body_text=body_text,
            )
        ).to_payload()
    except Exception as exc:
        emit_error(exc, json_output=json_output)
        raise typer.Exit(1) from exc
    if json_output:
        emit_json(payload)
        return
    show_banner()
    console.print(f"[green]Субагент создан:[/green] {subagent_id}")


@subagents_app.command("update")
def update_command(
    subagent_id: str = typer.Option(..., "--subagent-id", help="Идентификатор субагента"),
    from_file: str = typer.Option(..., "--from-file", help="Путь к JSON-файлу с метаданными субагента"),
    body_file: str = typer.Option(None, "--body-file", help="Необязательный Markdown-файл с текстом субагента"),
    json_output: bool = typer.Option(False, "--json-output", help="Вывести машиночитаемый JSON"),
) -> None:
    try:
        payload_data = read_args_file(
            from_file,
            aliases=SUBAGENT_FROM_FILE_ALIASES,
            allowed_keys=SUBAGENT_FROM_FILE_ALLOWED_KEYS,
        )
        body_text = Path(body_file).read_text(encoding="utf-8") if body_file else None
        payload = update_subagent(
            UpdateSubagentRequest(
                project_path=Path.cwd(),
                subagent_id=subagent_id,
                payload=payload_data,
                body_text=body_text,
            )
        ).to_payload()
    except Exception as exc:
        emit_error(exc, json_output=json_output)
        raise typer.Exit(1) from exc
    if json_output:
        emit_json(payload)
        return
    show_banner()
    console.print(f"[green]Субагент обновлен:[/green] {subagent_id}")


@subagents_app.command("remove")
def remove_command(
    subagent_id: str = typer.Option(..., "--subagent-id", help="Идентификатор субагента"),
    force: bool = typer.Option(False, "--force", help="Удалить даже если субагент включен"),
    json_output: bool = typer.Option(False, "--json-output", help="Вывести машиночитаемый JSON"),
) -> None:
    try:
        payload = remove_subagent(
            RemoveSubagentRequest(
                project_path=Path.cwd(),
                subagent_id=subagent_id,
                force=force,
            )
        ).to_payload()
    except Exception as exc:
        emit_error(exc, json_output=json_output)
        raise typer.Exit(1) from exc
    if json_output:
        emit_json(payload)
        return
    show_banner()
    console.print(f"[green]Субагент удален:[/green] {subagent_id}")


@subagents_app.command("enable")
def enable_command(
    subagent_id: str = typer.Option(..., "--subagent-id", help="Идентификатор субагента"),
    json_output: bool = typer.Option(False, "--json-output", help="Вывести машиночитаемый JSON"),
) -> None:
    try:
        payload = toggle_subagent(
            ToggleSubagentRequest(project_path=Path.cwd(), subagent_id=subagent_id, enabled=True)
        ).to_payload()
    except Exception as exc:
        emit_error(exc, json_output=json_output)
        raise typer.Exit(1) from exc
    if json_output:
        emit_json(payload)
        return
    show_banner()
    console.print(f"[green]Субагент включен:[/green] {subagent_id}")


@subagents_app.command("disable")
def disable_command(
    subagent_id: str = typer.Option(..., "--subagent-id", help="Идентификатор субагента"),
    json_output: bool = typer.Option(False, "--json-output", help="Вывести машиночитаемый JSON"),
) -> None:
    try:
        payload = toggle_subagent(
            ToggleSubagentRequest(project_path=Path.cwd(), subagent_id=subagent_id, enabled=False)
        ).to_payload()
    except Exception as exc:
        emit_error(exc, json_output=json_output)
        raise typer.Exit(1) from exc
    if json_output:
        emit_json(payload)
        return
    show_banner()
    console.print(f"[green]Субагент отключен:[/green] {subagent_id}")


@subagents_app.command("context")
def context_command(
    subagent_id: str = typer.Option(..., "--subagent-id", help="Идентификатор субагента"),
    branch_name: str = typer.Option(None, "--branch", help="Необязательная замена ветки"),
    stage: str = typer.Option(None, "--stage", help="Необязательная замена стадии"),
    session_key: str = typer.Option(SYSTEM_SESSION_KEY, "--session-key", help="Ключ runtime-сеанса; по умолчанию legacy active"),
    step_id: str = typer.Option(None, "--step-id", help="Необязательный идентификатор шага"),
    task_id: str = typer.Option(None, "--task-id", help="Необязательный идентификатор task coordination"),
    work_item_id: str = typer.Option(None, "--work-item-id", help="Необязательный идентификатор work item"),
    json_output: bool = typer.Option(False, "--json-output", help="Вывести машиночитаемый JSON"),
    toon_output: bool = typer.Option(False, "--toon-output", help="Вывести TOON для агентского контекста"),
) -> None:
    ensure_structured_output_mode(json_output=json_output, toon_output=toon_output)
    try:
        payload = subagent_context(
            SubagentContextRequest(
                project_path=Path.cwd(),
                subagent_id=subagent_id,
                branch_name=branch_name,
                stage=stage,
                session_key=session_key,
                step_id=step_id,
                task_id=task_id,
                work_item_id=work_item_id,
            )
        ).to_payload()
    except Exception as exc:
        emit_error(exc, json_output=json_output)
        raise typer.Exit(1) from exc
    if json_output:
        emit_json(payload)
        return
    if toon_output:
        emit_toon(payload)
        return
    show_banner()
    console.print(f"[cyan]Субагент:[/cyan] {payload['subagent']['subagentId']}")
    console.print(f"[cyan]Ветка:[/cyan] {payload['branch']}")
    console.print(f"[cyan]Стадия:[/cyan] {payload['stage']}")
    console.print(f"[cyan]Подтверждения правил:[/cyan] {len(payload['policy']['policy_context']['required'])}")
    console.print(f"[cyan]Статус gate-проверок:[/cyan] {payload['gates']['overall_status']}")


def register(app: typer.Typer) -> None:
    agents_app.add_typer(subagents_app, name="subagents")
    app.add_typer(agents_app, name="agents")
