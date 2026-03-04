from datetime import datetime, timedelta, timezone
from html import escape
from typing import Any

from fastapi.responses import HTMLResponse

from models import PARTICIPATION_OPTIONS, REVIEW_STATUSES, SECTION_OPTIONS


MOSCOW_TZ = timezone(timedelta(hours=3), name="UTC+3")

FIELD_LABELS = {
    "_id": "ID заявки",
    "owner_user_id": "ID пользователя",
    "owner_email": "Email аккаунта",
    "last_name": "Фамилия",
    "first_name": "Имя",
    "middle_name": "Отчество",
    "place_of_study": "Место учёбы",
    "department": "Кафедра",
    "place_of_work": "Место работы",
    "job_title": "Должность",
    "phone": "Телефон",
    "email": "Контактный email",
    "participation": "Участие",
    "section": "Секция",
    "publication_title": "Название публикации",
    "foreign_language_consultant": "ФИО Консультанта по иностранному языку",
    "publication_file": "Файл публикации",
    "publication_file.filename": "Файл публикации: имя",
    "publication_file.content_type": "Файл публикации: тип",
    "publication_file.size_bytes": "Файл публикации: размер",
    "expert_opinion_file": "Экспертное заключение",
    "expert_opinion_file.filename": "Экспертное заключение: имя",
    "expert_opinion_file.content_type": "Экспертное заключение: тип",
    "expert_opinion_file.size_bytes": "Экспертное заключение: размер",
    "review_status": "Статус",
    "admin_comment": "Комментарий к заявке",
    "created_at": "Создано",
}


def notice_message(key: str | None) -> str | None:
    mapping = {
        "login_required": "Сначала войдите в личный кабинет.",
        "logged_out": "Сеанс завершён.",
        "comment_saved": "Комментарий и статус заявки сохранены.",
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
.page {{ width:min(1600px, calc(100% - 32px)); margin:28px auto; }} .shell {{ background:var(--panel); border:1px solid rgba(15,89,89,.1); border-radius:24px; padding:24px; box-shadow:0 18px 50px rgba(15,89,89,.08); }}
.topbar, nav, .card-title {{ display:flex; gap:12px; justify-content:space-between; align-items:flex-start; flex-wrap:wrap; }} .topbar {{ margin-bottom:18px; }} nav {{ margin:18px 0 20px; }}
h1 {{ margin:0; font-size:clamp(2rem, 4vw, 2.7rem); line-height:1.05; }} h2 {{ margin:0 0 14px; font-size:1.2rem; }} p {{ margin:0 0 14px; color:var(--muted); }}
.subtitle {{ margin-top:8px; max-width:760px; }} .user-badge, nav a {{ padding:10px 14px; border-radius:999px; font-weight:600; text-decoration:none; }}
.user-badge {{ background:#f1f6f6; border:1px solid var(--line); color:var(--accent); }} nav a {{ background:var(--soft); color:var(--accent); }}
.banner {{ padding:14px 16px; border-radius:16px; margin-bottom:18px; font-weight:600; }} .banner.success {{ background:var(--ok-bg); color:var(--ok-text); }} .banner.error {{ background:var(--danger-bg); color:var(--danger-text); }}
.split, .grid {{ display:grid; grid-template-columns:repeat(2, minmax(0, 1fr)); gap:14px; }}
.split {{ gap:18px; }}
.panel, .card, .empty {{ border:1px solid var(--line); border-radius:18px; padding:18px; background:#fffdfa; }}
.empty {{ border-style:dashed; color:var(--muted); }}
form, .cards, .meta, label, .meta-row, .record-highlights {{ display:grid; gap:14px; }}
.cards {{ gap:16px; }}
.meta {{ gap:10px; }}
label, .meta-row {{ gap:6px; font-weight:600; }}
.meta-row span {{ color:var(--muted); font-size:.9rem; font-weight:400; }}
input, select, textarea, button {{ width:100%; font:inherit; color:inherit; border-radius:14px; border:1px solid var(--line); background:#fff; padding:12px 14px; }}
textarea {{ min-height:110px; resize:vertical; }}
button {{ border:none; cursor:pointer; background:linear-gradient(135deg, #0f5959, #207070); color:#fff; font-weight:700; min-height:46px; }}
.action-link {{ display:inline-flex; align-items:center; justify-content:center; width:100%; min-height:46px; padding:12px 14px; border-radius:14px; background:var(--soft); color:var(--accent); font-weight:700; text-decoration:none; }}
.record-highlights {{ margin-bottom:16px; }}
.record-highlight {{ border:1px solid var(--line); border-radius:16px; padding:16px; background:#fff; }}
.record-highlight span {{ display:block; margin-bottom:8px; color:var(--muted); font-size:.95rem; font-weight:600; }}
.record-highlight-body {{ font-size:1.08rem; font-weight:700; line-height:1.45; }}
.record-highlight-comment .record-highlight-body {{ font-size:1.02rem; font-weight:600; }}
.section-group {{ border:1px solid var(--line); border-radius:18px; background:#fffdfa; overflow:hidden; }}
.section-group + .section-group {{ margin-top:16px; }}
.section-summary {{ cursor:pointer; padding:16px 18px; font-weight:700; }}
.table-wrap {{ overflow-x:auto; padding:0 18px 18px; }}
.records-table {{ width:100%; border-collapse:collapse; min-width:1100px; }}
.records-table th, .records-table td {{ padding:12px 10px; vertical-align:top; border-top:1px solid var(--line); text-align:left; }}
.records-table th {{ color:var(--muted); font-size:.9rem; font-weight:700; }}
.records-table tbody tr:hover {{ background:rgba(15,89,89,.03); }}
.status-pill {{ display:inline-block; padding:6px 10px; border-radius:999px; background:#ece7cf; color:#6d5200; font-weight:700; }}
.status-pill.status-pending {{ background:#ece7cf; color:#6d5200; }}
.status-pill.status-accepted {{ background:#dff3e3; color:#155728; }}
.status-pill.status-rejected {{ background:#f8dddd; color:#7f2020; }}
.status-pill.status-pill-large {{ padding:10px 14px; font-size:1.02rem; }}
.admin-tools {{ display:grid; gap:10px; min-width:260px; }}
.admin-tools form {{ gap:10px; }}
.admin-tools textarea {{ min-height:84px; }}
.section-meta {{ color:var(--muted); font-weight:600; }}
@media (max-width:820px) {{ .split, .grid {{ grid-template-columns:1fr; }} .shell {{ padding:18px; border-radius:18px; }} }}
</style></head><body><main class="page"><section class="shell"><div class="topbar"><div><h1>{escape(title)}</h1></div>{user_badge(current_user)}</div><nav>{nav_html(current_user)}</nav>{banner(success, 'success')}{banner(error, 'error')}{body}</section></main></body></html>"""
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


def meta_html_row(label: str, value_html: str) -> str:
    return f'<div class="meta-row"><span>{escape(label)}</span><strong>{value_html}</strong></div>'


def format_dt(value: Any) -> str:
    if isinstance(value, datetime):
        return value.astimezone(MOSCOW_TZ).strftime("%d.%m.%Y %H:%M (МСК)")
    return "Не указано"


def optional_value(value: Any, *, empty: str = "Не указано") -> str:
    text = str(value or "").strip()
    return text or empty


def file_name(file_info: dict[str, Any] | None, *, empty: str = "Не загружен") -> str:
    if not isinstance(file_info, dict):
        return empty
    return optional_value(file_info.get("filename"), empty=empty)


def status_tone_class(status: str) -> str:
    mapping = {
        "На рассмотрении": "status-pending",
        "Принята": "status-accepted",
        "Отклонена": "status-rejected",
    }
    return mapping.get(status, "status-pending")


def render_status_badge(status: str, *, large: bool = False) -> str:
    classes = ["status-pill", status_tone_class(status)]
    if large:
        classes.append("status-pill-large")
    return f'<span class="{" ".join(classes)}">{escape(status)}</span>'


def render_highlight_block(label: str, body_html: str, *, extra_class: str = "") -> str:
    class_name = "record-highlight"
    if extra_class:
        class_name = f"{class_name} {extra_class}"
    return (
        f'<section class="{class_name}">'
        f"<span>{escape(label)}</span>"
        f'<div class="record-highlight-body">{body_html}</div>'
        "</section>"
    )


def field_label(path: str) -> str:
    return FIELD_LABELS.get(path, path.replace("_", " "))


def render_object_fields(record: dict[str, Any]) -> str:
    rows: list[str] = []

    def append_field(path: str, value: Any) -> None:
        if isinstance(value, dict):
            summary = "Не указано" if not value else optional_value(value.get("filename"), empty="См. вложенные поля")
            rows.append(meta_row(field_label(path), summary))
            if not value:
                return
            for nested_key, nested_value in value.items():
                if nested_key == "data":
                    continue
                append_field(f"{path}.{nested_key}", nested_value)
            return
        if path == "review_status":
            status = str(value or REVIEW_STATUSES[0])
            rows.append(meta_html_row(field_label(path), render_status_badge(status)))
            return
        if path == "admin_comment":
            text = str(value or "").strip() or "Комментарий пока не добавлен."
            rows.append(meta_row(field_label(path), text))
            return
        if path == "created_at" and isinstance(value, datetime):
            rows.append(meta_row(field_label(path), format_dt(value)))
            return
        if value is None:
            empty_value = "Не загружено" if path == "expert_opinion_file" else "Не указано"
            rows.append(meta_row(field_label(path), empty_value))
            return
        text = str(value).strip()
        if not text:
            empty_value = "Не загружено" if path == "expert_opinion_file" else "Не указано"
            rows.append(meta_row(field_label(path), empty_value))
            return
        rows.append(meta_row(field_label(path), text))

    for key, value in record.items():
        append_field(key, value)
    return "".join(rows)


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
        <br>
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


def render_conference_form(current_user: dict[str, Any], *, error: str | None = None, success: str | None = None, values: dict[str, str] | None = None) -> HTMLResponse:
    values = dict(values or {})
    values.setdefault("email", current_user["email"])
    values.setdefault("participation", PARTICIPATION_OPTIONS[0])
    values.setdefault("section", SECTION_OPTIONS[0])
    body = f"""
    <section class="panel"><h2>Регистрация на конференцию</h2><p>После сохранения заявка появится в разделе "Мои заявки".</p>
      <form method="post" action="/conference/register" enctype="multipart/form-data">
        <div class="grid">
          <label>Фамилия<input type="text" name="last_name" required value="{field_value(values, 'last_name')}"></label>
          <label>Имя<input type="text" name="first_name" required value="{field_value(values, 'first_name')}"></label>
          <label>Отчество<input type="text" name="middle_name" value="{field_value(values, 'middle_name')}"></label>
          <label>Место учёбы<input type="text" name="place_of_study" required value="{field_value(values, 'place_of_study')}"></label>
          <label>Кафедра<input type="text" name="department" required value="{field_value(values, 'department')}"></label>
          <label>Место работы<input type="text" name="place_of_work" value="{field_value(values, 'place_of_work')}"></label>
          <label>Должность<input type="text" name="job_title" value="{field_value(values, 'job_title')}"></label>
          <label>Телефон для связи<input type="tel" name="phone" required value="{field_value(values, 'phone')}"></label>
          <label>Электронная почта<input type="email" name="email" required value="{field_value(values, 'email')}"></label>
          <label>Участие{render_select('participation', PARTICIPATION_OPTIONS, values.get('participation'))}</label>
          <label>Секция{render_select('section', SECTION_OPTIONS, values.get('section'))}</label>
          <label>Название публикации<input type="text" name="publication_title" required value="{field_value(values, 'publication_title')}"></label>
          <label>ФИО Консультанта по иностранному языку<input type="text" name="foreign_language_consultant" required value="{field_value(values, 'foreign_language_consultant')}"></label>
          <label>Файл публикации<input type="file" name="publication_file" accept=".docx" required></label>
          <label>Экспертное заключение<input type="file" name="expert_opinion_file" accept=".docx"></label>
        </div>
        <button type="submit">Сохранить заявку</button>
      </form>
    </section>
    """
    return layout("Регистрация на конференцию", body, current_user=current_user, success=success, error=error)


def render_record_card(record: dict[str, Any], *, admin_mode: bool) -> str:
    publication_file = record.get("publication_file") or {}
    expert_opinion_file = record.get("expert_opinion_file") or {}
    review_status = str(record.get("review_status") or REVIEW_STATUSES[0])
    comment_text = str(record.get("admin_comment") or "").strip() or "Комментарий пока не добавлен."
    full_name = " ".join(
        part
        for part in [
            str(record.get("last_name", "")).strip(),
            str(record.get("first_name", "")).strip(),
            str(record.get("middle_name", "")).strip(),
        ]
        if part
    )
    rows = [
        meta_row("Фамилия", str(record.get("last_name", ""))),
        meta_row("Имя", str(record.get("first_name", ""))),
        meta_row("Отчество", optional_value(record.get("middle_name"))),
        meta_row("Место учёбы", str(record.get("place_of_study", ""))),
        meta_row("Кафедра", str(record.get("department", ""))),
        meta_row("Место работы", optional_value(record.get("place_of_work"))),
        meta_row("Должность", optional_value(record.get("job_title"))),
        meta_row("Телефон для связи", str(record.get("phone", ""))),
        meta_row("Электронная почта", str(record.get("email", ""))),
        meta_row("Участие", str(record.get("participation", ""))),
        meta_row("Секция", str(record.get("section", ""))),
        meta_row("Название публикации", str(record.get("publication_title", ""))),
        meta_row("ФИО Консультанта по иностранному языку", str(record.get("foreign_language_consultant", ""))),
        meta_row("Файл публикации", file_name(publication_file)),
        meta_row(
            "Размер файла публикации",
            f"{int(publication_file.get('size_bytes', 0))} байт" if publication_file.get("filename") else "Не указано",
        ),
        meta_row("Экспертное заключение", file_name(expert_opinion_file)),
        meta_row(
            "Размер экспертного заключения",
            f"{int(expert_opinion_file.get('size_bytes', 0))} байт" if expert_opinion_file.get("filename") else "Не указано",
        ),
        meta_row("Создано", format_dt(record.get("created_at"))),
    ]
    if admin_mode:
        rows.insert(0, meta_html_row("Статус", render_status_badge(review_status)))
        rows.append(meta_row("Владелец аккаунта", str(record.get("owner_email", ""))))
        comment_block = meta_row("Комментарий к заявке", comment_text)
        highlights_html = ""
    else:
        comment_html = escape(comment_text).replace("\n", "<br>")
        highlights_html = (
            '<section class="record-highlights"><br>'
            f'{render_highlight_block("Статус", render_status_badge(review_status, large=True))}'
            f'{render_highlight_block("Комментарий к заявке", comment_html, extra_class="record-highlight-comment")}'
            "</section>"
        )
        comment_block = ""
    return f'<article class="card"><div class="card-title"><strong>{escape(full_name or "Заявка без имени")}</strong><span>{escape(str(record.get("_id", "")))}</span></div>{highlights_html}<div class="meta">{"".join(rows)}{comment_block}</div></article>'


def render_admin_table(
    records: list[dict[str, Any]],
    *,
    selected_registration_id: str | None = None,
) -> str:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for record in records:
        section = str(record.get("section") or "Без секции")
        grouped.setdefault(section, []).append(record)

    ordered_sections = list(SECTION_OPTIONS)
    ordered_sections.extend(sorted(key for key in grouped if key not in SECTION_OPTIONS))

    sections_html: list[str] = []
    side_panels: list[str] = []
    selected_registration_id = str(selected_registration_id or "").strip()
    for section in ordered_sections:
        section_records = grouped.get(section)
        if not section_records:
            continue

        rows_html: list[str] = []
        for record in section_records:
            record_id = str(record.get("_id", ""))
            last_name = str(record.get("last_name", "")).strip()
            first_name = str(record.get("first_name", "")).strip()
            middle_name = str(record.get("middle_name", "")).strip()
            full_name = " ".join(
                part
                for part in [
                    last_name,
                    first_name,
                    middle_name,
                ]
                if part
            ) or "Без имени"
            name_cell = "".join(
                f"<div>{escape(part)}</div>"
                for part in [last_name, first_name, middle_name]
                if part
            ) or "<div>Без имени</div>"
            publication_file = record.get("publication_file") or {}
            expert_opinion_file = record.get("expert_opinion_file") or {}
            publication_name = file_name(publication_file)
            expert_name = file_name(expert_opinion_file, empty="Не загружено")
            review_status = str(record.get("review_status") or REVIEW_STATUSES[0])
            is_selected = bool(selected_registration_id and selected_registration_id == record_id)
            status_options = "".join(
                f'<option value="{escape(status, quote=True)}"{" selected" if status == review_status else ""}>{escape(status)}</option>'
                for status in REVIEW_STATUSES
            )
            download_links: list[str] = []
            if publication_file.get("filename"):
                download_links.append(
                    f'<a class="action-link" href="/englishconfernceregistartions2026/file/{record_id}/publication">Скачать публикацию</a>'
                )
            if expert_opinion_file.get("filename"):
                download_links.append(
                    f'<a class="action-link" href="/englishconfernceregistartions2026/file/{record_id}/expert-opinion">Скачать экспертное заключение</a>'
                )
            downloads_html = "".join(download_links)
            contacts_cell = (
                f'<div class="file-stack"><div>{escape(str(record.get("email", "")))}</div>'
                f'<div>{escape(str(record.get("phone", "")))}</div></div>'
            )
            record_fields_html = render_object_fields(record)

            rows_html.append(
                f"""
                <tr class="admin-row{" is-active" if is_selected else ""}" data-admin-target="admin-actions-{record_id}" tabindex="0" role="button" aria-selected="{"true" if is_selected else "false"}">
                  <td><div class="file-stack">{name_cell}</div></td>
                  <td>{contacts_cell}</td>
                  <td>{escape(str(record.get("participation", "")))}</td>
                  <td>{escape(str(record.get("publication_title", "")))}</td>
                  <td>{render_status_badge(review_status)}</td>
                  <td>{escape(format_dt(record.get("created_at")))}</td>
                </tr>
                """
            )
            side_panels.append(
                f"""
                <section id="admin-actions-{record_id}" class="panel admin-side-card{" active" if is_selected else ""}" data-admin-card>
                  <h2>{escape(full_name)}</h2>
                  <p>Вы можете скачать файлы, изменить статус и оставить комментарий к заявке.</p>
                  <div class="meta">{record_fields_html}</div>
                  <div class="admin-tools">
                    {downloads_html}
                    <form method="post" action="/englishconfernceregistartions2026/comment/{record_id}">
                      <label>Статус<select name="review_status">{status_options}</select></label>
                      <label>Комментарий<textarea name="admin_comment">{escape(str(record.get("admin_comment") or ""))}</textarea></label>
                      <button type="submit">Сохранить</button>
                    </form>
                  </div>
                </section>
                """
            )

        sections_html.append(
            f"""
            <details class="section-group" open>
              <summary class="section-summary">{escape(section)} <span class="section-meta">({len(section_records)} заявок)</span></summary>
              <div class="table-wrap">
                <table class="records-table">
                  <thead>
                    <tr>
                      <th>Участник</th>
                      <th>Контакты</th>
                      <th>Участие</th>
                      <th>Публикация</th>
                      <th>Статус</th>
                      <th>Создано</th>
                    </tr>
                  </thead>
                  <tbody>
                    {''.join(rows_html)}
                  </tbody>
                </table>
              </div>
            </details>
            """
        )

    side_placeholder = (
        '<div class="panel admin-side-placeholder" data-admin-placeholder>'
        "<h2>Действия по заявке</h2>"
        "<p>Нажмите на строку в таблице, чтобы открыть инструменты для выбранной заявки.</p>"
        "</div>"
    )
    return f"""
    <style>
    .admin-layout {{ display:grid; grid-template-columns:minmax(0, 1fr) minmax(300px, 340px); gap:18px; align-items:start; }}
    .admin-table-pane {{ min-width:0; }}
    .admin-side-pane {{ position:sticky; top:24px; display:grid; gap:14px; }}
    .admin-row {{ cursor:pointer; }}
    .admin-row.is-active {{ background:rgba(15,89,89,.08); }}
    .admin-row:focus-visible {{ outline:2px solid rgba(15,89,89,.35); outline-offset:-2px; }}
    .admin-side-card {{ display:none; gap:14px; }}
    .admin-side-card.active {{ display:grid; }}
    .admin-side-placeholder[hidden] {{ display:none; }}
    .row-action-hint {{ color:var(--accent); font-weight:700; white-space:nowrap; }}
    .file-stack {{ display:grid; gap:6px; }}
    @media (max-width:980px) {{ .admin-layout {{ grid-template-columns:1fr; }} .admin-side-pane {{ position:static; }} }}
    </style>
    <section class="admin-layout">
      <div class="admin-table-pane">
        {''.join(sections_html)}
      </div>
      <aside class="admin-side-pane">
        {side_placeholder}
        {''.join(side_panels)}
      </aside>
    </section>
    <script>
    (() => {{
      const rows = Array.from(document.querySelectorAll('.admin-row[data-admin-target]'));
      const panels = Array.from(document.querySelectorAll('[data-admin-card]'));
      const placeholder = document.querySelector('[data-admin-placeholder]');
      if (!rows.length) {{
        return;
      }}
      const setActive = (targetId) => {{
        let hasMatch = false;
        rows.forEach((row) => {{
          const active = row.dataset.adminTarget === targetId;
          row.classList.toggle('is-active', active);
          row.setAttribute('aria-selected', active ? 'true' : 'false');
        }});
        panels.forEach((panel) => {{
          const active = panel.id === targetId;
          panel.classList.toggle('active', active);
          hasMatch = hasMatch || active;
        }});
        if (placeholder) {{
          placeholder.hidden = hasMatch;
        }}
      }};
      rows.forEach((row) => {{
        row.addEventListener('click', () => setActive(row.dataset.adminTarget));
        row.addEventListener('keydown', (event) => {{
          if (event.key === 'Enter' || event.key === ' ') {{
            event.preventDefault();
            setActive(row.dataset.adminTarget);
          }}
        }});
      }});
      const activeRow = rows.find((row) => row.classList.contains('is-active'));
      if (activeRow) {{
        setActive(activeRow.dataset.adminTarget);
      }}
    }})();
    </script>
    """


def render_records_page(
    title: str,
    current_user: dict[str, Any],
    records: list[dict[str, Any]],
    *,
    admin_mode: bool,
    success: str | None = None,
    empty_text: str,
    empty_action_html: str = "",
    selected_registration_id: str | None = None,
) -> HTMLResponse:
    if records:
        if admin_mode:
            body = render_admin_table(records, selected_registration_id=selected_registration_id)
        else:
            body = f'<section class="cards">{"".join(render_record_card(record, admin_mode=admin_mode) for record in records)}</section>'
    else:
        body = f'<div class="empty">{escape(empty_text)}{empty_action_html}</div>'
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
