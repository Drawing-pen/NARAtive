import json

import pytest

from app.core.config import settings
from app.db import models
from app.services import admin_stats, billing, doc_type
from app.services.summarizer import SafetyBlock, SummaryError
from tests.builders import prose
from tests.test_upload_endpoint import EPUB, environment, leftovers, queued, story_epub, story_pdf, upload, user  # noqa: F401


def answer(kind):
    return lambda prompt, **kwargs: json.dumps({"jenis": kind, "alasan": "contoh"})


@pytest.fixture
def llm(monkeypatch):
    calls = []

    def fake(prompt, **kwargs):
        calls.append({"prompt": prompt, **kwargs})
        return fake.reply(prompt, **kwargs)

    fake.reply = answer("cerita")
    fake.calls = calls
    monkeypatch.setattr(doc_type, "_generate", fake)
    monkeypatch.setattr(doc_type, "configured", lambda: True)
    return fake


class TestSample:
    def test_a_short_document_is_sent_whole(self):
        texts = ["Satu.", "Dua.", "Tiga."]
        assert doc_type.sample(texts) == "Satu.\n\nDua.\n\nTiga."

    def test_a_long_document_gives_the_start_the_middle_and_the_end(self):
        texts = [f"p{i:03d} " + "x" * 100 for i in range(200)]
        out = doc_type.sample(texts)
        assert "p000" in out and "p100" in out and "p199" in out
        assert "p050" not in out and "p150" not in out

    def test_the_sample_stays_within_the_limit(self):
        texts = [f"p{i} " + "x" * 500 for i in range(300)]
        assert len(doc_type.sample(texts)) <= 3 * doc_type.CHARS_PER_SEGMENT + 50

    def test_explicit_words_are_redacted_before_sending(self, monkeypatch):
        monkeypatch.setattr(doc_type, "sexual_lexicon_score", lambda text: 0.9 if "RAHASIA" in text else 0.0)
        monkeypatch.setattr(doc_type, "redact_terms", lambda text, score: "[disamarkan]" if score >= 0.8 else text)
        out = doc_type.sample(["Aman.", "RAHASIA intim.", "Aman lagi."])
        assert "RAHASIA" not in out and "[disamarkan]" in out


class TestClassify:
    def test_a_story_is_a_novel(self, llm):
        assert doc_type.classify([prose(3)]) == "novel"

    def test_a_non_story_is_other(self, llm):
        llm.reply = answer("bukan_cerita")
        assert doc_type.classify([prose(3)]) == "other"

    def test_one_call_with_the_sample_zero_temperature_and_a_schema(self, llm):
        doc_type.classify([prose(3), prose(2, 4)])
        [call] = llm.calls
        assert call["temperature"] == 0.0 and call["schema"] is not None and call["purpose"] == "jenis dokumen"
        assert "Rana berjalan" in call["prompt"] and "2" in call["prompt"]

    def test_the_text_is_marked_as_data_not_instructions(self, llm):
        doc_type.classify([prose(1)])
        assert "DATA" in llm.calls[0]["system"] and "perintah" in llm.calls[0]["system"].lower()

    @pytest.mark.parametrize("error", [SummaryError("mati"), SafetyBlock("ditahan")])
    def test_a_failing_service_means_novel(self, llm, error):
        def boom(prompt, **kwargs):
            raise error

        llm.reply = boom
        assert doc_type.classify([prose(3)]) == "novel"

    @pytest.mark.parametrize("raw", ["bukan json", "[]", "null", json.dumps({"jenis": "entah"}), json.dumps({}), json.dumps({"jenis": None})])
    def test_an_unreadable_or_unknown_answer_means_novel(self, llm, raw):
        llm.reply = lambda prompt, **kwargs: raw
        assert doc_type.classify([prose(3)]) == "novel"

    def test_a_disabled_check_makes_no_call(self, llm, monkeypatch):
        monkeypatch.setattr(settings, "document_type_check", False)
        llm.reply = answer("bukan_cerita")
        assert doc_type.classify([prose(3)]) == "novel" and llm.calls == []

    def test_without_a_configured_ai_there_is_no_call(self, llm, monkeypatch):
        monkeypatch.setattr(doc_type, "configured", lambda: False)
        llm.reply = answer("bukan_cerita")
        assert doc_type.classify([prose(3)]) == "novel" and llm.calls == []

    @pytest.mark.parametrize("texts", [[], [""], ["   ", "\n"]])
    def test_nothing_to_check_means_novel_without_a_call(self, llm, texts):
        assert doc_type.classify(texts) == "novel" and llm.calls == []

    def test_the_default_setting_is_on(self):
        assert settings.document_type_check is True


@pytest.fixture
def other(monkeypatch):
    seen = []

    def classify(texts):
        seen.append(list(texts))
        return "other"

    monkeypatch.setattr(doc_type, "classify", classify)
    return seen


def used(db, user):
    db.expire_all()
    row = db.query(models.UsageQuota).filter_by(user_id=user.id).first()
    return row.used if row else 0


class TestUpload:
    def test_an_epub_that_is_not_a_novel_is_stored_without_text_or_quota(self, client, db, auth, user, queued, other, tmp_path):
        res = upload(client, auth, user, story_epub(), "Artikel.epub", EPUB)
        assert res.status_code == 201
        body = res.json()
        assert body["status"] == "not_novel" and body["rating"] is None and body["progress"] is None and body["failure_reason"] is None
        db.expire_all()
        doc = db.get(models.Document, body["id"])
        assert doc.paragraph_count == 0 and doc.paragraphs == [] and doc.chapters == []
        assert used(db, user) == 0 and queued == [] and leftovers(tmp_path) == []

    def test_the_texts_given_to_the_check_are_the_paragraphs_of_the_book(self, client, auth, user, other):
        upload(client, auth, user, story_epub(), "Artikel.epub", EPUB)
        [texts] = other
        assert any("Rana berjalan" in t for t in texts)

    def test_a_pdf_that_is_not_a_novel_ends_as_not_novel_without_text_or_quota(self, client, db, auth, user, queued, other, tmp_path):
        res = upload(client, auth, user, story_pdf(), "Makalah.pdf")
        doc_id = res.json()["id"]
        db.expire_all()
        doc = db.get(models.Document, doc_id)
        assert doc.status == "not_novel" and doc.failure_reason is None and doc.read_pages == doc.page_count
        assert doc.paragraphs == [] and doc.chapters == [] and doc.paragraph_count == 0
        assert used(db, user) == 0 and queued == [] and leftovers(tmp_path) == []

    def test_a_novel_is_still_queued_and_uses_the_quota(self, client, db, auth, user, queued, monkeypatch):
        monkeypatch.setattr(doc_type, "classify", lambda texts: "novel")
        body = upload(client, auth, user, story_epub(), "Novel.epub", EPUB).json()
        assert body["status"] == "queued" and queued == [body["id"]] and used(db, user) == 1

    def test_a_pdf_novel_is_still_queued_and_uses_the_quota(self, client, db, auth, user, queued, monkeypatch):
        monkeypatch.setattr(doc_type, "classify", lambda texts: "novel")
        doc_id = upload(client, auth, user, story_pdf()).json()["id"]
        db.expire_all()
        assert db.get(models.Document, doc_id).status == "queued" and queued == [doc_id] and used(db, user) == 1

    def test_the_remaining_quota_is_unchanged_after_a_non_novel(self, client, db, auth, user, other):
        before = billing.remaining_analyses(db, user)
        upload(client, auth, user, story_epub(), "Artikel.epub", EPUB)
        db.expire_all()
        assert billing.remaining_analyses(db, user) == before

    def test_it_is_listed_with_its_status_and_no_rating(self, client, auth, user, other):
        upload(client, auth, user, story_epub(), "Artikel.epub", EPUB)
        [row] = client.get("/documents", headers=auth(user)).json()
        assert row["status"] == "not_novel" and row["rating"] is None and row["progress"] is None


class TestLocks:
    @pytest.fixture
    def doc(self, client, auth, user, other):
        return upload(client, auth, user, story_epub(), "Artikel.epub", EPUB).json()["id"]

    def test_the_rating_breakdown_is_refused(self, client, auth, user, doc):
        assert client.get(f"/documents/{doc}/rating", headers=auth(user)).status_code == 409

    def test_a_summary_cannot_be_started(self, client, auth, user, doc):
        assert client.post(f"/documents/{doc}/summary", headers=auth(user)).status_code == 409

    def test_characters_cannot_be_detected(self, client, auth, user, doc, monkeypatch):
        from app.api.routers import documents

        monkeypatch.setattr(documents.character_service.character_ai, "available", lambda: True)
        assert client.post(f"/documents/{doc}/characters", headers=auth(user)).status_code == 409

    def test_there_is_no_text_to_read(self, client, auth, user, doc):
        assert client.get(f"/documents/{doc}/paragraphs", headers=auth(user)).json() == []

    def test_the_pdf_export_is_refused(self, client, db, auth, make_user, other):
        high = make_user("high")
        doc = upload(client, auth, high, story_epub(), "Artikel.epub", EPUB).json()["id"]
        assert client.get(f"/documents/{doc}/export", headers=auth(high)).status_code == 409


class TestActiveBooks:
    def test_non_novels_and_failures_do_not_fill_the_collection(self, db, user):
        for status in ("done", "queued", "not_novel", "not_novel", "failed"):
            db.add(models.Document(user_id=user.id, title=status, filename="x.pdf", page_count=1, paragraph_count=0, status=status))
        db.commit()
        assert billing.active_books(db, user) == 2


def test_the_admin_statistics_count_non_novels():
    assert "not_novel" in admin_stats.DOC_STATUSES
