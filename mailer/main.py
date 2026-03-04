from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage
import logging
import os
import signal
import smtplib
import ssl
from typing import Any

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorCollection
from pymongo import ReturnDocument


LOGGER = logging.getLogger("mailer")
UTC = timezone.utc
MOSCOW_TZ = timezone(timedelta(hours=3), name="UTC+3")


def now_utc() -> datetime:
    return datetime.now(UTC)


def normalize_email(value: str) -> str:
    return value.strip().lower()


@dataclass(frozen=True)
class Settings:
    mongo_uri: str
    mongo_db: str
    email_tasks_collection: str
    notification_email_sender: str
    notification_email_password: str
    notification_email_smtp_host: str
    notification_email_smtp_port: int
    notification_email_use_ssl: bool
    poll_interval_sec: int
    retry_delay_sec: int
    max_attempts: int
    log_level: str

    @classmethod
    def from_env(cls) -> "Settings":
        use_ssl = os.getenv("WEB_NOTIFICATION_EMAIL_USE_SSL", "true").strip().lower() not in {
            "0",
            "false",
            "no",
        }
        return cls(
            mongo_uri=os.getenv("MONGO_URI", "mongodb://localhost:27017"),
            mongo_db=os.getenv("MONGO_DB", "eng_conference"),
            email_tasks_collection=os.getenv("WEB_EMAIL_TASKS_COLLECTION", "email_tasks"),
            notification_email_sender=os.getenv(
                "WEB_NOTIFICATION_EMAIL_SENDER",
                "graduate.applications@yandex.ru",
            ).strip(),
            notification_email_password=os.getenv("WEB_NOTIFICATION_EMAIL_PASSWORD", ""),
            notification_email_smtp_host=os.getenv("WEB_NOTIFICATION_EMAIL_SMTP_HOST", "smtp.yandex.ru").strip(),
            notification_email_smtp_port=int(os.getenv("WEB_NOTIFICATION_EMAIL_SMTP_PORT", "465")),
            notification_email_use_ssl=use_ssl,
            poll_interval_sec=max(1, int(os.getenv("MAILER_POLL_INTERVAL_SEC", "5"))),
            retry_delay_sec=max(5, int(os.getenv("MAILER_RETRY_DELAY_SEC", "60"))),
            max_attempts=max(1, int(os.getenv("MAILER_MAX_ATTEMPTS", "5"))),
            log_level=os.getenv("LOG_LEVEL", "info").strip().upper() or "INFO",
        )


def notification_email_configured(settings: Settings) -> bool:
    return all(
        [
            settings.notification_email_sender,
            settings.notification_email_password,
            settings.notification_email_smtp_host,
            settings.notification_email_smtp_port > 0,
        ]
    )


def build_message(settings: Settings, payload: dict[str, Any]) -> EmailMessage:
    recipient = normalize_email(str(payload.get("recipient_email") or ""))
    if "@" not in recipient:
        raise RuntimeError("В задаче не указан корректный email получателя.")

    participant_name = str(payload.get("participant_name") or "Участник").strip() or "Участник"
    publication_title = str(payload.get("publication_title") or "Без названия").strip() or "Без названия"
    review_status = str(payload.get("review_status") or "На рассмотрении").strip() or "На рассмотрении"
    admin_comment = str(payload.get("admin_comment") or "Комментарий не указан.").strip() or "Комментарий не указан."
    registration_id = str(payload.get("registration_id") or "").strip()
    updated_at = now_utc().astimezone(MOSCOW_TZ).strftime("%d.%m.%Y %H:%M (МСК)")

    message = EmailMessage()
    message["Subject"] = "Обновление заявки на конференцию"
    message["From"] = settings.notification_email_sender
    message["To"] = recipient
    message.set_content(
        "\n".join(
            [
                "Здравствуйте!",
                "",
                "По вашей заявке на конференцию есть обновление.",
                f"ID заявки: {registration_id or 'Не указан'}",
                f"Участник: {participant_name}",
                f"Название публикации: {publication_title}",
                f"Статус заявки: {review_status}",
                f"Комментарий администратора: {admin_comment}",
                f"Время обновления: {updated_at}",
                "",
                "Это письмо отправлено автоматически.",
            ]
        )
    )
    return message


def send_message_via_smtp(settings: Settings, message: EmailMessage) -> None:
    context = ssl.create_default_context()
    if settings.notification_email_use_ssl:
        with smtplib.SMTP_SSL(
            settings.notification_email_smtp_host,
            settings.notification_email_smtp_port,
            timeout=20,
            context=context,
        ) as smtp:
            smtp.login(settings.notification_email_sender, settings.notification_email_password)
            smtp.send_message(message)
        return

    with smtplib.SMTP(
        settings.notification_email_smtp_host,
        settings.notification_email_smtp_port,
        timeout=20,
    ) as smtp:
        smtp.ehlo()
        smtp.starttls(context=context)
        smtp.ehlo()
        smtp.login(settings.notification_email_sender, settings.notification_email_password)
        smtp.send_message(message)


async def send_task_email(settings: Settings, task: dict[str, Any]) -> None:
    if not notification_email_configured(settings):
        raise RuntimeError("SMTP не настроен: заполните WEB_NOTIFICATION_EMAIL_* переменные среды.")

    payload = task.get("payload")
    if not isinstance(payload, dict):
        raise RuntimeError("У задачи отсутствует корректный payload.")

    message = build_message(settings, payload)
    await asyncio.to_thread(send_message_via_smtp, settings, message)


async def ensure_indexes(collection: AsyncIOMotorCollection) -> None:
    await collection.create_index(
        [("status", 1), ("available_at", 1), ("created_at", 1)],
        name="idx_email_tasks_status_available",
    )


async def claim_task(collection: AsyncIOMotorCollection) -> dict[str, Any] | None:
    claimed_at = now_utc()
    return await collection.find_one_and_update(
        {
            "kind": "registration_update_email",
            "status": {"$in": ["pending", "retry"]},
            "available_at": {"$lte": claimed_at},
        },
        {
            "$set": {
                "status": "processing",
                "updated_at": claimed_at,
                "started_at": claimed_at,
            },
            "$inc": {"attempts": 1},
        },
        sort=[("available_at", 1), ("created_at", 1)],
        return_document=ReturnDocument.AFTER,
    )


async def mark_task_sent(collection: AsyncIOMotorCollection, task_id: Any) -> None:
    sent_at = now_utc()
    await collection.update_one(
        {"_id": task_id},
        {
            "$set": {
                "status": "sent",
                "updated_at": sent_at,
                "sent_at": sent_at,
                "last_error": "",
            }
        },
    )


async def mark_task_failed(
    collection: AsyncIOMotorCollection,
    task: dict[str, Any],
    *,
    error: str,
    retry_delay_sec: int,
    max_attempts: int,
) -> None:
    failed_at = now_utc()
    attempts = int(task.get("attempts", 0))
    next_status = "failed" if attempts >= max_attempts else "retry"
    update: dict[str, Any] = {
        "status": next_status,
        "updated_at": failed_at,
        "last_error": error,
    }
    if next_status == "retry":
        update["available_at"] = failed_at + timedelta(seconds=retry_delay_sec)
    else:
        update["failed_at"] = failed_at
    await collection.update_one({"_id": task["_id"]}, {"$set": update})


async def process_tasks(settings: Settings) -> None:
    client = AsyncIOMotorClient(settings.mongo_uri)
    collection = client[settings.mongo_db][settings.email_tasks_collection]
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
        LOGGER.info("Mailer started. Poll interval: %ss", settings.poll_interval_sec)
        while not stop_event.is_set():
            task = await claim_task(collection)
            if task is None:
                try:
                    await asyncio.wait_for(stop_event.wait(), timeout=settings.poll_interval_sec)
                except asyncio.TimeoutError:
                    pass
                continue

            task_id = str(task.get("_id"))
            try:
                LOGGER.info("Processing task %s (attempt %s)", task_id, task.get("attempts"))
                await send_task_email(settings, task)
            except Exception as exc:
                LOGGER.exception("Task %s failed", task_id)
                await mark_task_failed(
                    collection,
                    task,
                    error=str(exc),
                    retry_delay_sec=settings.retry_delay_sec,
                    max_attempts=settings.max_attempts,
                )
            else:
                LOGGER.info("Task %s sent", task_id)
                await mark_task_sent(collection, task["_id"])
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
    asyncio.run(process_tasks(settings))


if __name__ == "__main__":
    main()
