from __future__ import annotations

from typing import Any

from .banners import console, show_banner
from .json_output import emit_json
from .toon_output import emit_toon


def emit_result(result: Any, *, json_output: bool, toon_output: bool = False) -> None:
    if json_output:
        emit_json(result)
        return
    if toon_output:
        emit_toon(result)


def emit_error(exc: Exception, *, json_output: bool, toon_output: bool = False) -> None:
    if json_output:
        emit_json({"error": str(exc)})
        return
    if toon_output:
        emit_toon({"error": str(exc)})
        return
    show_banner()
    console.print(f"[red]Error:[/red] {exc}")
