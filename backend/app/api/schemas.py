from datetime import datetime

from pydantic import BaseModel, Field, field_validator


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