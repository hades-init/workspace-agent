from typing import Dict
from dataclasses import dataclass


@dataclass
class HandlerResult:
    success: bool
    result: Dict
    error: str | None


class HandlerError(Exception):
    """Raised when a handler fails to execute."""
    pass