from __future__ import annotations

from urllib.parse import quote

from bson.binary import Binary
from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import RedirectResponse, Response
from pydantic import ValidationError
from pymongo.errors import DuplicateKeyError

from models import AccountLoginPayload, AccountRegistrationPayload, ConferenceRegistrationPayload
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
    set_session_cookie,
    validation_message,
)
from state import lifespan

app = FastAPI(title="Conference Personal Cabinet", lifespan=lifespan)


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
    place_of_study: str = Form(...),
    department: str = Form(...),
    phone: str = Form(...),
    email: str = Form(...),
    participation: str = Form(...),
    section: str = Form(...),
    publication_title: str = Form(...),
    language_consultant: str = Form(...),
    publication_file: UploadFile = File(...),
):
    current_user, response = await require_user(request)
    if response:
        return response

    form_values = {
        "last_name": last_name,
        "first_name": first_name,
        "place_of_study": place_of_study,
        "department": department,
        "phone": phone,
        "email": email,
        "participation": participation,
        "section": section,
        "publication_title": publication_title,
        "language_consultant": language_consultant,
    }

    try:
        payload = ConferenceRegistrationPayload(
            last_name=last_name,
            first_name=first_name,
            place_of_study=place_of_study,
            department=department,
            phone=phone,
            email=normalize_email(email),
            participation=participation,
            section=section,
            publication_title=publication_title,
            language_consultant=language_consultant,
        )
        file_content = await read_docx(publication_file)
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

    await request.app.state.registrations_collection.insert_one(
        {
            "owner_user_id": current_user["_id"],
            "owner_email": current_user["email"],
            "last_name": payload.last_name,
            "first_name": payload.first_name,
            "place_of_study": payload.place_of_study,
            "department": payload.department,
            "phone": payload.phone,
            "email": normalize_email(str(payload.email)),
            "participation": payload.participation,
            "section": payload.section,
            "publication_title": payload.publication_title,
            "language_consultant": payload.language_consultant,
            "file": {
                "filename": publication_file.filename,
                "content_type": publication_file.content_type or "application/octet-stream",
                "size_bytes": len(file_content),
                "data": Binary(file_content),
            },
            "admin_comment": "",
            "created_at": now_utc(),
        }
    )

    result = render_conference_form(
        current_user,
        success="Заявка сохранена в MongoDB.",
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
        {"file.data": 0},
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
        {"file.data": 0},
    ).sort("created_at", -1).to_list(length=500)
    return render_records_page(
        "Все заявки пользователей",
        current_user,
        records,
        admin_mode=True,
        success=notice_message(request.query_params.get("notice")),
        empty_text="В системе пока нет заявок.",
    )


@app.get("/englishconfernceregistartions2026/file/{registration_id}", include_in_schema=False)
async def download_admin_file(
    registration_id: str,
    request: Request,
):
    current_user, response = await require_admin(request, render_forbidden)
    if response:
        return response

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
        {"file": 1},
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

    file_info = record.get("file") or {}
    file_data = file_info.get("data")
    file_name = str(file_info.get("filename") or "publication.docx")
    content_type = str(file_info.get("content_type") or "application/octet-stream")
    if not file_data:
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
    admin_comment: str = Form(""),
):
    current_user, response = await require_admin(request, render_forbidden)
    if response:
        return response

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

    update_result = await request.app.state.registrations_collection.update_one(
        {"_id": object_id},
        {"$set": {"admin_comment": admin_comment.strip()}},
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

    return RedirectResponse(url="/englishconfernceregistartions2026?notice=comment_saved", status_code=303)


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
