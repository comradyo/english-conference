import json
from typing import Any, Dict

from fastapi import Depends, HTTPException, Request

from core.config import get_settings, Settings
from utils.formdata import formdata_to_dict


async def verify_tilda_api_key(
        request: Request,
        settings: Settings = Depends(get_settings),
) -> None:
    # Если ключи не заданы — проверка выключена
    if not settings.api_key_name or not settings.api_key_value:
        return

    got = request.headers.get(settings.api_key_name)
    if got != settings.api_key_value:
        raise HTTPException(status_code=401, detail="Invalid API key")


async def get_tilda_payload(
        request: Request,
        _: None = Depends(verify_tilda_api_key),  # <-- гарантирует, что ключ проверен ДО парсинга body
) -> Dict[str, Any]:
    cached = getattr(request.state, "tilda_payload", None)
    if cached is not None:
        return cached

    content_type = (request.headers.get("content-type") or "").lower()

    if "application/json" in content_type:
        raw = await request.body()
        try:
            data = json.loads(raw.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            raise HTTPException(status_code=400, detail="Invalid JSON")

        payload: Dict[str, Any] = data if isinstance(data, dict) else {"_raw": data}
    else:
        form = await request.form()
        payload = formdata_to_dict(form)

    request.state.tilda_payload = payload
    return payload
