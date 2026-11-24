import json

import pytest

from app.db import models
from app.services import heaviness, jobs, llm_analyzer
from app.services.summarizer import SummaryError


@pytest.fixture
def doc(make_user, make_doc):
    return make_doc(make_user("free"))


def scene_on_second(prompt, **kwargs):
    return json.dumps({"adegan": [{"dari": 2, "sampai": 2, "jenis": "kekerasan", "tingkat": 3}]})


@pytest.fixture(autouse=True)
def no_gemini_heaviness(monkeypatch):
    monkeypatch.setattr(jobs, "configured", lambda: False)


def reload(db, doc_id):
    db.expire_all()
    return db.get(models.Document, doc_id)


class TestProcess:
    def test_scenes_become_paragraph_scores_and_the_book_finishes(self, db, doc, monkeypatch):
        monkeypatch.setattr(llm_analyzer, "_generate", scene_on_second)
        jobs.process(doc.id)
        done = reload(db, doc.id)
        assert done.status == "done" and done.analyzed_at is not None
        assert [p.violence for p in done.paragraphs] == [0.0, 0.95]
        assert done.pct_violence == 50.0 and done.rating == "General"

    def test_no_emotion_is_stored_any_more(self, db, doc, monkeypatch):
        monkeypatch.setattr(llm_analyzer, "_generate", scene_on_second)
        jobs.process(doc.id)
        done = reload(db, doc.id)
        assert done.dominant_emotion is None
        assert all(p.emotion is None and p.emotion_score is None for p in done.paragraphs)

    def test_heaviness_falls_back_to_the_violence_share_without_the_llm_rating(self, db, doc, monkeypatch):
        monkeypatch.setattr(llm_analyzer, "_generate", scene_on_second)
        jobs.process(doc.id)
        done = reload(db, doc.id)
        assert done.heaviness_ai is None and done.heaviness == 50.0

    def test_the_llm_heaviness_rating_is_used_when_available(self, db, doc, monkeypatch):
        monkeypatch.setattr(llm_analyzer, "_generate", scene_on_second)
        monkeypatch.setattr(jobs, "configured", lambda: True)
        monkeypatch.setattr(heaviness, "rate_document", lambda d: (40.0, "catatan"))
        jobs.process(doc.id)
        done = reload(db, doc.id)
        assert done.heaviness_ai == 40.0 and done.heaviness == 40.0

    def test_a_failed_heaviness_rating_does_not_fail_the_book(self, db, doc, monkeypatch):
        monkeypatch.setattr(llm_analyzer, "_generate", scene_on_second)
        monkeypatch.setattr(jobs, "configured", lambda: True)

        def broken(d):
            raise SummaryError("mati")

        monkeypatch.setattr(heaviness, "rate_document", broken)
        jobs.process(doc.id)
        done = reload(db, doc.id)
        assert done.status == "done" and done.heaviness == 50.0

    def test_when_the_llm_is_unreachable_the_book_fails_with_a_friendly_reason(self, db, doc, monkeypatch):
        monkeypatch.setattr(llm_analyzer, "RETRY_WAIT", 0)

        def down(*a, **k):
            raise SummaryError("koneksi mati")

        monkeypatch.setattr(llm_analyzer, "_generate", down)
        jobs.process(doc.id)
        failed = reload(db, doc.id)
        assert failed.status == "failed"
        assert "Layanan AI belum bisa dihubungi" in failed.failure_reason
        assert "koneksi mati" not in failed.failure_reason
