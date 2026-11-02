import os

import pytest

from app.api.routers import documents
from app.core.config import settings
from app.db import models
from app.services import billing
from tests.builders import blank_pdf, drm_encryption, make_epub, make_pdf, prose

PDF = "application/pdf"
EPUB = "application/epub+zip"


@pytest.fixture(autouse=True)
def environment(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "upload_dir", str(tmp_path))
    monkeypatch.setattr(documents, "model_ready", lambda: True)
    queued = []
    monkeypatch.setattr(documents, "enqueue", queued.append)
    return queued


@pytest.fixture
def queued(environment):
    return environment


@pytest.fixture
def user(make_user):
    return make_user("middle")


def upload(client, auth, user, data, name="Cerita Rana.pdf", mime=PDF):
    return client.post("/documents", files={"file": (name, data, mime)}, headers=auth(user))


def story_pdf():
    return make_pdf([f"Bab 1\n\n{prose(3)}", f"Bab 2\n\n{prose(3, 4)}"])


def story_epub():
    return make_epub(
        [("a.xhtml", f"<h1>Bab Satu</h1><p>{prose(3)}</p>"), ("b.xhtml", f"<h1>Bab Dua</h1><p>{prose(3, 4)}</p>")]
    )


def leftovers(tmp_path):
    return [name for name in os.listdir(tmp_path)]


class TestSuccess:
    def test_a_pdf_is_stored_and_queued(self, client, db, auth, user, queued):
        res = upload(client, auth, user, story_pdf())
        assert res.status_code == 201
        body = res.json()
        assert body["title"] == "Cerita Rana" and body["status"] == "queued" and body["page_count"] == 2
        assert queued == [body["id"]]

    def test_an_epub_is_stored_and_queued(self, client, db, auth, user, queued):
        res = upload(client, auth, user, story_epub(), "Novel.epub", EPUB)
        assert res.status_code == 201 and res.json()["title"] == "Novel" and queued == [res.json()["id"]]

    def test_chapters_and_paragraphs_are_saved_in_order(self, client, db, auth, user):
        doc_id = upload(client, auth, user, story_pdf()).json()["id"]
        db.expire_all()
        doc = db.get(models.Document, doc_id)
        assert [c.title for c in doc.chapters] == ["Bab 1", "Bab 2"] and [c.number for c in doc.chapters] == [1, 2]
        assert [p.idx for p in doc.paragraphs] == list(range(len(doc.paragraphs)))
        assert {p.chapter_no for p in doc.paragraphs} == {1, 2}
        assert doc.paragraph_count == len(doc.paragraphs) and doc.user_id == user.id

    def test_the_analysis_scores_start_empty(self, client, db, auth, user):
        doc_id = upload(client, auth, user, story_pdf()).json()["id"]
        db.expire_all()
        assert all(p.profanity is None and p.emotion is None for p in db.get(models.Document, doc_id).paragraphs)

    def test_the_title_comes_from_the_file_name_without_the_extension(self, client, auth, user):
        assert upload(client, auth, user, story_pdf(), "Laskar.Pelangi.pdf").json()["title"] == "Laskar.Pelangi"

    def test_a_long_file_name_is_truncated_to_255_characters(self, client, db, auth, user):
        doc_id = upload(client, auth, user, story_pdf(), "a" * 300 + ".pdf").json()["id"]
        db.expire_all()
        doc = db.get(models.Document, doc_id)
        assert len(doc.title) == 255 and len(doc.filename) == 255

    def test_the_stored_file_name_has_no_folders(self, client, db, auth, user):
        doc_id = upload(client, auth, user, story_pdf(), "../../etc/rahasia.pdf").json()["id"]
        db.expire_all()
        assert "/" not in db.get(models.Document, doc_id).filename

    def test_an_uppercase_extension_is_accepted(self, client, auth, user):
        assert upload(client, auth, user, story_pdf(), "BUKU.PDF").status_code == 201

    @pytest.mark.parametrize("mime", [PDF, "application/octet-stream"])
    def test_pdf_content_types_that_are_accepted(self, client, auth, user, mime):
        assert upload(client, auth, user, story_pdf(), mime=mime).status_code == 201

    @pytest.mark.parametrize("mime", [EPUB, "application/octet-stream", "application/zip"])
    def test_epub_content_types_that_are_accepted(self, client, auth, user, mime):
        assert upload(client, auth, user, story_epub(), "n.epub", mime).status_code == 201

    def test_the_temporary_file_is_removed(self, client, auth, user, tmp_path):
        upload(client, auth, user, story_pdf())
        assert leftovers(tmp_path) == []

    def test_the_new_book_shows_up_in_the_library_newest_first(self, client, auth, user):
        first = upload(client, auth, user, story_pdf(), "Pertama.pdf").json()["id"]
        second = upload(client, auth, user, story_pdf(), "Kedua.pdf").json()["id"]
        assert [d["id"] for d in client.get("/documents", headers=auth(user)).json()] == [second, first]


class TestQuota:
    def test_an_upload_uses_one_analysis(self, client, db, auth, user):
        upload(client, auth, user, story_pdf())
        assert billing.used_this_month(db, user) == 1

    def test_extra_analyses_are_used_after_the_monthly_quota(self, client, db, auth, make_user):
        user = make_user("free", extra_checks=1)
        for n in range(3):
            assert upload(client, auth, user, story_pdf(), f"b{n}.pdf").status_code == 201
            db.expire_all()
        user = db.get(models.User, user.id)
        assert user.extra_checks == 1
        db.query(models.Document).delete()
        db.commit()
        assert upload(client, auth, user, story_pdf(), "tambahan.pdf").status_code == 201
        db.expire_all()
        assert db.get(models.User, user.id).extra_checks == 0

    def test_a_standard_account_cannot_upload_more_than_fifty_pages(self, client, db, auth, make_user, queued, tmp_path):
        user = make_user("free")
        res = upload(client, auth, user, make_pdf([prose(1, i) + f" Nomor {i * 31}." for i in range(51)]))
        assert res.status_code == 402 and "Batas halaman" in res.json()["detail"]
        db.expire_all()
        assert db.query(models.Document).count() == 0 and billing.used_this_month(db, user) == 0
        assert queued == [] and leftovers(tmp_path) == []

    def test_fifty_pages_are_allowed_for_a_standard_account(self, client, auth, make_user):
        pages = [prose(1, i) + f" Nomor {i * 31}." for i in range(50)]
        assert upload(client, auth, make_user("free"), make_pdf(pages)).status_code == 201

    def test_the_monthly_quota_blocks_the_next_upload(self, client, db, auth, make_user):
        user = make_user("free")
        db.add(models.UsageQuota(user_id=user.id, period=billing.current_period(), used=3))
        db.commit()
        res = upload(client, auth, user, story_pdf())
        assert res.status_code == 402 and "Kuota analisis" in res.json()["detail"]

    def test_a_full_library_blocks_the_next_upload(self, client, auth, make_user, make_doc):
        user = make_user("free")
        for n in range(3):
            make_doc(user, title=f"B{n}")
        res = upload(client, auth, user, story_pdf())
        assert res.status_code == 402 and "Koleksi aktif penuh" in res.json()["detail"]


class TestRejections:
    @pytest.mark.parametrize("name,mime", [("catatan.txt", "text/plain"), ("gambar.png", "image/png"), ("buku.docx", "application/octet-stream"), ("tanpa-ekstensi", PDF)])
    def test_unsupported_formats_are_rejected(self, client, db, auth, user, queued, name, mime):
        res = upload(client, auth, user, b"isi", name, mime)
        assert res.status_code == 400 and res.json()["detail"] == "Format file tidak didukung. Unggah file berformat PDF atau EPUB."
        db.expire_all()
        assert db.query(models.Document).count() == 0 and queued == []

    @pytest.mark.parametrize("name,mime", [("buku.pdf", "text/plain"), ("buku.epub", PDF), ("buku.pdf", EPUB)])
    def test_a_mismatched_content_type_is_rejected(self, client, auth, user, name, mime):
        assert upload(client, auth, user, b"isi", name, mime).status_code == 400

    def test_a_pdf_without_text_is_rejected(self, client, db, auth, user, queued, tmp_path):
        res = upload(client, auth, user, blank_pdf(3))
        assert res.status_code == 400 and res.json()["detail"] == "File tidak berisi teks yang dapat dianalisis."
        db.expire_all()
        assert db.query(models.Document).count() == 0 and billing.used_this_month(db, user) == 0
        assert queued == [] and leftovers(tmp_path) == []

    def test_a_corrupt_pdf_is_rejected_politely(self, client, db, auth, user, tmp_path):
        res = upload(client, auth, user, b"%PDF-1.4 rusak total")
        assert res.status_code == 400 and res.json()["detail"] == "File tidak dapat dibaca atau gagal disimpan. Coba unggah lagi."
        assert leftovers(tmp_path) == []

    def test_a_file_that_cannot_be_deleted_afterwards_does_not_fail_the_upload(self, client, db, auth, user, monkeypatch):
        def locked(path):
            raise PermissionError("berkas masih dipakai")

        monkeypatch.setattr(documents.os, "remove", locked)
        assert upload(client, auth, user, story_pdf()).status_code == 201

    def test_a_broken_epub_is_rejected_with_its_own_message(self, client, auth, user):
        res = upload(client, auth, user, b"bukan zip", "buku.epub", EPUB)
        assert res.status_code == 400 and "EPUB" in res.json()["detail"]

    def test_a_drm_epub_is_rejected(self, client, auth, user):
        data = make_epub([("a.xhtml", f"<h1>Bab</h1><p>{prose(2)}</p>")], encryption=drm_encryption("http://www.w3.org/2001/04/xmlenc#aes128-cbc"))
        res = upload(client, auth, user, data, "drm.epub", EPUB)
        assert res.status_code == 400 and "DRM" in res.json()["detail"]

    def test_an_epub_without_text_is_rejected(self, client, auth, user):
        res = upload(client, auth, user, make_epub([("a.xhtml", "<h1>Judul saja</h1>")]), "kosong.epub", EPUB)
        assert res.status_code == 400 and "tidak berisi teks" in res.json()["detail"]

    def test_nothing_is_kept_when_the_database_save_fails(self, client, db, auth, user, queued, tmp_path, monkeypatch):
        monkeypatch.setattr(billing, "consume_analysis", lambda *a: (_ for _ in ()).throw(RuntimeError("gagal")))
        res = upload(client, auth, user, story_pdf())
        assert res.status_code == 400 and queued == [] and leftovers(tmp_path) == []
        db.expire_all()
        assert db.query(models.Document).count() == 0

    def test_a_missing_model_blocks_the_upload(self, client, db, auth, user, queued, monkeypatch):
        monkeypatch.setattr(documents, "model_ready", lambda: False)
        res = upload(client, auth, user, story_pdf())
        assert res.status_code == 503 and "Model analisis belum terpasang" in res.json()["detail"]
        db.expire_all()
        assert db.query(models.Document).count() == 0 and queued == []

    def test_the_file_field_is_required(self, client, auth, user):
        assert client.post("/documents", headers=auth(user)).status_code == 422

    def test_login_is_required(self, client):
        assert client.post("/documents", files={"file": ("a.pdf", b"x", PDF)}).status_code == 401
