import pytest
from sqlalchemy import create_engine, event, func, select, text
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.db import models
from app.db.database import Base

OWNED = {"users", "documents"}


def foreign_keys():
    for table in Base.metadata.tables.values():
        for fk in table.foreign_keys:
            if fk.column.table.name in OWNED:
                yield table.name, fk


@pytest.mark.parametrize("table,fk", list(foreign_keys()), ids=lambda v: v if isinstance(v, str) else v.parent.name)
def test_every_row_that_belongs_to_a_user_or_a_book_is_removed_with_it(table, fk):
    assert fk.ondelete == "CASCADE"


@pytest.fixture
def strict_session():
    engine = create_engine("sqlite://", poolclass=StaticPool, connect_args={"check_same_thread": False})
    event.listen(engine, "connect", lambda conn, _: conn.execute("PRAGMA foreign_keys=ON"))
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


def populate(session):
    user = models.User(name="Uji", email="uji@example.com", password_hash="x", tier="free", role="user")
    session.add(user)
    session.flush()
    doc = models.Document(
        user_id=user.id, title="Buku", filename="b.pdf", page_count=1, paragraph_count=1, status="done", rating="General",
        pct_sexual=0.0, pct_violence=0.0, pct_profanity=0.0, pct_adult=0.0, heaviness=1.0, dominant_emotion="sad",
    )
    doc.chapters = [models.Chapter(number=1, title="Bab 1")]
    doc.paragraphs = [models.Paragraph(idx=0, chapter_no=1, text="Teks.")]
    doc.characters = [models.Character(name="Budi", role="Tokoh utama", mention_count=3)]
    session.add(doc)
    session.commit()


def test_deleting_a_user_row_directly_removes_everything_they_own(strict_session):
    populate(strict_session)
    strict_session.execute(text("DELETE FROM users"))
    strict_session.commit()
    for model in (models.Document, models.Chapter, models.Paragraph, models.Character):
        assert strict_session.scalar(select(func.count()).select_from(model)) == 0


def test_deleting_a_book_row_directly_removes_its_chapters_and_paragraphs(strict_session):
    populate(strict_session)
    strict_session.execute(text("DELETE FROM documents"))
    strict_session.commit()
    for model in (models.Chapter, models.Paragraph, models.Character):
        assert strict_session.scalar(select(func.count()).select_from(model)) == 0
    assert strict_session.scalar(select(func.count()).select_from(models.User)) == 1
