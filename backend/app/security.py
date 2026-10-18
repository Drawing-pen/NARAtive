from fastapi import Depends
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .database import SessionLocal, get_db
from .models import User

DEFAULT_EMAIL = "standard@narative.local"


def _get_or_create_default(db: Session) -> User:
    user = db.scalar(select(User).where(User.email == DEFAULT_EMAIL))
    if user is None:
        user = User(name="Standard User", email=DEFAULT_EMAIL, password_hash="-", tier="free", role="user")
        db.add(user)
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            user = db.scalar(select(User).where(User.email == DEFAULT_EMAIL))
    return user


def ensure_default_user() -> None:
    with SessionLocal() as db:
        _get_or_create_default(db)


def get_current_user(db: Session = Depends(get_db)) -> User:
    return _get_or_create_default(db)