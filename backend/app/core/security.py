from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.database import get_db
from app.db.models import User

ALGORITHM = "HS256"
DEFAULT_EMAIL = "standard@narative.local"

bearer = HTTPBearer(auto_error=False)


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("ascii")


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("ascii"))
    except (ValueError, UnicodeEncodeError):
        return False


def create_access_token(user_id: int) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.access_token_minutes)
    return jwt.encode({"sub": str(user_id), "exp": expire}, settings.secret_key, algorithm=ALGORITHM)


def _unauthorized(detail: str) -> HTTPException:
    return HTTPException(status.HTTP_401_UNAUTHORIZED, detail, headers={"WWW-Authenticate": "Bearer"})


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
    db: Session = Depends(get_db),
) -> User:
    if credentials is None:
        raise _unauthorized("Silakan masuk terlebih dahulu.")
    try:
        payload = jwt.decode(credentials.credentials, settings.secret_key, algorithms=[ALGORITHM])
        user_id = int(payload["sub"])
    except jwt.ExpiredSignatureError:
        raise _unauthorized("Sesi berakhir. Silakan masuk lagi.")
    except (jwt.InvalidTokenError, KeyError, ValueError):
        raise _unauthorized("Sesi tidak valid. Silakan masuk lagi.")
    user = db.get(User, user_id)
    if user is None or not user.is_active:
        raise _unauthorized("Akun tidak ditemukan atau tidak aktif.")
    return user


TIER_RANK = {"free": 0, "middle": 1, "high": 2}
TIER_LABEL = {"middle": "Middle", "high": "High"}


def has_tier(user: User, minimum: str) -> bool:
    return TIER_RANK.get(user.access_tier, 0) >= TIER_RANK[minimum]


def ensure_tier(user: User, minimum: str) -> None:
    if not has_tier(user, minimum):
        raise HTTPException(status.HTTP_403_FORBIDDEN, f"Fitur ini khusus pengguna {TIER_LABEL[minimum]} Tier.")


def require_tier(minimum: str):
    """Dependency: tolak (403) pengguna yang tingkatan akunnya di bawah `minimum`."""
    def dependency(user: User = Depends(get_current_user)) -> User:
        ensure_tier(user, minimum)
        return user
    return dependency