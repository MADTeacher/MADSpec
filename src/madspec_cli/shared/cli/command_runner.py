from __future__ import annotations

from collections.abc import Callable
from typing import TypeVar

import typer

from .banners import show_banner
from .json_output import emit_json
from .presenters import emit_error
from .toon_output import emit_toon

T = TypeVar("T")


def execute_cli_action(
    action: Callable[[], T],
    *,
    json_output: bool,
    toon_output: bool = False,
    text_output: Callable[[T], None] | None = None,
    should_fail: Callable[[T], bool] | None = None,
    show_banner_on_text: bool = True,
) -> T:
    try:
        payload = action()
    except Exception as exc:
        emit_error(exc, json_output=json_output, toon_output=toon_output)
        raise typer.Exit(1) from exc

    if json_output:
        emit_json(payload)
    elif toon_output:
        emit_toon(payload)
    else:
        if show_banner_on_text:
            show_banner()
        if text_output is not None:
            text_output(payload)

    if should_fail is not None and should_fail(payload):
        raise typer.Exit(1)

    return payload
