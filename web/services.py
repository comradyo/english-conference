import asyncio
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage
import secrets
import smtplib
import ssl
from typing import Any

from bson import ObjectId
from fastapi import HTTPException, Request, Response, UploadFile
from fastapi.responses import RedirectResponse
from pydantic import ValidationError

from config import Settings
from models import MAX_FILE_SIZE_BYTES


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def normalize_email(value: str) -> str:
    return value.strip().lower()


def is_admin_email(settings: Settings, email: str) -> bool:
    return normalize_email(email) in settings.admin_emails


def validation_message(exc: ValidationError, fallback: str) -> str:
    first_error = exc.errors()[0]
    field_name = ".".join(str(part) for part in first_error.get("loc", []))
    if "email" in field_name:
        return "Введите корректный адрес электронной почты."
    if "password" in field_name:
        return "Пароль должен содержать не менее 8 символов."
    return fallback


def validate_docx(
    upload: UploadFile | None,
    *,
    required: bool = True,
    field_label: str = "Файл",
) -> bool:
    if upload is None:
        if required:
            raise HTTPException(status_code=400, detail=f"{field_label}: файл обязателен.")
        return False
    filename = (upload.filename or "").strip()
    if not filename:
        if required:
            raise HTTPException(status_code=400, detail=f"{field_label}: файл обязателен.")
        return False
    if not filename.lower().endswith(".docx"):
        raise HTTPException(status_code=400, detail=f"{field_label}: можно загрузить только файл в формате .docx.")
    return True


async def read_docx(
    upload: UploadFile | None,
    *,
    required: bool = True,
    field_label: str = "Файл",
) -> bytes | None:
    if not validate_docx(upload, required=required, field_label=field_label):
        return None
    content = await upload.read()
    if not content:
        raise HTTPException(status_code=400, detail=f"{field_label}: загруженный файл пуст.")
    if len(content) > MAX_FILE_SIZE_BYTES:
        raise HTTPException(
            status_code=400,
            detail=f"{field_label}: размер файла превышает допустимые {MAX_FILE_SIZE_BYTES} байт.",
        )
    return content


def set_session_cookie(response: Response, request: Request, token: str) -> None:
    settings: Settings = request.app.state.settings
    response.set_cookie(
        key=settings.session_cookie_name,
        value=token,
        httponly=True,
        samesite="lax",
        secure=False,
        max_age=settings.session_ttl_hours * 3600,
        path="/",
    )


def clear_session_cookie(response: Response, request: Request) -> None:
    settings: Settings = request.app.state.settings
    response.delete_cookie(key=settings.session_cookie_name, path="/")


async def create_session(request: Request, user: dict[str, Any]) -> str:
    token = secrets.token_urlsafe(32)
    expires_at = now_utc() + timedelta(hours=request.app.state.settings.session_ttl_hours)
    await request.app.state.sessions_collection.insert_one(
        {
            "token": token,
            "user_id": user["_id"],
            "created_at": now_utc(),
            "expires_at": expires_at,
        }
    )
    return token


async def remove_current_session(request: Request) -> None:
    settings: Settings = request.app.state.settings
    token = request.cookies.get(settings.session_cookie_name)
    if token:
        await request.app.state.sessions_collection.delete_one({"token": token})


async def load_current_user(request: Request) -> dict[str, Any] | None:
    settings: Settings = request.app.state.settings
    token = request.cookies.get(settings.session_cookie_name)
    if not token:
        return None

    session = await request.app.state.sessions_collection.find_one(
        {
            "token": token,
            "expires_at": {"$gt": now_utc()},
        }
    )
    if not session:
        return None

    user = await request.app.state.users_collection.find_one({"_id": session["user_id"]})
    if not user:
        await request.app.state.sessions_collection.delete_one({"_id": session["_id"]})
        return None

    desired_admin = is_admin_email(settings, str(user["email"]))
    if bool(user.get("is_admin")) != desired_admin:
        await request.app.state.users_collection.update_one(
            {"_id": user["_id"]},
            {"$set": {"is_admin": desired_admin}},
        )
        user["is_admin"] = desired_admin

    return user


async def require_user(request: Request):
    user = await load_current_user(request)
    if user is None:
        return None, RedirectResponse(url="/?notice=login_required", status_code=303)
    return user, None


async def require_admin(request: Request, forbidden_response_factory):
    user, response = await require_user(request)
    if response:
        return None, response
    if not user.get("is_admin"):
        return None, forbidden_response_factory(user)
    return user, None


def parse_object_id(value: str) -> ObjectId | None:
    try:
        return ObjectId(value)
    except Exception:
        return None


def notification_email_configured(settings: Settings) -> bool:
    import os
    print(os.getenv("WEB_NOTIFICATION_EMAIL_PASSWORD", ""))
    print(settings.notification_email_password)
    print(settings.notification_email_sender,
          settings.notification_email_password,
          settings.notification_email_smtp_host,
          settings.notification_email_smtp_port > 0)
    return all(
        [
            settings.notification_email_sender,
            settings.notification_email_password,
            settings.notification_email_smtp_host,
            settings.notification_email_smtp_port > 0,
        ]
    )


def _send_message_via_smtp(settings: Settings, message: EmailMessage) -> None:
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


async def send_registration_update_email(settings: Settings, record: dict[str, Any]) -> None:
    if not notification_email_configured(settings):
        raise RuntimeError(
            "Почтовые уведомления не настроены: заполните WEB_NOTIFICATION_EMAIL_* переменные среды."
        )

    recipient = normalize_email(str(record.get("email") or ""))
    if "@" not in recipient:
        raise RuntimeError("В заявке не указан корректный адрес электронной почты для уведомления.")

    last_name = str(record.get("last_name") or "").strip()
    first_name = str(record.get("first_name") or "").strip()
    middle_name = str(record.get("middle_name") or "").strip()
    full_name = " ".join(part for part in [last_name, first_name, middle_name] if part) or "участник"
    publication_title = str(record.get("publication_title") or "").strip() or "Без названия"
    review_status = str(record.get("review_status") or "").strip() or "На рассмотрении"
    admin_comment = str(record.get("admin_comment") or "").strip() or "Комментарий не указан."
    updated_at = now_utc().astimezone(timezone(timedelta(hours=3))).strftime("%d.%m.%Y %H:%M (МСК)")

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
                f"Участник: {full_name}",
                f"Название публикации: {publication_title}",
                f"Статус заявки: {review_status}",
                f"Комментарий администратора: {admin_comment}",
                f"Время обновления: {updated_at}",
                "",
                "Это письмо отправлено автоматически.",
            ]
        )
    )

    try:
        await asyncio.to_thread(_send_message_via_smtp, settings, message)
    except Exception as exc:
        raise RuntimeError(f"Не удалось отправить email-уведомление: {exc}") from exc
