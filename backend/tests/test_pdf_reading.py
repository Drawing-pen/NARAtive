import os
from datetime import datetime, timedelta

import pymupdf
import pytest

from app.api.routers import documents
from app.core.config import settings
from app.db import models
from app.db.database import SessionLocal
from app.extraction import ocr
from app.services import jobs, reader_jobs
from tests.builders import blank_pdf, encrypted_pdf, make_epub, make_pdf, make_scanned_pdf, prose

BOOK = [f"Bab 1\n\n{prose(3)}", f"{prose(3, 4)}", f"Bab 2\n\n{prose(3, 6)}"]
SIZES = {"Bab 1": 22, "Bab 2": 22}
ANALYSED = []


@pytest.fixture(autouse=True)
def environment(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "upload_dir", str(tmp_path))
    monkeypatch.setattr(documents, "model_ready", lambda: True)
    monkeypatch.setattr(documents, "enqueue", lambda doc_id: None)
    monkeypatch.setattr(reader_jobs.jobs, "enqueue", lambda doc_id: ANALYSED.append(doc_id))
    ANALYSED.clear()


@pytest.fixture
def fake_ocr(monkeypatch):
    calls = []

    def recognize(page):
        calls.append(page.number)
        doc = pymupdf.open()
        sheet = doc.new_page(width=page.rect.width, height=page.rect.height)
        sheet.insert_textbox(pymupdf.Rect(36, 40, page.rect.width - 36, page.rect.height - 40), prose(3, 20 + page.number), fontsize=12)
        return doc.tobytes()

    monkeypatch.setattr(ocr, "ocr_ready", lambda: True)
    monkeypatch.setattr(ocr, "recognize", recognize)
    return calls


@pytest.fixture
def owner(make_user):
    return make_user("middle", expires_at=datetime.utcnow() + timedelta(days=10))


def reading(db, user, data, status="reading", store=True):
    with pymupdf.open(stream=data, filetype="pdf") as pdf:
        pages = len(pdf)
    doc = models.Document(user_id=user.id, title="Buku Uji", filename="Buku Uji.pdf", page_count=pages, paragraph_count=0, status=status, read_pages=0)
    db.add(doc)
    db.commit()
    if store:
        reader_jobs.store(doc.id, data)
    return doc


def fresh(db, doc):
    db.expire_all()
    return db.get(models.Document, doc.id)


def used(db, user):
    db.expire_all()
    row = db.query(models.UsageQuota).filter_by(user_id=user.id).first()
    return row.used if row else 0


def leftovers():
    folder = os.path.join(settings.upload_dir, reader_jobs.QUEUE_DIR)
    return sorted(os.listdir(folder)) if os.path.isdir(folder) else []


class TestProcessRead:
    def test_a_text_pdf_becomes_a_queued_document_with_paragraphs(self, db, owner, fake_ocr):
        doc = reading(db, owner, make_pdf(BOOK, sizes=SIZES))
        reader_jobs.process_read(doc.id)
        doc = fresh(db, doc)
        assert doc.status == "queued" and doc.failure_reason is None
        assert doc.read_pages == doc.page_count == 3 and doc.paragraph_count == len(doc.paragraphs) > 0
        assert [c.title for c in doc.chapters] == ["Bab 1", "Bab 2"]
        assert fake_ocr == [] and ANALYSED == [doc.id]

    def test_paragraphs_are_stored_in_order_with_plain_text_and_markdown(self, db, owner, fake_ocr):
        doc = reading(db, owner, make_pdf(BOOK, sizes=SIZES))
        reader_jobs.process_read(doc.id)
        paragraphs = fresh(db, doc).paragraphs
        assert [p.idx for p in paragraphs] == list(range(len(paragraphs)))
        assert all(p.text and p.kind == "p" for p in paragraphs)

    def test_a_scanned_pdf_is_read_through_ocr(self, db, owner, fake_ocr):
        doc = reading(db, owner, make_scanned_pdf(["a", "b", "c"]))
        reader_jobs.process_read(doc.id)
        doc = fresh(db, doc)
        assert doc.status == "queued" and fake_ocr == [0, 1, 2] and doc.paragraph_count > 0
        assert ANALYSED == [doc.id]

    def test_the_quota_is_used_once_when_reading_succeeds(self, db, owner, fake_ocr):
        doc = reading(db, owner, make_pdf(BOOK, sizes=SIZES))
        reader_jobs.process_read(doc.id)
        assert used(db, owner) == 1

    def test_extra_analyses_are_used_when_the_monthly_quota_is_gone(self, db, make_user, fake_ocr):
        user = make_user("free", extra_checks=2)
        db.add(models.UsageQuota(user_id=user.id, period=datetime.utcnow().strftime("%Y-%m"), used=3))
        db.commit()
        doc = reading(db, user, make_pdf(BOOK, sizes=SIZES))
        reader_jobs.process_read(doc.id)
        db.expire_all()
        assert db.get(models.User, user.id).extra_checks == 1

    def test_the_temporary_files_are_removed_after_success(self, db, owner, fake_ocr):
        doc = reading(db, owner, make_scanned_pdf(["a", "b"]))
        assert leftovers() == [f"{doc.id}.pdf"]
        reader_jobs.process_read(doc.id)
        assert leftovers() == []

    def test_progress_is_saved_every_five_pages_and_at_the_end(self, db, owner, monkeypatch):
        doc = reading(db, owner, make_pdf([prose(2, n) for n in range(7)]))
        seen = []

        def prepare(source, destination, on_page=None, should_stop=None):
            for n in range(1, 8):
                on_page(n)
                with SessionLocal() as other:
                    seen.append(other.get(models.Document, doc.id).read_pages)
            return ocr.Prepared(path=source, pages=7)

        monkeypatch.setattr(ocr, "prepare_pdf", prepare)
        reader_jobs.process_read(doc.id)
        assert seen == [0, 0, 0, 0, 5, 5, 7]

    def test_a_pdf_with_no_text_fails_with_a_plain_reason_and_no_quota(self, db, owner, monkeypatch):
        monkeypatch.setattr(ocr, "ocr_ready", lambda: False)
        doc = reading(db, owner, blank_pdf(2))
        reader_jobs.process_read(doc.id)
        doc = fresh(db, doc)
        assert doc.status == "failed" and doc.failure_reason == reader_jobs.NO_TEXT
        assert used(db, owner) == 0 and ANALYSED == [] and leftovers() == []

    def test_a_scan_without_ocr_available_fails_the_same_way(self, db, owner, monkeypatch):
        monkeypatch.setattr(ocr, "ocr_ready", lambda: False)
        doc = reading(db, owner, make_scanned_pdf(["a", "b"]))
        reader_jobs.process_read(doc.id)
        assert fresh(db, doc).failure_reason == reader_jobs.NO_TEXT

    def test_a_mixed_pdf_without_ocr_still_reads_its_text_pages(self, db, owner, monkeypatch):
        monkeypatch.setattr(ocr, "ocr_ready", lambda: False)
        mixed = pymupdf.open()
        mixed.insert_pdf(pymupdf.open("pdf", make_pdf(BOOK, sizes=SIZES)))
        mixed.insert_pdf(pymupdf.open("pdf", make_scanned_pdf(["x"])))
        doc = reading(db, owner, mixed.tobytes())
        reader_jobs.process_read(doc.id)
        doc = fresh(db, doc)
        assert doc.status == "queued" and doc.failure_reason is None

    def test_garbled_ocr_fails_with_the_quality_reason(self, db, owner, monkeypatch):
        monkeypatch.setattr(ocr, "ocr_ready", lambda: True)

        def garbage(page):
            doc = pymupdf.open()
            doc.new_page().insert_textbox(pymupdf.Rect(36, 40, 380, 500), "xkqz vwpf lrtm qzxv bnkw rtpl zxcv mnbq wprt klzx " * 6, fontsize=12)
            return doc.tobytes()

        monkeypatch.setattr(ocr, "recognize", garbage)
        doc = reading(db, owner, make_scanned_pdf(["a", "b"]))
        reader_jobs.process_read(doc.id)
        doc = fresh(db, doc)
        assert doc.status == "failed" and doc.failure_reason == reader_jobs.POOR_QUALITY and used(db, owner) == 0

    def test_a_pdf_that_is_mostly_text_is_not_judged_by_the_quality_of_a_few_scanned_pages(self, db, owner, monkeypatch):
        monkeypatch.setattr(ocr, "ocr_ready", lambda: True)
        monkeypatch.setattr(ocr, "recognize", lambda page: make_pdf(["xkqz vwpf lrtm qzxv bnkw rtpl zxcv mnbq " * 8]))
        mixed = pymupdf.open()
        for _ in range(3):
            mixed.insert_pdf(pymupdf.open("pdf", make_pdf([NORMAL])))
        mixed.insert_pdf(pymupdf.open("pdf", make_scanned_pdf(["x"])))
        doc = reading(db, owner, mixed.tobytes())
        reader_jobs.process_read(doc.id)
        assert fresh(db, doc).status == "queued"

    def test_a_missing_file_fails_with_the_restart_reason(self, db, owner):
        doc = reading(db, owner, make_pdf(BOOK), store=False)
        reader_jobs.process_read(doc.id)
        assert fresh(db, doc).failure_reason == reader_jobs.LOST

    def test_an_unexpected_error_fails_politely_and_keeps_the_quota(self, db, owner, monkeypatch):
        def boom(*args, **kwargs):
            raise RuntimeError("meledak")

        monkeypatch.setattr(ocr, "prepare_pdf", boom)
        doc = reading(db, owner, make_pdf(BOOK))
        reader_jobs.process_read(doc.id)
        doc = fresh(db, doc)
        assert doc.status == "failed" and doc.failure_reason == reader_jobs.GENERIC and used(db, owner) == 0 and leftovers() == []

    def test_a_document_deleted_while_being_read_stops_the_work_and_cleans_up(self, db, owner, monkeypatch):
        doc = reading(db, owner, make_pdf(BOOK))
        doc_id = doc.id
        state = {}

        def prepare(source, destination, on_page=None, should_stop=None):
            with SessionLocal() as other:
                other.delete(other.get(models.Document, doc_id))
                other.commit()
            state["stop"] = should_stop()
            return ocr.Prepared(path=source, pages=3, stopped=True)

        monkeypatch.setattr(ocr, "prepare_pdf", prepare)
        reader_jobs.process_read(doc_id)
        assert state["stop"] is True and leftovers() == [] and ANALYSED == []

    def test_an_unknown_document_is_ignored(self):
        reader_jobs.process_read(99999)

    def test_nothing_is_changed_for_a_document_that_is_no_longer_waiting_to_be_read(self, db, owner, fake_ocr):
        doc = reading(db, owner, make_pdf(BOOK), status="done")
        reader_jobs.process_read(doc.id)
        assert fresh(db, doc).status == "done" and ANALYSED == []

    @pytest.mark.parametrize("name", ["NO_TEXT", "POOR_QUALITY", "LOST", "GENERIC", "UNREADABLE"])
    def test_no_reason_mentions_ocr_or_scanning(self, name):
        reason = getattr(reader_jobs, name).lower()
        assert "ocr" not in reason and "scan" not in reason and "gambar" not in reason and len(reason) <= 255


NORMAL = prose(3) + " " + prose(3, 2)


class TestRecovery:
    def test_waiting_documents_with_their_file_are_queued_again(self, db, owner, monkeypatch):
        doc = reading(db, owner, make_pdf(BOOK))
        queued = []
        monkeypatch.setattr(reader_jobs, "enqueue_read", queued.append)
        reader_jobs.recover()
        assert queued == [doc.id] and fresh(db, doc).status == "reading"

    def test_waiting_documents_without_their_file_fail(self, db, owner, monkeypatch):
        doc = reading(db, owner, make_pdf(BOOK), store=False)
        monkeypatch.setattr(reader_jobs, "enqueue_read", lambda doc_id: pytest.fail("tidak boleh diantrekan"))
        reader_jobs.recover()
        doc = fresh(db, doc)
        assert doc.status == "failed" and doc.failure_reason == reader_jobs.LOST

    def test_other_documents_are_left_alone(self, db, owner, monkeypatch):
        done = reading(db, owner, make_pdf(BOOK), status="done", store=False)
        monkeypatch.setattr(reader_jobs, "enqueue_read", lambda doc_id: pytest.fail("tidak boleh diantrekan"))
        reader_jobs.recover()
        assert fresh(db, done).status == "done"

    def test_files_without_a_waiting_document_are_removed(self, db, owner, monkeypatch):
        monkeypatch.setattr(reader_jobs, "enqueue_read", lambda doc_id: None)
        reader_jobs.store(4242, make_pdf(BOOK))
        reader_jobs.recover()
        assert leftovers() == []

    def test_the_files_of_waiting_documents_are_kept(self, db, owner, monkeypatch):
        monkeypatch.setattr(reader_jobs, "enqueue_read", lambda doc_id: None)
        doc = reading(db, owner, make_pdf(BOOK))
        reader_jobs.recover()
        assert leftovers() == [f"{doc.id}.pdf"]


@pytest.fixture
def queued_reads(monkeypatch):
    seen = []
    monkeypatch.setattr(reader_jobs, "enqueue_read", seen.append)
    return seen


def upload(client, auth, user, data, name="Buku.pdf", mime="application/pdf"):
    return client.post("/documents", files={"file": (name, data, mime)}, headers=auth(user))


class TestUploadEndpoint:
    def test_a_pdf_returns_at_once_as_a_document_being_read(self, client, db, auth, owner, queued_reads):
        data = make_pdf(BOOK, sizes=SIZES)
        res = upload(client, auth, owner, data)
        assert res.status_code == 201
        body = res.json()
        assert body["status"] == "reading" and body["page_count"] == 3 and body["read_pages"] == 0 and body["failure_reason"] is None
        assert queued_reads == [body["id"]]
        stored = os.path.join(settings.upload_dir, reader_jobs.QUEUE_DIR, f"{body['id']}.pdf")
        assert open(stored, "rb").read() == data
        assert fresh(db, models.Document(id=body["id"])).paragraphs == []

    def test_the_quota_is_not_used_yet(self, client, db, auth, owner, queued_reads):
        upload(client, auth, owner, make_pdf(BOOK))
        assert used(db, owner) == 0

    def test_a_scanned_pdf_is_accepted_like_any_other(self, client, auth, owner, queued_reads):
        res = upload(client, auth, owner, make_scanned_pdf(["a", "b"]))
        assert res.status_code == 201 and res.json()["status"] == "reading"

    def test_an_over_long_pdf_is_refused_before_anything_is_stored(self, client, db, auth, make_user, queued_reads):
        free = make_user("free")
        res = upload(client, auth, free, make_pdf([prose(1, n) for n in range(51)]))
        assert res.status_code == 402 and "Batas halaman" in res.json()["detail"]
        assert queued_reads == [] and leftovers() == [] and db.query(models.Document).count() == 0

    def test_a_corrupt_pdf_is_refused(self, client, auth, owner, queued_reads):
        res = upload(client, auth, owner, b"%PDF-1.4 rusak total")
        assert res.status_code == 400 and res.json()["detail"] == reader_jobs.UNREADABLE and queued_reads == []

    def test_a_password_protected_pdf_is_refused(self, client, auth, owner, queued_reads):
        res = upload(client, auth, owner, encrypted_pdf())
        assert res.status_code == 400 and res.json()["detail"] == reader_jobs.UNREADABLE and queued_reads == []

    def test_a_file_over_the_size_limit_is_refused(self, client, auth, owner, queued_reads, monkeypatch):
        monkeypatch.setattr(settings, "max_upload_mb", 0)
        res = upload(client, auth, owner, make_pdf(BOOK))
        assert res.status_code == 413 and "maksimal 0 MB" in res.json()["detail"] and queued_reads == []

    def test_the_size_limit_applies_to_epubs_too(self, client, auth, owner, monkeypatch):
        monkeypatch.setattr(settings, "max_upload_mb", 0)
        epub = make_epub([("a.xhtml", f"<h1>Bab</h1><p>{prose(3)}</p>")])
        assert upload(client, auth, owner, epub, "Novel.epub", "application/epub+zip").status_code == 413

    def test_the_default_limit_is_100_megabytes(self):
        from app.core.config import Settings
        assert Settings(_env_file=None).max_upload_mb == 100

    def test_an_epub_is_still_read_at_once(self, client, db, auth, owner):
        epub = make_epub([("a.xhtml", f"<h1>Bab Satu</h1><p>{prose(3)}</p>"), ("b.xhtml", f"<h1>Bab Dua</h1><p>{prose(3, 4)}</p>")])
        res = upload(client, auth, owner, epub, "Novel.epub", "application/epub+zip")
        assert res.status_code == 201 and res.json()["status"] == "queued"
        assert fresh(db, models.Document(id=res.json()["id"])).paragraphs and used(db, owner) == 1

    def test_unsupported_formats_are_still_refused(self, client, auth, owner):
        res = upload(client, auth, owner, b"teks biasa", "catatan.txt", "text/plain")
        assert res.status_code == 400 and "PDF atau EPUB" in res.json()["detail"]

    def test_a_document_being_read_can_be_deleted_and_its_file_goes_too(self, client, db, auth, owner, queued_reads):
        doc_id = upload(client, auth, owner, make_pdf(BOOK)).json()["id"]
        assert leftovers() == [f"{doc_id}.pdf"]
        assert client.delete(f"/documents/{doc_id}", headers=auth(owner)).status_code == 204
        assert leftovers() == [] and db.query(models.Document).count() == 0

    def test_the_failure_reason_is_visible_through_the_api(self, client, db, auth, owner, monkeypatch):
        monkeypatch.setattr(ocr, "ocr_ready", lambda: False)
        doc = reading(db, owner, blank_pdf(2))
        reader_jobs.process_read(doc.id)
        body = client.get(f"/documents/{doc.id}", headers=auth(owner)).json()
        assert body["status"] == "failed" and body["failure_reason"] == reader_jobs.NO_TEXT

    def test_the_list_carries_progress_for_every_book(self, client, db, auth, owner):
        doc = reading(db, owner, make_pdf(BOOK))
        doc.read_pages = 2
        db.commit()
        [item] = client.get("/documents", headers=auth(owner)).json()
        assert item["status"] == "reading" and item["read_pages"] == 2 and item["page_count"] == 3


class TestQuotaAndCapacity:
    def test_books_still_being_read_hold_their_quota(self, client, db, auth, make_user, queued_reads):
        free = make_user("free")
        db.add(models.UsageQuota(user_id=free.id, period=datetime.utcnow().strftime("%Y-%m"), used=2))
        db.commit()
        assert upload(client, auth, free, make_pdf(BOOK)).status_code == 201
        res = upload(client, auth, free, make_pdf(BOOK))
        assert res.status_code == 402 and "Kuota analisis bulan ini habis" in res.json()["detail"]

    def test_extra_analyses_count_toward_what_remains(self, client, db, auth, make_user, queued_reads):
        free = make_user("free", extra_checks=1)
        db.add(models.UsageQuota(user_id=free.id, period=datetime.utcnow().strftime("%Y-%m"), used=3))
        db.commit()
        assert upload(client, auth, free, make_pdf(BOOK)).status_code == 201
        assert upload(client, auth, free, make_pdf(BOOK)).status_code == 402

    def test_a_failed_read_gives_the_quota_back(self, client, db, auth, make_user, monkeypatch):
        monkeypatch.setattr(ocr, "ocr_ready", lambda: False)
        free = make_user("free")
        db.add(models.UsageQuota(user_id=free.id, period=datetime.utcnow().strftime("%Y-%m"), used=2))
        db.commit()
        blank = reading(db, free, blank_pdf(2))
        monkeypatch.setattr(reader_jobs, "enqueue_read", lambda doc_id: None)
        reader_jobs.process_read(blank.id)
        assert upload(client, auth, free, make_pdf(BOOK)).status_code == 201

    def test_failed_books_do_not_count_as_active(self, client, db, auth, make_user, queued_reads):
        free = make_user("free")
        for status in ("done", "done", "failed"):
            reading(db, free, make_pdf(BOOK), status=status, store=False)
        assert upload(client, auth, free, make_pdf(BOOK)).status_code == 201

    def test_books_being_read_do_count_as_active(self, client, db, auth, make_user, queued_reads):
        free = make_user("free")
        for _ in range(3):
            reading(db, free, make_pdf(BOOK), store=False)
        res = upload(client, auth, free, make_pdf(BOOK))
        assert res.status_code == 402 and "Koleksi aktif penuh" in res.json()["detail"]

    def test_three_done_books_fill_the_free_collection(self, client, db, auth, make_user, queued_reads):
        free = make_user("free")
        for _ in range(3):
            reading(db, free, make_pdf(BOOK), status="done", store=False)
        assert upload(client, auth, free, make_pdf(BOOK)).status_code == 402
