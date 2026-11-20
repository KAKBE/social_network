import hashlib
import hmac
import re
import secrets

_PASSWORD = re.compile(r"^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[^A-Za-z0-9]).{12,128}$")
LOGIN_PATTERN = re.compile(r"^[A-Za-z0-9_]{3,50}$")


def password_is_strong(password: str) -> bool:
    return _PASSWORD.fullmatch(password) is not None

_ITERATIONS = 200_000


def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), _ITERATIONS)
    return f"{salt}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    salt, expected = stored.split("$", 1)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), _ITERATIONS)
    return hmac.compare_digest(digest.hex(), expected)


def new_token() -> str:
    return secrets.token_urlsafe(32)
