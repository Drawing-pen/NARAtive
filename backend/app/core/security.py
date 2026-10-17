"""Sementara: belum ada login. Semua permintaan diperlakukan sebagai satu Standard User (Free).

Tahap login/registrasi nanti mengganti isi get_current_user dengan verifikasi token.
Semua router sudah memakai get_current_user, jadi router tidak perlu diubah.
"""
from fastapi import Depends
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.database import SessionLocal, get_db
from app.db.models import User

DEFAULT_EMAIL = "standard@narative.local"


def _get_or_create_default(db: Session) -> User:
    user = db.scalar(select(User).where(User.email == DEFAULT_EMAIL))
    if user is None:
        user = User(name="Standard User", email=DEFAULT_EMAIL, password_hash="-", tier="free", role="user")
        db.add(user)
        try:
            db.commit()
        except IntegrityError:
            # Dua permintaan pertama datang bersamaan: yang lain sudah membuatnya.
            db.rollback()
            user = db.scalar(select(User).where(User.email == DEFAULT_EMAIL))
    return user


def ensure_default_user() -> None:
    """Dipanggil saat server menyala supaya permintaan pertama tidak saling berebut membuat user."""
    with SessionLocal() as db:
        _get_or_create_default(db)


def get_current_user(db: Session = Depends(get_db)) -> User:
    return _get_or_create_default(db)