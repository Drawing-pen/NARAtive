from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.schemas import SensitivityIn, SensitivityOut
from app.core.security import get_current_user, require_tier
from app.db.database import get_db
from app.db.models import SensitivityProfile, User
from app.services import sensitivity as service

router = APIRouter(prefix="/sensitivity", tags=["sensitivity"])


def _out(db: Session, user: User) -> SensitivityOut:
    return SensitivityOut(
        editable=service.is_personalizable(user),
        personal=service.is_personalizable(user) and service.get_profile(db, user) is not None,
        thresholds=service.effective_thresholds(db, user),
        standard=service.STANDARD_PROFILE,
    )


@router.get("", response_model=SensitivityOut)
def get_sensitivity(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return _out(db, user)


@router.put("", response_model=SensitivityOut)
def save_sensitivity(body: SensitivityIn, user: User = Depends(require_tier("high")), db: Session = Depends(get_db)):
    profile = service.get_profile(db, user)
    if profile is None:
        profile = SensitivityProfile(user_id=user.id)
        db.add(profile)
    for dim in service.DIMENSIONS:
        setattr(profile, dim, getattr(body, dim))
    db.commit()
    return _out(db, user)


@router.delete("", response_model=SensitivityOut)
def reset_sensitivity(user: User = Depends(require_tier("high")), db: Session = Depends(get_db)):
    profile = service.get_profile(db, user)
    if profile is not None:
        db.delete(profile)
        db.commit()
    return _out(db, user)
