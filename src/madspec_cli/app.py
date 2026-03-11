from __future__ import annotations

import typer

from .features import git as git_feature
from .features import init as init_feature
from .features import meta as meta_feature
from .memory import cli as memory_cli
from .shared.cli.banners import BannerGroup, maybe_show_root_banner

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


init_feature.cli.register(app)
git_feature.cli.register(app)
meta_feature.cli.register(app)
memory_cli.register(memory_app)


def main() -> None:
    app()
