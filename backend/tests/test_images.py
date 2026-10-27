import os

import pytest

from app.core.config import settings
from app.db import models

JPEG = b"\xff\xd8\xff\xe0" + b"\x00" * 64
PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64
WEBP = b"RIFF\x24\x00\x00\x00WEBPVP8 " + b"\x00" * 64
MAX = 2 * 1024 * 1024
NOT_IMAGES = [b"<svg xmlns=\"http://www.w3.org/2000/svg\"></svg>", b"GIF89a" + b"\x00" * 20, b"%PDF-1.4 isi", b"teks biasa"]


@pytest.fixture(autouse=True)
def upload_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "upload_dir", str(tmp_path))
    return tmp_path


@pytest.fixture
def owner(make_user):
    return make_user("high")


@pytest.fixture
def doc(make_doc, owner):
    return make_doc(owner, characters=["Budi", "Sari"])


def character_id(db, doc, name="Budi"):
    return db.query(models.Character).filter_by(document_id=doc.id, name=name).one().id


def put(client, auth, user, url, data=JPEG, name="gambar.jpg", mime="image/jpeg"):
    return client.put(url, files={"file": (name, data, mime)}, headers=auth(user))


def stored(upload_dir):
    folder = upload_dir / "images"
    return sorted(os.listdir(folder)) if folder.exists() else []


def cover_url(doc):
    return f"/documents/{doc.id}/cover"


def photo_url(doc, char_id):
    return f"/documents/{doc.id}/characters/{char_id}/photo"


@pytest.fixture(params=["cover", "photo"])
def target(request, db, doc):
    return cover_url(doc) if request.param == "cover" else photo_url(doc, character_id(db, doc))


class TestUpload:
    @pytest.mark.parametrize("data,mime", [(JPEG, "image/jpeg"), (PNG, "image/png"), (WEBP, "image/webp")])
    def test_the_three_formats_are_stored_and_served_back(self, client, auth, owner, target, data, mime):
        assert put(client, auth, owner, target, data, "x", mime).status_code == 200
        res = client.get(target, headers=auth(owner))
        assert res.status_code == 200 and res.content == data and res.headers["content-type"] == mime

    def test_the_type_comes_from_the_content_not_the_name(self, client, auth, owner, target):
        assert put(client, auth, owner, target, PNG, "foto.jpg", "image/jpeg").status_code == 200
        assert client.get(target, headers=auth(owner)).headers["content-type"] == "image/png"

    @pytest.mark.parametrize("data", NOT_IMAGES)
    def test_other_formats_are_rejected(self, client, auth, owner, target, upload_dir, data):
        res = put(client, auth, owner, target, data, "gambar.jpg", "image/jpeg")
        assert res.status_code == 400 and res.json()["detail"] == "Format gambar tidak didukung. Gunakan JPG, PNG, atau WebP."
        assert stored(upload_dir) == []

    def test_an_empty_file_is_rejected(self, client, auth, owner, target):
        res = put(client, auth, owner, target, b"")
        assert res.status_code == 400 and res.json()["detail"] == "File gambar kosong."

    def test_two_megabytes_is_the_limit(self, client, auth, owner, target, upload_dir):
        assert put(client, auth, owner, target, JPEG + b"\x00" * (MAX - len(JPEG))).status_code == 200
        res = put(client, auth, owner, target, JPEG + b"\x00" * (MAX - len(JPEG) + 1))
        assert res.status_code == 413 and res.json()["detail"] == "Ukuran gambar maksimal 2 MB."
        assert len(stored(upload_dir)) == 1

    def test_a_missing_file_field_is_rejected(self, client, auth, owner, target):
        assert client.put(target, headers=auth(owner)).status_code == 422

    def test_the_response_tells_the_picture_is_set(self, client, db, auth, owner, doc):
        body = put(client, auth, owner, cover_url(doc)).json()
        assert body["id"] == doc.id and body["has_cover"] is True
        char = put(client, auth, owner, photo_url(doc, character_id(db, doc))).json()
        assert char["name"] == "Budi" and char["has_photo"] is True


class TestReplacingAndRemoving:
    def test_replacing_removes_the_old_file(self, client, auth, owner, target, upload_dir):
        put(client, auth, owner, target, JPEG)
        put(client, auth, owner, target, PNG, "b.png", "image/png")
        assert len(stored(upload_dir)) == 1
        assert client.get(target, headers=auth(owner)).content == PNG

    def test_a_rejected_replacement_keeps_the_old_picture(self, client, auth, owner, target):
        put(client, auth, owner, target, JPEG)
        assert put(client, auth, owner, target, b"bukan gambar").status_code == 400
        assert client.get(target, headers=auth(owner)).content == JPEG

    def test_restoring_the_default_removes_the_file(self, client, auth, owner, target, upload_dir):
        put(client, auth, owner, target)
        assert client.delete(target, headers=auth(owner)).status_code == 204
        assert client.get(target, headers=auth(owner)).status_code == 404
        assert stored(upload_dir) == []

    def test_restoring_without_a_picture_is_fine(self, client, auth, owner, target):
        assert client.delete(target, headers=auth(owner)).status_code == 204

    def test_without_a_picture_nothing_is_served(self, client, auth, owner, target):
        assert client.get(target, headers=auth(owner)).status_code == 404

    def test_the_flag_is_false_again_after_restoring(self, client, auth, owner, doc):
        put(client, auth, owner, cover_url(doc))
        client.delete(cover_url(doc), headers=auth(owner))
        assert client.get(f"/documents/{doc.id}", headers=auth(owner)).json()["has_cover"] is False


class TestTiers:
    @pytest.mark.parametrize("tier", ["free", "middle"])
    def test_only_high_may_change_pictures(self, client, auth, make_user, make_doc, db, tier, upload_dir):
        user = make_user(tier)
        doc = make_doc(user, characters=["Budi"])
        for url in (cover_url(doc), photo_url(doc, character_id(db, doc))):
            res = put(client, auth, user, url)
            assert res.status_code == 403 and res.json()["detail"] == "Fitur ini khusus pengguna High Tier."
            assert client.delete(url, headers=auth(user)).status_code == 403
        assert stored(upload_dir) == []

    def test_a_downgraded_owner_still_sees_the_picture_but_cannot_change_it(self, client, db, auth, owner, target):
        put(client, auth, owner, target)
        owner.tier = "free"
        db.commit()
        assert client.get(target, headers=auth(owner)).status_code == 200
        assert put(client, auth, owner, target, PNG).status_code == 403
        assert client.delete(target, headers=auth(owner)).status_code == 403

    def test_it_requires_login(self, client, target):
        assert client.get(target).status_code == 401
        assert client.put(target, files={"file": ("a.jpg", JPEG, "image/jpeg")}).status_code == 401
        assert client.delete(target).status_code == 401


class TestOwnership:
    def test_other_users_books_are_not_found(self, client, db, auth, make_user, doc):
        stranger = make_user("high")
        char = character_id(db, doc)
        for url in (cover_url(doc), photo_url(doc, char)):
            assert put(client, auth, stranger, url).status_code == 404
            assert client.get(url, headers=auth(stranger)).status_code == 404
            assert client.delete(url, headers=auth(stranger)).status_code == 404

    def test_other_users_pictures_are_not_served(self, client, auth, make_user, owner, target):
        put(client, auth, owner, target)
        assert client.get(target, headers=auth(make_user("high"))).status_code == 404

    def test_a_character_of_another_book_is_not_found(self, client, db, auth, owner, make_doc, doc):
        other = make_doc(owner, characters=["Lain"], title="Buku Lain")
        res = put(client, auth, owner, photo_url(doc, character_id(db, other, "Lain")))
        assert res.status_code == 404 and res.json()["detail"] == "Tokoh tidak ditemukan."

    def test_unknown_ids_are_not_found(self, client, auth, owner, doc):
        assert put(client, auth, owner, "/documents/9999/cover").status_code == 404
        assert put(client, auth, owner, photo_url(doc, 9999)).status_code == 404


class TestCleanup:
    def test_deleting_the_book_removes_its_pictures(self, client, db, auth, owner, doc, upload_dir):
        put(client, auth, owner, cover_url(doc))
        put(client, auth, owner, photo_url(doc, character_id(db, doc)), PNG, "a.png", "image/png")
        assert len(stored(upload_dir)) == 2
        assert client.delete(f"/documents/{doc.id}", headers=auth(owner)).status_code == 204
        assert stored(upload_dir) == []

    def test_deleting_one_book_keeps_the_pictures_of_another(self, client, auth, owner, make_doc, doc, upload_dir):
        keep = make_doc(owner, title="Simpan")
        put(client, auth, owner, cover_url(keep))
        put(client, auth, owner, cover_url(doc))
        client.delete(f"/documents/{doc.id}", headers=auth(owner))
        assert len(stored(upload_dir)) == 1
        assert client.get(cover_url(keep), headers=auth(owner)).status_code == 200


def test_listing_exposes_the_flags(client, auth, owner, doc):
    put(client, auth, owner, cover_url(doc))
    [item] = client.get("/documents", headers=auth(owner)).json()
    assert item["has_cover"] is True
    chars = client.get(f"/documents/{doc.id}/characters", headers=auth(owner)).json()["characters"]
    assert {c["name"]: c["has_photo"] for c in chars} == {"Budi": False, "Sari": False}


def test_detecting_characters_again_removes_the_old_photos(client, db, auth, owner, upload_dir):
    from app.services import characters
    from tests.test_characters_flow import fake_ner, make_story

    story = make_story(db, owner)
    characters.extract(db, story, ner=fake_ner("Rana", "Dede"))
    first = db.query(models.Character).filter_by(document_id=story.id).first()
    put(client, auth, owner, photo_url(story, first.id))
    assert len(stored(upload_dir)) == 1
    characters.extract(db, story, ner=fake_ner("Rana", "Dede"))
    assert stored(upload_dir) == []
