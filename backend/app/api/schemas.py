from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, EmailStr, Field, field_validator, model_validator

from app.core.plans import PAY_PER_CHECK_MAX


class RegisterIn(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    email: EmailStr
    password: str = Field(min_length=8, max_length=72)

    @field_validator("name")
    @classmethod
    def _clean_name(cls, v: str) -> str:
        v = " ".join(v.split())
        if not v:
            raise ValueError("Nama tidak boleh kosong.")
        return v

    @field_validator("password")
    @classmethod
    def _password_bytes(cls, v: str) -> str:
        if len(v.encode("utf-8")) > 72:
            raise ValueError("Kata sandi terlalu panjang.")
        return v


class VerifyIn(BaseModel):
    email: EmailStr
    code: str = Field(pattern=r"^\d{6}$")


class ResendIn(BaseModel):
    email: EmailStr


class RegistrationStarted(BaseModel):
    email: str
    expires_in: int
    resend_after: int


class LoginIn(BaseModel):
    email: str = Field(min_length=1, max_length=255)
    password: str = Field(min_length=1, max_length=200)


class UserOut(BaseModel):
    id: int
    name: str
    email: str
    tier: str = Field(validation_alias="access_tier")
    role: str

    model_config = {"from_attributes": True}


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


class DocumentOut(BaseModel):
    id: int
    title: str
    page_count: int
    status: str
    rating: str | None
    pct_profanity: float | None
    pct_sexual: float | None
    pct_violence: float | None
    dominant_emotion: str | None
    pct_adult: float | None
    heaviness: float | None
    heaviness_note: str | None
    age_range: str | None
    estimated_seconds: int | None
    created_at: datetime
    analyzed_at: datetime | None
    has_cover: bool = False

    model_config = {"from_attributes": True}


Threshold = Annotated[float, Field(ge=0.1, le=0.95)]


class SensitivityIn(BaseModel):
    """Ambang per jenis konten; null berarti jenis itu tidak disamarkan."""
    profanity: Threshold | None
    sexual: Threshold | None
    violence: Threshold | None


class SensitivityOut(BaseModel):
    editable: bool                      # hanya High Tier yang boleh mengubah
    personal: bool                      # True bila profil buatan pengguna yang sedang dipakai
    thresholds: dict[str, float | None]
    standard: dict[str, float | None]


class CheckoutIn(BaseModel):
    kind: Literal["upgrade", "pay_per_check"]
    plan: Literal["middle", "high"] | None = None          # wajib untuk upgrade
    quantity: int = Field(1, ge=1, le=PAY_PER_CHECK_MAX)   # hanya untuk pay-per-check
    bank: Literal["bca", "bni", "bri", "permata"]

    @model_validator(mode="after")
    def _check_plan(self):
        if self.kind == "upgrade" and self.plan is None:
            raise ValueError("Pilih paket yang ingin dibeli.")
        return self


class TransactionOut(BaseModel):
    order_id: str
    kind: str
    plan: str | None
    quantity: int
    amount: int
    bank: str
    va_number: str
    provider: str
    status: str
    created_at: datetime
    expires_at: datetime
    paid_at: datetime | None

    model_config = {"from_attributes": True}


class UsageOut(BaseModel):
    used: int
    monthly_limit: int | None
    extra_checks: int
    active_books: int
    max_active: int | None
    max_pages: int | None
    resets_at: datetime


class BillingOverview(BaseModel):
    tier: str                         # tingkatan yang berlaku sekarang (bisa terbuka karena mode pengembangan)
    paid_tier: str                    # tingkatan hasil pembelian
    tier_expires_at: datetime | None
    usage: UsageOut
    upgrade_prices: dict[str, int]
    period_days: int
    pay_per_check_price: int
    pay_per_check_max: int
    banks: list[str]
    provider: str                     # simulated | midtrans | unavailable


class DocumentRename(BaseModel):
    title: str = Field(min_length=1, max_length=255)

    @field_validator("title")
    @classmethod
    def _strip(cls, v: str) -> str:
        v = " ".join(v.split())
        if not v:
            raise ValueError("Judul tidak boleh kosong.")
        return v


class CollectionIn(BaseModel):
    name: str = Field(min_length=1, max_length=150)
    document_ids: list[int] = Field(min_length=2, max_length=50)    # berurutan: urutan baca

    @field_validator("name")
    @classmethod
    def _strip(cls, v: str) -> str:
        v = " ".join(v.split())
        if not v:
            raise ValueError("Nama koleksi tidak boleh kosong.")
        return v


class CollectionOut(BaseModel):
    id: int
    name: str
    document_ids: list[int]


class ChapterOut(BaseModel):
    number: int
    title: str

    model_config = {"from_attributes": True}


class ParagraphOut(BaseModel):
    idx: int
    chapter_no: int
    text: str
    profanity: float | None
    sexual: float | None
    violence: float | None
    emotion: str | None

    model_config = {"from_attributes": True}


class CharacterOut(BaseModel):
    id: int
    name: str
    role: str
    biodata: str | None
    mention_count: int
    aliases: str | None = None
    gender: str | None = None
    age: str | None = None
    occupation: str | None = None
    personality: str | None = None
    background: str | None = None
    has_photo: bool = False

    model_config = {"from_attributes": True}


class RelationOut(BaseModel):
    chapter: int
    a: int
    b: int
    type: str
    weight: int


class CharactersOut(BaseModel):
    status: str | None
    characters: list[CharacterOut]
    relations: list[RelationOut]


class ChapterSummaryOut(BaseModel):
    number: int
    title: str
    summary: str | None
    summary_source: str | None = None

    model_config = {"from_attributes": True}


class SummaryOut(BaseModel):
    status: str | None            
    done_chapters: int
    total_chapters: int
    overall: str | None
    chapters: list[ChapterSummaryOut]