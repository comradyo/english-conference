from typing import Any, Dict
from fastapi import APIRouter, BackgroundTasks, Depends, Request
from fastapi.responses import PlainTextResponse

from api.deps import get_tilda_payload
from services.lead_service import process_lead

router = APIRouter()


@router.post("/tilda/webhook")
async def tilda_webhook(
        request: Request,
        background: BackgroundTasks,
        payload: Dict[str, Any] = Depends(get_tilda_payload),
):
    if payload.get("test") == "test":
        return PlainTextResponse("ok", status_code=200)

    referer = request.headers.get("referer")
    background.add_task(process_lead, payload, referer, request.app)
    return PlainTextResponse("Accepted", status_code=202)
