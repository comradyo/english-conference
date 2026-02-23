from __future__ import annotations

from datetime import date, datetime, time, timezone
from enum import Enum
from pathlib import Path
from typing import Any


def bson_safe(obj: Any) -> Any:
    """BSON-safe, но **сохраняем даты как даты** (Mongo Date/ISODate)."""

    if obj is None or isinstance(obj, (str, int, float, bool)):
        return obj

    if isinstance(obj, datetime):
        return obj

    if isinstance(obj, date) and not isinstance(obj, datetime):
        return datetime.combine(obj, time.min, tzinfo=timezone.utc)

    if isinstance(obj, Path):
        return str(obj)

    if isinstance(obj, Enum):
        return obj.value

    if isinstance(obj, dict):
        return {str(k): bson_safe(v) for k, v in obj.items()}

    if isinstance(obj, (list, tuple, set)):
        return [bson_safe(v) for v in obj]

    return str(obj)
