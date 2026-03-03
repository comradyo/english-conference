from datetime import datetime, timezone
from html import escape
from typing import Any

from fastapi.responses import HTMLResponse

from models import PARTICIPATION_OPTIONS, SECTION_OPTIONS


def notice_message(key: str | None) -> str | None:
    mapping = {
        "login_required": "Сначала войдите в личный кабинет.",
        "logged_out": "Сеанс завершён.",
        "comment_saved": "Комментарий администратора сохранён.",
    }
    return mapping.get(key)


def layout(
    title: str,
    body: str,
    *,
    current_user: dict[str, Any] | None = None,
    success: str | None = None,
    error: str | None = None,
) -> HTMLResponse:
    return HTMLResponse(
        content=f"""<!DOCTYPE html>
<html lang="ru"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{escape(title)}</title>
<style>
:root {{ --bg:#f5efe7; --panel:#fffdf9; --line:#d7d2c8; --accent:#0f5959; --soft:#d9efef; --text:#1f2529; --muted:#60696f; --danger-bg:#f8dddd; --danger-text:#7f2020; --ok-bg:#dff3e3; --ok-text:#155728; font-family:"Segoe UI",Tahoma,Geneva,Verdana,sans-serif; }}
* {{ box-sizing:border-box; }} body {{ margin:0; min-height:100vh; color:var(--text); background:radial-gradient(circle at top right, rgba(15,89,89,.12), transparent 28%), radial-gradient(circle at bottom left, rgba(180,83,9,.1), transparent 20%), var(--bg); }}
.page {{ width:min(1100px, calc(100% - 32px)); margin:28px auto; }} .shell {{ background:var(--panel); border:1px solid rgba(15,89,89,.1); border-radius:24px; padding:24px; box-shadow:0 18px 50px rgba(15,89,89,.08); }}
.topbar, nav, .card-title {{ display:flex; gap:12px; justify-content:space-between; align-items:flex-start; flex-wrap:wrap; }} .topbar {{ margin-bottom:18px; }} nav {{ margin:18px 0 20px; }}
h1 {{ margin:0; font-size:clamp(2rem, 4vw, 2.7rem); line-height:1.05; }} h2 {{ margin:0 0 14px; font-size:1.2rem; }} p {{ margin:0 0 14px; color:var(--muted); }}
.subtitle {{ margin-top:8px; max-width:760px; }} .user-badge, nav a {{ padding:10px 14px; border-radius:999px; font-weight:600; text-decoration:none; }}
.user-badge {{ background:#f1f6f6; border:1px solid var(--line); color:var(--accent); }} nav a {{ background:var(--soft); color:var(--accent); }}
.banner {{ padding:14px 16px; border-radius:16px; margin-bottom:18px; font-weight:600; }} .banner.success {{ background:var(--ok-bg); color:var(--ok-text); }} .banner.error {{ background:var(--danger-bg); color:var(--danger-text); }}
.split, .grid {{ display:grid; grid-template-columns:repeat(2, minmax(0, 1fr)); gap:14px; }} .split {{ gap:18px; }}
.panel, .card, .empty {{ border:1px solid var(--line); border-radius:18px; padding:18px; background:#fffdfa; }} .empty {{ border-style:dashed; color:var(--muted); }}
form, .cards, .meta, label, .meta-row {{ display:grid; gap:14px; }} .cards {{ gap:16px; }} .meta {{ gap:10px; }} label, .meta-row {{ gap:6px; font-weight:600; }}
.meta-row span {{ color:var(--muted); font-size:.9rem; font-weight:400; }}
input, select, textarea, button {{ width:100%; font:inherit; color:inherit; border-radius:14px; border:1px solid var(--line); background:#fff; padding:12px 14px; }}
textarea {{ min-height:110px; resize:vertical; }} button {{ border:none; cursor:pointer; background:linear-gradient(135deg, #0f5959, #207070); color:#fff; font-weight:700; min-height:46px; }} .action-link {{ display:inline-flex; align-items:center; justify-content:center; width:100%; min-height:46px; padding:12px 14px; border-radius:14px; background:var(--soft); color:var(--accent); font-weight:700; text-decoration:none; }}
@media (max-width:820px) {{ .split, .grid {{ grid-template-columns:1fr; }} .shell {{ padding:18px; border-radius:18px; }} }}
</style></head><body><main class="page"><section class="shell"><div class="topbar"><div><h1>{escape(title)}</h1><p class="subtitle">Отдельный микросервис для личного кабинета участников конференции, регистрации заявок и административного просмотра.</p></div>{user_badge(current_user)}</div><nav>{nav_html(current_user)}</nav>{banner(success, 'success')}{banner(error, 'error')}{body}</section></main></body></html>"""
    )


def banner(message: str | None, kind: str) -> str:
    if not message:
        return ""
    return f'<div class="banner {kind}">{escape(message)}</div>'


def nav_html(current_user: dict[str, Any] | None) -> str:
    links = []
    if current_user:
        links.append('<a href="/conference/register">Регистрация на конференцию</a>')
        links.append('<a href="/my-registrations">Мои заявки</a>')
        if current_user.get("is_admin"):
            links.append('<a href="/englishconfernceregistartions2026">Все заявки</a>')
        links.append('<a href="/logout">Выйти</a>')
    else:
        links.append('<a href="/">Вход и регистрация</a>')
    return "".join(links)


def user_badge(current_user: dict[str, Any] | None) -> str:
    if not current_user:
        return '<div class="user-badge">Гость</div>'
    role = "Администратор" if current_user.get("is_admin") else "Пользователь"
    return f'<div class="user-badge">{escape(current_user["email"])} | {escape(role)}</div>'


def field_value(values: dict[str, str], key: str, default: str = "") -> str:
    return escape(values.get(key, default), quote=True)


def render_select(name: str, options: tuple[str, ...], selected: str | None) -> str:
    rendered = []
    for option in options:
        selected_attr = " selected" if selected == option else ""
        rendered.append(f'<option value="{escape(option, quote=True)}"{selected_attr}>{escape(option)}</option>')
    return f'<select name="{escape(name, quote=True)}">{"".join(rendered)}</select>'


def meta_row(label: str, value: str) -> str:
    return f'<div class="meta-row"><span>{escape(label)}</span><strong>{escape(value)}</strong></div>'


def format_dt(value: Any) -> str:
    if isinstance(value, datetime):
        return value.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    return "Не указано"


def render_auth_page(*, error: str | None = None, success: str | None = None, register_values: dict[str, str] | None = None, login_values: dict[str, str] | None = None) -> HTMLResponse:
    register_values = register_values or {}
    login_values = login_values or {}
    show_register = bool(register_values) and not bool(login_values)
    login_hidden_attr = " hidden" if show_register else ""
    register_hidden_attr = "" if show_register else " hidden"
    body = f"""
    <section class="cards">
      <section class="panel" id="login-panel"{login_hidden_attr}><h2>Вход в личный кабинет</h2><p>Введите email и пароль, чтобы открыть форму регистрации на конференцию и список своих заявок.</p>
        <form method="post" action="/login">
          <label>Адрес электронной почты<input type="email" name="email" required value="{field_value(login_values, 'email')}"></label>
          <label>Пароль<input type="password" name="password" required></label>
          <button type="submit">Войти</button>
        </form>
        <br>
        <button type="button" id="show-register-button">Создать аккаунт</button>
      </section>
      <section class="panel" id="register-panel"{register_hidden_attr}><h2>Регистрация</h2><p>Создайте личный кабинет. Повторно зарегистрировать тот же email нельзя.</p>
        <form method="post" action="/register-account">
          <label>Адрес электронной почты<input id="register-email" type="email" name="email" required value="{field_value(register_values, 'email')}"></label>
          <label>Пароль<input type="password" name="password" required minlength="8"></label>
          <label>Повторите пароль<input type="password" name="password_repeat" required minlength="8"></label>
          <button type="submit">Зарегистрироваться</button>
        </form>
        <button type="button" id="show-login-button">Назад ко входу</button>
      </section>
    </section>
    <script>
      (function () {{
        const loginPanel = document.getElementById("login-panel");
        const registerPanel = document.getElementById("register-panel");
        const showRegisterButton = document.getElementById("show-register-button");
        const showLoginButton = document.getElementById("show-login-button");
        const registerEmail = document.getElementById("register-email");

        if (!loginPanel || !registerPanel || !showRegisterButton || !showLoginButton) {{
          return;
        }}

        function showRegisterPanel() {{
          loginPanel.hidden = true;
          registerPanel.hidden = false;
          if (registerEmail) {{
            registerEmail.focus();
          }}
        }}

        function showLoginPanel() {{
          registerPanel.hidden = true;
          loginPanel.hidden = false;
        }}

        showRegisterButton.addEventListener("click", showRegisterPanel);
        showLoginButton.addEventListener("click", showLoginPanel);
      }})();
    </script>
    """
    return layout("Личный кабинет конференции", body, success=success, error=error)
    body = f"""
    <section class="split">
      <section class="panel"><h2>Регистрация</h2><p>Создайте личный кабинет. Повторно зарегистрировать тот же email нельзя.</p>
        <form method="post" action="/register-account">
          <label>Адрес электронной почты<input type="email" name="email" required value="{field_value(register_values, 'email')}"></label>
          <label>Пароль<input type="password" name="password" required minlength="8"></label>
          <label>Повторите пароль<input type="password" name="password_repeat" required minlength="8"></label>
          <button type="submit">Создать аккаунт</button>
        </form>
      </section>
      <section class="panel"><h2>Вход в личный кабинет</h2><p>Введите email и пароль, чтобы открыть форму регистрации и список своих заявок.</p>
        <form method="post" action="/login">
          <label>Адрес электронной почты<input type="email" name="email" required value="{field_value(login_values, 'email')}"></label>
          <label>Пароль<input type="password" name="password" required></label>
          <button type="submit">Войти</button>
        </form>
      </section>
    </section>
    """
    return layout("Личный кабинет конференции", body, success=success, error=error)


def render_conference_form(current_user: dict[str, Any], *, error: str | None = None, success: str | None = None, values: dict[str, str] | None = None) -> HTMLResponse:
    values = dict(values or {})
    values.setdefault("email", current_user["email"])
    values.setdefault("participation", PARTICIPATION_OPTIONS[0])
    values.setdefault("section", SECTION_OPTIONS[0])
    body = f"""
    <section class="panel"><h2>Регистрация на конференцию</h2><p>Эта форма доступна только авторизованному пользователю. После сохранения заявка появится в разделе "Мои заявки".</p>
      <form method="post" action="/conference/register" enctype="multipart/form-data">
        <div class="grid">
          <label>Фамилия<input type="text" name="last_name" required value="{field_value(values, 'last_name')}"></label>
          <label>Имя<input type="text" name="first_name" required value="{field_value(values, 'first_name')}"></label>
          <label>Место учебы<input type="text" name="place_of_study" required value="{field_value(values, 'place_of_study')}"></label>
          <label>Кафедра<input type="text" name="department" required value="{field_value(values, 'department')}"></label>
          <label>Телефон для связи<input type="tel" name="phone" required value="{field_value(values, 'phone')}"></label>
          <label>Электронная почта<input type="email" name="email" required value="{field_value(values, 'email')}"></label>
          <label>Участие{render_select('participation', PARTICIPATION_OPTIONS, values.get('participation'))}</label>
          <label>Секция{render_select('section', SECTION_OPTIONS, values.get('section'))}</label>
          <label>Название публикации<input type="text" name="publication_title" required value="{field_value(values, 'publication_title')}"></label>
          <label>Консультант по языку<input type="text" name="language_consultant" required value="{field_value(values, 'language_consultant')}"></label>
          <label>Файл публикации<input type="file" name="publication_file" accept=".docx" required></label>
        </div>
        <button type="submit">Сохранить заявку</button>
      </form>
    </section>
    """
    return layout("Регистрация на конференцию", body, current_user=current_user, success=success, error=error)


def render_record_card(record: dict[str, Any], *, admin_mode: bool) -> str:
    file_info = record.get("file", {})
    file_name = str(file_info.get("filename", ""))
    rows = [
        meta_row("Фамилия", str(record.get("last_name", ""))),
        meta_row("Имя", str(record.get("first_name", ""))),
        meta_row("Место учебы", str(record.get("place_of_study", ""))),
        meta_row("Кафедра", str(record.get("department", ""))),
        meta_row("Телефон для связи", str(record.get("phone", ""))),
        meta_row("Электронная почта", str(record.get("email", ""))),
        meta_row("Участие", str(record.get("participation", ""))),
        meta_row("Секция", str(record.get("section", ""))),
        meta_row("Название публикации", str(record.get("publication_title", ""))),
        meta_row("Консультант по языку", str(record.get("language_consultant", ""))),
        meta_row("Файл публикации", str(file_info.get("filename", "Нет файла"))),
        meta_row("Размер файла", f"{int(file_info.get('size_bytes', 0))} байт"),
        meta_row("Создано", format_dt(record.get("created_at"))),
    ]
    rows[10] = meta_row(
        "\u0424\u0430\u0439\u043b \u043f\u0443\u0431\u043b\u0438\u043a\u0430\u0446\u0438\u0438",
        file_name or "\u041d\u0435\u0442 \u0444\u0430\u0439\u043b\u0430",
    )
    if admin_mode:
        rows.append(meta_row("Владелец аккаунта", str(record.get("owner_email", ""))))
        comment_value = str(record.get("admin_comment") or "")
        download_link = ""
        if file_name:
            download_link = (
                f'<a class="action-link" href="/englishconfernceregistartions2026/file/{record["_id"]}">'
                "\u0421\u043a\u0430\u0447\u0430\u0442\u044c \u0444\u0430\u0439\u043b"
                "</a>"
            )
        comment_block = f'<form method="post" action="/englishconfernceregistartions2026/comment/{record["_id"]}"><label>Комментарий администратора<textarea name="admin_comment">{escape(comment_value)}</textarea></label><button type="submit">Сохранить комментарий</button></form>'
        comment_block = f"{download_link}{comment_block}"
    else:
        comment_text = str(record.get("admin_comment") or "").strip() or "Комментарий пока не добавлен."
        comment_block = meta_row("Комментарий администратора", comment_text)
    return f'<article class="card"><div class="card-title"><strong>{escape(str(record.get("last_name", "")))} {escape(str(record.get("first_name", "")))}</strong><span>{escape(str(record.get("_id", "")))}</span></div><div class="meta">{"".join(rows)}{comment_block}</div></article>'


def render_records_page(title: str, current_user: dict[str, Any], records: list[dict[str, Any]], *, admin_mode: bool, success: str | None = None, empty_text: str) -> HTMLResponse:
    if records:
        body = f'<section class="cards">{"".join(render_record_card(record, admin_mode=admin_mode) for record in records)}</section>'
    else:
        body = f'<div class="empty">{escape(empty_text)}</div>'
    return layout(title, body, current_user=current_user, success=success)


def render_forbidden(current_user: dict[str, Any]) -> HTMLResponse:
    response = layout(
        "Доступ запрещён",
        '<div class="empty">Для просмотра этой страницы нужны права администратора.</div>',
        current_user=current_user,
        error="Недостаточно прав доступа.",
    )
    response.status_code = 403
    return response
