from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import logging
import os
import signal
import tempfile
from typing import Any

from fastapi import FastAPI, File, UploadFile
from fastapi.responses import PlainTextResponse
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorCollection
from pymongo import ReturnDocument

from validator import Validator


LOGGER = logging.getLogger("checker")
UTC = timezone.utc

WAITING_STATUS = "Ожидает проверки. Обновите вкладку через несколько секунд."
PROCESSING_STATUS = "Идёт проверка"
PASSED_STATUS = "Ошибок не найдено"
FAILED_VALIDATION_STATUS = "Найдены замечания"
SYSTEM_ERROR_STATUS = "Ошибка проверки"

api_app = FastAPI(title="Checker Internal API")


def now_utc() -> datetime:
    return datetime.now(UTC)


@dataclass(frozen=True)
class Settings:
    mongo_uri: str
    mongo_db: str
    registrations_collection: str
    poll_interval_sec: int
    processing_timeout_sec: int
    log_level: str

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            mongo_uri=os.getenv("MONGO_URI", "mongodb://localhost:27017"),
            mongo_db=os.getenv("MONGO_DB", "eng_conference"),
            registrations_collection=os.getenv("WEB_REGISTRATIONS_COLLECTION", "conference_registrations"),
            poll_interval_sec=max(1, int(os.getenv("CHECKER_POLL_INTERVAL_SEC", "5"))),
            processing_timeout_sec=max(30, int(os.getenv("CHECKER_PROCESSING_TIMEOUT_SEC", "300"))),
            log_level=os.getenv("LOG_LEVEL", "info").strip().upper() or "INFO",
        )


def validate_publication_content(content: bytes) -> tuple[list[str], list[str]]:
    temp_path: str | None = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".docx") as temp_file:
            temp_file.write(content)
            temp_path = temp_file.name
        errors_ru, errors_eng = Validator(temp_path).validate()
        return [
            str(item).strip() for item in errors_ru if str(item).strip()
        ], [
            str(item).strip() for item in errors_eng if str(item).strip()
        ]
    finally:
        if temp_path:
            try:
                os.unlink(temp_path)
            except FileNotFoundError:
                pass


def format_validation_result_text(errors: list[str], errors_eng: list[str]) -> str:
    if not errors:
        return "Предварительная проверка завершена: ошибок не найдено.\n" + "The preliminary check is completed: no errors were found."
    return "Предварительная проверка завершена: найдены замечания.\n- " + "\n- ".join(errors) + "\nThe preliminary check has been completed: comments have been found.\n- " + "\n- ".join(errors_eng)


@api_app.post("/validate", include_in_schema=False, response_class=PlainTextResponse)
async def validate_file_api(file: UploadFile = File(...)) -> PlainTextResponse:
    filename = (file.filename or "").strip()
    if not filename:
        return PlainTextResponse("Файл публикации обязателен.", status_code=400)
    if not filename.lower().endswith(".docx"):
        return PlainTextResponse("Можно загрузить только файл в формате .docx.", status_code=400)

    content = await file.read()
    if not content:
        return PlainTextResponse("Загруженный файл пуст.", status_code=400)

    try:
        errors_ru, errors_eng = await asyncio.to_thread(validate_publication_content, content)
    except Exception as exc:
        LOGGER.exception("API validation failed for %s", filename)
        return PlainTextResponse(f"Не удалось выполнить проверку файла: {exc}", status_code=500)

    return PlainTextResponse(format_validation_result_text(errors_ru))


async def ensure_indexes(collection: AsyncIOMotorCollection) -> None:
    await collection.create_index(
        [("publication_validation.status", 1), ("created_at", 1)],
        name="idx_registration_publication_validation",
    )


async def claim_registration(
    collection: AsyncIOMotorCollection,
    *,
    processing_timeout_sec: int,
) -> dict[str, Any] | None:
    claimed_at = now_utc()
    stale_before = claimed_at - timedelta(seconds=processing_timeout_sec)
    return await collection.find_one_and_update(
        {
            "publication_file.data": {"$exists": True},
            "$or": [
                {"publication_validation.status": {"$exists": False}},
                {"publication_validation.status": WAITING_STATUS},
                {
                    "publication_validation.status": PROCESSING_STATUS,
                    "publication_validation.started_at": {"$lte": stale_before},
                },
            ],
        },
        {
            "$set": {
                "publication_validation.status": PROCESSING_STATUS,
                "publication_validation.summary": "Идёт автоматическая проверка файла публикации.",
                "publication_validation.errors": [],
                "publication_validation.checked_at": None,
                "publication_validation.started_at": claimed_at,
                "publication_validation.updated_at": claimed_at,
                "publication_validation.last_error": "",
            }
        },
        sort=[("created_at", 1)],
        return_document=ReturnDocument.AFTER,
    )


async def mark_validation_complete(
    collection: AsyncIOMotorCollection,
    registration_id: Any,
    errors: list[str],
    errors_eng: list[str],
) -> None:
    checked_at = now_utc()
    if errors:
        status = FAILED_VALIDATION_STATUS
        summary = "Автоматическая проверка завершена: найдены замечания."
    else:
        status = PASSED_STATUS
        summary = "Автоматическая проверка завершена: ошибок не найдено."

    await collection.update_one(
        {"_id": registration_id},
        {
            "$set": {
                "publication_validation.status": status,
                "publication_validation.summary": summary,
                "publication_validation.errors": errors,
                "publication_validation.checked_at": checked_at,
                "publication_validation.updated_at": checked_at,
                "publication_validation.last_error": "",
            }
        },
    )


async def mark_validation_error(
    collection: AsyncIOMotorCollection,
    registration_id: Any,
    *,
    error: str,
) -> None:
    checked_at = now_utc()
    await collection.update_one(
        {"_id": registration_id},
        {
            "$set": {
                "publication_validation.status": SYSTEM_ERROR_STATUS,
                "publication_validation.summary": "Не удалось выполнить автоматическую проверку файла публикации.",
                "publication_validation.errors": [],
                "publication_validation.checked_at": checked_at,
                "publication_validation.updated_at": checked_at,
                "publication_validation.last_error": error,
            }
        },
    )


async def process_registrations(settings: Settings) -> None:
    client = AsyncIOMotorClient(settings.mongo_uri)
    collection = client[settings.mongo_db][settings.registrations_collection]
    stop_event = asyncio.Event()

    loop = asyncio.get_running_loop()
    for signame in ("SIGINT", "SIGTERM"):
        if hasattr(signal, signame):
            try:
                loop.add_signal_handler(getattr(signal, signame), stop_event.set)
            except (NotImplementedError, RuntimeError):
                pass

    try:
        await ensure_indexes(collection)
        LOGGER.info("Checker started. Poll interval: %ss", settings.poll_interval_sec)
        while not stop_event.is_set():
            record = await claim_registration(
                collection,
                processing_timeout_sec=settings.processing_timeout_sec,
            )
            if record is None:
                try:
                    await asyncio.wait_for(stop_event.wait(), timeout=settings.poll_interval_sec)
                except asyncio.TimeoutError:
                    pass
                continue

            registration_id = record["_id"]
            file_info = record.get("publication_file") or {}
            file_data = file_info.get("data")
            if not file_data:
                await mark_validation_error(
                    collection,
                    registration_id,
                    error="В заявке отсутствует содержимое файла публикации.",
                )
                continue

            try:
                errors, errors_eng = await asyncio.to_thread(validate_publication_content, bytes(file_data))
            except Exception as exc:
                LOGGER.exception("Validation failed for registration %s", registration_id)
                await mark_validation_error(collection, registration_id, error=str(exc))
            else:
                LOGGER.info("Validation finished for registration %s", registration_id)
                await mark_validation_complete(collection, registration_id, errors, errors_eng)
    finally:
        client.close()


def configure_logging(level_name: str) -> None:
    level = getattr(logging, level_name.upper(), logging.INFO)
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    )


def main() -> None:
    settings = Settings.from_env()
    configure_logging(settings.log_level)
    asyncio.run(process_registrations(settings))


if __name__ == "__main__":
    main()
