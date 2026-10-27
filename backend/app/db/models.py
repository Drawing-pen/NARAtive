from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
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
    tier: Mapped[str] = mapped_column(String(10), default="free")      # free | middle | high
    role: Mapped[str] = mapped_column(String(10), default="user")      # user | admin
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    tier_expires_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)   # NULL = tidak berbatas waktu
    extra_checks: Mapped[int] = mapped_column(Integer, default=0, server_default="0")    # sisa analisis pay-per-check

    documents: Mapped[list["Document"]] = relationship(back_populates="owner")

    @property
    def paid_tier(self) -> str:
        """Tingkatan hasil pembelian; kembali ke free bila langganannya sudah berakhir."""
        if self.tier != "free" and self.tier_expires_at and self.tier_expires_at <= datetime.utcnow():
            return "free"
        return self.tier

    @property
    def access_tier(self) -> str:
        """Tingkatan yang berlaku untuk pembatasan fitur (paid_tier, atau high bila DEV_UNLOCK_ALL_TIERS menyala)."""
        return "high" if settings.dev_unlock_all_tiers else self.paid_tier


class EmailVerification(Base):
    __tablename__ = "email_verifications"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(100))
    password_hash: Mapped[str] = mapped_column(String(255))
    code_hash: Mapped[str] = mapped_column(String(64))
    expires_at: Mapped[datetime] = mapped_column(DateTime)
    attempts: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    last_sent_at: Mapped[datetime] = mapped_column(DateTime)


class SensitivityProfile(Base):
    """Ambang batas Safe Mode personal (UC-12, khusus High Tier). NULL = jenis konten itu tidak disamarkan."""
    __tablename__ = "sensitivity_profiles"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), unique=True)
    profanity: Mapped[float | None] = mapped_column(Float, nullable=True)
    sexual: Mapped[float | None] = mapped_column(Float, nullable=True)
    violence: Mapped[float | None] = mapped_column(Float, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Transaction(Base):
    """Satu pembayaran lewat Virtual Account: upgrade tingkatan atau pay-per-check (UC-07, UC-08)."""
    __tablename__ = "transactions"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    order_id: Mapped[str] = mapped_column(String(40), unique=True)
    kind: Mapped[str] = mapped_column(String(15))                          # upgrade | pay_per_check
    plan: Mapped[str | None] = mapped_column(String(10), nullable=True)    # middle | high (untuk upgrade)
    quantity: Mapped[int] = mapped_column(Integer, default=1, server_default="1")   # jumlah analisis (pay-per-check)
    amount: Mapped[int] = mapped_column(Integer)                           # rupiah
    bank: Mapped[str] = mapped_column(String(10))
    va_number: Mapped[str] = mapped_column(String(30))
    provider: Mapped[str] = mapped_column(String(12))                      # simulated | midtrans
    status: Mapped[str] = mapped_column(String(10), default="pending")     # pending | paid | failed | expired | cancelled
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    expires_at: Mapped[datetime] = mapped_column(DateTime)
    paid_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class UsageQuota(Base):
    """Pemakaian analisis per bulan; periode baru = baris baru, jadi kuota otomatis ter-reset (FR-22)."""
    __tablename__ = "usage_quota"
    __table_args__ = (UniqueConstraint("user_id", "period", name="uq_usage_user_period"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    period: Mapped[str] = mapped_column(String(7))                         # YYYY-MM
    used: Mapped[int] = mapped_column(Integer, default=0, server_default="0")


class Collection(Base):
    """Seri/koleksi buku yang saling bersambung (UC-02). Tiap buku di dalamnya tetap dokumen sendiri."""
    __tablename__ = "collections"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(150))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Document(Base):
    """Satu file e-book = satu item koleksi pengguna."""
    __tablename__ = "documents"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    collection_id: Mapped[int | None] = mapped_column(ForeignKey("collections.id", ondelete="SET NULL"), nullable=True, index=True)
    position: Mapped[int] = mapped_column(Integer, default=0, server_default="0")   # urutan dalam koleksi
    title: Mapped[str] = mapped_column(String(255))
    filename: Mapped[str] = mapped_column(String(255))
    page_count: Mapped[int] = mapped_column(Integer)
    paragraph_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    status: Mapped[str] = mapped_column(String(15), default="uploaded")  # queued | analyzing | done | failed
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
    characters_status: Mapped[str | None] = mapped_column(String(10), nullable=True) 
    cover_path: Mapped[str | None] = mapped_column(String(255), nullable=True)

    owner: Mapped["User"] = relationship(back_populates="documents")

    @property
    def has_cover(self) -> bool:
        return bool(self.cover_path)

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
    characters: Mapped[list["Character"]] = relationship(
        back_populates="document", cascade="all, delete-orphan", order_by="Character.mention_count.desc()"
    )


class Chapter(Base):
    __tablename__ = "chapters"

    id: Mapped[int] = mapped_column(primary_key=True)
    document_id: Mapped[int] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"), index=True)
    number: Mapped[int] = mapped_column(Integer)
    title: Mapped[str] = mapped_column(String(255))
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)  
    summary_source: Mapped[str | None] = mapped_column(String(10), nullable=True)    # ai | local; NULL = data lama (dianggap ai)

    document: Mapped["Document"] = relationship(back_populates="chapters")
    relations: Mapped[list["CharacterRelation"]] = relationship(back_populates="chapter", cascade="all, delete-orphan")


class Paragraph(Base):
    __tablename__ = "paragraphs"

    id: Mapped[int] = mapped_column(primary_key=True)
    document_id: Mapped[int] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"), index=True)
    idx: Mapped[int] = mapped_column(Integer)
    chapter_no: Mapped[int] = mapped_column(Integer, default=1, server_default="1")
    text: Mapped[str] = mapped_column(Text)
    profanity: Mapped[float | None] = mapped_column(Float, nullable=True) 
    sexual: Mapped[float | None] = mapped_column(Float, nullable=True)
    violence: Mapped[float | None] = mapped_column(Float, nullable=True)
    emotion: Mapped[str | None] = mapped_column(String(10), nullable=True)
    emotion_score: Mapped[float | None] = mapped_column(Float, nullable=True)

    document: Mapped["Document"] = relationship(back_populates="paragraphs")


class Character(Base):
    __tablename__ = "characters"

    id: Mapped[int] = mapped_column(primary_key=True)
    document_id: Mapped[int] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(100))
    role: Mapped[str] = mapped_column(String(50))
    biodata: Mapped[str | None] = mapped_column(Text, nullable=True)
    mention_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    photo_path: Mapped[str | None] = mapped_column(String(255), nullable=True)
    aliases: Mapped[str | None] = mapped_column(String(255), nullable=True)
    gender: Mapped[str | None] = mapped_column(String(20), nullable=True)
    age: Mapped[str | None] = mapped_column(String(100), nullable=True)
    occupation: Mapped[str | None] = mapped_column(String(300), nullable=True)
    personality: Mapped[str | None] = mapped_column(Text, nullable=True)
    background: Mapped[str | None] = mapped_column(Text, nullable=True)

    document: Mapped["Document"] = relationship(back_populates="characters")

    @property
    def has_photo(self) -> bool:
        return bool(self.photo_path)

    relations_a: Mapped[list["CharacterRelation"]] = relationship(
        back_populates="character_a", foreign_keys="CharacterRelation.character_a_id", cascade="all, delete-orphan"
    )
    relations_b: Mapped[list["CharacterRelation"]] = relationship(
        back_populates="character_b", foreign_keys="CharacterRelation.character_b_id", cascade="all, delete-orphan"
    )


class CharacterRelation(Base):
    __tablename__ = "character_relations"
    __table_args__ = (UniqueConstraint("character_a_id", "character_b_id", "chapter_id", name="uq_relation_pair_chapter"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    character_a_id: Mapped[int] = mapped_column(ForeignKey("characters.id", ondelete="CASCADE"), index=True)
    character_b_id: Mapped[int] = mapped_column(ForeignKey("characters.id", ondelete="CASCADE"), index=True)
    chapter_id: Mapped[int] = mapped_column(ForeignKey("chapters.id", ondelete="CASCADE"), index=True)
    relation_type: Mapped[str] = mapped_column(String(10))
    weight: Mapped[int] = mapped_column(Integer, default=1, server_default="1")

    character_a: Mapped["Character"] = relationship(back_populates="relations_a", foreign_keys=[character_a_id])
    character_b: Mapped["Character"] = relationship(back_populates="relations_b", foreign_keys=[character_b_id])
    chapter: Mapped["Chapter"] = relationship(back_populates="relations")