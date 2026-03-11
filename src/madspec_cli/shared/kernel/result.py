from __future__ import annotations

from dataclasses import asdict, dataclass, is_dataclass
from typing import Any


@dataclass(frozen=True)
class PayloadResult:
    payload: dict[str, Any]

    def to_payload(self) -> dict[str, Any]:
        return dict(self.payload)

    def as_dict(self) -> dict[str, Any]:
        return self.to_payload()


def serialize(value: Any) -> Any:
    if hasattr(value, "to_payload"):
        return value.to_payload()
    if hasattr(value, "as_dict"):
        return value.as_dict()
    if is_dataclass(value):
        return asdict(value)
    return value
