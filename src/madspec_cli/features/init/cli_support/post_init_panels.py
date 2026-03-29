from __future__ import annotations

from pathlib import Path

from rich.panel import Panel

from madspec_cli.config import AGENT_CONFIG
from madspec_cli.shared.cli.banners import console

from ..application.contracts import InitMemorySelection, InitializeProjectResult


def print_dense_memory_panel(
    *,
    memory_selection: InitMemorySelection,
    result: InitializeProjectResult | None,
) -> None:
    if not memory_selection.is_dense:
        return
    console.print()
    bootstrap = (result.memory_bootstrap if result else None) or {}
    bootstrap_payload = (bootstrap.get("bootstrap") or {}) if isinstance(bootstrap, dict) else {}
    details = [
        f"[cyan]Provider:[/cyan] {memory_selection.provider}",
        f"[cyan]Model:[/cyan] {memory_selection.model}",
        f"[cyan]Download policy:[/cyan] {memory_selection.download_policy}",
        f"[cyan]Model cache:[/cyan] {memory_selection.cache_dir}",
        f"[cyan]Bootstrap status:[/cyan] {bootstrap.get('status', 'unknown')}",
    ]
    if bootstrap_payload.get("localPath"):
        details.append(f"[cyan]Local path:[/cyan] {bootstrap_payload['localPath']}")
    if bootstrap_payload.get("message"):
        details.append(f"[yellow]{bootstrap_payload['message']}[/yellow]")
    console.print(
        Panel(
            "\n".join(details),
            title="[yellow]Memory Embeddings[/yellow]",
            border_style="yellow",
            padding=(1, 2),
        )
    )


def print_git_warning_panel(
    *,
    result: InitializeProjectResult,
    project_path: Path,
    here: bool,
) -> None:
    if not result.git_error_message:
        return
    console.print()
    console.print(
        Panel(
            f"[yellow]Warning:[/yellow] Git repository initialization failed\n\n"
            f"{result.git_error_message}\n\n"
            f"[dim]You can initialize git manually later with:[/dim]\n"
            f"[cyan]cd {project_path if not here else '.'}[/cyan]\n"
            f"[cyan]madspec git init[/cyan]",
            title="[red]Git Initialization Failed[/red]",
            border_style="red",
            padding=(1, 2),
        )
    )


def print_agent_folder_security_panel(selected_ai: str) -> None:
    agent_config = AGENT_CONFIG[selected_ai]
    console.print()
    console.print(
        Panel(
            "Some agents may store credentials, auth tokens, or other identifying and private artifacts in the agent folder within your project.\n"
            f"Consider adding [cyan]{agent_config.folder}[/cyan] (or parts of it) to [cyan].gitignore[/cyan] to prevent accidental credential leakage.",
            title="[yellow]Agent Folder Security[/yellow]",
            border_style="yellow",
            padding=(1, 2),
        )
    )


def print_next_steps_panel(*, project_name: str, here: bool) -> None:
    steps_lines = []
    if not here:
        steps_lines.append(f"1. Go to the project folder: [cyan]cd {project_name}[/cyan]")
    else:
        steps_lines.append("1. You're already in the project directory!")
    steps_lines.append("2. Начните работу с командами MADSpec в вашей AI-среде:")
    steps_lines.append("")
    steps_lines.append("   [bold]MVP режим (разработка с нуля):[/bold]")
    steps_lines.append("   2.1 [cyan]/madspec.mvp.concept[/] - Зафиксировать идею проекта")
    steps_lines.append("   2.2 [cyan]/madspec.mvp.design[/] - Спроектировать интерфейс и прототипы")
    steps_lines.append("   2.3 [cyan]/madspec.mvp.tech[/] - Выбрать технологический стек")
    steps_lines.append("   2.4 [cyan]/madspec.mvp.architecture[/] - Зафиксировать архитектуру")
    steps_lines.append("   2.5 [cyan]/madspec.deploy[/] - Рекомендуемый этап перед планированием: описать окружения, CI/CD, секреты, миграции и наблюдаемость")
    steps_lines.append("   2.6 [cyan]/madspec.mvp.plan[/] - Составить план реализации")
    steps_lines.append("   2.7 [cyan]/madspec.mvp.implement[/] - Выполнить шаг реализации")
    steps_lines.append("")
    steps_lines.append("   [bold]Feature режим (добавление функциональности):[/bold]")
    steps_lines.append("   2.8 [cyan]/madspec.feature.init[/] - Зафиксировать контекст новой функции")
    steps_lines.append("   2.9 [cyan]/madspec.feature.plan[/] - Спланировать реализацию функции")
    steps_lines.append("   2.10 [cyan]/madspec.feature.implement[/] - Реализовать шаг функции")
    steps_lines.append("")
    steps_lines.append("   [bold]Общие команды:[/bold]")
    steps_lines.append("   2.11 [cyan]/madspec.deploy[/] - Самостоятельно уточнить или обновить план развертывания позже, если это понадобится")
    steps_lines.append("   2.12 [cyan]/madspec.change[/] - Подготовить и ратифицировать пакет изменений ветки")
    steps_lines.append("   2.13 [cyan]/madspec.gate[/] - Проверить контрольные проверки, блокировки и исключения")
    console.print()
    console.print(Panel("\n".join(steps_lines), title="Next Steps", border_style="cyan", padding=(1, 2)))


def print_review_commands_panel() -> None:
    console.print()
    console.print(
        Panel(
            "\n".join(
                [
                    "Optional commands for review and improvement [bright_black](recommended)[/bright_black]",
                    "",
                    "○ [cyan]/madspec.change[/] [bright_black](optional)[/bright_black] - Prepare a branch change bundle before review or handoff",
                    "○ [cyan]/madspec.gate[/] [bright_black](optional)[/bright_black] - Inspect blockers, gate status and waiver flow before state transitions",
                    "○ [cyan]/madspec.review[/] [bright_black](optional)[/bright_black] - Review implementation quality and capture improvements",
                ]
            ),
            title="Review Commands",
            border_style="cyan",
            padding=(1, 2),
        )
    )


def print_quality_commands_panel() -> None:
    console.print()
    console.print(
        Panel(
            "\n".join(
                [
                    "Quality & safety commands [bright_black](recommended)[/bright_black]",
                    "",
                    "○ [cyan]/madspec.security[/] [bright_black](optional)[/bright_black] - Security audit (OWASP/privacy/dependencies/code)",
                ]
            ),
            title="Quality & Safety Commands",
            border_style="cyan",
            padding=(1, 2),
        )
    )
