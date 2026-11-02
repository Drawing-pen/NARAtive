import hmac
from datetime import datetime

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.db.models import PasswordReset, User
from app.services import email_templates, mailer
from app.services.verification import CODE_TTL, MAX_ATTEMPTS, RESEND_COOLDOWN, _digest, _new_code

REFUSED = "Kode salah atau sudah kedaluwarsa. Minta kode baru."
TOO_MANY = "Terlalu banyak percobaan. Minta kode baru."


def _user(db: Session, email: str) -> User | None:
    user = db.scalar(select(User).where(User.email == email))
    return user if user is not None and user.is_active else None


def _record(db: Session, email: str) -> PasswordReset | None:
    return db.scalar(select(PasswordReset).where(PasswordReset.email == email))


def start(db: Session, email: str) -> None:
    user = _user(db, email)
    if user is None:
        return
    row = _record(db, email)
    now = datetime.utcnow()
    if row is not None and now - row.last_sent_at < RESEND_COOLDOWN:
        return
    if row is None:
        row = PasswordReset(email=email)
        db.add(row)
    code = _new_code()
    row.code_hash = _digest(email, code)
    row.expires_at = now + CODE_TTL
    row.attempts = 0
    row.last_sent_at = now
    db.commit()
    mail = email_templates.password_reset_email(user.name, code, int(CODE_TTL.total_seconds() // 60))
    mailer.send(email, mail.subject, mail.text, mail.html)


def reset(db: Session, email: str, code: str, new_password: str) -> User:
    row = _record(db, email)
    user = _user(db, email)
    if row is None or user is None or datetime.utcnow() > row.expires_at:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, REFUSED)
    if not hmac.compare_digest(row.code_hash, _digest(email, code)):
        row.attempts += 1
        if row.attempts >= MAX_ATTEMPTS:
            db.delete(row)
            db.commit()
            raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, TOO_MANY)
        db.commit()
        raise HTTPException(status.HTTP_400_BAD_REQUEST, REFUSED)
    user.password_hash = hash_password(new_password)
    db.delete(row)
    db.commit()
    return user
