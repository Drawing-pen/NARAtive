from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base
from app.core.config import settings
from app.ml.analyzer import AGE_RANGES


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    tier: Mapped[str] = mapped_column(String(10), default="free")      
    role: Mapped[str] = mapped_column(String(10), default="user")     
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    documents: Mapped[list["Document"]] = relationship(back_populates="owner")


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    title: Mapped[str] = mapped_column(String(255))
    filename: Mapped[str] = mapped_column(String(255))
    page_count: Mapped[int] = mapped_column(Integer)
    paragraph_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    status: Mapped[str] = mapped_column(String(15), default="uploaded")  
    rating: Mapped[str | None] = mapped_column(String(20), nullable=True)
    pct_profanity: Mapped[float | None] = mapped_column(Float, nullable=True)
    pct_sexual: Mapped[float | None] = mapped_column(Float, nullable=True)
    pct_violence: Mapped[float | None] = mapped_column(Float, nullable=True)
    dominant_emotion: Mapped[str | None] = mapped_column(String(10), nullable=True)
    pct_adult: Mapped[float | None] = mapped_column(Float, nullable=True)   
    heaviness: Mapped[float | None] = mapped_column(Float, nullable=True)   
    heaviness_ai: Mapped[float | None] = mapped_column(Float, nullable=True)
    heaviness_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    analyzed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)                 
    summary_status: Mapped[str | None] = mapped_column(String(10), nullable=True)    

    owner: Mapped["User"] = relationship(back_populates="documents")

    @property
    def age_range(self) -> str | None:
        return AGE_RANGES.get(self.rating)

    @property
    def estimated_seconds(self) -> int | None:
        """Perkiraan sisa waktu analisis (UC-03: estimasi waktu selesai). Kasar, bukan jaminan."""
        if self.status not in ("queued", "analyzing"):
            return None
        return max(5, round(self.paragraph_count * settings.seconds_per_paragraph))
    paragraphs: Mapped[list["Paragraph"]] = relationship(
        back_populates="document", cascade="all, delete-orphan", order_by="Paragraph.idx"
    )
    chapters: Mapped[list["Chapter"]] = relationship(
        back_populates="document", cascade="all, delete-orphan", order_by="Chapter.number"
    )


class Chapter(Base):
    __tablename__ = "chapters"

    id: Mapped[int] = mapped_column(primary_key=True)
    document_id: Mapped[int] = mapped_column(ForeignKey("documents.id"), index=True)
    number: Mapped[int] = mapped_column(Integer)
    title: Mapped[str] = mapped_column(String(255))
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)   

    document: Mapped["Document"] = relationship(back_populates="chapters")


class Paragraph(Base):
    __tablename__ = "paragraphs"

    id: Mapped[int] = mapped_column(primary_key=True)
    document_id: Mapped[int] = mapped_column(ForeignKey("documents.id"), index=True)
    idx: Mapped[int] = mapped_column(Integer)
    chapter_no: Mapped[int] = mapped_column(Integer, default=1, server_default="1")
    text: Mapped[str] = mapped_column(Text)
    profanity: Mapped[float | None] = mapped_column(Float, nullable=True)  # skor 0..1
    sexual: Mapped[float | None] = mapped_column(Float, nullable=True)
    violence: Mapped[float | None] = mapped_column(Float, nullable=True)
    emotion: Mapped[str | None] = mapped_column(String(10), nullable=True)
    emotion_score: Mapped[float | None] = mapped_column(Float, nullable=True)

    document: Mapped["Document"] = relationship(back_populates="paragraphs")