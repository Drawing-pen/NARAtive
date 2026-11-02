from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.schemas import (
    AccountDelete, LoginIn, PasswordChange, ProfileUpdate, RegisterIn, RegistrationStarted, ResendIn, ResetIn, TokenOut, UserOut, VerifyIn,
)
from app.core.security import create_access_token, get_current_user, hash_password, verify_password
from app.db.database import get_db
from app.db.models import User
from app.services import accounts, password_reset, verification

router = APIRouter(prefix="/auth", tags=["auth"])

WRONG_LOGIN = "Email atau kata sandi salah."


def _token_for(user: User) -> TokenOut:
    return TokenOut(access_token=create_access_token(user.id), user=UserOut.model_validate(user))


def _started(email: str) -> RegistrationStarted:
    return RegistrationStarted(
        email=email,
        expires_in=int(verification.CODE_TTL.total_seconds()),
        resend_after=int(verification.RESEND_COOLDOWN.total_seconds()),
    )


@router.post("/register", response_model=RegistrationStarted, status_code=status.HTTP_202_ACCEPTED)
def register(body: RegisterIn, db: Session = Depends(get_db)):
    pending = verification.start(db, body.name, body.email.lower(), body.password)
    return _started(pending.email)


@router.post("/register/resend", response_model=RegistrationStarted, status_code=status.HTTP_202_ACCEPTED)
def resend_code(body: ResendIn, db: Session = Depends(get_db)):
    pending = verification.resend(db, body.email.lower())
    return _started(pending.email)


@router.post("/register/verify", response_model=TokenOut, status_code=status.HTTP_201_CREATED)
def verify_registration(body: VerifyIn, db: Session = Depends(get_db)):
    return _token_for(verification.verify(db, body.email.lower(), body.code))


@router.post("/password/forgot", response_model=RegistrationStarted, status_code=status.HTTP_202_ACCEPTED)
def forgot_password(body: ResendIn, db: Session = Depends(get_db)):
    email = body.email.lower()
    password_reset.start(db, email)
    return _started(email)


@router.post("/password/reset", response_model=TokenOut)
def reset_password(body: ResetIn, db: Session = Depends(get_db)):
    return _token_for(password_reset.reset(db, body.email.lower(), body.code, body.new_password))


@router.post("/login", response_model=TokenOut)
def login(body: LoginIn, db: Session = Depends(get_db)):
    user = db.scalar(select(User).where(User.email == body.email.lower()))
    if user is None or not verify_password(body.password, user.password_hash):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, WRONG_LOGIN)
    if not user.is_active:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Akun tidak aktif.")
    return _token_for(user)


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)):
    return user


@router.patch("/me", response_model=UserOut)
def rename(body: ProfileUpdate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    user.name = body.name
    db.commit()
    return user


@router.put("/me/password", status_code=status.HTTP_204_NO_CONTENT)
def change_password(body: PasswordChange, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if not verify_password(body.current_password, user.password_hash):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Kata sandi lama salah.")
    if body.new_password == body.current_password:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Kata sandi baru harus berbeda dari yang lama.")
    user.password_hash = hash_password(body.new_password)
    db.commit()


@router.delete("/me", status_code=status.HTTP_204_NO_CONTENT)
def delete_me(body: AccountDelete, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if not verify_password(body.password, user.password_hash):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Kata sandi salah.")
    accounts.delete_account(db, user)
