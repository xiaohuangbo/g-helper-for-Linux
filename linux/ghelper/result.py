from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class Result:
    ok: bool
    message: str = ""
    data: Any = None

    def to_dict(self) -> dict:
        return {"ok": self.ok, "message": self.message, "data": self.data}
