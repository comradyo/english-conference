from __future__ import annotations

from urllib.parse import quote

from bson.binary import Binary
from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import RedirectResponse, Response
from pydantic import ValidationError
from pymongo.errors import DuplicateKeyError

from models import AccountLoginPayload, AccountRegistrationPayload, ConferenceRegistrationPayload, REVIEW_STATUSES
from render import (
    layout,
    notice_message,
    render_auth_page,
    render_conference_form,
    render_forbidden,
    render_records_page,
)
from security import hash_password, verify_password
from services import (
    clear_session_cookie,
    create_session,
    is_admin_email,
    load_current_user,
    normalize_email,
    now_utc,
    parse_object_id,
    read_docx,
    remove_current_session,
    require_admin,
    require_user,
    send_registration_update_email,
    set_session_cookie,
    validation_message,
)
from state import lifespan

app = FastAPI(title="Conference Personal Cabinet", lifespan=lifespan)


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


@app.get("/", include_in_schema=False)
async def auth_page(request: Request):
    current_user = await load_current_user(request)
    if current_user is not None:
        return RedirectResponse(url="/my-registrations", status_code=303)
    return render_auth_page(success=notice_message(request.query_params.get("notice")))


@app.post("/register-account", include_in_schema=False)
async def register_account(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    password_repeat: str = Form(...),
):
    register_values = {"email": email}
    try:
        payload = AccountRegistrationPayload(
            email=normalize_email(email),
            password=password,
            password_repeat=password_repeat,
        )
    except ValidationError as exc:
        response = render_auth_page(
            error=validation_message(exc, "Проверьте данные для регистрации."),
            register_values=register_values,
        )
        response.status_code = 400
        return response

    if payload.password != payload.password_repeat:
        response = render_auth_page(error="Пароли не совпадают.", register_values=register_values)
        response.status_code = 400
        return response

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
            error="Аккаунт с таким адресом электронной почты уже существует.",
            register_values=register_values,
        )
        response.status_code = 409
        return response

    user = await request.app.state.users_collection.find_one({"_id": result.inserted_id})
    if user is None:
        raise HTTPException(status_code=500, detail="Не удалось создать пользователя.")

    token = await create_session(request, user)
    response = RedirectResponse(url="/my-registrations", status_code=303)
    set_session_cookie(response, request, token)
    return response


@app.post("/login", include_in_schema=False)
async def login(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
):
    login_values = {"email": email}
    try:
        payload = AccountLoginPayload(email=normalize_email(email), password=password)
    except ValidationError:
        response = render_auth_page(error="Введите корректные email и пароль.", login_values=login_values)
        response.status_code = 400
        return response

    normalized_email = normalize_email(str(payload.email))
    user = await request.app.state.users_collection.find_one({"email": normalized_email})
    if user is None or not verify_password(payload.password, user):
        response = render_auth_page(error="Неверный email или пароль.", login_values=login_values)
        response.status_code = 401
        return response

    desired_admin = is_admin_email(request.app.state.settings, normalized_email)
    if bool(user.get("is_admin")) != desired_admin:
        await request.app.state.users_collection.update_one(
            {"_id": user["_id"]},
            {"$set": {"is_admin": desired_admin}},
        )
        user["is_admin"] = desired_admin

    token = await create_session(request, user)
    response = RedirectResponse(url="/my-registrations", status_code=303)
    set_session_cookie(response, request, token)
    return response


@app.get("/logout", include_in_schema=False)
async def logout(request: Request):
    await remove_current_session(request)
    response = RedirectResponse(url="/?notice=logged_out", status_code=303)
    clear_session_cookie(response, request)
    return response


@app.get("/conference/register")
async def conference_registration_page(request: Request):
    current_user, response = await require_user(request)
    if response:
        return response
    return render_conference_form(current_user)


@app.post("/conference/register")
async def submit_conference_registration(
    request: Request,
    last_name: str = Form(...),
    first_name: str = Form(...),
    middle_name: str = Form(""),
    place_of_study: str = Form(...),
    department: str = Form(...),
    place_of_work: str = Form(""),
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
    current_user, response = await require_user(request)
    if response:
        return response

    middle_name_value = optional_form_value(middle_name)
    place_of_work_value = optional_form_value(place_of_work)
    job_title_value = optional_form_value(job_title)
    form_values = {
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

    try:
        payload = ConferenceRegistrationPayload(
            last_name=last_name,
            first_name=first_name,
            middle_name=middle_name_value,
            place_of_study=place_of_study,
            department=department,
            place_of_work=place_of_work_value,
            job_title=job_title_value,
            phone=phone,
            email=normalize_email(email),
            participation=participation,
            section=section,
            publication_title=publication_title,
            foreign_language_consultant=foreign_language_consultant,
        )
        publication_file_content = await read_docx(publication_file, field_label="Файл публикации")
        expert_opinion_content = await read_docx(
            expert_opinion_file,
            required=False,
            field_label="Экспертное заключение",
        )
    except ValidationError as exc:
        result = render_conference_form(
            current_user,
            error=validation_message(exc, "Проверьте заполнение формы."),
            values=form_values,
        )
        result.status_code = 400
        return result
    except HTTPException as exc:
        result = render_conference_form(current_user, error=str(exc.detail), values=form_values)
        result.status_code = exc.status_code
        return result

    if publication_file_content is None:
        raise HTTPException(status_code=500, detail="Не удалось прочитать файл публикации.")

    await request.app.state.registrations_collection.insert_one(
        {
            "owner_user_id": current_user["_id"],
            "owner_email": current_user["email"],
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
            "review_status": REVIEW_STATUSES[0],
            "admin_comment": "",
            "created_at": now_utc(),
        }
    )

    result = render_conference_form(
        current_user,
        success="Заявка сохранена.",
        values={"email": current_user["email"]},
    )
    result.status_code = 201
    return result


@app.get("/my-registrations")
async def my_registrations(request: Request):
    current_user, response = await require_user(request)
    if response:
        return response

    records = await request.app.state.registrations_collection.find(
        {"owner_user_id": current_user["_id"]},
        {"publication_file.data": 0, "expert_opinion_file.data": 0},
    ).sort("created_at", -1).to_list(length=200)

    return render_records_page(
        "Мои заявки",
        current_user,
        records,
        admin_mode=False,
        success=notice_message(request.query_params.get("notice")),
        empty_action_html=' <a href="/conference/register">Перейти к форме регистрации</a>',
        empty_text="Вы ещё не оставляли заявок на конференцию.",
    )


@app.get("/englishconfernceregistartions2026")
async def admin_registrations(request: Request):
    current_user, response = await require_admin(request, render_forbidden)
    if response:
        return response

    records = await request.app.state.registrations_collection.find(
        {},
        {"publication_file.data": 0, "expert_opinion_file.data": 0},
    ).sort("created_at", -1).to_list(length=500)
    return render_records_page(
        "Все заявки пользователей",
        current_user,
        records,
        admin_mode=True,
        success=notice_message(request.query_params.get("notice")),
        empty_text="В системе пока нет заявок.",
        selected_registration_id=request.query_params.get("selected"),
    )


@app.get("/englishconfernceregistartions2026/file/{registration_id}/{file_kind}", include_in_schema=False)
async def download_admin_file(
    registration_id: str,
    file_kind: str,
    request: Request,
):
    current_user, response = await require_admin(request, render_forbidden)
    if response:
        return response

    file_map = {
        "publication": ("publication_file", "Файл публикации", "publication.docx"),
        "expert-opinion": ("expert_opinion_file", "Экспертное заключение", "expert-opinion.docx"),
    }
    selected_file = file_map.get(file_kind)
    if selected_file is None:
        result = layout(
            "Ошибка",
            '<div class="empty">Запрошенный тип файла не поддерживается.</div>',
            current_user=current_user,
            error="Некорректный тип файла.",
        )
        result.status_code = 404
        return result
    file_field, file_label, default_filename = selected_file

    object_id = parse_object_id(registration_id)
    if object_id is None:
        result = layout(
            "РћС€РёР±РєР°",
            '<div class="empty">Р—Р°СЏРІРєР° РЅРµ РЅР°Р№РґРµРЅР°.</div>',
            current_user=current_user,
            error="РќРµРєРѕСЂСЂРµРєС‚РЅС‹Р№ РёРґРµРЅС‚РёС„РёРєР°С‚РѕСЂ Р·Р°СЏРІРєРё.",
        )
        result.status_code = 404
        return result

    record = await request.app.state.registrations_collection.find_one(
        {"_id": object_id},
        {file_field: 1},
    )
    if not record:
        result = layout(
            "РћС€РёР±РєР°",
            '<div class="empty">Р—Р°СЏРІРєР° РЅРµ РЅР°Р№РґРµРЅР°.</div>',
            current_user=current_user,
            error="Р—Р°СЏРІРєР° РЅРµ РЅР°Р№РґРµРЅР°.",
        )
        result.status_code = 404
        return result

    file_info = record.get(file_field) or {}
    file_data = file_info.get("data")
    file_name = str(file_info.get("filename") or default_filename)
    content_type = str(file_info.get("content_type") or "application/octet-stream")
    if not file_data:
        result = layout(
            "Ошибка",
            f'<div class="empty">{file_label} для этой заявки не найден.</div>',
            current_user=current_user,
            error=f"{file_label} не найден.",
        )
        result.status_code = 404
        return result
    if False and not file_data:
        result = layout(
            "РћС€РёР±РєР°",
            '<div class="empty">Р¤Р°Р№Р» РґР»СЏ СЌС‚РѕР№ Р·Р°СЏРІРєРё РЅРµ РЅР°Р№РґРµРЅ.</div>',
            current_user=current_user,
            error="Р¤Р°Р№Р» РЅРµ РЅР°Р№РґРµРЅ.",
        )
        result.status_code = 404
        return result

    headers = {
        "Content-Disposition": f"attachment; filename*=UTF-8''{quote(file_name)}",
    }
    return Response(content=bytes(file_data), media_type=content_type, headers=headers)


@app.post("/englishconfernceregistartions2026/comment/{registration_id}", include_in_schema=False)
async def save_admin_comment(
    registration_id: str,
    request: Request,
    review_status: str = Form(""),
    admin_comment: str = Form(""),
):
    current_user, response = await require_admin(request, render_forbidden)
    if response:
        return response

    if review_status not in REVIEW_STATUSES:
        result = layout(
            "Ошибка",
            '<div class="empty">Указан недопустимый статус заявки.</div>',
            current_user=current_user,
            error="Недопустимый статус заявки.",
        )
        result.status_code = 400
        return result

    object_id = parse_object_id(registration_id)
    if object_id is None:
        result = layout(
            "Ошибка",
            '<div class="empty">Заявка не найдена.</div>',
            current_user=current_user,
            error="Некорректный идентификатор заявки.",
        )
        result.status_code = 404
        return result

    record = await request.app.state.registrations_collection.find_one(
        {"_id": object_id},
        {"publication_file.data": 0, "expert_opinion_file.data": 0},
    )
    if not record:
        result = layout(
            "Ошибка",
            '<div class="empty">Заявка не найдена.</div>',
            current_user=current_user,
            error="Заявка не найдена.",
        )
        result.status_code = 404
        return result

    trimmed_comment = admin_comment.strip()
    update_result = await request.app.state.registrations_collection.update_one(
        {"_id": object_id},
        {"$set": {"admin_comment": trimmed_comment, "review_status": review_status}},
    )
    if update_result.matched_count == 0:
        result = layout(
            "Ошибка",
            '<div class="empty">Заявка не найдена.</div>',
            current_user=current_user,
            error="Заявка не найдена.",
        )
        result.status_code = 404
        return result

    updated_record = dict(record)
    updated_record["admin_comment"] = trimmed_comment
    updated_record["review_status"] = review_status
    try:
        await send_registration_update_email(request.app.state.settings, updated_record)
    except RuntimeError as exc:
        result = layout(
            "Уведомление не отправлено",
            (
                '<div class="empty">Изменения в заявке сохранены, но письмо отправить не удалось. '
                f'<a href="/englishconfernceregistartions2026?selected={registration_id}">'
                "Вернуться к списку заявок</a></div>"
            ),
            current_user=current_user,
            error=str(exc),
        )
        result.status_code = 502
        return result

    return RedirectResponse(
        url=f"/englishconfernceregistartions2026?notice=comment_saved&selected={registration_id}",
        status_code=303,
    )


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
