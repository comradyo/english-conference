from dataclasses import dataclass
import os


SESSION_TTL_HOURS_DEFAULT = 24 * 7


@dataclass(frozen=True)
class Settings:
    mongo_uri: str
    mongo_db: str
    users_collection: str
    registrations_collection: str
    email_tasks_collection: str
    password_reset_tokens_collection: str
    sessions_collection: str
    session_cookie_name: str
    session_ttl_hours: int
    password_reset_ttl_minutes: int
    checker_api_url: str
    checker_api_timeout_sec: int
    admin_emails: frozenset[str]

    @classmethod
    def from_env(cls) -> "Settings":
        raw_admin_emails = os.getenv("WEB_ADMIN_EMAILS", "")
        admin_emails = frozenset(
            email.strip().lower()
            for email in raw_admin_emails.split(",")
            if email.strip()
        )
        return cls(
            mongo_uri=os.getenv("MONGO_URI", "mongodb://localhost:27017"),
            mongo_db=os.getenv("MONGO_DB", "eng_conference"),
            users_collection=os.getenv("WEB_USERS_COLLECTION", "web_users"),
            registrations_collection=os.getenv("WEB_REGISTRATIONS_COLLECTION", "conference_registrations"),
            email_tasks_collection=os.getenv("WEB_EMAIL_TASKS_COLLECTION", "email_tasks"),
            password_reset_tokens_collection=os.getenv(
                "WEB_PASSWORD_RESET_TOKENS_COLLECTION",
                "password_reset_tokens",
            ),
            sessions_collection=os.getenv("WEB_SESSIONS_COLLECTION", "web_sessions"),
            session_cookie_name=os.getenv("WEB_SESSION_COOKIE_NAME", "conference_session"),
            session_ttl_hours=int(os.getenv("WEB_SESSION_TTL_HOURS", str(SESSION_TTL_HOURS_DEFAULT))),
            password_reset_ttl_minutes=max(1, int(os.getenv("WEB_PASSWORD_RESET_TTL_MINUTES", "30"))),
            checker_api_url=os.getenv("WEB_CHECKER_API_URL", "http://checker-api:8000/validate").strip(),
            checker_api_timeout_sec=max(1, int(os.getenv("WEB_CHECKER_API_TIMEOUT_SEC", "30"))),
            admin_emails=admin_emails,
        )
