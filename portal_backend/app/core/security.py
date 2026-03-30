from datetime import UTC, datetime, timedelta
from uuid import uuid4

import jwt
from fastapi import HTTPException, status
from passlib.context import CryptContext

from app.core.config import get_settings

pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")
settings = get_settings()


class TokenType:
    ACCESS = "access"
    REFRESH = "refresh"
    ACTIVATION = "activation"
    PASSWORD_RESET = "password_reset"


class TokenError(HTTPException):
    def __init__(self, detail: str = "Invalid token") -> None:
        super().__init__(status_code=status.HTTP_401_UNAUTHORIZED, detail=detail)


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(password: str, password_hash: str | None) -> bool:
    if not password_hash:
        return False
    return pwd_context.verify(password, password_hash)


def _build_token(
    *,
    subject: str,
    token_type: str,
    expires_delta: timedelta,
    extra: dict | None = None,
) -> tuple[str, str, datetime]:
    now = datetime.now(UTC)
    expires_at = now + expires_delta
    jti = str(uuid4())
    payload = {
        "sub": subject,
        "type": token_type,
        "jti": jti,
        "iat": int(now.timestamp()),
        "exp": int(expires_at.timestamp()),
    }
    if extra:
        payload.update(extra)
    token = jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
    return token, jti, expires_at


def create_access_token(*, user_id: int, email: str, role: str) -> tuple[str, str, datetime]:
    return _build_token(
        subject=str(user_id),
        token_type=TokenType.ACCESS,
        expires_delta=timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
        extra={"email": email, "role": role},
    )


def create_refresh_token(*, user_id: int, email: str, role: str) -> tuple[str, str, datetime]:
    return _build_token(
        subject=str(user_id),
        token_type=TokenType.REFRESH,
        expires_delta=timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
        extra={"email": email, "role": role},
    )


def create_activation_token(*, user_id: int, email: str) -> tuple[str, str, datetime]:
    return _build_token(
        subject=str(user_id),
        token_type=TokenType.ACTIVATION,
        expires_delta=timedelta(hours=settings.ACTIVATION_TOKEN_EXPIRE_HOURS),
        extra={"email": email},
    )


def create_password_reset_token(*, user_id: int, email: str) -> tuple[str, str, datetime]:
    return _build_token(
        subject=str(user_id),
        token_type=TokenType.PASSWORD_RESET,
        expires_delta=timedelta(hours=settings.PASSWORD_RESET_TOKEN_EXPIRE_HOURS),
        extra={"email": email},
    )


def decode_token(token: str, *, expected_type: str | None = None) -> dict:
    try:
        payload = jwt.decode(
            token,
            settings.JWT_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM],
        )
    except jwt.ExpiredSignatureError as exc:
        raise TokenError("Token has expired") from exc
    except jwt.PyJWTError as exc:
        raise TokenError() from exc

    if expected_type and payload.get("type") != expected_type:
        raise TokenError("Invalid token type")

    return payload
