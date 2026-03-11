from __future__ import annotations

from typing import Any

from .banners import console, show_banner
from .json_output import emit_json


def emit_result(result: Any, *, json_output: bool) -> None:
    if json_output:
        emit_json(result)


def emit_error(exc: Exception, *, json_output: bool) -> None:
    if json_output:
        emit_json({"error": str(exc)})
        return
    show_banner()
    console.print(f"[red]Error:[/red] {exc}")
