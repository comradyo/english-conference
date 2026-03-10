from datetime import datetime, timedelta, timezone
from html import escape
from typing import Any

from fastapi.responses import HTMLResponse

from i18n import (
    DEFAULT_LANGUAGE,
    field_label as localized_field_label,
    notice_text,
    participation_label,
    resolve_language,
    review_status_label,
    section_label,
    text,
    validation_status_label,
    validation_summary_label,
)
from models import PARTICIPATION_OPTIONS, REVIEW_STATUSES, SECTION_OPTIONS


MOSCOW_TZ = timezone(timedelta(hours=3), name="UTC+3")

def notice_message(key: str | None, lang: str = DEFAULT_LANGUAGE) -> str | None:
    return notice_text(lang, key)


def layout(
    title: str,
    body: str,
    *,
    current_user: dict[str, Any] | None = None,
    success: str | None = None,
    error: str | None = None,
    lang: str = DEFAULT_LANGUAGE,
) -> HTMLResponse:
    current_lang = resolve_language(lang)
    return HTMLResponse(
        content=f"""<!DOCTYPE html>
<html lang="{escape(current_lang, quote=True)}"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{escape(title)}</title>
<style>
:root {{ --bg:#f5efe7; --panel:#fffdf9; --line:#d7d2c8; --accent:#0f5959; --soft:#d9efef; --text:#1f2529; --muted:#60696f; --danger-bg:#f8dddd; --danger-text:#7f2020; --ok-bg:#dff3e3; --ok-text:#155728; font-family:"Segoe UI",Tahoma,Geneva,Verdana,sans-serif; }}
* {{ box-sizing:border-box; }} body {{ margin:0; min-height:100vh; color:var(--text); background:radial-gradient(circle at top right, rgba(15,89,89,.12), transparent 28%), radial-gradient(circle at bottom left, rgba(180,83,9,.1), transparent 20%), var(--bg); }}
.page {{ width:min(1600px, calc(100% - 32px)); margin:28px auto; }} .shell {{ background:var(--panel); border:1px solid rgba(15,89,89,.1); border-radius:24px; padding:24px; box-shadow:0 18px 50px rgba(15,89,89,.08); }}
.topbar, nav, .card-title {{ display:flex; gap:12px; justify-content:space-between; align-items:flex-start; flex-wrap:wrap; }} .topbar {{ margin-bottom:18px; }} .topbar-side {{ display:grid; gap:12px; justify-items:end; }} nav {{ margin:18px 0 20px; }}
h1 {{ margin:0; font-size:clamp(2rem, 4vw, 2.7rem); line-height:1.05; }} h2 {{ margin:0 0 14px; font-size:1.2rem; }} p {{ margin:0 0 14px; color:var(--muted); }}
.subtitle {{ margin-top:8px; max-width:760px; }} .user-badge, nav a, .language-link {{ padding:10px 14px; border-radius:999px; font-weight:600; text-decoration:none; }}
.user-badge {{ background:#f1f6f6; border:1px solid var(--line); color:var(--accent); }} nav a {{ background:var(--soft); color:var(--accent); }}
.language-switcher {{ display:flex; align-items:center; gap:8px; color:var(--muted); font-weight:600; }} .language-link {{ background:#fff; border:1px solid var(--line); color:var(--accent); }} .language-link.active {{ background:var(--soft); }}
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
input::placeholder, textarea::placeholder {{ color:#96a1a8; opacity:1; }}
textarea {{ min-height:110px; resize:vertical; }}
button {{ border:none; cursor:pointer; background:linear-gradient(135deg, #0f5959, #207070); color:#fff; font-weight:700; min-height:46px; }}
.auth-actions {{ display:grid; gap:10px; justify-items:start; }}
.text-button {{ width:auto; min-height:0; padding:0; border:none; background:none; color:var(--accent); font-weight:700; cursor:pointer; }}
.action-link {{ display:inline-flex; align-items:center; justify-content:center; width:100%; min-height:46px; padding:12px 14px; border-radius:14px; background:var(--soft); color:var(--accent); font-weight:700; text-decoration:none; }}
.action-link.action-link-warning {{ background:#f6dc6b; color:#5a4300; }}
.modal-overlay {{ position:fixed; inset:0; z-index:1400; display:flex; align-items:center; justify-content:center; padding:20px; background:rgba(31,37,41,.45); backdrop-filter:blur(2px); }}
.modal-window {{ width:min(560px, 100%); border:1px solid #b8e3c0; border-radius:16px; background:#fff; box-shadow:0 26px 56px rgba(15,89,89,.22); padding:16px 18px 18px; }}
.modal-header {{ display:flex; justify-content:space-between; align-items:center; gap:12px; margin-bottom:8px; }}
.modal-title {{ margin:0; font-size:1.16rem; color:var(--ok-text); }}
.modal-close {{ width:34px; min-height:34px; padding:0; border:1px solid var(--line); border-radius:10px; background:#fff; color:var(--muted); font-size:1.25rem; font-weight:700; line-height:1; cursor:pointer; }}
.modal-message {{ margin:0; color:var(--text); font-weight:600; }}
.record-highlights {{ margin-bottom:16px; }}
.record-highlight {{ border:1px solid var(--line); border-radius:16px; padding:16px; background:#fff; }}
.record-highlight span {{ display:block; margin-bottom:8px; color:var(--muted); font-size:.95rem; font-weight:600; }}
.record-highlight-body {{ font-size:1.08rem; font-weight:700; line-height:1.45; }}
.record-highlight-comment .record-highlight-body {{ font-size:1.02rem; font-weight:600; }}
.record-highlight-validation .record-highlight-body {{ font-size:1rem; font-weight:600; }}
.comment-thread {{ display:grid; gap:10px; }}
.comment-item {{ border:1px solid var(--line); border-radius:12px; background:#fff; padding:10px 12px; }}
.comment-meta {{ color:var(--muted); font-size:.86rem; font-weight:700; margin-bottom:6px; }}
.comment-text {{ white-space:normal; }}
.record-comment-form {{ margin-top:14px; gap:10px; }}
.record-comment-form textarea {{ min-height:84px; }}
.record-actions {{ margin:0; }}
.section-group {{ border:1px solid var(--line); border-radius:18px; background:#fffdfa; overflow:hidden; }}
.section-group + .section-group {{ margin-top:16px; }}
.section-summary {{ cursor:pointer; padding:16px 18px; font-weight:700; }}
.table-wrap {{ overflow-x:auto; padding:0 18px 18px; }}
.records-table {{ width:100%; border-collapse:collapse; min-width:1100px; }}
.records-table th, .records-table td {{ padding:12px 10px; vertical-align:top; border-top:1px solid var(--line); text-align:left; }}
.records-table th {{ color:var(--muted); font-size:.9rem; font-weight:700; }}
.records-table tbody tr:hover {{ background:rgba(15,89,89,.03); }}
.status-pill {{ display:inline-block; padding:6px 10px; border-radius:999px; background:#e8ebef; color:#4b5563; font-weight:700; }}
.status-pill.status-pending {{ background:#e8ebef; color:#4b5563; }}
.status-pill.status-accepted {{ background:#dff3e3; color:#155728; }}
.status-pill.status-revision {{ background:#f6dc6b; color:#5a4300; }}
.status-pill.status-rejected {{ background:#f8dddd; color:#7f2020; }}
.status-pill.status-pill-large {{ padding:10px 14px; font-size:1.02rem; }}
.admin-tools {{ display:grid; gap:10px; min-width:260px; }}
.admin-tools form {{ gap:10px; }}
.admin-tools textarea {{ min-height:84px; }}
.section-meta {{ color:var(--muted); font-weight:600; }} .field-caption {{ display:inline-flex; align-items:baseline; gap:4px; }} .required-mark {{ color:#a33030; font-weight:800; }} .field-hint {{ color:var(--muted); font-size:.9rem; font-weight:500; }} .consent-row {{ display:flex; align-items:flex-start; gap:10px; font-weight:600; }} .consent-row input[type="checkbox"] {{ width:18px; min-width:18px; height:18px; margin-top:2px; padding:0; border-radius:4px; accent-color:var(--accent); }} .submit-button:disabled {{ background:#c9ced3; color:#7a8288; cursor:not-allowed; }} .form-note {{ margin-top:14px; margin-bottom:0; font-size:.95rem; color:var(--muted); }} .site-footer {{ margin-top:18px; padding:14px 8px 0; text-align:center; color:var(--muted); font-size:.95rem; }}
@media (max-width:820px) {{ .split, .grid {{ grid-template-columns:1fr; }} .shell {{ padding:18px; border-radius:18px; }} }}
</style></head><body><main class="page"><section class="shell"><div class="topbar"><div><h1>{escape(title)}</h1></div><div class="topbar-side">{language_switcher(current_lang)}{user_badge(current_user, lang=current_lang)}</div></div><nav>{nav_html(current_user, lang=current_lang)}</nav>{banner(success, 'success')}{banner(error, 'error')}{body}</section><footer class="site-footer">{escape(text(current_lang, "footer"))}</footer></main><script>
(() => {{
  const links = Array.from(document.querySelectorAll('[data-lang-switch]'));
  if (!links.length) {{
    return;
  }}
  links.forEach((link) => {{
    link.addEventListener('click', (event) => {{
      event.preventDefault();
      const targetLang = link.dataset.langSwitch;
      if (!targetLang) {{
        return;
      }}
      const url = new URL(window.location.href);
      url.searchParams.set('lang', targetLang);
      window.location.assign(url.toString());
    }});
  }});
}})();
(() => {{
  const overlay = document.querySelector('[data-modal-overlay]');
  if (!overlay) {{
    return;
  }}
  const closeModal = () => {{
    overlay.remove();
  }};
  const closeButton = overlay.querySelector('[data-modal-close]');
  if (closeButton) {{
    closeButton.addEventListener('click', closeModal);
  }}
  overlay.addEventListener('click', (event) => {{
    if (event.target === overlay) {{
      closeModal();
    }}
  }});
  document.addEventListener('keydown', (event) => {{
    if (event.key === 'Escape') {{
      closeModal();
    }}
  }});
}})();
</script></body></html>"""
    )


def banner(message: str | None, kind: str) -> str:
    if not message:
        return ""
    return f'<div class="banner {kind}">{escape(message)}</div>'


def language_switcher(lang: str) -> str:
    current_lang = resolve_language(lang)
    links = []
    for language_code, label_key in (("ru", "language_ru"), ("en", "language_en")):
        active_class = " active" if language_code == current_lang else ""
        links.append(
            f'<a href="#" class="language-link{active_class}" data-lang-switch="{language_code}">{escape(text(current_lang, label_key))}</a>'
        )
    return f'<div class="language-switcher"><span>{escape(text(current_lang, "language_switcher_label"))}:</span>{"".join(links)}</div>'


def nav_html(current_user: dict[str, Any] | None, *, lang: str = DEFAULT_LANGUAGE) -> str:
    links = []
    if current_user:
        links.append(f'<a href="/conference/register">{escape(text(lang, "nav_register"))}</a>')
        links.append(f'<a href="/my-registrations">{escape(text(lang, "nav_my_records"))}</a>')
        if current_user.get("is_admin"):
            links.append(f'<a href="/all_applications">{escape(text(lang, "nav_all_records"))}</a>')
        links.append(f'<a href="/logout">{escape(text(lang, "nav_logout"))}</a>')
    else:
        links.append(f'<a href="/">{escape(text(lang, "nav_auth"))}</a>')
    return "".join(links)


def user_badge(current_user: dict[str, Any] | None, *, lang: str = DEFAULT_LANGUAGE) -> str:
    if not current_user:
        return f'<div class="user-badge">{escape(text(lang, "guest"))}</div>'
    role = text(lang, "role_admin") if current_user.get("is_admin") else text(lang, "role_user")
    return f'<div class="user-badge">{escape(current_user["email"])} | {escape(role)}</div>'


def field_value(values: dict[str, str], key: str, default: str = "") -> str:
    return escape(values.get(key, default), quote=True)


def render_select(name: str, options: tuple[str, ...], selected: str | None, *, lang: str = DEFAULT_LANGUAGE) -> str:
    rendered = []
    for option in options:
        selected_attr = " selected" if selected == option else ""
        display_value = option
        if name == "participation":
            display_value = participation_label(lang, option)
        elif name == "section":
            display_value = section_label(lang, option)
        elif name == "review_status":
            display_value = review_status_label(lang, option)
        rendered.append(
            f'<option value="{escape(option, quote=True)}"{selected_attr}>{escape(display_value)}</option>'
        )
    return f'<select name="{escape(name, quote=True)}">{"".join(rendered)}</select>'


def meta_row(label: str, value: str) -> str:
    return f'<div class="meta-row"><span>{escape(label)}</span><strong>{escape(value)}</strong></div>'


def meta_html_row(label: str, value_html: str) -> str:
    return f'<div class="meta-row"><span>{escape(label)}</span><strong>{value_html}</strong></div>'


def format_dt(value: Any, *, lang: str = DEFAULT_LANGUAGE) -> str:
    if isinstance(value, datetime):
        suffix = text(lang, "timezone_suffix")
        return f'{value.astimezone(MOSCOW_TZ).strftime("%d.%m.%Y %H:%M")} ({suffix})'
    return text(lang, "not_specified")


def optional_value(value: Any, *, empty: str | None = None, lang: str = DEFAULT_LANGUAGE) -> str:
    fallback = empty or text(lang, "not_specified")
    value_text = str(value or "").strip()
    return value_text or fallback


def file_name(file_info: dict[str, Any] | None, *, empty: str | None = None, lang: str = DEFAULT_LANGUAGE) -> str:
    fallback = empty or text(lang, "not_uploaded")
    if not isinstance(file_info, dict):
        return fallback
    return optional_value(file_info.get("filename"), empty=fallback, lang=lang)


def validation_summary_text(validation_info: dict[str, Any] | None, *, lang: str = DEFAULT_LANGUAGE) -> str:
    if not isinstance(validation_info, dict):
        return text(lang, "checker_pending_summary")
    summary = str(validation_info.get("summary") or "").strip()
    return validation_summary_label(lang, summary or text(lang, "checker_pending_summary"))


def validation_errors_text(validation_info: dict[str, Any] | None, *, lang: str = DEFAULT_LANGUAGE) -> str:
    if not isinstance(validation_info, dict):
        return text(lang, "no_remarks")
    errors = validation_info.get("errors")
    if not isinstance(errors, (list, tuple)):
        return text(lang, "no_remarks")
    parts = [str(item).strip() for item in errors if str(item).strip()]
    return "; ".join(parts) if parts else text(lang, "no_remarks")


def render_validation_details_html(validation_info: dict[str, Any] | None, *, lang: str = DEFAULT_LANGUAGE) -> str:
    summary = escape(validation_summary_text(validation_info, lang=lang))
    if not isinstance(validation_info, dict):
        return summary

    errors = validation_info.get("errors")
    if not isinstance(errors, (list, tuple)):
        return summary

    parts = [str(item).strip() for item in errors if str(item).strip()]
    if not parts:
        return summary

    errors_html = "<br>".join(escape(item) for item in parts)
    return f"{summary}<br><br>{errors_html}"


def status_tone_class(status: str) -> str:
    mapping = {
        "На рассмотрении": "status-pending",
        "Принята": "status-accepted",
        "На доработке": "status-revision",
        "Отклонена": "status-rejected",
    }
    return mapping.get(status, "status-pending")


def render_status_badge(status: str, *, large: bool = False, lang: str = DEFAULT_LANGUAGE) -> str:
    classes = ["status-pill", status_tone_class(status)]
    if large:
        classes.append("status-pill-large")
    return f'<span class="{" ".join(classes)}">{escape(review_status_label(lang, status))}</span>'


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


def registration_comments(record: dict[str, Any]) -> list[dict[str, Any]]:
    comments = record.get("comments")
    if not isinstance(comments, list):
        return []

    normalized: list[dict[str, Any]] = []
    for item in comments:
        if not isinstance(item, dict):
            continue
        comment_text = str(item.get("text") or "").strip()
        if not comment_text:
            continue
        normalized.append(
            {
                "author_role": str(item.get("author_role") or "").strip().lower(),
                "author_email": str(item.get("author_email") or "").strip(),
                "text": comment_text,
                "created_at": item.get("created_at"),
            }
        )
    return normalized


def comment_author_label(comment: dict[str, Any], *, lang: str = DEFAULT_LANGUAGE) -> str:
    role = str(comment.get("author_role") or "").strip().lower()
    if role == "admin":
        base_label = text(lang, "comment_author_admin")
    elif role == "author":
        base_label = text(lang, "comment_author_author")
    else:
        base_label = text(lang, "comment_author_unknown")

    author_email = str(comment.get("author_email") or "").strip()
    if not author_email:
        return base_label
    return f"{base_label} ({author_email})"


def render_comments_thread_html(record: dict[str, Any], *, lang: str = DEFAULT_LANGUAGE) -> str:
    comments = registration_comments(record)
    if not comments:
        return escape(text(lang, "comment_not_added"))

    items_html: list[str] = []
    for comment in comments:
        created_at = comment.get("created_at")
        created_text = format_dt(created_at, lang=lang) if isinstance(created_at, datetime) else text(lang, "not_specified")
        comment_text_html = escape(str(comment.get("text") or "")).replace("\n", "<br>")
        items_html.append(
            '<article class="comment-item">'
            f'<div class="comment-meta">{escape(comment_author_label(comment, lang=lang))} | {escape(created_text)}</div>'
            f'<div class="comment-text">{comment_text_html}</div>'
            "</article>"
        )

    return f'<div class="comment-thread">{"".join(items_html)}</div>'


def field_label(path: str, *, lang: str = DEFAULT_LANGUAGE) -> str:
    return localized_field_label(lang, path)


def form_language_label(value: Any, *, lang: str = DEFAULT_LANGUAGE) -> str:
    value_text = str(value or "").strip().lower()
    if not value_text:
        return text(lang, "not_specified")
    if value_text == "ru":
        return text(lang, "language_ru")
    if value_text == "en":
        return text(lang, "language_en")
    return value_text


def _legacy_render_object_fields(record: dict[str, Any]) -> str:
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


def render_object_fields(record: dict[str, Any], *, lang: str = DEFAULT_LANGUAGE) -> str:
    rows: list[str] = []

    def append_field(path: str, value: Any) -> None:
        if isinstance(value, dict):
            if path == "publication_validation":
                summary = validation_summary_text(value, lang=lang)
            else:
                summary = text(lang, "not_specified") if not value else optional_value(
                    value.get("filename"),
                    empty=text(lang, "see_nested_fields"),
                    lang=lang,
                )
            rows.append(meta_row(field_label(path, lang=lang), summary))
            if not value:
                return
            for nested_key, nested_value in value.items():
                if nested_key in {"data", "summary", "checked_at", "started_at"}:
                    continue
                append_field(f"{path}.{nested_key}", nested_value)
            return
        if path in {'publication_file.content_type', 'expert_opinion_file.content_type', 'publication_file.filename',
                    'expert_opinion_file.filename', 'last_name', 'first_name', 'middle_name', 'owner_email', 'comments',
                    'admin_comment'}:
            return
        if path == "publication_validation.status":
            status_value = validation_status_label(lang, str(value or ""))
            rows.append(meta_row(field_label(path, lang=lang), status_value or text(lang, "not_specified")))
            return
        if path == "review_status":
            status = str(value or REVIEW_STATUSES[0])
            rows.append(meta_html_row(field_label(path, lang=lang), render_status_badge(status, lang=lang)))
            return
        if isinstance(value, datetime):
            rows.append(meta_row(field_label(path, lang=lang), format_dt(value, lang=lang)))
            return
        if isinstance(value, (list, tuple)):
            parts = [str(item).strip() for item in value if str(item).strip()]
            if not parts:
                empty_value = text(lang, "no_remarks") if path == "publication_validation.errors" else text(lang, "not_specified")
                rows.append(meta_row(field_label(path, lang=lang), empty_value))
                return
            rows.append(meta_html_row(field_label(path, lang=lang), "<br>".join(escape(item) for item in parts)))
            return
        if value is None:
            empty_value = text(lang, "not_uploaded") if path == "expert_opinion_file" else text(lang, "not_specified")
            rows.append(meta_row(field_label(path, lang=lang), empty_value))
            return
        value_text = str(value).strip()
        if not value_text:
            empty_value = text(lang, "not_uploaded") if path == "expert_opinion_file" else text(lang, "not_specified")
            rows.append(meta_row(field_label(path, lang=lang), empty_value))
            return
        if path == "participation":
            value_text = participation_label(lang, value_text)
        elif path == "section":
            value_text = section_label(lang, value_text)
        elif path == "form_language":
            value_text = form_language_label(value_text, lang=lang)
        rows.append(meta_row(field_label(path, lang=lang), value_text))

    for key, value in record.items():
        append_field(key, value)
    return "".join(rows)


def render_auth_page(
    *,
    error: str | None = None,
    success: str | None = None,
    register_values: dict[str, str] | None = None,
    login_values: dict[str, str] | None = None,
    forgot_values: dict[str, str] | None = None,
    lang: str = DEFAULT_LANGUAGE,
) -> HTMLResponse:
    register_values = register_values or {}
    login_values = login_values or {}
    forgot_values = forgot_values or {}
    show_register = bool(register_values) and not bool(login_values) and not bool(forgot_values)
    show_forgot = bool(forgot_values) and not bool(login_values) and not bool(register_values)
    login_hidden_attr = " hidden" if (show_register or show_forgot) else ""
    register_hidden_attr = "" if show_register else " hidden"
    forgot_hidden_attr = "" if show_forgot else " hidden"
    body = f"""
    <section class="cards">
      <section class="panel" id="login-panel"{login_hidden_attr}><h2>{escape(text(lang, "auth_login_title"))}</h2><p>{escape(text(lang, "auth_login_desc"))}</p>
        <form method="post" action="/login">
          <label>{escape(text(lang, "auth_email"))}<input type="email" name="email" required value="{field_value(login_values, 'email')}"></label>
          <label>{escape(text(lang, "auth_password"))}<input type="password" name="password" required></label>
          <button type="submit">{escape(text(lang, "auth_sign_in"))}</button>
        </form>
        <br>
        <div class="auth-actions">
          <button type="button" id="show-register-button">{escape(text(lang, "auth_create_account"))}</button>
          <button type="button" class="text-button" id="show-forgot-button">{escape(text(lang, "auth_forgot_password"))}</button>
        </div>
      </section>
      <section class="panel" id="register-panel"{register_hidden_attr}><h2>{escape(text(lang, "auth_register_title"))}</h2><p>{escape(text(lang, "auth_register_desc"))}</p>
        <form method="post" action="/register-account">
          <label>{escape(text(lang, "auth_email"))}<input id="register-email" type="email" name="email" required value="{field_value(register_values, 'email')}"></label>
          <label>{escape(text(lang, "auth_password"))}<input type="password" name="password" required minlength="8"></label>
          <label>{escape(text(lang, "auth_repeat_password"))}<input type="password" name="password_repeat" required minlength="8"></label>
          <button type="submit">{escape(text(lang, "auth_register_button"))}</button>
        </form>
        <br>
        <div class="auth-actions">
          <button type="button" id="show-login-button">{escape(text(lang, "auth_back_to_login"))}</button>
        </div>
      </section>
      <section class="panel" id="forgot-panel"{forgot_hidden_attr}><h2>{escape(text(lang, "forgot_title"))}</h2><p>{escape(text(lang, "forgot_desc"))}</p>
        <form method="post" action="/forgot-password">
          <label>{escape(text(lang, "auth_email"))}<input id="forgot-email" type="email" name="email" required value="{field_value(forgot_values, 'email')}"></label>
          <button type="submit">{escape(text(lang, "forgot_button"))}</button>
        </form>
        <br>
        <div class="auth-actions">
          <button type="button" id="show-login-from-forgot-button">{escape(text(lang, "auth_back_to_login"))}</button>
        </div>
      </section>
    </section>
    <script>
      (function () {{
        const loginPanel = document.getElementById("login-panel");
        const registerPanel = document.getElementById("register-panel");
        const forgotPanel = document.getElementById("forgot-panel");
        const showRegisterButton = document.getElementById("show-register-button");
        const showLoginButton = document.getElementById("show-login-button");
        const showForgotButton = document.getElementById("show-forgot-button");
        const showLoginFromForgotButton = document.getElementById("show-login-from-forgot-button");
        const registerEmail = document.getElementById("register-email");
        const forgotEmail = document.getElementById("forgot-email");

        if (!loginPanel || !registerPanel || !forgotPanel || !showRegisterButton || !showLoginButton || !showForgotButton || !showLoginFromForgotButton) {{
          return;
        }}

        function showRegisterPanel() {{
          loginPanel.hidden = true;
          registerPanel.hidden = false;
          forgotPanel.hidden = true;
          if (registerEmail) {{
            registerEmail.focus();
          }}
        }}

        function showForgotPanel() {{
          loginPanel.hidden = true;
          registerPanel.hidden = true;
          forgotPanel.hidden = false;
          if (forgotEmail) {{
            forgotEmail.focus();
          }}
        }}

        function showLoginPanel() {{
          registerPanel.hidden = true;
          forgotPanel.hidden = true;
          loginPanel.hidden = false;
        }}

        showRegisterButton.addEventListener("click", showRegisterPanel);
        showForgotButton.addEventListener("click", showForgotPanel);
        showLoginButton.addEventListener("click", showLoginPanel);
        showLoginFromForgotButton.addEventListener("click", showLoginPanel);
      }})();
    </script>
    """
    return layout(text(lang, "auth_page_title"), body, success=success, error=error, lang=lang)


def render_password_reset_page(
    token: str,
    *,
    error: str | None = None,
    success: str | None = None,
    lang: str = DEFAULT_LANGUAGE,
) -> HTMLResponse:
    body = f"""
    <section class="panel">
      <h2>{escape(text(lang, "reset_title"))}</h2>
      <p>{escape(text(lang, "reset_desc"))}</p>
      <form method="post" action="/reset-password">
        <input type="hidden" name="token" value="{escape(token, quote=True)}">
        <label>{escape(text(lang, "reset_title"))}<input type="password" name="password" required minlength="8"></label>
        <label>{escape(text(lang, "auth_repeat_password"))}<input type="password" name="password_repeat" required minlength="8"></label>
        <button type="submit">{escape(text(lang, "reset_save_button"))}</button>
      </form>
      <br>
      <div class="auth-actions">
        <a class="action-link" href="/">{escape(text(lang, "back_to_login"))}</a>
      </div>
    </section>
    """
    return layout(text(lang, "reset_page_title"), body, success=success, error=error, lang=lang)


def render_invalid_reset_token_page(error: str, *, lang: str = DEFAULT_LANGUAGE) -> HTMLResponse:
    body = f"""
    <section class="panel">
      <h2>{escape(text(lang, "reset_invalid_title"))}</h2>
      <p>{escape(text(lang, "reset_invalid_desc"))}</p>
      <br>
      <div class="auth-actions">
        <a class="action-link" href="/">{escape(text(lang, "back_to_login"))}</a>
      </div>
    </section>
    """
    return layout(text(lang, "reset_page_title"), body, error=error, lang=lang)


def render_conference_form(
    current_user: dict[str, Any],
    *,
    error: str | None = None,
    success: str | None = None,
    values: dict[str, str] | None = None,
    precheck_error: str | None = None,
    precheck_file_name: str | None = None,
    precheck_result_text: str | None = None,
    edit_registration_id: str | None = None,
    existing_publication_file_name: str | None = None,
    existing_expert_opinion_file_name: str | None = None,
    lang: str = DEFAULT_LANGUAGE,
) -> HTMLResponse:
    is_edit_mode = bool(str(edit_registration_id or "").strip())
    form_action = "/conference/register"
    if is_edit_mode:
        form_action = f'/conference/register/{str(edit_registration_id).strip()}/edit'

    form_title_key = "conference_edit_title" if is_edit_mode else "conference_title"
    form_desc_key = "conference_edit_desc" if is_edit_mode else "conference_desc"
    submit_button_key = "submit_application_update" if is_edit_mode else "submit_application"
    page_title_key = "conference_edit_page_title" if is_edit_mode else "conference_page_title"

    publication_required_mark = ' <span class="required-mark">*</span>' if not is_edit_mode else ""
    publication_required_attr = " required" if not is_edit_mode else ""

    publication_hint_parts = [text(lang, "hint_publication_file")]
    existing_publication_name = str(existing_publication_file_name or "").strip()
    if is_edit_mode and existing_publication_name:
        publication_hint_parts.append(text(lang, "current_file_name_hint", filename=existing_publication_name))
    publication_hint_html = "<br>".join(escape(part) for part in publication_hint_parts)

    expert_hint_parts = [text(lang, "hint_expert_opinion_file")]
    existing_expert_name = str(existing_expert_opinion_file_name or "").strip()
    if is_edit_mode and existing_expert_name:
        expert_hint_parts.append(text(lang, "current_file_name_hint", filename=existing_expert_name))
    expert_hint_html = "<br>".join(escape(part) for part in expert_hint_parts)

    values = dict(values or {})
    values.setdefault("email", current_user["email"])
    values.setdefault("participation", PARTICIPATION_OPTIONS[0])
    values.setdefault("section", SECTION_OPTIONS[0])
    precheck_result_html = ""
    if precheck_result_text:
        lines = [line.strip() for line in str(precheck_result_text).splitlines() if line.strip()]
        rendered_text = "<br>".join(escape(line) for line in lines) if lines else escape(precheck_result_text)
        file_name_html = ""
        if precheck_file_name:
            file_name_html = f'<p><strong>{escape(text(lang, "file_name_prefix"))}</strong> {escape(precheck_file_name)}</p>'
        precheck_result_html = (
            '<div class="record-highlight record-highlight-validation">'
            f'<span>{escape(text(lang, "precheck_result"))}</span>'
            f'{file_name_html}<div class="record-highlight-body">{rendered_text}</div>'
            "</div>"
        )
    precheck_section = f"""
    <section class="panel">
      <h2>{escape(text(lang, "precheck_title"))}</h2>
      <p>{escape(text(lang, "precheck_desc"))}</p>
      {banner(precheck_error, 'error')}
      {precheck_result_html}
      <form method="post" action="/conference/precheck" enctype="multipart/form-data">
        <label><span class="field-caption">{escape(field_label("publication_file", lang=lang))}</span><input type="file" name="publication_file" accept=".docx" required></label>
        <button type="submit">{escape(text(lang, "precheck_button"))}</button>
      </form>
    </section>
    """
    success_modal = ""
    if success:
        success_modal = (
            '<div class="modal-overlay" data-modal-overlay>'
            '<div class="modal-window" role="dialog" aria-modal="true">'
            f'<div class="modal-header"><h3 class="modal-title">{escape(text(lang, "modal_success_title"))}</h3>'
            f'<button type="button" class="modal-close" data-modal-close aria-label="{escape(text(lang, "modal_close"), quote=True)}">&times;</button></div>'
            "</div></div>"
        )
    body = f"""
    {success_modal}
    {precheck_section}
    <section class="panel"><h2>{escape(text(lang, form_title_key))}</h2><p>{escape(text(lang, form_desc_key))}</p>
      <form id="conference-registration-form" method="post" action="{escape(form_action, quote=True)}" enctype="multipart/form-data">
        <div class="grid">
          <label><span class="field-caption">{escape(field_label("last_name", lang=lang))} <span class="required-mark">*</span></span><input type="text" name="last_name" placeholder="{escape(text(lang, "placeholder_last_name"), quote=True)}" required value="{field_value(values, 'last_name')}"></label>
          <label><span class="field-caption">{escape(field_label("first_name", lang=lang))} <span class="required-mark">*</span></span><input type="text" name="first_name" placeholder="{escape(text(lang, "placeholder_first_name"), quote=True)}" required value="{field_value(values, 'first_name')}"></label>
          <label><span class="field-caption">{escape(field_label("middle_name", lang=lang))}</span><input type="text" name="middle_name" value="{field_value(values, 'middle_name')}"></label>
          <label><span class="field-caption">{escape(field_label("place_of_study", lang=lang))} <span class="required-mark">*</span></span><input type="text" name="place_of_study" placeholder="{escape(text(lang, "placeholder_place_of_study"), quote=True)}" required value="{field_value(values, 'place_of_study')}"></label>
          <label><span class="field-caption">{escape(field_label("department", lang=lang))}</span><input type="text" name="department" placeholder="{escape(text(lang, "placeholder_department"), quote=True)}" value="{field_value(values, 'department')}"></label>
          <label><span class="field-caption">{escape(field_label("place_of_work", lang=lang))} <span class="required-mark">*</span></span><input type="text" name="place_of_work" required value="{field_value(values, 'place_of_work')}"></label>
          <label><span class="field-caption">{escape(field_label("job_title", lang=lang))}</span><input type="text" name="job_title" value="{field_value(values, 'job_title')}"></label>
          <label><span class="field-caption">{escape(field_label("phone", lang=lang))} <span class="required-mark">*</span></span><input type="tel" name="phone" placeholder="{escape(text(lang, "placeholder_phone"), quote=True)}" required value="{field_value(values, 'phone')}"></label>
          <label><span class="field-caption">{escape(text(lang, "auth_email"))} <span class="required-mark">*</span></span><input type="email" name="email" placeholder="{escape(text(lang, "placeholder_email"), quote=True)}" required value="{field_value(values, 'email')}"></label>
          <label><span class="field-caption">{escape(field_label("participation", lang=lang))} <span class="required-mark">*</span></span>{render_select('participation', PARTICIPATION_OPTIONS, values.get('participation'), lang=lang)}<span class="field-hint">{escape(text(lang, "hint_participation_student_moscow"))}</span></label>
          <label><span class="field-caption">{escape(field_label("section", lang=lang))} <span class="required-mark">*</span></span>{render_select('section', SECTION_OPTIONS, values.get('section'), lang=lang)}</label>
          <label><span class="field-caption">{escape(field_label("publication_title", lang=lang))} <span class="required-mark">*</span></span><input type="text" name="publication_title" required value="{field_value(values, 'publication_title')}"></label>
          <label><span class="field-caption">{escape(field_label("foreign_language_consultant", lang=lang))} <span class="required-mark">*</span></span><input type="text" name="foreign_language_consultant" required value="{field_value(values, 'foreign_language_consultant')}"></label>
          <label><span class="field-caption">{escape(field_label("publication_file", lang=lang))}{publication_required_mark}</span><input type="file" name="publication_file" accept=".docx"{publication_required_attr}><span class="field-hint">{publication_hint_html}</span></label>
          <label><span class="field-caption">{escape(field_label("expert_opinion_file", lang=lang))}</span><input type="file" name="expert_opinion_file" accept=".docx"><span class="field-hint">{expert_hint_html}</span></label>
        </div>
        <label class="consent-row"><input type="checkbox" name="personal_data_consent" required><span>{escape(text(lang, "personal_data_consent"))}</span></label>
        <button id="conference-submit-button" class="submit-button" type="submit" disabled>{escape(text(lang, submit_button_key))}</button>
      </form>
      <script>
        (() => {{
          const form = document.getElementById("conference-registration-form");
          const submitButton = document.getElementById("conference-submit-button");
          if (!form || !submitButton) {{
            return;
          }}
          const updateSubmitState = () => {{
            submitButton.disabled = !form.checkValidity();
          }};
          form.addEventListener("input", updateSubmitState);
          form.addEventListener("change", updateSubmitState);
          updateSubmitState();
        }})();
      </script>
      <p class="form-note"><span class="required-mark">*</span> {escape(text(lang, "required_note"))}</p>
    </section>
    """
    return layout(text(lang, page_title_key), body, current_user=current_user, error=error, lang=lang)


def _legacy_render_record_card(record: dict[str, Any], *, admin_mode: bool) -> str:
    publication_file = record.get("publication_file") or {}
    expert_opinion_file = record.get("expert_opinion_file") or {}
    review_status = str(record.get("review_status") or REVIEW_STATUSES[0])
    comment_text = str(record.get("admin_comment") or "").strip() or "Комментарий пока не добавлен."
    full_name = " ".join(
        part
        for part in [
            str(record.get("last_name") or "").strip(),
            str(record.get("first_name") or "").strip(),
            str(record.get("middle_name") or "").strip(),
        ]
        if part
    )
    rows = [
        meta_row("Фамилия", str(record.get("last_name", ""))),
        meta_row("Имя", str(record.get("first_name", ""))),
        meta_row("Отчество", optional_value(record.get("middle_name"))),
        meta_row("Место учёбы", str(record.get("place_of_study", ""))),
        meta_row("Кафедра", optional_value(record.get("department"))),
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


def render_record_card(record: dict[str, Any], *, admin_mode: bool, lang: str = DEFAULT_LANGUAGE) -> str:
    publication_file = record.get("publication_file") or {}
    expert_opinion_file = record.get("expert_opinion_file") or {}
    publication_validation = record.get("publication_validation") or {}
    review_status = str(record.get("review_status") or REVIEW_STATUSES[0])
    record_id = str(record.get("_id") or "").strip()
    comments_html = render_comments_thread_html(record, lang=lang)
    validation_summary = validation_summary_text(publication_validation, lang=lang)
    full_name = " ".join(
        part
        for part in [
            str(record.get("last_name") or "").strip(),
            str(record.get("first_name") or "").strip(),
            str(record.get("middle_name") or "").strip(),
        ]
        if part
    )
    rows = [
        meta_row(field_label("last_name", lang=lang), str(record.get("last_name", ""))),
        meta_row(field_label("first_name", lang=lang), str(record.get("first_name", ""))),
        meta_row(field_label("middle_name", lang=lang), optional_value(record.get("middle_name"), lang=lang)),
        meta_row(field_label("place_of_study", lang=lang), str(record.get("place_of_study", ""))),
        meta_row(field_label("department", lang=lang), optional_value(record.get("department"), lang=lang)),
        meta_row(field_label("place_of_work", lang=lang), optional_value(record.get("place_of_work"), lang=lang)),
        meta_row(field_label("job_title", lang=lang), optional_value(record.get("job_title"), lang=lang)),
        meta_row(field_label("phone", lang=lang), str(record.get("phone", ""))),
        meta_row(text(lang, "auth_email"), str(record.get("email", ""))),
        meta_row(field_label("participation", lang=lang), participation_label(lang, str(record.get("participation", "")))),
        meta_row(field_label("section", lang=lang), section_label(lang, str(record.get("section", "")))),
        meta_row(field_label("publication_title", lang=lang), str(record.get("publication_title", ""))),
        meta_row(field_label("foreign_language_consultant", lang=lang), str(record.get("foreign_language_consultant", ""))),
        meta_row(field_label("publication_file", lang=lang), file_name(publication_file, lang=lang)),
        meta_row(
            text(lang, "publication_file_size"),
            f"{int(publication_file.get('size_bytes', 0))} {text(lang, 'bytes_unit')}" if publication_file.get("filename") else text(lang, "not_specified"),
        ),
        meta_row(text(lang, "validation_result_label"), validation_summary),
        meta_row(field_label("expert_opinion_file", lang=lang), file_name(expert_opinion_file, lang=lang)),
        meta_row(
            text(lang, "expert_file_size"),
            f"{int(expert_opinion_file.get('size_bytes', 0))} {text(lang, 'bytes_unit')}" if expert_opinion_file.get("filename") else text(lang, "not_specified"),
        ),
        meta_row(field_label("form_language", lang=lang), form_language_label(record.get("form_language"), lang=lang)),
        meta_row(field_label("created_at", lang=lang), format_dt(record.get("created_at"), lang=lang)),
    ]
    if admin_mode:
        rows.insert(0, meta_html_row(text(lang, "highlight_status"), render_status_badge(review_status, lang=lang)))
        rows.append(meta_row(text(lang, "owner_account_email"), str(record.get("owner_email", ""))))
        comment_block = render_highlight_block(text(lang, "highlight_comment"), comments_html, extra_class="record-highlight-comment")
        highlights_html = ""
        author_comment_form_html = ""
    else:
        edit_action_html = ""
        if review_status == REVIEW_STATUSES[2] and record_id:
            edit_action_html = (
                '<div class="record-actions">'
                f'<a class="action-link action-link-warning" href="/conference/register/{escape(record_id, quote=True)}/edit">{escape(text(lang, "edit_rejected_application"))}</a>'
                "</div>"
            )
        highlights_html = (
            '<section class="record-highlights"><br>'
            f'{render_highlight_block(text(lang, "highlight_status"), render_status_badge(review_status, large=True, lang=lang))}'
            f"{edit_action_html}"
            f'{render_highlight_block(text(lang, "highlight_validation"), render_validation_details_html(publication_validation, lang=lang), extra_class="record-highlight-validation")}'
            f'{render_highlight_block(text(lang, "highlight_comment"), comments_html, extra_class="record-highlight-comment")}'
            "</section>"
        )
        comment_block = ""
        author_comment_form_html = ""
        if record_id:
            author_comment_form_html = (
                f'<form method="post" action="/my-registrations/comment/{escape(record_id, quote=True)}" class="record-comment-form">'
                f'<label>{escape(text(lang, "comment_add_label"))}<textarea name="comment_text" placeholder="{escape(text(lang, "author_comment_placeholder"), quote=True)}"></textarea></label>'
                f'<button type="submit">{escape(text(lang, "comment_submit_button"))}</button>'
                "</form>"
            )
    return f'<article class="card"><div class="card-title"><strong>{escape(full_name or text(lang, "unnamed_record"))}</strong></div>{highlights_html}<div class="meta">{"".join(rows)}{comment_block}</div>{author_comment_form_html}</article>'


def render_admin_table(
    records: list[dict[str, Any]],
    *,
    selected_registration_id: str | None = None,
    lang: str = DEFAULT_LANGUAGE,
) -> str:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for record in records:
        section = str(record.get("section") or text(lang, "without_section"))
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
            last_name = str(record.get("last_name") or "").strip()
            first_name = str(record.get("first_name") or "").strip()
            middle_name = str(record.get("middle_name") or "").strip()
            full_name = " ".join(
                part
                for part in [
                    last_name,
                    first_name,
                    middle_name,
                ]
                if part
            ) or text(lang, "unnamed_person")
            name_cell = "".join(
                f"<div>{escape(part)}</div>"
                for part in [last_name, first_name, middle_name]
                if part
            ) or f'<div>{escape(text(lang, "unnamed_person"))}</div>'
            publication_file = record.get("publication_file") or {}
            expert_opinion_file = record.get("expert_opinion_file") or {}
            review_status = str(record.get("review_status") or REVIEW_STATUSES[0])
            is_selected = bool(selected_registration_id and selected_registration_id == record_id)
            status_options = "".join(
                f'<option value="{escape(status, quote=True)}"{" selected" if status == review_status else ""}>{escape(review_status_label(lang, status))}</option>'
                for status in REVIEW_STATUSES
            )
            download_links: list[str] = []
            if publication_file.get("filename"):
                download_links.append(
                    f'<a class="action-link" href="/all_applications/file/{record_id}/publication">{escape(text(lang, "admin_download_publication"))}</a>'
                )
            if expert_opinion_file.get("filename"):
                download_links.append(
                    f'<a class="action-link" href="/all_applications/file/{record_id}/expert-opinion">{escape(text(lang, "admin_download_expert"))}</a>'
                )
            downloads_html = "".join(download_links)
            contacts_cell = (
                f'<div class="file-stack"><div>{escape(str(record.get("email", "")))}</div>'
                f'<div>{escape(str(record.get("phone", "")))}</div></div>'
            )
            record_fields_html = render_object_fields(record, lang=lang)
            comments_html = render_comments_thread_html(record, lang=lang)

            rows_html.append(
                f"""
                <tr class="admin-row{" is-active" if is_selected else ""}" data-admin-target="admin-actions-{record_id}" tabindex="0" role="button" aria-selected="{"true" if is_selected else "false"}">
                  <td><div class="file-stack">{name_cell}</div></td>
                  <td>{contacts_cell}</td>
                  <td>{escape(participation_label(lang, str(record.get("participation", ""))))}</td>
                  <td>{escape(str(record.get("publication_title", "")))}</td>
                  <td>{render_status_badge(review_status, lang=lang)}</td>
                  <td>{escape(format_dt(record.get("created_at"), lang=lang))}</td>
                </tr>
                """
            )
            side_panels.append(
                f"""
                <section id="admin-actions-{record_id}" class="panel admin-side-card{" active" if is_selected else ""}" data-admin-card>
                  <h2>{escape(full_name or text(lang, "unnamed_person"))}</h2>
                  <p>{escape(text(lang, "admin_tools_desc"))}</p>
                  <div class="meta">{record_fields_html}</div>
                  {render_highlight_block(text(lang, "highlight_comment"), comments_html, extra_class="record-highlight-comment")}
                  <div class="admin-tools">
                    {downloads_html}
                    <form method="post" action="/all_applications/comment/{record_id}">
                      <label>{escape(text(lang, "highlight_status"))}<select name="review_status">{status_options}</select></label>
                      <label>{escape(text(lang, "comment_add_label"))}<textarea name="comment_text" placeholder="{escape(text(lang, "admin_comment_placeholder"), quote=True)}"></textarea></label>
                      <button type="submit">{escape(text(lang, "admin_save"))}</button>
                    </form>
                  </div>
                </section>
                """
            )

        sections_html.append(
            f"""
            <details class="section-group" open>
              <summary class="section-summary">{escape(section_label(lang, section))} <span class="section-meta">{escape(text(lang, "section_count", count=len(section_records)))}</span></summary>
              <div class="table-wrap">
                <table class="records-table">
                  <thead>
                    <tr>
                      <th>{escape(text(lang, "admin_table_participant"))}</th>
                      <th>{escape(text(lang, "admin_table_contacts"))}</th>
                      <th>{escape(text(lang, "admin_table_participation"))}</th>
                      <th>{escape(text(lang, "admin_table_publication"))}</th>
                      <th>{escape(text(lang, "admin_table_status"))}</th>
                      <th>{escape(text(lang, "admin_table_created_at"))}</th>
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
        f"<h2>{escape(text(lang, 'admin_side_empty_title'))}</h2>"
        f"<p>{escape(text(lang, 'admin_side_empty_desc'))}</p>"
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
    lang: str = DEFAULT_LANGUAGE,
) -> HTMLResponse:
    if records:
        if admin_mode:
            body = render_admin_table(records, selected_registration_id=selected_registration_id, lang=lang)
        else:
            body = f'<section class="cards">{"".join(render_record_card(record, admin_mode=admin_mode, lang=lang) for record in records)}</section>'
    else:
        body = f'<div class="empty">{escape(empty_text)}{empty_action_html}</div>'
    return layout(title, body, current_user=current_user, success=success, lang=lang)


def render_forbidden(current_user: dict[str, Any], *, lang: str = DEFAULT_LANGUAGE) -> HTMLResponse:
    response = layout(
        text(lang, "forbidden_title"),
        f'<div class="empty">{escape(text(lang, "forbidden_body"))}</div>',
        current_user=current_user,
        error=text(lang, "forbidden_error"),
        lang=lang,
    )
    response.status_code = 403
    return response
