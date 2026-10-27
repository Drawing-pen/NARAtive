import os
import tempfile

_db_file = os.path.join(tempfile.mkdtemp(prefix="narative-test-"), "test.db")
os.environ["DATABASE_URL"] = f"sqlite:///{_db_file}"
os.environ["SECRET_KEY"] = "kunci-uji-minimal-32-karakter-aaaaaaaa"
os.environ["GEMINI_API_KEY"] = ""
os.environ["SMTP_HOST"] = ""
os.environ["MIDTRANS_SERVER_KEY"] = ""
os.environ["DEV_UNLOCK_ALL_TIERS"] = "false"

import re
from datetime import datetime

import pytest
from fastapi.testclient import TestClient

from app.core.security import create_access_token, hash_password
from app.db import models
from app.db.database import Base, SessionLocal, engine
from app.main import app
from app.services import mailer


@pytest.fixture(autouse=True)
def fresh_database():
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    yield


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def db():
    with SessionLocal() as session:
        yield session


@pytest.fixture
def outbox(monkeypatch):
    sent = []
    monkeypatch.setattr(mailer, "send", lambda to, subject, body: sent.append({"to": to, "subject": subject, "body": body}))
    return sent


def code_from(mail: dict) -> str:
    found = re.search(r"(?<!\d)(\d{6})(?!\d)", mail["body"])
    assert found, "email tidak memuat kode 6 angka"
    return found.group(1)


@pytest.fixture
def make_user(db):
    counter = {"n": 0}

    def make(tier="free", expires_at=None, email=None, extra_checks=0):
        counter["n"] += 1
        user = models.User(
            name=f"Pengguna {counter['n']}",
            email=email or f"user{counter['n']}@example.com",
            password_hash=hash_password("sandi-uji-123"),
            tier=tier,
            role="user",
            tier_expires_at=expires_at,
            extra_checks=extra_checks,
        )
        db.add(user)
        db.commit()
        return user

    return make


@pytest.fixture
def auth():
    return lambda user: {"Authorization": f"Bearer {create_access_token(user.id)}"}


@pytest.fixture
def make_doc(db):
    def make(owner, status="done", summary=None, characters=None, title="Buku Uji"):
        doc = models.Document(
            user_id=owner.id, title=title, filename=f"{title}.pdf", page_count=10, paragraph_count=2,
            status=status, rating="General", pct_sexual=0.0, pct_violence=0.0, pct_profanity=0.0,
            pct_adult=0.0, heaviness=10.0, dominant_emotion="sad",
            analyzed_at=datetime.utcnow() if status == "done" else None,
        )
        doc.chapters = [models.Chapter(number=1, title="Bab 1")]
        doc.paragraphs = [
            models.Paragraph(idx=0, chapter_no=1, text="Paragraf pertama.", profanity=0.0, sexual=0.0, violence=0.0, emotion="sad", emotion_score=0.5),
            models.Paragraph(idx=1, chapter_no=1, text="Paragraf kedua.", profanity=0.0, sexual=0.0, violence=0.0, emotion="happy", emotion_score=0.5),
        ]
        if summary:
            doc.summary, doc.summary_status = summary, "done"
            doc.chapters[0].summary = "Ringkasan bab satu."
        if characters:
            doc.characters_status = "done"
            doc.characters = [models.Character(name=n, role="Tokoh utama", biodata="Biodata.", mention_count=5) for n in characters]
        db.add(doc)
        db.commit()
        return doc

    return make
