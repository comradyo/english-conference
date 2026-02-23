from datetime import datetime, timezone
from typing import Any, Dict, Optional

from fastapi import FastAPI

from schemas.tilda import TildaSubmission


async def process_lead(payload: Dict[str, Any], referer: Optional[str], app: FastAPI) -> str:
    # 1) нормализация/валидация
    submission = TildaSubmission.model_validate(payload)
    data = submission.model_dump(mode="json", by_alias=False)

    # 2) готовим документ для Mongo
    data.update({
        "raw_payload": payload,
        "created_at": datetime.now(timezone.utc),
        "referer": referer,
        "result": None,
        "locked_at": None
    })

    result = await app.state.mongo_collection.insert_one(data)
    return str(result.inserted_id)
