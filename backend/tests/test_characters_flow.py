import json
from datetime import datetime, timedelta

import pytest
from sqlalchemy.exc import IntegrityError

from app.db import models
from app.db.database import SessionLocal
from app.services import character_ai, characters
from app.services.summarizer import SummaryError


def make_story(db, owner, status="done", title="Cerita Uji"):
    doc = models.Document(
        user_id=owner.id, title=title, filename="c.pdf", page_count=5, paragraph_count=0, status=status, rating="General",
    )
    doc.chapters = [models.Chapter(number=1, title="Bab 1"), models.Chapter(number=2, title="Bab 2")]
    lines = (
        [(1, "Rana dan Dede adalah sahabat karib, teman baik.")] * 4
        + [(2, "Rana pulang sendiri.")] * 3
        + [(2, "Dede menunggu di rumah.")] * 2
    )
    for idx, (chapter, text) in enumerate(lines):
        doc.paragraphs.append(models.Paragraph(
            idx=idx, chapter_no=chapter, text=text, profanity=0.0, sexual=0.0, violence=0.0, emotion="happy", emotion_score=0.5,
        ))
    doc.paragraph_count = len(lines)
    db.add(doc)
    db.commit()
    return doc


def counts(db):
    db.expire_all()
    return db.query(models.Character).count(), db.query(models.CharacterRelation).count()


def chunk_reply(*names, relations=None):
    people = [{"nama": n, "panggilan": [], "peran": f"{n} adalah tokoh cerita."} for n in names]
    if relations is None:
        relations = [{"a": "Rana", "b": "Dede", "jenis": "sahabat", "bukti": "Rana dan Dede adalah sahabat karib"}]
    return json.dumps({"sudut_pandang": "ketiga", "narator": "", "kata_ganti_pertama": [], "tokoh": people, "relasi": relations})


class FakeLLM:
    def __init__(self):
        self.calls = []
        self.chunk = lambda prompt: chunk_reply("Rana", "Dede")
        self.merge = lambda prompt: json.dumps({"tokoh": []})

    def __call__(self, prompt, system="", schema=None, temperature=0.3, max_tokens=2048, prefer="", purpose=""):
        self.calls.append(purpose)
        handler = self.chunk if purpose == "tokoh per bab" else self.merge
        return handler(prompt)


@pytest.fixture
def llm(monkeypatch):
    fake = FakeLLM()
    monkeypatch.setattr(character_ai, "_generate", fake)
    monkeypatch.setattr(character_ai, "configured", lambda: True)
    monkeypatch.setattr(character_ai.time, "sleep", lambda seconds: None)
    return fake


@pytest.fixture
def owner(make_user):
    return make_user("middle", expires_at=datetime.utcnow() + timedelta(days=10))


@pytest.fixture
def story(db, owner):
    return make_story(db, owner)


def test_extract_stores_characters_ordered_with_their_description(db, story, llm):
    assert characters.extract(db, story) == (2, 1, True)
    rows = db.query(models.Character).filter_by(document_id=story.id).order_by(models.Character.mention_count.desc()).all()
    assert [r.name for r in rows] == ["Rana", "Dede"]
    assert [r.mention_count for r in rows] == [7, 6]
    assert rows[0].role == "" and rows[0].biodata == "Rana adalah tokoh cerita."
    assert rows[0].gender is None and rows[0].personality is None


def test_a_single_chunk_needs_one_request_and_no_merge(db, story, llm):
    characters.extract(db, story)
    assert llm.calls == ["tokoh per bab"]


def test_relations_are_stored_per_chapter_with_ordered_character_ids(db, story, llm):
    characters.extract(db, story)
    [relation] = db.query(models.CharacterRelation).all()
    chapter = db.get(models.Chapter, relation.chapter_id)
    assert chapter.number == 1 and chapter.document_id == story.id
    assert relation.character_a_id < relation.character_b_id
    assert relation.relation_type == "sahabat" and relation.weight == 4


def test_aliases_are_stored_for_the_card(db, story, llm):
    llm.chunk = lambda prompt: json.dumps({
        "sudut_pandang": "ketiga", "narator": "", "kata_ganti_pertama": [],
        "tokoh": [{"nama": "Rana", "panggilan": ["Dede"], "peran": "x"}], "relasi": [],
    })
    characters.extract(db, story)
    [rana] = db.query(models.Character).all()
    assert rana.name == "Rana" and rana.aliases == "Dede"


def test_detecting_again_replaces_the_old_results_without_duplicates(db, story, llm):
    characters.extract(db, story)
    assert characters.extract(db, story) == (2, 1, True)
    assert counts(db) == (2, 1)
    assert sorted(c.name for c in db.query(models.Character).all()) == ["Dede", "Rana"]


def test_detecting_again_with_different_names_leaves_nothing_of_the_old_run(db, story, llm):
    characters.extract(db, story)
    llm.chunk = lambda prompt: chunk_reply("Rana", relations=[])
    characters.extract(db, story)
    assert [c.name for c in db.query(models.Character).all()] == ["Rana"]
    assert counts(db)[1] == 0


def test_a_pair_can_only_be_stored_once_per_chapter(db, story, llm):
    characters.extract(db, story)
    [relation] = db.query(models.CharacterRelation).all()
    db.add(models.CharacterRelation(
        character_a_id=relation.character_a_id, character_b_id=relation.character_b_id,
        chapter_id=relation.chapter_id, relation_type="teman", weight=2,
    ))
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()


def test_other_documents_characters_are_untouched_by_a_new_detection(db, owner, story, llm):
    other = make_story(db, owner, title="Lain")
    characters.extract(db, other)
    llm.chunk = lambda prompt: chunk_reply("Rana", relations=[])
    characters.extract(db, story)
    assert db.query(models.Character).filter_by(document_id=other.id).count() == 2


def test_nothing_is_sent_for_a_paragraph_marked_sexual(db, owner, llm):
    doc = make_story(db, owner)
    doc.paragraphs[0].text = "RAHASIA-INTIM Rana dan Dede."
    doc.paragraphs[0].sexual = 0.9
    db.commit()
    sent = []
    llm.chunk = lambda prompt: sent.append(prompt) or chunk_reply("Rana", "Dede")
    characters.extract(db, doc)
    assert sent and "RAHASIA-INTIM" not in sent[0]


def test_detection_needs_a_configured_llm(db, story, monkeypatch):
    monkeypatch.setattr(character_ai, "configured", lambda: False)
    with pytest.raises(characters.CharacterError, match="layanan AI"):
        characters.extract(db, story)


class TestMultipleChunks:
    @pytest.fixture(autouse=True)
    def small_chunks(self, monkeypatch):
        monkeypatch.setattr(character_ai, "CHUNK_CHARS", 120)

    def test_each_chunk_is_one_request_plus_one_merge(self, db, story, llm):
        characters.extract(db, story)
        assert llm.calls.count("tokoh per bab") > 1 and llm.calls.count("gabung tokoh") == 1

    def test_the_merge_description_is_stored(self, db, story, llm):
        llm.merge = lambda prompt: json.dumps({"tokoh": [{"id": [0], "nama_utama": "Rana", "deskripsi": "Sahabat Dede sejak kecil."}]})
        characters.extract(db, story)
        assert db.query(models.Character).filter_by(name="Rana").one().biodata == "Sahabat Dede sejak kecil."

    def test_a_failed_merge_gives_a_partial_result_with_the_role_description(self, db, story, llm):
        def failing(prompt):
            raise SummaryError("gagal")

        llm.merge = failing
        assert characters.extract(db, story) == (2, 1, False)
        assert db.query(models.Character).filter_by(name="Rana").one().biodata == "Rana adalah tokoh cerita."


class TestStatus:
    def test_a_successful_run_is_done(self, db, story, llm):
        characters.run(story.id)
        db.expire_all()
        assert db.get(models.Document, story.id).characters_status == "done"
        assert counts(db) == (2, 1)

    def test_a_run_with_a_failed_chunk_is_partial_but_keeps_the_characters(self, db, story, llm, monkeypatch):
        monkeypatch.setattr(character_ai, "CHUNK_CHARS", 120)
        state = {"n": 0}
        original = llm.chunk

        def flaky(prompt):
            state["n"] += 1
            if state["n"] <= 2:
                raise SummaryError("9router ditahan")
            return original(prompt)

        llm.chunk = flaky
        characters.run(story.id)
        db.expire_all()
        assert db.get(models.Document, story.id).characters_status in ("done", "partial")

    def test_a_partial_run_is_only_logged_for_the_server(self, db, story, llm, monkeypatch, caplog):
        import logging

        monkeypatch.setattr(character_ai, "CHUNK_CHARS", 120)

        def failing(prompt):
            raise SummaryError("gagal")

        llm.merge = failing
        caplog.set_level(logging.WARNING, logger="narative.characters")
        characters.run(story.id)
        db.expire_all()
        assert db.get(models.Document, story.id).characters_status == "partial"
        assert any("selesai sebagian" in r.getMessage() and str(story.id) in r.getMessage() for r in caplog.records)

    def test_when_every_chunk_fails_the_run_is_failed(self, db, story, llm):
        def failing(prompt):
            raise SummaryError("mati")

        llm.chunk = failing
        characters.run(story.id)
        db.expire_all()
        assert db.get(models.Document, story.id).characters_status == "failed"
        assert counts(db) == (0, 0)

    def test_a_failed_run_does_not_destroy_the_previous_results(self, db, story, llm):
        characters.run(story.id)

        def failing(prompt):
            raise SummaryError("mati")

        llm.chunk = failing
        characters.run(story.id)
        db.expire_all()
        assert db.get(models.Document, story.id).characters_status == "failed"
        assert counts(db) == (2, 1)

    def test_the_status_is_running_while_detection_works(self, db, story, llm):
        seen = {}

        def watching(prompt):
            with SessionLocal() as other:
                seen["status"] = other.get(models.Document, story.id).characters_status
            return chunk_reply("Rana", "Dede")

        llm.chunk = watching
        characters.run(story.id)
        assert seen["status"] == "running"

    def test_detection_runs_under_the_lock_so_documents_do_not_run_in_parallel(self, db, story, llm):
        seen = {}

        def locked_check(prompt):
            seen["locked"] = characters._lock.locked()
            return chunk_reply("Rana")

        llm.chunk = locked_check
        characters.run(story.id)
        assert seen["locked"] is True and not characters._lock.locked()

    def test_a_run_without_an_llm_is_failed(self, db, story, monkeypatch):
        monkeypatch.setattr(character_ai, "configured", lambda: False)
        characters.run(story.id)
        db.expire_all()
        assert db.get(models.Document, story.id).characters_status == "failed"

    def test_a_missing_document_is_ignored(self):
        characters.run(99999)

    def test_runs_left_running_are_marked_failed_on_startup(self, db, owner):
        running = make_story(db, owner)
        done = make_story(db, owner)
        running.characters_status, done.characters_status = "running", "done"
        db.commit()
        characters.reset_stale()
        db.expire_all()
        assert db.get(models.Document, running.id).characters_status == "failed"
        assert db.get(models.Document, done.id).characters_status == "done"


class TestEndpoints:
    @pytest.fixture(autouse=True)
    def started(self, monkeypatch):
        from app.api.routers import documents
        self.calls = []
        monkeypatch.setattr(documents.character_service, "start", lambda doc_id: self.calls.append(doc_id))
        monkeypatch.setattr(character_ai, "configured", lambda: True)

    def test_a_document_never_analysed_for_characters_is_empty(self, client, story, owner, auth):
        body = client.get(f"/documents/{story.id}/characters", headers=auth(owner)).json()
        assert body == {"status": None, "characters": [], "relations": []}

    def test_the_result_lists_characters_by_mentions_and_relations_by_chapter(self, client, db, story, owner, auth, llm):
        characters.extract(db, story)
        story.characters_status = "done"
        db.commit()
        body = client.get(f"/documents/{story.id}/characters", headers=auth(owner)).json()
        assert body["status"] == "done"
        assert [c["name"] for c in body["characters"]] == ["Rana", "Dede"]
        assert set(body["characters"][0]) >= {"id", "name", "biodata", "mention_count", "aliases"}
        assert not ({"role", "gender", "age", "occupation", "personality", "background"} & set(body["characters"][0]))
        [relation] = body["relations"]
        ids = {c["id"] for c in body["characters"]}
        assert relation["chapter"] == 1 and {relation["a"], relation["b"]} == ids
        assert relation["type"] == "sahabat" and relation["weight"] == 4

    def test_detection_needs_a_finished_analysis(self, client, db, owner, auth):
        unfinished = make_story(db, owner, status="analyzing")
        res = client.post(f"/documents/{unfinished.id}/characters", headers=auth(owner))
        assert res.status_code == 409
        assert res.json()["detail"] == "Tokoh bisa dideteksi setelah analisis selesai."
        assert self.calls == []

    def test_starting_marks_the_status_and_launches_one_job(self, client, db, story, owner, auth):
        res = client.post(f"/documents/{story.id}/characters", headers=auth(owner))
        assert res.status_code == 202 and res.json()["status"] == "running"
        assert self.calls == [story.id]

    def test_asking_while_running_does_not_start_a_second_job(self, client, db, story, owner, auth):
        story.characters_status = "running"
        db.commit()
        assert client.post(f"/documents/{story.id}/characters", headers=auth(owner)).status_code == 202
        assert self.calls == []

    def test_without_an_llm_the_request_is_refused(self, client, story, owner, auth, monkeypatch):
        monkeypatch.setattr(character_ai, "configured", lambda: False)
        res = client.post(f"/documents/{story.id}/characters", headers=auth(owner))
        assert res.status_code == 409
        assert res.json()["detail"] == "Deteksi tokoh butuh layanan AI (9router atau Gemini) di server."
        assert self.calls == []

    def test_the_old_ai_parameter_is_ignored(self, client, story, owner, auth):
        res = client.post(f"/documents/{story.id}/characters?ai=true", headers=auth(owner))
        assert res.status_code == 202 and self.calls == [story.id]

    def test_deleting_the_book_removes_its_characters_and_relations(self, client, db, story, owner, auth, llm):
        characters.extract(db, story)
        assert client.delete(f"/documents/{story.id}", headers=auth(owner)).status_code == 204
        assert counts(db) == (0, 0)
