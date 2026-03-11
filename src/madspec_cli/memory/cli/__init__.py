from __future__ import annotations

import typer

from . import bootstrap, capture, checkpoint, implementation, learning, planning, query


def register(memory_app: typer.Typer) -> None:
    bootstrap.register(memory_app)
    capture.register(memory_app)
    checkpoint.register(memory_app)
    query.register(memory_app)
    implementation.register(memory_app)
    planning.register(memory_app)
    learning.register(memory_app)
