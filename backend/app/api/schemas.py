from datetime import datetime

from pydantic import BaseModel, EmailStr, Field, field_validator


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


class LoginIn(BaseModel):
    email: str = Field(min_length=1, max_length=255)
    password: str = Field(min_length=1, max_length=200)


class UserOut(BaseModel):
    id: int
    name: str
    email: str

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

    model_config = {"from_attributes": True}


class DocumentRename(BaseModel):
    title: str = Field(min_length=1, max_length=255)

    @field_validator("title")
    @classmethod
    def _strip(cls, v: str) -> str:
        v = " ".join(v.split())
        if not v:
            raise ValueError("Judul tidak boleh kosong.")
        return v


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

    model_config = {"from_attributes": True}


class SummaryOut(BaseModel):
    status: str | None            
    done_chapters: int
    total_chapters: int
    overall: str | None
    chapters: list[ChapterSummaryOut]