from hashlib import pbkdf2_hmac
import base64
import secrets
from typing import Any


PASSWORD_HASH_ITERATIONS = 200_000


def hash_password(password: str) -> dict[str, Any]:
    salt = secrets.token_bytes(16)
    digest = pbkdf2_hmac("sha256", password.encode("utf-8"), salt, PASSWORD_HASH_ITERATIONS)
    return {
        "password_salt": base64.b64encode(salt).decode("ascii"),
        "password_hash": base64.b64encode(digest).decode("ascii"),
        "password_iterations": PASSWORD_HASH_ITERATIONS,
    }


def verify_password(password: str, user: dict[str, Any]) -> bool:
    try:
        salt = base64.b64decode(user["password_salt"])
        expected_hash = base64.b64decode(user["password_hash"])
        iterations = int(user.get("password_iterations", PASSWORD_HASH_ITERATIONS))
    except (KeyError, ValueError, TypeError):
        return False

    actual_hash = pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
    return secrets.compare_digest(actual_hash, expected_hash)
