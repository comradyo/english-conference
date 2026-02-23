from datetime import datetime, timezone
from typing import Any, Dict, Optional

from fastapi import FastAPI
from pydantic import HttpUrl

from schemas.tilda import TildaSubmission


def _extract_file_name_from_tilda_url(url: HttpUrl) -> str:
    return str(url).rsplit("/", 1)[-1]


async def process_lead(payload: Dict[str, Any], referer: Optional[str], app: FastAPI) -> str:
    # 1) нормализация/валидация
    submission = TildaSubmission.model_validate(payload)
    data = submission.model_dump(mode="json", by_alias=False)

    # 2) готовим документ для Mongo
    data.update({
        "raw_payload": payload,
        "created_at": datetime.now(timezone.utc),
        "referer": referer,
        "publication_file_name": _extract_file_name_from_tilda_url(submission.publication_file_url),
        "result": None,
        "locked_at": None
    })

    result = await app.state.mongo_collection.insert_one(data)
    return str(result.inserted_id)
