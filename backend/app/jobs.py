import logging
import queue
import threading
from datetime import datetime

from sqlalchemy import select

from .database import SessionLocal
from .ml.analyzer import get_analyzer, summarize
from .models import Document

log = logging.getLogger("uvicorn.error")

_queue: "queue.Queue[int]" = queue.Queue()
_worker: threading.Thread | None = None


def enqueue(doc_id: int) -> None:
    _queue.put(doc_id)


def process(doc_id: int) -> None:
    db = SessionLocal()
    try:
        doc = db.get(Document, doc_id)
        if doc is None:
            return
        doc.status = "analyzing"
        db.commit()
        paras = list(doc.paragraphs)
        results = get_analyzer().analyze([p.text for p in paras])
        for p, r in zip(paras, results):
            p.profanity, p.sexual, p.violence, p.emotion = r["profanity"], r["sexual"], r["violence"], r["emotion"]
        s = summarize(results)
        doc.pct_profanity, doc.pct_sexual, doc.pct_violence = s["pct"]["profanity"], s["pct"]["sexual"], s["pct"]["violence"]
        doc.rating, doc.dominant_emotion = s["rating"], s["emotion"]
        doc.pct_adult, doc.heaviness = s["adult"], s["heaviness"]
        doc.status, doc.analyzed_at = "done", datetime.utcnow()
        db.commit()
    except Exception:
        log.exception("Analisis dokumen %s gagal", doc_id)
        db.rollback()
        doc = db.get(Document, doc_id)
        if doc is not None:
            doc.status = "failed"
            db.commit()
    finally:
        db.close()


def _loop() -> None:
    while True:
        doc_id = _queue.get()
        try:
            process(doc_id)
        except Exception:
            log.exception("Worker analisis: dokumen %s dilewati", doc_id)
        finally:
            _queue.task_done()


def start_worker() -> None:
    global _worker
    if _worker is not None:
        return
    with SessionLocal() as db:
        pending = db.scalars(
            select(Document.id).where(Document.status.in_(("queued", "analyzing"))).order_by(Document.id)
        ).all()
    for doc_id in pending:
        enqueue(doc_id)
    if pending:
        log.info("%d dokumen belum selesai dimasukkan kembali ke antrean.", len(pending))
    _worker = threading.Thread(target=_loop, name="analysis-worker", daemon=True)
    _worker.start()