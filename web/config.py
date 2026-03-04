from dataclasses import dataclass
import os


SESSION_TTL_HOURS_DEFAULT = 24 * 7


@dataclass(frozen=True)
class Settings:
    mongo_uri: str
    mongo_db: str
    users_collection: str
    registrations_collection: str
    sessions_collection: str
    session_cookie_name: str
    session_ttl_hours: int
    admin_emails: frozenset[str]
    notification_email_sender: str
    notification_email_password: str
    notification_email_smtp_host: str
    notification_email_smtp_port: int
    notification_email_use_ssl: bool

    @classmethod
    def from_env(cls) -> "Settings":
        raw_admin_emails = os.getenv("WEB_ADMIN_EMAILS", "")
        admin_emails = frozenset(
            email.strip().lower()
            for email in raw_admin_emails.split(",")
            if email.strip()
        )
        use_ssl = os.getenv("WEB_NOTIFICATION_EMAIL_USE_SSL", "true").strip().lower() not in {
            "0",
            "false",
            "no",
        }
        return cls(
            mongo_uri=os.getenv("MONGO_URI", "mongodb://localhost:27017"),
            mongo_db=os.getenv("MONGO_DB", "eng_conference"),
            users_collection=os.getenv("WEB_USERS_COLLECTION", "web_users"),
            registrations_collection=os.getenv("WEB_REGISTRATIONS_COLLECTION", "conference_registrations"),
            sessions_collection=os.getenv("WEB_SESSIONS_COLLECTION", "web_sessions"),
            session_cookie_name=os.getenv("WEB_SESSION_COOKIE_NAME", "conference_session"),
            session_ttl_hours=int(os.getenv("WEB_SESSION_TTL_HOURS", str(SESSION_TTL_HOURS_DEFAULT))),
            admin_emails=admin_emails,
            notification_email_sender=os.getenv(
                "WEB_NOTIFICATION_EMAIL_SENDER",
                "graduate.applications@yandex.ru",
            ).strip(),
            notification_email_password=os.getenv("WEB_NOTIFICATION_EMAIL_PASSWORD", ""),
            notification_email_smtp_host=os.getenv("WEB_NOTIFICATION_EMAIL_SMTP_HOST", "smtp.yandex.ru").strip(),
            notification_email_smtp_port=int(os.getenv("WEB_NOTIFICATION_EMAIL_SMTP_PORT", "465")),
            notification_email_use_ssl=use_ssl,
        )
