import json
from typing import Any


def bson_safe(obj: Any) -> Any:
    """
    Гарантируем сериализацию для Mongo:
    DateTime/Path/Enum/прочее уедет в str.
    """
    return json.loads(json.dumps(obj, ensure_ascii=False, default=str))
