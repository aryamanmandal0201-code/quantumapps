from datetime import datetime, timedelta, timezone

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError

from .config import get_settings

ALGORITHM = "HS256"

# Argon2id with argon2-cffi's defaults (the RFC 9106 low-memory profile).
_hasher = PasswordHasher()


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password: str, hashed: str) -> bool:
    """True only if the password matches. A wrong password and an unreadable stored hash
    are both treated as a failed login (never as an error that reveals which one it was)."""
    try:
        return _hasher.verify(hashed, password)
    except (VerificationError, InvalidHashError):
        return False


def create_access_token(user_id: int) -> str:
    settings = get_settings()
    now = datetime.now(timezone.utc)
    payload = {"sub": str(user_id), "iat": now, "exp": now + timedelta(minutes=settings.jwt_expire_minutes)}
    return jwt.encode(payload, settings.jwt_secret, algorithm=ALGORITHM)


def decode_access_token(token: str) -> int:
    """Returns the user id inside a valid token. Raises jwt.PyJWTError / ValueError / KeyError otherwise."""
    payload = jwt.decode(token, get_settings().jwt_secret, algorithms=[ALGORITHM])
    return int(payload["sub"])
