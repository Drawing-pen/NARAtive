import json
from datetime import datetime, timedelta

import pytest

from app.core.config import settings
from app.db import models
from app.db.database import SessionLocal
from app.services import character_ai, characters, heaviness, jobs, llm_analyzer
from app.services.summarizer import SummaryError
from tests.test_characters_flow import FakeLLM, make_story


def stored(doc_id, field):
    with SessionLocal() as other:
        return getattr(other.get(models.Document, doc_id), field)


def document(db, owner, **fields):
    base = dict(user_id=owner.id, title="Buku Uji", filename="b.pdf", page_count=10, paragraph_count=2, status="queued")
    doc = models.Document(**{**base, **fields})
    db.add(doc)
    db.commit()
    return doc


@pytest.fixture
def owner(make_user):
    return make_user("middle", expires_at=datetime.utcnow() + timedelta(days=10))


class TestDocumentProgress:
    def test_while_reading_it_is_the_share_of_pages_read(self, db, owner):
        assert document(db, owner, status="reading", page_count=10, read_pages=4).progress == 40

    def test_reading_a_document_without_pages_is_zero(self, db, owner):
        assert document(db, owner, status="reading", page_count=0, read_pages=0).progress == 0

    def test_reading_never_passes_one_hundred(self, db, owner):
        assert document(db, owner, status="reading", page_count=5, read_pages=9).progress == 100

    def test_a_waiting_document_is_at_zero(self, db, owner):
        assert document(db, owner, status="queued", analysis_progress=70).progress == 0

    def test_an_analysing_document_reports_the_stored_number(self, db, owner):
        assert document(db, owner, status="analyzing", analysis_progress=55).progress == 55

    @pytest.mark.parametrize("status", ["done", "failed", "uploaded"])
    def test_other_statuses_have_no_progress(self, db, owner, status):
        assert document(db, owner, status=status, analysis_progress=100).progress is None

    def test_the_endpoint_exposes_it(self, db, client, auth, owner):
        doc = document(db, owner, status="analyzing", analysis_progress=33)
        body = client.get(f"/documents/{doc.id}", headers=auth(owner)).json()
        assert body["progress"] == 33

    def test_the_endpoint_gives_null_when_nothing_is_running(self, db, client, auth, owner):
        doc = document(db, owner, status="done")
        assert client.get(f"/documents/{doc.id}", headers=auth(owner)).json()["progress"] is None

    def test_the_list_carries_it_too(self, db, client, auth, owner):
        document(db, owner, status="reading", page_count=4, read_pages=1)
        assert client.get("/documents", headers=auth(owner)).json()[0]["progress"] == 25

    def test_the_default_estimate_is_thirty_hundredths_of_a_second_per_paragraph(self):
        assert settings.seconds_per_paragraph == 0.3


class TestAnalyzeCallback:
    ITEMS = [(1, "a" * 50), (2, "b" * 50), (3, "c" * 50)]

    @pytest.fixture(autouse=True)
    def quiet(self, monkeypatch):
        monkeypatch.setattr(settings, "analyzer_chunk_chars", 60)
        monkeypatch.setattr(llm_analyzer, "RETRY_WAIT", 0)

    def test_every_finished_chunk_is_reported_in_order(self, monkeypatch):
        monkeypatch.setattr(llm_analyzer, "_generate", lambda *a, **k: json.dumps({"adegan": []}))
        seen = []
        llm_analyzer.analyze(self.ITEMS, on_progress=lambda done, total: seen.append((done, total)))
        assert seen == [(1, 3), (2, 3), (3, 3)]

    def test_a_failed_chunk_counts_once_and_the_retry_adds_nothing(self, monkeypatch):
        def flaky(prompt, **kwargs):
            if "b" * 20 in prompt:
                raise SummaryError("mati")
            return json.dumps({"adegan": []})

        monkeypatch.setattr(llm_analyzer, "_generate", flaky)
        seen = []
        llm_analyzer.analyze(self.ITEMS, on_progress=lambda done, total: seen.append((done, total)))
        assert [d for d, _ in seen] == [1, 2, 3] and {t for _, t in seen} == {3}

    def test_no_callback_still_works(self, monkeypatch):
        monkeypatch.setattr(llm_analyzer, "_generate", lambda *a, **k: json.dumps({"adegan": []}))
        assert len(llm_analyzer.analyze(self.ITEMS)) == 3

    def test_nothing_to_analyse_reports_nothing(self):
        seen = []
        assert llm_analyzer.analyze([], on_progress=lambda *a: seen.append(a)) == []
        assert seen == []


class TestJobProgress:
    @pytest.fixture(autouse=True)
    def no_gemini_heaviness(self, monkeypatch):
        monkeypatch.setattr(jobs, "configured", lambda: False)

    @pytest.fixture
    def doc(self, db, owner):
        return document(db, owner, status="queued", analysis_progress=77)

    @staticmethod
    def scores(items):
        return [{"profanity": 0.0, "sexual": 0.0, "violence": 0.0} for _ in items]

    def test_the_number_is_reset_when_analysis_starts(self, doc, monkeypatch):
        seen = {}

        def analyze(items, on_progress=None):
            seen["start"] = stored(doc.id, "analysis_progress")
            return self.scores(items)

        monkeypatch.setattr(llm_analyzer, "analyze", analyze)
        jobs.process(doc.id)
        assert seen["start"] == 0

    def test_finished_chunks_are_written_up_to_ninety_percent(self, doc, monkeypatch):
        seen = []

        def analyze(items, on_progress=None):
            for done in (1, 2, 4):
                on_progress(done, 4)
                seen.append(stored(doc.id, "analysis_progress"))
            return self.scores(items)

        monkeypatch.setattr(llm_analyzer, "analyze", analyze)
        jobs.process(doc.id)
        assert seen == [22, 45, 90]

    def test_the_story_weight_step_sets_ninety_five(self, doc, monkeypatch):
        seen = {}
        monkeypatch.setattr(llm_analyzer, "analyze", lambda items, on_progress=None: self.scores(items))
        monkeypatch.setattr(jobs, "configured", lambda: True)

        def rate(d):
            seen["during"] = stored(doc.id, "analysis_progress")
            return 40.0, "catatan"

        monkeypatch.setattr(heaviness, "rate_document", rate)
        jobs.process(doc.id)
        assert seen["during"] == 95

    def test_a_finished_document_ends_at_one_hundred_with_no_progress_shown(self, db, doc, monkeypatch):
        monkeypatch.setattr(llm_analyzer, "analyze", lambda items, on_progress=None: self.scores(items))
        jobs.process(doc.id)
        db.expire_all()
        done = db.get(models.Document, doc.id)
        assert done.status == "done" and done.analysis_progress == 100 and done.progress is None


@pytest.fixture
def llm(monkeypatch):
    fake = FakeLLM()
    monkeypatch.setattr(character_ai, "_generate", fake)
    monkeypatch.setattr(character_ai, "configured", lambda: True)
    monkeypatch.setattr(character_ai.time, "sleep", lambda seconds: None)
    return fake


class TestCharactersProgress:
    def test_read_chunks_reports_each_finished_chunk(self, llm):
        chunks = character_ai.make_chunks([{"chapter_no": n, "text": "Rana datang.", "sexual": 0.0} for n in (1, 2, 3)], limit=15)
        seen = []
        character_ai.read_chunks(chunks, on_progress=lambda done, total: seen.append((done, total)))
        assert seen == [(1, 3), (2, 3), (3, 3)]

    def test_a_failed_first_round_is_not_counted_twice(self, llm):
        chunks = character_ai.make_chunks([{"chapter_no": n, "text": "Rana datang.", "sexual": 0.0} for n in (1, 2)], limit=15)

        def fail(prompt):
            raise SummaryError("mati")

        llm.chunk = fail
        seen = []
        character_ai.read_chunks(chunks, on_progress=lambda done, total: seen.append((done, total)))
        assert seen == [(1, 2), (2, 2)]

    def test_read_chunks_works_without_a_callback(self, llm):
        assert character_ai.read_chunks([]) == []

    def test_a_run_ends_at_one_hundred_and_shows_no_progress(self, db, owner, llm):
        story = make_story(db, owner)
        characters.run(story.id)
        db.expire_all()
        done = db.get(models.Document, story.id)
        assert done.characters_status == "done" and done.characters_progress == 100

    def test_the_run_starts_from_zero(self, db, owner, llm):
        story = make_story(db, owner)
        story.characters_progress = 80
        db.commit()
        seen = {}

        def chunk(prompt):
            seen["start"] = stored(story.id, "characters_progress")
            return json.dumps({"sudut_pandang": "ketiga", "narator": "", "kata_ganti_pertama": [], "tokoh": [], "relasi": []})

        llm.chunk = chunk
        characters.run(story.id)
        assert seen["start"] == 0

    def test_chunks_are_written_up_to_eighty_and_the_merge_sets_ninety(self, db, owner, llm, monkeypatch):
        monkeypatch.setattr(character_ai, "CHUNK_CHARS", 60)
        story = make_story(db, owner)
        seen = {}

        def merge(prompt):
            seen["merge"] = stored(story.id, "characters_progress")
            return json.dumps({"tokoh": []})

        llm.merge = merge
        characters.run(story.id)
        assert seen["merge"] == 90


class TestRouterOutputs:
    def test_the_summary_reports_the_share_of_chapters_done_while_running(self, db, client, auth, owner):
        doc = document(db, owner, status="done", summary_status="running")
        doc.chapters = [models.Chapter(number=1, title="Bab 1", summary="Sudah."), models.Chapter(number=2, title="Bab 2")]
        db.commit()
        assert client.get(f"/documents/{doc.id}/summary", headers=auth(owner)).json()["progress"] == 50

    def test_a_summary_with_no_chapters_is_at_zero_while_running(self, db, client, auth, owner):
        doc = document(db, owner, status="done", summary_status="running")
        assert client.get(f"/documents/{doc.id}/summary", headers=auth(owner)).json()["progress"] == 0

    def test_a_finished_summary_has_no_progress(self, db, client, auth, owner):
        doc = document(db, owner, status="done", summary_status="done", summary="Ringkas.")
        assert client.get(f"/documents/{doc.id}/summary", headers=auth(owner)).json()["progress"] is None

    def test_characters_report_the_stored_number_while_running(self, db, client, auth, owner):
        doc = document(db, owner, status="done", characters_status="running", characters_progress=40)
        assert client.get(f"/documents/{doc.id}/characters", headers=auth(owner)).json()["progress"] == 40

    def test_finished_characters_have_no_progress(self, db, client, auth, owner):
        doc = document(db, owner, status="done", characters_status="done", characters_progress=100)
        assert client.get(f"/documents/{doc.id}/characters", headers=auth(owner)).json()["progress"] is None

    def test_asking_to_detect_again_resets_the_number(self, db, client, auth, owner, monkeypatch):
        from app.api.routers import documents

        monkeypatch.setattr(documents.character_service.character_ai, "available", lambda: True)
        monkeypatch.setattr(documents.character_service, "start", lambda doc_id: None)
        doc = document(db, owner, status="done", characters_status="done", characters_progress=100)
        client.post(f"/documents/{doc.id}/characters", headers=auth(owner))
        assert stored(doc.id, "characters_progress") == 0
