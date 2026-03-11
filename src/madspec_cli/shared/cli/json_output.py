from __future__ import annotations

import json
from typing import Any

from ..kernel.result import serialize
from .banners import console


def emit_json(payload: Any) -> None:
    console.print_json(json.dumps(serialize(payload), ensure_ascii=False))
