from __future__ import annotations

import sys

import readchar
import typer
from rich.align import Align
from rich.console import Console
from rich.live import Live
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich.tree import Tree
from typer.core import TyperGroup

BANNER = """
███╗   ███╗ █████╗ ██████╗   ███████╗██████╗ ███████╗ ██████╗
████╗ ████║██╔══██╗██╔══██╗  ██╔════╝██╔══██╗██╔════╝██╔════╝
██╔████╔██║███████║██║  ██║  ███████╗██████╔╝█████╗  ██║
██║╚██╔╝██║██╔══██║██║  ██║  ╚════██║██╔═══╝ ██╔══╝  ██║
██║ ╚═╝ ██║██║  ██║██████╔╝  ███████║██║     ███████╗╚██████╗
╚═╝     ╚═╝╚═╝  ╚═╝╚═════╝   ╚══════╝╚═╝     ╚══════╝ ╚═════╝
"""

TAGLINE = "MADSpec Framework"


def _init_windows_console() -> None:
    """Set UTF-8 codepage and enable VT processing on Windows.

    Must run before Console() so Rich detects ANSI support
    and avoids the legacy Win32 renderer that chokes on cp1251.
    """
    if sys.platform != "win32":
        return
    try:
        import ctypes

        kernel32 = ctypes.windll.kernel32
        kernel32.SetConsoleOutputCP(65001)
        kernel32.SetConsoleCP(65001)
        STD_OUTPUT_HANDLE = -11
        ENABLE_VIRTUAL_TERMINAL_PROCESSING = 0x0004
        handle = kernel32.GetStdHandle(STD_OUTPUT_HANDLE)
        if handle and handle != -1:
            mode = ctypes.c_ulong()
            if kernel32.GetConsoleMode(handle, ctypes.byref(mode)):
                kernel32.SetConsoleMode(
                    handle, mode.value | ENABLE_VIRTUAL_TERMINAL_PROCESSING
                )
    except Exception:
        pass
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            try:
                stream.reconfigure(encoding="utf-8", errors="replace")
            except Exception:
                pass


_init_windows_console()

console = Console()


class StepTracker:
    """Track and render hierarchical steps without emojis."""

    def __init__(self, title: str):
        self.title = title
        self.steps: list[dict[str, str]] = []
        self._refresh_cb = None

    def attach_refresh(self, cb) -> None:
        self._refresh_cb = cb

    def add(self, key: str, label: str) -> None:
        if key not in [step["key"] for step in self.steps]:
            self.steps.append(
                {"key": key, "label": label, "status": "pending", "detail": ""}
            )
            self._maybe_refresh()

    def start(self, key: str, detail: str = "") -> None:
        self._update(key, status="running", detail=detail)

    def complete(self, key: str, detail: str = "") -> None:
        self._update(key, status="done", detail=detail)

    def error(self, key: str, detail: str = "") -> None:
        self._update(key, status="error", detail=detail)

    def skip(self, key: str, detail: str = "") -> None:
        self._update(key, status="skipped", detail=detail)

    def _update(self, key: str, status: str, detail: str) -> None:
        for step in self.steps:
            if step["key"] == key:
                step["status"] = status
                if detail:
                    step["detail"] = detail
                self._maybe_refresh()
                return

        self.steps.append(
            {"key": key, "label": key, "status": status, "detail": detail}
        )
        self._maybe_refresh()

    def _maybe_refresh(self) -> None:
        if self._refresh_cb:
            try:
                self._refresh_cb()
            except Exception:
                pass

    def render(self) -> Tree:
        tree = Tree(f"[cyan]{self.title}[/cyan]", guide_style="grey50")
        for step in self.steps:
            label = step["label"]
            detail_text = step["detail"].strip() if step["detail"] else ""
            status = step["status"]
            if status == "done":
                symbol = "[green]●[/green]"
            elif status == "pending":
                symbol = "[green dim]○[/green dim]"
            elif status == "running":
                symbol = "[cyan]○[/cyan]"
            elif status == "error":
                symbol = "[red]●[/red]"
            elif status == "skipped":
                symbol = "[yellow]○[/yellow]"
            else:
                symbol = " "

            if status == "pending":
                if detail_text:
                    line = (
                        f"{symbol} [bright_black]{label} ({detail_text})[/bright_black]"
                    )
                else:
                    line = f"{symbol} [bright_black]{label}[/bright_black]"
            else:
                if detail_text:
                    line = f"{symbol} [white]{label}[/white] [bright_black]({detail_text})[/bright_black]"
                else:
                    line = f"{symbol} [white]{label}[/white]"

            tree.add(line)
        return tree


def get_key() -> str:
    key = readchar.readkey()

    if key == readchar.key.UP or key == readchar.key.CTRL_P:
        return "up"
    if key == readchar.key.DOWN or key == readchar.key.CTRL_N:
        return "down"
    if key == readchar.key.ENTER:
        return "enter"
    if key == readchar.key.ESC:
        return "escape"
    if key == readchar.key.CTRL_C:
        raise KeyboardInterrupt
    return key


def select_with_arrows(
    options: dict[str, str],
    prompt_text: str = "Select an option",
    default_key: str | None = None,
) -> str:
    option_keys = list(options.keys())
    selected_index = option_keys.index(default_key) if default_key in option_keys else 0
    selected_key: str | None = None

    def create_selection_panel() -> Panel:
        table = Table.grid(padding=(0, 2))
        table.add_column(style="cyan", justify="left", width=3)
        table.add_column(style="white", justify="left")

        for index, key in enumerate(option_keys):
            if index == selected_index:
                table.add_row("▶", f"[cyan]{key}[/cyan] [dim]({options[key]})[/dim]")
            else:
                table.add_row(" ", f"[cyan]{key}[/cyan] [dim]({options[key]})[/dim]")

        table.add_row("", "")
        table.add_row(
            "",
            "[dim]Use ↑/↓ to navigate, Enter to select, Esc to cancel[/dim]",
        )

        return Panel(
            table,
            title=f"[bold]{prompt_text}[/bold]",
            border_style="cyan",
            padding=(1, 2),
        )

    console.print()

    with Live(
        create_selection_panel(),
        console=console,
        transient=True,
        auto_refresh=False,
    ) as live:
        while True:
            try:
                key = get_key()
                if key == "up":
                    selected_index = (selected_index - 1) % len(option_keys)
                elif key == "down":
                    selected_index = (selected_index + 1) % len(option_keys)
                elif key == "enter":
                    selected_key = option_keys[selected_index]
                    break
                elif key == "escape":
                    console.print("\n[yellow]Selection cancelled[/yellow]")
                    raise typer.Exit(1)

                live.update(create_selection_panel(), refresh=True)
            except KeyboardInterrupt as exc:
                console.print("\n[yellow]Selection cancelled[/yellow]")
                raise typer.Exit(1) from exc

    if selected_key is None:
        console.print("\n[red]Selection failed.[/red]")
        raise typer.Exit(1)

    return selected_key


class BannerGroup(TyperGroup):
    """Custom group that shows the banner before help."""

    def format_help(self, ctx, formatter):
        show_banner()
        super().format_help(ctx, formatter)


def show_banner() -> None:
    try:
        banner_lines = BANNER.strip().split("\n")
        colors = ["bright_blue", "blue", "cyan", "bright_cyan", "white", "bright_white"]

        styled_banner = Text()
        for index, line in enumerate(banner_lines):
            styled_banner.append(line + "\n", style=colors[index % len(colors)])

        console.print(Align.center(styled_banner))
        console.print(Align.center(Text(TAGLINE, style="italic bright_yellow")))
        console.print()
    except UnicodeEncodeError:
        console.print("[bright_blue]MADSpec Framework[/bright_blue]")
        console.print()


def maybe_show_root_banner() -> None:
    if "--help" not in sys.argv and "-h" not in sys.argv:
        show_banner()
        console.print(
            Align.center("[dim]Run 'madspec --help' for usage information[/dim]")
        )
        console.print()
