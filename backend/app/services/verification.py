import hashlib
import hmac
import secrets
from datetime import datetime, timedelta

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import hash_password
from app.db.models import EmailVerification, User
from app.services import mailer

CODE_TTL = timedelta(minutes=10)
RESEND_COOLDOWN = timedelta(seconds=60)
MAX_ATTEMPTS = 5

EMAIL_TAKEN = "Email sudah terdaftar. Silakan masuk."
NOT_FOUND = "Pendaftaran tidak ditemukan. Mulai pendaftaran lagi."
TOO_SOON = "Tunggu sebentar sebelum meminta kode baru."
WRONG_CODE = "Kode verifikasi salah."
EXPIRED = "Kode verifikasi sudah kedaluwarsa. Kirim ulang kode."
TOO_MANY = "Terlalu banyak percobaan. Mulai pendaftaran lagi."


def _digest(email: str, code: str) -> str:
    return hmac.new(settings.secret_key.encode("utf-8"), f"{email}:{code}".encode("utf-8"), hashlib.sha256).hexdigest()


def _new_code() -> str:
    return f"{secrets.randbelow(10**6):06d}"


def _user_exists(db: Session, email: str) -> bool:
    return db.scalar(select(User.id).where(User.email == email)) is not None


def _pending(db: Session, email: str) -> EmailVerification | None:
    return db.scalar(select(EmailVerification).where(EmailVerification.email == email))


def _ensure_cooldown_passed(pending: EmailVerification | None) -> None:
    if pending is not None and datetime.utcnow() - pending.last_sent_at < RESEND_COOLDOWN:
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, TOO_SOON)


def _issue(db: Session, pending: EmailVerification) -> None:
    code = _new_code()
    now = datetime.utcnow()
    pending.code_hash = _digest(pending.email, code)
    pending.expires_at = now + CODE_TTL
    pending.attempts = 0
    pending.last_sent_at = now
    db.commit()
    minutes = int(CODE_TTL.total_seconds() // 60)
    mailer.send(
        pending.email,
        "Kode verifikasi NARAtive",
        f"Halo {pending.name},\n\nKode verifikasi NARAtive kamu: {code}\n"
        f"Kode berlaku {minutes} menit. Jika bukan kamu yang mendaftar, abaikan email ini.\n\nSalam,\nNARAtive",
    )


def start(db: Session, name: str, email: str, password: str) -> EmailVerification:
    if _user_exists(db, email):
        raise HTTPException(status.HTTP_409_CONFLICT, EMAIL_TAKEN)
    pending = _pending(db, email)
    _ensure_cooldown_passed(pending)
    if pending is None:
        pending = EmailVerification(email=email)
        db.add(pending)
    pending.name = name
    pending.password_hash = hash_password(password)
    _issue(db, pending)
    return pending


def resend(db: Session, email: str) -> EmailVerification:
    pending = _pending(db, email)
    if pending is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, NOT_FOUND)
    if _user_exists(db, email):
        db.delete(pending)
        db.commit()
        raise HTTPException(status.HTTP_409_CONFLICT, EMAIL_TAKEN)
    _ensure_cooldown_passed(pending)
    _issue(db, pending)
    return pending


def verify(db: Session, email: str, code: str) -> User:
    pending = _pending(db, email)
    if pending is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, NOT_FOUND)
    if _user_exists(db, email):
        db.delete(pending)
        db.commit()
        raise HTTPException(status.HTTP_409_CONFLICT, EMAIL_TAKEN)
    if datetime.utcnow() > pending.expires_at:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, EXPIRED)
    if not hmac.compare_digest(pending.code_hash, _digest(email, code)):
        pending.attempts += 1
        if pending.attempts >= MAX_ATTEMPTS:
            db.delete(pending)
            db.commit()
            raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, TOO_MANY)
        db.commit()
        raise HTTPException(status.HTTP_400_BAD_REQUEST, WRONG_CODE)
    user = User(name=pending.name, email=email, password_hash=pending.password_hash, tier="free", role="user")
    db.add(user)
    db.delete(pending)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, EMAIL_TAKEN)
    return user
