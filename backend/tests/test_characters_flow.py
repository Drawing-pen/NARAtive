import re
from datetime import datetime, timedelta

import pytest
from sqlalchemy.exc import IntegrityError

from app.db import models
from app.db.database import SessionLocal
from app.services import character_ai, characters


def fake_ner(*names):
    def ner(texts):
        out = []
        for text in texts:
            found = []
            for name in names:
                for m in re.finditer(re.escape(name), text):
                    found.append({"entity_group": "PER", "score": 0.99, "start": m.start(), "end": m.end(), "word": name})
            out.append(sorted(found, key=lambda e: e["start"]))
        return out

    return ner


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


@pytest.fixture
def owner(make_user):
    return make_user("middle", expires_at=datetime.utcnow() + timedelta(days=10))


@pytest.fixture
def story(db, owner):
    return make_story(db, owner)


def test_extract_stores_characters_ordered_with_their_details(db, story):
    made = characters.extract(db, story, ner=fake_ner("Rana", "Dede"))
    assert made == (2, 1, True)
    rows = db.query(models.Character).filter_by(document_id=story.id).order_by(models.Character.mention_count.desc()).all()
    assert [r.name for r in rows] == ["Rana", "Dede"]
    assert [r.mention_count for r in rows] == [7, 6]
    assert rows[0].role == "Tokoh utama" and rows[0].biodata.startswith("Rana adalah tokoh utama")


def test_relations_are_stored_per_chapter_with_ordered_character_ids(db, story):
    characters.extract(db, story, ner=fake_ner("Rana", "Dede"))
    [relation] = db.query(models.CharacterRelation).all()
    chapter = db.get(models.Chapter, relation.chapter_id)
    assert chapter.number == 1 and chapter.document_id == story.id
    assert relation.character_a_id < relation.character_b_id
    assert relation.relation_type == "sahabat" and relation.weight == 4


def test_detecting_again_replaces_the_old_results_without_duplicates(db, story):
    characters.extract(db, story, ner=fake_ner("Rana", "Dede"))
    again = characters.extract(db, story, ner=fake_ner("Rana", "Dede"))
    assert again == (2, 1, True)
    assert counts(db) == (2, 1)
    assert sorted(c.name for c in db.query(models.Character).all()) == ["Dede", "Rana"]


def test_detecting_again_with_different_names_leaves_nothing_of_the_old_run(db, story):
    characters.extract(db, story, ner=fake_ner("Rana", "Dede"))
    characters.extract(db, story, ner=fake_ner("Rana"))
    assert [c.name for c in db.query(models.Character).all()] == ["Rana"]
    assert counts(db)[1] == 0


def test_a_pair_can_only_be_stored_once_per_chapter(db, story):
    characters.extract(db, story, ner=fake_ner("Rana", "Dede"))
    [relation] = db.query(models.CharacterRelation).all()
    db.add(models.CharacterRelation(
        character_a_id=relation.character_a_id, character_b_id=relation.character_b_id,
        chapter_id=relation.chapter_id, relation_type="teman", weight=2,
    ))
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()


def test_other_documents_characters_are_untouched_by_a_new_detection(db, owner, story):
    other = make_story(db, owner, title="Lain")
    characters.extract(db, other, ner=fake_ner("Rana", "Dede"))
    characters.extract(db, story, ner=fake_ner("Rana"))
    assert db.query(models.Character).filter_by(document_id=other.id).count() == 2


def test_ai_profile_fields_are_stored_when_the_ai_succeeds(db, story, monkeypatch):
    def fake_safe(items):
        return [{
            "ids": [item["id"] for item in items if item["name"] == "Rana"], "gender": "Perempuan", "age": "Dewasa",
            "occupation": "Mahasiswa", "personality": "Pendiam.", "background": "Anak sulung.", "summary": "Rana itu pendiam.",
        }]

    monkeypatch.setattr(character_ai, "safe", fake_safe)
    assert characters.extract(db, story, ner=fake_ner("Rana", "Dede"), ai=True)[2] is True
    rana = db.query(models.Character).filter_by(name="Rana").one()
    assert (rana.gender, rana.personality, rana.background, rana.biodata) == ("Perempuan", "Pendiam.", "Anak sulung.", "Rana itu pendiam.")


def test_the_basic_result_is_kept_when_the_ai_fails(db, story, monkeypatch):
    monkeypatch.setattr(character_ai, "safe", lambda items: None)
    assert characters.extract(db, story, ner=fake_ner("Rana", "Dede"), ai=True) == (2, 1, False)
    rana = db.query(models.Character).filter_by(name="Rana").one()
    assert rana.personality is None and rana.biodata.startswith("Rana adalah")


def test_without_the_ai_flag_gemini_is_never_asked(db, story, monkeypatch):
    monkeypatch.setattr(character_ai, "safe", lambda items: pytest.fail("Gemini dipanggil tanpa diminta"))
    characters.extract(db, story, ner=fake_ner("Rana", "Dede"))


class TestStatus:
    def test_a_successful_run_is_done(self, db, story, monkeypatch):
        monkeypatch.setattr(characters, "detect", fake_ner("Rana", "Dede"))
        characters.run(story.id)
        db.expire_all()
        assert db.get(models.Document, story.id).characters_status == "done"
        assert counts(db) == (2, 1)

    def test_a_run_whose_ai_failed_is_partial_but_keeps_the_characters(self, db, story, monkeypatch):
        monkeypatch.setattr(characters, "detect", fake_ner("Rana", "Dede"))
        monkeypatch.setattr(character_ai, "safe", lambda items: None)
        characters.run(story.id, ai=True)
        db.expire_all()
        assert db.get(models.Document, story.id).characters_status == "partial"
        assert counts(db) == (2, 1)

    def test_a_broken_ner_model_marks_the_run_failed(self, db, story, monkeypatch):
        def broken(texts):
            raise characters.CharacterError("Model NER tidak dapat dimuat")

        monkeypatch.setattr(characters, "detect", broken)
        characters.run(story.id)
        db.expire_all()
        assert db.get(models.Document, story.id).characters_status == "failed"

    def test_a_failed_run_does_not_destroy_the_previous_results(self, db, story, monkeypatch):
        monkeypatch.setattr(characters, "detect", fake_ner("Rana", "Dede"))
        characters.run(story.id)

        def broken(texts):
            raise RuntimeError("meledak")

        monkeypatch.setattr(characters, "detect", broken)
        characters.run(story.id)
        db.expire_all()
        assert db.get(models.Document, story.id).characters_status == "failed"
        assert counts(db) == (2, 1)

    def test_the_status_is_running_while_detection_works(self, db, story, monkeypatch):
        seen = {}

        def watching(texts):
            with SessionLocal() as other:
                seen["status"] = other.get(models.Document, story.id).characters_status
            return fake_ner("Rana", "Dede")(texts)

        monkeypatch.setattr(characters, "detect", watching)
        characters.run(story.id)
        assert seen["status"] == "running"

    def test_detection_runs_under_the_lock_so_documents_do_not_run_in_parallel(self, db, story, monkeypatch):
        seen = {}

        def locked_check(texts):
            seen["locked"] = characters._lock.locked()
            return fake_ner("Rana")(texts)

        monkeypatch.setattr(characters, "detect", locked_check)
        characters.run(story.id)
        assert seen["locked"] is True and not characters._lock.locked()

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
        monkeypatch.setattr(documents.character_service, "start", lambda doc_id, ai=False: self.calls.append((doc_id, ai)))

    def test_a_document_never_analysed_for_characters_is_empty(self, client, story, owner, auth):
        body = client.get(f"/documents/{story.id}/characters", headers=auth(owner)).json()
        assert body == {"status": None, "characters": [], "relations": []}

    def test_the_result_lists_characters_by_mentions_and_relations_by_chapter(self, client, db, story, owner, auth):
        characters.extract(db, story, ner=fake_ner("Rana", "Dede"))
        story.characters_status = "done"
        db.commit()
        body = client.get(f"/documents/{story.id}/characters", headers=auth(owner)).json()
        assert body["status"] == "done"
        assert [c["name"] for c in body["characters"]] == ["Rana", "Dede"]
        assert set(body["characters"][0]) >= {"id", "name", "role", "biodata", "mention_count", "aliases", "gender", "age", "occupation", "personality", "background"}
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
        assert self.calls == [(story.id, False)]

    def test_asking_while_running_does_not_start_a_second_job(self, client, db, story, owner, auth):
        story.characters_status = "running"
        db.commit()
        assert client.post(f"/documents/{story.id}/characters", headers=auth(owner)).status_code == 202
        assert self.calls == []

    def test_the_ai_variant_needs_the_gemini_key(self, client, story, owner, auth, monkeypatch):
        monkeypatch.setattr(character_ai, "available", lambda: False)
        res = client.post(f"/documents/{story.id}/characters?ai=true", headers=auth(owner))
        assert res.status_code == 409
        assert res.json()["detail"] == "Biodata AI butuh GEMINI_API_KEY di server."
        assert self.calls == []

    def test_the_ai_variant_is_passed_on_to_the_job(self, client, story, owner, auth, monkeypatch):
        monkeypatch.setattr(character_ai, "available", lambda: True)
        assert client.post(f"/documents/{story.id}/characters?ai=true", headers=auth(owner)).status_code == 202
        assert self.calls == [(story.id, True)]

    def test_deleting_the_book_removes_its_characters_and_relations(self, client, db, story, owner, auth):
        characters.extract(db, story, ner=fake_ner("Rana", "Dede"))
        assert client.delete(f"/documents/{story.id}", headers=auth(owner)).status_code == 204
        assert counts(db) == (0, 0)
