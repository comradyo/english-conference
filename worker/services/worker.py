import asyncio
import logging

import aiohttp

from core.config import Settings
from db.mongo import MongoRepo
from services.downloader import download_file
from services.processor import process_file

log = logging.getLogger("worker")


async def run_worker(stop: asyncio.Event, settings: Settings) -> None:
    repo = MongoRepo(settings)
    await repo.ensure_indexes()

    timeout = aiohttp.ClientTimeout(total=180)
    headers = {
        "Accept": "application/json",
        "Authorization": f"OAuth {settings.yandex_api_token}",
    }
    print('1')

    async with aiohttp.ClientSession(headers=headers, timeout=timeout, raise_for_status=True) as session:
        settings.download_dir.mkdir(parents=True, exist_ok=True)

        log.info(
            "started worker_id=%s poll=%.2fs lock_timeout=%ss",
            settings.worker_id,
            settings.poll_interval_sec,
            settings.lock_timeout_sec,
        )

        try:
            while not stop.is_set():
                doc = await repo.acquire_job()
                if not doc:
                    await asyncio.sleep(settings.poll_interval_sec)
                    continue

                try:
                    file_name = doc.get("publication_file_name")
                    if not isinstance(file_name, str) or not file_name:
                        raise ValueError("publication_file_url is missing or not a string")

                    job_dir = settings.download_dir
                    file_path = await download_file(settings, session, file_name, job_dir)

                    result_value = await process_file(file_path, doc)

                    await repo.mark_done(
                        doc_id=doc["_id"],
                        result_value=result_value,
                        file_local_path=str(file_path),
                    )

                    log.info("done _id=%s file=%s", str(doc["_id"]), str(file_path))

                except Exception as e:
                    await repo.mark_failed(doc, str(e))
                    log.exception("failed _id=%s err=%s", str(doc.get("_id")), str(e))

        finally:
            await repo.close()
            log.info("stopped worker_id=%s", settings.worker_id)
