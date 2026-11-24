import logging
import os
import queue
import re
import threading

from sqlalchemy import select

from app.core.config import settings
from app.db.database import SessionLocal
from app.db.models import Chapter, Document, Paragraph, User
from app.extraction import ocr
from app.extraction.reader import read_document
from app.services import billing, doc_type, jobs

log = logging.getLogger("uvicorn.error")

QUEUE_DIR = "antrean"
PROGRESS_EVERY = 5
MIN_QUALITY = 0.5

UNREADABLE = "Berkas tidak dapat dibuka. Pastikan PDF tidak rusak atau terkunci kata sandi."
NO_TEXT = "Berkas ini tidak berisi teks yang dapat dibaca."
POOR_QUALITY = "Teks pada berkas ini tidak terbaca dengan baik. Coba berkas dengan kualitas lebih tinggi."
LOST = "Berkas hilang karena server dimulai ulang. Unggah ulang."
GENERIC = "Berkas gagal dibaca. Coba unggah lagi."

_queue: "queue.Queue[int]" = queue.Queue()
_worker: threading.Thread | None = None


def _folder() -> str:
    return os.path.join(settings.upload_dir, QUEUE_DIR)


def queue_path(doc_id: int) -> str:
    return os.path.join(_folder(), f"{doc_id}.pdf")


def _work_path(doc_id: int) -> str:
    return os.path.join(_folder(), f"{doc_id}.work.pdf")


def store(doc_id: int, data: bytes) -> None:
    os.makedirs(_folder(), exist_ok=True)
    with open(queue_path(doc_id), "wb") as f:
        f.write(data)


def _remove(path: str) -> None:
    try:
        os.remove(path)
    except FileNotFoundError:
        pass
    except OSError:
        log.warning("File sementara %s tidak bisa dihapus.", path)


def discard(doc_id: int) -> None:
    _remove(queue_path(doc_id))
    _remove(_work_path(doc_id))


def enqueue_read(doc_id: int) -> None:
    _queue.put(doc_id)


def _gone(db, doc_id: int) -> bool:
    return db.scalar(select(Document.id).where(Document.id == doc_id)) is None


def _fail(db, doc_id: int, reason: str) -> None:
    doc = db.get(Document, doc_id)
    if doc is not None:
        doc.status, doc.failure_reason = "failed", reason
        db.commit()


def process_read(doc_id: int) -> None:
    db = SessionLocal()
    try:
        doc = db.get(Document, doc_id)
        if doc is None or doc.status != "reading":
            return
        source = queue_path(doc_id)
        if not os.path.exists(source):
            _fail(db, doc_id, LOST)
            return
        total = doc.page_count

        def on_page(done: int) -> None:
            if done % PROGRESS_EVERY == 0 or done == total:
                doc.read_pages = done
                db.commit()

        prepared = ocr.prepare_pdf(source, _work_path(doc_id), on_page=on_page, should_stop=lambda: _gone(db, doc_id))
        if prepared.stopped:
            return
        if prepared.skipped >= prepared.pages:
            _fail(db, doc_id, NO_TEXT)
            return
        if prepared.ocr_pages * 2 >= prepared.pages and prepared.quality is not None and prepared.quality < MIN_QUALITY:
            _fail(db, doc_id, POOR_QUALITY)
            return
        if prepared.ocr_pages and prepared.ocr_pages * 2 >= prepared.pages and prepared.low_confidence_pages * 2 >= prepared.ocr_pages:
            _fail(db, doc_id, POOR_QUALITY)
            return
        parsed = read_document(prepared.path, ".pdf")
        if not parsed.blocks:
            _fail(db, doc_id, NO_TEXT)
            return
        if _gone(db, doc_id):
            return
        if doc_type.classify([block.text for _, block in parsed.blocks]) == "other":
            doc.status, doc.read_pages = "not_novel", doc.page_count
            db.commit()
            return
        doc.chapters = [Chapter(number=i + 1, title=t[:255]) for i, t in enumerate(parsed.titles)]
        doc.paragraphs = [Paragraph(idx=i, chapter_no=n, text=b.text, markdown=b.markdown, kind=b.kind) for i, (n, b) in enumerate(parsed.blocks)]
        doc.paragraph_count = len(parsed.blocks)
        doc.read_pages = doc.page_count
        doc.status = "queued"
        billing.consume_analysis(db, db.get(User, doc.user_id))
        db.commit()
        jobs.enqueue(doc_id)
    except Exception:
        log.exception("Pembacaan dokumen %s gagal", doc_id)
        db.rollback()
        _fail(db, doc_id, GENERIC)
    finally:
        db.close()
        discard(doc_id)


def recover() -> None:
    with SessionLocal() as db:
        waiting = db.scalars(select(Document.id).where(Document.status == "reading").order_by(Document.id)).all()
        lost = [doc_id for doc_id in waiting if not os.path.exists(queue_path(doc_id))]
        for doc_id in lost:
            _fail(db, doc_id, LOST)
    keep = [doc_id for doc_id in waiting if doc_id not in lost]
    for doc_id in keep:
        enqueue_read(doc_id)
    if os.path.isdir(_folder()):
        for name in os.listdir(_folder()):
            found = re.match(r"^(\d+)", name)
            if name.endswith(".work.pdf") or found is None or int(found.group(1)) not in keep:
                _remove(os.path.join(_folder(), name))
    if waiting:
        log.info("%d dokumen yang sedang dibaca diperiksa ulang.", len(waiting))


def _loop() -> None:
    while True:
        doc_id = _queue.get()
        try:
            process_read(doc_id)
        except Exception:
            log.exception("Pekerja pembaca: dokumen %s dilewati", doc_id)
        finally:
            _queue.task_done()


def start_worker() -> None:
    global _worker
    if _worker is not None:
        return
    recover()
    _worker = threading.Thread(target=_loop, name="reader-worker", daemon=True)
    _worker.start()
