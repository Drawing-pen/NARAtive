from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import SensitivityProfile, User
from app.ml.analyzer import THRESHOLDS

DIMENSIONS = ("profanity", "sexual", "violence")

# Safe Mode standar (UC-05) hanya menyamarkan konten seksual
STANDARD_PROFILE: dict[str, float | None] = {"profanity": None, "sexual": THRESHOLDS["sexual"], "violence": None}


def is_personalizable(user: User) -> bool:
    return user.access_tier == "high"


def get_profile(db: Session, user: User) -> SensitivityProfile | None:
    return db.scalar(select(SensitivityProfile).where(SensitivityProfile.user_id == user.id))


def effective_thresholds(db: Session, user: User) -> dict[str, float | None]:
    """Profil yang dipakai Safe Mode: milik pengguna bila High Tier dan sudah mengatur, selain itu standar."""
    profile = get_profile(db, user) if is_personalizable(user) else None
    if profile is None:
        return dict(STANDARD_PROFILE)
    return {d: getattr(profile, d) for d in DIMENSIONS}
