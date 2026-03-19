from __future__ import annotations

import shutil


def check_tool(tool: str) -> bool:
    return shutil.which(tool) is not None
