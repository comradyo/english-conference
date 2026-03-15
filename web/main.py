from __future__ import annotations

from datetime import timedelta
from html import escape
import httpx
from urllib.parse import quote

from bson.binary import Binary
from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import RedirectResponse, Response
from pydantic import ValidationError
from pymongo.errors import DuplicateKeyError

from i18n import field_label, notice_text, text
from models import (
    AccountLoginPayload,
    AccountRegistrationPayload,
    ConferenceRegistrationPayload,
    PasswordResetConfirmPayload,
    PasswordResetRequestPayload,
    REVIEW_STATUSES,
)
from render import (
    layout,
    render_auth_page,
    render_conference_form,
    render_forbidden,
    render_invalid_reset_token_page,
    render_password_reset_page,
    render_records_page,
)
from security import hash_password, verify_password
from services import (
    build_initial_publication_validation,
    build_registration_update_email_task,
    build_password_reset_email_task,
    apply_language_cookie,
    clear_session_cookie,
    create_password_reset_token,
    create_session,
    is_admin_email,
    localized_redirect,
    load_current_user,
    normalize_email,
    now_utc,
    parse_object_id,
    request_language,
    read_docx,
    remove_current_session,
    require_admin,
    require_user,
    set_session_cookie,
    validation_message,
)
from state import lifespan

app = FastAPI(title="Conference Personal Cabinet", lifespan=lifespan)

PENDING_REVIEW_STATUS = REVIEW_STATUSES[0]
REVISION_REVIEW_STATUS = REVIEW_STATUSES[2]


def with_language(request: Request, response):
    apply_language_cookie(response, request_language(request))
    return response


def optional_form_value(value: str) -> str | None:
    stripped = value.strip()
    return stripped or None


def file_document(upload: UploadFile | None, content: bytes | None) -> dict[str, object] | None:
    if upload is None or content is None:
        return None
    filename = (upload.filename or "").strip()
    if not filename:
        return None
    return {
        "filename": filename,
        "content_type": upload.content_type or "application/octet-stream",
        "size_bytes": len(content),
        "data": Binary(content),
    }


def registration_comment_entry(
    *,
    author_role: str,
    author_email: str,
    comment_text: str,
) -> dict[str, object]:
    return {
        "author_role": author_role,
        "author_email": normalize_email(author_email),
        "text": comment_text,
        "created_at": now_utc(),
    }


def conference_form_values(
    *,
    last_name: str,
    first_name: str,
    middle_name: str,
    place_of_study: str,
    department: str,
    place_of_work: str,
    job_title: str,
    phone: str,
    email: str,
    participation: str,
    section: str,
    publication_title: str,
    foreign_language_consultant: str,
) -> dict[str, str]:
    return {
        "last_name": last_name,
        "first_name": first_name,
        "middle_name": middle_name,
        "place_of_study": place_of_study,
        "department": department,
        "place_of_work": place_of_work,
        "job_title": job_title,
        "phone": phone,
        "email": email,
        "participation": participation,
        "section": section,
        "publication_title": publication_title,
        "foreign_language_consultant": foreign_language_consultant,
    }


def conference_form_values_from_record(record: dict[str, object]) -> dict[str, str]:
    return conference_form_values(
        last_name=str(record.get("last_name") or ""),
        first_name=str(record.get("first_name") or ""),
        middle_name=str(record.get("middle_name") or ""),
        place_of_study=str(record.get("place_of_study") or ""),
        department=str(record.get("department") or ""),
        place_of_work=str(record.get("place_of_work") or ""),
        job_title=str(record.get("job_title") or ""),
        phone=str(record.get("phone") or ""),
        email=str(record.get("email") or ""),
        participation=str(record.get("participation") or ""),
        section=str(record.get("section") or ""),
        publication_title=str(record.get("publication_title") or ""),
        foreign_language_consultant=str(record.get("foreign_language_consultant") or ""),
    )


def registration_file_name(record: dict[str, object], field_name: str) -> str:
    file_info = record.get(field_name)
    if not isinstance(file_info, dict):
        return ""
    return str(file_info.get("filename") or "").strip()


async def find_revision_registration_for_user(
    request: Request,
    *,
    registration_id: str,
    owner_user_id,
) -> dict | None:
    object_id = parse_object_id(registration_id)
    if object_id is None:
        return None
    return await request.app.state.registrations_collection.find_one(
        {
            "_id": object_id,
            "owner_user_id": owner_user_id,
            "review_status": REVISION_REVIEW_STATUS,
        },
        {"publication_file.data": 0, "expert_opinion_file.data": 0},
    )


async def request_publication_precheck(
    request: Request,
    *,
    filename: str,
    content: bytes,
    content_type: str,
) -> str:
    settings = request.app.state.settings
    target_url = settings.checker_api_url
    lang = request_language(request)
    if not target_url:
        raise HTTPException(status_code=503, detail=text(lang, "request_precheck_service_not_configured"))

    async with httpx.AsyncClient(timeout=settings.checker_api_timeout_sec) as client:
        try:
            response = await client.post(
                target_url,
                files={
                    "file": (
                        filename,
                        content,
                        content_type or "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    )
                },
            )
        except httpx.RequestError as exc:
            raise HTTPException(
                status_code=502,
                detail=text(lang, "request_precheck_service_unavailable", error=exc),
            ) from exc

    response_text = response.text.strip() or text(lang, "request_precheck_empty_result")
    if response.status_code == 400:
        raise HTTPException(status_code=400, detail=response_text)
    if response.is_error:
        raise HTTPException(status_code=502, detail=response_text)
    return response_text


async def find_valid_password_reset_token(request: Request, token: str) -> dict | None:
    return await request.app.state.password_reset_tokens_collection.find_one(
        {
            "token": token,
            "used_at": None,
            "expires_at": {"$gt": now_utc()},
        }
    )


def build_error_page(
    request: Request,
    *,
    current_user: dict | None,
    lang: str,
    title_key: str,
    body_html: str,
    error_text: str,
    status_code: int,
):
    response = layout(
        text(lang, title_key),
        body_html,
        current_user=current_user,
        error=error_text,
        lang=lang,
    )
    response.status_code = status_code
    return with_language(request, response)


async def _download_admin_file_impl(
    registration_id: str,
    file_kind: str,
    request: Request,
):
    lang = request_language(request)
    current_user, response = await require_admin(request, lambda user: render_forbidden(user, lang=lang))
    if response:
        return with_language(request, response)

    file_map = {
        "publication": ("publication_file", field_label(lang, "publication_file"), "publication.docx"),
        "expert-opinion": ("expert_opinion_file", field_label(lang, "expert_opinion_file"), "expert-opinion.docx"),
    }
    selected_file = file_map.get(file_kind)
    if selected_file is None:
        return build_error_page(
            request,
            current_user=current_user,
            lang=lang,
            title_key="error_title",
            body_html=f'<div class="empty">{escape(text(lang, "invalid_file_kind_body"))}</div>',
            error_text=text(lang, "invalid_file_kind_error"),
            status_code=404,
        )

    file_field, file_label_text, default_filename = selected_file
    object_id = parse_object_id(registration_id)
    if object_id is None:
        return build_error_page(
            request,
            current_user=current_user,
            lang=lang,
            title_key="error_title",
            body_html=f'<div class="empty">{escape(text(lang, "record_not_found_body"))}</div>',
            error_text=text(lang, "invalid_record_id_error"),
            status_code=404,
        )

    record = await request.app.state.registrations_collection.find_one(
        {"_id": object_id},
        {file_field: 1},
    )
    if not record:
        return build_error_page(
            request,
            current_user=current_user,
            lang=lang,
            title_key="error_title",
            body_html=f'<div class="empty">{escape(text(lang, "record_not_found_body"))}</div>',
            error_text=text(lang, "record_not_found_error"),
            status_code=404,
        )

    file_info = record.get(file_field) or {}
    file_data = file_info.get("data")
    if not file_data:
        return build_error_page(
            request,
            current_user=current_user,
            lang=lang,
            title_key="error_title",
            body_html=f'<div class="empty">{escape(file_label_text)} {escape(text(lang, "record_not_found_body").lower())}</div>',
            error_text=f"{file_label_text} {text(lang, 'record_not_found_error').lower()}",
            status_code=404,
        )

    file_name = str(file_info.get("filename") or default_filename)
    content_type = str(file_info.get("content_type") or "application/octet-stream")
    headers = {
        "Content-Disposition": f"attachment; filename*=UTF-8''{quote(file_name)}",
    }
    return Response(content=bytes(file_data), media_type=content_type, headers=headers)


async def _save_admin_comment_impl(
    registration_id: str,
    request: Request,
    review_status: str,
    comment_text: str,
):
    lang = request_language(request)
    current_user, response = await require_admin(request, lambda user: render_forbidden(user, lang=lang))
    if response:
        return with_language(request, response)

    if review_status not in REVIEW_STATUSES:
        return build_error_page(
            request,
            current_user=current_user,
            lang=lang,
            title_key="error_title",
            body_html=f'<div class="empty">{escape(text(lang, "invalid_status_body"))}</div>',
            error_text=text(lang, "invalid_status_error"),
            status_code=400,
        )

    object_id = parse_object_id(registration_id)
    if object_id is None:
        return build_error_page(
            request,
            current_user=current_user,
            lang=lang,
            title_key="error_title",
            body_html=f'<div class="empty">{escape(text(lang, "record_not_found_body"))}</div>',
            error_text=text(lang, "invalid_record_id_error"),
            status_code=404,
        )

    record = await request.app.state.registrations_collection.find_one(
        {"_id": object_id},
        {"publication_file.data": 0, "expert_opinion_file.data": 0},
    )
    if not record:
        return build_error_page(
            request,
            current_user=current_user,
            lang=lang,
            title_key="error_title",
            body_html=f'<div class="empty">{escape(text(lang, "record_not_found_body"))}</div>',
            error_text=text(lang, "record_not_found_error"),
            status_code=404,
        )

    trimmed_comment = comment_text.strip()
    appended_comment = None
    update_doc: dict[str, dict[str, object]] = {
        "$set": {
            "review_status": review_status,
            "updated_at": now_utc(),
        }
    }
    if trimmed_comment:
        appended_comment = registration_comment_entry(
            author_role="admin",
            author_email=str(current_user["email"]),
            comment_text=trimmed_comment,
        )
        update_doc["$push"] = {"comments": appended_comment}

    update_result = await request.app.state.registrations_collection.update_one(
        {"_id": object_id},
        update_doc,
    )
    if update_result.matched_count == 0:
        return build_error_page(
            request,
            current_user=current_user,
            lang=lang,
            title_key="error_title",
            body_html=f'<div class="empty">{escape(text(lang, "record_not_found_body"))}</div>',
            error_text=text(lang, "record_not_found_error"),
            status_code=404,
        )

    updated_record = dict(record)
    current_comments = record.get("comments")
    updated_comments = [item for item in current_comments if isinstance(item, dict)] if isinstance(current_comments, list) else []
    if appended_comment is not None:
        updated_comments.append(appended_comment)
    updated_record["comments"] = updated_comments
    updated_record["review_status"] = review_status
    back_link_html = (
        f'<a href="/all_applications?selected={registration_id}">'
        f'{escape(text(lang, "back_to_records_link"))}</a>'
    )
    try:
        task = build_registration_update_email_task(updated_record, lang=lang)
        await request.app.state.email_tasks_collection.insert_one(task)
    except RuntimeError as exc:
        return build_error_page(
            request,
            current_user=current_user,
            lang=lang,
            title_key="task_not_queued_title",
            body_html=f'<div class="empty">{text(lang, "email_task_runtime_body", link=back_link_html)}</div>',
            error_text=str(exc),
            status_code=502,
        )
    except Exception as exc:
        return build_error_page(
            request,
            current_user=current_user,
            lang=lang,
            title_key="task_not_queued_title",
            body_html=f'<div class="empty">{text(lang, "email_task_storage_body", link=back_link_html)}</div>',
            error_text=text(lang, "queue_write_failed", error=exc),
            status_code=502,
        )

    return localized_redirect(
        request,
        f"/all_applications?notice=comment_saved&selected={registration_id}",
        status_code=303,
    )


@app.get("/", include_in_schema=False)
async def auth_page(request: Request):
    lang = request_language(request)
    current_user = await load_current_user(request)
    if current_user is not None:
        return localized_redirect(request, "/my-registrations", status_code=303)
    return with_language(
        request,
        render_auth_page(
            success=notice_text(lang, request.query_params.get("notice")),
            lang=lang,
        ),
    )


@app.post("/forgot-password", include_in_schema=False)
async def forgot_password(
    request: Request,
    email: str = Form(...),
):
    lang = request_language(request)
    forgot_values = {"email": email}
    try:
        payload = PasswordResetRequestPayload(email=normalize_email(email))
    except ValidationError:
        response = render_auth_page(
            error=text(lang, "invalid_email"),
            forgot_values=forgot_values,
            lang=lang,
        )
        response.status_code = 400
        return with_language(request, response)

    normalized_email = normalize_email(str(payload.email))
    user = await request.app.state.users_collection.find_one({"email": normalized_email})
    if user is not None:
        token = create_password_reset_token()
        created_at = now_utc()
        expires_at = created_at + timedelta(minutes=request.app.state.settings.password_reset_ttl_minutes)
        token_doc = {
            "token": token,
            "user_id": user["_id"],
            "email": user["email"],
            "created_at": created_at,
            "updated_at": created_at,
            "expires_at": expires_at,
            "used_at": None,
        }
        reset_base_url = str(request.url_for("reset_password_page_view"))
        if reset_base_url.startswith("http://"):
            reset_base_url = f"https://{reset_base_url[len('http://'):]}"
        reset_url = f'{reset_base_url}?token={quote(token, safe="")}&lang={quote(lang, safe="")}'
        try:
            await request.app.state.password_reset_tokens_collection.insert_one(token_doc)
            task = build_password_reset_email_task(
                recipient_email=user["email"],
                reset_url=reset_url,
                expires_at=expires_at,
                lang=lang,
            )
            await request.app.state.email_tasks_collection.insert_one(task)
        except Exception as exc:
            await request.app.state.password_reset_tokens_collection.delete_one({"token": token})
            response = render_auth_page(
                error=text(lang, "forgot_email_task_failed", error=exc),
                forgot_values=forgot_values,
                lang=lang,
            )
            response.status_code = 502
            return with_language(request, response)

    return localized_redirect(request, "/?notice=password_reset_email_queued", status_code=303)


@app.get("/reset-password", include_in_schema=False)
async def reset_password_page_view(
    request: Request,
    token: str = "",
):
    lang = request_language(request)
    normalized_token = token.strip()
    if not normalized_token:
        response = render_invalid_reset_token_page(text(lang, "reset_missing_token"), lang=lang)
        response.status_code = 400
        return with_language(request, response)

    token_doc = await find_valid_password_reset_token(request, normalized_token)
    if token_doc is None:
        response = render_invalid_reset_token_page(text(lang, "reset_invalid_token"), lang=lang)
        response.status_code = 400
        return with_language(request, response)

    return with_language(request, render_password_reset_page(normalized_token, lang=lang))


@app.post("/reset-password", include_in_schema=False)
async def reset_password_submit(
    request: Request,
    token: str = Form(...),
    password: str = Form(...),
    password_repeat: str = Form(...),
):
    lang = request_language(request)
    try:
        payload = PasswordResetConfirmPayload(
            token=token,
            password=password,
            password_repeat=password_repeat,
        )
    except ValidationError:
        response = render_password_reset_page(token.strip(), error=text(lang, "password_too_short"), lang=lang)
        response.status_code = 400
        return with_language(request, response)

    if payload.password != payload.password_repeat:
        response = render_password_reset_page(payload.token, error=text(lang, "auth_passwords_mismatch"), lang=lang)
        response.status_code = 400
        return with_language(request, response)

    token_doc = await find_valid_password_reset_token(request, payload.token)
    if token_doc is None:
        response = render_invalid_reset_token_page(text(lang, "reset_invalid_token"), lang=lang)
        response.status_code = 400
        return with_language(request, response)

    password_data = hash_password(payload.password)
    now = now_utc()
    user_update = await request.app.state.users_collection.update_one(
        {"_id": token_doc["user_id"]},
        {"$set": password_data},
    )
    if user_update.matched_count == 0:
        response = render_invalid_reset_token_page(text(lang, "reset_user_not_found"), lang=lang)
        response.status_code = 404
        return with_language(request, response)

    await request.app.state.password_reset_tokens_collection.update_many(
        {
            "user_id": token_doc["user_id"],
            "used_at": None,
        },
        {
            "$set": {
                "used_at": now,
                "updated_at": now,
            }
        },
    )
    await request.app.state.sessions_collection.delete_many({"user_id": token_doc["user_id"]})

    return localized_redirect(request, "/?notice=password_changed", status_code=303)


@app.post("/register-account", include_in_schema=False)
async def register_account(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    password_repeat: str = Form(...),
):
    lang = request_language(request)
    register_values = {"email": email}
    try:
        payload = AccountRegistrationPayload(
            email=normalize_email(email),
            password=password,
            password_repeat=password_repeat,
        )
    except ValidationError as exc:
        response = render_auth_page(
            error=validation_message(exc, text(lang, "auth_registration_invalid"), lang=lang),
            register_values=register_values,
            lang=lang,
        )
        response.status_code = 400
        return with_language(request, response)

    if payload.password != payload.password_repeat:
        response = render_auth_page(
            error=text(lang, "auth_passwords_mismatch"),
            register_values=register_values,
            lang=lang,
        )
        response.status_code = 400
        return with_language(request, response)

    normalized_email = normalize_email(str(payload.email))
    user_doc = {
        "email": normalized_email,
        "created_at": now_utc(),
        "is_admin": is_admin_email(request.app.state.settings, normalized_email),
    }
    user_doc.update(hash_password(payload.password))

    try:
        result = await request.app.state.users_collection.insert_one(user_doc)
    except DuplicateKeyError:
        response = render_auth_page(
            error=text(lang, "auth_account_exists"),
            register_values=register_values,
            lang=lang,
        )
        response.status_code = 409
        return with_language(request, response)

    user = await request.app.state.users_collection.find_one({"_id": result.inserted_id})
    if user is None:
        raise HTTPException(status_code=500, detail=text(lang, "auth_user_create_failed"))

    token = await create_session(request, user)
    response = localized_redirect(request, "/my-registrations", status_code=303)
    set_session_cookie(response, request, token)
    return response


@app.post("/login", include_in_schema=False)
async def login(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
):
    lang = request_language(request)
    login_values = {"email": email}
    try:
        payload = AccountLoginPayload(email=normalize_email(email), password=password)
    except ValidationError:
        response = render_auth_page(
            error=text(lang, "auth_invalid_login_input"),
            login_values=login_values,
            lang=lang,
        )
        response.status_code = 400
        return with_language(request, response)

    normalized_email = normalize_email(str(payload.email))
    user = await request.app.state.users_collection.find_one({"email": normalized_email})
    if user is None or not verify_password(payload.password, user):
        response = render_auth_page(
            error=text(lang, "auth_invalid_credentials"),
            login_values=login_values,
            lang=lang,
        )
        response.status_code = 401
        return with_language(request, response)

    desired_admin = is_admin_email(request.app.state.settings, normalized_email)
    if bool(user.get("is_admin")) != desired_admin:
        await request.app.state.users_collection.update_one(
            {"_id": user["_id"]},
            {"$set": {"is_admin": desired_admin}},
        )
        user["is_admin"] = desired_admin

    token = await create_session(request, user)
    response = localized_redirect(request, "/my-registrations", status_code=303)
    set_session_cookie(response, request, token)
    return response


@app.get("/logout", include_in_schema=False)
async def logout(request: Request):
    await remove_current_session(request)
    response = localized_redirect(request, "/?notice=logged_out", status_code=303)
    clear_session_cookie(response, request)
    return response


@app.get("/conference/register")
async def conference_registration_page(request: Request):
    lang = request_language(request)
    current_user, response = await require_user(request)
    if response:
        return response
    return with_language(request, render_conference_form(current_user, lang=lang))


@app.get("/conference/register/{registration_id}/edit")
async def edit_conference_registration_page(
    registration_id: str,
    request: Request,
):
    lang = request_language(request)
    current_user, response = await require_user(request)
    if response:
        return response

    existing_record = await find_revision_registration_for_user(
        request,
        registration_id=registration_id,
        owner_user_id=current_user["_id"],
    )
    if existing_record is None:
        return localized_redirect(request, "/my-registrations?notice=edit_not_allowed", status_code=303)

    return with_language(
        request,
        render_conference_form(
            current_user,
            values=conference_form_values_from_record(existing_record),
            edit_registration_id=str(existing_record["_id"]),
            existing_publication_file_name=registration_file_name(existing_record, "publication_file"),
            existing_expert_opinion_file_name=registration_file_name(existing_record, "expert_opinion_file"),
            lang=lang,
        ),
    )


@app.post("/conference/precheck")
async def precheck_publication_file(
    request: Request,
    publication_file: UploadFile = File(...),
):
    lang = request_language(request)
    current_user, response = await require_user(request)
    if response:
        return response

    try:
        publication_file_content = await read_docx(
            publication_file,
            field_label=field_label(lang, "publication_file"),
            lang=lang,
        )
        if publication_file_content is None:
            raise HTTPException(status_code=500, detail=text(lang, "publication_read_failed"))
        result_text = await request_publication_precheck(
            request,
            filename=(publication_file.filename or "").strip() or "publication.docx",
            content=publication_file_content,
            content_type=publication_file.content_type or "",
        )
    except HTTPException as exc:
        result = render_conference_form(current_user, precheck_error=str(exc.detail), lang=lang)
        result.status_code = exc.status_code
        return with_language(request, result)

    result = render_conference_form(
        current_user,
        precheck_file_name=(publication_file.filename or "").strip(),
        precheck_result_text=result_text,
        lang=lang,
    )
    result.status_code = 200
    return with_language(request, result)


@app.post("/conference/register")
async def submit_conference_registration(
    request: Request,
    last_name: str = Form(...),
    first_name: str = Form(...),
    middle_name: str = Form(""),
    place_of_study: str = Form(...),
    department: str = Form(""),
    place_of_work: str = Form(...),
    job_title: str = Form(""),
    phone: str = Form(...),
    email: str = Form(...),
    participation: str = Form(...),
    section: str = Form(...),
    publication_title: str = Form(...),
    foreign_language_consultant: str = Form(...),
    publication_file: UploadFile = File(...),
    expert_opinion_file: UploadFile | None = File(None),
):
    lang = request_language(request)
    current_user, response = await require_user(request)
    if response:
        return response

    middle_name_value = optional_form_value(middle_name)
    department_value = optional_form_value(department)
    job_title_value = optional_form_value(job_title)
    form_values = conference_form_values(
        last_name=last_name,
        first_name=first_name,
        middle_name=middle_name,
        place_of_study=place_of_study,
        department=department,
        place_of_work=place_of_work,
        job_title=job_title,
        phone=phone,
        email=email,
        participation=participation,
        section=section,
        publication_title=publication_title,
        foreign_language_consultant=foreign_language_consultant,
    )

    try:
        payload = ConferenceRegistrationPayload(
            last_name=last_name,
            first_name=first_name,
            middle_name=middle_name_value,
            place_of_study=place_of_study,
            department=department_value,
            place_of_work=place_of_work,
            job_title=job_title_value,
            phone=phone,
            email=normalize_email(email),
            participation=participation,
            section=section,
            publication_title=publication_title,
            foreign_language_consultant=foreign_language_consultant,
        )
        publication_file_content = await read_docx(
            publication_file,
            field_label=field_label(lang, "publication_file"),
            lang=lang,
        )
        expert_opinion_content = await read_docx(
            expert_opinion_file,
            required=False,
            field_label=field_label(lang, "expert_opinion_file"),
            lang=lang,
        )
    except ValidationError as exc:
        result = render_conference_form(
            current_user,
            error=validation_message(exc, text(lang, "form_invalid"), lang=lang),
            values=form_values,
            lang=lang,
        )
        result.status_code = 400
        return with_language(request, result)
    except HTTPException as exc:
        result = render_conference_form(current_user, error=str(exc.detail), values=form_values, lang=lang)
        result.status_code = exc.status_code
        return with_language(request, result)

    if publication_file_content is None:
        raise HTTPException(status_code=500, detail=text(lang, "publication_read_failed"))

    await request.app.state.registrations_collection.insert_one(
        {
            "owner_user_id": current_user["_id"],
            "owner_email": current_user["email"],
            "form_language": lang,
            "last_name": payload.last_name,
            "first_name": payload.first_name,
            "middle_name": payload.middle_name,
            "place_of_study": payload.place_of_study,
            "department": payload.department,
            "place_of_work": payload.place_of_work,
            "job_title": payload.job_title,
            "phone": payload.phone,
            "email": normalize_email(str(payload.email)),
            "participation": payload.participation,
            "section": payload.section,
            "publication_title": payload.publication_title,
            "foreign_language_consultant": payload.foreign_language_consultant,
            "publication_file": file_document(publication_file, publication_file_content),
            "expert_opinion_file": file_document(expert_opinion_file, expert_opinion_content),
            "publication_validation": build_initial_publication_validation(),
            "review_status": PENDING_REVIEW_STATUS,
            "comments": [],
            "created_at": now_utc(),
        }
    )

    result = render_conference_form(
        current_user,
        success=text(lang, "registration_saved"),
        values={"email": current_user["email"]},
        lang=lang,
    )
    result.status_code = 201
    return with_language(request, result)


@app.post("/conference/register/{registration_id}/edit")
async def update_conference_registration(
    registration_id: str,
    request: Request,
    last_name: str = Form(...),
    first_name: str = Form(...),
    middle_name: str = Form(""),
    place_of_study: str = Form(...),
    department: str = Form(""),
    place_of_work: str = Form(...),
    job_title: str = Form(""),
    phone: str = Form(...),
    email: str = Form(...),
    participation: str = Form(...),
    section: str = Form(...),
    publication_title: str = Form(...),
    foreign_language_consultant: str = Form(...),
    publication_file: UploadFile | None = File(None),
    expert_opinion_file: UploadFile | None = File(None),
):
    lang = request_language(request)
    current_user, response = await require_user(request)
    if response:
        return response

    existing_record = await find_revision_registration_for_user(
        request,
        registration_id=registration_id,
        owner_user_id=current_user["_id"],
    )
    if existing_record is None:
        return localized_redirect(request, "/my-registrations?notice=edit_not_allowed", status_code=303)

    form_values = conference_form_values(
        last_name=last_name,
        first_name=first_name,
        middle_name=middle_name,
        place_of_study=place_of_study,
        department=department,
        place_of_work=place_of_work,
        job_title=job_title,
        phone=phone,
        email=email,
        participation=participation,
        section=section,
        publication_title=publication_title,
        foreign_language_consultant=foreign_language_consultant,
    )
    existing_publication_file_name = registration_file_name(existing_record, "publication_file")
    existing_expert_file_name = registration_file_name(existing_record, "expert_opinion_file")

    middle_name_value = optional_form_value(middle_name)
    department_value = optional_form_value(department)
    job_title_value = optional_form_value(job_title)

    try:
        payload = ConferenceRegistrationPayload(
            last_name=last_name,
            first_name=first_name,
            middle_name=middle_name_value,
            place_of_study=place_of_study,
            department=department_value,
            place_of_work=place_of_work,
            job_title=job_title_value,
            phone=phone,
            email=normalize_email(email),
            participation=participation,
            section=section,
            publication_title=publication_title,
            foreign_language_consultant=foreign_language_consultant,
        )
        publication_file_content = await read_docx(
            publication_file,
            required=False,
            field_label=field_label(lang, "publication_file"),
            lang=lang,
        )
        expert_opinion_content = await read_docx(
            expert_opinion_file,
            required=False,
            field_label=field_label(lang, "expert_opinion_file"),
            lang=lang,
        )
    except ValidationError as exc:
        result = render_conference_form(
            current_user,
            error=validation_message(exc, text(lang, "form_invalid"), lang=lang),
            values=form_values,
            edit_registration_id=str(existing_record["_id"]),
            existing_publication_file_name=existing_publication_file_name,
            existing_expert_opinion_file_name=existing_expert_file_name,
            lang=lang,
        )
        result.status_code = 400
        return with_language(request, result)
    except HTTPException as exc:
        result = render_conference_form(
            current_user,
            error=str(exc.detail),
            values=form_values,
            edit_registration_id=str(existing_record["_id"]),
            existing_publication_file_name=existing_publication_file_name,
            existing_expert_opinion_file_name=existing_expert_file_name,
            lang=lang,
        )
        result.status_code = exc.status_code
        return with_language(request, result)

    if publication_file_content is None and not existing_publication_file_name:
        result = render_conference_form(
            current_user,
            error=text(lang, "docx_file_required", field=field_label(lang, "publication_file")),
            values=form_values,
            edit_registration_id=str(existing_record["_id"]),
            existing_publication_file_name=existing_publication_file_name,
            existing_expert_opinion_file_name=existing_expert_file_name,
            lang=lang,
        )
        result.status_code = 400
        return with_language(request, result)

    update_fields: dict[str, object] = {
        "owner_email": current_user["email"],
        "form_language": lang,
        "last_name": payload.last_name,
        "first_name": payload.first_name,
        "middle_name": payload.middle_name,
        "place_of_study": payload.place_of_study,
        "department": payload.department,
        "place_of_work": payload.place_of_work,
        "job_title": payload.job_title,
        "phone": payload.phone,
        "email": normalize_email(str(payload.email)),
        "participation": payload.participation,
        "section": payload.section,
        "publication_title": payload.publication_title,
        "foreign_language_consultant": payload.foreign_language_consultant,
        "publication_validation": build_initial_publication_validation(),
        "review_status": PENDING_REVIEW_STATUS,
        "updated_at": now_utc(),
    }
    if publication_file_content is not None:
        update_fields["publication_file"] = file_document(publication_file, publication_file_content)
    if expert_opinion_content is not None:
        update_fields["expert_opinion_file"] = file_document(expert_opinion_file, expert_opinion_content)

    update_result = await request.app.state.registrations_collection.update_one(
        {
            "_id": existing_record["_id"],
            "owner_user_id": current_user["_id"],
            "review_status": REVISION_REVIEW_STATUS,
        },
        {"$set": update_fields},
    )
    if update_result.matched_count == 0:
        return localized_redirect(request, "/my-registrations?notice=edit_not_allowed", status_code=303)

    return localized_redirect(request, "/my-registrations?notice=registration_updated", status_code=303)


@app.post("/my-registrations/comment/{registration_id}", include_in_schema=False)
async def save_author_comment(
    registration_id: str,
    request: Request,
    comment_text: str = Form(""),
):
    current_user, response = await require_user(request)
    if response:
        return response

    trimmed_comment = comment_text.strip()
    if not trimmed_comment:
        return localized_redirect(request, "/my-registrations?notice=comment_empty", status_code=303)

    object_id = parse_object_id(registration_id)
    if object_id is None:
        return localized_redirect(request, "/my-registrations?notice=comment_add_failed", status_code=303)

    appended_comment = registration_comment_entry(
        author_role="author",
        author_email=str(current_user["email"]),
        comment_text=trimmed_comment,
    )
    update_result = await request.app.state.registrations_collection.update_one(
        {
            "_id": object_id,
            "owner_user_id": current_user["_id"],
        },
        {
            "$push": {"comments": appended_comment},
            "$set": {"updated_at": now_utc()},
        },
    )
    if update_result.matched_count == 0:
        return localized_redirect(request, "/my-registrations?notice=comment_add_failed", status_code=303)

    return localized_redirect(request, "/my-registrations?notice=comment_added", status_code=303)


@app.post("/my-registrations/delete/{registration_id}", include_in_schema=False)
async def delete_author_registration(
    registration_id: str,
    request: Request,
):
    current_user, response = await require_user(request)
    if response:
        return response

    object_id = parse_object_id(registration_id)
    if object_id is None:
        return localized_redirect(request, "/my-registrations?notice=delete_not_allowed", status_code=303)

    delete_result = await request.app.state.registrations_collection.delete_one(
        {
            "_id": object_id,
            "owner_user_id": current_user["_id"],
            "review_status": PENDING_REVIEW_STATUS,
        }
    )
    if delete_result.deleted_count == 0:
        return localized_redirect(request, "/my-registrations?notice=delete_not_allowed", status_code=303)

    return localized_redirect(request, "/my-registrations?notice=registration_deleted", status_code=303)


@app.get("/my-registrations")
async def my_registrations(request: Request):
    lang = request_language(request)
    current_user, response = await require_user(request)
    if response:
        return response

    records = await request.app.state.registrations_collection.find(
        {"owner_user_id": current_user["_id"]},
        {"publication_file.data": 0, "expert_opinion_file.data": 0},
    ).sort("created_at", -1).to_list(length=200)

    return with_language(
        request,
        render_records_page(
            text(lang, "records_my_title"),
            current_user,
            records,
            admin_mode=False,
            success=notice_text(lang, request.query_params.get("notice")),
            empty_action_html=f' <a href="/conference/register">{escape(text(lang, "records_empty_action"))}</a>',
            empty_text=text(lang, "records_empty_my"),
            lang=lang,
        ),
    )


@app.get("/all_applications")
async def admin_registrations(request: Request):
    lang = request_language(request)
    current_user, response = await require_admin(request, lambda user: render_forbidden(user, lang=lang))
    if response:
        return with_language(request, response)

    records = await request.app.state.registrations_collection.find(
        {},
        {"publication_file.data": 0, "expert_opinion_file.data": 0},
    ).sort("created_at", -1).to_list(length=500)
    return with_language(
        request,
        render_records_page(
            text(lang, "records_admin_title"),
            current_user,
            records,
            admin_mode=True,
            success=notice_text(lang, request.query_params.get("notice")),
            empty_text=text(lang, "records_empty_admin"),
            selected_registration_id=request.query_params.get("selected"),
            lang=lang,
        ),
    )


@app.get("/all_applications/file/{registration_id}/{file_kind}", include_in_schema=False)
async def download_admin_file(
    registration_id: str,
    file_kind: str,
    request: Request,
):
    return await _download_admin_file_impl(registration_id, file_kind, request)


@app.post("/all_applications/comment/{registration_id}", include_in_schema=False)
async def save_admin_comment(
    registration_id: str,
    request: Request,
    review_status: str = Form(""),
    comment_text: str = Form(""),
):
    return await _save_admin_comment_impl(registration_id, request, review_status, comment_text)


@app.get("/health", include_in_schema=False)
async def health():
    return {"status": "ok"}


@app.get("/ready", include_in_schema=False)
async def ready(request: Request):
    try:
        await request.app.state.mongo_db.command("ping")
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"mongo not ready: {exc}") from exc
    return {"status": "ok"}
