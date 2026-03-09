from __future__ import annotations

import typer

from .commands import branch as branch_commands
from .commands import init as init_commands
from .commands import memory as memory_commands
from .commands import meta as meta_commands
from .ui import BannerGroup, maybe_show_root_banner

app = typer.Typer(
    name="madspec",
    help="Setup tool for MADSpec projects",
    add_completion=False,
    invoke_without_command=True,
    cls=BannerGroup,
)
memory_app = typer.Typer(help="Structured memory management for MADSpec projects")
app.add_typer(memory_app, name="memory")


@app.callback()
def callback(ctx: typer.Context) -> None:
    """Show banner when no subcommand is provided."""
    if ctx.invoked_subcommand is None:
        maybe_show_root_banner()


init_commands.register(app)
branch_commands.register(app)
meta_commands.register(app)
memory_commands.register(memory_app)


def main() -> None:
    app()
