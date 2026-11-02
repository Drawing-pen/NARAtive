from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.db.models import Collection, EmailVerification, PasswordReset, SensitivityProfile, Transaction, UsageQuota, User
from app.services import images


def delete_account(db: Session, user: User) -> None:
    pictures = []
    for doc in list(user.documents):
        pictures.append(doc.cover_path)
        pictures.extend(c.photo_path for c in doc.characters)
        db.delete(doc)
    db.flush()
    for model in (Transaction, UsageQuota, Collection, SensitivityProfile):
        db.execute(delete(model).where(model.user_id == user.id))
    db.execute(delete(EmailVerification).where(EmailVerification.email == user.email))
    db.execute(delete(PasswordReset).where(PasswordReset.email == user.email))
    db.execute(delete(User).where(User.id == user.id))
    db.commit()
    images.remove(*pictures)
