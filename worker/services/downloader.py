from pathlib import Path
from typing import Any

import aiohttp
from aiohttp import ClientSession

from core.config import Settings


async def download_file(settings: Settings, session: aiohttp.ClientSession, file_name: str, dst_dir: Path) -> Path:
    href = await _get_download_url(settings, session, file_name)
    out_path = dst_dir / file_name
    await _download(session, href, out_path)
    return out_path


async def _get_download_url(settings: Settings, session: ClientSession, file_name: str) -> Any:
    yandex_disk_path = Path(settings.yandex_disk_path) / file_name
    async with session.get(settings.yandex_aip_url, params={"path": str(yandex_disk_path)}) as resp:
        data = await resp.json()
        href = data["href"]
    return href


async def _download(session: ClientSession, href, out_path: Path):
    async with session.get(href) as resp:
        with open(out_path, "wb") as f:
            async for chunk in resp.content.iter_chunked(1024 * 1024):
                f.write(chunk)
