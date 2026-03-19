from __future__ import annotations

from .constants import GITIGNORE_SECTIONS


def gitignore_sections() -> dict[str, list[str]]:
    return GITIGNORE_SECTIONS
